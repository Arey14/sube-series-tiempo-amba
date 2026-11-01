# Interpretación de resultados (bitácora)

Cada bloque guarda qué se midió, qué dio, cómo se lee y qué se dijo en su momento. Se agregan bloques nuevos al final; los anteriores no se reescriben, para poder evaluarlos al terminar. Las tablas y figuras salen de los scripts: `resultados/tablas/` y `resultados/figuras/`.

## 1. Precio y demanda (pregunta P-1), primera corrida — 1-nov-2026

Script: `scripts/modelo_precio_demanda.py`. Datos: transacciones diarias por modo (marzo de 2022 a septiembre de 2026) y tarifa mínima con SUBE registrada (`data/hitos/serie_tarifas_diaria.csv`).

### Qué se busca

Responder cuánto cambia la demanda cuando cambia la tarifa. Es la parte de P-1 que pide la cátedra: no alcanza con describir que la demanda cayó después de un aumento, hay que separar el efecto del precio de lo que habría pasado igual (estación, feriados, paros, tendencia general).

La medida es la **elasticidad**: el cambio porcentual de la demanda cuando la tarifa cambia 1%. Una elasticidad de −0,2 significa que una suba de 10% en la tarifa se asocia con una baja de 2% en la demanda. Cerca de cero, la demanda casi no reacciona; menos de −1, reacciona más que proporcionalmente.

Se usan tres métodos porque ninguno es concluyente por sí solo. Si los tres coinciden, el resultado es robusto; si no, se muestra la incertidumbre en lugar de elegir el que más gusta.

### A. Niveles semanales (`tabla_elasticidad_niveles.csv`)

Se ajusta log(demanda semanal) contra log(tarifa), con controles de mes del año, feriados, paros y elecciones.

- **Sin tendencia:** el modelo atribuye al precio todo lo que cambia con el tiempo. Como la tarifa solo sube, cualquier cosa que caiga en el tiempo (salarios reales, hábitos, trabajo remoto) se lee como efecto del precio.
- **Con tendencia lineal:** el modelo permite que la demanda siga una recta en el tiempo y le deja al precio solo lo que se aparta de ella. Es más prudente, pero con una tarifa casi monótona queda poca variación para estimar.

Cómo leer la tabla: `elasticidad` es el coeficiente; `error_std_HAC` es su error corregido por autocorrelación; `ic95_inf` e `ic95_sup` son el intervalo al 95% (si contiene el cero, no se distingue de "sin efecto"); `R2` es qué parte de la variación explica el modelo (no mide si el efecto es real).

| Modo | Sin tendencia | Con tendencia |
|---|---|---|
| Colectivo nacional | −0,080 (−0,105 a −0,056) | +0,097 (0,043 a 0,150) |
| Colectivo provincial (desde feb-2024) | −0,182 | −0,260 |
| Tren | −0,058 | +0,031 (−0,005 a 0,067) |
| Subte | −0,154 | −0,087 (−0,184 a 0,011) |

**Lectura:** el signo del colectivo nacional y del tren se invierte al agregar la tendencia. Eso significa que la regresión de niveles no identifica el efecto del precio: sin tendencia captura la caída general; con tendencia captura ruido. No se usa como resultado principal.

### B. Diferencias interanuales (`tabla_elasticidad_interanual.csv`)

Para cada semana se resta el valor de la misma semana un año antes, tanto en demanda como en tarifa. Así desaparecen la estacionalidad y el nivel. La elasticidad es cómo cambia la variación interanual de la demanda cuando cambia la variación interanual de la tarifa.

Un ejemplo de lectura: subte −0,09 significa que, si la tarifa se duplicó respecto del año anterior (log = 0,69), la demanda interanual baja en promedio alrededor de 6% más.

| Modo | Elasticidad | Intervalo 95% |
|---|---|---|
| Colectivo nacional | +0,063 | 0,014 a 0,112 |
| Colectivo provincial | −0,286 | −0,429 a −0,144 |
| Tren | +0,014 | −0,031 a 0,059 |
| Subte | −0,092 | −0,164 a −0,020 |

