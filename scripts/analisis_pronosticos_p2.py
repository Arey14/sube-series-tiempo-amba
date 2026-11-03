"""
Análisis de la evaluación con origen móvil (P-2): errores globales, por tipo de día, por horizonte y por período;
prueba de Diebold-Mariano; intervalos de predicción por método conforme (split conformal).

Métricas: MAE, RMSE, MAPE, sesgo (pronóstico - real) y MASE (error absoluto medio dividido por el error absoluto
medio del naive de 7 días dentro de la muestra de entrenamiento de cada corte; menor a 1 es mejor que el naive).
"Sin atípicos" excluye los días de paro y de elección de data/hitos/hitos_paros_elecciones.csv, que ningún modelo
puede anticipar con el calendario.

Diebold-Mariano: diferencia del error absoluto diario entre dos modelos, con errores estándar HAC (rezagos 27).
Intervalos: para cada corte desde el noveno, el cuantil del error absoluto de los cortes anteriores en el mismo
horizonte (±3 días) da el semiancho del intervalo; se informa cobertura observada y semiancho medio.

Entradas: data/procesado/pronosticos_p2_folds.csv, data/procesado/serie_sube_diaria_reconstruida.csv,
          data/hitos/hitos_paros_elecciones.csv
Salidas:  resultados/tablas/tabla_p2_*.csv; resultados/figuras/fig20_p2_error_por_tipo_dia.png, fig21_p2_error_por_corte.png
"""

import os
import warnings
import numpy as np
import pandas as pd
import holidays
import statsmodels.api as sm
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')
plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FOLDS = os.path.join(BASE_DIR, "data", "procesado", "pronosticos_p2_folds.csv")
SERIE = os.path.join(BASE_DIR, "data", "procesado", "serie_sube_diaria_reconstruida.csv")
EVT = os.path.join(BASE_DIR, "data", "hitos", "hitos_paros_elecciones.csv")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")
FIG_DIR = os.path.join(BASE_DIR, "resultados", "figuras")
PRINCIPALES = ['naive_7', 'naive_364', 'sarimax', 'prophet', 'gradient_boosting']
VARIANTES = ['sarimax_sin_anual', 'sarimax_orden_original']


