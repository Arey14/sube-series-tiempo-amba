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

Estado (2-nov-2026): el README y el notebook (`notebooks/TP_Final_Series_de_Tiempo.ipynb`) están reescritos en torno a las Preguntas 1 y 2. La sección 12 resume todos los cambios de enfoque y sus motivos en un solo lugar.

---

## 1. Verificación de que el pipeline se reproduce

**Qué se hizo:** se ejecutó `scripts/analisis_series_tiempo_sube.py` en un entorno nuevo (Python 3.11, `requirements.txt`) y se comparó contra las tablas publicadas.

**Resultado:** coincide. La única diferencia es Prophet, con MAPE 10,11% frente a 10,12% (ruido numérico). Los resultados originales eran reproducibles con los datos que había en ese momento.

---

## 2. Calidad de datos (`scripts/calidad_datos.py`, archivo nuevo)

### 2.1 Días faltantes

**Qué se encontró:** el README decía "100% de cobertura sin valores faltantes", pero el CSV tenía 2.391 filas para 2.453 días calendario. Faltan **62 días, que son dos meses completos: agosto de 2022 y enero de 2024**. El CSV oficial actual del portal tiene exactamente los mismos huecos: vienen de la fuente. El script original los rellenaba con una recta entre los bordes (`interpolate(method='linear')`).

**Por qué importa:** la serie tiene un ciclo semanal muy marcado. Una recta de 31 días elimina ese ciclo, y esos meses entraban así en STL, en los tests de estacionariedad y en el entrenamiento.

**Evidencia:** se ocultaron 89 bloques de 31 días de datos reales y se midió el error de cada método sobre los días ocultos (`tabla_simulacion_interpolacion.csv`, figura `fig7_interpolacion_huecos.png`):

| Método | Error mediano (MAPE) | Ciclo semanal que conserva |
|---|---|---|
| Lineal (el original) | 51% | ~1% |
| Spline cúbico | 76% (hasta 323% en el peor decil) | 15% |
| Lineal por día de la semana | 17% | 95% |

El spline llega a valores negativos con huecos largos. Con la interpolación por día de la semana, el error sube a 12%–25% y el sesgo va de −6% a +14% en meses de vacaciones (enero, julio).

**Estado:** este enfoque queda como **línea base de comparación**. El método que se usa es el de la sección 3, que reduce el error unas nueve veces.

### 2.2 Qué mide `total_amba`

**Qué se encontró:** según el portal, la unidad es "usuarios (tarjetas diferentes) utilizadas por día", no viajes ni pasajeros. El total nunca supera la suma de los modos y equivale a entre 83% y 89% de ella (`tabla_total_vs_suma_modos.csv`), lo que sugiere que deduplica tarjetas que usan más de un modo. El portal no documenta esto último; es una inferencia.

**Qué se cambió:** el README ahora habla de "tarjetas distintas por día" y no de "pasajeros". Hay que mantener ese criterio en la presentación.

### 2.3 Días atípicos

**Qué se encontró:** valores como subte = 1 o tren = 90 no son errores de registro. Se detectaron los días en que un modo cae por debajo de la mitad de la mediana del mismo día de la semana (±4 semanas): son feriados en su mayoría. Las fechas restantes (`tabla_dias_atipicos.csv`) corresponden a paros, domingos de elecciones con transporte gratuito y los 24 y 31 de diciembre (ver sección 7).

**Qué se cambió:** nada en los datos. No se descartan: son información para la Pregunta 1 y se incorporarán como eventos (dummies).

### 2.4 Datos preliminares y actualización del CSV

**Qué se encontró:**
- Los últimos 18 días del CSV del repo (1 al 18 de septiembre de 2026) estaban subestimados entre 1,7% y 4,9% respecto del CSV oficial actual. Es típico de datos preliminares que luego se completan.
- En el dataset de transacciones (ver sección 3), alrededor del 10% de las filas de 2026 (febrero a octubre) están marcadas `DATO_PRELIMINAR = SI`. Los datos más recientes se revisan al alza.

**Qué se cambió:** `data/total-usuarios-por-dia-AMBA.csv` se reemplazó por la versión oficial vigente (descargada de la URL que ya usa `scripts/descargar_datos.py`): 2.432 filas hasta el 29-oct-2026, contra 2.391 hasta el 18-sep-2026. El archivo anterior queda en el historial de git.

**Efecto:** las figuras y tablas del pipeline original que se habían generado con los datos anteriores cambiarán al volver a correrlo (se hará en la etapa de modelado). Los últimos días de la serie pueden seguir siendo preliminares: conviene que la ventana de evaluación de los modelos no termine pegada al final de los datos.

---

## 3. Reconstrucción de los usuarios en los huecos desde las transacciones (`scripts/usos_transacciones.py`, archivo nuevo)

**Qué se encontró:** el portal publica otro dataset, "Cantidad de transacciones (usos) por fecha" (un CSV por año, por línea, con modo, jurisdicción y marca AMBA). **No tiene huecos**: están los 31 días de agosto de 2022 y los 31 de enero de 2024. Usuarios y transacciones están muy relacionados: la correlación en logaritmos es de 0,995 para el total y de 0,999 para tren y subte, y el cociente usuarios/transacciones tiene un desvío de 0,03.

**Qué se hizo:** se estiman los usuarios de los días faltantes como `transacciones x razón usuarios/transacciones`, con la razón tomada por tipo de día (hábil, sábado, domingo) de los 28 días anteriores y posteriores al hueco, interpolada entre los bordes.

**Evidencia** (mismos 89 bloques de 31 días ocultos de la sección 2.1; `tabla_reconstruccion_usuarios.csv`, `fig12_reconstruccion_huecos.png`):

| Serie | Interpolación por día de semana | **Reconstrucción desde transacciones** |
|---|---|---|
| Total | 17,4% | **1,9%** |
| Colectivo | 17,2% | **1,8%** |
| Subte | 20,9% | **1,3%** |
| Tren | 23,7% | **2,0%** |

El sesgo mediano es de −0,4% a −0,1%. En meses de vacaciones (`tabla_reconstruccion_meses_vacaciones.csv`) el error es de 1,6% a 3,2% contra 12% a 21% de la interpolación (enero de 2025: 1,6% contra 15,9%; julio de 2026: 3,2% contra 20,8%). En los 2.433 días de la serie, ningún total queda fuera del rango [máximo de los modos, suma de los modos].

