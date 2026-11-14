"""
Modelos de pronóstico para P-2 (¿qué métodos pronostican mejor la demanda diaria del AMBA, y por qué?).

Reglas que cumplen todos los modelos:
  - Solo usan observaciones hasta el corte (`fin_train`). Del futuro solo usan el calendario, que se conoce de
    antemano: día de la semana, feriados nacionales, Nochebuena y fin de año, y la estacionalidad anual.
  - No usan paros, elecciones ni tarifas del futuro: no se conocen con antelación suficiente. Eso se evalúa aparte
    (errores en días atípicos).

Cada modelo recibe `serie` (pd.Series diaria, en millones de usuarios), `fin_train` y `horizonte`, y devuelve un
pd.Series con las fechas pronosticadas.

Modelos: Naive estacional (7 días), Naive estacional anual (364 días), SARIMAX, Prophet, Gradient Boosting recursivo,
Chronos-2 (Time Series Foundation Model, zero-shot con y sin covariables de calendario) y PatchTST (Specialized
Transformer con parches temporales de 7 días y normalización RevIN).
"""

import numpy as np
import pandas as pd
import holidays
import torch
import torch.nn as nn
from statsmodels.tsa.statespace.sarimax import SARIMAX
from prophet import Prophet
from sklearn.ensemble import HistGradientBoostingRegressor

_CHRONOS2_PIPE = None

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


def _get_chronos2_pipe():
    global _CHRONOS2_PIPE
    if _CHRONOS2_PIPE is None:
        from chronos import Chronos2Pipeline
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device == "cuda" else torch.float32
        _CHRONOS2_PIPE = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=device, dtype=dtype)
    return _CHRONOS2_PIPE


def _calendario_extendido(indice):
    c = calendario(indice).copy()
    for dw in range(6):
        c[f'dow_{dw}'] = (c.index.dayofweek == dw).astype(float)
    return c


def chronos2(serie, fin_train, horizonte, usar_covariables=True):
    """Chronos-2 (Amazon, Foundation Model pre-entrenado sobre series de tiempo).

    Con `usar_covariables=True` recibe las mismas covariables futuras conocidas de calendario que los demás modelos
    (feriados nacionales, Nochebuena/fin de año, día de la semana y armónicos anuales). Con `usar_covariables=False`
    opera en modo zero-shot univariado puro (solo el pasado de la serie).
    """
    train, idx = _dividir(serie, fin_train, horizonte)
    s_tr = train.interpolate(method='linear').bfill().ffill()
    pipe = _get_chronos2_pipe()
    if usar_covariables:
        cal_tr = _calendario_extendido(train.index)
        cal_fu = _calendario_extendido(idx)
        df_tr = cal_tr.assign(item_id='s', timestamp=cal_tr.index, target=s_tr.values).reset_index(drop=True)
        df_fu = cal_fu.assign(item_id='s', timestamp=cal_fu.index).reset_index(drop=True)
        out = pipe.predict_df(df_tr, future_df=df_fu, prediction_length=horizonte, quantile_levels=[0.5])
    else:
        df_tr = pd.DataFrame({'item_id': 's', 'timestamp': train.index, 'target': s_tr.values})
        out = pipe.predict_df(df_tr, prediction_length=horizonte, quantile_levels=[0.5])
    return pd.Series(out['predictions'].values, index=idx)


class _PatchTSTNet(nn.Module):
    """Arquitectura PatchTST (Nie et al., ICLR 2023) con normalización por instancia (RevIN) y parches semanales."""
    def __init__(self, n_patches=8, patch_len=7, n_cov=14, d_model=32, nhead=4, num_layers=2):
        super().__init__()
        self.patch_len = patch_len
        self.patch_emb = nn.Linear(patch_len, d_model)
        self.cov_emb = nn.Linear(patch_len * n_cov, d_model)
        self.pos_emb = nn.Parameter(torch.zeros(1, n_patches, d_model))
        enc_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=d_model * 2,
            dropout=0.1, batch_first=True, activation='gelu', norm_first=True
        )
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=num_layers, enable_nested_tensor=False)
        self.week_head = nn.Linear(n_patches * d_model, patch_len)
        self.cov_head = nn.Sequential(
            nn.Linear(n_cov + 1, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

    def forward(self, y_patches, c_patches, c_fut):
        mu = y_patches.mean(dim=(1, 2), keepdim=True)
        sd = y_patches.std(dim=(1, 2), keepdim=True) + 1e-5
        y_norm = (y_patches - mu) / sd
        z = self.patch_emb(y_norm) + self.cov_emb(c_patches) + self.pos_emb
        z = self.encoder(z).reshape(y_patches.size(0), -1)
        week_profile = self.week_head(z)
        idx_h = [h % self.patch_len for h in range(c_fut.size(1))]
        base_h = week_profile[:, idx_h]
        cov_in = torch.cat([c_fut, base_h.unsqueeze(-1)], dim=-1)
        out_norm = base_h + self.cov_head(cov_in).squeeze(-1)
        return out_norm * sd.squeeze(-1) + mu.squeeze(-1)


def patchtst(serie, fin_train, horizonte, n_patches=8, patch_len=7, epochs=150, lr=4e-3, seed=42):
    """PatchTST entrenado sobre los datos hasta `fin_train` con parches no solapados de 7 días y calendario."""
    torch.manual_seed(seed); torch.cuda.manual_seed_all(seed); np.random.seed(seed)
    train, idx = _dividir(serie, fin_train, horizonte)
    s_tr = train.interpolate(method='linear').bfill().ffill().values.astype(np.float32)
    cal_tr = _calendario_extendido(train.index).values.astype(np.float32)
    cal_fu = _calendario_extendido(idx).values.astype(np.float32)
    ctx = n_patches * patch_len
    n_cov = cal_tr.shape[1]
    H_tr = min(horizonte, 28)

    Yp, Cp, Cf, Yt = [], [], [], []
    for t in range(ctx, len(s_tr) - H_tr + 1):
        Yp.append(s_tr[t - ctx:t].reshape(n_patches, patch_len))
        Cp.append(cal_tr[t - ctx:t].reshape(n_patches, patch_len * n_cov))
        Cf.append(cal_tr[t:t + H_tr])
        Yt.append(s_tr[t:t + H_tr])

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    Yp = torch.tensor(np.array(Yp), dtype=torch.float32, device=device)
    Cp = torch.tensor(np.array(Cp), dtype=torch.float32, device=device)
    Cf = torch.tensor(np.array(Cf), dtype=torch.float32, device=device)
    Yt = torch.tensor(np.array(Yt), dtype=torch.float32, device=device)

    model = _PatchTSTNet(n_patches=n_patches, patch_len=patch_len, n_cov=n_cov).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
    loss_fn = nn.L1Loss()
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        pred = model(Yp, Cp, Cf)
        loss = loss_fn(pred, Yt)
        loss.backward()
        opt.step()

    model.eval()
    with torch.no_grad():
        yp = torch.tensor(s_tr[-ctx:].reshape(1, n_patches, patch_len), dtype=torch.float32, device=device)
        cp = torch.tensor(cal_tr[-ctx:].reshape(1, n_patches, patch_len * n_cov), dtype=torch.float32, device=device)
        cf = torch.tensor(cal_fu[None, :, :], dtype=torch.float32, device=device)
        out = model(yp, cp, cf).cpu().numpy()[0]
    return pd.Series(out, index=idx)
