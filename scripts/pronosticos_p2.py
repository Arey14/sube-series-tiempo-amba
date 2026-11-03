"""
Modelos de pronóstico para P-2 (¿qué métodos pronostican mejor la demanda diaria del AMBA, y por qué?).

Reglas que cumplen todos los modelos:
  - Solo usan observaciones hasta el corte (`fin_train`). Del futuro solo usan el calendario, que se conoce de
    antemano: día de la semana, feriados nacionales, Nochebuena y fin de año, y la estacionalidad anual.
  - No usan paros, elecciones ni tarifas del futuro: no se conocen con antelación suficiente. Eso se evalúa aparte
    (errores en días atípicos).

Cada modelo recibe `serie` (pd.Series diaria, en millones de usuarios), `fin_train` y `horizonte`, y devuelve un
pd.Series con las fechas pronosticadas.

Modelos: Naive estacional (7 días), Naive estacional anual (364 días), SARIMAX, Prophet y Gradient Boosting recursivo.
"""

import numpy as np
import pandas as pd
import holidays
from statsmodels.tsa.statespace.sarimax import SARIMAX
from prophet import Prophet
from sklearn.ensemble import HistGradientBoostingRegressor

K_ANUAL = 3
LAGS = [1, 2, 7, 14, 21, 28]
_FER = holidays.Argentina(years=range(2019, 2028))


def calendario(indice, k_anual=K_ANUAL):
    """Variables de calendario conocidas de antemano para cada fecha del índice."""
    idx = pd.DatetimeIndex(indice)
    c = pd.DataFrame(index=idx)
    c['feriado'] = [float(f in _FER) for f in idx]
    c['nochebuena_fin_anio'] = [float((f.month == 12 and f.day in (24, 31))) for f in idx]
    doy = idx.dayofyear.values
    for k in range(1, k_anual + 1):
        c[f'sen_{k}'] = np.sin(2 * np.pi * k * doy / 365.25)
        c[f'cos_{k}'] = np.cos(2 * np.pi * k * doy / 365.25)
    return c


def _dividir(serie, fin_train, horizonte):
    fin_train = pd.Timestamp(fin_train)
    train = serie.loc[:fin_train]
    futuro = serie.loc[fin_train + pd.Timedelta(days=1):].iloc[:horizonte]
    if len(futuro) < horizonte:
        raise ValueError("No hay suficientes fechas después del corte para el horizonte pedido")
    return train, futuro.index


def naive_semanal(serie, fin_train, horizonte, s=7):
    train, idx = _dividir(serie, fin_train, horizonte)
    ult = train.iloc[-s:].values
    return pd.Series([ult[i % s] for i in range(horizonte)], index=idx)


def naive_anual(serie, fin_train, horizonte):
    """Mismo día de la semana del año anterior (364 días antes)."""
    train, idx = _dividir(serie, fin_train, horizonte)
    return pd.Series([train.get(f - pd.Timedelta(days=364), np.nan) for f in idx], index=idx)


def sarimax(serie, fin_train, horizonte, order=(1, 0, 1), seasonal_order=(1, 1, 1, 7), k_anual=K_ANUAL, usar_anual=True,
            start_params=None, en_logs=False):
    train, idx = _dividir(serie, fin_train, horizonte)
    cols = ['feriado', 'nochebuena_fin_anio'] + ([c for c in calendario(idx[:1], k_anual).columns if c.startswith(('sen_', 'cos_'))] if usar_anual else [])
    X_tr = calendario(train.index, k_anual)[cols]; X_fu = calendario(idx, k_anual)[cols]
    y_tr = np.log(train) if en_logs else train
    mod = SARIMAX(y_tr, exog=X_tr, order=order, seasonal_order=seasonal_order, enforce_stationarity=False, enforce_invertibility=False)
    res = mod.fit(disp=False, start_params=start_params, maxiter=200)
    pred = np.asarray(res.forecast(steps=horizonte, exog=X_fu))
    return pd.Series(np.exp(pred) if en_logs else pred, index=idx), res


def prophet(serie, fin_train, horizonte):
    train, idx = _dividir(serie, fin_train, horizonte)
    cal_tr, cal_fu = calendario(train.index), calendario(idx)
    d = pd.DataFrame({'ds': train.index, 'y': train.values, 'nochebuena_fin_anio': cal_tr['nochebuena_fin_anio'].values}).dropna(subset=['y'])
    m = Prophet(weekly_seasonality=True, yearly_seasonality=True, daily_seasonality=False, changepoint_prior_scale=0.05)
    m.add_country_holidays(country_name='AR')
    m.add_regressor('nochebuena_fin_anio')
    m.fit(d)
    f = pd.DataFrame({'ds': idx, 'nochebuena_fin_anio': cal_fu['nochebuena_fin_anio'].values})
    return pd.Series(m.predict(f)['yhat'].values, index=idx)


def _features(hist, fecha, cal_fila):
    f = {f'lag_{l}': hist[fecha - pd.Timedelta(days=l)] for l in LAGS}
    ult7 = [hist[fecha - pd.Timedelta(days=k)] for k in range(1, 8)]
    f['media_7'] = float(np.mean(ult7)); f['desvio_7'] = float(np.std(ult7, ddof=1))
    for c, v in cal_fila.items():
        f[c] = v
    f['dia_semana'] = fecha.dayofweek; f['mes'] = fecha.month
    return f


def gradient_boosting(serie, fin_train, horizonte, random_state=42, con_rezagos=True):
    """Gradient boosting con rezagos, pronóstico recursivo (cada paso se alimenta con las predicciones previas).

    Con `con_rezagos=False` usa solo el calendario (día de la semana, mes, feriado, estacionalidad anual): es la
    variante para medir cuánto aportan los rezagos.
    """
    train, idx = _dividir(serie, fin_train, horizonte)
    cal_tr, cal_fu = calendario(train.index), calendario(idx)
    if not con_rezagos:
        def solo_cal(c):
            x = c.copy(); x['dia_semana'] = c.index.dayofweek; x['mes'] = c.index.month
            return x
        modelo = HistGradientBoostingRegressor(max_iter=200, random_state=random_state).fit(solo_cal(cal_tr), train.values)
        return pd.Series(modelo.predict(solo_cal(cal_fu)), index=idx)
    hist = dict(train.items())
    X = [_features(hist, f, cal_tr.loc[f]) for f in train.index[max(LAGS):]]
    X = pd.DataFrame(X); cols = list(X.columns)
    y = train.iloc[max(LAGS):].values; ok = ~np.isnan(y)       # con días faltantes en la serie se descartan como objetivo
    modelo = HistGradientBoostingRegressor(max_iter=200, random_state=random_state).fit(X[ok], y[ok])
    pred = []
    for f in idx:
        p = float(modelo.predict(pd.DataFrame([_features(hist, f, cal_fu.loc[f])])[cols])[0])
        hist[f] = p; pred.append(p)
    return pd.Series(pred, index=idx)