**Lectura:** el colectivo nacional y el tren quedan en cero o levemente positivos, el subte levemente negativo. Limitación: sigue habiendo una deriva macroeconómica común (caída del ingreso real) que no está en el modelo y que puede confundirse con el precio.

### C. Estudio de eventos (`tabla_estudio_eventos.csv`, `fig14_estudio_eventos.png`)

Para cada salto tarifario se mide cuánto cambió la demanda de días hábiles normales (sin feriado, paro ni elección) entre 6 semanas antes y 6 semanas después, y se resta el mismo cambio un año antes (el año anterior hace de "qué habría pasado sin el aumento"). La elasticidad de arco es el cambio en log de la demanda dividido por el cambio en log de la tarifa. El placebo repite el cálculo en fechas sin cambio de precio para ver cuánto "efecto" aparece por azar (`tabla_placebo_eventos.csv`, banda de −0,05 a +0,08 en log).

Resultados principales (cambio neto de la demanda):

- Colectivo nacional, ene–feb 2024 (tarifa ×3,9): −13% (elasticidad −0,10).
- Colectivo nacional, ago 2024 (×1,32): −1% (dentro del ruido). Feb 2026 (×1,38): +9% (confunde otras cosas).
- Subte: −9% (may-2023), −21,5% (ene–feb 2024; ver 3), −18% (may-2024, tarifa ×4,2), −10% (oct-2024).
- Tren: +1% (ene–feb 2024, tarifa ×3,2) y −15% (may-2024, ×1,34): inconsistentes entre sí.
- Colectivo provincial, mar-2025: +17,6% con un alza de precio, que no se interpreta.

### Qué se puede afirmar y qué no

Se puede afirmar que la demanda respondió poco al precio en el colectivo y el tren, y más en el subte. No se puede afirmar un efecto causal: faltan el ingreso, la inflación y las tarifas de los otros modos. La tarifa deflactada por IPC es el siguiente paso.

## 2. Subte: dos hallazgos de datos — 1-nov-2026

**Línea D cerrada del 8-ene-2024 al 6-mar-2024** (59 días con 0 a 7 usos; 33 de ellos sin registro). La línea D mueve cerca de 22% de la demanda del subte, así que el resultado del evento de ene–feb 2024 (−21,5%, elasticidad −0,83) mide el cierre y no el precio. Quitando la línea D de la serie del subte el efecto baja a −6,1% (elasticidad −0,22). Los demás eventos del subte casi no cambian (−7,2%, −19,4%, −10,4%). Corrección pendiente en el modelo: usar el subte sin la línea D o excluir esas semanas.

**Diferencia con CEPA desde 2025:** el tren coincide con CEPA entre 1% y 3% en todos los meses revisados; el subte coincide hasta 2024 (1,5% a 3%) y desde 2025 queda 18% a 30% por debajo (julio de 2025: 13,0 M contra 18,4 M; febrero de 2026: 8,0 M contra 11,7 M). Se revisó la serie por línea: no desaparece ninguna línea ni hay registros faltantes en 2025 que lo expliquen (todas las líneas bajan parejas). Es probable que sea una diferencia de definición (CEPA usa datos de la concesionaria, que pueden incluir viajes sin SUBE) y no un error del archivo. No se resolvió: la serie de SUBE sigue siendo la fuente del modelo y la diferencia queda documentada como limitación.

Las **tarifas** del subte no dependen de esto: salen de las resoluciones del Boletín Oficial.

## 3. Hipótesis complementaria H-ingreso (pre-registro) — 1-nov-2026

Se escribe antes de mirar ningún resultado por línea, para que no se pueda ajustar a lo que salga.

**Hipótesis (propuesta por Germán):** las líneas de subte que sirven a zonas de mayor poder adquisitivo se ven menos afectadas por los saltos tarifarios que las que sirven a zonas de ingresos medios o bajos.

**Por qué no se saca la línea D:** la línea D (Palermo, Recoleta, Belgrano) es la única línea de ingresos altos con servicio normal en casi todo el período y es clave para esta comparación. Se excluye solo la línea D entre el 8-ene-2024 y el 6-mar-2024 (cierre por obras), no toda la línea.

