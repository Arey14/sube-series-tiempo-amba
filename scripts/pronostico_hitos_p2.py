"""
Pronóstico de los hitos (P-2 aplicada a P-1): ¿qué método anticipa mejor lo que pasa con la demanda en feriados,
paros, elecciones y saltos tarifarios?

Se usan los pronósticos del origen móvil ya calculados (42 cortes de 28 días, julio de 2023 a septiembre de 2026), que
incluyen los días de paro y de elección (en las comparaciones principales de P-2 se excluyen). Ningún modelo recibe
información de paros, elecciones ni precios: solo el pasado y el calendario de feriados.

A. Error en días de hito. Para cada grupo de días y cada método: MAE (millones de usuarios) y "demanda pronosticada
   que no se materializó" = promedio de (pronóstico - real) / pronóstico, en %. Un día ordinario da cerca de 0; un paro
   total da cerca de 100% (se pronosticó un día normal y no hubo demanda).
B. Escenario con el efecto de P-1. Para paros y elecciones, el pronóstico del método se multiplica por el cociente
   típico que midió P-1 para ese tipo de día y ese modo (mediana de los otros días del mismo grupo, dejando afuera el
   día evaluado). Es un pronóstico condicional: "si hay un paro de este tipo, ¿cuánto baja?". Pocos eventos por grupo
   (3 a 6): es una ilustración, no una prueba.
C. Saltos tarifarios. Pronósticos hechos el día anterior a cada salto (pronosticos_antes_del_salto_p2.py): sesgo
   (porcentaje de sobreestimación) y MAPE en los 28 días hábiles posteriores al último aumento, contra el error
   habitual del mismo método a 22-28 días de horizonte. Además, un pronóstico condicional al precio: el del método
   multiplicado por exp(elasticidad x cambio en log de la tarifa real desde el origen), con la elasticidad
   interanual de P-1 (colectivo -0,012; tren -0,043; subte -0,224). La elasticidad se estimó con toda la muestra,
   de modo que el resultado es optimista: solo muestra si incorporar el precio ayuda en el mejor de los casos.
   Se excluye el subte de enero de 2024 (cierre de la línea D) y los saltos anteriores a julio de 2023.

Entradas: data/procesado/pronosticos_p2_folds.csv, pronosticos_p2_{colectivo,tren,subte}_amba.csv, pronosticos_p2_saltos.csv,
          resultados/tablas/tabla_hitos_cociente_dias.csv, tabla_estudio_eventos.csv,
          data/hitos/serie_tarifas_diaria.csv, data/externos/ipc_nacional_indec.csv
Salidas:  resultados/tablas/tabla_p2_hitos_errores.csv, tabla_p2_hitos_escenario.csv, tabla_p2_hitos_tarifas.csv,
          tabla_p2_hitos_tarifas_resumen.csv
          resultados/figuras/fig27_p2_hitos.png
"""

import os
import warnings
import numpy as np
import pandas as pd
import holidays
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')
plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROC = os.path.join(BASE_DIR, "data", "procesado")
TAB = os.path.join(BASE_DIR, "resultados", "tablas")
FIG = os.path.join(BASE_DIR, "resultados", "figuras")
MODELOS = ['naive_7', 'naive_364', 'sarimax', 'prophet', 'gradient_boosting']
MODOS = {'colectivo': 'colectivo_amba', 'tren': 'tren_amba', 'subte': 'subte_amba'}
ELASTICIDAD = {'colectivo': -0.012, 'tren': -0.043, 'subte': -0.224}
SERIE_TARIFA = {'colectivo': 'colectivo_nacional', 'tren': 'tren', 'subte': 'subte'}
PARO_MODOS = {   # quién paró (mismo criterio que hitos_efectos.py)
    '2023-07-07': ['colectivo'], '2024-01-24': ['colectivo', 'tren', 'subte'], '2024-02-21': ['tren'], '2024-04-11': ['colectivo'],
    '2024-05-09': ['colectivo', 'tren', 'subte'], '2024-10-30': ['tren', 'subte'], '2025-04-10': ['tren', 'subte'],
    '2025-05-06': ['colectivo'], '2026-02-19': ['colectivo', 'tren', 'subte']}


def cargar():
    d = {'total': pd.read_csv(os.path.join(PROC, 'pronosticos_p2_folds.csv'), parse_dates=['origen', 'fecha'])}
    for m, f in MODOS.items():
        d[m] = pd.read_csv(os.path.join(PROC, f'pronosticos_p2_{f}.csv'), parse_dates=['origen', 'fecha'])
    for k in d:
        d[k] = d[k][d[k].modelo.isin(MODELOS)].copy()
    return d


def grupos_dias():
    """Fecha -> (grupo, subtipo) para feriados laborables, paros y elecciones del período de prueba."""
    t = pd.read_csv(os.path.join(TAB, 'tabla_hitos_cociente_dias.csv'), parse_dates=['fecha'])
    t = t[t.fecha >= '2023-07-01']
    return t


def metricas(g):
    return pd.Series({'dias': g.fecha.nunique(), 'MAE': g.abs_error.mean(),
                      'no_materializado_pct': ((g.pronostico - g.real) / g.pronostico).mean() * 100})


