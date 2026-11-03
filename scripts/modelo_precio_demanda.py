"""
Modelo de precio y demanda (pregunta P-1): cómo responde la demanda a las tarifas.

Salidas de demanda: transacciones diarias (usos) por modo, sin huecos (usos_transacciones.py).
Precio: tarifa mínima con SUBE registrada vigente cada día (tarifas_serie.py).
Período: marzo de 2022 a septiembre de 2026 (octubre es preliminar y no entra).

Tres estimaciones por modo, con supuestos distintos:
  A. Niveles semanales: log(usos) contra log(tarifa) con efectos de mes del año, feriados, paros y
     elecciones. Sin tendencia, el precio absorbe todo lo que crece o cae con el tiempo; con tendencia lineal
     solo queda la variación de precio que se aparta de la tendencia. Se muestran las dos.
  B. Diferencias interanuales (52 semanas): quita estacionalidad y el nivel; la elasticidad sale de cómo cambia
     la caída interanual cuando cambia la tarifa interanual.
  C. Estudio de eventos: para cada salto (agrupando los que están a menos de 45 días) se compara el cambio de
     la demanda antes y después con el mismo cambio un año antes ("diferencia en diferencias estacional"). La
     elasticidad de arco es el cociente entre el cambio en log de la demanda y el cambio en log de la tarifa.
     Como prueba de placebo, se calcula el mismo cociente en fechas donde no cambió el precio.

  D. Control por salario real: se repite A y B agregando el salario real (RIPTE deflactado por IPC) como
     regresora, y se estima la elasticidad con la tarifa medida en salarios (tarifa / RIPTE). Responde si la
     elasticidad cambia cuando se tiene en cuenta que el poder de compra del salario se movió al mismo tiempo.

Son estimaciones de asociación con controles, no un experimento: dependen de que los controles absorban lo que se
movió al mismo tiempo que la tarifa (inflación, ingreso, devaluación, tarifas de otros modos).

Entradas: data/procesado/usos_diarios_amba.csv, data/hitos/serie_tarifas_diaria.csv,
          data/hitos/hitos_tarifas.csv, data/hitos/hitos_paros_elecciones.csv,
          data/externos/ipc_nacional_indec.csv, data/externos/ripte_mensual.csv
Salidas:  resultados/tablas/tabla_elasticidad_niveles.csv, tabla_elasticidad_interanual.csv,
          tabla_elasticidad_control_salario.csv, tabla_estudio_eventos.csv, tabla_placebo_eventos.csv
          resultados/figuras/fig14_estudio_eventos.png
"""

import os
import numpy as np
import pandas as pd
import holidays
import statsmodels.api as sm
import matplotlib.pyplot as plt

plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
USOS = os.path.join(BASE_DIR, "data", "procesado", "usos_diarios_amba.csv")
TAR_D = os.path.join(BASE_DIR, "data", "hitos", "serie_tarifas_diaria.csv")
TAR_H = os.path.join(BASE_DIR, "data", "hitos", "hitos_tarifas.csv")
EVT = os.path.join(BASE_DIR, "data", "hitos", "hitos_paros_elecciones.csv")
IPC = os.path.join(BASE_DIR, "data", "externos", "ipc_nacional_indec.csv")
RIPTE = os.path.join(BASE_DIR, "data", "externos", "ripte_mensual.csv")
SUBTE_LINEAS = os.path.join(BASE_DIR, "data", "procesado", "usos_diarios_subte_por_linea.csv")
TABLA_DIR = os.path.join(BASE_DIR, "resultados", "tablas")
FIG_DIR = os.path.join(BASE_DIR, "resultados", "figuras")

INICIO, FIN = '2022-03-07', '2026-09-27'          # lunes a domingo
INICIO_PROV = '2024-02-05'                          # la tarifa provincial se conoce desde la adhesión a la Res. 5/2024
MODOS = ['colectivo_nacional', 'colectivo_provincial', 'tren', 'subte']
SEMANAS_ANIO = 52
UMBRAL_AGRUPAR_DIAS = 45


