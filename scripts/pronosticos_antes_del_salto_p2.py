"""
Pronósticos hechos justo antes de cada salto tarifario (P-2 aplicada a P-1).

El origen móvil de 28 días no sirve para ver cómo un modelo "recibe" un salto: el pronóstico de los días posteriores
casi siempre se hizo con datos que ya incluían parte del salto. Acá, para cada salto de la tabla del estudio de
eventos, el origen es el día anterior al primer aumento del grupo y el horizonte alcanza hasta 28 días después del
último aumento. Ningún modelo recibe información de precios.

Saltos: los de colectivo nacional, tren y subte de tabla_estudio_eventos.csv. El modo del colectivo es el total del
colectivo del AMBA (todas las jurisdicciones). Modelos: los de P-2 con la configuración estándar (el SARIMAX con el
orden identificado para cada serie).

Entradas: data/procesado/serie_sube_diaria_reconstruida.csv, resultados/tablas/tabla_estudio_eventos.csv,
          resultados/tablas/tabla_sarimax_grilla_*.csv
Salida:   data/procesado/pronosticos_p2_saltos.csv (evento, modo, origen, fecha, modelo, real, pronostico)
"""

import os
import sys
import time
import warnings
import pandas as pd

warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pronosticos_p2 as P   # noqa: E402

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERIE = os.path.join(BASE_DIR, "data", "procesado", "serie_sube_diaria_reconstruida.csv")
EVT = os.path.join(BASE_DIR, "resultados", "tablas", "tabla_estudio_eventos.csv")
SALIDA = os.path.join(BASE_DIR, "data", "procesado", "pronosticos_p2_saltos.csv")
COLUMNA = {'colectivo_nacional': ('colectivo', 'colectivo_amba'), 'tren': ('tren', 'tren_amba'), 'subte': ('subte', 'subte_amba')}


def orden(col):
    f = os.path.join(BASE_DIR, "resultados", "tablas", f"tabla_sarimax_grilla_{col}.csv")
    g = pd.read_csv(f)
    g = g[(g.LjungBox_p7 > 0.05) & (g.LjungBox_p14 > 0.05)].sort_values('BIC')
    a, b = g.iloc[0]['orden'].split('x')
    ev = lambda t: tuple(int(x) for x in t.strip('()').split(','))
    return dict(order=ev(a), seasonal_order=ev(b))


def main():
    ev = pd.read_csv(EVT, parse_dates=['desde', 'hasta'])
    ev = ev[ev.modo.isin(COLUMNA)]
    serie = pd.read_csv(SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D').loc['2022-01-01':'2026-09-30']
    hechos = set()
    if os.path.exists(SALIDA):
        prev = pd.read_csv(SALIDA)
        hechos = set(zip(prev.modo, prev.salto_desde))
    for _, e in ev.iterrows():
        modo, col = COLUMNA[e.modo]
        clave = (modo, str(e.desde.date()))
        origen = e.desde - pd.Timedelta(days=1)
        h = (e.hasta - e.desde).days + 29
        s = serie[col] / 1e6
        if clave in hechos or origen + pd.Timedelta(days=h) > s.index[-1] or origen < pd.Timestamp('2022-12-31'):
            continue
        ord_ = orden(col)
        modelos = {
            'naive_7': lambda s, c: P.naive_semanal(s, c, h), 'naive_364': lambda s, c: P.naive_anual(s, c, h),
            'sarimax': lambda s, c: P.sarimax(s, c, h, **ord_)[0], 'prophet': lambda s, c: P.prophet(s, c, h),
            'gradient_boosting': lambda s, c: P.gradient_boosting(s, c, h)}
        t0 = time.time(); filas = []
        for nombre, f in modelos.items():
            try:
                pred = f(s, origen)
            except Exception as ex:
                print('  error', nombre, modo, e.desde.date(), str(ex)[:80], flush=True); continue
            for k, (fecha, p) in enumerate(pred.items(), 1):
                filas.append({'modo': modo, 'salto_desde': e.desde.date(), 'salto_hasta': e.hasta.date(), 'tarifa_x': e.tarifa_x,
                              'cambio_demanda_pct_P1': e.cambio_demanda_pct, 'origen': origen.date(), 'fecha': fecha.date(), 'h': k,
                              'modelo': nombre, 'real': s.loc[fecha], 'pronostico': p})
        pd.DataFrame(filas).to_csv(SALIDA, mode='a', header=not os.path.exists(SALIDA), index=False)
        print(f"{modo} {e.desde.date()} horizonte {h} listo en {time.time() - t0:.0f} s", flush=True)


if __name__ == '__main__':
    main()
