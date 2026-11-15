"""Control de la elasticidad del subte por las fechas de apertura de los nuevos medios de pago (multipago).

Fechas (prensa, ver docs/interpretacion_resultados.md, bloque 23):
  - 2-dic-2024: el subte acepta tarjetas contactless y celulares con NFC en toda la red (desde el 25-nov-2024 hubo una
    prueba en cinco molinetes; algunas notas dicen 1-dic).
  - 22-may-2025: pago con QR en todas las líneas del subte.
  - 27-mar-2025: primeras líneas de colectivo con tarjetas contactless y NFC (AMBA: CABA y línea 1).

PRE-REGISTRO (escrito antes de correr). Si el multipago saca viajes de SUBE, se espera:
  P1. En el subte, el indicador de multipago tiene signo negativo (SUBE registra menos viajes).
  P2. Al agregar el indicador, la elasticidad del subte de la muestra completa baja en valor absoluto
      (parte de lo que se leía como respuesta al precio era migración de medio de pago).
  P3. En el tren (que no tuvo multipago en esa fecha) el indicador de diciembre de 2024 es cercano a cero.
  P4. En la ventana de la apertura (sep-2024 a feb-2025), con la tarifa del subte constante desde el 1-oct-2024, el
      salto del 2-dic-2024 se ve como un escalón negativo fuera del rango de escalones en fechas sin evento.
Si P1 y P2 no se cumplen, la frase "la estimación completa está amplificada por el multipago" no tiene apoyo.

Cómo: la misma regresión interanual de `modelo_precio_demanda.interanual()` (tarifa real, feriados, paros y elecciones;
error estándar HAC), con indicadores de escalón. Un escalón de nivel M_t en la serie interanual entra como
M_t - M_{t-52}: vale 1 durante las 52 semanas siguientes a la apertura y vuelve a 0 después, porque la semana del año
anterior ya tenía multipago.

Salida: resultados/tablas/tabla_multipago_fechas.csv y tabla_multipago_placebo_escalon.csv
"""

import os
import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, os.path.dirname(__file__))
import modelo_precio_demanda as M

SUBTE_CONTACTLESS = pd.Timestamp('2024-12-02')
SUBTE_QR = pd.Timestamp('2025-05-26')          # primera semana completa posterior al 22-may-2025
COLECTIVO_CONTACTLESS = pd.Timestamp('2025-03-31')  # primera semana completa posterior al 27-mar-2025
VENTANA = ('2024-09-02', '2025-02-23')


def escalon(indice, desde):
    m = pd.Series((indice >= desde).astype(float), index=indice)
    return m - m.shift(M.SEMANAS_ANIO)


def regresion(y, p, ctrl, sal, modo, escalones, ini=None, fin=None, lags=8):
    """Interanual de `modo` con los escalones dados {nombre: fecha}. Devuelve coeficientes de precio y de cada escalón."""
    dy = y[modo] - y[modo].shift(M.SEMANAS_ANIO)
    dp = p[modo] - p[modo].shift(M.SEMANAS_ANIO)
    X = pd.DataFrame({'dlog_tarifa': dp,
                      'dferiados': ctrl['feriados_habiles'] - ctrl['feriados_habiles'].shift(M.SEMANAS_ANIO),
                      'dparo': ctrl['paro'] - ctrl['paro'].shift(M.SEMANAS_ANIO),
                      'deleccion': ctrl['eleccion'] - ctrl['eleccion'].shift(M.SEMANAS_ANIO)})
    if sal is not None:
        X['dlog_salario_real'] = sal - sal.shift(M.SEMANAS_ANIO)
    for nombre, f in escalones.items():
        X[nombre] = escalon(y.index, f)
    d = pd.concat([dy.rename('dy'), X], axis=1).dropna()
    if ini is not None:
        d = d[d.index >= pd.Timestamp(ini)]
    if fin is not None:
        d = d[d.index <= pd.Timestamp(fin)]
    # un escalón sin variación en la muestra no se puede estimar
    d = d.loc[:, (d.nunique() > 1) | (d.columns == 'dy')]
    Xm = sm.add_constant(d.drop(columns='dy'))
    res = sm.OLS(d['dy'], Xm).fit().get_robustcov_results(cov_type='HAC', maxlags=lags)
    nombres = list(Xm.columns)
    out = {'semanas': len(d), 'R2': round(res.rsquared, 3), 'cond_num': round(float(np.linalg.cond(Xm.values)), 1)}
    for k in ['dlog_tarifa'] + list(escalones):
        if k in nombres:
            i = nombres.index(k)
            out[f'{k}'] = round(res.params[i], 3)
            out[f'{k}_ee'] = round(res.bse[i], 3)
            out[f'{k}_p'] = round(res.pvalues[i], 3)
    return out


