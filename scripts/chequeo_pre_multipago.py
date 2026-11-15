"""Chequeo de la elasticidad precio del subte restringiendo la muestra antes del multipago.

Pregunta: Arey14 atribuye la brecha entre SUBE y CEPA en el subte (desde 2025) al pago contactless/QR (multipago),
cuyos viajes no pasan por SUBE, y reporta que la elasticidad interanual real del subte "hasta noviembre de 2024"
es -0,175 (-0,178 con control salarial). Este script reproduce ese cálculo con las mismas funciones de
`modelo_precio_demanda.py` (sin modificarlas) y agrega un barrido de fechas de corte, para ver si el resultado depende
de la fecha elegida.

Cómo se hace: se arma el panel semanal completo, se calcula la diferencia interanual (52 semanas) sobre toda la
serie y recién después se descartan las semanas posteriores al corte; así cada observación interanual es la misma que
en la muestra completa. La regresión es la de `interanual()` de `modelo_precio_demanda.py` (tarifa real, controles de
feriados, paros y elecciones; error estándar HAC de 8 rezagos), con y sin el salario real (RIPTE / IPC).

Salida: resultados/tablas/tabla_chequeo_pre_multipago.csv
"""

import os
import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, os.path.dirname(__file__))
import modelo_precio_demanda as M

CORTES = ['2024-06-30', '2024-09-29', '2024-11-24', '2024-12-29', '2025-03-30', '2025-06-29', '2026-09-27']
MODO = 'subte'


def regresion(y, p, ctrl, sal, corte, desde=None):
    """Elasticidad interanual del subte con la muestra de semanas cuyo domingo cae entre `desde` y `corte`."""
    dy = y[MODO] - y[MODO].shift(M.SEMANAS_ANIO)
    dp = p[MODO] - p[MODO].shift(M.SEMANAS_ANIO)
    X = pd.DataFrame({'dlog_tarifa': dp,
                      'dferiados': ctrl['feriados_habiles'] - ctrl['feriados_habiles'].shift(M.SEMANAS_ANIO),
                      'dparo': ctrl['paro'] - ctrl['paro'].shift(M.SEMANAS_ANIO),
                      'deleccion': ctrl['eleccion'] - ctrl['eleccion'].shift(M.SEMANAS_ANIO)})
    if sal is not None:
        X['dlog_salario_real'] = sal - sal.shift(M.SEMANAS_ANIO)
    datos = pd.concat([dy.rename('dy'), X], axis=1).dropna()
    fin_semana = datos.index + pd.Timedelta(days=6)
    datos = datos[fin_semana <= pd.Timestamp(corte)]
    if desde is not None:
        datos = datos[datos.index >= pd.Timestamp(desde)]
    res = M._hac(sm.OLS(datos['dy'], sm.add_constant(datos.drop(columns='dy'))).fit())
    return {'semanas': len(datos), 'primera_semana': datos.index[0].date(), 'ultima_semana': datos.index[-1].date(),
            'elasticidad': round(res.params[1], 3), 'error_std_HAC': round(res.bse[1], 3),
            'ic95_inf': round(res.params[1] - 1.96 * res.bse[1], 3), 'ic95_sup': round(res.params[1] + 1.96 * res.bse[1], 3),
            'R2': round(res.rsquared, 3)}


def main():
    usos, tar, evt = M.cargar()
    y, p, ctrl, yh, pr = M.semanal(usos, tar, evt)
    d_idx = usos.loc[M.INICIO:M.FIN].index
    semana = d_idx.to_period('W-SUN').start_time
    rip_nom, rip_real = M.ripte_diario(d_idx)
    sal = np.log(rip_real.groupby(semana).mean())

    filas = []
    for corte in CORTES:
        for con_sal in (False, True):
            r = regresion(y, pr, ctrl, sal if con_sal else None, corte)
            filas.append({'muestra': f'hasta {corte}', 'control_salario': con_sal, **r})
    # posterior al corte, como referencia: ¿cambia la elasticidad desde el multipago?
    for con_sal in (False, True):
        # semanas interanuales cuyo extremo reciente cae después de nov-2024 (la comparación mira un año antes)
        r = regresion(y, pr, ctrl, sal if con_sal else None, M.FIN, desde='2024-12-02')
        filas.append({'muestra': 'desde 2024-12-02 (solo posterior)', 'control_salario': con_sal, **r})
    t = pd.DataFrame(filas)
    t.to_csv(os.path.join(M.TABLA_DIR, 'tabla_chequeo_pre_multipago.csv'), index=False)
    print(t.to_string(index=False))


if __name__ == '__main__':
    main()
