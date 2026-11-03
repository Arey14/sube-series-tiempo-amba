"""
Tarifas reales (P-1): la tarifa mínima con SUBE de cada modo y jurisdicción corregida por inflación y por salario.

La serie nominal engaña: casi todo el aumento de 2022 y 2023 fue inflación. Se muestran dos correcciones:
  - Tarifa real: tarifa nominal dividida por el IPC nacional (INDEC), en pesos constantes de enero de 2022.
  - Costo de un uso mensual relativo al salario: 40 viajes por mes (20 días hábiles, ida y vuelta) como porcentaje
    del RIPTE (remuneración imponible promedio de los trabajadores estables, Secretaría de Trabajo). Los 40 viajes
    son un supuesto ilustrativo, no un dato de la serie.

Entradas: data/hitos/serie_tarifas_diaria.csv, data/externos/ipc_nacional_indec.csv, data/externos/ripte_mensual.csv
Salidas:  resultados/tablas/tabla_tarifas_reales_resumen.csv
          resultados/figuras/fig25_tarifas_reales.png
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TAR = os.path.join(BASE_DIR, "data", "hitos", "serie_tarifas_diaria.csv")
IPC = os.path.join(BASE_DIR, "data", "externos", "ipc_nacional_indec.csv")
RIPTE = os.path.join(BASE_DIR, "data", "externos", "ripte_mensual.csv")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")
FIG_DIR = os.path.join(BASE_DIR, "resultados", "figuras")

VIAJES_MES = 40
COLORES = {'colectivo_nacional': '#2980b9', 'colectivo_provincial': '#8e44ad', 'colectivo_caba': '#7f8c8d',
           'tren': '#27ae60', 'subte': '#e67e22'}


def mensual_a_diario(serie, indice):
    """Valor de cada mes asignado a todos sus días; los meses sin dato repiten el último."""
    return serie.reindex(serie.index.union(indice)).ffill().reindex(indice)


def main():
    tar = pd.read_csv(TAR, parse_dates=['fecha']).pivot(index='fecha', columns='serie', values='tarifa')
    idx = tar.index
    ipc = pd.read_csv(IPC, parse_dates=['indice_tiempo']).set_index('indice_tiempo').iloc[:, 0]
    rip = pd.read_csv(RIPTE, parse_dates=['indice_tiempo']).set_index('indice_tiempo')['ripte']
    rip = rip.iloc[:-1] if rip.iloc[-1] == rip.iloc[-3] else rip      # el último mes publicado repite el anterior: provisorio
    ipc_d = mensual_a_diario(ipc, idx)
    rip_d = mensual_a_diario(rip, idx)
    base = ipc_d.loc['2022-01-01']
    real = tar.mul(base / ipc_d, axis=0)                                # pesos constantes de enero de 2022
    rel_sal = tar.mul(VIAJES_MES).div(rip_d, axis=0) * 100                           # % del RIPTE

    fin = pd.Timestamp('2026-07-31')                                    # último mes con RIPTE definitivo
    filas = []
    for s in tar.columns:
        v = tar[s].dropna()
        if v.empty:
            continue
        ini = v.index[0]
        filas.append({'serie': s, 'primer_valor': ini.date(), 'tarifa_nominal_inicial': round(v.iloc[0], 2), 'tarifa_nominal_final': round(v.iloc[-1], 2),
                      'nominal_x': round(v.iloc[-1] / v.iloc[0], 1),
                      'real_inicial_pesos_ene22': round(real[s].dropna().iloc[0], 1), 'real_final_pesos_ene22': round(real[s].dropna().iloc[-1], 1),
                      'real_x': round(real[s].dropna().iloc[-1] / real[s].dropna().iloc[0], 2),
                      'pct_ripte_inicial': round(rel_sal[s].dropna().iloc[0], 2), 'pct_ripte_julio_2026': round(rel_sal[s].loc[:fin].dropna().iloc[-1], 2),
                      'pct_ripte_maximo': round(rel_sal[s].loc[:fin].max(), 2), 'fecha_maximo': rel_sal[s].loc[:fin].idxmax().date()})
    t = pd.DataFrame(filas)
    t.to_csv(os.path.join(TABLA_DIR, 'tabla_tarifas_reales_resumen.csv'), index=False)
    print(t.to_string(index=False))

    fig, ax = plt.subplots(1, 2, figsize=(14, 4.8))
    for s in tar.columns:
        g = real[s].dropna()
        if len(g):
            ax[0].plot(g.index, g, label=s, color=COLORES.get(s), lw=1.4)
        h = rel_sal[s].loc[:fin].dropna()
        if len(h):
            ax[1].plot(h.index, h, label=s, color=COLORES.get(s), lw=1.4)
    ax[0].set_title('Tarifa real (pesos constantes de enero de 2022)', fontweight='bold')
    ax[0].set_ylabel('$ por viaje, deflactado por IPC nacional')
    ax[1].set_title(f'Costo de {VIAJES_MES} viajes por mes, en % del salario (RIPTE)', fontweight='bold')
    ax[1].set_ylabel('% del RIPTE mensual')
    ax[0].legend(fontsize=8, ncol=2)
    for a in ax:
        a.xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator(bymonth=(1, 7)))
        a.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%m/%y'))
        a.tick_params(axis='x', rotation=45)
    plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig25_tarifas_reales.png'), dpi=200); plt.close()


if __name__ == '__main__':
    main()