**Qué se cambió:** se agregan `data/procesado/usos_diarios_amba.csv` (transacciones por día y serie: colectivo nacional, provincial, municipal y CABA; tren; subte) y `data/procesado/serie_sube_diaria_reconstruida.csv` (usuarios con los 62 días reconstruidos y la bandera `imputado`). Los scripts de análisis usan ahora esa serie. El CSV crudo de transacciones (~60 MB por año) se descarga con el script y no se versiona (`data/raw_usos/` en `.gitignore`).

**Limitaciones:**
- Es una estimación (error mediano ≈ 2%), no un dato observado; los días quedan marcados.
- Transacciones y usuarios no miden lo mismo; la razón entre ambos se asume estable en el mes del hueco.
- Las líneas de jurisdicción CABA aparecen recién en 2025 (se transfirieron desde la jurisdicción nacional), de modo que las series por jurisdicción de colectivos tienen una discontinuidad de composición desde 2025.
- El subte viene en el dataset sin jurisdicción, provincia ni marca AMBA; hay que incluirlo sin filtrar.

---

## 4. Correcciones menores del repo (P10)

| Archivo | Cambio | Motivo |
|---|---|---|
| `notebooks/TP_Final_Series_de_Tiempo.ipynb` | La ruta de lectura pasó de `../data/series_tiempo/...` a `../data/...` | La carpeta `data/series_tiempo/` no existe en el repo; el notebook no corría. |
| `notebooks/TP_Final_Series_de_Tiempo.ipynb` | Se escaparon `\text{Var}` y `\text{Cov}` en una celda de Markdown | La barra simple se interpretaba como tabulación y rompía las fórmulas. |
| notebook y `analisis_series_tiempo_sube.py` | El título "Residuos Estandarizados SARIMAX" pasó a "Residuos SARIMAX (millones de usuarios)" | Se graficaba `sarimax_res.resid`, que no está estandarizado. |
| `README.md` | Se corrigió la cobertura de datos, la unidad de medida y el árbol de archivos | Ver 2.1 y 2.2. |
| `.gitignore` | Se agregaron archivos temporales de Office, formatos intermedios y los CSV crudos de transacciones | El original era genérico. |

---

## 5. Corrección de la fuga de información en la comparación de modelos (Fase 1b)

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

**Efecto sobre los resultados** (misma ventana de 90 días, 21-jun a 18-sep de 2026, con los datos anteriores a la actualización de la sección 2.4):

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

**Qué sigue sin cambiar:** es una sola ventana de test y no hay test de significancia, así que estos números no alcanzan para afirmar que un modelo es mejor que otro (ver sección 8). Los números se recalcularán con la serie reconstruida y los datos actualizados.

**Nota técnica:** Prophet no carga su backend desde Git Bash en Windows; funciona desde PowerShell o CMD.

---

## 6. Herramientas vistas en clase aplicadas a la serie (Fase 2)

Script nuevo: `scripts/herramientas_clase.py`. Figuras 8 a 11 y tablas `tabla_adf_kpss_decision_clase.csv`, `tabla_fft_picos_total.csv`, `tabla_ccf_tren_colectivo.csv`, `tabla_dias_candidatos_paro.csv`.

**Decisiones de diseño**
- **Serie principal:** del 7-ene-2022 al 29-oct-2026 (1.757 días = 251 semanas exactas), con los 62 días reconstruidos de la sección 3. Se recorta a semanas completas para que el ciclo semanal caiga exacto en un bin de la FFT.
- **Sensibilidad:** el tramo desde el 1-feb-2024 (1.001 días), que no tiene ningún día reconstruido. Las conclusiones no cambian entre ambas.
- El COVID queda fuera de todo este análisis.

**Resultados**

| Herramienta | Qué se observa |
|---|---|
| **ADF + KPSS con la tabla de decisión de la clase** | Total, colectivo y tren son estacionarios en nivel (el KPSS del tren queda en el borde, p = 0,0525; en el tramo corto el tren cae en "indefinida"); **el subte no lo es**. Esto **contradice la conclusión del repo original** (todas las series I(1)), que se había obtenido sobre 2020-2026 incluyendo el colapso del COVID. |
| **FFT sin DC** | Picos nítidos en 1/7, 2/7 y 3/7 ciclos/día (7; 3,5 y 2,3 días), con amplitudes de 0,94; 0,61 y 0,30 millones. Parseval verificado (energía en el tiempo = en frecuencia). La amplitud semanal es robusta: 0,944 M con la serie principal y 0,927 M en el tramo sin días reconstruidos. **Con 4,8 años de datos el ciclo anual ya es resoluble:** pico de ~351 días (0,24 M) y de ~176 días (0,22 M). |
| **Descomposición con MA** | Serie−MA7 deja los feriados como valles: media de −1,23 M en feriados contra +0,07 M en el resto. Se usa **MA28 y no MA30/MA21**: una media móvil de largo múltiplo de 7 anula exactamente el ciclo semanal. Contra la tendencia de STL: correlación 0,96, RMSE 0,18 M. La tendencia STL queda por encima de la MA28 porque STL robusto descuenta los valles de feriados y la media móvil no. La tendencia muestra valles anuales claros en cada enero. |
| **Filtros en el dominio de la frecuencia** | El elimina-banda anula el ciclo semanal por construcción (amplitud 0). Una MA7 también lo anula (0,0012 M): la media móvil es en sí un notch en 1/7 y sus múltiplos. El pasa-bajos ideal **oscila alrededor de la MA28** (rizado, tipo Gibbs). El elimina-banda deja la serie desestacionalizada con todos los feriados como valles profundos; algunos días llegan a valores ≤ 0, lo que no tiene sentido físico, resultado de restar el perfil semanal promedio a días que se comportan como domingo. El pasa-bajos se aparta algo más de la tendencia STL en los bordes (0,21 M en los primeros y últimos 14 días contra 0,16 M en el interior), efecto esperable de la periodicidad que asume la FFT. |
| **Retraso de las medias móviles** | La MA28 causal (solo pasado) llega 14 días tarde respecto del pasa-bajos en frecuencia (≈ (28−1)/2, lo esperado). **La MA centrada no tiene retraso**; la afirmación de que la media móvil "retrasa la señal" solo vale para la versión causal. |
| **CCF tren–colectivo** | Con residuos sin calendario, correlación de 0,85 en lag 0 y de 0,42 y 0,41 en lags −1 y +1; con diferencias simple + estacional, 0,92 en lag 0. No hay evidencia de un efecto con retraso: ambos modos se mueven juntos el mismo día. |
| **ACF** | Picos en los lags 7, 14, 21, 28, 35 y 42 (≈ 0,70 al inicio, decayendo lento). |

