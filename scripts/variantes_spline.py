"""Variantes del spline cúbico para completar huecos de 31 días (misma simulación que `calidad_datos.py`).

Pregunta: el spline cúbico aplicado a la serie diaria da un error muy alto (MAPE mediano 76,3%). ¿Se arregla
aplicándolo de otra manera? Se prueban, sobre los mismos 89 bloques ocultos de 31 días:
  - spline_por_dia_semana:  un spline cúbico para cada día de la semana (7 splines, cada uno con un punto por semana).
  - pchip_por_dia_semana:   igual, con el interpolador monótono PCHIP (no oscila).
  - spline_tendencia_x_perfil: un spline sobre la media móvil de 7 días (la serie sin ciclo semanal), multiplicado por
                            el perfil semanal (cociente medio de cada día respecto de la tendencia en los 28 días
                            vecinos al hueco). Combina dos componentes, como en una descomposición.
  - pchip_tendencia_x_perfil y lineal_tendencia_x_perfil: lo mismo con PCHIP y con una recta para la tendencia.
Referencia: lineal_por_dia_semana y spline de `calidad_datos.py`.

Salida: resultados/tablas/tabla_variantes_spline.csv
"""

import os
import sys
import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline, PchipInterpolator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calidad_datos as cd   # noqa: E402


def _ord(ix):
    return ix.map(pd.Timestamp.toordinal).values


def por_dia_semana(s, clase=CubicSpline):
    out = s.copy()
    for d in range(7):
        sub = s[s.index.day_of_week == d]
        k = sub.dropna()
        f = clase(_ord(k.index), k.values)
        m = sub.isna()
        out[sub.index[m]] = f(_ord(sub.index[m]))
    return out


def tendencia_x_perfil(s, clase=CubicSpline, borde=28):
    faltan = s.index[s.isna()]
    ini, fin = faltan[0], faltan[-1]
    k = s.rolling(7, center=True).mean().dropna()
    f = clase(_ord(k.index), k.values)
    tend = pd.Series(f(_ord(s.index)), index=s.index)
    razon = s / tend
    antes = (razon.index >= ini - pd.Timedelta(days=borde)) & (razon.index < ini)
    despues = (razon.index > fin) & (razon.index <= fin + pd.Timedelta(days=borde))
    vec = razon[antes | despues].dropna()
    perfil = vec.groupby(vec.index.day_of_week).mean()
    out = s.copy()
    out[faltan] = [tend[d] * perfil[d.day_of_week] for d in faltan]
    return out


def recta(x, y):
    return lambda z: np.interp(z, x, y)


METODOS = {
    'lineal_por_dia_semana (referencia)': cd.interp_lineal_por_dia_semana,
    'spline (referencia)': cd.interp_spline,
    'spline_por_dia_semana': por_dia_semana,
    'pchip_por_dia_semana': lambda s: por_dia_semana(s, PchipInterpolator),
    'spline_tendencia_x_perfil': tendencia_x_perfil,
    'pchip_tendencia_x_perfil': lambda s: tendencia_x_perfil(s, PchipInterpolator),
    'lineal_tendencia_x_perfil': lambda s: tendencia_x_perfil(s, recta),
}

if __name__ == '__main__':
    cd.METODOS.clear()
    cd.METODOS.update(METODOS)
    sim = cd.simular_huecos(cd.cargar_serie_cruda()['total_amba'])
    sim['mes'] = pd.to_datetime(sim['inicio']).dt.month
    g = sim.groupby('metodo')
    res = pd.DataFrame({
        'bloques': g['inicio'].nunique(),
        'MAPE_mediano': g['MAPE (%)'].median(),
        'MAPE_p90': g['MAPE (%)'].quantile(0.9),
        'MAPE_mediano_ene_feb_jul': sim[sim.mes.isin([1, 2, 7])].groupby('metodo')['MAPE (%)'].median(),
        'ciclo_semanal_conservado': g['ciclo_semanal_conservado'].median(),
    }).round(2).sort_values('MAPE_mediano')
    res.to_csv(os.path.join(cd.TABLA_DIR, 'tabla_variantes_spline.csv'))
    print(res.to_string())
