"""
Efecto cruzado entre modos y causalidad de Granger entre tarifa y demanda (pregunta P-1).

Modos: colectivo nacional, tren y subte (sin línea D). El colectivo provincial queda afuera porque su tarifa se
conoce solo desde febrero de 2024.

1. Efecto cruzado en diferencias interanuales (52 semanas): la variación de la demanda de un modo contra la variación
   de la tarifa real propia y la de los otros dos. Se informa el factor de inflación de la varianza (VIF): las
   tarifas se mueven juntas y valores altos indican que los coeficientes cruzados no se pueden separar.
2. Efecto cruzado en eventos: ante cada salto de un modo, cambio neto (menos lo ocurrido un año antes) de la demanda de
   los otros modos. Solo es una lectura de sustitución cuando la tarifa nominal del modo observado no cambió en esa
   ventana ("limpio").
3. Granger: las series se llevan a estacionariedad (primera diferencia del log de la demanda, descontados feriados,
   paros, elecciones y mes; primera diferencia del log de la tarifa real) y se verifica con la tabla ADF + KPSS de
   la clase. El rezago se elige por AIC (máximo 8 semanas). Se prueba precio -> demanda (propio y cruzado) y, como
   control, demanda -> precio. Corrección de Holm por las 9 pruebas de cada sentido.
   Granger mide si el pasado de una serie ayuda a predecir otra; no es causalidad por sí solo: las tarifas se
   anuncian con anticipación, las series comparten shocks comunes (inflación) y los saltos son pocos.

Entradas: las de modelo_precio_demanda.py
Salidas:  resultados/tablas/tabla_efecto_cruzado_interanual.csv, tabla_efecto_cruzado_eventos.csv,
          tabla_estacionariedad_granger.csv, tabla_granger_precio_demanda.csv
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.api import VAR
from statsmodels.tsa.stattools import adfuller, kpss, grangercausalitytests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modelo_precio_demanda as m   # noqa: E402

warnings.filterwarnings('ignore')
MODOS3 = ['colectivo_nacional', 'tren', 'subte']
MAX_REZAGO = 8


def interanual_cruzado(y, pr, ctrl):
    filas = []
    dp = pd.DataFrame({k: pr[k] - pr[k].shift(m.SEMANAS_ANIO) for k in MODOS3})
    ctl = pd.DataFrame({'dferiados': ctrl['feriados_habiles'] - ctrl['feriados_habiles'].shift(m.SEMANAS_ANIO),
                        'dparo': ctrl['paro'] - ctrl['paro'].shift(m.SEMANAS_ANIO),
                        'deleccion': ctrl['eleccion'] - ctrl['eleccion'].shift(m.SEMANAS_ANIO)})
    for i in MODOS3:
        dy = (y[i] - y[i].shift(m.SEMANAS_ANIO)).rename('dy')
        d = pd.concat([dy, dp.add_prefix('p_'), ctl], axis=1).dropna()
        X = sm.add_constant(d.drop(columns='dy'))
        res = sm.OLS(d['dy'], X).fit().get_robustcov_results(cov_type='HAC', maxlags=8)
        vif = {c: variance_inflation_factor(X.values, j) for j, c in enumerate(X.columns)}
        for k in MODOS3:
            j = list(X.columns).index('p_' + k)
            filas.append({'demanda_de': i, 'tarifa_de': k, 'tipo': 'propia' if i == k else 'cruzada', 'coeficiente': round(res.params[j], 3),
                          'error_std_HAC': round(res.bse[j], 3), 'ic95_inf': round(res.params[j] - 1.96 * res.bse[j], 3),
                          'ic95_sup': round(res.params[j] + 1.96 * res.bse[j], 3), 'VIF': round(vif['p_' + k], 1), 'semanas': len(d)})
    return pd.DataFrame(filas)


def eventos_cruzados(yh, p, pr):
    saltos = [(s, a, b) for s, a, b in m.eventos_salto() if s in MODOS3]
    filas = []
    for s, a, b in saltos:
        for o in MODOS3:
            if o == s:
                continue
            e = m.estudio_evento(yh, pr, set(), o, a, b)
            en = m.estudio_evento(yh, p, set(), o, a, b)
            filas.append({'salto_en': s, 'desde': a.date(), 'hasta': b.date(), 'demanda_de': o,
                          'dlog_demanda_neto': e['dlog_demanda_neto'], 'cambio_demanda_pct': e['cambio_demanda_pct'],
                          'dlog_tarifa_propia_nominal': en['dlog_tarifa'], 'limpio': abs(en['dlog_tarifa']) < 0.03})
    return pd.DataFrame(filas).dropna(subset=['dlog_demanda_neto'])


def series_estacionarias(y, pr, ctrl):
    """Primera diferencia del log de la demanda sin feriados/paros/elecciones/mes, y primera diferencia del log de la tarifa real."""
    meses = pd.get_dummies(ctrl['mes'], prefix='m', drop_first=True).astype(float)
    X0 = pd.DataFrame({'dfer': ctrl['feriados_habiles'].diff(), 'dparo': ctrl['paro'].diff(), 'deleccion': ctrl['eleccion'].diff()})
    dem, pre = {}, {}
    for k in MODOS3:
        d = pd.concat([y[k].diff().rename('dy'), X0, meses], axis=1).dropna()
        dem[k] = sm.OLS(d['dy'], sm.add_constant(d.drop(columns='dy'))).fit().resid
        pre[k] = pr[k].diff()
    return pd.DataFrame(dem).dropna(), pd.DataFrame(pre).dropna()


def decision_adf_kpss(x):
    p_adf = adfuller(x, autolag='AIC')[1]
    p_kpss = kpss(x, regression='c', nlags='auto')[1]
    if p_adf < 0.05 and p_kpss >= 0.05:
        dec = 'estacionaria'
    elif p_adf >= 0.05 and p_kpss < 0.05:
        dec = 'no estacionaria'
    else:
        dec = 'indefinida'
    return round(p_adf, 4), round(p_kpss, 4), dec


def granger(causa, efecto):
    """p-valor (prueba F) de que el pasado de `causa` ayuda a predecir `efecto`, con el rezago elegido por AIC."""
    d = pd.concat([efecto.rename('efecto'), causa.rename('causa')], axis=1).dropna()
    lag = max(1, VAR(d).select_order(MAX_REZAGO).aic)
    r = grangercausalitytests(d[['efecto', 'causa']], maxlag=lag)
    return lag, r[lag][0]['ssr_ftest'][1], len(d)


def holm(pvals):
    orden = np.argsort(pvals); n = len(pvals); aj = np.empty(n); mx = 0.0
    for r, i in enumerate(orden):
        mx = max(mx, (n - r) * pvals[i]); aj[i] = min(1.0, mx)
    return aj


def main():
    usos, tar, evt = m.cargar()
    y, p, ctrl, yh, pr = m.semanal(usos, tar, evt)

    t_ia = interanual_cruzado(y, pr, ctrl)
    t_ia.to_csv(os.path.join(m.TABLA_DIR, 'tabla_efecto_cruzado_interanual.csv'), index=False)
    print('1. Efecto cruzado, diferencias interanuales (tarifa real)'); print(t_ia.to_string(index=False))

    t_ev = eventos_cruzados(yh, p, pr)
    t_ev.to_csv(os.path.join(m.TABLA_DIR, 'tabla_efecto_cruzado_eventos.csv'), index=False)
    print('\n2. Efecto cruzado en eventos (limpio = la tarifa nominal del modo observado no cambió)'); print(t_ev.to_string(index=False))

    dem, pre = series_estacionarias(y, pr, ctrl)
    filas = []
    for nombre, df in [('demanda (dif. log, ajustada)', dem), ('tarifa real (dif. log)', pre)]:
        for k in MODOS3:
            a, kp, dec = decision_adf_kpss(df[k])
            filas.append({'serie': nombre, 'modo': k, 'p_ADF': a, 'p_KPSS': kp, 'decision': dec})
    t_est = pd.DataFrame(filas); t_est.to_csv(os.path.join(m.TABLA_DIR, 'tabla_estacionariedad_granger.csv'), index=False)
    print('\n3a. Estacionariedad (ADF + KPSS)'); print(t_est.to_string(index=False))

    filas = []
    for sentido in ['tarifa -> demanda', 'demanda -> tarifa']:
        bloque = []
        for i in MODOS3:
            for k in MODOS3:
                if sentido == 'tarifa -> demanda':
                    lag, pv, n = granger(pre[k], dem[i])
                else:
                    lag, pv, n = granger(dem[i], pre[k])
                bloque.append({'sentido': sentido, 'demanda_de': i, 'tarifa_de': k, 'tipo': 'propia' if i == k else 'cruzada',
                               'rezago_AIC': lag, 'p_valor': pv, 'semanas': n})
        aj = holm(np.array([b['p_valor'] for b in bloque]))
        for b, a in zip(bloque, aj):
            b['p_valor'] = round(b['p_valor'], 4); b['p_Holm'] = round(a, 4)
        filas += bloque
    t_g = pd.DataFrame(filas); t_g.to_csv(os.path.join(m.TABLA_DIR, 'tabla_granger_precio_demanda.csv'), index=False)
    print('\n3b. Granger'); print(t_g.to_string(index=False))


if __name__ == '__main__':
    main()
