"""
Serie de tarifas (boleto mínimo con SUBE registrada) por modo y jurisdicción, con fuente y estado.

Es la base para estimar el efecto del precio sobre la demanda (P-1): se usan TODOS los cambios
confirmables, grandes y chicos. Cada fila es un cambio de tarifa; entre cambios el valor se mantiene.

Estados de verificación:
  - norma + prensa      : la norma oficial identifica el cambio (fecha); el importe sale de prensa
  - prensa (>=2)        : dos o más medios coinciden
  - una fuente          : un solo medio o el Observatorio
  - conflicto           : las fuentes difieren en el importe o la fecha
  - inferido            : calculado a partir de otros datos (por ejemplo, el valor previo a un % informado)

Los importes salen de prensa porque los anexos oficiales son imágenes o PDF no legibles; las normas
(Boletín Oficial) confirman los cambios, no los montos. `fecha_exacta = False` indica que solo se
conoce el mes.

Salidas:
  data/hitos/serie_tarifas.csv         un cambio por fila
  data/hitos/serie_tarifas_diaria.csv  tarifa vigente por día y serie (solo tramos con valor conocido)
  data/hitos/hitos_tarifas.csv         cambios de la serie, clasificados en salto (>=10%) o ajuste
  resultados/tablas/tabla_tarifas_cobertura.csv
"""

import os
import numpy as np
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HITOS_DIR = os.path.join(BASE_DIR, "data", "hitos")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")
os.makedirs(HITOS_DIR, exist_ok=True)
os.makedirs(TABLA_DIR, exist_ok=True)

NP = 'norma + prensa'
PR = 'prensa (>=2)'
UNA = 'una fuente'
CON = 'conflicto'
INF = 'inferido'
UMBRAL_SALTO = 10.0   # % a partir del cual un cambio se trata como salto discreto
MESES_MAX_ENTRE_VALORES = 1.6   # en régimen de ajuste mensual, más separación implica valores intermedios faltantes

# desde cuándo cada serie se ajusta todos los meses (IPC + 2%): ahí, un salto grande entre dos valores
# separados por varios meses puede ser la suma de ajustes mensuales no relevados
AJUSTE_MENSUAL = {
    'colectivo_caba': [('2025-04-01', '2099-12-31')],
    'colectivo_provincial': [('2025-04-01', '2099-12-31')],
    'subte': [('2025-03-01', '2099-12-31')],
    'colectivo_nacional': [('2023-03-01', '2023-08-31')],
    'tren': [('2023-03-01', '2023-08-31'), ('2026-05-18', '2026-09-30')],
}

# cambios cuyo porcentaje informan directamente las fuentes como un solo paso, aunque falten meses previos
SALTOS_INFORMADOS = {
    ('2024-05-06', 'tren'), ('2024-08-12', 'colectivo_nacional'), ('2024-08-12', 'colectivo_provincial'),
    ('2025-02-21', 'colectivo_caba'), ('2025-03-01', 'colectivo_provincial'), ('2026-02-18', 'colectivo_nacional'),
    ('2026-05-18', 'tren'), ('2024-09-16', 'tren'),
}

OBS = ('https://observatoriociudad.org/informe-sobre-la-evoluci%C3%B3n-de-pasajeros-y-la-tarifa-del-subte-de-la-ciudad-de-buenos-aires-en-la-%C3%BAltima-d%C3%A9cada-2015-2025/')
BO_CABA = 'https://boletinoficial.buenosaires.gob.ar/normativaba/norma/'

