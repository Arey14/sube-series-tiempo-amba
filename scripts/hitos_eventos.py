"""
Tabla de hitos (paros, elecciones, saltos tarifarios) con fuentes y comportamiento observado.

Las fechas y descripciones se cargaron a mano desde fuentes de prensa y normativa (URLs en la tabla).
Cada hito tiene un `estado` de verificación:
  - confirmado (>=2 fuentes)
  - confirmado con discrepancias (>=2 fuentes que difieren en algún detalle)
  - una fuente / a verificar
  - sin fuente (inferido del dato)

El script calcula, para cada día de paro o elección, el cociente de cada modo contra la mediana
del mismo día de la semana (±4 semanas, sin días imputados).

Salidas:
  data/hitos/hitos_paros_elecciones.csv
  data/hitos/hitos_tarifas.csv
"""

import os
import numpy as np
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROC_PATH = os.path.join(BASE_DIR, "data", "procesado", "serie_sube_diaria_reconstruida.csv")
HITOS_DIR = os.path.join(BASE_DIR, "data", "hitos")
os.makedirs(HITOS_DIR, exist_ok=True)

CONF = 'confirmado (>=2 fuentes)'
CONF_DISC = 'confirmado con discrepancias'
UNA = 'una fuente / a verificar'
SIN = 'sin fuente (inferido del dato)'