def cargar():
    usos = pd.read_csv(USOS, parse_dates=['fecha']).set_index('fecha').asfreq('D')
    tar = pd.read_csv(TAR_D, parse_dates=['fecha']).pivot(index='fecha', columns='serie', values='tarifa')
    evt = pd.read_csv(EVT, parse_dates=['fecha'])
    # el subte se modela sin la línea D: estuvo cerrada del 8-ene al 6-mar de 2024 y ese cierre no es una respuesta al precio
    lineas = pd.read_csv(SUBTE_LINEAS, parse_dates=['fecha']).set_index('fecha')
    usos['subte'] = lineas['subte_sin_D'].reindex(usos.index)
    return usos, tar, evt


def deflactor_diario(indice):
    """IPC nacional (INDEC) asignado a cada día de su mes. Si falta el último mes, se prolonga con la variación del anterior."""
    ipc = pd.read_csv(IPC, parse_dates=['indice_tiempo']).set_index('indice_tiempo').iloc[:, 0]
    while ipc.index[-1] < indice[-1].to_period('M').to_timestamp():
        ipc.loc[ipc.index[-1] + pd.offsets.MonthBegin(1)] = ipc.iloc[-1] * ipc.iloc[-1] / ipc.iloc[-2]
    d = ipc.reindex(ipc.index.union(indice)).ffill().reindex(indice)
    return d / d.iloc[0]


def ripte_diario(indice):
    """RIPTE mensual (Secretaría de Trabajo) asignado a cada día de su mes; los meses sin dato repiten el último salario real."""
    ipc = pd.read_csv(IPC, parse_dates=['indice_tiempo']).set_index('indice_tiempo').iloc[:, 0]
    rip = pd.read_csv(RIPTE, parse_dates=['indice_tiempo']).set_index('indice_tiempo')['ripte']
    # el último mes publicado repite el anterior (valor provisorio): se descarta
    rip = rip.iloc[:-1] if rip.iloc[-1] == rip.iloc[-3] else rip
    real = (rip / ipc).dropna()
    nominal = rip.reindex(rip.index.union(indice)).ffill().reindex(indice)
    real_d = real.reindex(real.index.union(indice)).ffill().reindex(indice)
    return nominal / nominal.iloc[0], real_d / real_d.iloc[0]


def semanal(usos, tar, evt):
    """Panel semanal (semanas de lunes a domingo): log de los usos medios diarios y log de la tarifa media."""
    d = usos.loc[INICIO:FIN, MODOS].copy()
    semana = d.index.to_period('W-SUN').start_time
    y = np.log(d.groupby(semana).mean())
    p = np.log(tar.loc[INICIO:FIN, MODOS].groupby(semana).mean())
    defl = deflactor_diario(d.index)
    pr = np.log((tar.loc[INICIO:FIN, MODOS].div(defl, axis=0)).groupby(semana).mean())
    feriados = holidays.Argentina(years=range(2021, 2027))
    es_fer = pd.Series([(f in feriados) and f.day_of_week < 5 for f in d.index], index=d.index)
    ctrl = pd.DataFrame({'feriados_habiles': es_fer.groupby(semana).sum().astype(float)})
    for tipo in ['paro', 'eleccion']:
        marc = pd.Series(0.0, index=ctrl.index)
        for f in evt.loc[evt.tipo == tipo, 'fecha']:
            ini = f.to_period('W-SUN').start_time
            if ini in marc.index:
                marc[ini] = 1.0
        ctrl[tipo] = marc
    ctrl['mes'] = ctrl.index.month
    # demanda de días hábiles "normales": lunes a viernes sin feriado, paro ni elección (al menos 3 días por semana)
    dias_evento = set(evt['fecha'])
    normal = pd.Series([(f.day_of_week < 5) and (f not in feriados) and (f not in dias_evento) for f in d.index], index=d.index)
    dn = d.where(normal, np.nan)
    cuenta = dn.notna().groupby(semana).sum()
    yh = np.log(dn.groupby(semana).mean()).where(cuenta >= 3)
    return y, p, ctrl, yh, pr


def _hac(res_modelo, lags=8):
    return res_modelo.get_robustcov_results(cov_type='HAC', maxlags=lags)