def preparar():
    d = pd.read_csv(FOLDS, parse_dates=['origen', 'fecha'])
    abl = FOLDS.replace('folds', 'ablaciones')
    if os.path.exists(abl):
        d = pd.concat([d, pd.read_csv(abl, parse_dates=['origen', 'fecha'])], ignore_index=True)
    d['error'] = d['pronostico'] - d['real']
    d['abs_error'] = d['error'].abs()
    d['pct_error'] = d['abs_error'] / d['real'] * 100
    fer = holidays.Argentina(years=range(2022, 2027))
    d['tipo_dia'] = np.where(d.fecha.isin([pd.Timestamp(f) for f in fer]), 'feriado',
                     np.where(d.fecha.dt.dayofweek == 5, 'sábado', np.where(d.fecha.dt.dayofweek == 6, 'domingo', 'hábil')))
    evt = pd.read_csv(EVT, parse_dates=['fecha'])
    d['atipico'] = d.fecha.isin(evt['fecha'])
    serie = pd.read_csv(SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')['total_amba'] / 1e6
    escala = {o: serie.loc[:o].diff(7).abs().mean() for o in d['origen'].unique()}
    d['escala'] = d['origen'].map(escala)
    d['ase'] = d['abs_error'] / d['escala']
    d['periodo'] = np.where(d.fecha < '2024-01-01', '2023 (jul-dic)', d.fecha.dt.year.astype(str))
    d['bucket_h'] = pd.cut(d['h'], [0, 7, 14, 21, 28], labels=['1-7', '8-14', '15-21', '22-28'])
    return d


def metricas(g):
    return pd.Series({'dias': len(g), 'MAE': g.abs_error.mean(), 'RMSE': np.sqrt((g.error ** 2).mean()), 'MAPE_pct': g.pct_error.mean(),
                      'sesgo': g.error.mean(), 'MASE': g.ase.mean()})


def dm_test(d, a, b, lag=27):
    x = d[d.modelo == a].set_index('fecha')['abs_error']; y = d[d.modelo == b].set_index('fecha')['abs_error']
    dif = (x - y).dropna().sort_index()
    r = sm.OLS(dif.values, np.ones(len(dif))).fit(cov_type='HAC', cov_kwds={'maxlags': lag})
    return float(r.params[0]), float(r.bse[0]), float(r.pvalues[0]), len(dif)


def intervalos(d, modelo, niveles=(0.8, 0.95), min_cortes=8):
    g = d[d.modelo == modelo].copy()
    origenes = sorted(g.origen.unique())
    filas = []
    for k, o in enumerate(origenes):
        if k < min_cortes:
            continue
        ant = g[g.origen.isin(origenes[:k])]
        act = g[g.origen == o]
        for h, fila in act.set_index('h').iterrows():
            e = ant[(ant.h >= h - 3) & (ant.h <= h + 3)]['abs_error']
            rec = {'modelo': modelo, 'h': h, 'real': fila['real'], 'pron': fila['pronostico'], 'fecha': fila['fecha']}
            for n in niveles:
                q = e.quantile(n); rec[f'ancho_{int(n*100)}'] = q
                rec[f'cubre_{int(n*100)}'] = abs(fila['pronostico'] - fila['real']) <= q
            filas.append(rec)
    return pd.DataFrame(filas)


def main():
    d = preparar()
    print(f"{d.origen.nunique()} cortes, {d.fecha.min().date()} a {d.fecha.max().date()}, modelos: {sorted(d.modelo.unique())}")
    todos = list(d.modelo.unique())

    glob = []
    for etiqueta, sub in [('todos los días', d), ('sin atípicos', d[~d.atipico])]:
        m = sub.groupby('modelo').apply(metricas); m.insert(0, 'muestra', etiqueta); glob.append(m.reset_index())
    t_glob = pd.concat(glob).round(3); t_glob.to_csv(os.path.join(TABLA_DIR, 'tabla_p2_metricas_globales.csv'), index=False)
    print('\nMétricas globales'); print(t_glob.to_string(index=False))

    sub = d[~d.atipico]
    t_tipo = sub.groupby(['tipo_dia', 'modelo']).apply(metricas).reset_index().round(3)
    t_tipo.to_csv(os.path.join(TABLA_DIR, 'tabla_p2_metricas_por_tipo_dia.csv'), index=False)
    print('\nMAE por tipo de día (sin atípicos)'); print(t_tipo.pivot(index='modelo', columns='tipo_dia', values='MAE').round(3).to_string())
    print('\nMAPE % por tipo de día'); print(t_tipo.pivot(index='modelo', columns='tipo_dia', values='MAPE_pct').round(1).to_string())

    t_h = sub.groupby(['bucket_h', 'modelo']).apply(metricas).reset_index().round(3)
    t_h.to_csv(os.path.join(TABLA_DIR, 'tabla_p2_metricas_por_horizonte.csv'), index=False)
    print('\nMAE por horizonte (sin atípicos)'); print(t_h.pivot(index='modelo', columns='bucket_h', values='MAE').round(3).to_string())

    t_per = sub.groupby(['periodo', 'modelo']).apply(metricas).reset_index().round(3)
    t_per.to_csv(os.path.join(TABLA_DIR, 'tabla_p2_metricas_por_periodo.csv'), index=False)
    print('\nMAE por período (sin atípicos)'); print(t_per.pivot(index='modelo', columns='periodo', values='MAE').round(3).to_string())

    mejor = t_glob[(t_glob.muestra == 'sin atípicos') & t_glob.modelo.isin(PRINCIPALES)].sort_values('MAE').modelo.iloc[0]
    filas = []
    for a in todos:
        for b in ['naive_7', mejor]:
            if a == b:
                continue
            dif, ee, p, n = dm_test(sub, a, b)
            filas.append({'modelo': a, 'contra': b, 'dif_MAE': round(dif, 3), 'error_std_HAC': round(ee, 3), 'p_valor': round(p, 4), 'dias': n})
    t_dm = pd.DataFrame(filas); t_dm.to_csv(os.path.join(TABLA_DIR, 'tabla_p2_diebold_mariano.csv'), index=False)
    print(f'\nDiebold-Mariano (sin atípicos; dif_MAE negativa = el modelo es mejor que "contra"); mejor modelo principal: {mejor}')
    print(t_dm.to_string(index=False))

    filas = []
    for m in PRINCIPALES:
        if m.startswith('naive_364') and d[d.modelo == m].pronostico.isna().any():
            pass
        iv = intervalos(d[~d.pronostico.isna()], m)
        if len(iv):
            filas.append({'modelo': m, 'dias': len(iv), 'cobertura_80': round(iv.cubre_80.mean(), 3), 'semiancho_80': round(iv.ancho_80.mean(), 3),
                          'cobertura_95': round(iv.cubre_95.mean(), 3), 'semiancho_95': round(iv.ancho_95.mean(), 3)})
    t_iv = pd.DataFrame(filas); t_iv.to_csv(os.path.join(TABLA_DIR, 'tabla_p2_intervalos.csv'), index=False)
    print('\nIntervalos por método conforme (nominal 80% y 95%)'); print(t_iv.to_string(index=False))

    piv = t_tipo.pivot(index='modelo', columns='tipo_dia', values='MAE').loc[[m for m in PRINCIPALES if m in t_tipo.modelo.values]]
    piv[['hábil', 'sábado', 'domingo', 'feriado']].plot(kind='bar', figsize=(10, 4.5), width=0.8)
    plt.ylabel('Error absoluto medio (millones de usuarios)'); plt.title('Error por tipo de día (sin atípicos, horizonte 28 días)', fontweight='bold')
    plt.xticks(rotation=0); plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig20_p2_error_por_tipo_dia.png'), dpi=200); plt.close()

    por_corte = sub[sub.modelo.isin(PRINCIPALES)].groupby(['origen', 'modelo'])['abs_error'].mean().unstack()
    por_corte.plot(figsize=(11, 4.5), marker='o', ms=3)
    plt.ylabel('Error absoluto medio del bloque (millones)'); plt.title('Error de cada bloque de 28 días', fontweight='bold')
    plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig21_p2_error_por_corte.png'), dpi=200); plt.close()


if __name__ == '__main__':
    main()