# fecha, tipo, descripcion, modos_afectados_segun_fuentes, estado, fuentes (separadas por " | "), nota
PAROS_ELECCIONES = [
    ('2021-09-12', 'eleccion', 'PASO 2021: transporte público gratuito', 'colectivo, tren, subte', CONF,
     'https://www.baenegocios.com/politica/elecciones-2021-que-debo-presentar-para-viajar-gratis-durante-las-paso-20210910-0055.html'
     ' | https://www.econoblog.com.ar/100658/colectivos-y-trenes-gratis-durante-elecciones', ''),
    ('2021-11-14', 'eleccion', 'Generales 2021: transporte público gratuito', 'colectivo, tren, subte', CONF,
     'https://www.letrap.com.ar/nota/2021-11-8-17-2-0-elecciones-2021-habra-transporte-publico-gratuito-para-ir-a-votar'
     ' | https://www.noticiasnqn.com.ar/noticias/2021/11/09/250226-elecciones-generales-el-transporte-pblico-ser-libre-y-gratuito-durante-el-prximo-domingo', ''),
    ('2023-08-13', 'eleccion', 'PASO 2023: transporte gratuito (Res. 435/2023, jurisdicción nacional, frecuencia de sábado)', 'colectivo, tren (nacional); subte sin confirmar', CONF_DISC,
     'https://www.ambito.com/politica/elecciones-2023-habra-transporte-publico-gratuito-todo-el-pais-n5786474'
     ' | https://www.lacapital.com.ar/politica/el-transporte-publico-sera-gratuito-las-paso-del-domingo-y-tambien-las-generales-n2686412.html',
     'Las fuentes no confirman si el subte de CABA adhirió, pero el dato muestra subte ~0'),
    ('2023-10-22', 'eleccion', 'Generales 2023: transporte gratuito (Res. 435/2023)', 'colectivo, tren (nacional); subte sin confirmar', CONF_DISC,
     'https://www.ambito.com/politica/elecciones-2023-habra-transporte-publico-gratuito-todo-el-pais-n5786474'
     ' | https://www.lacapital.com.ar/politica/el-transporte-publico-sera-gratuito-las-paso-del-domingo-y-tambien-las-generales-n2686412.html', ''),
    ('2023-11-19', 'eleccion', 'Balotaje 2023', 'sin confirmar', SIN, '',
     'No se encontró fuente de gratuidad; el dato es consistente con transporte gratuito'),
    ('2025-05-18', 'eleccion', 'Elecciones legislativas CABA 2025', 'sin confirmar', SIN, '',
     'El dato no muestra colapso: no parece haber gratuidad'),
    ('2025-09-07', 'eleccion', 'Elecciones legislativas Provincia de Buenos Aires 2025', 'sin confirmar', SIN, '',
     'Una búsqueda sugiere medida provincial de gratuidad en 2025, no confirmada; el dato no muestra colapso'),
    ('2025-10-26', 'eleccion', 'Elecciones legislativas nacionales 2025', 'sin confirmar', SIN, '',
     'El dato no muestra colapso: no parece haber gratuidad nacional'),
    ('2023-07-07', 'paro', 'Paro de colectivos de la UTA por paritaria (AMBA)', 'colectivo', CONF_DISC,
     'https://www.econoblog.com.ar/123285/paro-nacional-de-colectivos-del-viernes-7-de-julio-de-2023'
     ' | https://www.minutouno.com/sociedad/argentina/colectivos-el-paro-nacional-la-uta-cual-es-el-alcance-y-cuanto-tiempo-n5763229',
     'La prensa informa que el paro se levantó por la tarde tras la intervención del Gobierno; el dato muestra una caída del colectivo a ~15% de lo habitual, lo que sugiere que se sostuvo gran parte del día'),
    ('2024-01-24', 'paro', 'Primer paro general de la CGT contra el Gobierno de Milei', 'colectivo, tren, subte (según mención posterior)', UNA,
     'https://www.lanacion.com.ar/politica/cuando-es-el-paro-general-de-la-cgt-y-el-transporte-nid07052024/',
     'Mencionado indirectamente en notas del paro del 9-may-2024. Cae dentro del hueco de enero de 2024: el dato es una reconstrucción desde transacciones (error mediano ≈ 2%)'),
    ('2024-02-21', 'paro', 'Paro nacional de trenes de La Fraternidad (24 h)', 'tren', CONF,
     'https://www.lanacion.com.ar/sociedad/cuando-es-el-paro-de-trenes-nid16022024/'
     ' | https://www.perfil.com/noticias/politica/la-fraternidad-hara-un-paro-nacional-de-trenes-por-24-horas-el-proximo-miercoles.phtml'
     ' | https://www.ambito.com/politica/la-fraternidad-ratifico-el-paro-trenes-del-miercoles-cuales-son-las-excepciones-n5949510', ''),
    ('2024-04-11', 'paro', 'Retención de tareas de la UTA por sueldos impagos (líneas de colectivos del AMBA)', 'colectivo', CONF_DISC,
     'https://www.c5n.com/sociedad/paro-colectivos-el-amba-cuales-son-las-lineas-que-no-funcionan-este-jueves-11-abril-n153823'
     ' | https://www.canal26.com/general/2024/04/11/paro-de-colectivos-en-el-amba-cuales-son-las-lineas-que-no-prestan-servicio-este-jueves/',
     'Las fuentes difieren en la cantidad de líneas afectadas (≈140 contra 11 listadas)'),
    ('2024-05-09', 'paro', 'Segundo paro general de la CGT (UTA, trenes y subte adhirieron)', 'colectivo, tren, subte', CONF,
     'https://www.lanacion.com.ar/politica/cuando-es-el-paro-general-de-la-cgt-y-el-transporte-nid07052024/'
     ' | https://eleconomista.com.ar/politica/cuales-son-servicios-transporte-afectados-paro-general-convocado-cgt-n73448'
     ' | https://www.c5n.com/sociedad/paro-transporte-este-jueves-9-mayo-como-funcionaran-colectivos-subtes-y-trenes-n157072',
     'Ocurre 7 días después del aumento de trenes del 2-may-2024: efectos superpuestos'),
    ('2024-10-30', 'paro', 'Paro de transporte (trenes y subte); la UTA no adhirió', 'tren, subte', CONF,
     'https://www.lanacion.com.ar/politica/paro-de-transporte-del-30-de-octubre-que-servicios-se-veran-afectados-nid28102024/'
     ' | https://www.baenegocios.com/sociedad/Doble-paro-de-transporte-el-cronograma-confirmado-de-colectivos-trenes-y-subtes-sin-servicio-20241029-0017.html'
     ' | https://www.canal26.com/general/paro-de-transporte-del-30-de-octubre-como-funcionaran-trenes-colectivos-subtes-y-aviones--397512', ''),
    ('2025-04-10', 'paro', 'Tercer paro general de la CGT (subte paró; la UTA no adhirió por conciliación obligatoria)', 'subte, tren (alcance ferroviario con matices)', CONF_DISC,
     'https://www.canal26.com/general/2025/04/10/paro-general-de-la-cgt-como-funcionan-los-trenes-colectivos-y-subtes-este-jueves-10-de-abril/'
     ' | https://eleconomista.com.ar/politica/todo-lo-tenes-saber-sobre-paro-general-10-abril-n83742'
     ' | https://www.econoblog.com.ar/145824/uta-confirmo-que-habran-colectivos-durante-el-paro-del-10-de-abril',
     'Las fuentes difieren sobre el alcance en trenes; el dato muestra tren ~0'),
    ('2025-05-06', 'paro', 'Paro de colectivos de la UTA de 24 h (adhesión parcial: DOTA, Metropol y Misión Buenos Aires no adhirieron)', 'colectivo', CONF,
     'https://www.lanacion.com.ar/sociedad/paro-de-colectivos-que-lineas-no-funcionan-este-martes-6-de-mayo-nid05052025'
     ' | https://www.cronica.com.ar/sociedad/Paro-de-colectivos-que-lineas-no-funcionaran-este-martes-6-de-mayo-20250503-0085.html'
     ' | https://www.canal26.com/general/2025/05/06/paro-de-colectivos-del-martes-6-de-mayo-que-lineas-se-adhieren-a-la-medida-de-fuerza-y-cuales-funcionan/', ''),
    ('2026-02-19', 'paro', 'Paro general de la CGT contra la reforma laboral (UTA excepto DOTA, La Fraternidad y subte)', 'colectivo, tren, subte', CONF,
     'https://eleconomista.com.ar/politica/paro-general-24-horas-pasara-trenes-subtes-colectivos-n92689'
     ' | https://elintransigente.com/2026/02/paro-general-19-de-febrero-metrodelegados-confirmaron-su-adhesion-y-no-habra-subtes/'
     ' | https://www.econoblog.com.ar/153819/confirmaron-paro-general-para-el-jueves-19-de-febrero-de-2026/',
     'Algunas páginas muestran fechas de publicación inconsistentes; el contenido coincide'),
]