**Diseño previsto:**
1. Panel semanal por línea (A, B, C, D, E, H). La tarifa es la misma para todas las líneas, así que cualquier efecto común (inflación, ingreso general, estación, feriados, paros) se absorbe con efectos fijos por semana. Lo que queda identifica la diferencia entre líneas: log(usos línea, semana) = efecto de línea + efecto de semana + δ · log(tarifa) · índice de ingreso de la línea. El coeficiente δ dice cuánto cambia la elasticidad al subir el ingreso de la línea. La hipótesis predice δ > 0 (menos sensibles las de ingreso alto).
2. Estudio de eventos por línea en los saltos del subte (mayo-2023, ene–feb-2024, mayo-2024, oct-2024), con la misma ventana y el mismo placebo del bloque 1.
3. El índice de ingreso por línea se define **antes** de correr nada, a partir de datos oficiales (ingreso per cápita familiar por zona de la Ciudad y ubicación de las estaciones por comuna). La clasificación se muestra y se aprueba antes de usarla. Se probará también con un índice alternativo (por ejemplo, ingreso medio de las comunas donde la línea tiene estaciones, ponderado por usos de cada estación si hay datos) para que el resultado no dependa de una sola definición.
4. Una sola comparación está planteada de antemano (ingreso alto contra ingreso bajo). No se recorren las seis líneas buscando diferencias.

**Límites que se declaran de antemano:**
- Es el ingreso de la zona de la línea, no el de sus pasajeros: muchos pasajeros viven en el conurbano y usan las líneas que llegan a las terminales (Constitución, Retiro, Once). Es una falacia ecológica posible.
- Hay solo seis líneas y cuatro saltos: pocos puntos, intervalos amplios.
- Las líneas tienen choques propios (cierre de la D, obras, extensiones de la E y la H). Se controla con efectos fijos y tendencias por línea, y se muestra con y sin ellas.
- La elasticidad por línea mide la respuesta de los usuarios de esa línea al precio, no la de los usuarios que cambiaron de modo. No se interpreta como sustitución.

## 4. Segunda corrida: tarifa real (IPC) y subte sin línea D — 1-nov-2026

Cambios respecto del bloque 1: (a) todos los métodos se repiten con la tarifa deflactada por el IPC nacional de INDEC (`data/externos/ipc_nacional_indec.csv`; el IPC de septiembre de 2026 todavía no estaba publicado en la API y se prolongó con la variación de agosto); (b) el subte se modela sin la línea D (`scripts/usos_por_linea.py`), que además queda disponible por línea para la hipótesis H-ingreso. Tablas actualizadas: las mismas del bloque 1, con una columna `precio` (nominal o real).

### Qué cambió al usar la tarifa real

Con la tarifa nominal, una tarifa que solo sube se confunde con cualquier tendencia. Con la real (la tarifa dividida por el nivel de precios) el precio sube y baja: sube en los saltos y cae entre saltos por la inflación. Eso da variación propia para estimar el efecto.

**A. Niveles semanales, con tendencia (la lectura prudente):**

| Modo | Nominal | Real | Intervalo 95% real |
|---|---|---|---|
| Colectivo nacional | +0,097 | −0,016 | −0,150 a +0,118 |
| Colectivo provincial | −0,260 | −0,256 | −0,361 a −0,152 |
| Tren | +0,031 | −0,037 | −0,103 a +0,030 |
| Subte (sin D) | −0,091 | **−0,255** | −0,317 a −0,192 |

**B. Diferencias interanuales, tarifa real:** colectivo nacional −0,012; colectivo provincial −0,268; tren −0,043; subte −0,224 (intervalo −0,275 a −0,173).

**Lectura:** con la tarifa real el signo ya no se invierte con la tendencia en el subte ni en el colectivo provincial. El subte da −0,26 en niveles con tendencia y −0,22 en diferencias interanuales: dos métodos con supuestos distintos coinciden en que una suba de 10% de la tarifa real se asocia con una baja de alrededor de 2,5% en la demanda del subte. El colectivo nacional y el tren quedan cerca de cero y con intervalos que contienen el cero. El colectivo provincial da −0,26 pero solo cubre desde febrero de 2024 (138 semanas) y sus eventos individuales no son confiables.

