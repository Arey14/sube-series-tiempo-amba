"""
Calidad de datos: huecos de la serie SUBE e imputación.

Responde a: ¿qué días faltan?, ¿qué método de interpolación es razonable para
bloques largos con estacionalidad semanal? (Clase de Interpolación: approx y spline).

Salidas:
  resultados/tablas/tabla_huecos_datos.csv
  resultados/tablas/tabla_simulacion_interpolacion.csv
  resultados/figuras/fig7_interpolacion_huecos.png
  data/procesado/serie_sube_diaria_imputada.csv  (con columna `imputado`)
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import CubicSpline

plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(BASE_DIR, "data", "total-usuarios-por-dia-AMBA.csv")
PROC_DIR = os.path.join(BASE_DIR, "data", "procesado")
FIG_DIR = os.path.join(BASE_DIR, "resultados", "figuras")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")
for d in (PROC_DIR, FIG_DIR, TABLA_DIR):
    os.makedirs(d, exist_ok=True)

COLUMNAS = ['total_amba', 'colectivo_amba', 'subte_amba', 'tren_amba']
LARGO_HUECO_SIM = 31


def cargar_serie_cruda(csv_path=DATA_PATH):
    """Carga el CSV y fuerza frecuencia diaria; los días ausentes quedan como NaN."""
    df = pd.read_csv(csv_path, parse_dates=['indice_tiempo']).set_index('indice_tiempo')
    return df.asfreq('D')


def tabla_huecos(df):
    """Agrupa los días faltantes en rachas consecutivas."""
    faltan = df.index[df['total_amba'].isna()]
    if len(faltan) == 0:
        return pd.DataFrame(columns=['inicio', 'fin', 'dias', 'dia_semana_inicio'])
    s = pd.Series(faltan)
    grupo = (s.diff() != pd.Timedelta(days=1)).cumsum()
    filas = [{'inicio': g.iloc[0].date(), 'fin': g.iloc[-1].date(), 'dias': len(g),
              'dia_semana_inicio': g.iloc[0].day_name()} for _, g in s.groupby(grupo)]
    return pd.DataFrame(filas)


# --- Métodos de interpolación -------------------------------------------------

def interp_lineal(s):
    """approx() de la clase: recta entre los bordes del hueco."""
    return s.interpolate(method='linear')


def interp_spline(s):
    """spline() de la clase: spline cúbico sobre los puntos conocidos."""
    k = s.dropna()
    cs = CubicSpline(k.index.map(pd.Timestamp.toordinal).values, k.values)
    out = s.copy()
    m = out.isna()
    out[m] = cs(out.index[m].map(pd.Timestamp.toordinal).values)
    return out


def interp_lineal_por_dia_semana(s):
    """Interpola linealmente cada día de la semana por separado (7 sub-series).

    Conserva el ciclo semanal: un lunes faltante se estima entre los lunes vecinos.
    """
    out = s.copy()
    for d in range(7):
        sub = out[out.index.day_of_week == d]
        out[sub.index] = sub.interpolate(method='linear')
    return out


METODOS = {
    'lineal': interp_lineal,
    'spline': interp_spline,
    'lineal_por_dia_semana': interp_lineal_por_dia_semana,
}


def simular_huecos(serie, largo=LARGO_HUECO_SIM, paso_dias=14, margen=35):
    """Oculta bloques de `largo` días de datos reales y mide el error de cada método.

    Solo usa ventanas sin huecos reales cerca. Evalúa solo sobre los días ocultos.
    """
    filas = []
    inicios = pd.date_range('2022-10-01', '2026-07-31', freq=f'{paso_dias}D')
    for ini in inicios:
        fin = ini + pd.Timedelta(days=largo - 1)
        ventana = serie.loc[ini - pd.Timedelta(days=margen):fin + pd.Timedelta(days=margen)]
        if ventana.isna().any():
            continue
        real = serie.loc[ini:fin]
        s = serie.loc[ini - pd.Timedelta(days=60):fin + pd.Timedelta(days=60)].copy()
        s.loc[ini:fin] = np.nan
        for nombre, f in METODOS.items():
            est = f(s).loc[ini:fin]
            err = est - real
            amp = lambda x: (x - x.rolling(7, center=True, min_periods=4).mean()).std()
            filas.append({
                'inicio': ini.date(), 'metodo': nombre,
                'MAPE (%)': (err.abs() / real).mean() * 100,
                'MAE (M)': err.abs().mean() / 1e6,
                'sesgo (%)': err.mean() / real.mean() * 100,
                'ciclo_semanal_conservado': amp(est) / amp(real),
            })
    return pd.DataFrame(filas)


def imputar(df, metodo='lineal_por_dia_semana'):
    """Imputa todas las columnas y agrega la bandera `imputado` (True = dato no observado)."""
    out = df.copy()
    out['imputado'] = df['total_amba'].isna()
    for c in COLUMNAS:
        out[c] = METODOS[metodo](df[c])
    return out


def graficar(df_crudo, resumen_sim, sim):
    """Hueco real de ene-2024 con cada método + distribución del error simulado."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 5), gridspec_kw={'width_ratios': [1.6, 1]})
    ini, fin = pd.Timestamp('2023-12-01'), pd.Timestamp('2024-03-01')
    serie = df_crudo['total_amba'].loc[ini:fin]
    ax = axes[0]
    ax.plot(serie.index, serie / 1e6, 'k-', lw=1.6, label='Observado')
    colores = {'lineal': '#e74c3c', 'spline': '#8e44ad', 'lineal_por_dia_semana': '#27ae60'}
    for nombre, f in METODOS.items():
        est = f(df_crudo['total_amba']).loc[ini:fin]
        ax.plot(est.index, est / 1e6, '--', lw=1.3, color=colores[nombre], label=nombre)
    ax.set_title('Hueco real de enero 2024: imputación según método', fontweight='bold')
    ax.set_ylabel('Millones de usuarios')
    ax.legend(loc='lower right')

    ax = axes[1]
    orden = ['lineal', 'spline', 'lineal_por_dia_semana']
    datos = [sim.loc[sim.metodo == m, 'MAPE (%)'].clip(upper=150) for m in orden]
    bp = ax.boxplot(datos, tick_labels=['lineal', 'spline', 'lineal por\ndía de semana'], patch_artist=True)
    for patch, m in zip(bp['boxes'], orden):
        patch.set_facecolor(colores[m]); patch.set_alpha(0.5)
    ax.set_title('Error al ocultar bloques de 31 días reales', fontweight='bold')
    ax.set_ylabel('MAPE (%) (recortado en 150)')
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'fig7_interpolacion_huecos.png'), dpi=200)
    plt.close()