def niveles(y, p, ctrl, precio='nominal', sal=None):
    filas = []
    meses = pd.get_dummies(ctrl['mes'], prefix='m', drop_first=True).astype(float)
    for m in MODOS:
        ini = pd.Timestamp(INICIO_PROV) if m == 'colectivo_provincial' else y.index[0]
        idx = y.index[y.index >= ini]
        for con_tendencia in (False, True):
            X = pd.concat([p.loc[idx, [m]].rename(columns={m: 'log_tarifa'}),
                           ctrl.loc[idx, ['feriados_habiles', 'paro', 'eleccion']], meses.loc[idx]], axis=1)
            if con_tendencia:
                X['tendencia_anios'] = (idx - idx[0]).days / 365.25
            if sal is not None:
                X['log_salario_real'] = sal.loc[idx]
            X = sm.add_constant(X)
            res = _hac(sm.OLS(y.loc[idx, m], X).fit())
            i = list(X.columns).index('log_tarifa')
            filas.append({'precio': precio, 'control_salario': sal is not None, 'modo': m, 'con_tendencia': con_tendencia, 'semanas': len(idx),
                          'elasticidad': round(res.params[i], 3), 'error_std_HAC': round(res.bse[i], 3),
                          'ic95_inf': round(res.params[i] - 1.96 * res.bse[i], 3),
                          'ic95_sup': round(res.params[i] + 1.96 * res.bse[i], 3), 'R2': round(res.rsquared, 3)})
    return pd.DataFrame(filas)


def interanual(y, p, ctrl, precio='nominal', sal=None):
    filas = []
    for m in MODOS:
        dy = y[m] - y[m].shift(SEMANAS_ANIO)
        dp = p[m] - p[m].shift(SEMANAS_ANIO)
        X = pd.DataFrame({'dlog_tarifa': dp, 'dferiados': ctrl['feriados_habiles'] - ctrl['feriados_habiles'].shift(SEMANAS_ANIO),
                          'dparo': ctrl['paro'] - ctrl['paro'].shift(SEMANAS_ANIO),
                          'deleccion': ctrl['eleccion'] - ctrl['eleccion'].shift(SEMANAS_ANIO)})
        if sal is not None:
            X['dlog_salario_real'] = sal - sal.shift(SEMANAS_ANIO)
        ini = pd.Timestamp(INICIO_PROV) + pd.Timedelta(weeks=SEMANAS_ANIO) if m == 'colectivo_provincial' else None
        datos = pd.concat([dy.rename('dy'), X], axis=1).dropna()
        if ini is not None:
            datos = datos[datos.index >= ini]
        res = _hac(sm.OLS(datos['dy'], sm.add_constant(datos.drop(columns='dy'))).fit())
        i = 1
        filas.append({'precio': precio, 'control_salario': sal is not None, 'modo': m, 'semanas': len(datos), 'elasticidad': round(res.params[i], 3),
                      'error_std_HAC': round(res.bse[i], 3), 'ic95_inf': round(res.params[i] - 1.96 * res.bse[i], 3),
                      'ic95_sup': round(res.params[i] + 1.96 * res.bse[i], 3), 'R2': round(res.rsquared, 3)})
    return pd.DataFrame(filas)


def eventos_salto():
    h = pd.read_csv(TAR_H, parse_dates=['fecha_vigencia'])
    h = h[(h.tipo == 'salto') & (h.serie.isin(MODOS))].sort_values(['serie', 'fecha_vigencia'])
    eventos = []
    for s, g in h.groupby('serie'):
        grupo = []
        for f in g['fecha_vigencia']:
            if grupo and (f - grupo[-1]).days > UMBRAL_AGRUPAR_DIAS:
                eventos.append((s, grupo[0], grupo[-1])); grupo = []
            grupo.append(f)
        if grupo:
            eventos.append((s, grupo[0], grupo[-1]))
    return eventos