### C. Estudio de eventos, subte sin D

Los eventos del subte dan caídas netas de −7% (may-2023), −6% (ene–feb 2024, ahora sin el cierre de la D), −19% (may-2024, tarifa ×4,2) y −10% (oct-2024). La elasticidad de arco con tarifa real es inestable cuando el cambio real de precio es casi cero (ene–feb 2024: tarifa real +4%, elasticidad −1,6, que no tiene interpretación). Se reportan, pero no se promedian.

### Qué se puede afirmar

El subte reacciona al precio (elasticidad cerca de −0,25 a −0,22 en dos métodos) y el colectivo nacional y el tren no se distinguen de cero. Sigue sin ser un efecto causal: queda sin controlar el ingreso real y las tarifas de los otros modos. Para el subte, además, las diferencias entre líneas (H-ingreso) deberían decir si esa reacción promedio esconde grupos muy distintos.

### Observación descriptiva (no es la prueba de H-ingreso)

La participación de la línea D en el subte fue de 21% a 23% en 2022–2023 y de 18% a 20% desde 2024. La caída empieza en el primer trimestre de 2024, que incluye el cierre, y no se recupera. No se interpreta como respuesta al precio: puede ser el cierre, obras posteriores o un cambio en las rutas de los pasajeros.

## 5. Clasificación de líneas por ingreso (antes de correr el panel) — 1-nov-2026

Se ubicó cada estación en su comuna (puntos de las estaciones y polígonos de comunas de BA Data) y cada comuna en la zona del IDECBA (Norte: 2, 13, 14; Centro: 1, 3, 5, 6, 7, 11, 12, 15; Sur: 4, 8, 9, 10). Índice = ingreso per cápita familiar medio de la zona (2.º trimestre de 2024: Norte $805.736, Centro $548.042, Sur $377.273), promediado entre las estaciones de la línea. Tabla: `resultados/tablas/tabla_lineas_subte_ingreso.csv`.

| Línea | Estaciones | Norte / Centro / Sur | Índice |
|---|---|---|---|
| D | 16 | 75% / 25% / 0% | $741.312 |
| H | 12 | 33% / 33% / 33% | $577.017 |
| A, B, C, E | 18, 17, 9, 18 | 0% / 100% / 0% | $548.042 |

**Limitación detectada antes de usar el índice:** con zonas, cuatro de las seis líneas empatan (todas atraviesan solo la zona Centro). La comparación de H-ingreso quedaría reducida a la línea D contra el resto, con la H en el medio. No distingue, por ejemplo, Caballito y Almagro de Flores y Balvanera. Se necesita ingreso por comuna para separar las líneas del Centro. No se miró ningún resultado por línea al armar esta clasificación.

### 5.1 Índice por comuna (EAH del IDECBA) — 1-nov-2026

Con la tabla de ingreso per cápita familiar por comuna (`data/externos/MT_eah_2417.xlsx`, una hoja por año, 2019 a 2025; en 2020 solo hay total de la Ciudad) se reemplaza la zona por la comuna. El ingreso se expresa **relativo al total de la Ciudad de cada año** (los valores están en pesos corrientes y no se pueden comparar entre años), y el índice principal es su promedio entre 2022 y 2025. El orden de las comunas es estable: la 14, la 13 y la 2 son las más ricas (1,41, 1,29 y 1,29) y la 8, la 4 y la 9 las más pobres (0,48, 0,66 y 0,73) en todos los años. Tabla: `resultados/tablas/tabla_comunas_ingreso_relativo.csv`.

Índice de cada línea (promedio de sus estaciones, sin ponderar por usos):

| Línea | Índice 2022–2025 | Índice 2019–2025 | Rango de comunas de sus estaciones |
|---|---|---|---|
| D | **1,235** | 1,253 | 0,84 a 1,41 |
| B | 0,961 | 0,958 | 0,84 a 1,08 |
| A | 0,940 | 0,941 | 0,82 a 1,16 |
| H | 0,930 | 0,926 | 0,66 a 1,29 |
| C | 0,898 | 0,927 | 0,90 |
| E | 0,885 | 0,891 | 0,82 a 1,16 |