def main():
    d = cargar()
    t = grupos_dias()
    fer = set(pd.Timestamp(f) for f in holidays.Argentina(years=range(2022, 2028)))
    for k in d:
        d[k]['abs_error'] = (d[k].pronostico - d[k].real).abs()
    eventos = set(t[t.tipo.isin(['paro', 'eleccion'])].fecha)

    # --- A. error en días de hito -----------------------------------------------------------------------------------
    def etiqueta(f, modo):
        r = t[t.fecha == f]
        if len(r):
            r = r.iloc[0]
            if r.tipo == 'feriado':
                return 'feriado laborable'
            if r.tipo == 'eleccion':
                return 'elección ' + ('con gratuidad' if r.subtipo.startswith('con gratuidad') else 'sin gratuidad')
            if r.tipo == 'paro':
                if modo == 'total':
                    return 'paro (cualquier modo)'
                return 'paro: modo que paró' if modo in PARO_MODOS[str(f.date())] else 'paro: modo que no paró'
            return None
        if f in fer or f in eventos or f.dayofweek >= 5:
            return None
        return 'día hábil ordinario'

    filas = []
    for modo, df in d.items():
        df = df.copy()
        df['grupo'] = [etiqueta(f, modo) for f in df.fecha]
        df = df[df.grupo.notna()]
        for (g, m), x in df.groupby(['grupo', 'modelo']):
            r = metricas(x); r['modo'] = modo; r['grupo'] = g; r['modelo'] = m; filas.append(r)
    ta = pd.DataFrame(filas)[['modo', 'grupo', 'modelo', 'dias', 'MAE', 'no_materializado_pct']].round(3)
    ta.to_csv(os.path.join(TAB, 'tabla_p2_hitos_errores.csv'), index=False)
    print('A. Error en días de hito (MAE en millones; % de demanda pronosticada que no se materializó)')
    print(ta.pivot_table(index=['modo', 'grupo'], columns='modelo', values='MAE')[MODELOS].round(3).to_string())

    # --- B. escenario con el efecto de P-1 --------------------------------------------------------------------------
    cod = t[t.tipo.isin(['paro', 'eleccion'])].copy()
    cod['grupo'] = [etiqueta(f, 'x') for f in cod.fecha]
    filas = []
    for modo in MODOS:
        for _, ev in cod.iterrows():
            f = ev.fecha
            if ev.tipo == 'paro':
                rol = 'paró' if modo in PARO_MODOS[str(f.date())] else 'no paró'
                par = [r for _, r in cod[cod.tipo == 'paro'].iterrows() if r.fecha != f and ((modo in PARO_MODOS[str(r.fecha.date())]) == (rol == 'paró'))]
                grupo = f'paro, modo que {rol}'
            else:
                par = [r for _, r in cod[cod.tipo == 'eleccion'].iterrows() if r.fecha != f and r.subtipo.startswith('con') == ev.subtipo.startswith('con')]
                grupo = 'elección ' + ('con gratuidad' if ev.subtipo.startswith('con') else 'sin gratuidad')
            k = float(np.median([r[modo] for r in par]))
            x = d[modo][d[modo].fecha == f]
            for _, r in x.iterrows():
                filas.append({'modo': modo, 'grupo': grupo, 'fecha': f.date(), 'modelo': r.modelo, 'real': r.real, 'pron_base': r.pronostico,
                              'multiplicador': k, 'pron_escenario': r.pronostico * k})
    tb = pd.DataFrame(filas)
    tb['abs_base'] = (tb.pron_base - tb.real).abs(); tb['abs_escenario'] = (tb.pron_escenario - tb.real).abs()
    res = tb.groupby(['modo', 'grupo', 'modelo']).agg(dias=('fecha', 'nunique'), MAE_base=('abs_base', 'mean'), MAE_escenario=('abs_escenario', 'mean'), multiplicador_medio=('multiplicador', 'mean')).reset_index()
    res['reduccion_pct'] = (1 - res.MAE_escenario / res.MAE_base) * 100
    res = res.round(3)
    res.to_csv(os.path.join(TAB, 'tabla_p2_hitos_escenario.csv'), index=False)
    glob = tb.groupby(['grupo', 'modelo'])[['abs_base', 'abs_escenario']].mean()
    glob['reduccion_pct'] = (1 - glob.abs_escenario / glob.abs_base) * 100
    print('\nB. Escenario con el cociente de P-1 (tres modos juntos): MAE sin y con escenario')
    print(glob.round(3).to_string())

    # --- C. saltos tarifarios ------------------------------------------------------------------------------------------
    tar = pd.read_csv(os.path.join(BASE_DIR, 'data', 'hitos', 'serie_tarifas_diaria.csv'), parse_dates=['fecha']).pivot(index='fecha', columns='serie', values='tarifa')
    ipc = pd.read_csv(os.path.join(BASE_DIR, 'data', 'externos', 'ipc_nacional_indec.csv'), parse_dates=['indice_tiempo']).set_index('indice_tiempo').iloc[:, 0]
    ipc_d = ipc.reindex(ipc.index.union(tar.index)).ffill().reindex(tar.index)
    real = tar.div(ipc_d, axis=0)
    sal = pd.read_csv(os.path.join(PROC, 'pronosticos_p2_saltos.csv'), parse_dates=['salto_desde', 'salto_hasta', 'origen', 'fecha'])
    sal = sal[(sal.salto_desde >= '2023-07-01') & ~((sal.modo == 'subte') & (sal.salto_desde == '2024-01-05'))]   # subte ene-2024: cierre de la línea D
    filas = []
    for (modo, desde), g in sal.groupby(['modo', 'salto_desde']):
        serie_t = {'colectivo': 'colectivo_nacional', 'tren': 'tren', 'subte': 'subte'}[modo]
        g = g.copy()
        g['ln_real'] = np.log(real[serie_t].reindex(g.fecha).values)
        g['ln_real_origen'] = np.log(real[serie_t].reindex(g.origen).values)
        g['pron_precio'] = g.pronostico * np.exp(ELASTICIDAD[modo] * (g.ln_real - g.ln_real_origen))
        g['habil'] = (g.fecha.dt.dayofweek < 5) & ~g.fecha.isin(fer) & ~g.fecha.isin(eventos)
        hasta = g.salto_hasta.iloc[0]
        ven = g[g.habil & (g.fecha > hasta) & (g.fecha <= hasta + pd.Timedelta(days=28))]
        for m, x in ven.groupby('modelo'):
            # error habitual del mismo modelo y modo a 22-28 días de horizonte (origen móvil de 28 días, días hábiles sin atípicos)
            b = d[modo][(d[modo].modelo == m) & (d[modo].h >= 22)].copy()
            b = b[(b.fecha.dt.dayofweek < 5) & ~b.fecha.isin(fer) & ~b.fecha.isin(eventos)]
            sesgo = lambda df, c: ((df[c] - df.real) / df.real).mean() * 100
            mape = lambda df, c: (((df[c] - df.real).abs()) / df.real).mean() * 100
            filas.append({'modo': modo, 'salto_desde': desde.date(), 'tarifa_x': x.tarifa_x.iloc[0], 'cambio_demanda_pct_P1': x.cambio_demanda_pct_P1.iloc[0],
                          'modelo': m, 'dias_ventana': len(x), 'sobreestimacion_pct': sesgo(x, 'pronostico'), 'sobreestimacion_pct_habitual': sesgo(b, 'pronostico'),
                          'MAPE': mape(x, 'pronostico'), 'MAPE_habitual': mape(b, 'pronostico'),
                          'sobreestimacion_pct_con_precio': sesgo(x, 'pron_precio'), 'MAPE_con_precio': mape(x, 'pron_precio')})
    tc = pd.DataFrame(filas).round(2)
    tc.to_csv(os.path.join(TAB, 'tabla_p2_hitos_tarifas.csv'), index=False)
    print('\nC. Saltos tarifarios: pronóstico hecho el día anterior; sobreestimación (%) en los 28 días hábiles siguientes al último aumento')
    print(tc[tc.modelo == 'gradient_boosting'].to_string(index=False))
    rs = tc.assign(grande=tc.tarifa_x >= 3).groupby(['grande', 'modelo'])[['sobreestimacion_pct', 'sobreestimacion_pct_habitual', 'MAPE', 'MAPE_habitual', 'MAPE_con_precio']].mean().round(2)
    print('\nPromedio por tipo de salto (grande = tarifa x3 o más)'); print(rs.to_string())
    rs.to_csv(os.path.join(TAB, 'tabla_p2_hitos_tarifas_resumen.csv'))

    # --- figura -----------------------------------------------------------------------------------------------------
    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    p = ta[(ta.modo == 'total')].pivot(index='grupo', columns='modelo', values='MAE')[MODELOS]
    p = p.loc[['día hábil ordinario', 'feriado laborable', 'paro (cualquier modo)', 'elección con gratuidad', 'elección sin gratuidad']]
    p.plot(kind='bar', ax=ax[0], width=0.8); ax[0].set_ylabel('MAE (millones de usuarios)'); ax[0].set_xlabel('')
    ax[0].set_title('Total AMBA: error según tipo de día', fontweight='bold'); ax[0].tick_params(axis='x', rotation=20); ax[0].legend(fontsize=8)
    q = glob.reset_index(); q = q[q.modelo == 'gradient_boosting'].set_index('grupo')[['abs_base', 'abs_escenario']]
    q.columns = ['sin escenario', 'con el cociente de P-1']
    q.plot(kind='bar', ax=ax[1], width=0.7, color=['#c0392b', '#27ae60']); ax[1].set_ylabel('MAE por modo (millones)'); ax[1].set_xlabel('')
    ax[1].set_title('Gradient Boosting en días de paro y elección:\nefecto de usar el cociente medido en P-1', fontweight='bold'); ax[1].tick_params(axis='x', rotation=20)
    plt.tight_layout(); plt.savefig(os.path.join(FIG, 'fig27_p2_hitos.png'), dpi=200); plt.close()


if __name__ == '__main__':
    main()
