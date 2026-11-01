"""
Control sintético para los saltos del colectivo del AMBA (pregunta P-1, componente causal).

Idea: lo que habría pasado con la demanda de colectivo del AMBA sin el aumento se estima con una combinación de
ciudades del interior (fuera del AMBA, también en SUBE) cuyas tarifas no cambiaron con ese aumento nacional. Los
pesos (no negativos, suman 1) se eligen para que la combinación replique la demanda del AMBA en las 52 semanas
previas; la brecha después del aumento es el efecto estimado.

Se usa el logaritmo de los usos medios diarios de días hábiles normales (lunes a viernes sin feriado, paro ni
elección; al menos 3 días por semana). Inferencia por placebos en el espacio: el mismo procedimiento aplicado a cada
ciudad donante como si hubiera sido la tratada; el p-valor es la proporción de placebos con una relación brecha
posterior / ajuste previo (RMSPE) igual o mayor que la del AMBA.

Límites: (1) las ciudades del interior fijan sus propias tarifas y ajustan seguido; si subieron en la misma
ventana, el efecto se subestima. No se pudo verificar la tarifa de cada ciudad; el placebo en el espacio es el
chequeo disponible. (2) Para el tren y el subte no hay donantes, así que el método solo se aplica al colectivo.
(3) El AMBA tiene una tarifa nacional y las del interior no son comparables en nivel, solo en tendencia.

Entradas: data/raw_usos/dat-ab-usos-{2022..2026}.csv, data/hitos/hitos_paros_elecciones.csv
Salidas:  resultados/tablas/tabla_control_sintetico.csv, tabla_control_sintetico_donantes.csv
          resultados/figuras/fig18_control_sintetico.png
"""

import os
import numpy as np
import pandas as pd
import holidays
import matplotlib.pyplot as plt
from scipy.optimize import minimize

plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(BASE_DIR, "data", "raw_usos")
EVT = os.path.join(BASE_DIR, "data", "hitos", "hitos_paros_elecciones.csv")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")
FIG_DIR = os.path.join(BASE_DIR, "resultados", "figuras")

INICIO, FIN = '2022-01-03', '2026-09-27'
MIN_USOS_DIARIOS = 3000
N_DONANTES = 40
SEMANAS_PRE = 52
SEMANAS_POST = (2, 8)     # semanas después del aumento que se promedian (se salta la primera por la transición)
EVENTOS = [('2024-01-15', '2024-02-06', 'colectivo nacional, enero-febrero 2024 (tarifa x5)'),
           ('2024-08-12', '2024-08-12', 'colectivo nacional, agosto 2024 (+37%)'),
           ('2026-02-18', '2026-02-18', 'colectivo nacional, febrero 2026 (+31%)')]


def cargar_colectivos():
    partes = []
    for a in range(2022, 2027):
        d = pd.read_csv(os.path.join(RAW, f"dat-ab-usos-{a}.csv"), low_memory=False,
                        usecols=['DIA_TRANSPORTE', 'AMBA', 'TIPO_TRANSPORTE', 'JURISDICCION', 'PROVINCIA', 'MUNICIPIO', 'CANTIDAD'])
        partes.append(d[d.TIPO_TRANSPORTE == 'COLECTIVO'])
    d = pd.concat(partes)
    d['fecha'] = pd.to_datetime(d['DIA_TRANSPORTE'])
    return d


def semanal_normal(diario, evt):
    fer = holidays.Argentina(years=range(2021, 2027))
    excl = set(evt['fecha'])
    idx = diario.index
    normal = pd.Series([(f.day_of_week < 5) and (f not in fer) and (f not in excl) for f in idx], index=idx)
    dn = diario.where(normal, np.nan) if isinstance(diario, pd.Series) else diario.where(normal, axis=0)
    semana = idx.to_period('W-SUN').start_time
    cuenta = dn.notna().groupby(semana).sum()
    return np.log(dn.groupby(semana).mean()).where(cuenta >= 3)


def pesos_sinteticos(y_tratada, donantes):
    X = donantes.values
    n = X.shape[1]
    f = lambda w: np.sum((y_tratada.values - X @ w) ** 2)
    r = minimize(f, np.ones(n) / n, method='SLSQP', bounds=[(0, 1)] * n, constraints={'type': 'eq', 'fun': lambda w: w.sum() - 1},
                 options={'maxiter': 500, 'ftol': 1e-12})
    return pd.Series(r.x, index=donantes.columns)