**Lectura:** la línea D es claramente la de mayor ingreso (cerca de 30% por encima de las demás). Las otras cinco quedan juntas (0,89 a 0,96, una diferencia de 8%), con orden estable entre los dos promedios salvo la C. La prueba tiene poder para una sola comparación: la D contra el resto. Dentro del resto, el gradiente es demasiado chico para sostener un contraste por línea, y la H mezcla comunas muy distintas (0,66 a 1,29), así que no se le asigna un grupo.

**Comparación pre-registrada para el panel:** (1) principal: índice continuo de la línea (2022–2025) interactuado con la tarifa real; (2) contraste simple: línea D contra el promedio de A, B, C y E (la H queda afuera). Se corren ambas. Todavía no se miró ningún resultado por línea.

## 6. H-ingreso: panel por línea y eventos por línea — 1-nov-2026

Script: `scripts/panel_subte_lineas.py`. Tablas: `tabla_panel_subte_delta.csv`, `tabla_eventos_subte_por_linea.csv`. Figura: `fig15_eventos_subte_por_linea.png`. Diseño y límites: bloques 3, 5 y 5.1.

### Cómo se lee el panel

`delta` multiplica el índice de ingreso de la línea por la tarifa real. La elasticidad de una línea es la del subte entero más `delta` por su índice (centrado). **La hipótesis predice `delta` positivo** (las líneas de ingreso alto, con índice mayor, reaccionan menos: elasticidad más cercana a cero). Un `delta` negativo va en sentido contrario.

| Línea D excluida hasta | Especificación | Tendencia por línea | delta | p de permutación |
|---|---|---|---|---|
| 10-mar-2024 | índice continuo | no | −0,49 | 0,015 |
| 10-mar-2024 | índice continuo | sí | −0,05 | 0,54 |
| 10-mar-2024 | D contra A, B, C, E | no | −0,12 | 0,20 (mínimo posible) |
| 10-mar-2024 | D contra A, B, C, E | sí | −0,005 | 0,80 |
| 30-abr-2024 | índice continuo | no | −0,58 | 0,015 |
| 30-abr-2024 | índice continuo | sí | −0,23 | 0,026 |
| 30-abr-2024 | D contra A, B, C, E | no / sí | −0,15 / −0,06 | 0,20 / 0,20 |

El p de permutación reparte los índices entre las líneas de todas las formas posibles (720 para el índice continuo; solo 5 para D contra el resto, por lo que el p no puede bajar de 0,20: ese contraste no tiene poder estadístico con seis líneas).

### Lectura

- **El signo es negativo o nulo, nunca positivo.** Ninguna especificación respalda la hipótesis. Cuando `delta` es significativo (−0,49 y −0,58 sin tendencia, −0,23 con tendencia y cierre ampliado), apunta en sentido opuesto: la línea de mayor ingreso (D) pierde más demanda a medida que sube la tarifa real.
- **Es muy sensible a cómo se trata la línea D alrededor de su reapertura.** Con tendencia propia por línea y cierre hasta el 10-mar, `delta` es casi cero (−0,05, p = 0,54); al alargar la exclusión hasta el 30-abr pasa a −0,23 (p = 0,026). Eso indica que la recuperación gradual de la D después del cierre (y la caída de su participación de ~22% a ~19% desde 2024) pesa más que el precio. Sin tendencia propia, la deriva de la D se atribuye al precio.
- **Eventos por línea:** la D cae menos que el promedio de A, B, C, E y H en mayo-2024 (−15% contra −19%) y oct-2024 (−7% contra −10%), pero cae más en mayo-2023 (−16,5% contra −8%) y no se puede medir en ene–feb 2024 (cerrada). Dos de tres sentidos a favor, el más grande en contra: no hay patrón.
- **Las otras líneas no siguen el orden de ingreso:** en mayo-2024 la A (ingreso medio) cae −27% y la E (la de menor ingreso) −13%.

### Qué se puede afirmar

No hay evidencia a favor de H-ingreso con estos datos, y tampoco se la puede descartar: el contraste D contra el resto no tiene poder (una sola línea de ingreso alto, un cierre justo en el medio) y la unidad de análisis es el ingreso de la comuna de la estación, no el de los pasajeros. Sería necesario otro tipo de dato (por ejemplo, viajes por tarjeta o por estación de origen) para ponerla a prueba de verdad. Resultado a conservar tal cual: la hipótesis no queda respaldada.

