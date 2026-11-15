# Guion del video: secciones 1 a 7 (parte de Germán)

**Base:** `docs/Informe_final.md`. Cada cifra sale de ahí (la sección entre paréntesis es donde está el respaldo y la figura).
**Duración estimada:** 9 minutos, a unas 140 palabras por minuto (el video completo es de unos 15). Es un supuesto: si Augusto necesita más de 6 minutos para las secciones 8 a 10, se recorta la sección 7 o la 4.
**Cómo usarlo:** el texto en tipografía normal es lo que se dice; `[Pantalla: …]` indica qué mostrar. Está escrito para hablarse, con frases cortas. Las cifras son las del informe; si se cambia alguna, hay que cambiarla acá.

| Tramo | Sección | Tiempo | Acumulado |
|---|---|---|---|
| 1 | 1 y 2: motivación y preguntas | 1:00 | 1:00 |
| 2 | 3: datos | 1:00 | 2:00 |
| 3 | 4: exploración | 2:30 | 4:30 |
| 4 | 5: interpolación | 1:15 | 5:45 |
| 5 | 6: CCF | 0:45 | 6:30 |
| 6 | 7: P-1 | 2:30 | 9:00 |

---

## Tramo 1 · Secciones 1 y 2: motivación y preguntas (1:00)

`[Pantalla: portada con el título y la figura 1, series por modo]`

Buenas. Les cuento la primera parte del trabajo: de la introducción hasta la pregunta P-1.

Estudiamos la demanda diaria de transporte público en el AMBA, entre 2020 y 2026, con datos de la tarjeta SUBE: colectivo, tren y subte. En ese período hubo una pandemia, una secuencia de aumentos de tarifa y, en el medio, paros, elecciones y feriados que alteran un día cualquiera.

Nos hicimos dos preguntas distintas, que piden herramientas distintas. La primera, P-1: cuando algo cambia, el precio o el calendario, ¿cuánto se mueve la demanda y podemos atribuirlo a esa causa? Eso exige un contrafactual: qué habría pasado sin el cambio. La segunda, P-2, que cuenta Augusto: qué método pronostica mejor. Para pronosticar alcanza con acertar; para entender hay que aislar un efecto.

---

## Tramo 2 · Sección 3: datos (1:00)

`[Pantalla: tabla de 3.1, usuarios contra transacciones]`

Usamos dos conjuntos del mismo portal de datos abiertos de Transporte. El primero cuenta **usuarios**: tarjetas distintas por día. El segundo cuenta **transacciones**: cada uso de la tarjeta; una tarjeta usada cinco veces suma cinco.

Los usuarios los usamos en la exploración y en el pronóstico. Las transacciones, en P-1, y para reconstruir los días faltantes: la serie de usuarios no tiene 62 días, agosto de 2022 y enero de 2024.

Un aviso importante: ninguna de las dos medidas es una cantidad de personas ni de viajes completos. Cuando digo que "baja la demanda", quiero decir menos tarjetas distintas o menos transacciones. Las dos medidas se mueven casi igual: la correlación de sus logaritmos diarios es de 0,995 para el total.

---

## Tramo 3 · Sección 4: exploración (2:30)

`[Pantalla: figuras 1 y 2, ciclos semanal y anual]`

Antes de modelar, conocemos la serie. Primero, el nivel y los ciclos. Hay un **ciclo semanal** muy marcado: un día hábil ronda los 3,7 a 3,9 millones de usuarios, un sábado 2,4 y un domingo 1,4. Y hay un **ciclo anual**, con valles en las vacaciones de verano y de invierno. Por eso trabajamos con datos desde enero de 2022: 2020 y 2021 son la pandemia y se estudian aparte.

`[Pantalla: figura 2, paneles inferiores de ACF y PACF]`

Para leer la memoria de la serie usamos la **ACF** y la **PACF**: la correlación de la serie con ella misma días antes, total y descontando los rezagos intermedios. Los picos en el rezago 7 y sus múltiplos confirman el ciclo semanal.

`[Pantalla: figura 3, tres versiones de la serie]`

Segundo, la **estacionariedad**, con las pruebas ADF y KPSS de la clase de Forecasting. Con la pandemia, el nivel no es estacionario; desde 2022 sí lo es. Y comprobamos que alcanza con **una** diferencia estacional de 7 días: agregar la diferencia simple **sobrediferencia**. Sube el desvío de 0,76 a 0,95 millones y aparece una autocorrelación negativa artificial. Por eso el modelo de P-2 usa d igual a 0 y D igual a 1.

`[Pantalla: figura 7, espectro de la FFT]`

Tercero, el **análisis espectral**. Con la FFT, el ciclo de 7 días y sus dos armónicos explican el **62,5%** de toda la variación de la serie. Los ciclos lentos, el anual y la tendencia, apenas el 10%.

`[Pantalla: figura 6, residuo de STL en los hitos]`

Cuarto, la **descomposición STL**. Lo informativo es el residuo, lo que queda cuando se saca tendencia y estacionalidad. Con un umbral de ±20% del valor esperado, el residuo marca 74 de los 77 feriados laborables, 7 de los 9 paros y 5 de las 6 elecciones. O sea: sirve para detectar días atípicos.