def cambio_ventana(serie, ini_pre, fin_pre, ini_post, fin_post, ex):
    """Diferencia entre el log medio de la ventana posterior y el de la anterior; descarta semanas con feriado/paro/elección."""
    pre = serie.loc[ini_pre:fin_pre]; post = serie.loc[ini_post:fin_post]
    pre = pre.dropna(); post = post.dropna()
    if len(pre) < 3 or len(post) < 3:
        return np.nan
    return post.mean() - pre.mean()


def estudio_evento(y, p, ex, modo, f_ini, f_fin, pre=6, gap_post=1, post=6, anios=1):
    """Diferencia en diferencias estacional: cambio de demanda esta vez menos el mismo cambio un año antes."""
    s0 = f_ini.to_period('W-SUN').start_time
    s1 = f_fin.to_period('W-SUN').start_time
    w = pd.Timedelta(weeks=1)
    def ventanas(desp):
        a = s0 - desp
        b = s1 - desp
        return (a - pre * w, a - w, b + (1 + gap_post) * w, b + (gap_post + post) * w)
    v = ventanas(pd.Timedelta(0)); v_prev = ventanas(pd.Timedelta(weeks=SEMANAS_ANIO * anios))
    dy = cambio_ventana(y[modo], *v, ex)
    dy_prev = cambio_ventana(y[modo], *v_prev, ex)
    dp = cambio_ventana(p[modo], v[0], v[1], v[2], v[3], set())
    dp_prev = cambio_ventana(p[modo], *v_prev, set())
    dif = dy - dy_prev
    dp_neto = dp - (0 if np.isnan(dp_prev) else dp_prev)
    return {'modo': modo, 'desde': f_ini.date(), 'hasta': f_fin.date(), 'dlog_tarifa': round(dp_neto, 3),
            'tarifa_x': round(float(np.exp(dp_neto)), 2), 'dlog_demanda': round(dy, 3), 'dlog_demanda_1_anio_antes': round(dy_prev, 3),
            'dlog_demanda_neto': round(dif, 3), 'cambio_demanda_pct': round((np.exp(dif) - 1) * 100, 1),
            'elasticidad_arco': round(dif / dp_neto, 3) if abs(dp_neto) > 1e-9 else np.nan}


def placebo(y, p, ex, modo, saltos, n=400, seed=0, min_semanas_a_salto=10):
    """Mismo cociente en fechas sin cambio de precio (|d log tarifa| < 0,02): distribución del 'efecto' sin tratamiento."""
    rng = np.random.default_rng(seed)
    fechas = y.index[(y.index >= y.index[0] + pd.Timedelta(weeks=SEMANAS_ANIO + 8)) & (y.index <= y.index[-1] - pd.Timedelta(weeks=9))]
    saltos_modo = [pd.Timestamp(f) for m, f, _ in saltos if m == modo]
    res = []
    for f in pd.DatetimeIndex(rng.permutation(fechas)[:n * 4]):
        if any(abs((f - s).days) < min_semanas_a_salto * 7 for s in saltos_modo):
            continue
        e = estudio_evento(y, p, ex, modo, f, f)
        if np.isnan(e['dlog_demanda_neto']) or abs(e['dlog_tarifa']) > 0.02:
            continue
        res.append(e['dlog_demanda_neto'])
        if len(res) >= n:
            break
    r = np.array(res)
    return {'modo': modo, 'n_placebos': len(r), 'p05_dlog_demanda': round(np.quantile(r, 0.05), 3) if len(r) else np.nan,
            'p95_dlog_demanda': round(np.quantile(r, 0.95), 3) if len(r) else np.nan, 'sd_dlog_demanda': round(r.std(), 3) if len(r) else np.nan}