# fecha, jurisdiccion/modo, descripcion, magnitud, estado, fuentes, nota
OFI = 'norma oficial verificada (importes de prensa)'
OBS = 'https://observatoriociudad.org/informe-sobre-la-evoluci%C3%B3n-de-pasajeros-y-la-tarifa-del-subte-de-la-ciudad-de-buenos-aires-en-la-%C3%BAltima-d%C3%A9cada-2015-2025/'

TARIFAS = [
    ('2022-08-01', 'colectivo y tren AMBA (jurisdicción nacional)', 'Aumento del 40% (Res. 469/2022 del Ministerio de Transporte, publicada el 21-jul-2022)', '+40%', CONF,
     'https://www.bloomberglinea.com/2022/07/21/aumenta-40-el-boleto-de-colectivo-y-tren-en-el-amba-cuanto-costara-el-pasaje/'
     ' | https://eleconomista.com.ar/economia/aumenta-40-boleto-colectivos-trenes-amba-pasara-beneficios-sociales-tarjeta-sube-n54925'
     ' | https://lanacion.com.ar/economia/nuevas-tarifas-en-amba-cuanto-cuesta-el-colectivo-y-el-tren-nid01082022',
     'Número de resolución según prensa; texto oficial no leído. Una recopilación externa cita la Res. 1017/2022: es incorrecto (esa norma fija el mecanismo de actualización de fines de 2022). Cae en el hueco de ago-2022 (reconstruido)'),
    ('2024-01-05', 'subte CABA', 'Tramo A de la Res. 27/SBASE/23: boleto de $80 a $110', '+37,5%', OFI,
     'https://boletinoficial.buenosaires.gob.ar/normativaba/norma/704801'
     ' | https://www.baenegocios.com/sociedad/aumentos-del-37-5-en-subte-cuando-sube-y-cuanto-costara-20231227-0052.html',
     'Res. sancionada el 26-dic-2023 y publicada el 27-dic-2023. Fecha derivada de la norma (tramo A rige luego del quinto día hábil desde la publicación); importes del Anexo II no legibles'),
    ('2024-01-15', 'colectivo y tren AMBA (jurisdicción nacional)', 'Res. 8/2023 del Ministerio de Infraestructura: restablece la actualización mensual por IPC; prensa: mínimo de $52,96 a $76,92', '+45% (prensa)', OFI,
     'https://www.argentina.gob.ar/normativa/nacional/norma-395786/texto'
     ' | https://www.baenegocios.com/sociedad/Suba-de-colectivos-el-boleto-minimo-aumentara-a-76-92-en-el-AMBA-20231228-0077.html',
     'La norma rige desde las 0 h del 15-ene-2024 (resuelve la duda entre el 1 y el 15). Se dictó el 29-dic-2023 y se publicó el 3-ene-2024. No fija valores: el +45% y el $76,92 son de prensa. Hueco de ene-2024 (reconstruido)'),
    ('2024-02-04', 'subte CABA', 'Tramo B de la Res. 27/SBASE/23: boleto de $110 a $125', '+13,6%', OFI,
     'https://boletinoficial.buenosaires.gob.ar/normativaba/norma/704801'
     ' | https://www.lanacion.com.ar/economia/cuanto-sale-el-boleto-de-subte-en-febrero-2024-nid04022024/',
     'Tramo B: 30 días corridos después del tramo A, lo que coincide con la fecha de la prensa'),
    ('2024-02-06', 'colectivo y tren AMBA (jurisdicción nacional y Provincia)', 'Res. 5/2024 de la Secretaría de Transporte (5-feb-2024): colectivo mínimo de $76,92 a $270 y tren a $130; la Provincia adhirió con la Res. 41/2024 (6-feb-2024)', 'colectivo +251%, tren +247%', CONF,
     'https://eleconomista.com.ar/economia/confirmado-martes-aumenta-250-boleto-minimo-colectivo-tren-amba-n70624'
     ' | https://normas.gba.gob.ar/ar-b/resolucion/2024/41/414919'
     ' | https://artear-eltrece-prod.cdn.arcpublishing.com/poco-correctos/2024/02/05/aumentan-trenes-y-colectivos-a-partir-de-este-martes-cuanto-costaran-los-boletos',
     'La vigencia del 6-feb proviene de prensa (el texto de la Res. 5/2024 no se pudo leer). La adhesión de la Provincia el mismo día implica que los colectivos provinciales NO sirven de control. Una nota de prensa menciona una suspensión judicial previa; el aumento terminó aplicándose'),
    ('2024-05-02', 'tren AMBA', 'Boleto mínimo de $130 a $200', '+53,85%', CONF,
     'https://eleconomista.com.ar/actualidad/ciudad-buenos-aires-boleto-subte-subira-mas-350-proximos-dias-n73222'
     ' | https://www.a24.com/economia/aumenta-la-tarifa-los-trenes-cuanto-saldra-el-boleto-partir-mayo-n1313012'
     ' | https://www.izquierdadiario.es/Milei-da-otro-mazazo-al-bolsillo-nuevo-aumento-del-boleto-de-trenes',
     'El paro general del 9-may-2024 ocurre 7 días después y el aumento del subte del 17-may, 15 días después: efectos superpuestos'),
    ('2024-05-17', 'subte CABA', 'Tramo A de la Res. 5/SBASE/24 (publicada el 9-may-2024): boleto de $125 a $574', '+359%', OFI,
     'https://documentosboletinoficial.buenosaires.gob.ar/publico/ck_PE-RESDIC-MJGGC-SBASE-5-24-6869.pdf | ' + OBS,
     'La norma fija vigencia luego del quinto día hábil desde la publicación (17-may según el Observatorio y el Decreto 404/2024). El importe de $574 es del Observatorio y la prensa: el Anexo II no es legible'),
    ('2024-06-01', 'subte CABA', 'Tramo B de la Res. 5/SBASE/24: boleto a $650', '+13%', OFI,
     'https://documentosboletinoficial.buenosaires.gob.ar/publico/ck_PE-RESDIC-MJGGC-SBASE-5-24-6869.pdf | ' + OBS,
     'Vigencia: 15 días corridos desde el tramo A. La resolución bajó el importe de $667 (propuesta) a $650: una recopilación externa que cita $667 se equivoca'),
    ('2024-09-16', 'tren AMBA', 'Aumento del boleto de tren', '+40%', CONF,
     'https://www.c5n.com/economia/ya-rige-un-nuevo-aumento-del-boleto-tren-cuanto-cuesta-el-minimo-n173823/amp'
     ' | https://www.lanacion.com.ar/sociedad/nuevo-aumento-en-los-boletos-de-trenes-en-el-amba-cuanto-suben-y-cual-sera-el-valor-minimo-nid13092024/', ''),
    ('2024-10-01', 'subte CABA', 'Tramo C de la Res. 5/SBASE/24: boleto a $757 (postergado por la Res. 12/SBASE/24 del 1-ago al 1-oct-2024)', '+16%', OFI,
     'https://boletinoficial.buenosaires.gob.ar/normativaba/norma/742647 | ' + OBS,
     'Res. 12/SBASE/24 sancionada el 24-jul y publicada el 26-jul-2024: pospone el tramo C por el retraso en el recambio de validadores. El Observatorio y una recopilación externa ubican el $757 en agosto: incorrecto. El importe sale de los considerandos de la Res. 5; el Anexo II.C no es legible. Hay un fallo judicial sobre estos aumentos aún sin verificar'),
    ('2024-12', 'subte CABA', 'Boleto con SUBE registrada a $832', '+10%', UNA, OBS, 'Solo el Observatorio'),
    ('2025-04 a 2025-07', 'subte CABA', 'Ajustes mensuales: $869 (abr), $919 (may), $963 (jun), $996,71 proyectado (jul)', '+3,5% a +5,7% por mes', UNA, OBS,
     'Solo el Observatorio; julio de 2025 figura como proyección'),
    ('2026-05-18', 'tren y colectivo nacional AMBA', 'Tren a $330 (+18%); colectivo nacional +2% (con ajustes mensuales por tres meses)', 'tren +18%, colectivo +2%', UNA,
     'https://www.infobae.com/economia/2026/05/17/manana-aumentan-el-colectivo-y-el-tren-a-cuanto-pasa-el-boleto-en-el-amba-y-cual-es-la-brecha-de-precios-con-el-interior-del-pais/', ''),
    ('2026-07-01', 'tren AMBA', 'Primera sección a $380,10', '+8,6%', UNA,
     'https://www.infobae.com/economia/2026/07/01/aumentos-en-colectivos-subte-y-trenes-cuanto-costara-viajar-a-partir-de-julio/', ''),
    ('2026-09-01', 'tren AMBA', 'Mínimo de $420 a $480', '+14,29%', UNA,
     'https://www.ambito.com/economia/aumenta-el-transporte-septiembre-cuanto-costara-viajar-colectivo-tren-y-subte-manana-n6316386',
     'Una recopilación externa indica $450 (+7%): contradice a Ámbito; falta la fuente oficial'),
    ('2025-2026', 'colectivo y subte CABA/PBA', 'Ajuste mensual por IPC más 2% (subte mensual durante 2026; colectivos con actualización mensual desde 2025)', '≈ +4% a +5% por mes', UNA,
     'https://www.canal26.com/economia/2026/01/05/el-boleto-de-subte-aumentara-todos-los-meses-del-2026-la-explicacion-oficial-y-como-se-calculara/'
     ' | https://www.baenegocios.com/sociedad/Aumento-el-boleto-de-colectivo-en-el-AMBA-cuales-son-las-nuevas-tarifas-20250601-0029.html',
     'Pasos chicos y frecuentes: no son saltos discretos aislables; sirven como contexto, no como evento'),
]


