# Registro de cambios respecto del repo original

Este documento lista qué se modificó sobre el trabajo inicial (commit `fadc6b6`, "Initial commit") y **por qué**. Se actualiza a medida que avanza el trabajo. Está pensado para que cualquiera que conozca la versión original pueda ver rápido qué cambió y revisar las razones.

Cada cambio indica: qué se hizo, el motivo, la evidencia (números reproducibles con los scripts del repo) y el efecto sobre los resultados.

Rama de trabajo: `trabajo/herramientas-materia`.

---

## 0. Cambios de enfoque

| Qué | Por qué |
|---|---|
| Las Hipótesis 1 y 2 se reemplazan por las **Preguntas 1 y 2** de la presentación | Las hipótesis emitían "veredictos" (por ejemplo, que el teletrabajo causó una pérdida permanente de demanda) que los datos no permiten sostener. Las preguntas ordenan mejor el trabajo: P-1 = demanda ante hitos (COVID, saltos tarifarios, feriados); P-2 = qué métodos predicen mejor y por qué. |
| Se quita el sub-objetivo de medir la **recuperación post-COVID contra el nivel pre-pandemia** | Del período previo a la pandemia solo hay enero y febrero de 2020 (59 días), que además son temporada baja. No alcanza para distinguir "recuperación" de estacionalidad anual. El COVID pasa a tratarse como **shock descriptivo** (colapso y reapertura) y queda **fuera del entrenamiento** de los modelos, que ya usaban datos desde 2022. Se declara como limitación. |

Estado: aún no se reescribió el README ni el notebook en lo referido a hipótesis y veredictos. Se hará al final.

---

## 1. Verificación de que el pipeline se reproduce

**Qué se hizo:** se ejecutó `scripts/analisis_series_tiempo_sube.py` en un entorno nuevo (Python 3.11, `requirements.txt`) y se comparó contra las tablas publicadas.

**Resultado:** coincide. La única diferencia es Prophet, con MAPE 10,11% frente a 10,12% (ruido numérico). Los resultados originales eran reproducibles.

---

## 2. Calidad de datos (`scripts/calidad_datos.py`, archivo nuevo)

### 2.1 Días faltantes e imputación

**Qué se encontró:** el README decía "100% de cobertura sin valores faltantes", pero el CSV tiene 2.391 filas para 2.453 días calendario. Faltan **62 días, que son dos meses completos: agosto de 2022 y enero de 2024**. El script original los rellenaba con `interpolate(method='linear')`, es decir, con una recta entre los bordes.

**Por qué importa:** la serie tiene un ciclo semanal muy marcado. Una recta de 31 días elimina ese ciclo y el modelo de esos meses pasa a ser una línea plana, que luego entra en STL, en los tests de estacionariedad y en el entrenamiento.

**Evidencia:** se ocultaron 89 bloques de 31 días de datos reales y se midió cuánto se equivocaba cada método sobre los días ocultos (`resultados/tablas/tabla_simulacion_interpolacion.csv`, figura `fig7_interpolacion_huecos.png`):

| Método | Error mediano (MAPE) | Ciclo semanal que conserva |
|---|---|---|
| Lineal (el original) | 51% | ~1% |
| Spline cúbico | 76% (hasta 323% en el peor decil) | 15% |
| Lineal por día de la semana | 17% | 95% |

El spline llega a valores negativos con huecos largos.

**Qué se cambió:** se agregó una versión imputada por **día de la semana** (cada día de la semana se interpola por separado) en `data/procesado/serie_sube_diaria_imputada.csv`, con una columna `imputado` que marca los 62 días no observados. El archivo crudo no se modifica.

**Limitación:** un error mediano del 17% sigue siendo alto. La imputación sirve para no romper el muestreo uniforme que exigen algunas técnicas, pero esos días **no son datos reales** y se excluyen de métricas y tests cuando corresponde.

**Efecto sobre resultados:** pendiente de medir (análisis de sensibilidad con y sin los días imputados).

### 2.2 Qué mide `total_amba`

**Qué se encontró:** según el portal, la unidad es "usuarios (tarjetas diferentes) utilizadas por día", no viajes ni pasajeros. El total nunca supera la suma de los modos y equivale a entre 83% y 89% de ella (`tabla_total_vs_suma_modos.csv`), lo que sugiere que deduplica tarjetas que usan más de un modo. El portal no documenta esto último; es una inferencia.