**Limitaciones que hay que tener presentes**
- **La CCF entre modos está dominada por causas compartidas** (calendario, clima, paros generales que afectan a todos), por lo que **no permite concluir una relación causal** entre el tren y el colectivo. En los residuos aparece además un piso de correlación ≈ 0,2 a 0,4 en todos los lags, que refleja variación lenta compartida.
- En la CCF de las series diferenciadas, los valores negativos en lags ±1 y ±7 son un **artefacto de las propias diferencias** (inducen correlación negativa en esos lags); solo el lag 0 es interpretable.

---

## 7. Tabla de hitos con fuentes (Fase 3, en curso)

Archivos nuevos: `scripts/hitos_eventos.py` y `data/hitos/hitos_paros_elecciones.csv` (paros y elecciones); los cambios de tarifa están en la serie de la sección 7.5. Cada hito tiene su fecha, descripción, modos afectados, **estado de verificación y URLs de las fuentes** (prensa y normativa). El script calcula además, desde los datos, cuánto cayó cada modo ese día respecto de su mediana del mismo día de la semana.

Estados: *confirmado (≥2 fuentes)*, *confirmado con discrepancias*, *norma oficial verificada (importes de prensa)*, *una fuente / a verificar*, *sin fuente (inferido del dato)*. Las fechas inferidas de memoria no se usaron sin verificar.

### 7.1 Paros y elecciones

| Hito | Resultado |
|---|---|
| **Paros generales de la CGT** | Cuatro contra el gobierno actual: 24-ene-2024, 9-may-2024, 10-abr-2025 y 19-feb-2026. Con la serie reconstruida **los cuatro son observables**. El del 24-ene-2024 fue más débil: colectivo 0,64, subte 0,73 y tren 0,54 de lo habitual, contra 0,08 en el colectivo el 9-may-2024 y 0,12 el 19-feb-2026. |
| **Paros específicos** | Trenes 21-feb-2024 (La Fraternidad); colectivos 11-abr-2024, 6-may-2025 y 7-jul-2023 (UTA); trenes y subte 30-oct-2024. Todos coinciden con los días atípicos de la sección 2.3. |
| **Elecciones** | Con transporte gratuito (Resolución 435/2023 y antecedentes de 2021) en las PASO y generales de 2021 y 2023: el subte cae a ~0 y el tren a 0,02–0,13 de lo habitual. **En 2025 las tres elecciones no muestran ese colapso** (cocientes de 0,6 a 1,1). El balotaje del 19-nov-2023 es consistente con gratuidad pero no se encontró fuente. |

**Hallazgo adicional: no hay sustitución entre modos.** En los 3 paros de colectivos (UTA), el colectivo cae a 0,15–0,27 de lo habitual, el subte queda en 0,96–0,98 y **el tren baja a 0,65–0,80**. En los paros de tren y subte, el colectivo no sube (0,74 y 0,63; 1,00 el 21-feb-2024). Es decir, no hay evidencia de que los usuarios pasen de un modo a otro; el tren incluso cae cuando para el colectivo, lo que sugiere complementariedad (muchos usuarios llegan a la estación en colectivo). Son pocas fechas, cada una confundida con otros factores del día: es una pista y no una conclusión.

### 7.2 Saltos tarifarios: qué quedó verificado en fuentes oficiales

Se contrastaron las tarifas contra el Boletín Oficial de la Ciudad y de la Nación y normas de la Provincia. Resultado:

| Hito | Estado y corrección |
|---|---|
| **Subte, Res. 27/SBASE/23** (sancionada el 26-dic-2023, publicada el 27-dic-2023) | Verificada. Dos tramos: A (≈ 5-ene-2024, $80 a $110, +37,5%) y B (30 días corridos después, 4-feb-2024, $125). Los importes son de prensa porque el Anexo II no es legible. |
| **Subte, Res. 5/SBASE/24** (8-may-2024, publicada el 9-may-2024) | Verificada. Tramo A ($574, +359%) rige desde el 17-may-2024; tramo B ($650) 15 días después. **El tramo B se bajó de $667 (propuesta) a $650**: una recopilación externa que cita $667 se equivoca. |
| **Subte, Res. 12/SBASE/24** (sancionada el 24-jul-2024, publicada el 26-jul-2024) | Verificada. **Posterga el tramo C ($757) del 1-ago al 1-oct-2024** por el retraso en el recambio de validadores. El Observatorio de la Ciudad y la recopilación externa ubican el $757 en agosto: es incorrecto. |
| **Colectivo y tren AMBA, Res. 8/2023 del Ministerio de Infraestructura** | Verificada. Dictada el 29-dic-2023, **publicada el 3-ene-2024 y vigente desde las 0 h del 15-ene-2024**. Restablece la actualización mensual por IPC y no fija valores (el +45% es de prensa). Resuelve la duda entre el 1 y el 15 de enero. |
| **Colectivo y tren AMBA, Res. 5/2024 de la Secretaría de Transporte** (5-feb-2024) | Norma identificada por dos fuentes, junto con la **adhesión de la Provincia (Res. 41/2024, 6-feb-2024)**. Colectivo mínimo a $270 (+251%) y tren a $130 (+247%). La vigencia del 6-feb es de prensa (el texto no se pudo leer). Como la Provincia adhirió el mismo día, los colectivos provinciales **no** son grupo de control. |
| **Colectivo y tren, agosto de 2022** | **+40% desde el 1-ago-2022, Res. 469/2022 del Ministerio de Transporte** (publicada el 21-jul-2022), según prensa. La recopilación externa cita la Res. 1017/2022: es incorrecto (esa norma fija el mecanismo de actualización de fines de 2022). Ahora **es evaluable**, porque cae en el hueco reconstruido. |
| **Tren, 6-may-2024 (+53,85%) y 16-sep-2024 (+40%, Res. 33/2024)** | Confirmados por prensa. Del primero, una nota da el 2-may y otra el lunes 6-may: se usa el 6-may (la versión anterior de esta tabla decía 2-may). Ocurre 3 días antes del paro general del 9-may-2024 y 11 días antes del salto del subte. |
| **2025 y 2026** | Solo una fuente. La recopilación externa contradice a Ámbito sobre el tren del 1-sep-2026 ($450 contra $480) y menciona un aumento "entrado en vigor" el 1-nov-2026, que es posterior a la fecha de este registro. Se necesita fuente oficial. |

Una conclusión sobre el subte: **hubo saltos de gran tamaño** (+37,5%, +13,6%, +359%, +13% y +16% entre enero y octubre de 2024), que la versión anterior de esta tabla no registraba por completo.

### 7.3 El salto de febrero de 2024 sí se puede evaluar

