"""
Los modelos de pronóstico de P-2 frente a los dos meses sin dato de la serie de usuarios (ago-2022 y ene-2024).

Pregunta: si los 62 días faltantes se pronosticaran con cada modelo (solo con lo anterior a cada mes, sin ver nada
posterior), ¿cuánto se acercan a la estimación hecha con las transacciones, y cómo quedan frente a la mejor interpolación?

Diseño
  - Referencia: la serie reconstruida desde las transacciones (serie_sube_diaria_reconstruida.csv). No es el dato real,
    que no existe, sino otra estimación con error de 1,6% a 3,2% en meses de vacaciones.
  - Para cada mes se pronostican 31 días con origen el último día anterior al hueco (ago-2022: entrenamiento de
    ene a jul de 2022; ene-2024: entrenamiento de ene-2022 a dic-2023, con ago-2022 reconstruido).
  - Siete modelos de P-2 con la misma configuración que en la comparación principal.
  - Interpolaciones (usan los datos de ambos lados del hueco, por lo que tienen una ventaja que los modelos no
    tienen): PCHIP x perfil semanal (la mejor), lineal por día de la semana y spline cúbico original.

Entradas: data/procesado/serie_sube_diaria_reconstruida.csv, data/total-usuarios-por-dia-AMBA.csv
Salidas:  data/procesado/pronosticos_p2_huecos_modelos.csv, resultados/tablas/tabla_modelos_sobre_huecos.csv,
          resultados/figuras/fig35_modelos_sobre_huecos.png
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pronosticos_p2 as P                 # noqa: E402
import evaluacion_pronosticos as E         # noqa: E402
import calidad_datos as C                  # noqa: E402

warnings.filterwarnings('ignore')
BASE = C.BASE_DIR
SALIDA = os.path.join(BASE, 'data', 'procesado', 'pronosticos_p2_huecos_modelos.csv')
RECON = os.path.join(BASE, 'data', 'procesado', 'serie_sube_diaria_reconstruida.csv')
HUECOS = [('agosto de 2022', '2022-08-01', '2022-08-31'), ('enero de 2024', '2024-01-01', '2024-01-31')]
LARGO = 31
ETIQ = {'naive_7': 'Naive 7 días', 'naive_364': 'Naive 364 días', 'sarimax': 'SARIMAX', 'prophet': 'Prophet',
        'gradient_boosting': 'Gradient Boosting', 'chronos2': 'Chronos-2', 'patchtst': 'PatchTST',
        'interp_pchip_x_perfil': 'Interpolación: PCHIP × perfil semanal',
        'interp_lineal_por_dia': 'Interpolación: lineal por día de la semana',
        'interp_spline_original': 'Interpolación: spline cúbico original'}
COL = {'naive_7': '#95a5a6', 'naive_364': '#bdc3c7', 'sarimax': '#8e44ad', 'prophet': '#e67e22', 'gradient_boosting': '#27ae60',
       'chronos2': '#2980b9', 'patchtst': '#c0392b', 'interp_pchip_x_perfil': '#000000', 'interp_lineal_por_dia': '#7f8c8d',
       'interp_spline_original': '#d35400'}


def modelos():
    return {
        'naive_7': lambda s, c: P.naive_semanal(s, c, LARGO),
        'naive_364': lambda s, c: P.naive_anual(s, c, LARGO),
        'sarimax': lambda s, c: P.sarimax(s, c, LARGO, **E.ORDEN_SARIMAX)[0],
        'prophet': lambda s, c: P.prophet(s, c, LARGO),
        'gradient_boosting': lambda s, c: P.gradient_boosting(s, c, LARGO),
        'chronos2': lambda s, c: P.chronos2(s, c, LARGO),
        'patchtst': lambda s, c: P.patchtst(s, c, LARGO),
    }


def pronosticar(ref):
    hechos = pd.read_csv(SALIDA, parse_dates=['fecha']) if os.path.exists(SALIDA) else pd.DataFrame()
    filas = [] if hechos.empty else [hechos]
    ya = set() if hechos.empty else set(zip(hechos.hueco, hechos.metodo))
    for nombre, ini, fin in HUECOS:
        corte = pd.Timestamp(ini) - pd.Timedelta(days=1)
        for m, f in modelos().items():
            if (nombre, m) in ya:
                continue
            p = f(ref, corte)
            filas.append(pd.DataFrame({'hueco': nombre, 'metodo': m, 'fecha': p.index, 'pronostico': p.values}))
            print(nombre, m, flush=True)
            pd.concat(filas).to_csv(SALIDA, index=False)
    return pd.read_csv(SALIDA, parse_dates=['fecha'])


def interpolaciones():
    crudo = C.cargar_serie_cruda()['total_amba'].loc[E.INICIO:E.FIN] / 1e6
    return {'interp_pchip_x_perfil': C.tendencia_x_perfil(crudo, PchipInterpolator),
            'interp_lineal_por_dia': C.interp_lineal_por_dia_semana(crudo),
            'interp_spline_original': C.interp_spline(crudo)}


def metricas(pron, interp, ref):
    filas = []
    for nombre, ini, fin in HUECOS:
        dias = pd.date_range(ini, fin)
        real = ref.loc[dias]
        series = {m: g.set_index('fecha')['pronostico'].loc[dias] for m, g in pron[pron.hueco == nombre].groupby('metodo')}
        series.update({m: s.loc[dias] for m, s in interp.items()})
        for m, p in series.items():
            e = (p - real)
            ok = e.notna()
            filas.append({'hueco': nombre, 'metodo': m, 'dias': int(ok.sum()),
                          'MAE_M': round(float(e[ok].abs().mean()), 3) if ok.any() else np.nan,
                          'MAPE_pct': round(float((e[ok].abs() / real[ok]).mean() * 100), 1) if ok.any() else np.nan,
                          'sesgo_pct': round(float((e[ok] / real[ok]).mean() * 100), 1) if ok.any() else np.nan})
    t = pd.DataFrame(filas)
    t.to_csv(os.path.join(C.TABLA_DIR, 'tabla_modelos_sobre_huecos.csv'), index=False)
    return t


def figura(pron, interp, ref, t):
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), gridspec_kw={'height_ratios': [1.25, 1]})
    for j, (nombre, ini, fin) in enumerate(HUECOS):
        dias = pd.date_range(ini, fin)
        marco = pd.date_range(dias[0] - pd.Timedelta(days=14), dias[-1] + pd.Timedelta(days=14))
        ax = axes[0, j]
        ax.plot(marco, ref.loc[marco], color='k', lw=2.4, label='Reconstrucción desde transacciones (referencia)', zorder=5)
        for m, g in pron[pron.hueco == nombre].groupby('metodo'):
            if m in ('naive_364', 'naive_7') and m == 'naive_364' and g.pronostico.isna().all():
                continue
            ax.plot(g.fecha, g.pronostico, color=COL[m], lw=1.3, label=ETIQ[m], alpha=0.9)
        ax.plot(dias, interp['interp_pchip_x_perfil'].loc[dias], color='#000000', lw=1.6, ls='--', label=ETIQ['interp_pchip_x_perfil'], zorder=6)
        ax.axvspan(dias[0], dias[-1], color='#f1c40f', alpha=0.12)
        ax.set_title(f'Pronóstico de {nombre} con lo anterior al mes', fontweight='bold')
        ax.set_ylabel('millones de usuarios'); ax.tick_params(axis='x', labelrotation=30)
        if j == 0:
            ax.legend(fontsize=7, loc='lower left', ncol=2)
        ax = axes[1, j]
        d = t[t.hueco == nombre].set_index('metodo').reindex(list(ETIQ)).dropna(subset=['MAPE_pct']).sort_values('MAPE_pct')
        ax.barh([ETIQ[m] for m in d.index], d.MAPE_pct, color=[COL[m] for m in d.index])
        for i, (m, r) in enumerate(d.iterrows()):
            ax.text(r.MAPE_pct + 0.3, i, f'{r.MAPE_pct:.1f}%', va='center', fontsize=8)
        ax.invert_yaxis(); ax.set_xlabel('MAPE contra la reconstrucción (%)')
        ax.set_title(f'Error por método, {nombre}', fontweight='bold')
        ax.tick_params(axis='y', labelsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(C.FIG_DIR, 'fig35_modelos_sobre_huecos.png'), dpi=170)
    plt.close()


def main():
    rec = pd.read_csv(RECON, parse_dates=['fecha']).set_index('fecha').asfreq('D')
    ref = rec['total_amba'].loc[E.INICIO:E.FIN] / 1e6
    pron = pronosticar(ref)
    interp = interpolaciones()
    t = metricas(pron, interp, ref)
    figura(pron, interp, ref, t)
    print(t.pivot(index='metodo', columns='hueco', values='MAPE_pct').to_string())
    print(t.pivot(index='metodo', columns='hueco', values='MAE_M').to_string())
    print(t.pivot(index='metodo', columns='hueco', values='sesgo_pct').to_string())


if __name__ == '__main__':
    main()