def main():
    usos, tar, evt = M.cargar()
    y, p, ctrl, yh, pr = M.semanal(usos, tar, evt)
    d_idx = usos.loc[M.INICIO:M.FIN].index
    semana = d_idx.to_period('W-SUN').start_time
    _, rip_real = M.ripte_diario(d_idx)
    sal = np.log(rip_real.groupby(semana).mean())

    filas = []

    def fila(spec, modo, muestra, con_sal, escal, **kw):
        r = regresion(y, pr, ctrl, sal if con_sal else None, modo, escal, **kw)
        filas.append({'especificacion': spec, 'modo': modo, 'muestra': muestra, 'control_salario': con_sal,
                      'escalones': '+'.join(escal) if escal else 'ninguno', **r})

    # A. Muestra completa, subte: sin escalón, con el escalón de diciembre y con los dos (contactless y QR)
    for con_sal in (False, True):
        fila('A. subte completa', 'subte', 'completa', con_sal, {})
        fila('A. subte completa', 'subte', 'completa', con_sal, {'multipago_dic24': SUBTE_CONTACTLESS})
        fila('A. subte completa', 'subte', 'completa', con_sal,
             {'multipago_dic24': SUBTE_CONTACTLESS, 'qr_may25': SUBTE_QR})
    # B. Placebo de modo: el tren con el mismo escalón (no tuvo multipago en esa fecha); el colectivo con su propia fecha
    for con_sal in (False, True):
        fila('B. tren con escalón del subte', 'tren', 'completa', con_sal, {'multipago_dic24': SUBTE_CONTACTLESS})
        fila('B. colectivo nacional con escalón del subte', 'colectivo_nacional', 'completa', con_sal,
             {'multipago_dic24': SUBTE_CONTACTLESS})
        fila('B. colectivo nacional con su propia fecha (27-mar-2025)', 'colectivo_nacional', 'completa', con_sal,
             {'contactless_colectivo_mar25': COLECTIVO_CONTACTLESS})
    # C. Ventana de la apertura (la tarifa del subte no cambia entre el 1-oct-2024 y el 28-feb-2025)
    for modo in ('subte', 'tren', 'colectivo_nacional'):
        fila('C. ventana de la apertura', modo, f'{VENTANA[0]} a {VENTANA[1]}', False,
             {'multipago_dic24': SUBTE_CONTACTLESS}, ini=VENTANA[0], fin=VENTANA[1], lags=4)

    # E. Colectivo con todas las jurisdicciones: en 2025 líneas de jurisdicción nacional pasaron a CABA, de modo que
    #    `colectivo_nacional` pierde líneas (ruptura de composición) y no sirve para este chequeo. Se usa la suma de
    #    jurisdicciones con la tarifa del colectivo nacional como aproximación del precio.
    d = usos.loc[M.INICIO:M.FIN, 'colectivo']
    sem = d.index.to_period('W-SUN').start_time
    y['colectivo_total'] = np.log(d.groupby(sem).mean())
    p['colectivo_total'] = p['colectivo_nacional']; pr['colectivo_total'] = pr['colectivo_nacional']
    for con_sal in (False, True):
        fila('E. colectivo total sin escalón', 'colectivo_total', 'completa', con_sal, {})
        fila('E. colectivo total con su fecha (27-mar-2025)', 'colectivo_total', 'completa', con_sal,
             {'contactless_colectivo_mar25': COLECTIVO_CONTACTLESS})
        fila('E. colectivo total con escalón del subte (placebo)', 'colectivo_total', 'completa', con_sal,
             {'multipago_dic24': SUBTE_CONTACTLESS})

    t = pd.DataFrame(filas)
    t.to_csv(os.path.join(M.TABLA_DIR, 'tabla_multipago_fechas.csv'), index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    print(t.drop(columns=['R2']).to_string(index=False))

    # D. Placebo: el mismo escalón en semanas sin evento de pago (la regresión de la ventana C, con ventana de 24 semanas)
    esc = []
    for f in pd.date_range('2023-06-05', '2024-08-26', freq='7D'):
        ini = f - pd.Timedelta(weeks=13); fin = f + pd.Timedelta(weeks=11)
        try:
            r = regresion(y, pr, ctrl, None, 'subte', {'escalon': f}, ini=ini, fin=fin, lags=4)
            esc.append({'semana_escalon': f.date(), 'coef': r.get('escalon'), 'ee': r.get('escalon_ee'), 'semanas': r['semanas']})
        except Exception as e:
            esc.append({'semana_escalon': f.date(), 'coef': np.nan, 'ee': np.nan, 'semanas': 0})
    pl = pd.DataFrame(esc).dropna()
    pl.to_csv(os.path.join(M.TABLA_DIR, 'tabla_multipago_placebo_escalon.csv'), index=False)
    real = t[(t['especificacion'] == 'C. ventana de la apertura') & (t['modo'] == 'subte')]['multipago_dic24'].iloc[0]
    print('\nD. Placebo de escalón (subte, fechas sin evento de pago, jun-2023 a ago-2024):')
    print(pl['coef'].describe().round(3).to_string())
    print('percentiles 5 / 50 / 95:', pl['coef'].quantile([.05, .5, .95]).round(3).tolist())
    print('proporción de placebos con |coeficiente| >= |real| (dos colas):', round(float((pl['coef'].abs() >= abs(real)).mean()), 3))
    print('escalón real (2-dic-2024):', real, '| proporción de placebos con coeficiente <= real:', round(float((pl['coef'] <= real).mean()), 3))


if __name__ == '__main__':
    main()
