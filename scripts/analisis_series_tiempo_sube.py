"""
Pipeline de Análisis Estadístico y Modelado de Series de Tiempo
Dataset: SUBE - Usuarios Diarios en el AMBA (2020-2026)
Objetivo: Verificación formal de Hipótesis de Investigación para TP Final
"""

import os
import holidays
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Statsmodels
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.stats.diagnostic import acorr_ljungbox

# Prophet
from prophet import Prophet

# Scikit-learn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, mean_absolute_percentage_error

# Configuración visual
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['figure.dpi'] = 300

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(BASE_DIR, "data", "total-usuarios-por-dia-AMBA.csv")
FIG_DIR = os.path.join(BASE_DIR, "resultados", "figuras")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")

os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(TABLA_DIR, exist_ok=True)


def load_and_preprocess_data(csv_path=DATA_PATH):
    """Carga y estructura el dataset diario agregando variables de calendario."""
    print(">>> 1. Cargando y preprocesando datos...")
    df = pd.read_csv(csv_path)
    df['fecha'] = pd.to_datetime(df['indice_tiempo'])
    df = df.sort_values('fecha').set_index('fecha').asfreq('D')

    # Feriados de Argentina
    ar_holidays = holidays.Argentina(years=range(2020, 2027))
    df['es_feriado'] = df.index.map(lambda d: 1 if d in ar_holidays else 0)
    df['dia_semana'] = df.index.dayofweek # 0=Lunes, 6=Domingo
    df['es_fin_de_semana'] = df['dia_semana'].apply(lambda d: 1 if d in [5, 6] else 0)
    df['es_dia_habil'] = ((df['es_fin_de_semana'] == 0) & (df['es_feriado'] == 0)).astype(int)
    df['mes'] = df.index.month
    df['anio'] = df.index.year

    # Rellenar eventuales huecos por asfreq mediante interpolación lineal suave
    df[['total_amba', 'colectivo_amba', 'subte_amba', 'tren_amba']] = (
        df[['total_amba', 'colectivo_amba', 'subte_amba', 'tren_amba']].interpolate(method='linear')
    )

    print(f"Dataset estructurado: {df.shape[0]} días entre {df.index.min().date()} y {df.index.max().date()}")
    return df


def test_stationarity(series, name):
    """Ejecuta ADF y KPSS sobre una serie y retorna diccionario estructurado."""
    adf_res = adfuller(series.dropna(), autolag='AIC')
    adf_stat, adf_p = adf_res[0], adf_res[1]
    
    kpss_res = kpss(series.dropna(), regression='c', nlags='auto')
    kpss_stat, kpss_p = kpss_res[0], kpss_res[1]

    adf_conclusion = "Estacionaria (p < 0.05)" if adf_p < 0.05 else "No Estacionaria (p >= 0.05)"
    kpss_conclusion = "Estacionaria (p >= 0.05)" if kpss_p >= 0.05 else "No Estacionaria (p < 0.05)"

    return {
        'Serie': name,
        'ADF_Stat': round(adf_stat, 4),
        'ADF_pvalue': round(adf_p, 4),
        'ADF_Conclusion': adf_conclusion,
        'KPSS_Stat': round(kpss_stat, 4),
        'KPSS_pvalue': round(kpss_p, 4),
        'KPSS_Conclusion': kpss_conclusion
    }


def perform_statistical_tests(df):
    """Ejecuta los tests de estacionariedad para niveles, primera diferencia y diferencia estacional."""
    print(">>> 2. Ejecutando tests estadísticos de estacionariedad (ADF y KPSS)...")
    results = []
    
    for col in ['total_amba', 'colectivo_amba', 'subte_amba', 'tren_amba']:
        results.append(test_stationarity(df[col], f"{col} (Nivel)"))
        results.append(test_stationarity(df[col].diff().dropna(), f"{col} (Diff d=1)"))
        results.append(test_stationarity(df[col].diff(7).dropna(), f"{col} (Diff Estacional s=7)"))
        results.append(test_stationarity(df[col].diff().diff(7).dropna(), f"{col} (Diff d=1, s=7)"))

    df_tests = pd.DataFrame(results)
    df_tests.to_csv(os.path.join(TABLA_DIR, "tabla_tests_estacionariedad_adf_kpss.csv"), index=False)
    print("Tabla de tests de estacionariedad guardada.")
    return df_tests