def main():
    print(">>> Calidad de datos: huecos e imputación")
    crudo = cargar_serie_cruda()

    huecos = tabla_huecos(crudo)
    huecos.to_csv(os.path.join(TABLA_DIR, 'tabla_huecos_datos.csv'), index=False)
    print(huecos.to_string(index=False))
    print(f"Total de días faltantes: {int(crudo['total_amba'].isna().sum())} de {len(crudo)}")

    sim = simular_huecos(crudo['total_amba'])
    resumen = (sim.groupby('metodo')
                  .agg(ventanas=('inicio', 'nunique'),
                       MAPE_mediano=('MAPE (%)', 'median'),
                       MAPE_p90=('MAPE (%)', lambda x: x.quantile(0.9)),
                       MAE_medio_M=('MAE (M)', 'mean'),
                       ciclo_semanal_conservado=('ciclo_semanal_conservado', 'median'))
                  .round(2).sort_values('MAPE_mediano'))
    resumen.to_csv(os.path.join(TABLA_DIR, 'tabla_simulacion_interpolacion.csv'))
    print(resumen.to_string())

    graficar(crudo, resumen, sim)
    imputado = imputar(crudo)
    imputado.to_csv(os.path.join(PROC_DIR, 'serie_sube_diaria_imputada.csv'), index_label='fecha')
    print(f"Serie imputada guardada ({int(imputado['imputado'].sum())} días marcados).")


if __name__ == '__main__':
    main()