Con la serie reconstruida y, sobre todo, con las **transacciones por jurisdicción** (sección 3), el salto de febrero de 2024 y el hueco de enero ya no impiden el análisis. Como primera mirada descriptiva (`scripts/tarifas_descriptivo.py`, `fig13_usos_yoy_tarifas_2024.png`, `tabla_tarifas_feb2024_yoy.csv`), se compara cada serie contra el mismo día de la semana del año anterior, en días hábiles que no son feriado en ninguno de los dos años (los feriados móviles no coinciden entre años y generaban picos de ±50%):

| Serie | Cociente interanual antes (16-ene a 5-feb) | Después (14-feb a 8-mar) | Cambio |
|---|---|---|---|
| Colectivo nacional | 1,035 | 0,957 | −7,6% |
| Colectivo provincial | 0,975 | 0,886 | −9,2% |
| Colectivo municipal | 0,985 | 0,883 | −10,3% |
| Tren | 1,074 | 1,120 | **+4,3%** |
| Subte | 0,777 | 0,781 | +0,4% |

Además, el subte muestra un **escalón de −22,7% el 5-ene-2024**, cuando rige el tramo A (+37,5%), y de −3,9% alrededor del 4-feb-2024.

**Cómo leerlo:** los tres colectivos bajan juntos después del 6-feb, por lo que el colectivo municipal no es un control independiente. El tren no baja pese a +247%, lo que sugiere sustitución desde el colectivo (cuyo boleto pasó a ser más del doble que el del tren). **Es descriptivo, no causal**: hay otros cambios al mismo tiempo (devaluación de diciembre de 2023, caída del salario real, ajustes de otras jurisdicciones) y la comparación interanual no controla vacaciones ni otros eventos. El diseño causal (con control de calendario y de eventos) es el paso siguiente.

### 7.4 Pendientes de verificación

- Los importes de tarifas de 2024 salen de prensa y del Observatorio de la Ciudad; los Anexos II de las resoluciones del subte no se pudieron leer. No se pudo leer el texto de la Res. 5/2024 (nacional) ni de la Res. 469/2022.
- Existe un conflicto judicial por los aumentos del subte de 2024 (prensa y recopilación externa lo describen de forma distinta): no se verificó si alteró las tarifas efectivas.
- Hay que contrastar con fuente oficial los aumentos de 2025 y 2026.
- No se buscaron aún las caídas de menor tamaño que quedaron sin explicar (por ejemplo 18-dic-2022, 17-dic-2023 y 10-oct-2025).

### 7.5 Serie de tarifas por modo y jurisdicción

Para estimar el efecto del precio sobre la demanda con **todos** los cambios confirmables (grandes y chicos) hace falta la tarifa por modo y fecha, no solo porcentajes. Archivos nuevos: `scripts/tarifas_serie.py`, `data/hitos/serie_tarifas.csv` (un cambio por fila, con fuente y estado), `data/hitos/serie_tarifas_diaria.csv` (tarifa vigente por día), `data/hitos/hitos_tarifas.csv` (cambios clasificados) y `tabla_tarifas_cobertura.csv`. Reemplaza la lista de saltos que antes estaba en `hitos_eventos.py`.

**Qué contiene:** el boleto mínimo con SUBE registrada de cinco series (colectivo de jurisdicción nacional, líneas porteñas, líneas provinciales, tren y subte), de enero de 2022 a septiembre de 2026: 88 cambios. Cada fila indica si la norma oficial identifica el cambio (`norma + prensa`), si lo confirman dos medios, una sola fuente, un conflicto entre fuentes o si se infirió. Los importes salen de prensa porque los anexos oficiales son imágenes o PDF no legibles; las normas confirman cambios y fechas. La serie de tren sigue los ramales Mitre, Sarmiento, San Martín y Tren de la Costa (los de mayor tarifa).

**Clasificación:** 27 saltos (≥ 10% y sin valores intermedios faltantes), 46 ajustes chicos y **8 "acumulados con huecos"**: variaciones grandes entre dos valores separados por varios meses de ajuste mensual (por ejemplo, el colectivo porteño de +28,9% entre febrero y septiembre de 2025), que son la suma de ajustes no relevados y no deben tratarse como un salto.

**Lo que se encontró al verificar:**
- **Colectivo nacional:** $18 hasta julio de 2022; $25,20 (1-ago-2022, +40%, Res. 469/2022); $35 (ene-2023); ajuste mensual por IPC de marzo a agosto de 2023 ($37,10, $39,59, $42,67, $46,35, $50,06 y $52,96); congelamiento por la **Res. 501/2023** (30-ago-2023); $76,92 (15-ene-2024); $270 (6-feb-2024); $371,13 (12-ago-2024). **Ocho meses sin aumentos** hasta el 23-may-2025 (Res. 28/2025: $397,11, $424,91 y $451,01). En 2026: +31% el 18-feb ($650) y +7,6% el 16-mar ($700), y la **Res. 27/2026** (sancionada el 15-may-2026, BO 18-may-2026) fija tres etapas de +2%.
- **Tren (Mitre, Sarmiento, San Martín):** $17,25 (ago-2022), $22 (ene-2023), ajuste mensual en 2023, $48,38 (15-ene-2024), $130 (6-feb-2024, **+168,7%**, que coincide con el 169% de la prensa; Roca, Belgrano y Urquiza pasaron de $37,38, de ahí el +247%), $200 (6-may-2024) y $280 (16-sep-2024, Res. 33/2024), y **sin cambios durante unos veinte meses** hasta el 18-may-2026. La Res. 27/2026 prevé cinco etapas mensuales cuyos importes están en anexos no legibles; las fuentes se contradicen (por ejemplo, $330 o $310 para la primera etapa y $450, $480 o $530 para septiembre).
- **Subte:** $42 desde el 23-sep-2022 (+40%, Res. 17/SBASE/22), $58 (7-mar-2023, Res. 5/SBASE/23), $67 (6-may), $74 (5-jun) y $80 (3-sep-2023, tramo D a 90 días del C según la norma; algunas notas dicen octubre). Siguen los tramos de 2024 de la sección 7.2. **El $832 rige desde el 28-feb-2025** (Res. 47/SBASE/25, quinto día hábil desde su publicación el 20-feb); una fuente anterior lo ubicaba en diciembre de 2024, lo que es incorrecto.
- **Provincia y Ciudad:** hasta febrero de 2025 las líneas porteñas y las provinciales mantuvieron el valor nacional ($371,13). Después: Ciudad +10% el 21-feb-2025; Provincia +10% el 1-mar-2025 y +14,8% el 1-dic-2025 (incluye un 10% extraordinario); ambas con ajuste mensual (IPC + 2%) desde abril de 2025.