def plot_eda_and_seasonality(df):
    """Genera figuras completas de AED, estacionalidad y descomposición."""
    print(">>> 3. Generando gráficos de análisis exploratorio y estacionalidad...")

    # 1. Serie histórica completa por modo
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    palette = {'total_amba': '#2c3e50', 'colectivo_amba': '#2980b9', 'subte_amba': '#e67e22', 'tren_amba': '#27ae60'}
    titles = {
        'total_amba': 'Total AMBA (Todos los modos)',
        'colectivo_amba': 'Colectivo AMBA (Red de buses urbanos)',
        'subte_amba': 'Subte AMBA (Red de subterráneos de CABA)',
        'tren_amba': 'Tren AMBA (7 líneas metropolitanas)'
    }

    for ax, col in zip(axes, ['total_amba', 'colectivo_amba', 'subte_amba', 'tren_amba']):
        ax.plot(df.index, df[col] / 1e6, color=palette[col], linewidth=0.9, label='Diario')
        ax.plot(df.index, df[col].rolling(30, center=True).mean() / 1e6, color='#c0392b', linewidth=1.5, label='Media Móvil 30d')
        ax.set_title(titles[col], fontweight='bold')
        ax.set_ylabel('Millones de Usuarios')
        ax.legend(loc='upper right', frameon=True)
        ax.axvspan(pd.Timestamp('2020-03-20'), pd.Timestamp('2020-11-08'), color='#e74c3c', alpha=0.15, label='ASPO')

    axes[-1].set_xlabel('Fecha')
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig1_series_historicas_modos.png"))
    plt.close()

    # 2. Boxplots de estacionalidad semanal y mensual
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    dias_nombres = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

    df_post21 = df[df.index >= '2022-01-01'].copy()
    df_post21['dia_nom'] = df_post21['dia_semana'].apply(lambda d: dias_nombres[d])
    df_post21['mes_nom'] = df_post21['mes'].apply(lambda m: meses_nombres[m-1])

    # Semanal
    df_melt_week = df_post21.melt(id_vars=['dia_nom', 'dia_semana'], value_vars=['colectivo_amba', 'subte_amba', 'tren_amba'],
                                  var_name='Modo', value_name='Usuarios')
    df_melt_week['Usuarios_M'] = df_melt_week['Usuarios'] / 1e6
    df_melt_week = df_melt_week.sort_values('dia_semana')

    sns.boxplot(data=df_melt_week, x='dia_nom', y='Usuarios_M', hue='Modo', palette=['#2980b9', '#e67e22', '#27ae60'], ax=axes[0, 0])
    axes[0, 0].set_title("Estacionalidad Semanal (2022-2026)", fontweight='bold')
    axes[0, 0].set_ylabel("Millones de Usuarios")
    axes[0, 0].set_xlabel("Día de la Semana")

    # Mensual
    df_melt_month = df_post21.melt(id_vars=['mes_nom', 'mes'], value_vars=['colectivo_amba', 'subte_amba', 'tren_amba'],
                                   var_name='Modo', value_name='Usuarios')
    df_melt_month['Usuarios_M'] = df_melt_month['Usuarios'] / 1e6
    df_melt_month = df_melt_month.sort_values('mes')

    sns.boxplot(data=df_melt_month, x='mes_nom', y='Usuarios_M', hue='Modo', palette=['#2980b9', '#e67e22', '#27ae60'], ax=axes[0, 1])
    axes[0, 1].set_title("Estacionalidad Anual / Mensual (2022-2026)", fontweight='bold')
    axes[0, 1].set_ylabel("Millones de Usuarios")
    axes[0, 1].set_xlabel("Mes")

    # ACF y PACF de total_amba diferenciada (d=1, D=1, s=7)
    diff_series = df_post21['total_amba'].diff(1).diff(7).dropna()
    plot_acf(diff_series, lags=40, ax=axes[1, 0], title="Autocorrelación Simple (ACF) - Serie $(\\nabla_1 \\nabla_7 y_t)$")
    plot_pacf(diff_series, lags=40, ax=axes[1, 1], title="Autocorrelación Parcial (PACF) - Serie $(\\nabla_1 \\nabla_7 y_t)$")

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig2_estacionalidad_y_correlacion.png"))
    plt.close()

    # 3. Descomposición STL (Seasonal and Trend decomposition using Loess)
    stl = STL(df_post21['total_amba'] / 1e6, period=7, robust=True)
    res_stl = stl.fit()

    fig, axes = plt.subplots(4, 1, figsize=(14, 9), sharex=True)
    axes[0].plot(df_post21.index, res_stl.observed, color='#2c3e50', lw=1)
    axes[0].set_title("Descomposición STL - Total AMBA (Período Semanal $s=7$)", fontweight='bold')
    axes[0].set_ylabel("Observado (M)")

    axes[1].plot(df_post21.index, res_stl.trend, color='#c0392b', lw=1.5)
    axes[1].set_ylabel("Tendencia (M)")

    axes[2].plot(df_post21.index, res_stl.seasonal, color='#2980b9', lw=0.8)
    axes[2].set_ylabel("Estacionalidad (M)")

    axes[3].plot(df_post21.index, res_stl.resid, color='#7f8c8d', lw=0.7)
    axes[3].set_ylabel("Residuos (M)")
    axes[3].set_xlabel("Fecha")

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig3_descomposicion_stl.png"))
    plt.close()


