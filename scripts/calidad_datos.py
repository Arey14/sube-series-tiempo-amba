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


def total_vs_modos(df):
    """P2: relación entre `total_amba` y la suma de los modos, por año.

    El portal define la unidad como "tarjetas diferentes por día". Que el total sea
    siempre <= suma sugiere que deduplica tarjetas que usan más de un modo (inferencia,
    el portal no lo documenta).
    """
    d = df[df['total_amba'].notna()].copy()
    d['suma_modos'] = d[['colectivo_amba', 'subte_amba', 'tren_amba']].sum(axis=1)
    d['solapamiento'] = d['suma_modos'] - d['total_amba']
    d['total_sobre_suma'] = d['total_amba'] / d['suma_modos']
    por_anio = d.groupby(d.index.year).agg(
        total_sobre_suma_medio=('total_sobre_suma', 'mean'),
        solapamiento_medio_M=('solapamiento', lambda x: x.mean() / 1e6),
        dias_total_mayor_que_suma=('solapamiento', lambda x: int((x < 0).sum())),
    ).round(3)
    return por_anio


def detectar_atipicos(df, umbral=0.5, desde='2020-07-01'):
    """P3: días con valor < `umbral` x mediana del mismo día de la semana (±4 semanas).

    Se clasifican con el calendario de feriados; los no explicados quedan como candidatos
    a paro, evento o falla de registro (a verificar con fuentes en la Fase 3).
    """
    import holidays
    feriados = holidays.Argentina(years=range(2020, 2027))
    filas = []
    for col in COLUMNAS:
        s = df[col]
        vecinos = pd.concat([s.shift(7 * k) for k in (-4, -3, -2, -1, 1, 2, 3, 4)], axis=1).median(axis=1)
        razon = s / vecinos
        for fecha in razon.index[(razon < umbral) & (razon.index >= desde)]:
            filas.append({
                'fecha': fecha.date(), 'dia_semana': fecha.day_name(), 'modo': col,
                'valor': int(s[fecha]), 'mediana_vecinos': int(vecinos[fecha]),
                'razon': round(razon[fecha], 3),
                'feriado': fecha in feriados,
            })
    t = pd.DataFrame(filas)
    t['explicacion'] = np.where(t['feriado'], 'feriado', 'sin explicación en calendario')
    return t.sort_values(['fecha', 'modo']).reset_index(drop=True)


def resumen_atipicos_sin_feriado(t):
    """Una fila por fecha no feriada, con los valores de cada modo."""
    nf = t[~t['feriado']]
    return (nf.pivot_table(index='fecha', columns='modo', values='razon', aggfunc='first')
              .round(2).reset_index())


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

    print(">>> P2: total vs. suma de modos")
    p2 = total_vs_modos(crudo)
    p2.to_csv(os.path.join(TABLA_DIR, 'tabla_total_vs_suma_modos.csv'))
    print(p2.to_string())

    print(">>> P3: días atípicos por modo")
    at = detectar_atipicos(crudo)
    at.to_csv(os.path.join(TABLA_DIR, 'tabla_dias_atipicos.csv'), index=False)
    sin_fer = resumen_atipicos_sin_feriado(at)
    print(f"{len(at)} registros atípicos; {at['feriado'].sum()} en feriado.")
    print("Fechas atípicas NO feriado (razón vs. mediana del mismo día de semana):")
    print(sin_fer.to_string(index=False))

    graficar(crudo, resumen, sim)
    imputado = imputar(crudo)
    imputado.to_csv(os.path.join(PROC_DIR, 'serie_sube_diaria_imputada.csv'), index_label='fecha')
    print(f"Serie imputada guardada ({int(imputado['imputado'].sum())} días marcados).")


if __name__ == '__main__':
    main()