# fecha, serie, valor, fecha_exacta, estado, fuentes, nota
SERIE = [
    # --- Colectivo, jurisdicción nacional (líneas AMBA) -------------------------------------------
    ('2023-12-10', 'colectivo_nacional', 52.96, False, PR,
     'https://www.baenegocios.com/sociedad/Suba-de-colectivos-el-boleto-minimo-aumentara-a-76-92-en-el-AMBA-20231228-0077.html',
     'Valor vigente al asumir el gobierno; se desconoce desde cuándo regía (congelado desde la suspensión de la indexación, Res. 501/2023)'),
    ('2024-01-15', 'colectivo_nacional', 76.92, True, NP,
     'https://www.argentina.gob.ar/normativa/nacional/norma-395786/texto | https://www.baenegocios.com/sociedad/Suba-de-colectivos-el-boleto-minimo-aumentara-a-76-92-en-el-AMBA-20231228-0077.html',
     'Res. 8/2023 (MI) rige desde las 0 h del 15-ene-2024; el importe es de prensa (una fuente lo da desde el 1-ene)'),
    ('2024-02-06', 'colectivo_nacional', 270.0, True, NP,
     'https://eleconomista.com.ar/economia/confirmado-martes-aumenta-250-boleto-minimo-colectivo-tren-amba-n70624 | https://normas.gba.gob.ar/ar-b/resolucion/2024/41/414919',
     'Res. 1/2024 (cuadro) y Res. 5/2024 de la Secretaría de Transporte (5-feb-2024); la Provincia adhirió con la Res. 41/2024. Vigencia del 6-feb según prensa'),
    ('2024-08-12', 'colectivo_nacional', 371.13, True, PR,
     'https://chequeado.com/el-explicador/aumentan-un-375-las-tarifas-de-colectivo-en-el-amba-cuanto-cuesta-el-boleto-en-las-principales-ciudades-del-pais/ | https://www.iprofesional.com/economia/410801-desde-el-lunes-12-de-agosto-el-boleto-minimo-de-colectivo-en-amba-costara-370-pesos',
     'Prensa informa $370 y $371,13 (redondeo). Número de resolución sin confirmar. Siguieron ocho meses sin aumentos'),
    ('2025-05-23', 'colectivo_nacional', 397.11, True, PR,
     'https://eleconomista.com.ar/economia/viajar-sera-mas-caro-cuanto-aumentan-colectivos-amba-cuando-aplica-cada-suba-n84976 | https://www.baenegocios.com/sociedad/Aumentan-los-colectivos-del-AMBA-cuanto-costara-el-boleto-minimo-20250617-0007.html',
     'Res. 28/2025: +21,52% en tres tramos'),
    ('2025-06-18', 'colectivo_nacional', 424.91, True, PR,
     'https://www.baenegocios.com/sociedad/Aumentan-los-colectivos-del-AMBA-cuanto-costara-el-boleto-minimo-20250617-0007.html', 'Segundo tramo de la Res. 28/2025'),
    ('2025-07-16', 'colectivo_nacional', 451.01, True, PR,
     'https://www.canal26.com/economia/2025/07/12/aumenta-el-boleto-de-colectivo-en-el-amba-cuanto-costara-el-pasaje-minimo-a-partir-del-16-de-julio/ | https://www.baenegocios.com/sociedad/Mas-caro-cuanto-cuesta-viajar-en-colectivo-en-el-AMBA-20250715-0044.html',
     'Tercer tramo de la Res. 28/2025'),
    ('2025-11-01', 'colectivo_nacional', 494.83, False, UNA,
     'https://www.perfil.com/noticias/sociedad/suben-los-colectivos-nacionales-que-conectan-caba-con-el-gran-buenos-aires.phtml | https://eleconomista.com.ar/economia/aumentan-colectivos-caba-conurbano-cuanto-fue-boleto-minimo-n90584',
     '+9,72% sobre $451 en 104 líneas nacionales; la fecha exacta no se pudo confirmar (otoño-invierno de 2025 a fines de 2025)'),
    ('2026-02-18', 'colectivo_nacional', 650.0, True, PR,
     'https://dolarhoy.com/economia/viajar-en-colectivo-sera-mas-caro-desde-hoy-el-boleto-aumenta-un-31-en-el-amba-20262181450 | https://www.canal26.com/economia/2026/02/17/aumento-de-colectivos-en-el-amba-cuanto-costara-el-boleto-a-partir-de-este-miercoles-18-de-febrero/',
     'Aumento del 31%; el importe sale de las notas de marzo ("de $650 a $700")'),
    ('2026-03-16', 'colectivo_nacional', 700.0, True, PR,
     'https://www.lanacion.com.ar/economia/vuelve-a-aumentar-el-pasaje-de-colectivo-en-el-amba-el-minimo-llegara-a-700-nid16032026/ | https://www.canal26.com/general/2026/03/16/aumento-el-boleto-de-colectivo-en-el-amba-cuanto-cuesta-viajar-desde-este-lunes-16-de-marzo/', '+7,6%'),
    ('2026-05-18', 'colectivo_nacional', 714.0, True, NP,
     'https://www.argentina.gob.ar/normativa/nacional/norma-425863/texto', 'Res. 27/2026 (ST), etapa de mayo, +2%; sanción 15-may-2026, BO 18-may-2026. Importe de prensa'),
    ('2026-06-15', 'colectivo_nacional', 728.28, True, NP,
     'https://www.argentina.gob.ar/normativa/nacional/norma-425863/texto | https://www.ambito.com/economia/aumentan-los-colectivos-y-trenes-el-amba-este-lunes-cuanto-costara-viajar-partir-manana-n6288659', 'Res. 27/2026, etapa de junio (15-jun), +2%'),
    ('2026-07-15', 'colectivo_nacional', 742.81, True, NP,
     'https://www.argentina.gob.ar/normativa/nacional/norma-425863/texto | https://dolarhoy.com/economia/nuevo-aumento-de-colectivos-en-el-amba-tarifas-vigentes-desde-el-15-de-julio-2026715112832', 'Res. 27/2026, etapa de julio (15-jul), +2%. No se encontraron cambios posteriores'),
    # --- Colectivo, líneas de jurisdicción CABA (31 líneas transferidas desde la Nación) ---------
    ('2024-08-12', 'colectivo_caba', 371.13, False, INF,
     'https://www.perfil.com/noticias/informacion-general/quienes-pagan-el-boleto-mas-caro-de-la-argentina.phtml',
     'Las líneas transferidas mantuvieron el valor nacional hasta febrero de 2025 (prensa: "de $371 a $408,24")'),
    ('2025-02-21', 'colectivo_caba', 408.24, True, PR,
     'https://www.baenegocios.com/amp/Aumento-el-boleto-de-colectivo-en-la-Ciudad-de-Buenos-Aires-los-nuevos-precios-desde-hoy-20250221-0010/ | https://www.cronica.com.ar/sociedad/aumentan-los-colectivos-peajes-y-el-subte-en-caba-cuales-son-los-nuevos-montos-20250221-0001.html',
     '+10%. A partir de abril de 2025 se ajusta mensualmente por IPC + 2%. Faltan los valores de marzo a agosto de 2025'),
    ('2025-09-01', 'colectivo_caba', 526.13, False, UNA,
     'https://www.canal26.com/economia/2025/10/16/nuevo-aumento-en-las-tarifas-de-los-colectivos-de-caba-y-pba-desde-cuando-y-a-cuanto-se-ira-el-boleto-minimo-en-noviembre/', ''),
    ('2025-10-01', 'colectivo_caba', 546.54, False, UNA,
     'https://www.canal26.com/economia/2025/10/16/nuevo-aumento-en-las-tarifas-de-los-colectivos-de-caba-y-pba-desde-cuando-y-a-cuanto-se-ira-el-boleto-minimo-en-noviembre/', ''),
    ('2025-11-01', 'colectivo_caba', 568.91, True, PR,
     'https://dolarhoy.com/economia/aumentan-4-1-el-boleto-minimo-en-pba-y-caba-20251016105726 | https://www.canal26.com/economia/2025/10/16/nuevo-aumento-en-las-tarifas-de-los-colectivos-de-caba-y-pba-desde-cuando-y-a-cuanto-se-ira-el-boleto-minimo-en-noviembre/', '+4,1%'),
    ('2025-12-01', 'colectivo_caba', 593.52, True, UNA,
     'https://www.canal26.com/general/2025/11/30/el-fin-de-ano-llega-con-aumentos-uno-por-uno-todos-los-precios-actualizados-de-colectivos-subtes-y-peajes-en-diciembre-2025/', ''),
    ('2026-04-01', 'colectivo_caba', 715.24, True, PR,
     'https://lanacion.com.ar/sociedad/el-boleto-aumento-en-colectivos-y-subte-a-partir-del-hoy-1-de-abril-cuanto-sale-en-caba-y-provincia-nid01042026/ | https://www.canal26.com/economia/2026/04/01/ya-rige-el-aumento-del-pasaje-en-colectivo-y-subte-en-caba-y-pba-cuanto-sale-viajar-en-abril-2026/', 'IPC + 2%. Faltan enero a marzo de 2026'),
    ('2026-06-01', 'colectivo_caba', 788.28, True, PR,
     'https://www.iprofesional.com/impuestos/456075-cuanto-costara-el-boleto-de-subte-y-colectivo-en-caba-y-pba-desde-el-lunes-1-de-junio', 'Desde $753,74; falta el valor de mayo'),
    ('2026-08-01', 'colectivo_caba', 852.90, True, UNA,
     'https://canal26.com/economia/2026/07/23/aumenta-el-transporte-publico-cuanto-costara-el-boleto-de-colectivos-y-subtes-desde-el-1-de-agosto/', '+3,9%; falta el valor de julio'),
    ('2026-09-01', 'colectivo_caba', 887.87, True, PR,
     'https://www.ambito.com/economia/aumenta-el-transporte-septiembre-cuanto-costara-viajar-colectivo-tren-y-subte-manana-n6316386', '+4,1%'),
    # --- Colectivo, líneas provinciales (Provincia de Buenos Aires) ------------------------------
    ('2024-02-06', 'colectivo_provincial', 270.0, True, NP,
     'https://normas.gba.gob.ar/ar-b/resolucion/2024/41/414919', 'La Res. 41/2024 de la Provincia (6-feb-2024) adhiere a la Res. 5/2024 nacional'),
    ('2024-08-12', 'colectivo_provincial', 371.13, False, INF,
     'https://www.baenegocios.com/economia/El-boleto-de-colectivos-en-la-Provincia-de-Buenos-Aires-aumentara-10-en-marzo-20250214-0066.html',
     'Se infiere que acompañó el valor nacional hasta marzo de 2025 (prensa: "de $371,13 a $408,23"); sin resolución provincial confirmada'),
    ('2025-03-01', 'colectivo_provincial', 408.23, True, UNA,
     'https://www.baenegocios.com/economia/El-boleto-de-colectivos-en-la-Provincia-de-Buenos-Aires-aumentara-10-en-marzo-20250214-0066.html', '+10%; alcanza a líneas provinciales que no ingresan a la Ciudad'),
    ('2025-04-01', 'colectivo_provincial', 425.57, True, PR,
     'https://www.canal26.com/economia/aumenta-el-boleto-de-colectivo-en-la-provincia-de-buenos-aires-cuanto-costara-viajar-desde-el-1-de-abril--417612 | https://www.baenegocios.com/sociedad/Aumenta-el-colectivo-en-Buenos-Aires-cuanto-cuesta-el-boleto-minimo-20250331-0010.html', '+4,2%'),
    ('2025-05-01', 'colectivo_provincial', 451.01, True, UNA,
     'https://www.izquierdadiario.es/Un-nuevo-logro-de-bajar-la-inflacion-aumentan-6-los-colectivos-y-subtes-en-mayo', '+5,9%; faltan los valores de junio a octubre de 2025'),
    ('2025-12-01', 'colectivo_provincial', np.nan, True, PR,
     'https://www.izquierdadiario.es/Kicillof-autorizo-un-tarifazo-extraordinario-del-boleto-de-colectivo-aumentara-un-14-8-desde | https://www.cronica.com.ar/politica/Aumenta-el-colectivo-en-provincia-de-Buenos-Aires-Cuanto-costara-20251127-0078.html',
     '+14,8% (IPC + 2% más 10% extraordinario); importe sin confirmar'),
    ('2026-04-01', 'colectivo_provincial', 871.30, True, UNA,
     'https://lanacion.com.ar/sociedad/el-boleto-aumento-en-colectivos-y-subte-a-partir-del-hoy-1-de-abril-cuanto-sale-en-caba-y-provincia-nid01042026/', ''),
    ('2026-06-01', 'colectivo_provincial', 1015.61, True, PR,
     'https://www.iprofesional.com/impuestos/456075-cuanto-costara-el-boleto-de-subte-y-colectivo-en-caba-y-pba-desde-el-lunes-1-de-junio', 'Desde $968,57'),
    ('2026-09-01', 'colectivo_provincial', 1158.97, True, PR,
     'https://www.ambito.com/economia/aumenta-el-transporte-septiembre-cuanto-costara-viajar-colectivo-tren-y-subte-manana-n6316386', 'Falta el detalle de julio y agosto'),
    # --- Tren (jurisdicción nacional) ---------------------------------------------------------------
    ('2024-02-06', 'tren', 130.0, True, NP,
     'https://eleconomista.com.ar/economia/confirmado-martes-aumenta-250-boleto-minimo-colectivo-tren-amba-n70624 | https://www.a24.com/politica/trenes-y-colectivos-el-gobierno-confirmo-que-este-martes-suben-las-tarifas-amba-n1289001/amp',
     'Res. 5/2024 de la Secretaría de Transporte. Tarifa para SUBE nominalizada. Mitre, Sarmiento y San Martín: de $48,38 a $130 (+169%); Roca, Belgrano y Urquiza: de $37,38 (+247%)'),
    ('2024-05-06', 'tren', 200.0, True, CON,
     'https://www.ciudad.com.ar/actualidad/2024/04/22/aumento-en-trenes-cuanto-costara-viajar-en-mayo | https://www.a24.com/economia/aumenta-la-tarifa-los-trenes-cuanto-saldra-el-boleto-partir-mayo-n1313012',
     '+53,85%. Una nota da el 2-may y otra el lunes 6-may: se toma el 6-may (que fue lunes)'),
    ('2024-09-16', 'tren', 280.0, True, PR,
     'https://www.lanacion.com.ar/sociedad/nuevo-aumento-en-los-boletos-de-trenes-en-el-amba-cuanto-suben-y-cual-sera-el-valor-minimo-nid13092024/ | https://www.c5n.com/economia/ya-rige-un-nuevo-aumento-del-boleto-tren-cuanto-cuesta-el-minimo-n173823/amp',
     'Res. 33/2024; +40%. Siguieron ocho meses sin aumentos hasta mayo de 2026'),
    ('2026-05-18', 'tren', 310.0, True, NP,
     'https://www.argentina.gob.ar/normativa/nacional/norma-425863/texto',
     'Res. 27/2026, Anexo II (cuadro de los servicios metropolitanos, sección 1, SUBE nominalizada; igual en todas las líneas): $310. Corrige el $330 de una nota. +10,7% sobre $280'),
    ('2026-06-01', 'tren', 350.0, False, NP,
     'https://www.argentina.gob.ar/normativa/nacional/norma-425863/texto', 'Res. 27/2026, Anexo II: cuadro del mes de junio, sección 1: $350 (+12,9%). Reemplaza la fecha inferida del 15-jun'),
    ('2026-07-01', 'tren', 380.0, False, NP,
     'https://www.argentina.gob.ar/normativa/nacional/norma-425863/texto | https://www.infobae.com/economia/2026/07/01/aumentos-en-colectivos-subte-y-trenes-cuanto-costara-viajar-a-partir-de-julio/', 'Res. 27/2026, Anexo II: cuadro de julio, sección 1: $380 (+8,6%); una nota daba $380,10'),
    ('2026-08-01', 'tren', 420.0, False, NP,
     'https://www.argentina.gob.ar/normativa/nacional/norma-425863/texto', 'Res. 27/2026, Anexo II: cuadro de agosto, sección 1: $420 (+10,5%)'),
    ('2026-09-01', 'tren', 450.0, False, NP,
     'https://www.argentina.gob.ar/normativa/nacional/norma-425863/texto', 'Res. 27/2026, Anexo II: cuadro de septiembre, sección 1: $450 (+7,1%). Corrige $480 y $530 de notas'),
    # --- Subte (CABA) -------------------------------------------------------------------------------
    ('2023-12-01', 'subte', 80.0, False, PR,
     'https://www.baenegocios.com/sociedad/aumentos-del-37-5-en-subte-cuando-sube-y-cuanto-costara-20231227-0052.html', 'Valor previo a la Res. 27/SBASE/23; fecha de inicio anterior desconocida'),
    ('2024-01-05', 'subte', 110.0, True, NP,
     BO_CABA + '704801 | https://www.baenegocios.com/sociedad/aumentos-del-37-5-en-subte-cuando-sube-y-cuanto-costara-20231227-0052.html',
     'Res. 27/SBASE/23 (sancionada 26-dic-2023, publicada 27-dic-2023): tramo A rige luego del quinto día hábil. Fecha derivada de la norma'),
    ('2024-02-04', 'subte', 125.0, True, NP,
     BO_CABA + '704801 | https://www.lanacion.com.ar/economia/cuanto-sale-el-boleto-de-subte-en-febrero-2024-nid04022024/', 'Tramo B: 30 días corridos después del tramo A'),
    ('2024-05-17', 'subte', 574.0, True, NP,
     'https://documentosboletinoficial.buenosaires.gob.ar/publico/ck_PE-RESDIC-MJGGC-SBASE-5-24-6869.pdf | ' + OBS,
     'Res. 5/SBASE/24 (8-may-2024, publicada 9-may-2024), tramo A. Importe del Observatorio y la prensa (anexo no legible)'),
    ('2024-06-01', 'subte', 650.0, True, NP,
     'https://documentosboletinoficial.buenosaires.gob.ar/publico/ck_PE-RESDIC-MJGGC-SBASE-5-24-6869.pdf | ' + OBS,
     'Tramo B de la Res. 5/SBASE/24, 15 días corridos después del A. La resolución bajó el importe de $667 (propuesta) a $650'),
    ('2024-10-01', 'subte', 757.0, True, NP,
     BO_CABA + '742647 | ' + OBS, 'Tramo C, postergado del 1-ago al 1-oct-2024 por la Res. 12/SBASE/24 (publicada 26-jul-2024). Importe de los considerandos de la Res. 5'),
    ('2024-12-01', 'subte', 832.0, False, UNA, OBS, 'Solo el Observatorio (con SUBE registrada, 1 a 20 viajes)'),
    ('2025-04-01', 'subte', 869.0, False, UNA, OBS, 'Res. 47/2025 (publicada 20-feb-2025) establece un mecanismo de incremento mensual por doce meses; faltan los valores de febrero y marzo'),
    ('2025-05-01', 'subte', 919.0, False, UNA, OBS, ''),
    ('2025-06-01', 'subte', 963.0, False, NP,
     BO_CABA + '793637 | ' + OBS, 'Res. 70/2025 (sancionada 21-may, publicada 26-may-2025); vigencia luego del quinto día hábil'),
    ('2025-07-01', 'subte', 996.71, False, UNA, OBS, 'Figura como proyección (+3,5%)'),
    ('2025-09-01', 'subte', 1071.0, False, UNA,
     'https://www.canal26.com/economia/2025/08/28/aumentan-las-tarifas-en-el-amba-cual-sera-el-nuevo-valor-del-boleto-del-colectivo-y-subte-en-septiembre-de-2025/', '+3,87%; faltan agosto y octubre de 2025'),
    ('2025-11-01', 'subte', 1157.0, True, UNA, 'https://www.econoblog.com.ar/?p=151146', 'Con SUBE registrada; $1.839,63 sin registrar'),
    ('2026-01-01', 'subte', 1260.0, False, NP,
     BO_CABA + '830045 | https://www.canal26.com/economia/2026/01/05/el-boleto-de-subte-aumentara-todos-los-meses-del-2026-la-explicacion-oficial-y-como-se-calculara/', 'Res. de Directorio 134/2025, tramo A. Falta diciembre de 2025'),
    ('2026-05-01', 'subte', 1490.0, False, NP,
     BO_CABA + '850569 | https://www.iprofesional.com/economia/463002-el-subte-aumentara-4-desde-septiembre-cuanto-costara-viajar', 'Res. de Directorio 173/2026, tramo A (vigencia inferida del patrón de publicación)'),
    ('2026-06-01', 'subte', 1558.0, True, NP,
     BO_CABA + '856051 | https://www.iprofesional.com/impuestos/456075-cuanto-costara-el-boleto-de-subte-y-colectivo-en-caba-y-pba-desde-el-lunes-1-de-junio | https://www.baenegocios.com/economia/aumenta-el-boleto-de-subte-y-colectivo-cuanto-cuestan-a-partir-de-julio/', 'Res. de Directorio 185/2026, tramo A; +4,6%'),
    ('2026-07-01', 'subte', 1621.0, True, NP,
     BO_CABA + '861553 | https://www.baenegocios.com/economia/aumenta-el-boleto-de-subte-y-colectivo-cuanto-cuestan-a-partir-de-julio/ | https://www.infobae.com/economia/2026/07/01/aumentos-en-colectivos-subte-y-trenes-cuanto-costara-viajar-a-partir-de-julio/', 'Res. de Directorio 196/2026 (IPC de mayo 2,1% + 2%): $1.621; una nota daba $1.622'),
    ('2026-08-01', 'subte', 1684.0, True, NP,
     BO_CABA + '867180 | https://canal26.com/economia/2026/07/23/aumenta-el-transporte-publico-cuanto-costara-el-boleto-de-colectivos-y-subtes-desde-el-1-de-agosto/', 'Res. de Directorio 206/2026: $1.684; una nota daba $1.685,26'),
    ('2026-09-01', 'subte', 1753.0, True, PR,
     'https://www.iprofesional.com/economia/463002-el-subte-aumentara-4-desde-septiembre-cuanto-costara-viajar | https://www.ambito.com/economia/aumenta-el-transporte-septiembre-cuanto-costara-viajar-colectivo-tren-y-subte-manana-n6316386',
     '+4%. La Res. de Directorio 238/2026 corresponde a octubre y no se pudo leer el importe'),
]


