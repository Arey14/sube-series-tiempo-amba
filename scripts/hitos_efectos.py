"""
Efecto de los hitos del calendario sobre la demanda (pregunta P-1): paros, elecciones, feriados, y la pandemia
como descripción.

Para cada día se calcula el cociente entre lo observado y lo esperable: la mediana del mismo día de la semana en las
cuatro semanas anteriores y las cuatro posteriores, sin contar feriados, paros ni elecciones. Un cociente de 0,5
significa la mitad de lo habitual para ese día. La banda de ruido sale de los días ordinarios: el mismo cociente en
días laborables sin ningún hito (percentiles 2,5 y 97,5). Un hito solo se considera un efecto cuando queda fuera de
esa banda.

Demanda: transacciones diarias por modo (colectivo, tren y subte) de data/procesado/usos_diarios_amba.csv, sin huecos.
Período del análisis: marzo de 2022 a septiembre de 2026.

Pandemia (solo descripción): demanda semanal de 2020 y 2021 relativa a enero-febrero de 2020 (verano, época baja), por
lo que la caída está sobrestimada de manera moderada. No se mide recuperación (decisión del plan: el período de
referencia es solo de dos meses de verano).

Paros y elecciones se clasifican por quién paró y por si hubo gratuidad (diccionarios PARO_DE y GRATUIDAD), a partir
de la descripción y las fuentes de data/hitos/hitos_paros_elecciones.csv. Con eso se compara, para cada paro, lo que
pasó en el modo que paró y en los modos que no pararon (sustitución o complementariedad entre modos).

Entradas: data/procesado/usos_diarios_amba.csv, data/hitos/hitos_paros_elecciones.csv
Salidas:  resultados/tablas/tabla_hitos_cociente_dias.csv, tabla_hitos_resumen.csv, tabla_covid_descriptivo.csv,
          tabla_hitos_resumen_subtipo.csv, tabla_paros_modo_propio_vs_otros.csv
          resultados/figuras/fig16_covid_descriptivo.png, fig17_hitos_cociente.png, fig26_paros_por_tipo.png
"""

import os
import numpy as np
import pandas as pd
import holidays
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
USOS = os.path.join(BASE_DIR, "data", "procesado", "usos_diarios_amba.csv")
EVT = os.path.join(BASE_DIR, "data", "hitos", "hitos_paros_elecciones.csv")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")
FIG_DIR = os.path.join(BASE_DIR, "resultados", "figuras")

MODOS = ['colectivo', 'tren', 'subte']
INICIO, FIN = '2022-03-01', '2026-09-30'

# quién paró en cada paro (según las fuentes y el dato) y si hubo gratuidad en cada elección
PARO_DE = {
    '2023-07-07': ('colectivo (UTA)', ['colectivo']),
    '2024-01-24': ('general (CGT)', ['colectivo', 'tren', 'subte']),
    '2024-02-21': ('tren (La Fraternidad)', ['tren']),
    '2024-04-11': ('colectivo (UTA)', ['colectivo']),
    '2024-05-09': ('general (CGT)', ['colectivo', 'tren', 'subte']),
    '2024-10-30': ('tren y subte', ['tren', 'subte']),
    '2025-04-10': ('general (CGT)', ['tren', 'subte']),
    '2025-05-06': ('colectivo (UTA)', ['colectivo']),
    '2026-02-19': ('general (CGT)', ['colectivo', 'tren', 'subte']),
}
GRATUIDAD = {
    '2023-08-13': 'con gratuidad', '2023-10-22': 'con gratuidad', '2023-11-19': 'con gratuidad (inferida del dato)',
    '2025-05-18': 'sin gratuidad aparente', '2025-09-07': 'sin gratuidad aparente', '2025-10-26': 'sin gratuidad aparente',
}


def cociente_dia(serie, f, excluidos):
    """Valor del día sobre la mediana del mismo día de la semana (±4 semanas) sin días excluidos."""
    if np.isnan(serie.get(f, np.nan)):
        return np.nan
    vec = [serie.get(f + pd.Timedelta(days=7 * k), np.nan) for k in (-4, -3, -2, -1, 1, 2, 3, 4)
           if (f + pd.Timedelta(days=7 * k)) not in excluidos]
    vec = [v for v in vec if not np.isnan(v)]
    return float(serie[f] / np.median(vec)) if len(vec) >= 4 else np.nan