`[Pantalla: figura 11, comparación de tendencias]`

Por último, comparamos medias móviles y filtros en frecuencia contra STL. La media móvil centrada de 28 días se parece mucho a la tendencia de STL, pero en los bordes pierde datos, y el filtro que elimina la banda del ciclo semanal produce valores negativos de demanda al desestacionalizar, que no tienen sentido. Nos quedamos con STL.

---

## Tramo 4 · Sección 5: interpolación (1:15)

`[Pantalla: figura 12, el hueco y el error de cada método]`

Con eso en mano, volvemos a los 62 días faltantes. Evaluamos los métodos de interpolación sacando 89 bloques de 31 días de la serie conocida y midiendo cuánto se equivocaba cada uno. El **spline** que se usaba al comienzo tenía un error mediano de 76%, inaceptable porque oscila en huecos largos, y el mejor, el **PCHIP** multiplicado por el perfil semanal, bajó a 17%. Un dato de honestidad: PCHIP no se vio en clase; es de Fritsch y Carlson, 1980. Lo usamos porque no oscila.

`[Pantalla: figura 14, reconstrucción desde transacciones frente a interpolación]`

Pero el método elegido no es una interpolación pura. Como el mismo portal publica las transacciones sin huecos, estimamos los usuarios de cada día faltante como **transacciones del día por el cociente usuarios sobre transacciones**, interpolado entre los bordes del hueco. En los meses de vacaciones el error es de 1,6 a 3,2%. Cuando existe una fuente así, es muy superior a cualquier interpolación.

---

## Tramo 5 · Sección 6: correlación cruzada (0:45)

`[Pantalla: figuras 15 y 16, CCF tren-colectivo]`

Antes de P-1 miramos cómo se relacionan los modos. La **correlación cruzada** entre tren y colectivo, sobre los residuos sin calendario, da **0,85 el mismo día**, muy por encima de la banda de significancia, que corregida por autocorrelación es de ±0,13. Es estable en tres subperíodos, entre 0,78 y 0,88.

La conclusión: los modos se mueven juntos el mismo día, por causas comunes. Un modo no anticipa a otro ni lo reemplaza. Dos consecuencias: se puede pronosticar cada modo por separado, y es coherente con lo que vamos a ver en los paros.

---

## Tramo 6 · Sección 7: P-1, hitos, precio y causalidad (2:30)

`[Pantalla: figura 17, tarifas reales y como porcentaje del salario]`

Entramos en P-1. Primero, **precio**. Usamos las tarifas en términos reales y, como robustez, en proporción al salario. Los saltos grandes fueron tres, todos en 2024.

`[Pantalla: figuras 18 y 19, saltos tarifarios y estudio de eventos]`

Medimos la **elasticidad precio**: cuánto cambia la demanda, en porcentaje, ante un cambio de un uno por ciento en la tarifa. Para el **subte** da de menos 0,15 a menos 0,26, según se controle o no por el salario real. Para el **colectivo nacional** y el **tren**, no se distingue de cero. En el estudio de eventos, que compara con el mismo día del año anterior, el subte cae 19% con el salto de mayo de 2024. Con el **control sintético**, que arma un AMBA "sin salto" con ciudades del interior, el colectivo nacional no muestra una caída significativa.

Y acá la lectura es cautelosa. Son pocos saltos, todos en el mismo año, y los dos métodos discrepan para el colectivo. **No es un efecto causal demostrado**: son diseños con supuestos, y la confianza es media para el subte y baja para el resto. Tampoco encontramos sustitución entre modos.

`[Pantalla: figura 22, cociente por tipo de hito]`

Lo contrario pasa con el **calendario**: ahí el efecto es grande y claro. Medimos el cociente de cada día especial contra lo habitual de ese día de la semana. Un **feriado laborable** deja la demanda en cerca de 0,3 de un día normal. Un **paro** del propio modo la deja entre 0 y 0,2. Y una **elección con gratuidad**, cerca de cero; sin gratuidad, entre 0,5 y 1,1. Cada símbolo del gráfico es un tipo de día. Y vale algo importante de los paros: el modo que para cae a casi cero y los demás **no absorben** esa demanda, no hay sustitución: al revés, cuando para el colectivo el tren también cae.

**Cierre.** El precio mueve al subte y casi nada al colectivo y al tren; el calendario mueve la demanda mucho más que cualquier tarifa, y con confianza alta. Con esto le paso la palabra a Augusto, que cuenta cómo pronosticar esta demanda.

---

## Notas para la grabación (no se leen)

- **Lo no visto en clase** y que se dice al pasar: PCHIP (tramo 4); elasticidad, estudio de eventos y control sintético (tramo 6). El informe lo aclara en 5 y 7.
- **Si sobra tiempo:** en el tramo 3, mencionar que el residuo de STL señala también 47 días ordinarios (2,9%) sin explicación comprobada; en el tramo 6, que el paro general del 10/4/2025 dejó al colectivo en 0,62 aunque la UTA no adhirió.
- **Si falta tiempo:** sacar la comparación de filtros del tramo 3 y la robustez por salario del tramo 6.
- **Figuras:** los números de figura son los del informe (`docs/Informe_final.md`); cifras con el corte al 30/9/2026.
