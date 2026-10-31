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

**Cautela sobre los meses de vacaciones:** al repetir la simulación sobre eneros y julios completos, el error de la imputación por día de la semana es de 12% a 25% y el sesgo va de −6% a +14% según el mes (enero de 2025: −3,8%; enero de 2026: −5,7%; julio de 2025: +6,8%; julio de 2026: +13,5%). Los dos meses faltantes son estacionalmente atípicos (enero tiene un valle anual de vacaciones), así que el enero de 2024 imputado debe leerse con cautela.

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

## 4. Corrección de la fuga de información en la comparación de modelos (Fase 1b)

**Qué se encontró:** dos de los cuatro modelos usaban valores reales del tramo de test, de modo que no pronosticaban realmente 90 días hacia adelante.

| Modelo | Problema | Cómo se corrigió |
|---|---|---|
| **Seasonal Naïve** | Usaba `full_y.loc[fecha - 7 días]` de la serie completa. Pasada la primera semana del test tomaba valores reales del propio test. | Repite la **última semana observada del entrenamiento**. |
| **Gradient Boosting** | Calculaba `lag_1`, `lag_2`, `rolling_mean_7` y `rolling_std_7` sobre toda la serie y los tomaba del test con valores reales. Equivalía a predecir cada día conociendo el anterior. | **Pronóstico recursivo**: entrena con rezagos reales y, al pronosticar, alimenta cada paso con las predicciones anteriores. |

SARIMAX y Prophet ya pronosticaban a 90 días y **no se modificaron**: se mantienen sus parámetros originales, para que cualquier diferencia en los resultados se deba solo a las dos correcciones.

**Qué se cambió en el código:**
- `scripts/modelos_pronostico.py` (nuevo): los cuatro modelos como funciones que reciben la serie completa y una fecha de corte, y solo pueden usar datos hasta ese corte (más el calendario, que se conoce de antemano). Sirve además para evaluar en varios cortes más adelante.
- `scripts/analisis_series_tiempo_sube.py`: la función de entrenamiento ahora llama a ese módulo. Las métricas y figuras se generan igual que antes.
- `scripts/verificar_sin_fuga.py` (nuevo): reemplaza los valores reales posteriores al corte por basura (x10); si un modelo no usa el futuro, sus pronósticos no pueden cambiar. Incluye como control la fórmula original del Naïve, que sí falla la prueba. Resultado: los cuatro modelos corregidos pasan; el control falla (diferencia máxima 34,75).

**Efecto sobre los resultados** (misma ventana de 90 días, 21-jun a 18-sep de 2026):

| Modelo | MAPE original | MAPE corregido | RMSE (M) | MAE (M) |
|---|---|---|---|---|
| Prophet | 10,12% | **10,11%** | 0,289 | 0,225 |
| Gradient Boosting | 8,82% | **11,03%** | 0,341 | 0,278 |
| SARIMAX | 12,16% | 12,16% | 0,386 | 0,271 |
| Seasonal Naïve | 16,05% | **19,68%** | 0,924 | 0,557 |

(La diferencia en Prophet, 10,12% a 10,11%, es ruido numérico por la versión de las librerías.)

Lo que cambia:
- Prophet pasa a ser el mejor, por encima de Gradient Boosting.
- El Naïve empeora (era más fácil de lo que parecía por la fuga), así que las reducciones de error respecto de él cambian: Prophet −49%, Gradient Boosting −44%, SARIMAX −38% (antes −37%, −45% y −24%).
- El orden de los modelos depende de la métrica: por MAE, SARIMAX (0,271) supera a Gradient Boosting (0,278); por RMSE y MAPE no.
- **Gradient Boosting recursivo pierde nivel** al alejarse del corte, porque cada paso hereda el error del anterior (se ve en la figura 5 desde fines de agosto). Es un punto a explicar en la discusión de la Pregunta 2.

**Qué sigue sin cambiar:** es una sola ventana de test y no hay test de significancia, así que estos números no alcanzan para afirmar que un modelo es mejor que otro (ver sección 5).

**Nota técnica:** Prophet no carga su backend desde Git Bash en Windows; funciona desde PowerShell o CMD.

---

## 5. Herramientas vistas en clase aplicadas a la serie (Fase 2, en curso)

Script nuevo: `scripts/herramientas_clase.py`. Figuras 8 a 11 y tablas `tabla_adf_kpss_decision_clase.csv`, `tabla_fft_picos_total.csv`, `tabla_ccf_tren_colectivo.csv`, `tabla_dias_candidatos_paro.csv`.

