"""
Modelo híbrido (P-2): usar cada método en el tipo de día donde rinde mejor.

Motivación: en tren y subte los modelos aditivos (SARIMAX, Prophet) ganan en días hábiles y el Gradient Boosting gana
en feriados y fines de semana. Se prueban tres combinaciones, todas armadas con los pronósticos ya calculados en la
evaluación con origen móvil (no se reajusta ningún modelo):

  hibrido_fijo         días hábiles con SARIMAX; sábados, domingos y feriados con Gradient Boosting. Regla fijada a
                       partir del patrón visto en toda la muestra de prueba, así que es una cota optimista.
  hibrido_walkforward  para cada corte y tipo de día, usa el método de menor error absoluto medio en los cortes
                       ANTERIORES (candidatos: SARIMAX, Prophet, Gradient Boosting; con menos de 8 cortes previos usa
                       Gradient Boosting). Sin mirar el futuro: es la versión honesta.
  promedio_sarimax_gb  promedio simple de SARIMAX y Gradient Boosting (referencia: combinar sin regla).

Los bloques de prueba no se solapan (28 días cada uno), por lo que todos los días de los cortes anteriores son
anteriores al corte actual. Se comparan contra el Gradient Boosting y el mejor de los métodos individuales con
Diebold-Mariano (HAC, 27 rezagos). Muestra "sin atípicos", igual que en el resto de P-2.

Entradas: data/procesado/pronosticos_p2_folds.csv (total) y pronosticos_p2_{colectivo,tren,subte}_amba.csv
Salidas:  resultados/tablas/tabla_p2_hibrido_metricas.csv, tabla_p2_hibrido_tipo_dia.csv, tabla_p2_hibrido_dm.csv
          resultados/figuras/fig23_p2_hibrido.png
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analisis_pronosticos_p2 as A              # noqa: E402
import analisis_pronosticos_por_modo as M        # noqa: E402

warnings.filterwarnings('ignore')
plt.style.use('seaborn-v0_8-whitegrid')

CANDIDATOS = ['sarimax', 'prophet', 'gradient_boosting']
HIBRIDOS = ['hibrido_fijo', 'hibrido_walkforward', 'promedio_sarimax_gb']
MIN_CORTES = 8
SERIES = ['total_amba', 'colectivo_amba', 'tren_amba', 'subte_amba']


def cargar(col):
    if col == 'total_amba':
        d = A.preparar()
        d = d[d.modelo.isin(CANDIDATOS + ['naive_7'])].copy()
        return d
    serie = pd.read_csv(A.SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')
    evt = pd.read_csv(A.EVT, parse_dates=['fecha'])
    d = M.preparar(col, serie, evt)
    return d[d.modelo.isin(CANDIDATOS + ['naive_7'])].copy()


def construir(d):
    """Devuelve d con las filas de los tres híbridos agregadas."""
    base = d[d.modelo.isin(CANDIDATOS)]
    piv = base.pivot_table(index=['origen', 'fecha'], columns='modelo', values='pronostico')
    info = base[base.modelo == 'gradient_boosting'].set_index(['origen', 'fecha'])[['h', 'real', 'tipo_dia', 'atipico', 'ase', 'abs_error']]
    escala = (info['abs_error'] / info['ase']).replace([np.inf, -np.inf], np.nan).groupby(level='origen').median()
    info = info.drop(columns=['abs_error', 'ase'])
    x = info.join(piv)
    x['hibrido_fijo'] = np.where(x.tipo_dia == 'hábil', x['sarimax'], x['gradient_boosting'])
    x['promedio_sarimax_gb'] = (x['sarimax'] + x['gradient_boosting']) / 2

    # walk-forward: elección por tipo de día con los cortes anteriores
    x = x.reset_index()
    errores = {m: (x[m] - x['real']).abs() for m in CANDIDATOS}
    x['hibrido_walkforward'] = np.nan
    origenes = sorted(x.origen.unique())
    elegidos = []
    for k, o in enumerate(origenes):
        act = x.origen == o
        for t in x.loc[act, 'tipo_dia'].unique():
            m_t = act & (x.tipo_dia == t)
            if k < MIN_CORTES:
                m = 'gradient_boosting'
            else:
                pasado = (x.origen < o) & (x.tipo_dia == t) & (~x.atipico)
                m = min(CANDIDATOS, key=lambda c: errores[c][pasado].mean())
            x.loc[m_t, 'hibrido_walkforward'] = x.loc[m_t, m]
            elegidos.append({'origen': o, 'tipo_dia': t, 'elegido': m})
    x['escala'] = x.origen.map(escala)

    filas = []
    for h in HIBRIDOS:
        y = x[['origen', 'fecha', 'h', 'real', 'tipo_dia', 'atipico', 'escala']].copy()
        y['modelo'] = h; y['pronostico'] = x[h]
        filas.append(y)
    n = pd.concat(filas, ignore_index=True)
    n['error'] = n['pronostico'] - n['real']; n['abs_error'] = n['error'].abs()
    n['pct_error'] = n['abs_error'] / n['real'] * 100; n['ase'] = n['abs_error'] / n['escala']
    cols = ['origen', 'fecha', 'h', 'modelo', 'real', 'pronostico', 'error', 'abs_error', 'pct_error', 'tipo_dia', 'atipico', 'ase']
    return pd.concat([d[cols], n[cols]], ignore_index=True), pd.DataFrame(elegidos)


def main():
    met, tip, dm, elec = [], [], [], []
    for col in SERIES:
        d, eleg = construir(cargar(col))
        eleg['serie'] = col; elec.append(eleg)
        sub = d[~d.atipico]
        for m, g in sub.groupby('modelo'):
            r = A.metricas(g); r['serie'] = col; r['modelo'] = m; met.append(r)
        for (t, m), g in sub.groupby(['tipo_dia', 'modelo']):
            r = A.metricas(g); r['serie'] = col; r['modelo'] = m; r['tipo_dia'] = t; tip.append(r)
        mejor_ind = sub[sub.modelo.isin(CANDIDATOS)].groupby('modelo').abs_error.mean().idxmin()
        for h in HIBRIDOS:
            for b in sorted({'gradient_boosting', 'sarimax', mejor_ind}):
                dif, ee, p, n = A.dm_test(sub, h, b)
                dm.append({'serie': col, 'modelo': h, 'contra': b, 'dif_MAE': round(dif, 4), 'error_std_HAC': round(ee, 4), 'p_valor': round(p, 4), 'dias': n})
    t_met = pd.DataFrame(met)[['serie', 'modelo', 'dias', 'MAE', 'RMSE', 'MAPE_pct', 'sesgo', 'MASE']].round(3)
    t_met.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_hibrido_metricas.csv'), index=False)
    t_tip = pd.DataFrame(tip)[['serie', 'tipo_dia', 'modelo', 'dias', 'MAE', 'MAPE_pct', 'MASE']].round(3)
    t_tip.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_hibrido_tipo_dia.csv'), index=False)
    t_dm = pd.DataFrame(dm); t_dm.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_hibrido_dm.csv'), index=False)
    t_el = pd.concat(elec); t_el.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_hibrido_elecciones.csv'), index=False)

    orden = ['naive_7', 'sarimax', 'prophet', 'gradient_boosting'] + HIBRIDOS
    for col in SERIES:
        print(f"\n{col} (sin atípicos)")
        print(t_met[t_met.serie == col].drop(columns='serie').set_index('modelo').loc[orden].to_string())
    print('\nMAE por tipo de día')
    for col in SERIES:
        print(col); print(t_tip[t_tip.serie == col].pivot(index='modelo', columns='tipo_dia', values='MAE').loc[orden].to_string())
    print('\nDiebold-Mariano (dif_MAE negativa = el híbrido es mejor que "contra")'); print(t_dm.to_string(index=False))
    print('\nMétodo elegido por el walk-forward (cantidad de cortes)')
    print(t_el[t_el.origen >= sorted(t_el.origen.unique())[MIN_CORTES]].groupby(['serie', 'tipo_dia', 'elegido']).size().unstack(fill_value=0).to_string())

    piv = t_met.pivot(index='modelo', columns='serie', values='MASE').loc[orden][SERIES]
    piv.plot(kind='bar', figsize=(11, 4.8), width=0.8); plt.axhline(1, color='k', lw=0.8, ls='--')
    plt.ylabel('MASE (menor a 1 = mejor que el naive de 7 días)'); plt.xticks(rotation=20)
    plt.title('Híbridos contra métodos individuales, horizonte de 28 días (sin atípicos)', fontweight='bold')
    plt.tight_layout(); plt.savefig(os.path.join(A.FIG_DIR, 'fig23_p2_hibrido.png'), dpi=200); plt.close()


if __name__ == '__main__':
    main()