**Qué se cambió:** el README ahora habla de "tarjetas distintas por día" y no de "pasajeros". Hay que mantener ese criterio en la presentación.

### 2.3 Días atípicos

**Qué se encontró:** valores como subte = 1 o tren = 90 no son errores de registro. Se detectaron los días en que un modo cae por debajo de la mitad de la mediana del mismo día de la semana (±4 semanas): hay 386 registros, de los cuales **332 son feriados**. Las 26 fechas restantes (`tabla_dias_atipicos.csv`) muestran patrones claros: domingos con subte y tren en casi cero (parecen domingos de elecciones), caídas simultáneas de subte y tren con colectivo normal o bajo (parecen paros) y 24 y 31 de diciembre.

**Qué se cambió:** nada en los datos. No se descartan: son información para la Pregunta 1 y se incorporarán como eventos (dummies). Las causas son hipótesis que se verificarán con fuentes antes de usarlas.

---

## 3. Correcciones menores del repo (P10)

| Archivo | Cambio | Motivo |
|---|---|---|
| `notebooks/TP_Final_Series_de_Tiempo.ipynb` | La ruta de lectura pasó de `../data/series_tiempo/...` a `../data/...` | La carpeta `data/series_tiempo/` no existe en el repo; el notebook no corría. |
| `notebooks/TP_Final_Series_de_Tiempo.ipynb` | Se escaparon `\text{Var}` y `\text{Cov}` en una celda de Markdown | La barra simple se interpretaba como tabulación y rompía las fórmulas. |
| notebook y `analisis_series_tiempo_sube.py` | El título "Residuos Estandarizados SARIMAX" pasó a "Residuos SARIMAX (millones de usuarios)" | Se graficaba `sarimax_res.resid`, que no está estandarizado. |
| `README.md` | Se corrigió la cobertura de datos, la unidad de medida y el árbol de archivos | Ver 2.1 y 2.2. |
| `.gitignore` | Se agregaron archivos temporales de Office y formatos intermedios | El original era genérico. |

---

## 4. Hallazgos todavía sin corregir en el código (a resolver a continuación)

Estos dos puntos afectan la comparación de modelos de la Pregunta 2. Se verificaron con un experimento aparte, y se corregirán en el pipeline.

| Qué | Por qué es un problema | Evidencia |
|---|---|---|
| **Gradient Boosting** usa `lag_1`, `lag_2` y `rolling_mean_7` calculados sobre toda la serie y los toma del tramo de test con valores reales | Equivale a predecir cada día conociendo el anterior, no a pronosticar 90 días. Los otros modelos sí pronostican 90 días. | MAPE 8,65–8,82% con el esquema original; **11,03%** con pronóstico recursivo a 90 días. |
| **Seasonal Naïve** usa `full_y.loc[fecha - 7 días]` | Pasada la primera semana del test, toma valores reales del propio test en lugar de un pronóstico a 90 días. | MAPE 16,05% con el esquema original; **19,68%** repitiendo la última semana observada del entrenamiento. |

Efecto probable: con ambas líneas base corregidas, Prophet (10,11%) pasa a ser el mejor, por encima de Gradient Boosting (11,03%). Es una sola ventana de test y falta evaluar con varios orígenes y con un test de significancia.

---

## 5. Pendientes que ya identificamos (no se tocaron todavía)

- Evaluar con **rolling origin** (varios cortes) y comparar modelos con un test de significancia, en lugar de un único corte de 90 días.
- Revisar el SARIMAX: orden fijo sin justificación, regresoras redundantes (`es_dia_habil`, `es_fin_de_semana`, `es_feriado` son colineales) y sin estacionalidad anual. Los residuos no son ruido blanco (Ljung-Box con p < 0,05 en los tres rezagos).
- La ventana de test (junio–septiembre de 2026) incluye una caída fuerte a fines de julio que ningún modelo anticipa (probablemente vacaciones de invierno).
- Aplicar las herramientas vistas en clase que el trabajo todavía no usa: FFT, filtros en el dominio de la frecuencia, descomposición con medias móviles, correlación cruzada, causalidad.
- Construir la tabla de hitos (saltos tarifarios, paros, elecciones) con fuentes verificables.