def graficar(y, filas_ev):
    ev = pd.DataFrame(filas_ev)
    ev = ev[ev.dlog_tarifa.abs() > 0.15].sort_values('dlog_tarifa')
    fig, ax = plt.subplots(figsize=(10, 5.5))
    col = {'colectivo_nacional': '#2980b9', 'colectivo_provincial': '#8e44ad', 'tren': '#27ae60', 'subte': '#e67e22'}
    for _, r in ev.iterrows():
        ax.scatter(r.dlog_tarifa, r.dlog_demanda_neto, s=70, color=col[r.modo])
        ax.annotate(f"{r.modo.replace('colectivo_', 'col. ')} {pd.Timestamp(r.desde):%m/%y}", (r.dlog_tarifa, r.dlog_demanda_neto),
                    fontsize=7, xytext=(4, 4), textcoords='offset points')
    ax.axhline(0, color='k', lw=0.6)
    ax.set_xlabel('Cambio en log de la tarifa'); ax.set_ylabel('Cambio en log de la demanda\n(neto de lo ocurrido un año antes)')
    ax.set_title('Estudio de eventos: saltos tarifarios y respuesta de la demanda', fontweight='bold')
    plt.tight_layout(); plt.savefig(os.path.join(FIG_DIR, 'fig14_estudio_eventos.png'), dpi=200); plt.close()


def main():
    usos, tar, evt = cargar()
    y, p, ctrl, yh, pr = semanal(usos, tar, evt)
    ex = set()

    t_niv = pd.concat([niveles(y, p, ctrl, 'nominal'), niveles(y, pr, ctrl, 'real')], ignore_index=True); t_niv.to_csv(os.path.join(TABLA_DIR, 'tabla_elasticidad_niveles.csv'), index=False)
    t_ia = pd.concat([interanual(y, p, ctrl, 'nominal'), interanual(y, pr, ctrl, 'real')], ignore_index=True); t_ia.to_csv(os.path.join(TABLA_DIR, 'tabla_elasticidad_interanual.csv'), index=False)
    print('A. Niveles (con y sin tendencia)'); print(t_niv.to_string(index=False))
    print('\nB. Diferencias interanuales'); print(t_ia.to_string(index=False))

    # D. control por salario real y tarifa medida en salarios
    d_idx = usos.loc[INICIO:FIN].index
    semana = d_idx.to_period('W-SUN').start_time
    rip_nom, rip_real = ripte_diario(d_idx)
    sal = np.log(rip_real.groupby(semana).mean())
    p_sal = np.log((tar.loc[INICIO:FIN, MODOS].div(rip_nom, axis=0)).groupby(semana).mean())
    t_sal = pd.concat([niveles(y, pr, ctrl, 'real', sal), interanual(y, pr, ctrl, 'real', sal),
                       niveles(y, p_sal, ctrl, 'en salarios (RIPTE)'), interanual(y, p_sal, ctrl, 'en salarios (RIPTE)')], ignore_index=True)
    t_sal.insert(0, 'metodo', np.where(t_sal['con_tendencia'].isna(), 'interanual', 'niveles'))
    t_sal.to_csv(os.path.join(TABLA_DIR, 'tabla_elasticidad_control_salario.csv'), index=False)
    print('\nD. Control por salario real (RIPTE / IPC) y tarifa en salarios'); print(t_sal.to_string(index=False))

    saltos = eventos_salto()
    filas = []
    for m, a, b in saltos:
        if not (pd.Timestamp(a) - pd.Timedelta(weeks=SEMANAS_ANIO + 8) >= y.index[0] and pd.Timestamp(b) <= y.index[-1] - pd.Timedelta(weeks=8)):
            continue
        e = estudio_evento(yh, p, ex, m, a, b)
        er = estudio_evento(yh, pr, ex, m, a, b)
        e['dlog_tarifa_real'] = er['dlog_tarifa']
        e['elasticidad_arco_real'] = er['elasticidad_arco']
        filas.append(e)
    t_ev = pd.DataFrame(filas)
    t_ev.to_csv(os.path.join(TABLA_DIR, 'tabla_estudio_eventos.csv'), index=False)
    print('\nC. Estudio de eventos'); print(t_ev.to_string(index=False))
    t_pl = pd.DataFrame([placebo(yh, p, ex, m, saltos) for m in MODOS if m != 'colectivo_provincial'])
    t_pl.to_csv(os.path.join(TABLA_DIR, 'tabla_placebo_eventos.csv'), index=False)
    print('\nPlacebo (fechas sin cambio de precio)'); print(t_pl.to_string(index=False))
    graficar(yh, filas)


if __name__ == '__main__':
    main()
