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
