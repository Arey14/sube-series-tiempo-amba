"""
Evaluación con origen móvil (rolling origin) de los modelos de pronóstico de P-2.

Para cada corte, desde el 30-jun-2023 y cada 28 días, el modelo se ajusta con todo lo anterior al corte (ventana
creciente desde el 1-ene-2022) y pronostica los 28 días siguientes. Los bloques de prueba no se solapan y cubren
todos los días hasta el 30-sep-2026 (octubre de 2026 es preliminar y queda afuera).

Modelos principales: naive_7 (repite la última semana), naive_364 (mismo día del año anterior), sarimax
(orden elegido en identificacion_sarimax.py), prophet, gradient_boosting. Variantes para explicar diferencias:
sarimax_sin_anual (sin estacionalidad anual), sarimax_orden_original (orden (1,1,1)x(1,1,1,7) del repositorio).

El resultado se guarda de forma incremental (permite retomar si se interrumpe).

Entrada: data/procesado/serie_sube_diaria_reconstruida.csv
Salida:  data/procesado/pronosticos_p2_folds.csv (origen, fecha, h, modelo, real, pronostico)
"""

import os
import sys
import time
import warnings
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pronosticos_p2 as P   # noqa: E402

warnings.filterwarnings('ignore')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERIE = os.path.join(BASE_DIR, "data", "procesado", "serie_sube_diaria_reconstruida.csv")
ABLACIONES = 'ablaciones' in sys.argv
COL = next((a.split('=')[1] for a in sys.argv if a.startswith('col=')), 'total_amba')   # col=colectivo_amba, tren_amba, subte_amba
if COL != 'total_amba':
    nombre_salida = f"pronosticos_p2_{COL}.csv"
else:
    nombre_salida = "pronosticos_p2_ablaciones.csv" if ABLACIONES else "pronosticos_p2_folds.csv"
SALIDA = os.path.join(BASE_DIR, "data", "procesado", nombre_salida)

INICIO, FIN = '2022-01-01', '2026-09-30'
PRIMER_CORTE = '2023-06-30'
HORIZONTE = 28
ORDEN_SARIMAX = dict(order=(2, 0, 1), seasonal_order=(0, 1, 1, 7))


def orden_identificado(col):
    """Lee el orden elegido por BIC con residuos sin autocorrelación (identificacion_sarimax.py) para la serie `col`."""
    f = os.path.join(BASE_DIR, "resultados", "tablas", f"tabla_sarimax_grilla_{col}.csv")
    if not os.path.exists(f):
        return ORDEN_SARIMAX
    g = pd.read_csv(f)
    g = g[(g.LjungBox_p7 > 0.05) & (g.LjungBox_p14 > 0.05)].sort_values('BIC')
    o = g.iloc[0]['orden']          # formato (p,0,q)x(P,1,Q,7)
    a, b = o.split('x')
    ev = lambda t: tuple(int(x) for x in t.strip('()').split(','))
    return dict(order=ev(a), seasonal_order=ev(b))


def cortes(serie):
    out, c = [], pd.Timestamp(PRIMER_CORTE)
    while c + pd.Timedelta(days=HORIZONTE) <= serie.index[-1]:
        out.append(c); c += pd.Timedelta(days=HORIZONTE)
    return out


def main():
    serie = pd.read_csv(SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')[COL].loc[INICIO:FIN] / 1e6
    assert serie.notna().all()
    hechos = set()
    if os.path.exists(SALIDA):
        prev = pd.read_csv(SALIDA, parse_dates=['origen'])
        hechos = set(prev['origen'].unique())
    modelos = {
        'naive_7': lambda s, c: P.naive_semanal(s, c, HORIZONTE),
        'naive_364': lambda s, c: P.naive_anual(s, c, HORIZONTE),
        'sarimax': lambda s, c: P.sarimax(s, c, HORIZONTE, **ORDEN_SARIMAX)[0],
        'sarimax_sin_anual': lambda s, c: P.sarimax(s, c, HORIZONTE, usar_anual=False, **ORDEN_SARIMAX)[0],
        'sarimax_orden_original': lambda s, c: P.sarimax(s, c, HORIZONTE, order=(1, 1, 1), seasonal_order=(1, 1, 1, 7))[0],
        'prophet': lambda s, c: P.prophet(s, c, HORIZONTE),
        'gradient_boosting': lambda s, c: P.gradient_boosting(s, c, HORIZONTE),
    }
    if COL != 'total_amba':
        ord_ = orden_identificado(COL)
        print('Serie', COL, 'orden SARIMAX', ord_, flush=True)
        modelos = {
            'naive_7': modelos['naive_7'], 'naive_364': modelos['naive_364'],
            'sarimax': lambda s, c: P.sarimax(s, c, HORIZONTE, **ord_)[0],
            'sarimax_en_logs': lambda s, c: P.sarimax(s, c, HORIZONTE, en_logs=True, **ord_)[0],
            'prophet': modelos['prophet'], 'gradient_boosting': modelos['gradient_boosting'],
        }
    elif ABLACIONES:
        modelos = {
            'sarimax_en_logs': lambda s, c: P.sarimax(s, c, HORIZONTE, en_logs=True, **ORDEN_SARIMAX)[0],
            'gb_solo_calendario': lambda s, c: P.gradient_boosting(s, c, HORIZONTE, con_rezagos=False),
        }
    cs = cortes(serie)
    print(f"{len(cs)} cortes, de {cs[0].date()} a {cs[-1].date()}; ya hechos: {len(hechos)}", flush=True)
    for k, c in enumerate(cs, 1):
        if c in hechos:
            continue
        t0 = time.time(); filas = []
        for nombre, f in modelos.items():
            try:
                pred = f(serie, c)
            except Exception as e:
                print('  error', nombre, c.date(), str(e)[:80], flush=True); continue
            for h, (fecha, p) in enumerate(pred.items(), 1):
                filas.append({'origen': c, 'fecha': fecha, 'h': h, 'modelo': nombre, 'real': serie.loc[fecha], 'pronostico': p})
        pd.DataFrame(filas).to_csv(SALIDA, mode='a', header=not os.path.exists(SALIDA), index=False)
        print(f"corte {k}/{len(cs)} {c.date()} listo en {time.time() - t0:.0f} s", flush=True)


if __name__ == '__main__':
    main()