**Huecos y límites:**
- Faltan los valores mensuales de varios períodos con ajuste mensual: líneas porteñas (jul–ago de 2025, ene–mar y may/jul de 2026), líneas provinciales (ago, oct–nov de 2025 y ene–mar y jul–ago de 2026), subte (mar de 2025, ago–oct de 2025, dic-2025 y feb–abr de 2026), y tren en 2023 (feb, abr y jul).
- Las líneas provinciales de 2024 se infieren del valor nacional (la Provincia adhirió a la tarifa del 6-feb-2024). Las líneas provinciales y porteñas anteriores a 2024 no se cargaron (eran de jurisdicción nacional o seguían su propio cuadro).
- Hay cinco cambios de tren, tres de subte y uno de colectivo con conflicto entre fuentes.
- **Una recopilación externa de tarifas y el informe del Observatorio de la Ciudad contenían errores** que se corrigieron con normas: $667 contra $650 y $757 en agosto contra el 1-oct (subte 2024), $832 en diciembre de 2024 contra el 28-feb-2025, y la Res. 1017/2022 como origen del +40% de 2022. La serie solo usa esas fuentes para pistas que luego se contrastan.

---

## 8. Pendientes que ya identificamos (no se tocaron todavía)

*Actualización del 2-nov-2026: el origen móvil con test de significancia, la revisión del SARIMAX, la ventana de test, el diseño causal de P-1 y la reescritura del README y el notebook están hechos (secciones 10, 11 y 12). La lista de abajo es la original.*

- Evaluar con **rolling origin** (varios cortes) y comparar modelos con un test de significancia, en lugar de un único corte de 90 días; recalcular con la serie reconstruida y los datos actualizados.
- Revisar el SARIMAX: orden fijo sin justificación, regresoras redundantes (`es_dia_habil`, `es_fin_de_semana`, `es_feriado` son colineales) y sin estacionalidad anual. Los residuos no son ruido blanco (Ljung-Box con p < 0,05 en los tres rezagos).
- La ventana de test (junio–septiembre de 2026) incluye una caída fuerte a fines de julio que ningún modelo anticipa (probablemente vacaciones de invierno).
- Diseño causal de la Pregunta 1: diferencias en diferencias o impacto causal con control de calendario, pruebas placebo y Granger; elección de controles (la Provincia adhirió a las tarifas nacionales de febrero de 2024, y las líneas porteñas recién aparecen como jurisdicción en 2025).
- Reescribir README y notebook en torno a las Preguntas 1 y 2.

### 7.6 Trenes 2026 resueltos con el Anexo II de la Res. 27/2026

El anexo (imagen) se transcribió a mano desde capturas del texto oficial. Boleto mínimo con SUBE nominalizada (sección 1, 0–12 km), igual en las ocho líneas:

| Etapa | Valor | Antes en la serie |
|---|---|---|
| 18-may-2026 | $310 | $330 (conflicto) |
| 1-jun-2026 | $350 | $350 (inferido, con fecha 15-jun) |
| 1-jul-2026 | $380 | $380,10 |
| 1-ago-2026 | $420 | $420 (conflicto) |
| 1-sep-2026 | $450 | $480 (conflicto) |

Las etapas de colectivos nacionales (SGI) del mismo anexo confirman $714,00, $728,28 y $742,81. Desde mayo de 2026 todas las líneas tienen el mismo precio: Roca, Belgrano y Urquiza subieron más que Mitre, Sarmiento y San Martín (la serie sigue a estas últimas). El efectivo y la SUBE sin nominalizar pagan el doble o más.

### 7.7 Huecos cerrados con anexos de resoluciones y el informe de CEPA

Los importes del subte (tramo A) se transcribieron de las resoluciones de Directorio de SBASE; los de colectivos, de los anexos de Provincia y de la Ciudad. Resultado: 100 cambios, 29 saltos, 60 ajustes, 4 acumulados con huecos.

- **Subte:** se cargan $1.031 (Res. 89/2025), $1.112 (Res. 99/2025), $1.320 (Res. 143/2026), $1.363 (Res. 153/2026) y $1.414 (abril, informe de CEPA). Las resoluciones de 1260, 1490, 1558, 1621 y 1684 pasan a "norma + prensa" y resuelven los dos conflictos de centavos. La vigencia de cada una se infiere de que se publican a fin del mes anterior (por ejemplo la Res. 70/2025, publicada el 26-may, rige en junio). Marzo de 2025 no es un hueco: el $832 del 28-feb siguió vigente hasta abril.
- **Colectivos de Provincia:** el anexo de marzo de 2026 da $832,57 (+15,3% sobre $721,83), no los $757,20 de la prensa. El $871,30 de abril es +4,65% sobre $832,57 y +15% sobre $757,20, así que se toma el anexo. En mayo hubo un aumento extraordinario (+11%, $968,57).
- **Colectivos de la Ciudad:** se agregan febrero (inferido), marzo ($681,97), mayo ($753,74) y octubre de 2026 (inferido: $920,72). El anexo de noviembre ($956,69) es posterior al último dato de la serie diaria.
- **Tren de mayo de 2026:** el informe de CEPA repite $330, pero el Anexo II de la Res. 27/2026 dice $310 (sección 1). Se mantiene $310.
- **Siguen sin cerrar:** subte de diciembre de 2025; subte de octubre de 2026 (Res. 238/2026); tren de 2023 (febrero, abril y julio; sin cuadro tarifario); Provincia de enero a febrero de 2026 y de julio a octubre; Ciudad de julio de 2025 y enero de 2026.

### 7.8 Más huecos cerrados y validación contra CEPA