## 7. Efecto cruzado entre modos y Granger — 1-nov-2026

Script: `scripts/efectos_cruzados_granger.py`. Tablas: `tabla_efecto_cruzado_interanual.csv`, `tabla_efecto_cruzado_eventos.csv`, `tabla_estacionariedad_granger.csv`, `tabla_granger_precio_demanda.csv`. Modos: colectivo nacional, tren y subte (sin línea D). El colectivo provincial queda afuera porque su tarifa se conoce solo desde febrero de 2024.

### Qué se busca

Efecto cruzado: si cuando sube la tarifa de un modo la demanda de otro sube (sustitutos) o baja (complementarios). Granger: si el pasado de la tarifa ayuda a predecir la demanda futura más allá del pasado de la propia demanda. Granger no prueba causalidad: es una condición de precedencia temporal, y las tarifas se anuncian con anticipación y comparten shocks (inflación).

### 1. Diferencias interanuales con las tres tarifas reales a la vez

| Demanda de | Tarifa propia | Tarifa de tren | Tarifa de colectivo | Tarifa de subte |
|---|---|---|---|---|
| Colectivo nacional | −0,11 | +0,16 | (propia) | −0,10 |
| Tren | +0,22 | (propia) | −0,21 | −0,13 |
| Subte | −0,26 | +0,06 (no signif.) | +0,02 (no signif.) | (propia) |

VIF entre 2,4 y 6,9: las tarifas del colectivo y del tren se mueven juntas (VIF 4,4 y 6,9). **El coeficiente propio del tren da positivo (+0,22), lo que no tiene interpretación económica: es la señal de que, con tarifas tan correlacionadas, los coeficientes no se separan.** Solo el subte da una estimación estable y negativa (−0,26, igual que en el bloque 4) y sin efectos cruzados significativos.

### 2. Eventos: demanda de los otros modos ante un salto

Solo hay cuatro casos "limpios" (la tarifa nominal del modo observado no cambió en la ventana): el colectivo nacional en feb-2026 con el tren (−2,5%), el subte en oct-2024 con el colectivo (+0,4%), el tren en mayo-2026 con el subte (+5,4%) y el tren en ago-2026 con el subte (−0,1%). Ninguno muestra sustitución sistemática (todos entre −2,5% y +5,4%, dentro del ruido). En los casos no limpios (por ejemplo, el subte con el colectivo en ene–feb 2024) los modos cambiaron de precio al mismo tiempo y no se pueden separar.

### 3. Granger

Las series se llevan a estacionariedad (primera diferencia del log de la demanda sin feriados, paros, elecciones y mes; primera diferencia del log de la tarifa real). ADF + KPSS (tabla de la clase) da estacionaria en las seis series (KPSS del tren 0,06, en el límite). Rezago por AIC (3 a 5 semanas). Corrección de Holm por las nueve pruebas de cada sentido.

| Sentido | Resultado |
|---|---|
| Tarifa → demanda, subte (propia) | p = 0,002 (Holm 0,019): **significativo**, rezago 4 semanas |
| Tarifa → demanda, tren (propia) | p = 0,018 (Holm 0,14): no sobrevive la corrección |
| Tarifa del colectivo → demanda del tren | p = 0,026 (Holm 0,18): no sobrevive la corrección |
| Resto de las pruebas cruzadas y el colectivo | p entre 0,18 y 0,99, sin señal |
| Demanda → tarifa (control) | ninguna significativa tras Holm; la más cercana (subte propia) p = 0,046, Holm 0,42 |

**Lectura:** el pasado de la tarifa predice la demanda del subte (y solo esa) una vez corregido por pruebas múltiples, coherente con las elasticidades de los bloques 1 y 4. No hay evidencia de efectos cruzados ni de que la demanda anticipe o determine la tarifa (la política tarifaria no parece responder a la demanda semanal). La poca señal en el colectivo y el tren es coherente con elasticidades cercanas a cero, pero también con poca potencia: son pocos saltos y se mueven juntos.