# --- Filas agregadas: 2022-2023 y huecos de 2025 ---------------------------------------------------
# Tren: la serie sigue los ramales Mitre, Sarmiento, San Martín y Tren de la Costa (los de mayor tarifa).
# Roca, Belgrano Norte, Belgrano Sur y Urquiza tuvieron valores menores hasta enero de 2024.
SERIE_EXTRA = [
    # --- Colectivo nacional, 2022-2023 ---
    ('2022-01-01', 'colectivo_nacional', 18.0, False, PR,
     'https://lanacion.com.ar/economia/nuevas-tarifas-en-amba-cuanto-cuesta-el-colectivo-y-el-tren-nid01082022',
     'Tarifa vigente desde 2019 (más de tres años sin cambios)'),
    ('2022-08-01', 'colectivo_nacional', 25.20, True, PR,
     'https://lanacion.com.ar/economia/nuevas-tarifas-en-amba-cuanto-cuesta-el-colectivo-y-el-tren-nid01082022 | https://www.forbesargentina.com/today/se-disparan-tarifas-aumenta-40-boleto-colectivos-trenes-amba-n19196',
     'Res. 469/2022 (Ministerio de Transporte), +40%'),
    ('2023-01-01', 'colectivo_nacional', 35.0, True, PR,
     'https://eleconomista.com.ar/economia/estas-son-nuevas-tarifas-transporte-publico-1-enero-n58589 | https://www.forbesargentina.com/today/a-cuanto-ira-boleto-colectivo-partir-2023-n26979',
     '+39%; la prensa cita la Res. 952/2022. La indexación mensual por IPC arranca en marzo'),
    ('2023-03-01', 'colectivo_nacional', 37.10, False, UNA,
     'https://www.forbesargentina.com/today/a-cuanto-ira-boleto-colectivo-partir-2023-n26979', '+6%. No se encontró el valor de febrero de 2023'),
    ('2023-04-01', 'colectivo_nacional', 39.59, False, CON,
     'https://www.baenegocios.com/economia/Aumento-del-boleto-en-abril-cuanto-saldra-viajar-en-colectivo-el-proximo-mes-20230329-0087.html | https://www.izquierdadiario.es/El-ajuste-es-un-bondi-nuevo-aumento-de-boletos-de-colectivos-y-trenes-en-el-AMBA',
     'Una nota da $39,04 y otra $39,59 como valor previo a mayo; $39,59 es coherente con +6,6% sobre $37,10 y con +7,8% hasta $42,67'),
    ('2023-05-01', 'colectivo_nacional', 42.67, True, PR,
     'https://www.izquierdadiario.es/El-ajuste-es-un-bondi-nuevo-aumento-de-boletos-de-colectivos-y-trenes-en-el-AMBA | https://www.baenegocios.com/economia/Aumento-del-boleto-en-abril-cuanto-saldra-viajar-en-colectivo-el-proximo-mes-20230329-0087.html', ''),
    ('2023-06-01', 'colectivo_nacional', 46.35, False, PR,
     'https://lanacion.com.ar/economia/cuanto-sale-el-subte-el-tren-y-el-colectivo-en-junio-2023-nid01062023', '+8,6%'),
    ('2023-07-01', 'colectivo_nacional', 50.06, False, UNA,
     'https://eleconomista.com.ar/actualidad/aumento-colectivos-trenes-amba-cuanto-pasara-costar-boleto-partir-agosto-n64752', 'Valor previo a agosto ($50,06 → $52,96)'),
    ('2023-08-01', 'colectivo_nacional', 52.96, True, PR,
     'https://eleconomista.com.ar/actualidad/aumento-colectivos-trenes-amba-cuanto-pasara-costar-boleto-partir-agosto-n64752', '+5,8%. Último ajuste antes del congelamiento'),
    ('2023-09-01', 'colectivo_nacional', 52.96, True, NP,
     'https://eleconomista.com.ar/economia/el-gobierno-congela-tarifas-colectivos-trenes-despues-elecciones-n65789 | https://www.eltucumano.com/adjunto/2023/08/31/aviso_293214.pdf',
     'Res. 501/2023 (30-ago-2023): suspende la indexación mensual; sin cambio de valor hasta enero de 2024'),
    # --- Tren, 2022-2024 (ramales Mitre, Sarmiento, San Martín, Tren de la Costa) ---
    ('2022-01-01', 'tren', 12.32, False, INF,
     'https://www.forbesargentina.com/today/se-disparan-tarifas-aumenta-40-boleto-colectivos-trenes-amba-n19196', 'Inferido de $17,25 / 1,40; los valores de tren previos a agosto de 2022 no se encontraron'),
    ('2022-08-01', 'tren', 17.25, True, PR,
     'https://www.forbesargentina.com/today/se-disparan-tarifas-aumenta-40-boleto-colectivos-trenes-amba-n19196 | https://www.bloomberglinea.com/2022/07/21/aumenta-40-el-boleto-de-colectivo-y-tren-en-el-amba-cuanto-costara-el-pasaje/',
     '+40% (Res. 469/2022). Roca y Belgrano: valores menores'),
    ('2023-01-01', 'tren', 22.0, True, PR,
     'https://infozona.com.ar/nuevo-aumento-en-colectivos-y-trenes-en-el-amba-a-partir-de-enero/ | https://eleconomista.com.ar/economia/estas-son-nuevas-tarifas-transporte-publico-1-enero-n58589', '+27,5%'),
    ('2023-03-01', 'tren', 23.32, False, UNA,
     'https://www.c5n.com/sociedad/aumenta-el-boleto-colectivos-y-trenes-el-amba-cuanto-costara-el-1-marzo-n100984/amp', '+6%'),
    ('2023-05-01', 'tren', 26.82, False, UNA,
     'https://www.izquierdadiario.es/El-ajuste-es-un-bondi-nuevo-aumento-de-boletos-de-colectivos-y-trenes-en-el-AMBA', '+15% desde marzo: falta el valor de abril de 2023'),
    ('2023-06-01', 'tren', 29.12, False, CON,
     'https://lanacion.com.ar/economia/cuanto-sale-el-subte-el-tren-y-el-colectivo-en-junio-2023-nid01062023', 'Otra nota atribuye $29,12 a la tarifa social del colectivo'),
    ('2023-08-01', 'tren', 33.28, False, UNA,
     'https://eleconomista.com.ar/actualidad/aumento-colectivos-trenes-amba-cuanto-pasara-costar-boleto-partir-agosto-n64752', '+14% desde junio: falta el valor de julio'),
    ('2024-01-15', 'tren', 48.38, True, PR,
     'https://www.izquierdadiario.es/Otro-golpe-al-salario-el-precio-del-boleto-del-tren-subira-45-32-a-partir-del-15-de-enero | https://elintransigente.com/2023/12/los-pasajes-de-tren-subiran-4532-desde-el-15-de-enero-las-nuevas-tarifas-linea-por-linea/',
     '+45,32% (Res. 8/2023, rige desde el 15-ene-2024)'),
    # --- Subte, 2022-2023 ---
    ('2022-01-01', 'subte', 30.0, False, INF,
     OBS, 'Inferido: $42 / 1,40 (+40% de la Res. 17/2022) y $58 / 1,381 (+38,1% de marzo de 2023); el Observatorio cita $30 en abril de 2022'),
    ('2022-09-23', 'subte', 42.0, True, NP,
     BO_CABA + '620342', 'Res. 17/SBASE/22 (sancionada 9-sep-2022, publicada 14-sep-2022): rige desde el 23-sep-2022, +40%. El importe se infiere de las variaciones informadas'),
    ('2023-03-07', 'subte', 58.0, True, NP,
     BO_CABA + '647733 | https://lanacion.com.ar/economia/cuanto-cuesta-el-subte-desde-el-martes-7-de-marzo-nid06032023',
     'Res. 5/SBASE/23 (sancionada 15-feb, publicada 27-feb-2023), tramo A luego del quinto día hábil: +38,1%'),
    ('2023-05-06', 'subte', 67.0, True, NP,
     BO_CABA + '647733 | https://www.izquierdadiario.es/Ataques-al-bolsillo-otra-vez-cuales-son-los-aumentos-de-mayo', 'Tramo B: 60 días corridos después del A (+15,5%)'),
    ('2023-06-05', 'subte', 74.0, True, NP,
     BO_CABA + '647733 | https://lanacion.com.ar/economia/cuanto-cuesta-el-subte-desde-este-lunes-5-de-junio-nid05062023', 'Tramo C: 30 días corridos después del B'),
    ('2023-09-03', 'subte', 80.0, True, CON,
     BO_CABA + '647733 | https://www.clubmitsubishiasx.com/faq/cuanto-esta-el-subte-agosto-2023',
     'Tramo D: 90 días corridos después del C, lo que da el 3-sep-2023; algunas notas lo ubican en octubre. Se toma la fecha derivada de la norma'),
    # --- Subte, 2025 (corrige la fecha del $832) ---
    ('2025-02-28', 'subte', 832.0, True, NP,
     BO_CABA + '778582 | https://www.perfil.com/noticias/actualidad/aumento-del-boleto-del-subte-cuanto-costara-a-partir-de-este-viernes-28-febrero.phtml | https://www.minutouno.com/economia/el-subte-aumenta-este-viernes-28-febrero-cuanto-se-va-el-boleto-n6118525',
     'Res. 47/SBASE/25 (sancionada 19-feb, publicada 20-feb-2025): rige luego del quinto día hábil (28-feb) y fija ajuste mensual por doce meses. De $757 (+9,9%). Una fuente anterior ubicaba el $832 en diciembre de 2024: es incorrecto'),
    # --- Colectivos CABA y PBA, 2025 ---
    ('2025-04-01', 'colectivo_caba', 426.21, True, UNA,
     'https://www.izquierdadiario.es/Un-nuevo-logro-de-bajar-la-inflacion-aumentan-6-los-colectivos-y-subtes-en-mayo', 'Valor previo a mayo ($426,21 → $450,63); +4,4%'),
    ('2025-05-01', 'colectivo_caba', 450.63, True, UNA,
     'https://www.izquierdadiario.es/Un-nuevo-logro-de-bajar-la-inflacion-aumentan-6-los-colectivos-y-subtes-en-mayo', '+5,7%'),
    ('2025-06-01', 'colectivo_caba', 472.27, True, UNA,
     'https://www.izquierdadiario.es/Inflacion-domada-colectivos-y-subtes-aumentaran-5-en-junio', '+4,8%; faltan julio y agosto de 2025'),
    ('2025-06-01', 'colectivo_provincial', 472.66, True, UNA,
     'https://www.izquierdadiario.es/Inflacion-domada-colectivos-y-subtes-aumentaran-5-en-junio', '+4,8%'),
    ('2025-07-01', 'colectivo_provincial', 489.61, True, UNA,
     'https://www.cronista.com/informacion-gral/nuevo-aumento-en-colectivos-estos-son-los-precios-que-vas-a-pagar-desde-el-1-de-julio/', '+3,5%'),
    ('2025-09-01', 'colectivo_provincial', 529.25, True, UNA,
     'https://www.canal26.com/economia/2025/08/28/aumentan-las-tarifas-en-el-amba-cual-sera-el-nuevo-valor-del-boleto-del-colectivo-y-subte-en-septiembre-de-2025/', '+3,9%; falta agosto de 2025'),
]
SERIE = [r for r in SERIE
         if not (r[1] == 'subte' and r[0] in ('2023-12-01', '2024-12-01'))] + SERIE_EXTRA

