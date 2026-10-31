"""
Modelos de pronóstico sin fuga de información.

Cada función recibe la serie completa `df` (índice diario) y una fecha de corte
`fin_train`. Solo se usan observaciones de `total_amba` hasta `fin_train`; del
futuro únicamente se usa el calendario (feriados, fines de semana), que se conoce
de antemano. Devuelven un `pd.Series` indexado por las fechas pronosticadas.

Esto permite repetir la evaluación en varios cortes (rolling origin).
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from prophet import Prophet
from sklearn.ensemble import HistGradientBoostingRegressor

EXOG_COLS = ['es_dia_habil', 'es_fin_de_semana', 'es_feriado']
LAGS = [1, 2, 7, 14, 21, 28]


def _dividir(df, fin_train, horizonte):
    fin_train = pd.Timestamp(fin_train)
    train = df.loc[:fin_train]
    futuro = df.loc[fin_train + pd.Timedelta(days=1):].iloc[:horizonte]
    if len(futuro) < horizonte:
        raise ValueError("No hay suficientes fechas después del corte para el horizonte pedido")
    return train, futuro


def seasonal_naive(df, fin_train, horizonte, s=7):
    """Repite la última semana observada del entrenamiento (no usa nada del test)."""
    train, futuro = _dividir(df, fin_train, horizonte)
    ultimo_ciclo = (train['total_amba'] / 1e6).iloc[-s:].values
    pred = [ultimo_ciclo[i % s] for i in range(horizonte)]
    return pd.Series(pred, index=futuro.index)


def sarimax(df, fin_train, horizonte, order=(1, 1, 1), seasonal_order=(1, 1, 1, 7)):
    train, futuro = _dividir(df, fin_train, horizonte)
    mod = SARIMAX(train['total_amba'] / 1e6, exog=train[EXOG_COLS], order=order,
                  seasonal_order=seasonal_order, enforce_stationarity=False,
                  enforce_invertibility=False)
    res = mod.fit(disp=False)
    pred = res.forecast(steps=horizonte, exog=futuro[EXOG_COLS])
    return pd.Series(np.asarray(pred), index=futuro.index), res


def prophet(df, fin_train, horizonte):
    train, futuro = _dividir(df, fin_train, horizonte)
    d_train = pd.DataFrame({'ds': train.index, 'y': (train['total_amba'] / 1e6).values,
                            'es_dia_habil': train['es_dia_habil'].values,
                            'es_feriado': train['es_feriado'].values})
    m = Prophet(weekly_seasonality=True, yearly_seasonality=True, daily_seasonality=False,
                changepoint_prior_scale=0.05)
    m.add_country_holidays(country_name='AR')
    m.add_regressor('es_dia_habil')
    m.add_regressor('es_feriado')
    m.fit(d_train)
    d_fut = pd.DataFrame({'ds': futuro.index, 'es_dia_habil': futuro['es_dia_habil'].values,
                          'es_feriado': futuro['es_feriado'].values})
    return pd.Series(m.predict(d_fut)['yhat'].values, index=futuro.index)


def _features(hist, fecha, fila):
    """Features de un día usando solo `hist` (dict fecha -> valor en millones)."""
    f = {f'lag_{l}': hist[fecha - pd.Timedelta(days=l)] for l in LAGS}
    ult7 = [hist[fecha - pd.Timedelta(days=k)] for k in range(1, 8)]
    f['rolling_mean_7'] = float(np.mean(ult7))
    f['rolling_std_7'] = float(np.std(ult7, ddof=1))
    for c in EXOG_COLS:
        f[c] = fila[c]
    f['dia_semana'] = fecha.dayofweek
    f['mes'] = fecha.month
    return f


def gradient_boosting_recursivo(df, fin_train, horizonte, random_state=42):
    """Gradient boosting con rezagos y pronóstico recursivo.

    Entrena con rezagos reales y, para pronosticar, alimenta cada paso con las
    predicciones previas: el rezago 1 de un día a 60 pasos del corte es una predicción,
    no una observación.
    """
    train, futuro = _dividir(df, fin_train, horizonte)
    y = train['total_amba'] / 1e6
    hist = dict(y.items())
    X, objetivo = [], []
    for fecha in train.index[max(LAGS):]:
        X.append(_features(hist, fecha, train.loc[fecha]))
        objetivo.append(y.loc[fecha])
    X = pd.DataFrame(X)
    cols = list(X.columns)
    modelo = HistGradientBoostingRegressor(max_iter=200, random_state=random_state).fit(X, objetivo)

    pred = []
    for fecha in futuro.index:
        x = pd.DataFrame([_features(hist, fecha, futuro.loc[fecha])])[cols]
        p = float(modelo.predict(x)[0])
        hist[fecha] = p
        pred.append(p)
    return pd.Series(pred, index=futuro.index)
