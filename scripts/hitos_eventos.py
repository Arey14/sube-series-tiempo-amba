"""
Tabla de hitos (paros y elecciones) con fuentes y comportamiento observado.

Los cambios de tarifa están en tarifas_serie.py (serie de precios por modo con fuente y estado).

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

    pd.set_option('display.width', 200)
    print(t1[['fecha', 'tipo', 'estado_verificacion', 'dato_reconstruido', 'cociente_colectivo', 'cociente_subte', 'cociente_tren']].to_string(index=False))



if __name__ == '__main__':
    main()