def evaluate_hypothesis_1_recovery(df):
    """Contrasta cuantitativamente la Hipótesis 1 (Asimetría en la recuperación por modo)."""
    print(">>> 4. Evaluando Hipótesis 1 (Asimetría en la recuperación post-pandemia)...")
    
    pre_covid = df[(df.index >= '2020-01-01') & (df.index < '2020-03-01')][['colectivo_amba', 'subte_amba', 'tren_amba']].mean()
    
    anual = df.groupby(df.index.year)[['colectivo_amba', 'subte_amba', 'tren_amba']].mean()
    recov_matrix = (anual.div(pre_covid, axis=1) * 100).round(2)
    recov_matrix.to_csv(os.path.join(TABLA_DIR, "tabla_recuperacion_porcentual_modos.csv"))

    # Gráfico de evolución del índice de recuperación (Base 100 = Pre-COVID)
    df_indices = df[['colectivo_amba', 'subte_amba', 'tren_amba']].copy()
    for col in ['colectivo_amba', 'subte_amba', 'tren_amba']:
        df_indices[col] = (df_indices[col].rolling(30, center=True).mean() / pre_covid[col]) * 100

    plt.figure(figsize=(13, 6))
    plt.plot(df_indices.index, df_indices['colectivo_amba'], label='Colectivo (Buses)', color='#2980b9', lw=2.2)
    plt.plot(df_indices.index, df_indices['tren_amba'], label='Tren (Ferrocarriles)', color='#27ae60', lw=2.2)
    plt.plot(df_indices.index, df_indices['subte_amba'], label='Subte (Subterráneos CABA)', color='#e67e22', lw=2.2)
    plt.axhline(100, color='black', linestyle='--', alpha=0.7, label='Nivel Base Pre-COVID (100%)')
    plt.axvspan(pd.Timestamp('2020-03-20'), pd.Timestamp('2020-11-08'), color='#e74c3c', alpha=0.15, label='Período ASPO')
    
    plt.title("Evolución del Índice de Recuperación por Modo de Transporte (Base 100 = Pre-COVID Ene/Feb 2020)", fontweight='bold')
    plt.ylabel("Nivel de Demanda Relativo (%)")
    plt.xlabel("Fecha")
    plt.legend(loc='upper left', frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig4_recuperacion_asimetrica_modos.png"))
    plt.close()

    print("Resultados Hipótesis 1 guardados.")
    return recov_matrix


def train_and_evaluate_forecasting_models(df):
    """Entrena y compara SARIMAX, Prophet y Gradient Boosting en ventana de prueba."""
    print(">>> 5. Entrenando y evaluando modelos predictivos (Hipótesis 2)...")

    df_model = df[df.index >= '2022-01-01'].copy()
    
    test_days = 90
    train_df = df_model.iloc[:-test_days].copy()
    test_df = df_model.iloc[-test_days:].copy()

    y_train = train_df['total_amba'] / 1e6
    y_test = test_df['total_amba'] / 1e6

    exog_cols = ['es_dia_habil', 'es_fin_de_semana', 'es_feriado']
    exog_train = train_df[exog_cols]
    exog_test = test_df[exog_cols]

    predictions = pd.DataFrame(index=test_df.index)
    predictions['Real'] = y_test

    # 1. Baseline: Seasonal Naïve (s=7)
    s_naive = []
    full_y = df_model['total_amba'] / 1e6
    for date in test_df.index:
        s_naive.append(full_y.loc[date - pd.Timedelta(days=7)])
    predictions['Seasonal_Naive'] = s_naive

    # 2. Modelo SARIMAX (1, 1, 1) x (1, 1, 1, 7) con exógenas
    print("  - Ajustando SARIMAX(1, 1, 1)x(1, 1, 1, 7) con variables exógenas...")
    sarimax_mod = SARIMAX(
        y_train,
        exog=exog_train,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, 7),
        enforce_stationarity=False,
        enforce_invertibility=False
    )
    sarimax_res = sarimax_mod.fit(disp=False)
    predictions['SARIMAX'] = sarimax_res.forecast(steps=test_days, exog=exog_test)

    # 3. Modelo Facebook Prophet
    print("  - Ajustando Facebook Prophet con feriados y estacionalidades...")
    prophet_train = pd.DataFrame({
        'ds': train_df.index,
        'y': y_train.values,
        'es_dia_habil': train_df['es_dia_habil'].values,
        'es_feriado': train_df['es_feriado'].values
    })
    
    m_prophet = Prophet(
        weekly_seasonality=True,
        yearly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05
    )
    m_prophet.add_country_holidays(country_name='AR')
    m_prophet.add_regressor('es_dia_habil')
    m_prophet.add_regressor('es_feriado')
    m_prophet.fit(prophet_train)

    future = pd.DataFrame({
        'ds': test_df.index,
        'es_dia_habil': test_df['es_dia_habil'].values,
        'es_feriado': test_df['es_feriado'].values
    })
    prophet_fcst = m_prophet.predict(future)
    predictions['Prophet'] = prophet_fcst['yhat'].values

    # 4. Modelo Machine Learning (HistGradientBoosting con retardos)
    print("  - Ajustando Gradient Boosting Regressor con lags...")
    df_feat = df_model.copy()
    for lag in [1, 2, 7, 14, 21, 28]:
        df_feat[f'lag_{lag}'] = df_feat['total_amba'].shift(lag) / 1e6
    df_feat['rolling_mean_7'] = (df_feat['total_amba'] / 1e6).shift(1).rolling(7).mean()
    df_feat['rolling_std_7'] = (df_feat['total_amba'] / 1e6).shift(1).rolling(7).std()
    
    feature_cols = [c for c in df_feat.columns if c.startswith('lag_') or c.startswith('rolling_')] + exog_cols + ['dia_semana', 'mes']
    df_feat = df_feat.dropna()

    X_tr = df_feat.loc[df_feat.index < test_df.index[0], feature_cols]
    y_tr = df_feat.loc[df_feat.index < test_df.index[0], 'total_amba'] / 1e6
    X_te = df_feat.loc[test_df.index, feature_cols]

    gbr = HistGradientBoostingRegressor(max_iter=200, random_state=42)
    gbr.fit(X_tr, y_tr)
    predictions['Gradient_Boosting'] = gbr.predict(X_te)

    # Cálculo de Métricas de Evaluación
    metrics_list = []
    for model_name in ['Seasonal_Naive', 'SARIMAX', 'Prophet', 'Gradient_Boosting']:
        rmse = np.sqrt(mean_squared_error(predictions['Real'], predictions[model_name]))
        mae = mean_absolute_error(predictions['Real'], predictions[model_name])
        mape = mean_absolute_percentage_error(predictions['Real'], predictions[model_name]) * 100
        metrics_list.append({
            'Modelo': model_name,
            'RMSE (M)': round(rmse, 4),
            'MAE (M)': round(mae, 4),
            'MAPE (%)': round(mape, 2)
        })

    df_metrics = pd.DataFrame(metrics_list).sort_values('MAPE (%)')
    df_metrics.to_csv(os.path.join(TABLA_DIR, "tabla_comparacion_modelos_metricas.csv"), index=False)
    print("\n=== TABLA DE EVALUACIÓN DE MODELOS ===")
    print(df_metrics.to_string(index=False))

    # Gráficos de Pronóstico
    plt.figure(figsize=(14, 6))
    plt.plot(test_df.index, predictions['Real'], 'k-', label='Demanda Real', lw=2.2)
    plt.plot(test_df.index, predictions['SARIMAX'], '--', label=f'SARIMAX (MAPE: {df_metrics[df_metrics["Modelo"]=="SARIMAX"]["MAPE (%)"].values[0]}%)', lw=1.6, color='#e74c3c')
    plt.plot(test_df.index, predictions['Prophet'], '-.', label=f'Prophet (MAPE: {df_metrics[df_metrics["Modelo"]=="Prophet"]["MAPE (%)"].values[0]}%)', lw=1.6, color='#2980b9')
    plt.plot(test_df.index, predictions['Gradient_Boosting'], ':', label=f'Gradient Boosting (MAPE: {df_metrics[df_metrics["Modelo"]=="Gradient_Boosting"]["MAPE (%)"].values[0]}%)', lw=1.6, color='#27ae60')
    
    plt.title(f"Comparativa de Pronósticos en Ventana de Test (Horizonte: {test_days} días)", fontweight='bold')
    plt.ylabel("Millones de Usuarios")
    plt.xlabel("Fecha")
    plt.legend(loc='upper right', frameon=True)
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig5_comparativa_pronosticos.png"))
    plt.close()

    # Diagnóstico de Residuos SARIMAX
    sarimax_resid = sarimax_res.resid
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    
    axes[0, 0].plot(sarimax_resid, color='#2c3e50', lw=0.8)
    axes[0, 0].set_title("Residuos SARIMAX (millones de usuarios)", fontweight='bold')
    axes[0, 0].axhline(0, color='red', linestyle='--')
    
    sns.histplot(sarimax_resid, kde=True, ax=axes[0, 1], color='#2980b9')
    axes[0, 1].set_title("Distribución de Residuos", fontweight='bold')
    
    sm.qqplot(sarimax_resid, line='s', ax=axes[1, 0])
    axes[1, 0].set_title("Gráfico Q-Q Normal", fontweight='bold')
    
    plot_acf(sarimax_resid, lags=30, ax=axes[1, 1], title="ACF de Residuos")
    
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig6_diagnostico_residuos_sarimax.png"))
    plt.close()

    # Test Ljung-Box sobre residuos
    lb_test = acorr_ljungbox(sarimax_resid.dropna(), lags=[7, 14, 21], return_df=True)
    lb_test.to_csv(os.path.join(TABLA_DIR, "tabla_diagnostico_ljung_box.csv"))
    print("\nResultados de Ljung-Box en residuos SARIMAX:")
    print(lb_test)

    return df_metrics


def main():
    print("=================================================================")
    print("INICIANDO PIPELINE DE SERIES DE TIEMPO SUBE (SUBE AMBA)")
    print("=================================================================")
    
    df = load_and_preprocess_data()
    test_df = perform_statistical_tests(df)
    plot_eda_and_seasonality(df)
    recov_matrix = evaluate_hypothesis_1_recovery(df)
    df_metrics = train_and_evaluate_forecasting_models(df)

    print("\n=================================================================")
    print("PIPELINE COMPLETADO CON ÉXITO")
    print(f"Figuras guardadas en: {FIG_DIR}/")
    print(f"Tablas guardadas en: {TABLA_DIR}/")
    print("=================================================================")


if __name__ == "__main__":
    main()
