"""
Herramientas vistas en clase aplicadas a la serie SUBE (Pregunta 1: comportamiento de la demanda).

  1. ADF + KPSS con la tabla de decisión conjunta de la clase de Forecasting
  2. FFT con la componente continua (DC) removida; Parseval
  3. Descomposición "a mano" con medias móviles (Serie-MA7, MA7-MA28) vs. STL
  4. Filtros en el dominio de la frecuencia (pasa-bajos y elimina-banda) vs. medias móviles
  5. Correlación cruzada (CCF) tren-colectivo, sobre series sin calendario
  6. ACF de la serie

Decisiones de diseño:
  - Tramo principal: 2024-02-01 en adelante (960 días continuos, sin ningún día imputado).
    Se recorta a un múltiplo de 7 días para que el ciclo semanal caiga exacto en un bin de la FFT.
  - Sensibilidad: serie imputada completa desde 2022-01-01 (1.722 días = 246 semanas).
  - COVID queda fuera: todo el análisis es desde 2022.

Entrada: data/procesado/serie_sube_diaria_imputada.csv (generada por calidad_datos.py)
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import holidays
from statsmodels.tsa.stattools import adfuller, kpss, acf
from statsmodels.tsa.seasonal import STL

warnings.filterwarnings('ignore')
plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROC_PATH = os.path.join(BASE_DIR, "data", "procesado", "serie_sube_diaria_imputada.csv")
FIG_DIR = os.path.join(BASE_DIR, "resultados", "figuras")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")
os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(TABLA_DIR, exist_ok=True)

MODOS = ['total_amba', 'colectivo_amba', 'subte_amba', 'tren_amba']
COLORES = {'total_amba': '#2c3e50', 'colectivo_amba': '#2980b9', 'subte_amba': '#e67e22', 'tren_amba': '#27ae60'}
INICIO_TRAMO = '2024-02-01'
INICIO_SENSIBILIDAD = '2022-01-01'
SEMANA = 7


# --- Datos --------------------------------------------------------------------

def cargar():
    df = pd.read_csv(PROC_PATH, parse_dates=['fecha']).set_index('fecha').asfreq('D')
    df['imputado'] = df['imputado'].astype(bool)
    return df


def tramo_continuo(df, col, inicio=INICIO_TRAMO):
    """Serie en millones, desde `inicio`, recortada a semanas completas (las últimas)."""
    s = df.loc[inicio:, col] / 1e6
    n = len(s) // SEMANA * SEMANA
    return s.iloc[-n:]


# --- 1. ADF + KPSS con la tabla de decisión de clase ----------------------------

def decision_clase(adf_p, kpss_p):
    """Tabla de la clase del 26/10: ADF rechaza H0 (p<0,05) y KPSS no rechaza (p>=0,05) => estacionaria."""
    adf_rechaza = adf_p < 0.05
    kpss_rechaza = kpss_p < 0.05
    if adf_rechaza and not kpss_rechaza:
        return 'estacionaria'
    if not adf_rechaza and kpss_rechaza:
        return 'NO estacionaria'
    return 'indefinida'


def tests_estacionariedad(df, inicio=INICIO_TRAMO):
    filas = []
    for col in MODOS:
        s = tramo_continuo(df, col, inicio)
        variantes = {
            'nivel': s,
            'dif. simple (d=1)': s.diff().dropna(),
            'dif. estacional (s=7)': s.diff(SEMANA).dropna(),
            'dif. simple + estacional': s.diff().diff(SEMANA).dropna(),
        }
        for nombre, x in variantes.items():
            adf_p = adfuller(x, autolag='AIC')[1]
            kpss_p = kpss(x, regression='c', nlags='auto')[1]
            filas.append({'tramo_desde': inicio, 'serie': col, 'transformacion': nombre, 'ADF_p': round(adf_p, 4),
                          'KPSS_p (acotado 0,01-0,10)': round(kpss_p, 4),
                          'decision_clase': decision_clase(adf_p, kpss_p)})
    return pd.DataFrame(filas)


# --- 2. FFT sin DC ----------------------------------------------------------------

def espectro(s, quitar_tendencia=False):
    """Espectro de amplitud (en millones de usuarios) con la DC anulada.

    La FFT asume una serie periódica: por eso se recortó a semanas completas.
    """
    x = s.values.astype(float)
    n = len(x)
    if quitar_tendencia:
        t = np.arange(n)
        x = x - np.polyval(np.polyfit(t, x, 1), t)
    X = np.fft.fft(x)
    energia_t = np.sum(x ** 2)
    energia_f = np.sum(np.abs(X) ** 2) / n          # Parseval
    X[0] = 0                                        # quitar la componente continua
    amp = 2 * np.abs(X[:n // 2 + 1]) / n
    freq = np.arange(n // 2 + 1) / n                # ciclos por día
    return freq, amp, (energia_t, energia_f)


def picos(freq, amp, k=8, min_sep=3):
    """Los k picos más altos (separados al menos `min_sep` bins), con su período en días."""
    orden = np.argsort(amp)[::-1]
    elegidos = []
    for i in orden:
        if i == 0:
            continue
        if all(abs(i - j) >= min_sep for j in elegidos):
            elegidos.append(i)
        if len(elegidos) == k:
            break
    return pd.DataFrame({'frecuencia_ciclos_dia': freq[elegidos].round(5),
                         'periodo_dias': (1 / freq[elegidos]).round(2),
                         'amplitud_M': amp[elegidos].round(4)})


# --- 3. Descomposición con medias móviles vs. STL --------------------------------

def media_movil_centrada(s, n):
    """MA centrada de n términos; los bordes quedan en NaN (la serie no es periódica)."""
    return s.rolling(n, center=True).mean()


def descomposicion_ma(s, ventana_corta=7, ventana_larga=28):
    """Serie-MA7 (residuo rápido), MA7-MA28 (componente mensual), MA28 (tendencia).

    Se usa 28 y no 30: una MA de largo múltiplo de 7 anula exactamente el ciclo semanal.
    """
    ma7 = media_movil_centrada(s, ventana_corta)
    ma_larga = media_movil_centrada(s, ventana_larga)
    return pd.DataFrame({'observada': s, 'MA7': ma7, 'MA28_tendencia': ma_larga,
                         'residuo_rapido': s - ma7, 'componente_mensual': ma7 - ma_larga})


# --- 4. Filtros en el dominio de la frecuencia ------------------------------------

def filtrar_df(s, mascara_fn):
    """FFT directa, producto por una máscara simétrica (usa |f|) y FFT inversa."""
    x = s.values.astype(float)
    n = len(x)
    X = np.fft.fft(x)
    f = np.abs(np.fft.fftfreq(n))
    y = np.real(np.fft.ifft(X * mascara_fn(f, n)))
    return pd.Series(y, index=s.index)


def pasa_bajos(fc):
    return lambda f, n: (f <= fc).astype(float)


def elimina_banda_semanal(armonicas=(1, 2, 3)):
    """Anula 1/7, 2/7 y 3/7 ciclos/día (±1 bin) y sus espejos; deja pasar la DC."""
    def m(f, n):
        mask = np.ones(n)
        for h in armonicas:
            mask[np.abs(f - h / SEMANA) <= 1.5 / n] = 0
        return mask
    return m


def amplitud_en(s, freq_objetivo):
    """Amplitud del espectro (sin DC) en la frecuencia dada."""
    f, a, _ = espectro(s)
    return float(a[np.argmin(np.abs(f - freq_objetivo))])


def lag_del_maximo(x, y, max_lag=30):
    """Lag k que maximiza corr(x_t, y_{t+k}). k>0: y va después que x."""
    return max(range(-max_lag, max_lag + 1), key=lambda k: _corr_con_lag(x, y, k))


# --- 5. Correlación cruzada ---------------------------------------------------------

def _corr_con_lag(x, y, k):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if k >= 0:
        a, b = x[:len(x) - k], y[k:]
    else:
        a, b = x[-k:], y[:len(y) + k]
    return float(np.corrcoef(a, b)[0, 1])


def ccf(x, y, max_lag=14):
    """corr(x_t, y_{t+k}) para k en [-max_lag, max_lag]."""
    ks = list(range(-max_lag, max_lag + 1))
    return pd.Series([_corr_con_lag(x, y, k) for k in ks], index=ks)


def quitar_calendario(s, idx):
    """Residuo de regresar la serie en día de la semana, feriado y tendencia lineal.

    Evita que la correlación entre modos refleje solo el calendario compartido.
    """
    feriados = holidays.Argentina(years=range(2022, 2027))
    X = pd.get_dummies(pd.Series(idx.day_of_week, index=idx), dtype=float)
    X['feriado'] = [1.0 if d in feriados else 0.0 for d in idx]
    X['tendencia'] = np.arange(len(idx)) / len(idx)
    beta, *_ = np.linalg.lstsq(X.values, s.values, rcond=None)
    return pd.Series(s.values - X.values @ beta, index=idx)


def respuesta_colectivo_en_dias_candidatos(df, fechas):
    """Cociente de cada modo contra la mediana del mismo día de la semana (±4 semanas), días -1, 0 y +1."""
    filas = []
    for col in ['colectivo_amba', 'subte_amba', 'tren_amba']:
        s = df[col].where(~df['imputado'])
        vec = pd.concat([s.shift(7 * k) for k in (-4, -3, -2, -1, 1, 2, 3, 4)], axis=1).median(axis=1)
        razon = s / vec
        for f in fechas:
            f = pd.Timestamp(f)
            for d in (-1, 0, 1):
                filas.append({'fecha_candidata': f.date(), 'dia_relativo': d, 'modo': col,
                              'cociente_vs_mediana': round(float(razon.get(f + pd.Timedelta(days=d), np.nan)), 2)})
    t = pd.DataFrame(filas)
    return t.pivot_table(index=['fecha_candidata', 'dia_relativo'], columns='modo',
                         values='cociente_vs_mediana').reset_index()


# --- Figuras ------------------------------------------------------------------------

def fig_fft(df):
    s = tramo_continuo(df, 'total_amba')
    fig, axes = plt.subplots(2, 1, figsize=(13, 9))
    f, a, _ = espectro(s)
    ax = axes[0]
    ax.plot(f, a, color=COLORES['total_amba'], lw=1.2)
    for h in (1, 2, 3):
        ax.axvline(h / SEMANA, color='#c0392b', ls='--', alpha=0.6)
        ax.text(h / SEMANA + 0.003, a.max() * 0.92, f'{h}/7\n({SEMANA / h:.1f} d)', color='#c0392b', fontsize=9)
    ax.set_xlim(0, 0.5)
    ax.set_title(f'Espectro de amplitud del total AMBA, DC removida (feb-2024 a sep-2026, N={len(s)} días)',
                 fontweight='bold')
    ax.set_xlabel('Frecuencia (ciclos/día)'); ax.set_ylabel('Amplitud (millones de usuarios)')
    ax = axes[1]
    for col in ['colectivo_amba', 'subte_amba', 'tren_amba']:
        fm, am, _ = espectro(tramo_continuo(df, col))
        ax.semilogy(fm, am, color=COLORES[col], lw=1, label=col, alpha=0.9)
    for h in (1, 2, 3):
        ax.axvline(h / SEMANA, color='#c0392b', ls='--', alpha=0.4)
    ax.set_xlim(0, 0.5)
    ax.set_title('Espectro por modo (escala logarítmica)', fontweight='bold')
    ax.set_xlabel('Frecuencia (ciclos/día)'); ax.set_ylabel('Amplitud (M, log)')
    ax.legend()
    plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig8_fft_espectro_semanal.png'), dpi=200); plt.close()


def fig_descomposicion(df):
    s = tramo_continuo(df, 'total_amba')
    d = descomposicion_ma(s)
    stl = STL(s, period=SEMANA, robust=True).fit()
    fig, axes = plt.subplots(4, 1, figsize=(14, 11), sharex=True)
    axes[0].plot(s.index, s, color='#7f8c8d', lw=0.8, label='Observada')
    axes[0].plot(d.index, d['MA7'], color='#2980b9', lw=1.1, label='MA7')
    axes[0].plot(d.index, d['MA28_tendencia'], color='#c0392b', lw=1.8, label='MA28')
    axes[0].set_title('Descomposición manual con medias móviles (total AMBA)', fontweight='bold')
    axes[0].set_ylabel('Millones'); axes[0].legend(loc='lower right')
    axes[1].plot(d.index, d['residuo_rapido'], color='#7f8c8d', lw=0.8)
    axes[1].axhline(0, color='k', lw=0.6)
    axes[1].set_ylabel('Serie - MA7\n(residuo rápido)')
    axes[2].plot(d.index, d['componente_mensual'], color='#8e44ad', lw=1.1)
    axes[2].axhline(0, color='k', lw=0.6)
    axes[2].set_ylabel('MA7 - MA28\n(componente mensual)')
    axes[3].plot(d.index, d['MA28_tendencia'], color='#c0392b', lw=1.6, label='MA28 (a mano)')
    axes[3].plot(stl.trend.index, stl.trend, color='#27ae60', lw=1.4, ls='--', label='Tendencia STL')
    axes[3].set_ylabel('Tendencia'); axes[3].legend(loc='lower right')
    plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig9_descomposicion_ma_vs_stl.png'), dpi=200); plt.close()
    return d, stl


def fig_filtros_df(df):
    s = tramo_continuo(df, 'total_amba')
    tend_df = filtrar_df(s, pasa_bajos(1 / 28))
    desest_df = filtrar_df(s, elimina_banda_semanal())
    ma28 = media_movil_centrada(s, 28)
    ma7 = media_movil_centrada(s, 7)
    stl = STL(s, period=SEMANA, robust=True).fit()
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    ax = axes[0]
    ax.plot(s.index, s, color='#bdc3c7', lw=0.8, label='Observada')
    ax.plot(tend_df.index, tend_df, color='#2980b9', lw=1.8, label='Pasa-bajos DF (periodos > 28 d)')
    ax.plot(ma28.index, ma28, color='#c0392b', lw=1.4, ls='--', label='MA28 centrada')
    ax.set_title('Tendencia: filtro pasa-bajos en frecuencia vs. media móvil', fontweight='bold')
    ax.set_ylabel('Millones'); ax.legend(loc='lower right')
    ax = axes[1]
    ax.plot(s.index, s, color='#bdc3c7', lw=0.8, label='Observada')
    ax.plot(desest_df.index, desest_df, color='#27ae60', lw=1.3, label='Elimina-banda 1/7, 2/7, 3/7 (DF)')
    ax.plot(ma7.index, ma7, color='#c0392b', lw=1.2, ls='--', label='MA7 centrada')
    ax.set_title('Serie desestacionalizada (sin ciclo semanal)', fontweight='bold')
    ax.set_ylabel('Millones'); ax.legend(loc='lower right')
    plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig10_filtros_df_vs_ma.png'), dpi=200); plt.close()
    return s, tend_df, desest_df, ma7, ma28, stl


def fig_ccf_acf(df):
    idx = tramo_continuo(df, 'total_amba').index
    tren = tramo_continuo(df, 'tren_amba'); col = tramo_continuo(df, 'colectivo_amba')
    res_tren = quitar_calendario(tren, idx); res_col = quitar_calendario(col, idx)
    dif_tren = tren.diff().diff(SEMANA).dropna(); dif_col = col.diff().diff(SEMANA).dropna()
    ccf_res = ccf(res_tren.values, res_col.values)
    ccf_dif = ccf(dif_tren.values, dif_col.values)
    banda = 1.96 / np.sqrt(len(idx))
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
    for ax, c, tit in [(axes[0], ccf_res, 'CCF tren-colectivo\n(residuos sin calendario)'),
                       (axes[1], ccf_dif, 'CCF tren-colectivo\n(dif. simple + estacional)')]:
        ax.bar(c.index, c.values, color='#2980b9', width=0.8)
        ax.axhline(banda, color='r', ls='--', lw=0.8); ax.axhline(-banda, color='r', ls='--', lw=0.8)
        ax.set_title(tit, fontweight='bold'); ax.set_xlabel('Lag k (k>0: el colectivo va después del tren)')
        ax.set_ylabel('Correlación')
    tot = tramo_continuo(df, 'total_amba')
    a = acf(tot, nlags=42, fft=True)
    axes[2].bar(range(len(a)), a, color='#2c3e50', width=0.7)
    for k in (7, 14, 21, 28, 35, 42):
        axes[2].axvline(k, color='#c0392b', ls=':', alpha=0.5)
    axes[2].axhline(1.96 / np.sqrt(len(tot)), color='r', ls='--', lw=0.8)
    axes[2].axhline(-1.96 / np.sqrt(len(tot)), color='r', ls='--', lw=0.8)
    axes[2].set_title('ACF del total AMBA\n(picos en lags múltiplos de 7)', fontweight='bold')
    axes[2].set_xlabel('Lag (días)')
    plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig11_ccf_tren_colectivo_y_acf.png'), dpi=200); plt.close()
    return ccf_res, ccf_dif


# --- Principal ------------------------------------------------------------------------

def main():
    df = cargar()
    tramo = tramo_continuo(df, 'total_amba')
    assert not df.loc[tramo.index, 'imputado'].any(), "El tramo principal no debe tener días imputados"
    print(f">>> Tramo principal: {tramo.index[0].date()} a {tramo.index[-1].date()} "
          f"({len(tramo)} días = {len(tramo) // 7} semanas, sin días imputados)")

    print("\n>>> 1. ADF + KPSS con la tabla de decisión de clase")
    t1 = tests_estacionariedad(df)
    t1_sens = tests_estacionariedad(df, INICIO_SENSIBILIDAD)  # sensibilidad: serie imputada desde 2022
    pd.concat([t1, t1_sens]).to_csv(os.path.join(TABLA_DIR, 'tabla_adf_kpss_decision_clase.csv'), index=False)
    print(t1.to_string(index=False))
    print("Sensibilidad (serie imputada desde 2022): decisión de clase en nivel por serie:")
    print(t1_sens[t1_sens['transformacion'] == 'nivel'][['serie', 'ADF_p', 'KPSS_p (acotado 0,01-0,10)', 'decision_clase']].to_string(index=False))

    print("\n>>> 2. FFT sin DC")
    f, a, (et, ef) = espectro(tramo)
    print(f"Parseval: energía en el tiempo = {et:.4f}, en frecuencia = {ef:.4f}")
    p = picos(f, a)
    p.to_csv(os.path.join(TABLA_DIR, 'tabla_fft_picos_total.csv'), index=False)
    print(p.to_string(index=False))
    fig_fft(df)
    amp_sin = amplitud_en(tramo, 1 / 7)
    f2, a2, _ = espectro(tramo, quitar_tendencia=True)
    print(f"Amplitud semanal 1/7: {amp_sin:.4f} M (sin quitar tendencia) vs "
          f"{a2[np.argmin(np.abs(f2 - 1 / 7))]:.4f} M (tendencia lineal removida)")
    sens = tramo_continuo(df, 'total_amba', inicio=INICIO_SENSIBILIDAD)
    fs, as_, _ = espectro(sens)
    print(f"Sensibilidad (serie imputada 2022+, {len(sens)} días): amplitud 1/7 = "
          f"{as_[np.argmin(np.abs(fs - 1 / 7))]:.4f} M; picos:")
    print(picos(fs, as_, k=6).to_string(index=False))

    print("\n>>> 3. Descomposición con medias móviles vs STL")
    d, stl = fig_descomposicion(df)
    ok = d.dropna()
    corr_t = np.corrcoef(ok['MA28_tendencia'], stl.trend.loc[ok.index])[0, 1]
    rmse_t = float(np.sqrt(np.mean((ok['MA28_tendencia'] - stl.trend.loc[ok.index]) ** 2)))
    fer = holidays.Argentina(years=range(2022, 2027))
    es_fer = pd.Series([x in fer for x in ok.index], index=ok.index)
    print(f"Tendencia MA28 vs STL: correlación = {corr_t:.4f}, RMSE = {rmse_t:.4f} M")
    print(f"Residuo rápido (Serie-MA7): media en feriados = {ok.loc[es_fer, 'residuo_rapido'].mean():.3f} M, "
          f"en no feriados = {ok.loc[~es_fer, 'residuo_rapido'].mean():.3f} M, desvío = {ok['residuo_rapido'].std():.3f} M")
    print(f"Amplitud 1/7 en MA7 = {amplitud_en(d['MA7'].dropna().iloc[:len(d['MA7'].dropna()) // 7 * 7], 1 / 7):.5f} M "
          f"(original: {amp_sin:.4f} M)")

    print("\n>>> 4. Filtros en el dominio de la frecuencia")
    s, tend_df, desest_df, ma7, ma28, stl2 = fig_filtros_df(df)
    print(f"Amplitud 1/7 tras elimina-banda DF = {amplitud_en(desest_df, 1 / 7):.6f} M")
    inter = slice(14, -14)
    dif = (tend_df - stl2.trend).abs()
    print(f"Pasa-bajos DF vs tendencia STL: error medio interior = {dif.iloc[inter].mean():.4f} M, "
          f"en primeros/últimos 14 días = {pd.concat([dif.iloc[:14], dif.iloc[-14:]]).mean():.4f} M")
    causal28 = s.rolling(28).mean()
    ok2 = causal28.dropna()
    print(f"Retraso (lag del máximo de correlación) de la MA28 causal respecto del pasa-bajos DF: "
          f"{lag_del_maximo(tend_df.loc[ok2.index].values, ok2.values)} días "
          f"(la MA centrada no tiene retraso)")

    print("\n>>> 5. CCF tren-colectivo y ACF")
    ccf_res, ccf_dif = fig_ccf_acf(df)
    banda = 1.96 / np.sqrt(len(tramo))
    print(f"Banda de significancia ±{banda:.3f}")
    print("CCF residuos sin calendario, lags -2..2:", ccf_res.loc[-2:2].round(3).to_dict())
    print("CCF dif. simple+estacional, lags -2..2:", ccf_dif.loc[-2:2].round(3).to_dict())
    pd.DataFrame({'lag': ccf_res.index, 'ccf_residuos_sin_calendario': ccf_res.values.round(4),
                  'ccf_dif_simple_estacional': ccf_dif.values.round(4)}).to_csv(
        os.path.join(TABLA_DIR, 'tabla_ccf_tren_colectivo.csv'), index=False)

    print("\n>>> 6. Respuesta del colectivo en días candidatos a paro (a verificar con fuentes)")
    cand = ['2024-02-21', '2024-05-09', '2024-10-30', '2025-04-10', '2026-02-19']
    t6 = respuesta_colectivo_en_dias_candidatos(df, cand)
    t6.to_csv(os.path.join(TABLA_DIR, 'tabla_dias_candidatos_paro.csv'), index=False)
    print(t6.to_string(index=False))


if __name__ == '__main__':
    main()
