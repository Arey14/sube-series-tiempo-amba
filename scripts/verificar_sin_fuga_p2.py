"""
Verifica que los modelos de `pronosticos_p2.py` no usan información posterior al corte.

Prueba: se reemplazan los valores de la serie posteriores a `fin_train` por basura (x10). Si el pronóstico no usa el
futuro, no puede cambiar. Se corre en tres cortes de la evaluación con origen móvil.

Entrada: data/procesado/serie_sube_diaria_reconstruida.csv
Salida:  por pantalla, diferencia máxima entre el pronóstico con la serie real y con la serie sucia, por modelo y corte.
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pronosticos_p2 as P   # noqa: E402

warnings.filterwarnings('ignore')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERIE = os.path.join(BASE_DIR, "data", "procesado", "serie_sube_diaria_reconstruida.csv")
CORTES = ['2023-06-30', '2024-09-20', '2025-12-05']
H = 28
ORDEN = dict(order=(2, 0, 1), seasonal_order=(0, 1, 1, 7))


def main():
    s = pd.read_csv(SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')['total_amba'].loc['2022-01-01':'2026-09-30'] / 1e6
    modelos = {
        'naive_7': lambda x, c: P.naive_semanal(x, c, H),
        'naive_364': lambda x, c: P.naive_anual(x, c, H),
        'sarimax': lambda x, c: P.sarimax(x, c, H, **ORDEN)[0],
        'prophet': lambda x, c: P.prophet(x, c, H),
        'gradient_boosting': lambda x, c: P.gradient_boosting(x, c, H),
    }
    peor = 0.0
    for c in CORTES:
        sucio = s.copy(); sucio.loc[sucio.index > pd.Timestamp(c)] *= 10
        for nombre, f in modelos.items():
            dif = float(np.nanmax(np.abs(f(s, c).values - f(sucio, c).values)))
            peor = max(peor, dif)
            print(f"corte {c}  {nombre:18s} diferencia máxima {dif:.2e}")
    print('\nOK: ningún modelo usa el futuro' if peor < 1e-9 else f'\nATENCIÓN: hay fuga (diferencia máxima {peor:.3g})')


if __name__ == '__main__':
    main()
