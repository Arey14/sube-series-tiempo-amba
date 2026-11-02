# 🚆 Análisis de Series de Tiempo de la Demanda de Transporte Público en el AMBA (SUBE)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Statsmodels](https://img.shields.io/badge/Statsmodels-0.15+-orange.svg)](https://www.statsmodels.org/)
[![Prophet](https://img.shields.io/badge/Facebook-Prophet-blueviolet.svg)](https://facebook.github.io/prophet/)
[![Open Data](https://img.shields.io/badge/Datos%20Abiertos-SUBE%20Argentina-yellow.svg)](https://datos.transporte.gob.ar/)

> **Estado (2-nov-2026, rama `trabajo/herramientas-materia`).** Las hipótesis y veredictos de la versión inicial se reemplazaron por dos preguntas de trabajo (P-1 y P-2). Las métricas de la versión inicial tenían fuga de información y se rehicieron con una evaluación con origen móvil. Qué cambió y por qué: [`docs/registro_de_cambios.md`](docs/registro_de_cambios.md). Lectura de cada resultado, con sus límites: [`docs/interpretacion_resultados.md`](docs/interpretacion_resultados.md). El notebook todavía conserva el enfoque original.

Este repositorio contiene el análisis de la **demanda de transporte público del Área Metropolitana de Buenos Aires (AMBA)** con datos del **Sistema Único de Boleto Electrónico (SUBE)**, 2020–2026, para la materia Series Temporales de la Maestría en Ciencia de Datos.

---

## 📌 Tabla de Contenidos

- [Preguntas y respuestas](#-preguntas-y-respuestas)
- [Estructura del Repositorio](#-estructura-del-repositorio)
- [Dataset y Fuente de Datos](#-dataset-y-fuente-de-datos)
- [Metodología](#-metodología)
- [Guía de Reproducibilidad](#-guía-de-reproducibilidad)
- [Referencias Bibliográficas](#-referencias-bibliográficas)
- [Licencia](#-licencia)

---

## 🎯 Preguntas y respuestas

### P-1. ¿Cómo se comportó la demanda alrededor de los hitos, y por qué?

Hitos estudiados: pandemia (descriptivo), saltos tarifarios, feriados, paros y elecciones.

| Pregunta | Resultado | Confianza |
|---|---|---|
| ¿Reacciona la demanda al precio? | **Subte:** sí, elasticidad de −0,22 a −0,26 con tarifa real (deflactada por IPC), respaldada por Granger (p de Holm 0,019). **Colectivo nacional y tren:** no se distinguen de cero. | Subte: media. Colectivo y tren: baja |
| ¿Cuánto cayó con los saltos grandes? | Colectivo nacional ene–feb 2024: −13% (estudio de eventos) contra −3% sin significancia (control sintético). Subte may-2024 (tarifa ×4): −19%. Tren: inconsistente. | Baja a media |
| ¿Hay sustitución entre modos? | No se observa. | Media |
| ¿Las líneas de subte de mayor ingreso reaccionan menos? | Sin respaldo (poco poder: solo 6 líneas). | Baja |
| ¿Cómo se comporta la demanda en los hitos de calendario? | Feriados laborables: ~0,3 de un día normal. Paros propios del modo: 0,0 a 0,2. Elecciones con gratuidad: ~0. Pandemia: mínimo de 2% a 12% del verano de 2020; a fines de 2021, 97% (colectivo), 75% (tren) y 65% (subte). | Alta |

El precio importa para el subte y casi nada para el colectivo y el tren en los saltos observados, pero **no es un efecto causal limpio**: el ingreso queda sin controlar y el período es de inflación alta. Los hitos de calendario son los efectos más claros.

### P-2. ¿Qué métodos pronostican mejor la demanda diaria, y por qué?

Evaluación con **origen móvil**: 42 cortes (el primero el 30-jun-2023, uno cada 28 días), cada uno con 28 días de prueba que no se solapan (1.161 días sin paros ni elecciones). Los modelos solo usan el pasado y el calendario. Diferencias contrastadas con Diebold-Mariano.

| Modelo (total AMBA, 28 días) | MAE (millones) | MAPE | MASE |
| :--- | :---: | :---: | :---: |
| 🥇 **Gradient Boosting recursivo** | **0,187** | **7,4%** | **0,57** |
| 🥈 Prophet | 0,254 | 11,9% | 0,77 |
| 🥉 SARIMAX (2,0,1)x(0,1,1,7) | 0,270 | 11,8% | 0,82 |
| Naive 364 días | 0,395 | 17,4% | 1,20 |
| Naive 7 días | 0,472 | 19,5% | 1,43 |

MASE menor a 1 significa mejor que repetir la última semana. Lo que se encontró:

- **Por qué gana el Gradient Boosting:** los feriados explican el grueso de la diferencia con los Naive; la estacionalidad anual y el patrón semanal multiplicativo importan; y los rezagos aportan además del calendario.
- **No hay un método único:** en colectivo gana el Gradient Boosting, pero en tren y subte empata con el SARIMAX. Un **híbrido por tipo de día** (modelo aditivo en días hábiles, Gradient Boosting en el resto, con la regla elegida solo con cortes anteriores) mejora a ambos en tren (MASE 0,62 a 0,54) y subte (0,71 a 0,61), pero no en total ni colectivo. Es un hallazgo a confirmar en otro período.
- **Robusto** al tratamiento de los 62 días sin dato en la fuente (la reconstrucción desde transacciones mejora el error del Gradient Boosting: MASE 0,56 contra 0,63 con interpolación) y al horizonte (mismo ranking a 7, 28 y 90 días).
- **Límites:** configuración estándar sin ajuste fino de hiperparámetros, y los paros y elecciones no se pronostican.

---

## 📂 Estructura del Repositorio

```text
├── data/
│   ├── total-usuarios-por-dia-AMBA.csv    # Dataset oficial de usuarios (2020–2026)
│   ├── hitos/                             # Paros, elecciones y series de tarifas con fuentes
│   ├── externos/                          # IPC (INDEC), ingreso por comuna (EAH) y geografía del subte
│   ├── procesado/                         # Series reconstruidas, usos por línea y pronósticos de cada corte
│   └── raw_usos/                          # (no versionado) CSV de transacciones, los baja usos_transacciones.py
├── notebooks/
│   └── TP_Final_Series_de_Tiempo.ipynb    # Notebook original (pendiente de rehacer)
├── scripts/
│   ├── descargar_datos.py                 # Datos: actualizador desde el portal oficial
│   ├── calidad_datos.py                   # Datos: huecos, imputación, qué mide el total, días atípicos
│   ├── usos_transacciones.py              # Datos: transacciones y reconstrucción de los huecos
│   ├── usos_por_linea.py                  # Datos: transacciones por línea de subte
│   ├── tarifas_serie.py                   # P-1: serie de tarifas con fuentes
│   ├── tarifas_descriptivo.py             # P-1: descripción de los saltos tarifarios
│   ├── modelo_precio_demanda.py           # P-1: elasticidad (niveles, interanual, estudio de eventos)
│   ├── clasificacion_lineas_subte.py      # P-1: ingreso por línea de subte
│   ├── panel_subte_lineas.py              # P-1: hipótesis de ingreso (panel línea x semana)
│   ├── efectos_cruzados_granger.py        # P-1: efecto cruzado entre modos y Granger
│   ├── hitos_eventos.py, hitos_efectos.py # P-1: paros, elecciones, feriados y pandemia
│   ├── control_sintetico.py               # P-1: control sintético para el colectivo
│   ├── pronosticos_p2.py                  # P-2: los cinco modelos
│   ├── identificacion_sarimax.py          # P-2: orden del SARIMAX (ADF/KPSS, ACF/PACF, BIC)
│   ├── evaluacion_pronosticos.py          # P-2: origen móvil (args: ablaciones, col=<modo>, h=<días>)
│   ├── analisis_pronosticos_p2.py         # P-2: métricas, Diebold-Mariano, intervalos
│   ├── analisis_pronosticos_por_modo.py   # P-2: colectivo, tren y subte
│   ├── modelo_hibrido_p2.py               # P-2: híbrido por tipo de día
│   ├── sensibilidad_huecos_p2.py          # P-2: tratamiento de los días sin dato
│   ├── analisis_horizontes_p2.py          # P-2: horizontes de 7 y 90 días
│   ├── verificar_sin_fuga_p2.py           # P-2: prueba de que los modelos no usan el futuro
│   ├── herramientas_clase.py              # Herramientas vistas en clase (filtros, FFT, CCF)
│   └── analisis_series_tiempo_sube.py, modelos_pronostico.py, verificar_sin_fuga.py   # Versión inicial
├── resultados/
│   ├── figuras/                           # fig1 a fig24 (PNG)
│   └── tablas/                            # Tablas en CSV
├── docs/
│   ├── registro_de_cambios.md             # Qué se cambió respecto del repo original y por qué
│   └── interpretacion_resultados.md       # Lectura de cada resultado, con límites (bloques 1 a 15)
├── .gitignore
├── LICENSE
├── requirements.txt
└── README.md
```

---

## 📊 Dataset y Fuente de Datos

Los datos de usuarios provienen de los registros de validadoras de la red SUBE publicados por la **Secretaría de Transporte de la Nación** en [datos.transporte.gob.ar](https://datos.transporte.gob.ar/dataset/sube-cantidad-de-tarjetas-usuarios-por-dia-en-amba).

* **Período temporal**: 2020-01-01 a 2026-09-18 en el CSV original; la serie de trabajo llega a septiembre de 2026 (octubre es preliminar y queda fuera de la evaluación).
* **Calidad**: faltan **62 días**, dos meses completos (**agosto de 2022** y **enero de 2024**). Se reconstruyen a partir de las transacciones diarias y se marcan con la columna `imputado` (ver `scripts/usos_transacciones.py`).
* **Unidad de medida**: cantidad de **tarjetas diferentes** usadas por día, no viajes. El total nunca supera la suma de los modos, lo que sugiere que deduplica tarjetas que usan más de un modo (inferencia: el portal no lo documenta).
* **Variables**: `total_amba`, `colectivo_amba`, `subte_amba`, `tren_amba` (tarjetas distintas por día en cada caso).
* **Datos complementarios**: transacciones por día y línea (portal de transporte), tarifas oficiales (Boletín Oficial, resoluciones y fuentes indicadas en `data/hitos/`), IPC nacional (INDEC), ingreso por comuna (Encuesta Anual de Hogares de CABA) y geografía del subte (BA Data).

---

## 🛠️ Metodología

**P-1 (demanda y hitos).** Elasticidad con tarifa real: regresión en niveles (con y sin tendencia), diferencias interanuales de 52 semanas y estudio de eventos con doble diferencia estacional y bandas placebo. Panel línea × semana con efectos fijos por semana para la hipótesis de ingreso. Granger (con ADF y KPSS previos y corrección de Holm) y efectos cruzados entre modos. Cociente contra el mismo día de la semana de las semanas vecinas para los hitos de calendario. Control sintético con ciudades del interior para los saltos del colectivo.

**P-2 (pronóstico).** Origen móvil con ventana creciente; modelos que solo usan el pasado y el calendario; métricas MAE, RMSE, MAPE y MASE; Diebold-Mariano con errores HAC; intervalos de predicción por método conforme; variantes de cada modelo para explicar las diferencias (ablaciones); prueba de fuga (`scripts/verificar_sin_fuga_p2.py`: el futuro real se reemplaza por basura y los pronósticos no deben cambiar). El orden del SARIMAX se identifica con ADF y KPSS, ACF y PACF y una grilla por BIC con residuos sin autocorrelación (Ljung-Box).

**Herramientas de la materia aplicadas a la serie:** estacionariedad (ADF y KPSS), descomposición (media móvil y STL), filtros, espectro (FFT) y correlación cruzada entre modos; ver `scripts/herramientas_clase.py` y la sección 6 de `docs/registro_de_cambios.md`.

---

## 💻 Guía de Reproducibilidad

### 1. Clonar el repositorio
```bash
git clone https://github.com/Arey14/sube-series-tiempo-amba.git
cd sube-series-tiempo-amba
```

### 2. Crear y activar un entorno virtual
```bash
python3 -m venv venv
source venv/bin/activate   # En Linux / macOS
# venv\Scripts\activate    # En Windows
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Reproducir los resultados (en este orden)
```bash
# Datos
python scripts/usos_transacciones.py        # baja las transacciones (~60 MB por año) y reconstruye los huecos
python scripts/usos_por_linea.py

# P-1
python scripts/tarifas_serie.py
python scripts/modelo_precio_demanda.py
python scripts/clasificacion_lineas_subte.py
python scripts/panel_subte_lineas.py
python scripts/efectos_cruzados_granger.py
python scripts/hitos_efectos.py
python scripts/control_sintetico.py

# P-2 (la evaluación con origen móvil tarda; se puede interrumpir y retomar)
python scripts/identificacion_sarimax.py
python scripts/evaluacion_pronosticos.py                 # total AMBA, 28 días
python scripts/analisis_pronosticos_p2.py
python scripts/modelo_hibrido_p2.py
```
Variantes de la evaluación: `ablaciones`, `col=colectivo_amba|tren_amba|subte_amba` y `h=7|90`. Los datos externos (IPC, ingreso por comuna, geografía del subte) ya están en `data/externos/`.

### 5. Notebook original
```bash
jupyter notebook notebooks/TP_Final_Series_de_Tiempo.ipynb
```

---

## 📚 Referencias Bibliográficas

1. **Box, G. E., Jenkins, G. M., Reinsel, G. C., & Ljung, G. M. (2015).** *Time series analysis: forecasting and control*. John Wiley & Sons.
2. **Cleveland, R. B., Cleveland, W. S., McRae, J. E., & Terpenning, I. (1990).** *STL: A seasonal-trend decomposition procedure based on loess*. Journal of Official Statistics, 6(1), 3-73.
3. **Taylor, S. J., & Letham, B. (2018).** *Forecasting at scale*. The American Statistician, 72(1), 37-45.
4. **Hyndman, R. J., & Athanasopoulos, G. (2018).** *Forecasting: principles and practice*. OTexts.
5. **Dickey, D. A., & Fuller, W. A. (1979).** *Distribution of the estimators for autoregressive time series with a unit root*. Journal of the American Statistical Association, 74(366a), 427-431.
6. **Kwiatkowski, D., Phillips, P. C., Schmidt, P., & Shin, Y. (1992).** *Testing the null hypothesis of stationarity against the alternative of a unit root*. Journal of Econometrics, 54(1-3), 159-178.

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia **MIT**. Para más detalles, consulte el archivo [LICENSE](LICENSE).