def ajustar(y, donantes_cols, tratada, f_ini, f_fin):
    """Devuelve (brecha media posterior, RMSPE previo, RMSPE posterior, pesos, series)."""
    s0 = f_ini.to_period('W-SUN').start_time
    s1 = f_fin.to_period('W-SUN').start_time
    w = pd.Timedelta(weeks=1)
    pre = y.loc[s0 - SEMANAS_PRE * w: s0 - w]
    post = y.loc[s1 + SEMANAS_POST[0] * w: s1 + SEMANAS_POST[1] * w]
    cols = [c for c in donantes_cols if c != tratada]
    ok = pre[cols + [tratada]].dropna(axis=1, thresh=int(0.9 * len(pre))).columns
    cols = [c for c in cols if c in ok]
    pre_ = pre[cols + [tratada]].dropna(); post_ = post[cols + [tratada]].dropna()
    if tratada not in ok or len(pre_) < 30 or len(post_) < 4:
        return None
    # se ajusta la diferencia respecto del promedio previo de cada serie (se compara tendencia, no nivel)
    mu = pre_.mean()
    wts = pesos_sinteticos(pre_[tratada] - mu[tratada], pre_[cols] - mu[cols])
    sint_pre = (pre_[cols] - mu[cols]) @ wts; sint_post = (post_[cols] - mu[cols]) @ wts
    gap_pre = (pre_[tratada] - mu[tratada]) - sint_pre
    gap_post = (post_[tratada] - mu[tratada]) - sint_post
    rm_pre = float(np.sqrt((gap_pre ** 2).mean())); rm_post = float(np.sqrt((gap_post ** 2).mean()))
    return float(gap_post.mean()), rm_pre, rm_post, wts, (pre_, post_, mu, cols, wts)


def main():
    evt = pd.read_csv(EVT, parse_dates=['fecha'])
    d = cargar_colectivos()
    amba = d[d.AMBA == 'SI'].groupby('fecha')['CANTIDAD'].sum().asfreq('D')
    fuera = d[d.AMBA == 'NO'].groupby(['PROVINCIA', 'MUNICIPIO', 'fecha'])['CANTIDAD'].sum().unstack(['PROVINCIA', 'MUNICIPIO'])
    fuera = fuera.reindex(pd.date_range(INICIO, FIN))
    cobertura = fuera.notna().mean()
    volumen = fuera.mean()
    elegibles = volumen[(cobertura > 0.97) & (volumen >= MIN_USOS_DIARIOS)].sort_values(ascending=False).head(N_DONANTES).index
    fuera = fuera[elegibles]
    fuera.columns = [f"{p} - {m}" for p, m in fuera.columns]
    y = semanal_normal(pd.concat([amba.rename('AMBA'), fuera], axis=1).loc[INICIO:FIN], evt)
    donantes = list(fuera.columns)
    print(f"Donantes elegibles: {len(donantes)} (usos diarios medios entre {volumen[elegibles].min():.0f} y {volumen[elegibles].max():.0f})")

    filas = []; fig, axs = plt.subplots(1, len(EVENTOS), figsize=(5 * len(EVENTOS), 4.2))
    for ax, (a, b, nombre) in zip(axs, EVENTOS):
        f_ini, f_fin = pd.Timestamp(a), pd.Timestamp(b)
        r = ajustar(y, donantes, 'AMBA', f_ini, f_fin)
        if r is None:
            print(nombre, 'no estimable'); continue
        gap, rm_pre, rm_post, wts, (pre_, post_, mu, cols, w) = r
        plac = []
        for dn in donantes:
            rr = ajustar(y, donantes, dn, f_ini, f_fin)
            if rr is not None and rr[1] > 0:
                plac.append((rr[0], rr[2] / rr[1]))
        ratio = rm_post / rm_pre
        p = (np.mean([x[1] >= ratio for x in plac]) if plac else np.nan)
        gaps = np.array([x[0] for x in plac])
        filas.append({'evento': nombre, 'brecha_log': round(gap, 3), 'cambio_pct': round((np.exp(gap) - 1) * 100, 1),
                      'rmspe_previo': round(rm_pre, 3), 'rmspe_posterior': round(rm_post, 3), 'razon_post_pre': round(ratio, 2),
                      'p_placebos': round(p, 3), 'n_placebos': len(plac), 'donantes_con_peso_mayor_5pct': int((wts > 0.05).sum()),
                      'placebo_p5_brecha': round(np.quantile(gaps, 0.05), 3), 'placebo_p95_brecha': round(np.quantile(gaps, 0.95), 3)})
        top = wts[wts > 0.05].sort_values(ascending=False)
        pd.DataFrame({'evento': nombre, 'donante': top.index, 'peso': top.values.round(3)}).to_csv(
            os.path.join(TABLA_DIR, 'tabla_control_sintetico_donantes.csv'), mode='a' if filas[:-1] else 'w', header=not filas[:-1], index=False)
        serie = pd.concat([pre_, post_]); sintetica = (serie[cols] - mu[cols]) @ w
        ax.plot(serie.index, serie['AMBA'] - mu['AMBA'], color='#2980b9', label='AMBA')
        ax.plot(serie.index, sintetica, color='#7f8c8d', ls='--', label='AMBA sintético')
        ax.axvline(f_ini.to_period('W-SUN').start_time, color='k', ls=':')
        ax.set_title(nombre, fontsize=9); ax.set_ylabel('log de usos (relativo al promedio previo)')
    axs[0].legend(); plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig18_control_sintetico.png'), dpi=200); plt.close()
    t = pd.DataFrame(filas); t.to_csv(os.path.join(TABLA_DIR, 'tabla_control_sintetico.csv'), index=False)
    print(t.to_string(index=False))
    print(pd.read_csv(os.path.join(TABLA_DIR, 'tabla_control_sintetico_donantes.csv')).to_string(index=False))


if __name__ == '__main__':
    main()
