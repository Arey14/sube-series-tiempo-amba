# Revisión del Pull Request #1 (`trabajo/herramientas-materia`)

- **Estado:** ✅ **MERGED** en `main` (`2026-11-14`)
- **PR:** [#1 — Reencuadre del trabajo en dos preguntas (P-1 y P-2), corrección de fuga de datos y notebook reescrito](https://github.com/Arey14/sube-series-tiempo-amba/pull/1)
- **Autores del PR:** Germán Samartino (`@GermanSamartino`) y Claude (`@claude`)
- **Commit de cierre del PR:** `f1b051b`
- **Commit de integración y ajustes post-revisión en `main`:** `b33cac8`

---

## 1. Qué se auditó y se aprobó del PR #1

Se revisaron los 34 commits y 156 archivos del PR y se validaron las decisiones principales del nuevo enfoque:

1. **Reencuadre conceptual (Hipótesis 1 y 2 $\rightarrow$ Preguntas P-1 y P-2):**
   - Se acepta reemplazar los veredictos cerrados de H1 y H2 por las dos preguntas de investigación (**P-1:** respuesta de la demanda ante hitos y análisis causal; **P-2:** evaluación predictiva y explicación de por qué gana cada método).
   - Se comparte la decisión de dejar el período **COVID (2020–2021)** como análisis descriptivo y fuera del entrenamiento de los modelos, dado que los 59 días previos de enero–febrero de 2020 corresponden al receso de verano y no permiten separar recuperación estructural de estacionalidad anual.

2. **Calidad de datos y reconstrucción de los 62 días faltantes:**
   - Se validó la reconstrucción de **agosto de 2022** y **enero de 2024** a partir de los datasets crudos de transacciones (`scripts/usos_transacciones.py`), preservando el ciclo semanal y reduciendo el error en meses de vacaciones de 12%–21% (interpolación lineal) a 1,6%–3,2%.

3. **Corrección de fuga de información (*data leakage*) y diseño de P-2:**
   - Se verificó la corrección en **Seasonal Naïve** (repite la última semana observada antes del corte en lugar de leer $t-7$ del propio conjunto de prueba) y en **Gradient Boosting** (pronóstico recursivo alimentado con sus propias predicciones en lugar de rezagos reales del futuro), junto con el test automatizado en `scripts/verificar_sin_fuga_p2.py`.
   - Se validó el esquema de evaluación **walk-forward de 42 cortes sucesivos de 28 días** (1.161 días efectivos sin paros ni elecciones), los contrastes de **Diebold-Mariano (HAC)**, los intervalos de predicción conformes (*split conformal*), las ablaciones, la sensibilidad a los huecos/horizontes ($h = 7, 28, 90$), el modelo híbrido por tipo de día (`scripts/modelo_hibrido_p2.py`) y el entrenamiento con y sin días de paro/elección (`scripts/sensibilidad_hitos_p2.py`).

4. **Diseño causal en P-1:**
   - Se verificaron las estimaciones de elasticidad-precio en niveles, diferencias interanuales (52 semanas) y estudio de eventos con contrafactual del año anterior y bandas placebo (`scripts/modelo_precio_demanda.py`), la deflactación por IPC e incorporación de salario real RIPTE, el control sintético con donantes del interior centrado en logaritmos (`scripts/control_sintetico.py`), el análisis de sustitución y causalidad de Granger con corrección de Holm (`scripts/efectos_cruzados_granger.py`) y el panel por línea de subte cruzado con ingreso comunal de la EAH (`scripts/panel_subte_lineas.py`).

---

## 2. Qué agregamos al integrar en `main` (commit `b33cac8`)

Durante la auditoría detectamos tres puntos donde el trabajo ya tenía material generado o una limitación abierta que convenía dejar resuelta directamente en el Notebook y en el `README.md`:

### 2.1 Incorporación completa de `herramientas_clase.py` en la Sección 4 del Notebook y en el `README.md`
En la Fase 2 del PR habían creado `scripts/herramientas_clase.py` con las figuras `fig8` a `fig11` y sus tablas, pero al reescribir `notebooks/TP_Final_Series_de_Tiempo.ipynb` habían quedado fuera del Notebook (`fig8` y `fig11` estaban solo al final del `README.md`, y `fig9` y `fig10` no aparecían ni en el Notebook ni en el `README.md`).

Se integraron en la **Sección 4 (`Exploración de la serie`)** del Notebook (y se completaron en la galería del `README.md`):
- **Análisis espectral (FFT) y teorema de Parseval:** tabla `tabla_fft_picos_total.csv` y figura `fig8_fft_espectro_semanal.png` (frecuencia fundamental semanal $1/7$ y armónicos $2/7, 3/7$, ciclo anual de ~351 días y semestral de ~176 días sobre el recorte exacto de 251 semanas).
- **Descomposición con medias móviles (`MA7`, `MA28`) frente a STL y retraso de fase:** figura `fig9_descomposicion_ma_vs_stl.png` (anulación exacta del ciclo semanal con ventanas múltiplo de 7 y comparación entre la MA28 centrada sin desfasaje y la MA28 causal con el retraso teórico de $(28-1)/2 \approx 14$ días).
- **Filtros en el dominio de la frecuencia (elimina-banda *notch* y pasa-bajos ideal) frente a medias móviles:** figura `fig10_filtros_df_vs_ma.png` (valores negativos espurios del filtro *notch* en feriados/paros, rizado por fenómeno de Gibbs del pasa-bajos ideal y efecto de borde por periodicidad circular).
- **Correlación cruzada (CCF) tren–colectivo y ACF:** tabla `tabla_ccf_tren_colectivo.csv` y figura `fig11_ccf_tren_colectivo_y_acf.png` (pico contemporáneo en rezago 0 sin adelantos entre modos y explicación del artefacto negativo en rezagos $\pm 1$ y $\pm 7$ inducido por la doble diferenciación $(1-B)(1-B^7)$).

### 2.2 Explicación de la brecha SUBE vs. CEPA en el Subte (2025–2026) y chequeo de robustez pre-multipago
En `docs/interpretacion_resultados.md` (bloque 2) y en las limitaciones del Notebook se documentaba que desde 2025 el Subte en SUBE mide entre **18% y 30% menos viajes** que CEPA/Metrovías, dejándolo como una diferencia sin causa identificada.

- **Causa identificada y documentada:** en diciembre de 2024 se habilitó en el Subte el **sistema multipago** (tarjetas de débito/crédito *contactless*, celulares con NFC y pagos QR con fuertes reintegros promocionales bancarios), cuyos viajes no se registran en el dataset de validadoras SUBE.
- **Chequeo cuantitativo pre-multipago agregado al Notebook (Secciones 3, 5.2 y 7) y al `README.md`:** dado que la migración de usuarios hacia pago *contactless*/QR en 2025–2026 coincidió con tarifas reales altas y podía amplificar artificialmente la elasticidad estimada en SUBE, corrimos `modelo_precio_demanda.py` restringiendo la muestra hasta **noviembre de 2024** (`2022-03-07` a `2024-11-24`, 90 semanas interanuales con 100% de viajes en SUBE):
  - **Sin control salarial (hasta nov-2024):** elasticidad real interanual del subte $= \mathbf{-0,175}$ ($\text{SE}_{\text{HAC}} = 0,021$, IC 95%: $[-0,216;\, -0,134]$, $R^2 = 0,838$).
  - **Con control por salario real RIPTE (hasta nov-2024):** elasticidad real interanual del subte $= \mathbf{-0,178}$ ($\text{SE}_{\text{HAC}} = 0,021$, IC 95%: $[-0,219;\, -0,137]$, $R^2 = 0,840$).
  - Esto demuestra que **la sensibilidad al precio del Subte ya existía antes del cambio en los medios de pago**, si bien en la muestra completa 2022–2026 la estimación puntual sin control salarial ($-0,224$) está parcialmente amplificada por la sustitución de medio de pago.
- También se explicitó en la Sección 3 del Notebook el criterio de modelar `subte_sin_D` en toda la serie agregada de `modelo_precio_demanda.py` (para evitar que el cierre por obras de la Línea D del 8-ene al 6-mar de 2024 contamine el salto de ene–feb 2024) y de conservar la Línea D en el panel por línea de la Sección 5.5 excluyendo únicamente las semanas del cierre.

### 2.3 Limpieza de formato inicial y re-ejecución del Notebook
- Se quitó el cartel provisorio de estado de la rama (`Estado (2-nov-2026, rama trabajo/herramientas-materia)`) del encabezado de `README.md`, dejando la referencia limpia a `docs/registro_de_cambios.md` y `docs/interpretacion_resultados.md`.
- Se actualizó el árbol de archivos del `README.md` (`fig1` a `fig28`, bloques 1 a 20) aclarando que los scripts y figuras de la Fase 1 (`analisis_series_tiempo_sube.py`, `modelos_pronostico.py`, `verificar_sin_fuga.py`, `fig1`–`fig7`) quedan preservados por trazabilidad.

---

## 3. Novedades incorporadas post-PR: Cobertura 100% del Avance (19-Oct) y Modelos Estado del Arte (SOTA)

Para asegurar que **todos los puntos comprometidos en la presentación de Avance del 19 de Octubre de 2026** estén cubiertos en el Notebook y en el `README.md`, y para extender la evaluación predictiva de P-2 al **Estado del Arte (SOTA) actual en series de tiempo**, incorporamos las siguientes novedades:

### 3.1 Comparación explícita de Interpolación Lineal vs. Spline Cúbico vs. Día de Semana vs. Reconstrucción (Sección 3)
- En el Avance del 19 de Octubre figuraba explícitamente *"Interpolación lineal o Splines — Reconstrucción de la ST para integridad de muestreo"*.
- El script `scripts/calidad_datos.py` ya generaba `resultados/tablas/tabla_simulacion_interpolacion.csv` y `resultados/figuras/fig7_interpolacion_huecos.png` (evaluación sobre 89 bloques reales de 31 días completos), pero esa comparación no estaba incluida en el Notebook ni en el `README.md`.
- **Novedad en Sección 3 del Notebook y `README.md`:** se integraron `tabla_simulacion_interpolacion.csv` y `fig7_interpolacion_huecos.png` junto con `fig12_reconstruccion_huecos.png`, mostrando cuantitativamente por qué el **Spline cúbico diverge en huecos de 31 días** (`MAPE = 76,3%`, `MAE = 3,34 M/día`), la **Interpolación lineal directa** aplana el ciclo semanal (`MAPE = 51,3%`, `MAE = 2,17 M/día`), la **Interpolación lineal por día de semana** preserva la forma semanal (`MAPE = 17,4%`, `MAE = 0,88 M/día`) y la **Reconstrucción desde transacciones crudas** alcanza el estándar de oro en meses de vacaciones (`MAPE = 1,6%–3,2%`).

### 3.2 Incorporación de dos familias Estado del Arte (SOTA) en P-2 (`chronos2` y `patchtst`)
Extendimos la familia de modelos evaluados en P-2 de 5 a **7 modelos principales** (+ ablaciones e híbridos) sumando un representante de cada una de las dos corrientes SOTA modernas en *Time Series Forecasting*:

1. **`chronos2` — Time Series Foundation Model (`amazon/chronos-2`, 120M parámetros):**
   - Modelo fundacional pre-entrenado sobre millones de series temporales multi-dominio que realiza inferencia **en contexto (*zero-shot*)**, sin ajustar un solo peso sobre los datos de SUBE.
   - Se evalúa en dos variantes dentro de `scripts/pronosticos_p2.py`:
     - **`chronos2` (`usar_covariables=True`):** recibe como `future_df` las mismas variables futuras conocidas de calendario (`es_feriado`, `es_puente`, `es_receso_escolar`, `vispera_feriado`, `dia_despues_feriado`).
     - **`chronos2_zeroshot` (`usar_covariables=False`):** ablación univariada pura que solo observa los valores pasados de la serie.
2. **`patchtst` — Specialized Transformer por Parches con RevIN (`PatchTST`, Nie et al., ICLR 2023 + Kim et al., ICLR 2022):**
   - Arquitectura Transformer especializada para series de tiempo que divide la ventana de contexto de $L = 56$ días (8 semanas) en $N = 8$ **parches semanales no solapados** de $P = 7$ días.
   - Incorpora **Reversible Instance Normalization (RevIN)**: normaliza cada ventana de entrada por su media y desvío local antes de proyectar los parches y des-normaliza la salida al final, dotando al modelo de **invarianza ante quiebres estructurales de nivel** (como los saltos tarifarios de 2024–2025).
   - Se entrena en cada corte estrictamente con ventanas contenidas hasta `fin_train` y combina la representación de auto-atención multi-cabezal con las covariables futuras de calendario.

### 3.3 Verificación anti-fuga y regeneración completa del pipeline P-2
- **Auditoría de no-fuga (`scripts/verificar_sin_fuga_p2.py`):** se actualizó para auditar los 7 modelos (`naive_7`, `naive_364`, `sarimax`, `prophet`, `gradient_boosting`, `chronos2`, `patchtst`) en los 3 cortes de control perturbando el futuro con $+10\,\sigma$. Los 7 modelos pasan con **diferencia máxima `0.00e+00`** (`OK: ningún modelo usa el futuro`).
- **Archivos de pronóstico y scripts actualizados:**
  - `scripts/pronosticos_p2.py`, `scripts/evaluacion_pronosticos.py`, `scripts/analisis_pronosticos_p2.py`, `scripts/analisis_pronosticos_por_modo.py`, `scripts/analisis_horizontes_p2.py`, `scripts/sensibilidad_huecos_p2.py`, `scripts/sensibilidad_hitos_p2.py` y `scripts/pronosticos_antes_del_salto_p2.py`.
  - Se recalcularon los 12 archivos `data/procesado/pronosticos_p2_*.csv`, todas las tablas `resultados/tablas/tabla_p2_*.csv` y las figuras `fig20` a `fig28`.
  - Se actualizaron `requirements.txt` (`torch>=2.0.0`, `chronos-forecasting>=2.3.0`), `README.md` y `notebooks/TP_Final_Series_de_Tiempo.ipynb` (Secciones 3, 6, 7 y 8), re-ejecutando las 88 celdas de punta a punta sin errores.

### 3.4 Resumen de resultados de los nuevos modelos SOTA en los 42 cortes walk-forward

| Serie / Experimento | Resultado principal de `patchtst` y `chronos2` |
| :--- | :--- |
| **Total AMBA (`h = 28 d`, 1.161 días sin atípicos)** | **1.° `patchtst`** (`MAE = 0,180 M`, `RMSE = 0,267 M`, `MAPE = 7,17%`, `MASE = 0,547`) y **2.° `gradient_boosting`** (`MAE = 0,187 M`, `MAPE = 7,43%`, `MASE = 0,568`) **empatan estadísticamente en la cima** (Diebold-Mariano $p = 0,3922$). **3.° `chronos2`** (`MAE = 0,199 M`, `MASE = 0,605`) supera sin entrenamiento local a `prophet` (`0,769`) y `sarimax` (`0,819`). |
| **Desglose por tipo de día (`Total AMBA`)** | **`chronos2` logra el menor error de todos los modelos en días hábiles ordinarios** (`MAE = 0,177 M`, `MAPE = 5,3%`), seguido por `patchtst` (`0,178 M`, `5,4%`) y `gradient_boosting` (`0,190 M`, `5,7%`). En **feriados**, `gradient_boosting` sigue primero (`0,342 M`), seguido por `patchtst` (`0,379 M`). |
| **Ablación de covariables en `chronos2`** | Sin calendario (`chronos2_zeroshot`), el modelo fundacional obtiene `MAE = 0,268 M` (`MASE = 0,817`, empatando a `sarimax` sin conocer los feriados argentinos). Al inyectarle las covariables de calendario (`chronos2`), **su MAE cae un 26%** (a `0,199 M`). |
| **Por modo: Colectivo** | Empate técnico en el 1.er puesto entre **`patchtst`** (`MASE = 0,558`) y **`gradient_boosting`** (`MASE = 0,588`, $p = 0,219$), seguidos por **`chronos2`** (`MASE = 0,619`). |
| **Por modo: Tren** | **`patchtst` gana en solitario** (`MASE = 0,478`, `MAPE = 8,6%`, $p < 0,0001$ frente a todos los demás), superando incluso al híbrido `SARIMAX + GB` (`0,536`), con **`chronos2`** en 2.° lugar (`MASE = 0,576`). |
| **Por modo: Subte** | **`patchtst` (`MASE = 0,566`) y `chronos2` (`MASE = 0,571`) empatan en el 1.er puesto** ($p = 0,983$), superando por amplio margen a `gradient_boosting` (`0,713`), `sarimax` (`0,749`) y al propio híbrido (`0,612`). **Por qué:** la normalización local por ventana (**RevIN** en PatchTST y el re-escalado por contexto en Chronos-2) adapta instantáneamente la escala tras los saltos tarifarios y la migración a multipago de 2024–2025, mientras que los árboles de Gradient Boosting quedan anclados a los niveles históricos de sus retardos. |
| **Sensibilidad al horizonte ($h = 7, 28, 90$ días)** | En horizonte corto ($h = 7\text{ d}$) gana `gradient_boosting` (`MASE = 0,504`); en mediano ($h = 28\text{ d}$) lidera `patchtst` (`0,547`) empatado con `gradient_boosting` (`0,568`); y en largo plazo ($h = 90\text{ d}$) lideran `gradient_boosting` (`0,549`), `patchtst` (`0,577`) y `chronos2` (`0,623`). |