def main():
    usos = pd.read_csv(USOS, parse_dates=['fecha']).set_index('fecha').asfreq('D')[MODOS]
    evt = pd.read_csv(EVT, parse_dates=['fecha'])
    fer = holidays.Argentina(years=range(2021, 2027))
    dias_evt = set(evt['fecha'])
    excluidos = set(pd.Timestamp(f) for f in fer) | dias_evt

    # --- cociente de cada día de paro, elección y feriado laborable --------------------------------------------
    filas = []
    for _, r in evt[(evt.fecha >= INICIO) & (evt.fecha <= FIN)].iterrows():
        filas.append({'fecha': r.fecha.date(), 'tipo': r.tipo, 'detalle': r.descripcion[:70], 'dia_semana': r.fecha.day_name()[:3],
                      **{m: cociente_dia(usos[m], r.fecha, excluidos) for m in MODOS}})
    for f, nombre in sorted(fer.items()):
        f = pd.Timestamp(f)
        if f < pd.Timestamp(INICIO) or f > pd.Timestamp(FIN) or f in dias_evt:
            continue
        filas.append({'fecha': f.date(), 'tipo': 'feriado' if f.day_of_week < 5 else 'feriado en fin de semana',
                      'detalle': nombre[:70], 'dia_semana': f.day_name()[:3],
                      **{m: cociente_dia(usos[m], f, excluidos) for m in MODOS}})
    t = pd.DataFrame(filas)
    t['subtipo'] = [PARO_DE.get(str(f), ('', []))[0] if tp == 'paro' else GRATUIDAD.get(str(f), '') if tp == 'eleccion' else ''
                    for f, tp in zip(t['fecha'], t['tipo'])]
    t[MODOS] = t[MODOS].round(2)
    t = t[['fecha', 'tipo', 'subtipo', 'detalle', 'dia_semana'] + MODOS]
    t.to_csv(os.path.join(TABLA_DIR, 'tabla_hitos_cociente_dias.csv'), index=False)

    # --- banda de ruido: días laborables ordinarios --------------------------------------------------------------
    dias = pd.date_range(INICIO, FIN)
    ord_ = [d for d in dias if d.day_of_week < 5 and d not in excluidos]
    banda = {m: np.array([cociente_dia(usos[m], d, excluidos) for d in ord_]) for m in MODOS}
    banda = {m: v[~np.isnan(v)] for m, v in banda.items()}
    lim = {m: (np.quantile(v, 0.025), np.quantile(v, 0.975)) for m, v in banda.items()}

    # --- resumen por tipo de hito --------------------------------------------------------------------------------
    res = []
    for tipo, g in t.groupby('tipo'):
        for m in MODOS:
            v = g[m].dropna()
            if len(v) == 0:
                continue
            fuera = ((v < lim[m][0]) | (v > lim[m][1])).mean()
            res.append({'tipo': tipo, 'modo': m, 'dias': len(v), 'mediana_cociente': round(v.median(), 2), 'minimo': round(v.min(), 2),
                        'maximo': round(v.max(), 2), 'banda_ruido_inf': round(lim[m][0], 2), 'banda_ruido_sup': round(lim[m][1], 2),
                        'pct_fuera_de_banda': round(100 * fuera)})
    r = pd.DataFrame(res)
    r.to_csv(os.path.join(TABLA_DIR, 'tabla_hitos_resumen.csv'), index=False)
    sub = t[t.subtipo != '']
    rs = []
    for (tipo, st), g in sub.groupby(['tipo', 'subtipo']):
        for m in MODOS:
            v = g[m].dropna()
            rs.append({'tipo': tipo, 'subtipo': st, 'modo': m, 'dias': len(v), 'mediana_cociente': round(v.median(), 2), 'minimo': round(v.min(), 2),
                       'maximo': round(v.max(), 2), 'banda_ruido_inf': round(lim[m][0], 2), 'banda_ruido_sup': round(lim[m][1], 2)})
    pd.DataFrame(rs).to_csv(os.path.join(TABLA_DIR, 'tabla_hitos_resumen_subtipo.csv'), index=False)
    pp = []
    for _, r in t[t.tipo == 'paro'].iterrows():
        paran = PARO_DE[str(r['fecha'])][1]
        for m in MODOS:
            pp.append({'fecha': r['fecha'], 'paro': r['subtipo'], 'modo': m, 'rol': 'paró' if m in paran else 'no paró', 'cociente': r[m],
                       'banda_ruido_inf': round(lim[m][0], 2), 'banda_ruido_sup': round(lim[m][1], 2),
                       'posicion': 'sobre la banda' if r[m] > lim[m][1] else ('bajo la banda' if r[m] < lim[m][0] else 'dentro de la banda')})
    tp_ = pd.DataFrame(pp)
    tp_.to_csv(os.path.join(TABLA_DIR, 'tabla_paros_modo_propio_vs_otros.csv'), index=False)
    print('\nParos: modo que paró contra modos que no pararon'); print(tp_.groupby(['rol', 'modo']).cociente.describe().round(2).to_string())
    print('Banda de ruido (días laborables ordinarios, percentiles 2,5 y 97,5):')
    for m in MODOS:
        print(f'  {m}: {lim[m][0]:.2f} a {lim[m][1]:.2f}  ({len(banda[m])} días)')
    print('\nResumen por tipo de hito'); print(r.to_string(index=False))
    elec = t[t.tipo == 'eleccion'][['fecha', 'detalle'] + MODOS]
    print('\nElecciones'); print(elec.to_string(index=False))
    paros = t[t.tipo == 'paro'][['fecha', 'detalle'] + MODOS]
    print('\nParos'); print(paros.to_string(index=False))

    # --- COVID descriptivo ---------------------------------------------------------------------------------------
    cov = pd.read_csv(USOS, parse_dates=['fecha']).set_index('fecha').asfreq('D')[MODOS]
    base = cov.loc['2020-01-06':'2020-03-08']
    base = base[base.index.day_of_week < 5].mean()
    sem = cov.loc['2020-03-09':'2021-12-31']
    sem = sem[sem.index.day_of_week < 5].resample('W-SUN').mean().div(base)
    filas = []
    for m in MODOS:
        s = sem[m].dropna()
        filas.append({'modo': m, 'base_enero_marzo_2020_dia_habil': round(base[m]), 'semana_minima': s.idxmin().date(),
                      'cociente_minimo': round(s.min(), 3), 'cociente_dic_2020': round(s.loc['2020-12-01':'2020-12-31'].mean(), 3),
                      'cociente_dic_2021': round(s.loc['2021-12-01':'2021-12-31'].mean(), 3)})
    tc = pd.DataFrame(filas)
    tc.to_csv(os.path.join(TABLA_DIR, 'tabla_covid_descriptivo.csv'), index=False)
    print('\nCOVID (días hábiles de cada semana / promedio de días hábiles del 6-ene al 8-mar de 2020)'); print(tc.to_string(index=False))

    fig, ax = plt.subplots(figsize=(11, 5))
    col = {'colectivo': '#2980b9', 'tren': '#27ae60', 'subte': '#e67e22'}
    for m in MODOS:
        ax.plot(sem.index, sem[m] * 100, color=col[m], label=m)
    ax.axhline(100, color='k', lw=0.6)
    ax.set_ylabel('% del promedio de días hábiles de ene-mar 2020')
    ax.set_title('Pandemia: demanda semanal de días hábiles contra el verano de 2020 (descripción)', fontweight='bold')
    ax.legend(); plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig16_covid_descriptivo.png'), dpi=200); plt.close()

    fig, axs = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    for ax, m in zip(axs, MODOS):
        ax.axhspan(*lim[m], color='#bdc3c7', alpha=0.5, label='banda de días ordinarios')
        for tipo, c, nom in [('feriado', '#16a085', 'feriado laborable'), ('eleccion', '#8e44ad', 'elección'), ('paro', '#c0392b', 'paro')]:
            g = t[t.tipo == tipo]
            ax.scatter(pd.to_datetime(g['fecha']), g[m], s=26, color=c, label=nom, zorder=3)
        ax.set_title(m); ax.axhline(1, color='k', lw=0.6)
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
        ax.tick_params(axis='x', rotation=60, labelsize=8)
    axs[0].set_ylabel('Cociente contra un día habitual'); axs[0].legend(fontsize=8)
    plt.suptitle('Demanda en días de feriado, elección y paro (cada punto es un día)', fontweight='bold')
    plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig17_hitos_cociente.png'), dpi=200); plt.close()

    # cada paro con su fecha y quién paró; el modo que paró se marca con borde negro
    pr = t[t.tipo == 'paro'].reset_index(drop=True)
    etiquetas = [f"{pd.Timestamp(f):%d/%m/%y}\n{st}" for f, st in zip(pr['fecha'], pr['subtipo'])]
    x = np.arange(len(pr)); w = 0.27
    col = {'colectivo': '#2980b9', 'tren': '#27ae60', 'subte': '#e67e22'}
    fig, ax = plt.subplots(figsize=(14, 5.5))
    for k, m in enumerate(MODOS):
        paro_m = [m in PARO_DE[str(f)][1] for f in pr['fecha']]
        ax.bar(x + (k - 1) * w, pr[m], w, color=col[m], label=m, edgecolor=['black' if p else col[m] for p in paro_m], linewidth=1.6, zorder=3)
    ax.axhspan(0.78, 1.13, color='#bdc3c7', alpha=0.4, label='banda de días ordinarios (aprox.)', zorder=0); ax.axhline(1, color='k', lw=0.6)
    ax.set_xticks(x); ax.set_xticklabels(etiquetas, fontsize=8); ax.set_ylabel('Cociente contra un día habitual')
    ax.set_ylim(0, 1.45)
    ax.set_title('Paros: demanda de cada modo según quién paró (borde negro = ese modo paró)', fontweight='bold')
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=col[m], label=m) for m in MODOS] + [Patch(facecolor='white', edgecolor='black', linewidth=1.6, label='modo que paró'),
              Patch(color='#bdc3c7', alpha=0.5, label='banda de días ordinarios (aprox.)')], fontsize=8, ncol=5, loc='upper center'); plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'fig26_paros_por_tipo.png'), dpi=200); plt.close()


if __name__ == '__main__':
    main()
