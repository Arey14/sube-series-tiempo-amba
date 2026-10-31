"""
Descriptivo del salto tarifario de febrero de 2024 usando las transacciones por jurisdicción.

El salto del 6-feb-2024 (colectivo +251%, tren +247%) cae al lado del hueco de enero de 2024 en la
serie de usuarios. Las transacciones (usos) no tienen huecos y se pueden abrir por modo y
jurisdicción, así que se miran directamente.

Para neutralizar la estacionalidad se compara cada serie contra el mismo período del año anterior
(364 días antes, mismo día de la semana) y solo con días hábiles que no sean feriado en ninguno de los
dos años: los feriados móviles (carnaval, Semana Santa) no coinciden entre años y producen picos de ±50%. Es una comparación descriptiva,
no un efecto causal: hay otros cambios al mismo tiempo (devaluación de dic-2023, inflación, ajuste
mensual de otras jurisdicciones).

Entrada: data/procesado/usos_diarios_amba.csv (generada por usos_transacciones.py)
Salidas:
  resultados/tablas/tabla_tarifas_feb2024_yoy.csv
  resultados/figuras/fig13_usos_yoy_tarifas_2024.png
"""

import os
import numpy as np
import pandas as pd
import holidays
import matplotlib.pyplot as plt

plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
USOS_PATH = os.path.join(BASE_DIR, "data", "procesado", "usos_diarios_amba.csv")
FIG_DIR = os.path.join(BASE_DIR, "resultados", "figuras")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")

SERIES = ['colectivo_nacional', 'colectivo_provincial', 'colectivo_municipal', 'colectivo_caba', 'tren', 'subte']
COLORES = {'colectivo_nacional': '#2980b9', 'colectivo_provincial': '#8e44ad', 'colectivo_municipal': '#16a085',
           'colectivo_caba': '#7f8c8d', 'tren': '#27ae60', 'subte': '#e67e22'}
FECHAS = {'2024-01-15': 'colectivo y tren nacional\n(Res. 8/2023: IPC)', '2024-02-04': 'subte tramo B',
          '2024-02-06': 'colectivo y tren +251%/+247%', '2024-05-02': 'tren +54%', '2024-05-17': 'subte +359%'}

# ventanas: antes (después del cambio del 15-ene) y después del 6-feb-2024; los feriados quedan excluidos
PRE = ('2024-01-16', '2024-02-05')
POST = ('2024-02-14', '2024-03-08')


def razon_interanual(usos):
    """Cociente contra el mismo día de la semana del año anterior (364 días antes).

    Queda en NaN si el día o su par del año anterior es fin de semana o feriado.
    """
    feriados = holidays.Argentina(years=range(2020, 2027))
    idx = usos.index
    es_habil = (idx.day_of_week < 5) & np.array([d not in feriados for d in idx])
    es_habil = pd.Series(es_habil, index=idx)
    habil_par = es_habil.shift(364, fill_value=False)
    r = usos / usos.shift(364)
    return r.where(es_habil & habil_par)


def mediana_habiles(r, ini, fin):
    return r.loc[ini:fin].median()


def tabla(usos):
    filas = []
    for s in SERIES:
        r = razon_interanual(usos[s])
        pre, post = mediana_habiles(r, *PRE), mediana_habiles(r, *POST)
        filas.append({'serie': s, 'razon_interanual_pre': round(pre, 3), 'razon_interanual_post': round(post, 3),
                      'cambio_relativo_pct': round((post / pre - 1) * 100, 1)})
    t = pd.DataFrame(filas)
    t['cambio_vs_colectivo_municipal_pp'] = (t['cambio_relativo_pct']
                                              - t.loc[t.serie == 'colectivo_municipal', 'cambio_relativo_pct'].iloc[0]).round(1)
    return t


def graficar(usos):
    fig, ax = plt.subplots(figsize=(14, 6))
    for s in SERIES:
        r = razon_interanual(usos[s]).dropna().loc['2023-11-15':'2024-07-15']
        ax.plot(r.index, r.rolling(7, center=True, min_periods=3).median(), color=COLORES[s], lw=1.6, label=s)
    for f, txt in FECHAS.items():
        ax.axvline(pd.Timestamp(f), color='k', ls=':', alpha=0.5)
        ax.text(pd.Timestamp(f), ax.get_ylim()[1] * 0.98, txt, rotation=90, va='top', ha='right', fontsize=8)
    ax.axhline(1, color='k', lw=0.6)
    ax.set_ylim(0.5, 1.5)
    ax.set_title('Transacciones en días hábiles vs. el mismo día del año anterior (mediana móvil de 7 días hábiles)', fontweight='bold')
    ax.set_ylabel('Cociente 2024 / 2023'); ax.legend(loc='lower left', ncol=3)
    plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig13_usos_yoy_tarifas_2024.png'), dpi=200); plt.close()


def main():
    usos = pd.read_csv(USOS_PATH, parse_dates=['fecha']).set_index('fecha').asfreq('D')
    t = tabla(usos)
    t.to_csv(os.path.join(TABLA_DIR, 'tabla_tarifas_feb2024_yoy.csv'), index=False)
    print(f"Ventanas de días hábiles: pre {PRE[0]} a {PRE[1]}, post {POST[0]} a {POST[1]}")
    print(t.to_string(index=False))
    graficar(usos)


if __name__ == '__main__':
    main()