# --- Filas agregadas a partir de anexos transcriptos de las resoluciones y del informe de CEPA (nov-2026) ---
# La vigencia de las resoluciones de SBASE se infiere del patrón (publicación a fin del mes anterior): a confirmar con el texto.
CEPA = 'https://centrocepa.com.ar/images/2026/06/Transporte%20publico%20en%20el%20AMBA%20y%20las%20principales%20ciudades%20del%20pais%20tarifas%20inflacion%20y%20poder%20adquisitivo%20-%20Mayo%202026%20-%20CEPA.pdf'
SERIE_EXTRA2 = [
    ('2025-08-01', 'subte', 1031.0, False, UNA, BO_CABA + '804007', 'Res. de Directorio 89/2025, tramo A (vigencia inferida)'),
    ('2025-10-01', 'subte', 1112.0, False, UNA, BO_CABA + '815394', 'Res. de Directorio 99/2025, tramo A (vigencia inferida)'),
    ('2026-02-01', 'subte', 1320.0, False, UNA, BO_CABA + '836074', 'Res. de Directorio 143/2026 (publicada 23-ene-2026), tramo A; +4,8% = IPC de diciembre 2,8% + 2% (vigencia inferida)'),
    ('2026-03-01', 'subte', 1363.0, False, UNA, BO_CABA + '841131', 'Res. de Directorio 153/2026 (publicada 26-feb-2026), tramo A (vigencia inferida)'),
    ('2026-04-01', 'subte', 1414.0, False, UNA, CEPA, 'Valor de abril de 2026 del informe de CEPA (1.363 → 1.414 → 1.490); resolución no identificada'),
    ('2026-02-01', 'colectivo_provincial', 721.83, False, UNA, 'https://normas.gba.gob.ar', 'Columna "tarifa actual" del anexo de la resolución provincial de marzo de 2026 (publicada 27-feb); fecha de inicio no confirmada'),
    ('2026-03-01', 'colectivo_provincial', 832.57, True, CON, 'https://normas.gba.gob.ar', 'Anexo I de la resolución provincial de marzo de 2026 (+15,3% sobre $721,83). La prensa daba $757,20 (+4,9%), pero el $871,30 de abril es +4,65% sobre $832,57 y no sobre $757,20: se toma el anexo'),
    ('2026-05-04', 'colectivo_provincial', 968.57, True, UNA, 'https://www.iprofesional.com/impuestos/456075-cuanto-costara-el-boleto-de-subte-y-colectivo-en-caba-y-pba-desde-el-lunes-1-de-junio', 'Valor "desde" de la nota de junio; coincide con el aumento extraordinario de Provincia (+11% desde el 4-may). Sin resolución'),
    ('2026-02-01', 'colectivo_caba', 650.11, False, INF, 'https://www.lanacion.com.ar/economia/vuelve-a-aumentar-el-pasaje-de-colectivo-en-el-amba-el-minimo-llegara-a-700-nid16032026/', 'Inferido: $681,97 de marzo / 1,049'),
    ('2026-03-01', 'colectivo_caba', 681.97, False, UNA, 'https://www.lanacion.com.ar/economia/vuelve-a-aumentar-el-pasaje-de-colectivo-en-el-amba-el-minimo-llegara-a-700-nid16032026/', '+4,9% (nota del 16-mar-2026)'),
    ('2026-05-01', 'colectivo_caba', 753.74, False, UNA, 'https://www.iprofesional.com/impuestos/456075-cuanto-costara-el-boleto-de-subte-y-colectivo-en-caba-y-pba-desde-el-lunes-1-de-junio', 'Valor "desde" de la nota de junio (+5,4% sobre abril)'),
    ('2025-07-01', 'colectivo_caba', 488.70, False, UNA, 'https://www.canal26.com/economia/2025/07/29/agosto-vendra-con-aumentos-en-alquileres-boletos-de-transportes-y-prepagas-de-cuanto-sera-la-suba-en-cada-rubro/', 'Valor previo a agosto ($488,70 → $506,29)'),
    ('2025-08-01', 'colectivo_caba', 506.29, False, UNA, 'https://www.canal26.com/economia/2025/07/29/agosto-vendra-con-aumentos-en-alquileres-boletos-de-transportes-y-prepagas-de-cuanto-sera-la-suba-en-cada-rubro/', '31 líneas porteñas'),
    ('2025-08-01', 'colectivo_provincial', 509.41, False, INF, 'https://www.canal26.com/economia/2025/08/28/aumentan-las-tarifas-en-el-amba-cual-sera-el-nuevo-valor-del-boleto-del-colectivo-y-subte-en-septiembre-de-2025/', 'Inferido: $529,25 de septiembre / 1,039'),
    ('2025-12-01', 'subte', 1207.0, False, INF, BO_CABA + '830045', 'Inferido: con la fórmula IPC (n-2) + 2%, 1.157 x 1,043 = 1.207 y x 1,045 = 1.261, que coincide con los $1.260 de enero (Res. 134/2025, publicada el 17-dic-2025)'),
    ('2026-07-01', 'colectivo_caba', 820.99, False, CON, 'https://www.perfil.com/noticias/sociedad/rigen-los-aumentos-del-transporte-en-el-amba-cuanto-cuesta-el-boleto-minimo-de-colectivos-trenes-y-subte-a-partir-de-julio.phtml | https://static.buenosaires.gob.ar/sites/default/files/2026-06/RESOLUCI%C3%93N_TARIFAS_CABA_JULIO_2026.pdf', 'Una nota da $820,99 y otra $820,60; el cuadro oficial de la Ciudad no se pudo leer'),
    ('2026-07-01', 'colectivo_provincial', 1057.25, False, CON, 'https://www.perfil.com/noticias/sociedad/rigen-los-aumentos-del-transporte-en-el-amba-cuanto-cuesta-el-boleto-minimo-de-colectivos-trenes-y-subte-a-partir-de-julio.phtml', 'Tres valores: $1.063,98, $1.059,28 y $1.057,25 (Econoblog). Se toma $1.057,25: es exactamente +4,1% sobre junio ($1.015,61), igual que la Ciudad'),
    ('2026-08-01', 'colectivo_provincial', 1111.19, False, UNA, 'https://eleconomista.com.ar/economia/aumenta-transporte-septiembre-cuanto-costara-viajar-colectivo-subte-tren-amba-n97612', 'Valor "desde" de la nota de septiembre ($1.111,19 → $1.158,97)'),
    ('2026-10-01', 'colectivo_provincial', 1215.12, False, INF, 'https://www.econoblog.com.ar/?p=159995', 'Inferido: noviembre $1.262,48 / 1,039'),
    ('2026-10-01', 'colectivo_caba', 920.72, False, INF, 'Anexo IF-2026-48624678-GCABA-SECT (29-oct-2026)', 'Inferido: noviembre $956,69 / 1,039 = $920,8 y septiembre $887,87 x 1,037 = $920,7 (ambos porcentajes de prensa)'),
]
SERIE = SERIE + SERIE_EXTRA2