**Decisiones de diseño**
- **Tramo principal:** del 3-feb-2024 al 18-sep-2026 (959 días = 137 semanas exactas), sin ningún día imputado. Se recorta a semanas completas para que el ciclo semanal caiga exacto en un bin de la FFT.
- **Sensibilidad:** la serie imputada desde 2022 (1.722 días = 246 semanas).
- El COVID queda fuera de todo este análisis.

**Resultados**

| Herramienta | Qué se observa |
|---|---|
| **ADF + KPSS con la tabla de decisión de la clase** | En este tramo, total, colectivo y tren son estacionarios en nivel (tren cae en "indefinida" con el tramo corto); **subte no lo es**. La decisión no cambia con la serie imputada desde 2022. Esto **contradice la conclusión del repo original** (todas las series I(1)), que se había obtenido sobre 2020-2026 incluyendo el colapso del COVID. Hay que tener presente que el KPSS del total en nivel queda justo en el borde (p = 0,052). |
| **FFT sin DC** | Picos nítidos en 1/7, 2/7 y 3/7 ciclos/día (7; 3,5 y 2,3 días), con amplitudes de 0,92; 0,62 y 0,31 millones. Parseval verificado (energía en el tiempo = en frecuencia). La amplitud semanal es robusta: 0,920 M en el tramo y 0,940 M con la serie imputada. El ciclo anual no se puede resolver en el tramo de 2,6 años; con la serie desde 2022 aparece un pico de ~344 días. |
| **Descomposición con MA** | Serie−MA7 deja los feriados como valles: media de −1,18 M en feriados contra +0,07 M en el resto. Se usa **MA28 y no MA30/MA21**: una media móvil de largo múltiplo de 7 anula exactamente el ciclo semanal. Contra la tendencia de STL: correlación 0,94, RMSE 0,18 M. La tendencia STL queda por encima de la MA28 porque STL robusto descuenta los valles de feriados y la media móvil no. La tendencia muestra valles anuales claros en cada enero y en julio de 2026. |
| **Filtros en el dominio de la frecuencia** | El elimina-banda anula el ciclo semanal por construcción (amplitud 0). Una MA7 también lo anula (0,0012 M): la media móvil es en sí un notch en 1/7 y sus múltiplos. El pasa-bajos ideal **oscila alrededor de la MA28** (rizado, tipo Gibbs) y el elimina-banda deja la serie desestacionalizada con todos los feriados como valles profundos; algunos días llegan a valores ≤ 0, lo que no tiene sentido físico, resultado de restar el perfil semanal promedio a días que se comportan como domingo. No se detectó empeoramiento en los bordes de este tramo. |
| **Retraso de las medias móviles** | La MA28 causal (solo pasado) llega 14 días tarde respecto del pasa-bajos en frecuencia (≈ (28−1)/2, lo esperado). **La MA centrada no tiene retraso**; la afirmación de que la media móvil "retrasa la señal" solo vale para la versión causal. |
| **CCF tren–colectivo** | Con residuos sin calendario, correlación de 0,84 en lag 0 y de 0,33 y 0,31 en lags −1 y +1; con diferencias simple + estacional, 0,92 en lag 0. No hay evidencia de un efecto con retraso: ambos modos se mueven juntos el mismo día. |
| **Colectivo en días candidatos a paro** | En los días en que subte y tren caen a ~0 (30-oct-2024 y 10-abr-2025), el colectivo no sube: queda en 0,74 y 0,63 de su nivel habitual. Ese día y el 21-feb-2024 (solo tren) no muestran absorción por el colectivo. Son 5 fechas candidatas, cuyas causas están por verificar con fuentes. |
| **ACF** | Picos en los lags 7, 14, 21, 28, 35 y 42 (≈ 0,70 al inicio, decayendo lento). |

**Limitaciones que hay que tener presentes**
- **La CCF entre modos está dominada por causas compartidas** (calendario, clima, paros generales que afectan a todos), por lo que **no permite concluir una relación causal** entre el tren y el colectivo. En los residuos aparece además un piso de correlación ≈ 0,2 en todos los lags, que refleja variación lenta compartida.
- En la CCF de las series diferenciadas, los valores negativos en lags ±1 y ±7 son un **artefacto de las propias diferencias** (inducen correlación negativa en esos lags); solo el lag 0 es interpretable.
- Los resultados por modo y para los días de paro dependen de pocas observaciones.

## 6. Tabla de hitos con fuentes (Fase 3, en curso)

Archivos nuevos: `scripts/hitos_eventos.py`, `data/hitos/hitos_paros_elecciones.csv` y `data/hitos/hitos_tarifas.csv`. Cada hito tiene su fecha, descripción, modos afectados, **estado de verificación y URLs de las fuentes** (prensa y normativa). El script calcula además, desde los datos, cuánto cayó cada modo ese día respecto de su mediana del mismo día de la semana.