### Qué se puede afirmar

Hay evidencia de que la tarifa precede y predice la demanda del subte; no la hay para el colectivo nacional ni el tren, ni para efectos cruzados. No se afirma causalidad: falta ingreso, y el Granger solo cuenta como un chequeo de precedencia. Los coeficientes cruzados del bloque 1 no son interpretables por colinealidad.

## 8. Hitos de calendario: paros, elecciones, feriados y pandemia — 1-nov-2026

Script: `scripts/hitos_efectos.py`. Tablas: `tabla_hitos_cociente_dias.csv` (un renglón por día), `tabla_hitos_resumen.csv`, `tabla_covid_descriptivo.csv`. Figuras: `fig16_covid_descriptivo.png`, `fig17_hitos_cociente.png`.

### Qué se mide

Para cada día de paro, elección o feriado, el cociente entre lo observado y lo esperable: la mediana del mismo día de la semana en las cuatro semanas anteriores y las cuatro posteriores, sin contar feriados ni hitos. Un cociente de 0,5 es la mitad de lo habitual. Para saber qué es ruido se calcula el mismo cociente en 1.112 días laborables ordinarios: el 95% queda entre **0,78 y 1,13** (colectivo), 0,78 y 1,11 (tren) y 0,83 y 1,14 (subte). Un hito se toma como efecto solo si cae fuera de esa banda.

### Resultados

- **Feriados en día laborable (76 días):** la demanda baja a cerca de un tercio de un día normal (mediana 0,36 en colectivo, 0,28 en tren y 0,31 en subte), el 100% fuera de la banda. Es un comportamiento similar al de un domingo. Los feriados que caen en fin de semana casi no cambian nada (mediana 0,84 a 0,96).
- **Elecciones:** con transporte gratuito (PASO y generales de 2023 y balotaje) la demanda se desploma a 0,00 a 0,13 en todos los modos. Sin gratuidad (2025) queda en 0,54 a 1,07: el 18-may-2025 no cambia nada (0,96, 0,91 y 1,07); el 7-sep y el 26-oct-2025 son domingos electorales con caída de colectivo y tren (0,54 a 0,71) pero no del subte. Los tres domingos de 2025 no tienen gratuidad confirmada; la caída es un domingo electoral normal.
- **Paros:** los paros de la UTA hunden el colectivo a 0,06 a 0,20 (7-jul-2023, 11-abr-2024, 9-may-2024, 6-may-2025 y 19-feb-2026); los de La Fraternidad hunden el tren a 0,00; los del subte, el subte a 0,00. **Los modos que no paran no absorben a los que sí**: en los paros de colectivo, el tren queda en 0,66 a 0,79 (no sube) y el subte en 1,0; cuando para el tren, el colectivo queda en 1,0 o 0,75 (no sube). El efecto es de oferta cortada, no de sustitución.
- **Pandemia (solo descripción):** semana mínima del 29-mar-2020, con la demanda de días hábiles en 12% (colectivo), 4% (tren) y 2% (subte) del verano de 2020. En diciembre de 2020: 57%, 37% y 17%. En diciembre de 2021: 97%, 75% y 65%. El subte y el tren se recuperaron más lento que el colectivo. No es una medida de recuperación: el período de referencia son dos meses de verano.

### Qué se puede afirmar

Los feriados laborables y los paros propios del modo son los efectos más grandes y claros del calendario (bajan la demanda entre 65% y 100%), con una magnitud que supera con creces el ruido. La gratuidad electoral es el caso extremo: demanda casi nula. Los paros de un modo no trasladan viajeros a los otros. Esto ordena los eventos que se excluyen o se controlan en el resto de los modelos (días de paro y de elección fuera de las ventanas, dummies de feriado).

## 9. Control sintético para los saltos del colectivo — 1-nov-2026

Script: `scripts/control_sintetico.py`. Tablas: `tabla_control_sintetico.csv`, `tabla_control_sintetico_donantes.csv`. Figura: `fig18_control_sintetico.png`.

### Qué se hizo