def cargar():
    df = pd.read_csv(PROC_PATH, parse_dates=['fecha']).set_index('fecha').asfreq('D')
    return df


def cociente(df, col, fecha):
    """Valor del día / mediana del mismo día de la semana (±4 semanas).

    Los días de ago-2022 y ene-2024 son reconstruidos desde las transacciones, que sí observan los
    eventos del día, por lo que se incluyen y se marcan con `dato_reconstruido`.
    """
    s = df[col]
    f = pd.Timestamp(fecha)
    if f not in s.index or np.isnan(s.loc[f]):
        return np.nan
    vec = [s.get(f + pd.Timedelta(days=7 * k), np.nan) for k in (-4, -3, -2, -1, 1, 2, 3, 4)]
    vec = [v for v in vec if not np.isnan(v)]
    return round(float(s.loc[f] / np.median(vec)), 2) if vec else np.nan


def dias_previos_sin_imputar(df, fecha):
    """Días consecutivos con dato observado (no reconstruido) inmediatamente anteriores a la fecha."""
    f = pd.Timestamp(fecha)
    previos = df.loc[:f - pd.Timedelta(days=1), 'imputado']
    if previos.empty:
        return 0
    n = 0
    for v in previos.iloc[::-1]:
        if v:
            break
        n += 1
    return n


