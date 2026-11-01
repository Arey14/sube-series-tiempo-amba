"""
Hipótesis H-ingreso: ¿las líneas de subte que sirven a zonas de mayor ingreso reaccionan menos a la tarifa?
(pre-registrada en docs/interpretacion_resultados.md, bloques 3 y 5).

La tarifa del subte es la misma para todas las líneas. Un panel (línea x semana) con efecto fijo por semana absorbe
todo lo que afecta a todas las líneas por igual (inflación, ingreso general, estación, feriados, paros, el propio
efecto promedio del precio). Lo que queda identifica cuánto cambia la respuesta al precio según el ingreso de la
línea:

    log(usos medios diarios de la línea l en la semana s) = efecto de línea l + efecto de semana s
                                                           + delta * z_l * log(tarifa real de la semana s) + error

donde z_l es el índice de ingreso de la línea (centrado). La hipótesis predice delta > 0: las líneas de más ingreso
reaccionan menos (la elasticidad de la línea es la del subte entero más delta * z_l).

Especificaciones:
  1. índice continuo z_l (2022-2025);
  2. contraste simple: línea D contra el promedio de A, B, C y E (la H queda afuera);
  3. cada una con y sin tendencia lineal propia de cada línea;
  4. p-valor de permutación: se reparten los índices entre las líneas de todas las maneras posibles (720) y se mira
     qué tan extremo es el delta observado. Con solo seis líneas, los errores estándar agrupados son poco confiables.
La línea D se excluye entre el 8-ene-2024 y el 10-mar-2024 (cierre por obras). Sensibilidad: hasta el 30-abr-2024.

Además, estudio de eventos por línea en los saltos del subte (mismo método que modelo_precio_demanda.py).

Entradas: data/procesado/usos_diarios_subte_por_linea.csv, resultados/tablas/tabla_lineas_subte_ingreso.csv,
          y las de modelo_precio_demanda.py
Salidas:  resultados/tablas/tabla_panel_subte_delta.csv, tabla_eventos_subte_por_linea.csv,
          resultados/figuras/fig15_eventos_subte_por_linea.png
"""

import itertools
import os
import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modelo_precio_demanda as m   # noqa: E402

plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = m.BASE_DIR
LINEAS_CSV = os.path.join(BASE_DIR, "data", "procesado", "usos_diarios_subte_por_linea.csv")
INDICE_CSV = os.path.join(BASE_DIR, "resultados", "tablas", "tabla_lineas_subte_ingreso.csv")
LINEAS = ['A', 'B', 'C', 'D', 'E', 'H']
CIERRE_D = ('2024-01-08', '2024-03-10')
CIERRE_D_AMPLIADO = ('2024-01-08', '2024-04-30')


def cargar_lineas():
    lin = pd.read_csv(LINEAS_CSV, parse_dates=['fecha']).set_index('fecha')[LINEAS]
    z = pd.read_csv(INDICE_CSV).set_index('linea')['indice_comuna_2022_2025'].reindex(LINEAS)
    return lin, z


def semanal_lineas(lin, pr_subte):
    d = lin.loc[m.INICIO:m.FIN]
    semana = d.index.to_period('W-SUN').start_time
    y = np.log(d.groupby(semana).mean())
    return y, pr_subte


def panel(y, p, z, cierre, contraste=False, tendencia=False, permutar=None):
    """Devuelve delta (coeficiente de log tarifa x indicador de la línea) y su error estándar HAC."""
    y = y.copy()
    y.loc[cierre[0]:cierre[1], 'D'] = np.nan
    largo = y.stack().rename('y').reset_index()
    largo.columns = ['semana', 'linea', 'y']
    largo = largo.dropna(subset=['y'])
    zz = (permutar if permutar is not None else z)
    if contraste:
        zz = pd.Series({l: (1.0 if l == 'D' else 0.0) for l in LINEAS if l != 'H'})
        largo = largo[largo.linea.isin(zz.index)]
        if permutar is not None:
            zz = permutar
    else:
        zz = zz - zz.mean()
    largo['inter'] = largo['linea'].map(zz) * largo['semana'].map(p)
    X = pd.get_dummies(largo[['linea']], drop_first=False).astype(float)
    S = pd.get_dummies(largo['semana'], prefix='s', drop_first=True).astype(float)
    cols = [X, S, largo[['inter']]]
    if tendencia:
        t = (largo['semana'] - largo['semana'].min()).dt.days / 365.25
        cols.append(pd.DataFrame({f'tend_{l}': (largo['linea'] == l).astype(float) * t for l in sorted(largo.linea.unique())[1:]}))
    XX = pd.concat(cols, axis=1)
    res = sm.OLS(largo['y'].values, XX.values).fit(cov_type='cluster', cov_kwds={'groups': largo['semana'].factorize()[0]})
    i = list(XX.columns).index('inter')
    return res.params[i], res.bse[i], len(largo)