COLS = ['fecha_vigencia', 'serie', 'valor_minimo', 'fecha_exacta', 'estado_verificacion', 'fuentes', 'nota']


def construir():
    t = pd.DataFrame(SERIE, columns=COLS)
    t['fecha_vigencia'] = pd.to_datetime(t['fecha_vigencia'])
    t = t.sort_values(['serie', 'fecha_vigencia']).reset_index(drop=True)
    t['valor_previo'] = t.groupby('serie')['valor_minimo'].shift(1)
    t['variacion_pct'] = ((t['valor_minimo'] / t['valor_previo'] - 1) * 100).round(2)
    t['meses_desde_valor_previo'] = (t.groupby('serie')['fecha_vigencia'].diff().dt.days / 30.4).round(1)
    return t


def serie_diaria(t, hasta='2026-10-29'):
    """Tarifa vigente por día. Entre cambios conocidos se mantiene el valor; antes del primer dato, NaN."""
    idx = pd.date_range('2022-01-01', hasta)
    partes = []
    for s, g in t.groupby('serie'):
        v = g.set_index('fecha_vigencia')['valor_minimo']
        v = v[~v.index.duplicated(keep='last')].dropna()
        d = v.reindex(idx.union(v.index)).ffill().reindex(idx)
        partes.append(pd.DataFrame({'fecha': idx, 'serie': s, 'tarifa': d.values}))
    return pd.concat(partes, ignore_index=True)


