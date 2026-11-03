"""
Sensibilidad de P-2 al tratamiento de los 62 días sin dato en la fuente (ago-2022 y ene-2024).

La serie principal rellena esos días con la reconstrucción desde las transacciones (usos_transacciones.py). Aquí se
reentrenan SARIMAX, Prophet y Gradient Boosting (total AMBA, horizonte de 28 días, mismos 42 cortes) con otras dos
formas de tratar esos días y se compara el ranking:

  reconstruida  serie principal (se usan los pronósticos ya calculados).
  interpolada   los 62 días rellenados por interpolación según el día de la semana (serie_sube_diaria_imputada.csv).
  faltantes     los 62 días quedan vacíos en el entrenamiento (SARIMAX los trata como faltantes; Prophet y Gradient
                Boosting los descartan).

Para que las variantes sean comparables, todas se evalúan contra la serie reconstruida y se excluyen de las métricas
los 62 días reconstruidos (no son datos observados) además de paros y elecciones. Las métricas "sin atípicos" de los
bloques 11 a 13 sí incluyen esos días como objetivo: aquí se informa también la línea base sin ellos.

Entradas: data/procesado/serie_sube_diaria_reconstruida.csv, serie_sube_diaria_imputada.csv, pronosticos_p2_folds.csv
Salidas:  data/procesado/pronosticos_p2_huecos_{interpolada,faltantes}.csv
          resultados/tablas/tabla_p2_huecos_metricas.csv, tabla_p2_huecos_dm.csv
"""

import os
import sys
import warnings
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pronosticos_p2 as P                 # noqa: E402
import analisis_pronosticos_p2 as A        # noqa: E402
import evaluacion_pronosticos as E         # noqa: E402

warnings.filterwarnings('ignore')

BASE_DIR = A.BASE_DIR
IMPUTADA = os.path.join(BASE_DIR, "data", "procesado", "serie_sube_diaria_imputada.csv")
MODELOS = ['sarimax', 'prophet', 'gradient_boosting']


def series():
    rec = pd.read_csv(A.SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')
    imp = pd.read_csv(IMPUTADA, parse_dates=['fecha']).set_index('fecha').asfreq('D')
    ref = rec['total_amba'].loc[E.INICIO:E.FIN] / 1e6
    marcas = rec['imputado'].loc[E.INICIO:E.FIN].astype(bool)
    inter = imp['total_amba'].loc[E.INICIO:E.FIN] / 1e6
    falt = ref.copy(); falt[marcas] = float('nan')
    return ref, marcas, {'interpolada': inter, 'faltantes': falt}


def correr(nombre, serie, ref):
    salida = os.path.join(BASE_DIR, "data", "procesado", f"pronosticos_p2_huecos_{nombre}.csv")
    hechos = set(pd.read_csv(salida, parse_dates=['origen'])['origen'].unique()) if os.path.exists(salida) else set()
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
        pd.DataFrame(filas).to_csv(salida, mode='a', header=not os.path.exists(salida), index=False)
        print(nombre, 'corte', k, c.date(), flush=True)
    return pd.read_csv(salida, parse_dates=['origen', 'fecha'])


def main():
    ref, marcas, variantes = series()
    base = A.preparar()
    base = base[base.modelo.isin(MODELOS)].copy()
    info = base[base.modelo == 'gradient_boosting'].set_index('fecha')[['tipo_dia', 'atipico']]
    info = info[~info.index.duplicated()]
    partes = []
    for nombre, s in [('reconstruida', None)] + list(variantes.items()):
        if s is None:
            d = base.copy()
        else:
            d = correr(nombre, s, ref)
            d['error'] = d.pronostico - d.real; d['abs_error'] = d.error.abs(); d['pct_error'] = d.abs_error / d.real * 100
            d['tipo_dia'] = d.fecha.map(info.tipo_dia); d['atipico'] = d.fecha.map(info.atipico)
            escala = base.drop_duplicates('origen').set_index('origen')['escala']
            d['ase'] = d.abs_error / d.origen.map(escala)
        d['variante'] = nombre; partes.append(d)
    todo = pd.concat(partes, ignore_index=True)
    todo['reconstruido'] = todo.fecha.map(marcas).fillna(False).astype(bool)
    # Un pronóstico fuera de rango (más de 20 millones, cuando la serie ronda 3-5) es una divergencia numérica del ajuste:
    # se informa y ese corte se excluye en todas las variantes para que la comparación siga siendo sobre los mismos días.
    div = todo[todo.pronostico.abs() > 20].groupby(['variante', 'modelo']).origen.unique()
    print('Cortes con pronóstico divergente:'); print(div.to_string() if len(div) else 'ninguno')
    todo = todo[~todo.origen.isin(todo[todo.pronostico.abs() > 20].origen.unique())]

    filas, dms = [], []
    muestras = {'sin atípicos (como bloque 11)': lambda x: x[~x.atipico],
                'sin atípicos ni días reconstruidos': lambda x: x[~x.atipico & ~x.reconstruido]}
    for etiqueta, f in muestras.items():
        for (v, m), g in f(todo).groupby(['variante', 'modelo']):
            r = A.metricas(g); r['muestra'] = etiqueta; r['variante'] = v; r['modelo'] = m; filas.append(r)
        for v, g in f(todo).groupby('variante'):
            for a, b in [('gradient_boosting', 'sarimax'), ('gradient_boosting', 'prophet'), ('prophet', 'sarimax')]:
                dif, ee, p, n = A.dm_test(g, a, b)
                dms.append({'muestra': etiqueta, 'variante': v, 'modelo': a, 'contra': b, 'dif_MAE': round(dif, 4), 'error_std_HAC': round(ee, 4), 'p_valor': round(p, 4), 'dias': n})
    t = pd.DataFrame(filas)[['muestra', 'variante', 'modelo', 'dias', 'MAE', 'RMSE', 'MAPE_pct', 'sesgo', 'MASE']].round(3)
    t.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_huecos_metricas.csv'), index=False)
    d = pd.DataFrame(dms); d.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_huecos_dm.csv'), index=False)
    for etiqueta in muestras:
        print('\n' + etiqueta)
        print(t[t.muestra == etiqueta].pivot(index='modelo', columns='variante', values='MASE').to_string())
        print(t[t.muestra == etiqueta].pivot(index='modelo', columns='variante', values='MAE').to_string())
    print('\nDiebold-Mariano'); print(d.to_string(index=False))
    print('\nCortes que cubren días reconstruidos:', sorted(todo[todo.reconstruido].origen.dt.date.unique()))


if __name__ == '__main__':
    main()