Se estima qué habría pasado con la demanda de colectivo del AMBA sin el aumento con una combinación de 30 ciudades del interior (también en SUBE, con al menos 3.000 usos diarios y datos casi completos), con pesos no negativos que suman 1, elegidos para replicar la demanda del AMBA en las 52 semanas previas. La brecha entre el AMBA real y el sintético, promediada entre la segunda y la octava semana posterior, es el efecto estimado. La inferencia es por placebos en el espacio: se repite el procedimiento tratando como tratada a cada ciudad donante y se compara.

### Resultados

| Salto | Brecha estimada | Rango de placebos (p5 a p95) | p de placebos |
|---|---|---|---|
| Ene–feb 2024 (tarifa ×5) | −2,8% | −20% a +23% | 0,43 |
| Ago 2024 (+37%) | −2,5% | −9% a +13% | 0,27 |
| Feb 2026 (+31%) | −1,5% | −18% a +13% | 0,27 |

### Lectura

Ninguno de los tres efectos se distingue de lo que producen las ciudades donantes sin tratamiento. El ajuste previo es mediano (error de 3%) y empeora después del aumento (7% en 2024), pero los placebos muestran que ese tamaño de brecha aparece sin tratamiento. **El control sintético no confirma la caída de 13% del estudio de eventos del bloque 1 (colectivo nacional, ene–feb 2024):** da −3% y sin significancia. Los dos métodos coinciden en que no hay un efecto grande y claro del precio en el colectivo; no se pueden reconciliar en una cifra.

### Límites que pesan

- Las ciudades del interior fijan sus propias tarifas y las ajustan seguido; si subieron en la misma ventana (enero-febrero de 2024 fue un período de aumentos generalizados), el efecto se subestima. No se verificó la tarifa de cada donante.
- Varias donantes con mucho peso son ciudades turísticas (General Pueyrredón, Bariloche), cuya estacionalidad de verano difiere de la del AMBA justo en la ventana de 2024.
- La ventana de 2024 es la más contaminada por otros cambios (devaluación de diciembre de 2023, inflación mensual de 20% a 25%).
- Para el tren y el subte no hay donantes: el método solo se pudo aplicar al colectivo.

## 10. Síntesis de P-1: respuesta de la demanda a los hitos — 1-nov-2026

Esta es la lectura conjunta de los bloques 1 a 9. Se redacta antes de armar la presentación, para evaluar al final si se sostuvo.

| Pregunta | Resultado | Confianza |
|---|---|---|
| ¿Reacciona la demanda al precio? | **Subte:** sí, elasticidad de −0,22 a −0,26 con tarifa real (dos métodos), y Granger lo respalda (p de Holm 0,019). **Colectivo nacional y tren:** cerca de cero, no se distinguen de cero. | Subte: media. Colectivo y tren: baja (poco poder: pocos saltos que se mueven juntos) |
| ¿Cuánto cayó con los saltos grandes? | Colectivo nacional ene–feb 2024: −13% (eventos) contra −3% sin significancia (control sintético). Subte may-2024 (tarifa ×4): −19%. Tren: inconsistente (+1% y −15%). | Baja a media |
| ¿Hay sustitución entre modos? | No: los casos limpios muestran cambios dentro del ruido; en paros los modos que no paran no absorben a los que sí. | Media (pocos casos limpios) |
| ¿Las líneas de más ingreso reaccionan menos? | No hay respaldo: signo contrario o nulo según la especificación; la prueba solo compara D con el resto. | Baja (poder bajo) |
| ¿Cómo se comporta la demanda en los hitos del calendario? | Feriados laborables: ~0,3 de un día normal. Paros propios del modo: 0,0 a 0,2. Elecciones con gratuidad: ~0. Pandemia: mínimo de 2% a 12% del verano de 2020; a fines de 2021, 97% (colectivo), 75% (tren) y 65% (subte). | Alta |

**Mensaje para la presentación:** el precio importa para el subte y casi nada para el colectivo y el tren en los saltos observados, pero eso no es un efecto causal limpio: queda sin controlar el ingreso y el período es de inflación alta. Los hitos de calendario son los efectos más claros y estables. Para el video se muestra primero lo que se sostiene (calendario, subte) y después lo inestable (saltos del colectivo), con los límites a la vista.
