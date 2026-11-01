"""
Índice de ingreso por línea de subte (hipótesis H-ingreso, pre-registrado en docs/interpretacion_resultados.md).

Cada estación se ubica en una comuna (punto en polígono) y cada comuna en una zona del IDECBA (Norte: 2, 13, 14;
Centro: 1, 3, 5, 6, 7, 11, 12, 15; Sur: 4, 8, 9, 10). El índice de una línea es el ingreso per cápita familiar medio
de la zona (ETOI, 2.º trimestre de 2024) promediado entre sus estaciones, sin ponderar por usos.

Entradas: data/externos/estaciones_de_subte.geojson.txt, data/externos/comunas.geojson.txt (BA Data)
Salida:   resultados/tablas/tabla_lineas_subte_ingreso.csv
"""
import json
import os
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXT = os.path.join(BASE_DIR, "data", "externos")
SALIDA = os.path.join(BASE_DIR, "resultados", "tablas", "tabla_lineas_subte_ingreso.csv")

ZONA = {2: 'Norte', 13: 'Norte', 14: 'Norte', 1: 'Centro', 3: 'Centro', 5: 'Centro', 6: 'Centro', 7: 'Centro',
        11: 'Centro', 12: 'Centro', 15: 'Centro', 4: 'Sur', 8: 'Sur', 9: 'Sur', 10: 'Sur'}
INGRESO_ZONA = {'Norte': 805736, 'Centro': 548042, 'Sur': 377273}   # $ por persona, 2.º trimestre de 2024


def _en_anillo(x, y, anillo):
    dentro = False
    for i in range(len(anillo)):
        x1, y1 = anillo[i]; x2, y2 = anillo[(i + 1) % len(anillo)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dentro = not dentro
    return dentro


def _en_poligono(x, y, poly):
    return _en_anillo(x, y, poly[0]) and not any(_en_anillo(x, y, h) for h in poly[1:])


def comuna_de(x, y, comunas):
    for c in comunas:
        g = c['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        if any(_en_poligono(x, y, p) for p in polys):
            return c['properties']['comuna']
    return None


def main():
    comunas = json.load(open(os.path.join(EXT, 'comunas.geojson.txt'), encoding='utf-8'))['features']
    est = json.load(open(os.path.join(EXT, 'estaciones_de_subte.geojson.txt'), encoding='utf-8'))['features']
    filas = []
    for e in est:
        x, y = e['geometry']['coordinates'][:2]
        c = comuna_de(x, y, comunas)
        filas.append({'linea': e['properties']['linea'], 'estacion': e['properties']['estacion'], 'comuna': c, 'zona': ZONA[c]})
    df = pd.DataFrame(filas)
    res = []
    for l, g in df.groupby('linea'):
        idx = sum(INGRESO_ZONA[z] * n for z, n in g.zona.value_counts().items()) / len(g)
        res.append({'linea': l, 'estaciones': len(g), 'pct_norte': round(100 * (g.zona == 'Norte').mean()),
                    'pct_centro': round(100 * (g.zona == 'Centro').mean()), 'pct_sur': round(100 * (g.zona == 'Sur').mean()),
                    'comunas': ', '.join(str(int(c)) for c in sorted(g.comuna.unique())), 'indice_ingreso': round(idx)})
    t = pd.DataFrame(res).sort_values('indice_ingreso', ascending=False)
    t.to_csv(SALIDA, index=False)
    print(t.to_string(index=False))


if __name__ == '__main__':
    main()