def cobertura(t):
    """Cuántos cambios hay por serie, cuántos son de prensa vs. norma, y qué meses quedan sin dato."""
    filas = []
    for s, g in t.groupby('serie'):
        g = g.dropna(subset=['valor_minimo'])
        meses = pd.period_range('2024-01', '2026-09', freq='M')
        con_dato = {d.to_period('M') for d in g['fecha_vigencia']}
        filas.append({'serie': s, 'cambios_con_valor': len(g),
                      'con_norma_oficial': int((g['estado_verificacion'] == NP).sum()),
                      'con_conflicto_entre_fuentes': int((g['estado_verificacion'] == CON).sum()),
                      'primer_valor': g['fecha_vigencia'].min().date(),
                      'meses_2024_2026_sin_cambio_registrado': len([m for m in meses if m not in con_dato])})
    return pd.DataFrame(filas)


def hitos_derivados(t):
    """Cambios de la serie clasificados como salto (>= umbral) o ajuste."""
    h = t.dropna(subset=['variacion_pct']).copy()
    grande = h['variacion_pct'].abs() >= UMBRAL_SALTO
    informado = pd.Series([(f.strftime('%Y-%m-%d'), s) in SALTOS_INFORMADOS
                           for f, s in zip(h['fecha_vigencia'], h['serie'])], index=h.index)
    en_regimen_mensual = pd.Series(
        [any(pd.Timestamp(a) <= f <= pd.Timestamp(b) for a, b in AJUSTE_MENSUAL.get(s, []))
         for f, s in zip(h['fecha_vigencia'], h['serie'])], index=h.index)
    sin_huecos = (h['meses_desde_valor_previo'] <= MESES_MAX_ENTRE_VALORES) | ~en_regimen_mensual
    h['tipo'] = np.select([grande & (sin_huecos | informado), grande], ['salto', 'acumulado con huecos'],
                          default='ajuste')
    return h[['fecha_vigencia', 'serie', 'tipo', 'valor_previo', 'valor_minimo', 'variacion_pct',
              'meses_desde_valor_previo', 'fecha_exacta', 'estado_verificacion', 'fuentes',
              'nota']].sort_values('fecha_vigencia')


