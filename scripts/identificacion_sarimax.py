"""
Identificación del orden del SARIMAX (P-2) con las herramientas de la clase, solo con datos anteriores al primer
corte de la evaluación (hasta el 30-jun-2023), para no usar información del período de prueba.

Pasos:
  1. ADF + KPSS (tabla conjunta) sobre la serie, sobre la serie con diferencia estacional (7 días) y con una
     diferencia adicional; define cuántas diferencias hacen falta.
  2. ACF y PACF de la serie diferenciada: sugieren los órdenes autorregresivo y de medias móviles (picos en los
     rezagos 1, 2 y en los múltiplos de 7).
  3. Grilla de modelos (p, q en 0-2; P, Q en 0-1) con las variables de calendario como exógenas; se comparan AIC y
     BIC. Criterio: el menor BIC entre los que dejan residuos sin autocorrelación (Ljung-Box, rezagos 7 y 14, p > 0,05).

Entrada: data/procesado/serie_sube_diaria_reconstruida.csv
Salidas: resultados/tablas/tabla_sarimax_diferenciacion.csv, tabla_sarimax_grilla.csv
         resultados/figuras/fig19_acf_pacf_sarimax.png
"""

import itertools
import os
import sys
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.statespace.sarimax import SARIMAX

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pronosticos_p2 as P   # noqa: E402

warnings.filterwarnings('ignore')
plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERIE = os.path.join(BASE_DIR, "data", "procesado", "serie_sube_diaria_reconstruida.csv")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")
FIG_DIR = os.path.join(BASE_DIR, "resultados", "figuras")
INICIO, FIN_IDENT = '2022-01-01', '2023-06-30'
COL = sys.argv[1] if len(sys.argv) > 1 else 'total_amba'    # serie a identificar: total_amba, colectivo_amba, tren_amba o subte_amba
SUF = '' if COL == 'total_amba' else '_' + COL


def decision(x):
    pa, pk = adfuller(x.dropna(), autolag='AIC')[1], kpss(x.dropna(), regression='c', nlags='auto')[1]
    dec = 'estacionaria' if (pa < 0.05 and pk >= 0.05) else ('no estacionaria' if (pa >= 0.05 and pk < 0.05) else 'indefinida')
    return round(pa, 4), round(pk, 4), dec


def figura_acf(s):
    """ACF y PACF de la serie con diferencia estacional de 7 días; las líneas marcan los múltiplos de 7."""
    x = s.diff(7).dropna()
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.5))
    plot_acf(x, lags=42, ax=axs[0], title='ACF de la serie con diferencia estacional (7)')
    plot_pacf(x, lags=42, ax=axs[1], title='PACF de la serie con diferencia estacional (7)', method='ywm')
    for ax, y in zip(axs, ['autocorrelación', 'autocorrelación parcial']):
        ax.set_xlabel('rezago (días)'); ax.set_ylabel(y)
        for k in (7, 14, 21, 28, 35, 42):
            ax.axvline(k, color='grey', lw=0.6, ls=':')
    plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, f'fig19_acf_pacf_sarimax{SUF}.png'), dpi=200); plt.close()


def main():
    s = pd.read_csv(SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')[COL].loc[INICIO:FIN_IDENT] / 1e6
    filas = []
    for nombre, x in [('nivel', s), ('dif. estacional (7)', s.diff(7)), ('dif. estacional (7) + dif. (1)', s.diff(7).diff())]:
        pa, pk, dec = decision(x)
        filas.append({'serie': nombre, 'p_ADF': pa, 'p_KPSS': pk, 'decision': dec})
    t_dif = pd.DataFrame(filas); t_dif.to_csv(os.path.join(TABLA_DIR, f'tabla_sarimax_diferenciacion{SUF}.csv'), index=False)
    print(t_dif.to_string(index=False))

    figura_acf(s)

    cal = P.calendario(s.index)[['feriado', 'nochebuena_fin_anio'] + [c for c in P.calendario(s.index[:1]).columns if c.startswith(('sen_', 'cos_'))]]
    filas = []
    for p, q, PP, Q in itertools.product([0, 1, 2], [0, 1, 2], [0, 1], [0, 1]):
        try:
            r = SARIMAX(s, exog=cal, order=(p, 0, q), seasonal_order=(PP, 1, Q, 7), enforce_stationarity=False,
                        enforce_invertibility=False).fit(disp=False, maxiter=200)
            lb = acorr_ljungbox(r.resid.iloc[8:], lags=[7, 14], return_df=True)['lb_pvalue']
            filas.append({'orden': f'({p},0,{q})x({PP},1,{Q},7)', 'AIC': round(r.aic, 1), 'BIC': round(r.bic, 1),
                          'LjungBox_p7': round(lb.iloc[0], 3), 'LjungBox_p14': round(lb.iloc[1], 3)})
        except Exception as e:
            filas.append({'orden': f'({p},0,{q})x({PP},1,{Q},7)', 'AIC': np.nan, 'BIC': np.nan, 'LjungBox_p7': np.nan, 'LjungBox_p14': np.nan})
    g = pd.DataFrame(filas).sort_values('BIC'); g.to_csv(os.path.join(TABLA_DIR, f'tabla_sarimax_grilla{SUF}.csv'), index=False)
    print('\nGrilla (ordenada por BIC):'); print(g.head(12).to_string(index=False))
    ok = g[(g.LjungBox_p7 > 0.05) & (g.LjungBox_p14 > 0.05)]
    print('\nMejor por BIC con residuos sin autocorrelación:'); print(ok.head(3).to_string(index=False))
    print('\nMejor por AIC:'); print(g.sort_values('AIC').head(3).to_string(index=False))


if __name__ == '__main__':
    main()