- **Subte, diciembre de 2025:** la Res. 134/2025 se publicó el 17-dic-2025 con $1.260. Con la fórmula IPC (n-2) + 2%, $1.157 x 1,043 x 1,045 da $1.261, así que $1.260 corresponde a enero y diciembre queda inferido en $1.207. Si el anexo de la Res. 134 trae una columna de diciembre, hay que corregirlo.
- **Subte, julio de 2025:** el anexo confirma $996,71 (la fila ya estaba cargada).
- **Colectivos de la Ciudad:** se cargan julio de 2025 ($488,70), agosto de 2025 ($506,29) y julio de 2026 ($820,99; una nota da $820,60). Los cuadros oficiales de la Ciudad están en `static.buenosaires.gob.ar/sites/default/files/AAAA-MM/RESOLUCIÓN_TARIFAS_CABA_<MES>_<AÑO>.pdf`.
- **Colectivos de Provincia:** se cargan agosto de 2025 (inferido), julio de 2026 ($1.063,98 o $1.059,28), agosto de 2026 ($1.111,19) y octubre de 2026 (inferido).
- **Octubre de 2026:** el análisis termina el 30-sep-2026 (los últimos días de la serie son preliminares), así que no hace falta la Res. 238/2026 del subte. Los valores de octubre cargados son inferidos y no entran en el modelo.
- **Validación de la demanda contra CEPA** (pasajeros mensuales de INDEC, CNRT y Metrovías, nov-2023 a feb-2026): el tren coincide con las transacciones de SUBE entre 1% y 3% en todos los meses revisados, y el subte coincide hasta 2024 (1,5% a 3%). **Desde 2025 el subte de SUBE queda entre 18% y 30% por debajo de CEPA** (julio de 2025: 13,0 M contra 18,4 M; febrero de 2026: 8,0 M contra 11,7 M). Hay que revisar si el archivo de transacciones pierde registros del subte desde 2025 antes de usar esa serie. El colectivo no es comparable: CEPA toma un alcance menor (cerca de la mitad de nuestras transacciones) y estable.

- **Provincia, julio de 2026:** Econoblog da $1.057,25, que es +4,1% sobre junio, el mismo porcentaje de la Ciudad. Se toma ese valor en lugar de $1.063,98 o $1.059,28.
- **Subte:** se usan los importes de las resoluciones del Boletín Oficial. La comparación con CEPA queda como verificación pendiente de la demanda, no como fuente de tarifas.

### 7.9 Huecos revisados con la respuesta de otra IA (sin enlaces; se aceptó solo lo coherente)

- **Tren, abril y julio de 2023:** $24,88 y $31,44 (Mitre, Sarmiento, San Martín y Tren de la Costa). Cada valor reproduce las variaciones del colectivo nacional en los meses vecinos, así que se aceptan como una fuente.
- **Tren, febrero de 2023:** no era un hueco. La indexación mensual empieza en marzo (+6% sobre enero en colectivo y tren), así que febrero sigue en $22,00.
- **Ciudad y Provincia, enero de 2026:** $620,07 y $685,11. Coinciden con la fórmula IPC + 2% sobre diciembre.
- **Rechazado:** $721,08 para Provincia en febrero (el anexo oficial dice $721,83: error de transcripción), $637,58 para la Ciudad en febrero (contradice la fórmula y el +4,9% de marzo; se mantiene el inferido $650,11) y la Res. 1017/2022 como norma del aumento.
- **Sin información útil:** el tren de febrero de 2023 ("entre $18,02 y $24") y los valores de otras líneas (Roca, Belgrano, Urquiza), que no entran en la serie.

## 9. Modelo de precio y demanda (P-1), primer resultado

Script: `scripts/modelo_precio_demanda.py`. Demanda: transacciones diarias por modo (marzo de 2022 a septiembre de 2026). Precio: tarifa mínima con SUBE registrada. Tres estimaciones:

- **A. Niveles semanales** con efectos de mes, feriados, paros y elecciones. El signo depende de si se incluye una tendencia: sin ella, el precio absorbe todo lo que cambia con el tiempo (colectivo nacional −0,08, tren −0,06, subte −0,15); con tendencia lineal el colectivo nacional y el tren pasan a +0,10 y +0,03. Un precio que solo sube no se puede separar de la tendencia con una regresión de niveles.
- **B. Diferencias interanuales (52 semanas):** colectivo nacional +0,06, tren +0,01, subte −0,09, colectivo provincial −0,29 (solo desde febrero de 2024).
- **C. Estudio de eventos** (cambio de la demanda de días hábiles normales antes y después de cada salto, menos lo ocurrido un año antes). El colectivo nacional cayó 13% neto con una tarifa 3,9 veces mayor (elasticidad de arco −0,10); el subte cayó entre 10% y 22% con alzas de 13% a 34% (elasticidad entre −0,4 y −0,8) y 18% con el salto de +359%; el tren no cayó con el salto de enero-febrero de 2024 (+1%) pero sí con el de mayo de 2024 (−15%).
- **Placebo:** en fechas sin cambio de precio el efecto neto queda casi siempre entre −0,05 y +0,08 en log. Los saltos del colectivo nacional de 2024, los del subte y el del tren de mayo de 2024 quedan fuera de esa banda; los demás no se distinguen del ruido.

Lectura: la demanda respondió poco al precio (elasticidades de colectivo y tren cercanas a cero, subte más sensible), pero las estimaciones son inestables entre métodos y eventos. No es un efecto causal: faltan el ingreso, la inflación y las tarifas de los demás modos. Pendientes: tarifa real (deflactada por IPC), efecto cruzado entre modos, Granger y el control con serie sintética.

### 9.1 Corrección sobre el subte: línea D cerrada en 2024

La línea D estuvo sin servicio del 8-ene-2024 al 6-mar-2024. Eso explica la caída del subte en el evento de enero–febrero de 2024: sin la línea D el efecto pasa de −21,5% a −6,1%. El modelo debe usar el subte sin línea D en esas semanas. Detalle y lectura de los resultados en `docs/interpretacion_resultados.md`.

## 10. Pregunta 1 completa: precio, hitos y causalidad (2-nov-2026)

Las lecturas de cada paso, con sus límites, están en `docs/interpretacion_resultados.md` (bloques 1 a 10). Acá solo se lista qué se agregó y por qué.

**Datos nuevos**

| Archivo | Qué es |
|---|---|
| `data/hitos/serie_tarifas*.csv`, `hitos_tarifas.csv` | Serie de tarifas por modo y jurisdicción (112 cambios, 29 saltos) armada desde resoluciones oficiales y, donde no había norma a mano, inferida (por ejemplo, Ciudad y Provincia con la fórmula IPC + 2% sobre el mes anterior); cada fila indica su fuente. Cobertura en `resultados/tablas/tabla_tarifas_cobertura.csv`. Generada por `scripts/tarifas_serie.py`. |
| `data/externos/ipc_nacional_indec.csv` | IPC nacional (INDEC) para deflactar la tarifa. Septiembre de 2026 está extrapolado. |
| `data/externos/MT_eah_2417.xlsx`, `comunas.geojson.txt`, `estaciones_de_subte.geojson.txt`, `red_subte.geojson.txt` | Ingreso per cápita por comuna (Encuesta Anual de Hogares, CABA) y geografía del subte, para ubicar cada línea en una comuna. |
| `data/procesado/usos_diarios_subte_por_linea.csv` | Transacciones diarias por línea de subte (A, B, C, D, E, H, P) y `subte_sin_D`, de `scripts/usos_por_linea.py`. |

