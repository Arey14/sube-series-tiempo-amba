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

### 2.3 Limpieza de formato final y re-ejecución completa del Notebook
- Se quitó el cartel provisorio de estado de la rama (`Estado (2-nov-2026, rama trabajo/herramientas-materia)`) del encabezado de `README.md`, dejando la referencia limpia a `docs/registro_de_cambios.md` y `docs/interpretacion_resultados.md`.
- Se actualizó el árbol de archivos del `README.md` (`fig1` a `fig28`, bloques 1 a 20) aclarando que los scripts y figuras de la Fase 1 (`analisis_series_tiempo_sube.py`, `modelos_pronostico.py`, `verificar_sin_fuga.py`, `fig1`–`fig7`) quedan preservados por trazabilidad.
- Se re-ejecutó `notebooks/TP_Final_Series_de_Tiempo.ipynb` de punta a punta con `jupyter nbconvert --to notebook --execute --inplace` (88 celdas ejecutadas sin errores).

