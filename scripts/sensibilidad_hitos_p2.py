"""
Sensibilidad de P-2 al entrenamiento con y sin los días de paro y de elección.

La serie principal se entrena con todos los días, incluidos los de paro y de elección (que distorsionan la demanda y que
ningún método anticipa); esos días solo se excluyen al calcular las métricas. Aquí se prueba el otro enfoque: reentrenar
SARIMAX, Prophet y Gradient Boosting (total AMBA, horizonte de 28 días, mismos 42 cortes) con esos días vacíos en el
entrenamiento (SARIMAX los trata como faltantes; Prophet y Gradient Boosting los descartan como objetivo) y comparar.

  con_hitos         serie principal (se usan los pronósticos ya calculados).
  sin_hitos         los días de paro y de elección (data/hitos/hitos_paros_elecciones.csv) quedan vacíos en el entrenamiento.
  hitos_imputados   esos días se reemplazan por el valor habitual: la mediana del mismo día de la semana en las cuatro
                    semanas anteriores (sin feriados, paros ni elecciones). Solo usa el pasado, de modo que no hay fuga.
                    Se agrega porque con huecos el SARIMAX pierde las diferencias estacionales que cruzan cada vacío.

Los feriados no se quitan: son predecibles y los modelos los aprenden con el calendario.

Las dos variantes se evalúan sobre los mismos días: los 1.161 días sin paros ni elecciones del bloque 11 (en ellos los
pronósticos no usan esos días de ninguna manera, solo cambia lo que el modelo aprendió). Se informa también el error
por tipo de día y, aparte, el error en los días de paro y de elección.

Un pronóstico fuera de rango (más de 20 millones) o vacío es una falla numérica del ajuste: se informa y ese corte se
excluye en todas las variantes para comparar los mismos días.

Entradas: data/procesado/serie_sube_diaria_reconstruida.csv, pronosticos_p2_folds.csv, data/hitos/hitos_paros_elecciones.csv
Salidas:  data/procesado/pronosticos_p2_sin_hitos.csv, pronosticos_p2_hitos_imputados.csv
          resultados/tablas/tabla_p2_sin_hitos_metricas.csv, tabla_p2_sin_hitos_tipo_dia.csv, tabla_p2_sin_hitos_dm.csv
          resultados/figuras/fig28_p2_sin_hitos.png
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import holidays
import statsmodels.api as sm
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pronosticos_p2 as P                 # noqa: E402
import analisis_pronosticos_p2 as A        # noqa: E402
import evaluacion_pronosticos as E         # noqa: E402

warnings.filterwarnings('ignore')
plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = A.BASE_DIR
MODELOS = ['sarimax', 'prophet', 'gradient_boosting']


def correr(serie, ref, nombre):
    SALIDA = os.path.join(BASE_DIR, "data", "procesado", f"pronosticos_p2_{nombre}.csv")
    hechos = set(pd.read_csv(SALIDA, parse_dates=['origen'])['origen'].unique()) if os.path.exists(SALIDA) else set()
    modelos = {
        'sarimax': lambda s, c: P.sarimax(s, c, E.HORIZONTE, **E.ORDEN_SARIMAX)[0],
        'prophet': lambda s, c: P.prophet(s, c, E.HORIZONTE),
        'gradient_boosting': lambda s, c: P.gradient_boosting(s, c, E.HORIZONTE),
    }
    for k, c in enumerate(E.cortes(serie), 1):
        if c in hechos:
            continue
        filas = []
        for m, f in modelos.items():
            for h, (fecha, p) in enumerate(f(serie, c).items(), 1):
                filas.append({'origen': c, 'fecha': fecha, 'h': h, 'modelo': m, 'real': ref.loc[fecha], 'pronostico': p})
        pd.DataFrame(filas).to_csv(SALIDA, mode='a', header=not os.path.exists(SALIDA), index=False)
        print('corte', k, c.date(), flush=True)
    return pd.read_csv(SALIDA, parse_dates=['origen', 'fecha'])


def main():
    rec = pd.read_csv(A.SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')
    ref = rec['total_amba'].loc[E.INICIO:E.FIN] / 1e6
    evt = pd.read_csv(A.EVT, parse_dates=['fecha'])
    sin = ref.copy(); sin[sin.index.isin(evt.fecha)] = float('nan')
    print(f'{int(sin.isna().sum())} días de paro o elección vacíos en el entrenamiento')
    fer = set(pd.Timestamp(f) for f in holidays.Argentina(years=range(2021, 2028)))
    excl = set(evt.fecha) | fer
    imp = ref.copy()
    for f in sin.index[sin.isna()]:
        previos = [imp.get(f - pd.Timedelta(days=7 * k)) for k in range(1, 5) if (f - pd.Timedelta(days=7 * k)) not in excl]
        previos = [v for v in previos if v is not None and v == v]
        if previos:
            imp[f] = float(pd.Series(previos).median())
    variantes = {'sin_hitos': sin, 'hitos_imputados': imp}

    base = A.preparar()
    base = base[base.modelo.isin(MODELOS)].copy()
    info = base[base.modelo == 'gradient_boosting'].drop_duplicates('fecha').set_index('fecha')[['tipo_dia', 'atipico']]
    escala = base.drop_duplicates('origen').set_index('origen')['escala']
    base['variante'] = 'con_hitos'
    partes = [base]
    for nombre, serie in variantes.items():
        d = correr(serie, ref, nombre)
        d['error'] = d.pronostico - d.real; d['abs_error'] = d.error.abs(); d['pct_error'] = d.abs_error / d.real * 100
        d['tipo_dia'] = d.fecha.map(info.tipo_dia); d['atipico'] = d.fecha.map(info.atipico)
        d['ase'] = d.abs_error / d.origen.map(escala)
        d['variante'] = nombre
        partes.append(d)
    todo = pd.concat(partes, ignore_index=True)
    malo = (todo.pronostico.abs() > 20) | todo.pronostico.isna()
    div = todo[malo].groupby(['variante', 'modelo']).origen.unique()
    print('Cortes con pronóstico divergente o vacío:'); print(div.to_string() if len(div) else 'ninguno')
    todo = todo[~todo.origen.isin(todo[malo].origen.unique())]

    filas, tipos, dms = [], [], []
    for (v, m), g in todo[~todo.atipico].groupby(['variante', 'modelo']):
        r = A.metricas(g); r['variante'] = v; r['modelo'] = m; r['muestra'] = 'sin atípicos'; filas.append(r)
    for (v, m), g in todo[todo.atipico].groupby(['variante', 'modelo']):
        r = A.metricas(g); r['variante'] = v; r['modelo'] = m; r['muestra'] = 'solo paros y elecciones'; filas.append(r)
    for (v, m, t), g in todo[~todo.atipico].groupby(['variante', 'modelo', 'tipo_dia']):
        r = A.metricas(g); r['variante'] = v; r['modelo'] = m; r['tipo_dia'] = t; tipos.append(r)
    sub = todo[~todo.atipico]
    for v, g in sub.groupby('variante'):
        for a, b in [('gradient_boosting', 'sarimax'), ('gradient_boosting', 'prophet'), ('prophet', 'sarimax')]:
            dif, ee, p, n = A.dm_test(g, a, b)
            dms.append({'variante': v, 'modelo': a, 'contra': b, 'dif_MAE': round(dif, 4), 'error_std_HAC': round(ee, 4), 'p_valor': round(p, 4), 'dias': n})
    # el mismo modelo con y sin hitos: ¿cambia el error?
    for v in variantes:
        for m in MODELOS:
            x = sub[(sub.modelo == m)]
            w = x.pivot(index='fecha', columns='variante', values='abs_error').dropna()
            dif = (w[v] - w['con_hitos']).sort_index()
            r = sm.OLS(dif.values, np.ones(len(dif))).fit(cov_type='HAC', cov_kwds={'maxlags': 27})
            dms.append({'variante': f'{v} - con_hitos', 'modelo': m, 'contra': m, 'dif_MAE': round(float(r.params[0]), 4), 'error_std_HAC': round(float(r.bse[0]), 4),
                        'p_valor': round(float(r.pvalues[0]), 4), 'dias': len(dif)})
    t = pd.DataFrame(filas)[['muestra', 'variante', 'modelo', 'dias', 'MAE', 'RMSE', 'MAPE_pct', 'sesgo', 'MASE']].round(3)
    t.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_sin_hitos_metricas.csv'), index=False)
    tt = pd.DataFrame(tipos)[['tipo_dia', 'variante', 'modelo', 'dias', 'MAE', 'MAPE_pct', 'sesgo', 'MASE']].round(3)
    tt.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_sin_hitos_tipo_dia.csv'), index=False)
    dd = pd.DataFrame(dms); dd.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_sin_hitos_dm.csv'), index=False)

    for muestra in ['sin atípicos', 'solo paros y elecciones']:
        print('\n' + muestra)
        for col in ['MASE', 'MAE', 'MAPE_pct']:
            print(col); print(t[t.muestra == muestra].pivot(index='modelo', columns='variante', values=col).to_string())
    print('\nMAE por tipo de día'); print(tt.pivot_table(index=['modelo', 'tipo_dia'], columns='variante', values='MAE').to_string())
    print('\nDiebold-Mariano'); print(dd.to_string(index=False))

    orden_v = ['con_hitos', 'sin_hitos', 'hitos_imputados']
    p = t[t.muestra == 'sin atípicos'].pivot(index='modelo', columns='variante', values='MASE').loc[MODELOS][orden_v]
    q = tt.pivot_table(index=['modelo', 'tipo_dia'], columns='variante', values='MAE')
    fig, ax = plt.subplots(1, 2, figsize=(14, 4.8))
    p.plot(kind='bar', ax=ax[0], width=0.75, color=['#7f8c8d', '#27ae60', '#2980b9']); ax[0].set_ylabel('MASE (menor es mejor)'); ax[0].set_xlabel('')
    ax[0].set_title('Total AMBA, 28 días (sin atípicos): entrenar con y sin hitos', fontweight='bold'); ax[0].tick_params(axis='x', rotation=0)
    r = (1 - q['hitos_imputados'] / q['con_hitos']).mul(100).unstack('tipo_dia').loc[MODELOS]
    r.plot(kind='bar', ax=ax[1], width=0.8); ax[1].axhline(0, color='k', lw=0.8)
    ax[1].set_ylabel('% de mejora del MAE con hitos imputados\n(positivo = mejor que con hitos)'); ax[1].set_xlabel('')
    ax[1].set_title('Cambio del error según el tipo de día (hitos imputados)', fontweight='bold'); ax[1].tick_params(axis='x', rotation=0); ax[1].legend(title='tipo de día', fontsize=8)
    plt.tight_layout(); plt.savefig(os.path.join(A.FIG_DIR, 'fig28_p2_sin_hitos.png'), dpi=200); plt.close()


if __name__ == '__main__':
    main()