**Cambios y hallazgos**

1. **Tarifa real.** Las estimaciones se rehicieron con la tarifa deflactada por IPC (`scripts/modelo_precio_demanda.py`): en niveles el signo depende de si se incluye tendencia (no identificado); en diferencias interanuales y estudio de eventos, la demanda del subte responde (elasticidad de −0,22 a −0,26) y la del colectivo nacional y el tren no se distingue de cero.
2. **Subte sin línea D.** La línea D estuvo cerrada del 8-ene al 6-mar de 2024, y confundía el evento de enero–febrero de 2024. Se usa `subte_sin_D` en esas estimaciones. No se descartó la línea D de la serie porque se necesita para la hipótesis siguiente.
3. **Hipótesis de ingreso (H-ingreso).** Diseñada antes de correr (bloque 3): las líneas de zonas de mayor ingreso reaccionarían menos a los saltos de tarifa. Índice de ingreso por línea con `scripts/clasificacion_lineas_subte.py` y panel línea × semana con `scripts/panel_subte_lineas.py`. **No hay respaldo** (signo contrario o nulo; con 6 líneas la prueba tiene poco poder).
4. **Efecto cruzado entre modos y Granger** (`scripts/efectos_cruzados_granger.py`): no hay sustitución visible; solo el precio propio del subte anticipa su demanda (p de Holm 0,019).
5. **Hitos de calendario** (`scripts/hitos_efectos.py`): la demanda de feriados, paros propios, elecciones con gratuidad y pandemia, medida contra el mismo día de la semana de las semanas vecinas. Es el resultado más claro y estable de P-1.
6. **Control sintético** (`scripts/control_sintetico.py`) para los saltos del colectivo, con ciudades del interior como donantes: da −3% sin significancia, contra −13% del estudio de eventos. No confirma el resultado de eventos.

**Efecto sobre los resultados originales:** el resultado del precio del colectivo (casi nulo) queda con baja confianza; el del subte, con confianza media. Lo del COVID pasa a ser descriptivo, como se decidió en la sección 0.

## 11. Pregunta 2 completa: qué método pronostica mejor y por qué (2-nov-2026)

Detalle en `docs/interpretacion_resultados.md`, bloques 11 a 15.

**Qué cambió respecto de la comparación original (sección 5):** la comparación de modelos de una sola ventana de 90 días se reemplazó por una **evaluación con origen móvil**, que repite el pronóstico en 42 cortes sucesivos (el primero el 30-jun-2023, uno cada 28 días), cada uno con 28 días de prueba que no se solapan. Así hay 1.161 días de evaluación en lugar de 90 y se puede probar si una diferencia es real (Diebold-Mariano) en vez de comparar un número contra otro.

| Archivo | Qué hace |
|---|---|
| `scripts/pronosticos_p2.py` | Los cinco modelos (Naive de 7 días, Naive de 364 días, SARIMAX, Prophet, Gradient Boosting recursivo) con las reglas anti-fuga. |
| `scripts/identificacion_sarimax.py` | Identifica el orden del SARIMAX con ADF/KPSS, ACF/PACF y BIC, solo con datos anteriores al primer corte. |
| `scripts/evaluacion_pronosticos.py` | Origen móvil (argumentos: `ablaciones`, `col=<modo>`, `h=<días>`). |
| `scripts/analisis_pronosticos_p2.py`, `analisis_pronosticos_por_modo.py` | Métricas (MAE, RMSE, MAPE, MASE), Diebold-Mariano, por tipo de día y período, intervalos de predicción. |
| `scripts/modelo_hibrido_p2.py` | Híbrido por tipo de día. |
| `scripts/sensibilidad_huecos_p2.py` | Qué pasa si los 62 días sin dato se tratan de otra forma. |
| `scripts/analisis_horizontes_p2.py` | Horizontes de 7 y 90 días. |
| `scripts/verificar_sin_fuga_p2.py` | Prueba de que los modelos no usan información posterior al corte. |

**Resultados**

- **Total AMBA, 28 días:** gana el Gradient Boosting (MAE 0,187 millones, MAPE 7,4%, MASE 0,57), seguido por Prophet (0,254) y SARIMAX (0,270); los Naive quedan en 0,40 y 0,47. La diferencia es significativa (p < 0,0001) y se sostiene en los cuatro períodos evaluados.
- **Por qué:** los feriados explican el grueso de la diferencia con los Naive; la estacionalidad anual y el patrón semanal multiplicativo importan; el Gradient Boosting gana por su flexibilidad con el calendario y por los rezagos. Configuración estándar, sin ajuste fino.
- **Por modo:** colectivo, igual que el total. Tren y subte: el Gradient Boosting empata con el SARIMAX.
- **Híbrido por tipo de día** (aditivo en días hábiles, Gradient Boosting en el resto, con la elección hecha solo con cortes anteriores): mejora a ambos métodos en tren (MASE 0,62 → 0,54) y subte (0,71 → 0,61); no mejora en total ni colectivo. Hallazgo a confirmar en otro período.
- **Huecos:** el ranking no depende de cómo se traten los 62 días sin dato; la reconstrucción mejora el error del Gradient Boosting (MASE 0,56 contra 0,63 con interpolación).
- **Horizontes:** el ranking es el mismo a 7, 28 y 90 días; el error crece poco (MASE del Gradient Boosting 0,56, 0,57, 0,61).

**Errores corregidos en el camino:** la comparación original tenía fuga de información (sección 5); ahora `scripts/verificar_sin_fuga_p2.py` reemplaza el futuro por basura (×10) en tres cortes y verifica que los pronósticos de los cinco modelos no cambian (diferencia 0).

**Qué queda:** la presentación y el guion para el video.

## 12. Resumen de cambios de enfoque y sus motivos (2-nov-2026)

Esta sección junta en un solo lugar las decisiones que cambiaron el rumbo del trabajo respecto del repositorio original (commit `fadc6b6`). El detalle y la evidencia de cada una están en las secciones indicadas.