def main():
    t = construir()
    t.to_csv(os.path.join(HITOS_DIR, 'serie_tarifas.csv'), index=False, encoding='utf-8-sig')
    d = serie_diaria(t)
    d.to_csv(os.path.join(HITOS_DIR, 'serie_tarifas_diaria.csv'), index=False)
    h = hitos_derivados(t)
    h.to_csv(os.path.join(HITOS_DIR, 'hitos_tarifas.csv'), index=False, encoding='utf-8-sig')
    c = cobertura(t)
    c.to_csv(os.path.join(TABLA_DIR, 'tabla_tarifas_cobertura.csv'), index=False)
    pd.set_option('display.width', 200)
    print(c.to_string(index=False))
    print(f"\nCambios totales: {len(t)}; saltos (>= {UMBRAL_SALTO:.0f}%): {int((h['tipo'] == 'salto').sum())}; "
          f"acumulados con huecos: {int((h['tipo'] == 'acumulado con huecos').sum())}; "
          f"ajustes: {int((h['tipo'] == 'ajuste').sum())}")
    print(h[h['tipo'] == 'salto'][['fecha_vigencia', 'serie', 'valor_previo', 'valor_minimo', 'variacion_pct',
                                   'estado_verificacion']].to_string(index=False))


if __name__ == '__main__':
    main()
