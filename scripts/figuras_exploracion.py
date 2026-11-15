"""
Gráficos de detalle para la sección 4 del Informe final (exploración de la serie).

  fig29  estacionariedad: nivel, diferencia estacional y diferencia estacional + simple, con media y desvío móviles
  fig30  ACF de las tres versiones (muestra la autocorrelación negativa que agrega diferenciar de más)
  fig31  residuo de STL en los hitos (feriados, paros, elecciones): ¿se detectan como atípicos?
  fig32  detalle de los métodos de descomposición (bordes, feriados, retraso de la media causal, ciclo semanal anulado)
  fig33  comparación cuantitativa de métodos de descomposición
  fig34  detalle de la correlación cruzada tren-colectivo (dispersión, banda de Bartlett, subperíodos, estabilidad)

Entrada: data/procesado/serie_sube_diaria_reconstruida.csv, data/hitos/hitos_paros_elecciones.csv
Salida:  resultados/figuras/fig29..fig34 y resultados/tablas/tabla_*.csv (ver cada función)
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import holidays
from statsmodels.tsa.stattools import acf
from statsmodels.tsa.seasonal import STL

import herramientas_clase as hc

FIG, TAB = hc.FIG_DIR, hc.TABLA_DIR
BASE = hc.BASE_DIR
HITOS = os.path.join(BASE, 'data', 'hitos', 'hitos_paros_elecciones.csv')
GRATUIDAD = ['2023-08-13', '2023-10-22', '2023-11-19']


def guardar(nombre):
    plt.tight_layout()
    plt.savefig(os.path.join(FIG, nombre), dpi=170)
    plt.close()


# --- fig29 y fig30: estacionariedad ---------------------------------------------------

def versiones(df):
    completa = df.loc[:'2026-09-30', 'total_amba'] / 1e6
    s22 = completa.loc['2022-01-01':]
    return completa, s22, s22.diff(7).dropna(), s22.diff(7).diff().dropna()


def fig_estacionariedad(df):
    completa, s22, d7, d71 = versiones(df)
    paneles = [(completa, 'Nivel, con pandemia (2020-2026)', 'millones de usuarios'),
               (s22, 'Nivel, desde 2022', 'millones de usuarios'),
               (d7, 'Diferencia estacional: $y_t - y_{t-7}$ (desde 2022)', 'millones'),
               (d71, 'Diferencia estacional + simple (desde 2022)', 'millones')]
    fig, axes = plt.subplots(4, 1, figsize=(13, 11), sharex=False)
    for ax, (x, tit, yl) in zip(axes, paneles):
        m = x.rolling(91, center=True).mean()
        sd = x.rolling(91, center=True).std()
        ax.plot(x.index, x.values, color='#bdc3c7', lw=0.6, label='serie diaria')
        ax.plot(m.index, m.values, color='#c0392b', lw=1.8, label='media móvil de 91 días')
        ax.fill_between(m.index, (m - sd).values, (m + sd).values, color='#c0392b', alpha=0.18, label='media ± 1 desvío (91 días)')
        ax.set_title(tit, fontweight='bold', fontsize=10)
        ax.set_ylabel(yl)
    axes[0].legend(loc='lower right', fontsize=8, ncol=3)
    guardar('fig29_estacionariedad_versiones.png')


def fig_acf_versiones(df):
    _, s22, d7, d71 = versiones(df)
    filas = []
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3), sharey=True)
    for ax, (x, nombre) in zip(axes, [(s22, 'Nivel'), (d7, 'Diferencia estacional'), (d71, 'Diferencia estacional + simple')]):
        a = acf(x, nlags=28, fft=True)
        ax.bar(range(1, 29), a[1:], color='#2c3e50', width=0.7)
        for k in (7, 14, 21, 28):
            ax.axvline(k, color='#c0392b', ls=':', alpha=0.5)
        b = 1.96 / np.sqrt(len(x))
        ax.axhline(b, color='r', ls='--', lw=0.8); ax.axhline(-b, color='r', ls='--', lw=0.8)
        ax.set_title(f'{nombre}\ndesvío = {x.std():.3f} M | ACF(1) = {a[1]:+.2f} | ACF(7) = {a[7]:+.2f}', fontweight='bold', fontsize=10)
        ax.set_xlabel('Rezago (días)')
        filas.append({'version': nombre, 'dias': len(x), 'desvio_M': round(x.std(), 3), 'ACF_rezago_1': round(a[1], 3),
                      'ACF_rezago_7': round(a[7], 3), 'ACF_rezago_14': round(a[14], 3)})
    axes[0].set_ylabel('Autocorrelación')
    guardar('fig30_acf_versiones_diferenciacion.png')
    t = pd.DataFrame(filas)
    t.to_csv(os.path.join(TAB, 'tabla_diferenciacion_dispersion_acf.csv'), index=False)
    return t


# --- fig31: residuo de STL en los hitos -----------------------------------------------

def clasificar(idx):
    h = pd.read_csv(HITOS, encoding='utf-8-sig', parse_dates=['fecha'])
    paros = set(h.loc[h.tipo == 'paro', 'fecha'])
    elec = set(h.loc[h.tipo == 'eleccion', 'fecha'])
    fer = holidays.Argentina(years=range(2022, 2027))
    clase = []
    for d in idx:
        if d in paros:
            clase.append('paro')
        elif d in elec:
            clase.append('elección')
        elif d in fer and d.dayofweek < 5:
            clase.append('feriado laborable')
        elif (d.month, d.day) in ((12, 24), (12, 31)):
            clase.append('24 y 31 de diciembre')
        elif d in fer:
            clase.append('feriado en fin de semana')
        else:
            clase.append('ordinario')
    return pd.Series(clase, index=idx)


def fig_residuo_stl(df):
    s = df.loc['2022-01-01':'2026-09-30', 'total_amba'] / 1e6
    stl = STL(s, period=7, robust=True).fit()
    ajuste = stl.trend + stl.seasonal
    rel = 100 * stl.resid / ajuste
    clase = clasificar(s.index)
    ordin = rel[clase == 'ordinario']
    sd = 1.4826 * np.median(np.abs(ordin - np.median(ordin)))
    umbral = 20.0   # umbral práctico (ver informe); 3 desvíos robustos marcaba el 18% de los días ordinarios
    marca = rel.abs() > umbral
    colores = {'paro': '#c0392b', 'elección': '#8e44ad', 'feriado laborable': '#e67e22',
               'feriado en fin de semana': '#f1c40f', '24 y 31 de diciembre': '#16a085', 'ordinario': '#7f8c8d'}

    filas = []
    for c in ['ordinario', 'feriado en fin de semana', '24 y 31 de diciembre', 'feriado laborable', 'paro', 'elección']:
        m = clase == c
        filas.append({'tipo_de_dia': c, 'dias': int(m.sum()), 'mediana_residuo_pct': round(rel[m].median(), 1),
                      'dias_fuera_de_umbral': int((marca & m).sum()), 'pct_fuera_de_umbral': round(100 * (marca & m).sum() / m.sum(), 1)})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(os.path.join(TAB, 'tabla_stl_residuo_por_tipo_de_dia.csv'), index=False)
    n_marca = int(marca.sum())
    n_hito = int((marca & (clase != 'ordinario')).sum())
    sin_expl = pd.DataFrame({'fecha': s.index[marca & (clase == 'ordinario')],
                             'dia_semana': s.index[marca & (clase == 'ordinario')].day_name(),
                             'residuo_pct': rel[marca & (clase == 'ordinario')].round(1).values}).sort_values('residuo_pct')
    sin_expl.to_csv(os.path.join(TAB, 'tabla_stl_residuo_dias_sin_hito.csv'), index=False)

    fig = plt.figure(figsize=(15, 13))
    gs = fig.add_gridspec(3, 4, height_ratios=[1.1, 1.0, 1.0])
    ax = fig.add_subplot(gs[0, :])
    ax.plot(rel.index, rel.values, color='#bdc3c7', lw=0.7, zorder=1)
    for c, col in colores.items():
        m = clase == c
        ax.scatter(rel.index[m], rel[m], s=18 if c != 'ordinario' else 6, color=col, label=f'{c} ({int(m.sum())})', zorder=3 if c != 'ordinario' else 2)
    ax.axhline(umbral, color='k', ls='--', lw=0.8); ax.axhline(-umbral, color='k', ls='--', lw=0.8)
    ax.text(rel.index[5], umbral + 2, f'umbral: ±{umbral:.0f}%', fontsize=8)
    ax.set_title('Residuo de STL como porcentaje del valor esperado (tendencia + patrón semanal), total AMBA', fontweight='bold')
    ax.set_ylabel('residuo (% del esperado)'); ax.legend(ncol=5, fontsize=8, loc='lower right')

    ax = fig.add_subplot(gs[1, :2])
    orden = ['ordinario', 'feriado en fin de semana', '24 y 31 de diciembre', 'feriado laborable', 'paro', 'elección']
    datos = [rel[clase == c].values for c in orden]
    bp = ax.boxplot(datos, tick_labels=[f'{c}\n(n={len(d)})' for c, d in zip(orden, datos)], patch_artist=True, showfliers=True)
    for p, c in zip(bp['boxes'], orden):
        p.set_facecolor(colores[c]); p.set_alpha(0.6)
    ax.axhline(umbral, color='k', ls='--', lw=0.8); ax.axhline(-umbral, color='k', ls='--', lw=0.8)
    ax.set_title('Distribución del residuo por tipo de día', fontweight='bold'); ax.set_ylabel('residuo (% del esperado)')
    ax.tick_params(axis='x', labelsize=8)

    ax = fig.add_subplot(gs[1, 2:])
    ax.bar(range(len(orden)), tabla.set_index('tipo_de_dia').loc[orden, 'pct_fuera_de_umbral'], color=[colores[c] for c in orden])
    ax.set_xticks(range(len(orden))); ax.set_xticklabels([c.replace(' ', '\n') for c in orden], fontsize=8)
    ax.set_ylabel('% de días fuera del umbral'); ax.set_ylim(0, 105)
    for i, c in enumerate(orden):
        r = tabla.set_index('tipo_de_dia').loc[c]
        ax.text(i, r.pct_fuera_de_umbral + 2, f'{int(r.dias_fuera_de_umbral)} de {int(r.dias)}', ha='center', fontsize=8)
    ax.set_title(f'Días marcados como atípicos: {n_marca} en total, {n_hito} son hitos conocidos', fontweight='bold', fontsize=10)

    ventanas = [('2024-03-29', 'feriado: Viernes Santo 2024'), ('2023-10-22', 'elección con gratuidad (22-oct-2023)'),
                ('2025-04-10', 'paro general (10-abr-2025)'), ('2024-05-09', 'paro general (9-may-2024)')]
    for j, (f, tit) in enumerate(ventanas):
        ax = fig.add_subplot(gs[2, j])
        f = pd.Timestamp(f)
        w = slice(f - pd.Timedelta(days=10), f + pd.Timedelta(days=10))
        ax.plot(s.loc[w].index, s.loc[w], color='k', lw=1.4, marker='o', ms=3, label='observado')
        ax.plot(ajuste.loc[w].index, ajuste.loc[w], color='#2980b9', lw=1.4, ls='--', label='esperado (tendencia + semanal)')
        ax.axvline(f, color='#c0392b', lw=1, alpha=0.6)
        ax.set_title(f'{tit}\nresiduo del día: {rel.loc[f]:+.0f}%', fontsize=9, fontweight='bold')
        ax.tick_params(axis='x', labelrotation=45, labelsize=7)
        if j == 0:
            ax.set_ylabel('millones de usuarios'); ax.legend(fontsize=7, loc='lower left')
    guardar('fig31_stl_residuo_en_hitos.png')
    print(tabla.to_string(index=False))
    print(f'umbral = {umbral:.2f}% (desvío robusto de días ordinarios {sd:.2f}%); marcados = {n_marca}; hitos entre marcados = {n_hito}')
    print('marcados sin hito conocido (ordinarios):', len(sin_expl))
    print(sin_expl.to_string(index=False))
    return tabla


# --- fig32 y fig33: detalle y comparación de métodos de descomposición -------------------

def fig_descomposicion_detalle(df):
    s = hc.tramo_continuo(df, 'total_amba')
    stl = STL(s, period=7, robust=True).fit()
    ma28 = hc.media_movil_centrada(s, 28)
    causal = s.rolling(28).mean()
    bajos = hc.filtrar_df(s, hc.pasa_bajos(1 / 28))
    notch = hc.filtrar_df(s, hc.elimina_banda_semanal())
    ma7 = hc.media_movil_centrada(s, 7)

    def ventana(ax, a, b, titulo, causal_on=False, serie=s):
        w = slice(a, b)
        ax.plot(serie.loc[w].index, serie.loc[w], color='#bdc3c7', lw=1, label='observada')
        ax.plot(ma28.loc[w].index, ma28.loc[w], color='#c0392b', lw=1.8, label='MA28 centrada')
        ax.plot(stl.trend.loc[w].index, stl.trend.loc[w], color='#27ae60', lw=1.8, label='tendencia STL')
        ax.plot(bajos.loc[w].index, bajos.loc[w], color='#2980b9', lw=1.6, ls='--', label='pasa-bajos (FFT)')
        if causal_on:
            ax.plot(causal.loc[w].index, causal.loc[w], color='#8e44ad', lw=1.5, ls=':', label='MA28 causal')
        ax.set_title(titulo, fontweight='bold', fontsize=10)
        ax.tick_params(axis='x', labelrotation=30, labelsize=8)
        ax.set_ylabel('millones de usuarios')

    fig, axes = plt.subplots(3, 2, figsize=(14, 13))
    ventana(axes[0, 0], '2023-11-15', '2024-03-15', 'A. Caída de enero de 2024 (días reconstruidos):\nel pasa-bajos ondula (Gibbs); la MA28 suaviza el valle', causal_on=True)
    axes[0, 0].legend(fontsize=7, loc='lower right')
    ventana(axes[0, 1], '2022-01-01', '2022-04-15', 'B. Borde inicial: la MA28 centrada no existe en los primeros 14 días;\nel pasa-bajos y STL sí dan valor (con más error)')
    ventana(axes[1, 0], '2026-06-15', '2026-10-29', 'C. Borde final: lo mismo al final de la serie')
    # D: subte con salto de mayo 2024 (retraso de la media causal)
    sub = hc.tramo_continuo(df, 'subte_amba')
    cm = hc.media_movil_centrada(sub, 28); cc = sub.rolling(28).mean()
    ax = axes[1, 1]
    w = slice('2024-04-10', '2024-07-31')
    ax.plot(sub.loc[w].index, sub.loc[w], color='#bdc3c7', lw=1, label='subte observado')
    ax.plot(cm.loc[w].index, cm.loc[w], color='#c0392b', lw=1.8, label='MA28 centrada')
    ax.plot(cc.loc[w].index, cc.loc[w], color='#8e44ad', lw=1.8, ls=':', label='MA28 causal (solo pasado)')
    ax.axvline(pd.Timestamp('2024-05-17'), color='k', lw=1, alpha=0.6); ax.text(pd.Timestamp('2024-05-18'), sub.loc[w].max() * 0.95, 'salto tarifario\n17-may-2024', fontsize=8)
    ax.set_title('D. Retraso de la media causal ante un cambio de nivel (subte)', fontweight='bold', fontsize=10)
    ax.legend(fontsize=7); ax.tick_params(axis='x', labelrotation=30, labelsize=8); ax.set_ylabel('millones de usuarios')
    # E: serie desestacionalizada alrededor de las elecciones con gratuidad de 2023
    ax = axes[2, 0]
    w = slice('2023-10-01', '2023-11-30')
    desest_stl = s - stl.seasonal
    ax.plot(s.loc[w].index, s.loc[w], color='#bdc3c7', lw=1, label='observada')
    ax.plot(notch.loc[w].index, notch.loc[w], color='#27ae60', lw=1.6, label='elimina-banda (FFT)')
    ax.plot(desest_stl.loc[w].index, desest_stl.loc[w], color='#2980b9', lw=1.4, ls='--', label='serie - componente semanal STL')
    ax.plot(ma7.loc[w].index, ma7.loc[w], color='#c0392b', lw=1.4, ls=':', label='MA7 centrada')
    ax.axhline(0, color='k', lw=0.8)
    for f in ('2023-10-22', '2023-11-19'):
        ax.axvline(pd.Timestamp(f), color='#8e44ad', alpha=0.4)
    ax.set_title('E. Elecciones con gratuidad (22-oct y 19-nov-2023):\nserie desestacionalizada por tres métodos', fontweight='bold', fontsize=10)
    ax.legend(fontsize=7, loc='lower left'); ax.tick_params(axis='x', labelrotation=30, labelsize=8); ax.set_ylabel('millones de usuarios')
    # F: el patrón semanal que quita cada método (perfil medio por día de la semana)
    ax = axes[2, 1]
    dias = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
    perfil = {'componente semanal STL': stl.seasonal, 'serie - MA7': (s - ma7), 'serie - elimina-banda (FFT)': (s - notch)}
    for (n, x), col in zip(perfil.items(), ['#2980b9', '#c0392b', '#27ae60']):
        g = x.groupby(x.index.dayofweek).mean()
        ax.plot(range(7), g.values, marker='o', color=col, label=n)
    ax.set_xticks(range(7)); ax.set_xticklabels(dias); ax.axhline(0, color='k', lw=0.6)
    ax.set_title('F. Qué patrón semanal resta cada método (promedio por día de la semana)', fontweight='bold', fontsize=10)
    ax.set_ylabel('millones de usuarios'); ax.legend(fontsize=7)
    guardar('fig32_descomposicion_detalle.png')
    return s, stl, ma28, causal, bajos, notch, ma7


def tabla_comparacion(df, s, stl, ma28, causal, bajos, notch, ma7):
    tr = stl.trend
    interior = slice(14, -14)
    filas = []

    def err(x, nombre, detalle):
        d = (x - tr)
        di = d.iloc[interior].dropna()
        borde = pd.concat([d.iloc[:14], d.iloc[-14:]]).dropna()
        filas.append({'metodo': nombre, 'dias_con_valor': int(x.notna().sum()), 'dias_sin_valor': int(x.isna().sum()),
                      'RMSE_vs_STL_interior_M': round(float(np.sqrt((di ** 2).mean())), 3),
                      'RMSE_vs_STL_bordes_M': round(float(np.sqrt((borde ** 2).mean())), 3) if len(borde) else np.nan,
                      'correlacion_con_STL': round(float(np.corrcoef(x.dropna(), tr.loc[x.dropna().index])[0, 1]), 3), 'nota': detalle})
    err(ma28, 'MA28 centrada', 'pierde 27 días (14 en cada extremo, aprox.)')
    err(causal, 'MA28 causal', 'solo usa pasado; llega unos 14 días tarde')
    err(bajos, 'Pasa-bajos ideal (FFT)', 'ondula cerca de cambios bruscos (Gibbs)')
    t = pd.DataFrame(filas)
    t.to_csv(os.path.join(TAB, 'tabla_comparacion_tendencia.csv'), index=False)
    # desestacionalización: qué tan negativo queda en los días de colapso
    fil2 = []
    colapso = pd.to_datetime(['2023-08-13', '2023-10-22', '2023-11-19'])
    for nombre, x in [('Serie - componente semanal STL', s - stl.seasonal), ('MA7 centrada', ma7), ('Elimina-banda (FFT)', notch)]:
        x = x.dropna()
        fil2.append({'metodo': nombre, 'minimo_M': round(float(x.min()), 3), 'dias_con_valor_menor_o_igual_a_0': int((x <= 0).sum()),
                     'valor_medio_en_elecciones_gratuitas_M': round(float(x.reindex(colapso).mean()), 3)})
    t2 = pd.DataFrame(fil2)
    t2.to_csv(os.path.join(TAB, 'tabla_comparacion_desestacionalizada.csv'), index=False)
    print(t.to_string(index=False)); print(t2.to_string(index=False))
    return t, t2


def fig_comparacion(t, t2):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    x = np.arange(len(t)); w = 0.38
    ax = axes[0]
    ax.bar(x - w / 2, t.RMSE_vs_STL_interior_M, w, label='interior', color='#2980b9')
    ax.bar(x + w / 2, t.RMSE_vs_STL_bordes_M.fillna(0), w, label='bordes (14 días en cada extremo)', color='#e67e22')
    ax.set_xticks(x); ax.set_xticklabels([m.replace(' (', '\n(') for m in t.metodo], fontsize=8)
    ax.set_ylabel('RMSE contra la tendencia de STL (M)'); ax.legend(fontsize=8)
    ax.set_title('Tendencia: cuánto se aparta cada método de STL', fontweight='bold', fontsize=10)
    ax = axes[1]
    ax.bar(range(len(t2)), t2.minimo_M, color=['#2980b9', '#c0392b', '#27ae60'])
    ax.set_xticks(range(len(t2))); ax.set_xticklabels([m.replace(' - ', '\n- ').replace(' (', '\n(') for m in t2.metodo], fontsize=8)
    ax.axhline(0, color='k', lw=0.8); ax.set_ylabel('valor mínimo de la serie desestacionalizada (M)')
    ax.set_title('Desestacionalizada: valor más bajo', fontweight='bold', fontsize=10)
    ax = axes[2]
    ax.bar(range(len(t2)), t2.valor_medio_en_elecciones_gratuitas_M, color=['#2980b9', '#c0392b', '#27ae60'])
    ax.set_xticks(range(len(t2))); ax.set_xticklabels([m.replace(' - ', '\n- ').replace(' (', '\n(') for m in t2.metodo], fontsize=8)
    ax.axhline(0, color='k', lw=0.8); ax.set_ylabel('valor medio en las 3 elecciones con gratuidad (M)')
    ax.set_title('Desestacionalizada en días de colapso', fontweight='bold', fontsize=10)
    guardar('fig33_comparacion_descomposicion.png')


# --- fig34: detalle de la CCF -----------------------------------------------------------------

def fig_ccf_detalle(df):
    idx = hc.tramo_continuo(df, 'total_amba').index
    tren = hc.tramo_continuo(df, 'tren_amba'); col = hc.tramo_continuo(df, 'colectivo_amba')
    rt = hc.quitar_calendario(tren, idx); rc = hc.quitar_calendario(col, idx)
    n = len(idx)
    c = hc.ccf(rt.values, rc.values, max_lag=14)
    ax_ = acf(rt.values, nlags=40, fft=True); ay_ = acf(rc.values, nlags=40, fft=True)
    suma = 1 + 2 * np.sum(ax_[1:] * ay_[1:])
    banda_ing = 1.96 / np.sqrt(n)
    banda_bart = 1.96 * np.sqrt(max(suma, 0) / n)
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    ax = axes[0, 0]
    ax.scatter(rt.values, rc.values, s=6, alpha=0.4, color='#2c3e50')
    b = np.polyfit(rt.values, rc.values, 1)
    xs = np.linspace(rt.min(), rt.max(), 50); ax.plot(xs, np.polyval(b, xs), color='#c0392b')
    ax.set_xlabel('residuo del tren (M)'); ax.set_ylabel('residuo del colectivo (M)')
    ax.set_title(f'A. Residuos del mismo día: r = {c.loc[0]:.2f}', fontweight='bold', fontsize=10)
    ax = axes[0, 1]
    ax.bar(c.index, c.values, color='#2980b9', width=0.8)
    ax.axhline(banda_ing, color='r', ls='--', lw=0.8, label=f'banda ingenua ±{banda_ing:.3f}')
    ax.axhline(-banda_ing, color='r', ls='--', lw=0.8)
    ax.axhline(banda_bart, color='#e67e22', ls='-', lw=1.2, label=f'banda de Bartlett ±{banda_bart:.3f}')
    ax.axhline(-banda_bart, color='#e67e22', ls='-', lw=1.2)
    ax.set_xlabel('rezago k (k>0: el colectivo va después del tren)'); ax.set_ylabel('correlación'); ax.legend(fontsize=8)
    ax.set_title('B. CCF de los residuos con dos bandas de significancia', fontweight='bold', fontsize=10)
    ax = axes[1, 0]
    periodos = {'2022-2023': ('2022-01-01', '2023-12-31'), '2024': ('2024-01-01', '2024-12-31'), '2025-2026': ('2025-01-01', '2026-10-29')}
    filas = []
    for (nombre, (a, b2)), colr in zip(periodos.items(), ['#2980b9', '#e67e22', '#27ae60']):
        m = (rt.index >= a) & (rt.index <= b2)
        cc = hc.ccf(rt.values[m], rc.values[m], max_lag=7)
        ax.plot(cc.index, cc.values, marker='o', color=colr, label=f'{nombre} (n={int(m.sum())})')
        filas.append({'periodo': nombre, 'dias': int(m.sum()), 'ccf_lag_0': round(cc.loc[0], 3), 'ccf_lag_-1': round(cc.loc[-1], 3), 'ccf_lag_1': round(cc.loc[1], 3)})
    ax.set_xlabel('rezago k'); ax.set_ylabel('correlación'); ax.legend(fontsize=8); ax.set_ylim(0, 1)
    ax.set_title('C. CCF por subperíodo', fontweight='bold', fontsize=10)
    ax = axes[1, 1]
    roll = rt.rolling(90).corr(rc)
    ax.plot(roll.index, roll.values, color='#2c3e50')
    ax.set_ylim(0, 1); ax.set_ylabel('correlación en rezago 0'); ax.axhline(c.loc[0], color='#c0392b', ls='--', lw=0.8, label=f'total del período: {c.loc[0]:.2f}')
    ax.legend(fontsize=8)
    ax.set_title('D. Correlación del mismo día en ventanas móviles de 90 días', fontweight='bold', fontsize=10)
    guardar('fig34_ccf_detalle.png')
    t = pd.DataFrame(filas)
    t.to_csv(os.path.join(TAB, 'tabla_ccf_por_subperiodo.csv'), index=False)
    print(t.to_string(index=False))
    print(f'banda ingenua {banda_ing:.3f}; banda Bartlett {banda_bart:.3f}; corr rolling min/max = {roll.min():.2f}/{roll.max():.2f}')
    print('CCF lag -1,0,1:', c.loc[-1], c.loc[0], c.loc[1])


def main():
    df = hc.cargar()
    fig_estacionariedad(df)
    print(fig_acf_versiones(df).to_string(index=False))
    fig_residuo_stl(df)
    s, stl, ma28, causal, bajos, notch, ma7 = fig_descomposicion_detalle(df)
    t, t2 = tabla_comparacion(df, s, stl, ma28, causal, bajos, notch, ma7)
    fig_comparacion(t, t2)
    fig_ccf_detalle(df)


if __name__ == '__main__':
    main()