def permutaciones(y, p, z, cierre, contraste, tendencia):
    obs, ee, n = panel(y, p, z, cierre, contraste, tendencia)
    base = z if not contraste else pd.Series({l: (1.0 if l == 'D' else 0.0) for l in LINEAS if l != 'H'})
    valores = list(base.values)
    vistos = set(); deltas = []
    for perm in itertools.permutations(range(len(valores))):
        clave = tuple(round(valores[i], 6) for i in perm)
        if clave in vistos:
            continue
        vistos.add(clave)
        nuevo = pd.Series([valores[i] for i in perm], index=base.index)
        deltas.append(panel(y, p, z, cierre, contraste, tendencia, permutar=nuevo)[0])
    deltas = np.array(deltas)
    return obs, ee, n, float((np.abs(deltas) >= abs(obs) - 1e-12).mean()), len(deltas)


def normal_semanal(lin, evt):
    """Usos medios por línea de días hábiles normales (sin feriado, paro ni elección), con al menos 3 días por semana."""
    import holidays
    d = lin.loc[m.INICIO:m.FIN].copy()
    d.loc[CIERRE_D[0]:CIERRE_D[1], 'D'] = np.nan
    fer = holidays.Argentina(years=range(2021, 2027))
    dias_evt = set(evt['fecha'])
    normal = pd.Series([(f.day_of_week < 5) and (f not in fer) and (f not in dias_evt) for f in d.index], index=d.index)
    dn = d.where(normal, np.nan)
    semana = d.index.to_period('W-SUN').start_time
    cuenta = dn.notna().groupby(semana).sum()
    return np.log(dn.groupby(semana).mean()).where(cuenta >= 3)


def eventos_por_linea(lin, evt, pr_subte, z):
    yh = normal_semanal(lin, evt)
    pdf = pd.DataFrame({l: pr_subte for l in LINEAS})
    saltos = [(s, a, b) for s, a, b in m.eventos_salto() if s == 'subte']
    filas = []
    for _, a, b in saltos:
        for l in LINEAS:
            e = m.estudio_evento(yh, pdf, set(), l, a, b)
            e['linea'] = l; e['indice_ingreso'] = round(z[l], 3)
            filas.append(e)
    t = pd.DataFrame(filas).dropna(subset=['dlog_demanda_neto'])
    return t.rename(columns={'dlog_tarifa': 'dlog_tarifa_real', 'tarifa_x': 'tarifa_real_x'})


def graficar(t_ev):
    eventos = t_ev[['desde', 'hasta']].drop_duplicates().values.tolist()
    fig, axs = plt.subplots(1, len(eventos), figsize=(4 * len(eventos), 4), sharey=True)
    for ax, (d0, d1) in zip(np.atleast_1d(axs), eventos):
        g = t_ev[(t_ev.desde == d0) & (t_ev.hasta == d1)].sort_values('indice_ingreso')
        ax.bar(g.linea, g.dlog_demanda_neto, color=['#c0392b' if l == 'D' else '#7f8c8d' for l in g.linea])
        ax.axhline(0, color='k', lw=0.6)
        ax.set_title(f'{pd.Timestamp(d0):%m/%y}  (tarifa real x{g.tarifa_real_x.iloc[0]})', fontsize=10)
    np.atleast_1d(axs)[0].set_ylabel('Cambio neto de la demanda (log)\n(líneas ordenadas por ingreso, menor a mayor)')
    plt.suptitle('Respuesta de cada línea de subte a los saltos tarifarios', fontweight='bold')
    plt.tight_layout(); plt.savefig(os.path.join(m.FIG_DIR, 'fig15_eventos_subte_por_linea.png'), dpi=200); plt.close()


def main():
    usos, tar, evt = m.cargar()
    y_all, p_all, ctrl, yh, pr = m.semanal(usos, tar, evt)
    lin, z = cargar_lineas()
    pr_subte = pr['subte']
    y, _ = semanal_lineas(lin, pr_subte)
    print('Índice de ingreso por línea:', z.round(3).to_dict())

    filas = []
    for cierre_nom, cierre in [('cierre', CIERRE_D), ('cierre ampliado', CIERRE_D_AMPLIADO)]:
        for contraste in (False, True):
            for tend in (False, True):
                d, ee, n, pv, nperm = permutaciones(y, pr_subte, z, cierre, contraste, tend)
                filas.append({'definicion_D_excluida': cierre_nom, 'especificacion': 'D contra A,B,C,E' if contraste else 'indice continuo',
                              'tendencia_por_linea': tend, 'observaciones': n, 'delta': round(d, 3), 'error_std': round(ee, 3),
                              'p_permutacion': round(pv, 3), 'n_permutaciones': nperm})
    t = pd.DataFrame(filas)
    t.to_csv(os.path.join(m.TABLA_DIR, 'tabla_panel_subte_delta.csv'), index=False)
    print('\nPanel línea x semana, efecto fijo por semana'); print(t.to_string(index=False))

    t_ev = eventos_por_linea(lin, evt, pr_subte, z)
    t_ev.to_csv(os.path.join(m.TABLA_DIR, 'tabla_eventos_subte_por_linea.csv'), index=False)
    cols = ['desde', 'hasta', 'tarifa_real_x', 'linea', 'indice_ingreso', 'dlog_demanda_neto', 'cambio_demanda_pct']
    print('\nEventos por línea'); print(t_ev[cols].to_string(index=False))
    graficar(t_ev)


if __name__ == '__main__':
    main()