| # | Qué se cambió | Por qué | Dónde |
|---|---|---|---|
| 1 | Las **Hipótesis 1 y 2** y sus veredictos se reemplazan por las **Preguntas P-1 y P-2** | Los veredictos (por ejemplo, que el teletrabajo causó una pérdida permanente de demanda) no son sostenibles con los datos disponibles. Las preguntas admiten respuestas con distinto grado de confianza y son las de la presentación de la materia. | 0 |
| 2 | Se quita la **recuperación post-COVID contra el nivel pre-pandemia**; el COVID pasa a ser un shock **descriptivo** y queda fuera del entrenamiento | Solo hay enero y febrero de 2020 como base (59 días, temporada baja): no distingue recuperación de estacionalidad anual. | 0, 10 |
| 3 | Se corrige la **fuga de información** del Seasonal Naïve y del Gradient Boosting | El Naïve tomaba valores reales del tramo de prueba y el Gradient Boosting usaba rezagos reales al pronosticar. El MAPE del Gradient Boosting pasó de 8,82% a 11,03% con la corrección. Ahora los modelos solo usan el pasado y el calendario y hay una prueba que lo verifica. | 5, 11 |
| 4 | La evaluación pasa de **una ventana de 90 días** a **42 cortes sucesivos de 28 días** (origen móvil) con Diebold-Mariano | Con una sola ventana no se distingue un modelo mejor de uno con suerte. Con 1.161 días de prueba y una prueba de significancia sí. Después se verifica con horizontes de 7 y 90 días. | 11 |
| 5 | Se **reconstruyen los 62 días sin dato** desde las transacciones, en lugar de interpolar | Error de 1,6% a 3,2% en meses de vacaciones, contra 12% a 21% de la interpolación. El ranking de modelos no depende de esta decisión (verificado). | 3, 11 |
| 6 | El **SARIMAX** se identifica con ADF/KPSS, ACF/PACF y BIC, y se agrega estacionalidad anual | El orden original era fijo y sin justificación, con regresoras colineales y residuos autocorrelacionados. | 11 |
| 7 | Se agrega **causalidad** a P-1: tarifa real, estudio de eventos con control del año anterior, control sintético, panel por línea y Granger | El docente pidió incorporar causalidad y explicar el porqué. Cada diseño declara sus supuestos y sus límites; ninguno es un experimento. | 10 |
| 8 | Se agrega la **hipótesis de ingreso por línea de subte** (fijada antes de correr) | Hipótesis complementaria propuesta: las líneas de zonas de mayor ingreso reaccionarían menos a los saltos tarifarios. Resultado sin respaldo y con poco poder. | 10 |
| 9 | Se agrega la **serie de tarifas con fuentes** y el **IPC** | Sin una serie de tarifas verificada no hay análisis de precio. Se usan resoluciones oficiales; lo inferido está marcado. | 7, 10 |
| 10 | Se agregan el **modelo híbrido por tipo de día**, la **sensibilidad a los huecos** y los **horizontes de 7 y 90 días** | Responden "por qué" gana cada método y si el resultado es robusto. | 11 |
| 11 | Se **reescriben el README y el notebook** | Para que el repositorio sea coherente con el nuevo enfoque y no muestre resultados que ya no se sostienen (el notebook original mostraba las métricas con fuga y las hipótesis "corroboradas"). El notebook lee los resultados guardados por los scripts. | 0 |

**Qué se conserva del trabajo original:** los cuatro modelos (Seasonal Naïve, SARIMAX, Prophet y Gradient Boosting) y el pipeline inicial (`analisis_series_tiempo_sube.py`, `modelos_pronostico.py`). Las figuras `fig4`, `fig5` y `fig6` salen de ese pipeline y quedan como referencia: ya no sustentan ninguna conclusión.

---

## 13. Correcciones de la revisión del notebook (3-nov-2026)

Cambios hechos después de revisar el notebook, con su motivo. Evidencia en `docs/interpretacion_resultados.md`, bloques 16 a 19.

| # | Qué se cambió | Por qué | Dónde |
|---|---|---|---|
| 12 | **ADF y KPSS** se calculan en tres tramos: serie completa desde 2020, 2022–2026 y entrenamiento inicial (2022 a jun-2023) | Mostrar que la no estacionariedad del nivel de la serie completa viene de la pandemia: sin ella (2022–2026) el nivel es estacionario. La decisión del SARIMAX (d = 0, D = 1 con período 7) no cambia. | Notebook, sección 4 |
| 13 | **Tarifa real y tarifa en salarios** (`tarifas_reales.py`, `fig25`) | La serie nominal confunde inflación con aumento real. Se muestra la tarifa deflactada por IPC y el costo de 40 viajes mensuales como porcentaje del RIPTE. | 16 |
| 14 | **Control por salario real** (RIPTE / IPC) en la elasticidad; se incorpora el **RIPTE** como dato externo | Se había dejado como trabajo futuro y es fácil de obtener (datos.gob.ar). No cambia las conclusiones cualitativas; baja la elasticidad del subte de −0,22 a −0,15 y el colectivo provincial pierde significancia. Antes se decía que el efecto "no es limpio por falta de control de ingreso"; la formulación se reemplazó por una más precisa sobre los supuestos de cada diseño. | 17 |
| 15 | **Paros clasificados por quién paró** y **elecciones por gratuidad**; `fig17` rehecha con fechas legibles y nueva `fig26` | "Paro" mezclaba paros de colectivo, de tren, de tren y subte y generales. La demanda de cada modo depende de quién paró; separarlos muestra que no hay sustitución hacia otros modos. La mediana de las elecciones (0,34) mezclaba dos situaciones. | 18 |
| 16 | **Terminología precisa**: "salto tarifario" (≥ 10% en un cambio), "salto tarifario grande" (la tarifa se duplica o más) y "ajuste" (< 10%); definición de **elasticidad** con valores de referencia | En el notebook y el README "saltos" y "saltos grandes" no decían a qué se referían. | Notebook, sección 5; README |
| 17 | **Explicación metodológica ampliada** del notebook: con y sin tendencia, bandas placebo, columnas de cada tabla, lectura de gráficos, control sintético, efecto cruzado y Granger, contraste de ingreso | La versión anterior resumía de más y no permitía leer las tablas. | Notebook, sección 5 |
| 18 | **Fuentes de datos externas** definidas (transacciones del interior, EAH de CABA, RIPTE, IPC, tarifas, BA Data) con su alcance | Condicionan cómo se leen los resultados (la EAH cubre solo la Ciudad; las tarifas del interior no se verificaron). | Notebook, sección 3 |
| 19 | **P-2 aplicada a los hitos de P-1** (`pronostico_hitos_p2.py`, `pronosticos_antes_del_salto_p2.py`, `fig27`): error en feriados, paros, elecciones y saltos tarifarios; pronóstico condicional con el cociente de P-1; pronóstico con precio | Para planificar importa qué pasa con la demanda ante un paro, una elección o un aumento. Resultado: los feriados se anticipan, los paros y elecciones gratuitas no con ningún método, y el escenario con el efecto de P-1 reduce el error de 81% a 94%; el precio ayuda poco en saltos moderados y empeora en los grandes. | 19; notebook, sección 6.9 |