def main():
    df = cargar()
    filas = []
    for fecha, tipo, desc, modos, estado, fuentes, nota in PAROS_ELECCIONES:
        f = pd.Timestamp(fecha)
        fila = {'fecha': fecha, 'tipo': tipo, 'descripcion': desc, 'modos_afectados_segun_fuentes': modos,
                'estado_verificacion': estado, 'fuentes': fuentes, 'nota': nota,
                'dato_reconstruido': bool(df.loc[f, 'imputado'])}
        for c in ['colectivo_amba', 'subte_amba', 'tren_amba']:
            fila['cociente_' + c.split('_')[0]] = cociente(df, c, fecha)
        filas.append(fila)
    t1 = pd.DataFrame(filas).sort_values('fecha')
    t1.to_csv(os.path.join(HITOS_DIR, 'hitos_paros_elecciones.csv'), index=False, encoding='utf-8-sig')

    filas = []
    for fecha, juris, desc, magnitud, estado, fuentes, nota in TARIFAS:
        pre = dias_previos_sin_imputar(df, fecha) if len(fecha) == 10 else np.nan
        filas.append({'fecha': fecha, 'jurisdiccion_modo': juris, 'descripcion': desc, 'magnitud': magnitud,
                      'estado_verificacion': estado, 'fuentes': fuentes, 'nota': nota,
                      'dias_previos_con_dato_observado': pre})
    t2 = pd.DataFrame(filas)
    t2.to_csv(os.path.join(HITOS_DIR, 'hitos_tarifas.csv'), index=False, encoding='utf-8-sig')

    pd.set_option('display.width', 200)
    print(t1[['fecha', 'tipo', 'estado_verificacion', 'dato_reconstruido', 'cociente_colectivo', 'cociente_subte', 'cociente_tren']].to_string(index=False))
    print()
    print(t2[['fecha', 'jurisdiccion_modo', 'magnitud', 'estado_verificacion', 'dias_previos_con_dato_observado']].to_string(index=False))


if __name__ == '__main__':
    main()