Estados: *confirmado (≥2 fuentes)*, *confirmado con discrepancias*, *una fuente / a verificar*, *sin fuente (inferido del dato)*. Las fechas inferidas de memoria no se usaron sin verificar.

### 6.1 Qué se encontró

| Hito | Resultado |
|---|---|
| **Paros generales de la CGT** | Cuatro en total contra el gobierno actual: 24-ene-2024, 9-may-2024, 10-abr-2025 y 19-feb-2026. Tres son observables en los datos; **el primero (24-ene-2024) cae dentro del hueco de enero de 2024 y no se puede ver**. |
| **Paros específicos** | Trenes 21-feb-2024 (La Fraternidad); colectivos 11-abr-2024 y 6-may-2025 y 7-jul-2023 (UTA); trenes y subte 30-oct-2024. Todos coinciden con los días atípicos que había detectado la Fase 1. |
| **Elecciones** | Con transporte gratuito (Resolución 435/2023 y antecedentes de 2021) en las PASO y generales de 2021 y 2023: el subte cae a ~0 y el tren a 0,02–0,13 de lo habitual. **En 2025 las tres elecciones no muestran ese colapso** (cocientes de 0,6 a 1,1). El balotaje del 19-nov-2023 es consistente con gratuidad pero no se encontró fuente. |
| **Saltos tarifarios** | Ver 6.2. |

### 6.2 Limitación importante para medir el efecto de las tarifas

El salto más grande de la serie, el boleto mínimo de colectivo y tren de $76,92 a $270 (**+251%**, 6-feb-2024, fecha probable), **cae justo donde empieza el tramo continuo de datos**: el pre-período disponible son 5 días y enero de 2024 está imputado. Lo mismo ocurre con el salto de enero de 2024 del colectivo (+45%): su período posterior es el hueco. **Ninguno de los dos se puede evaluar causalmente con estos datos.**

Los saltos con pre-período largo y fuentes confirmadas son los de trenes del **2-may-2024 (+53,85%, 91 días previos)** y del **16-sep-2024 (+40%, 228 días previos)**. El primero ocurre 7 días antes del paro general del 9-may-2024, así que sus efectos se superponen. En 2026 los aumentos de tren (18-may, 1-jul y 1-sep) están separados por 6 a 10 semanas y quedan pocos días de datos posteriores al último.

Los ajustes de colectivos y subte en CABA y Provincia son mensuales y chicos (≈ 4% a 5%, por IPC más 2%): no son saltos aislables, sirven como contexto.

### 6.3 Hallazgo adicional: no hay sustitución entre modos

En los 3 paros de colectivos (UTA), el colectivo cae a 0,15–0,27 de lo habitual, el subte queda en 0,96–0,98 y **el tren baja a 0,65–0,80**. En los paros de tren y subte, el colectivo no sube (0,74 y 0,63; 0,96 el 21-feb-2024). Es decir, **no hay evidencia de que los usuarios pasen de un modo a otro**; el tren incluso cae cuando para el colectivo, lo que sugiere complementariedad (muchos usuarios llegan a la estación en colectivo). Son pocas fechas, cada una confundida con otros factores del día, por lo que es una pista y no una conclusión.

### 6.4 Pendientes de verificación

- Las cifras de tarifas son de prensa; hace falta contrastarlas con las resoluciones del Boletín Oficial (Nación, CABA y Provincia) antes de usarlas como magnitud del tratamiento.
- Discrepancias que quedan abiertas: fecha exacta del aumento de colectivos de enero de 2024 (1 o 15), aumento del subte de fines de febrero de 2024 y alcance ferroviario del paro del 10-abr-2025.
- No se buscaron aún las caídas de menor tamaño que quedaron sin explicar (por ejemplo 18-dic-2022, 17-dic-2023 y 10-oct-2025).

---

## 7. Pendientes que ya identificamos (no se tocaron todavía)

- Evaluar con **rolling origin** (varios cortes) y comparar modelos con un test de significancia, en lugar de un único corte de 90 días.
- Revisar el SARIMAX: orden fijo sin justificación, regresoras redundantes (`es_dia_habil`, `es_fin_de_semana`, `es_feriado` son colineales) y sin estacionalidad anual. Los residuos no son ruido blanco (Ljung-Box con p < 0,05 en los tres rezagos).
- La ventana de test (junio–septiembre de 2026) incluye una caída fuerte a fines de julio que ningún modelo anticipa (probablemente vacaciones de invierno).
- Aplicar las herramientas vistas en clase que el trabajo todavía no usa: FFT, filtros en el dominio de la frecuencia, descomposición con medias móviles, correlación cruzada, causalidad.
- Construir la tabla de hitos (saltos tarifarios, paros, elecciones) con fuentes verificables.
