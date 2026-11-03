"""
Transacciones diarias del subte por línea (A, B, C, D, E, H y premetro), a partir de las transacciones de SUBE.

Las líneas cambiaron de nombre en el archivo ("LINEA_A", "LINEA SUBTE C", "LIN_AMARILLA_C", "LIN_VERDE_D"...), así
que se normalizan a una letra. La línea D estuvo sin servicio del 8-ene-2024 al 6-mar-2024 (obras): en esos días
el valor queda en NaN en la serie por línea, para no confundir el cierre con una caída de la demanda.

Entrada: data/raw_usos/dat-ab-usos-{2022..2026}.csv (bajados por usos_transacciones.py)
Salida:  data/procesado/usos_diarios_subte_por_linea.csv (columnas A, B, C, D, E, H, P, subte_sin_D)
"""

import os
import re
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw_usos")
SALIDA = os.path.join(BASE_DIR, "data", "procesado", "usos_diarios_subte_por_linea.csv")

ANIOS = range(2022, 2027)
CIERRE_D = ('2024-01-08', '2024-03-06')


def letra_linea(nombre):
    if nombre == 'LIN_PREMETRO':
        return 'P'
    m = re.search(r'(?:SUBTE |LINEA_|_)([A-EH])$', nombre)
    return m.group(1) if m else None


def cargar():
    partes = []
    for a in ANIOS:
        d = pd.read_csv(os.path.join(RAW_DIR, f"dat-ab-usos-{a}.csv"), low_memory=False,
                        usecols=['DIA_TRANSPORTE', 'LINEA', 'TIPO_TRANSPORTE', 'CANTIDAD'])
        partes.append(d[d.TIPO_TRANSPORTE == 'SUBTE'])
    s = pd.concat(partes)
    s['fecha'] = pd.to_datetime(s['DIA_TRANSPORTE'])
    s['linea'] = s['LINEA'].map(letra_linea)
    sin_letra = s[s.linea.isna()]['LINEA'].unique()
    if len(sin_letra):
        print('Nombres de línea sin letra:', sin_letra)
    return s.dropna(subset=['linea'])


def main():
    s = cargar()
    p = s.pivot_table(index='fecha', columns='linea', values='CANTIDAD', aggfunc='sum')
    p = p.reindex(pd.date_range(p.index.min(), p.index.max(), freq='D'))
    p.index.name = 'fecha'
    p.loc[CIERRE_D[0]:CIERRE_D[1], 'D'] = float('nan')
    p['subte_sin_D'] = p[['A', 'B', 'C', 'E', 'H', 'P']].sum(axis=1, min_count=1)
    p.to_csv(SALIDA)
    cuota = (p['D'] / p[['A', 'B', 'C', 'D', 'E', 'H', 'P']].sum(axis=1, min_count=7)).resample('QS').mean()
    print('Participación media de la línea D en el subte, por trimestre:')
    print(cuota.dropna().round(3).to_string())
    print(f"Guardado: {SALIDA} ({len(p)} días)")


if __name__ == '__main__':
    main()
