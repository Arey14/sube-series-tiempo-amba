"""
Verifica que los modelos de `modelos_pronostico.py` no usan información posterior al corte.

Prueba: se reemplazan los valores de `total_amba` posteriores a `fin_train` por basura
(x10). Si el pronóstico no usa el futuro, no puede cambiar. Como control se incluye la
fórmula original del Seasonal Naïve (full_y.loc[fecha - 7 días]), que sí debe fallar.
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import modelos_pronostico as mp
from analisis_series_tiempo_sube import load_and_preprocess_data

HORIZONTE = 90


def naive_original(df, fin_train, horizonte):
    """Fórmula del script original: toma el valor de hace 7 días de la serie completa."""
    futuro = df.loc[pd.Timestamp(fin_train) + pd.Timedelta(days=1):].iloc[:horizonte]
    y = df['total_amba'] / 1e6
    return pd.Series([y.loc[d - pd.Timedelta(days=7)] for d in futuro.index], index=futuro.index)


def main():
    df = load_and_preprocess_data()
    df = df[df.index >= '2022-01-01'].copy()
    fin_train = df.index[-HORIZONTE - 1]

    sucio = df.copy()
    sucio.loc[sucio.index > fin_train, 'total_amba'] *= 10

    pruebas = {
        'Seasonal_Naive (corregido)': lambda d: mp.seasonal_naive(d, fin_train, HORIZONTE),
        'Gradient_Boosting (recursivo)': lambda d: mp.gradient_boosting_recursivo(d, fin_train, HORIZONTE),
        'SARIMAX': lambda d: mp.sarimax(d, fin_train, HORIZONTE)[0],
        'Prophet': lambda d: mp.prophet(d, fin_train, HORIZONTE),
        'CONTROL: Seasonal_Naive (original)': lambda d: naive_original(d, fin_train, HORIZONTE),
    }
    print(f"Corte: {fin_train.date()}  Horizonte: {HORIZONTE} días\n")
    ok = True
    for nombre, f in pruebas.items():
        a, b = f(df), f(sucio)
        dif = float(np.max(np.abs(a.values - b.values)))
        sin_fuga = dif < 1e-9
        esperado = not nombre.startswith('CONTROL')
        estado = 'OK' if sin_fuga == esperado else 'FALLA'
        ok &= (sin_fuga == esperado)
        print(f"[{estado}] {nombre:38s} diferencia máxima = {dif:.6f}"
              f"  ({'sin fuga' if sin_fuga else 'USA datos del futuro'})")
    print("\nResultado:", "todas las verificaciones pasaron" if ok else "HAY FALLAS")
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
