"""
Transacciones diarias de SUBE (dataset "usos") y reconstrucción de los usuarios en los huecos.

La serie de usuarios (tarjetas distintas por día) tiene dos meses faltantes: agosto de 2022 y
enero de 2024. El portal publica además la cantidad de TRANSACCIONES por día, línea y jurisdicción
(un CSV por año), sin huecos. Usuarios y transacciones están muy correlacionados, así que los
usuarios de los días faltantes se estiman como transacciones x razón usuarios/transacciones, con la
razón tomada de los días vecinos.

Fuente: https://datos.transporte.gob.ar/dataset/sube-cantidad-de-transacciones-usos-por-fecha

Salidas:
  data/procesado/usos_diarios_amba.csv                 transacciones por día y serie
  data/procesado/serie_sube_diaria_reconstruida.csv    usuarios con los huecos reconstruidos (`imputado`)
  resultados/tablas/tabla_reconstruccion_usuarios.csv  error de la reconstrucción vs. interpolación
  resultados/figuras/fig12_reconstruccion_huecos.png

Los CSV originales (~60 MB por año) se guardan en data/raw_usos/ y no se versionan.
"""

import os
import sys
import urllib.request
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
import calidad_datos as cd

plt.style.use('seaborn-v0_8-whitegrid')

BASE_DIR = cd.BASE_DIR
RAW_DIR = os.path.join(BASE_DIR, "data", "raw_usos")
PROC_DIR = cd.PROC_DIR
FIG_DIR = cd.FIG_DIR
TABLA_DIR = cd.TABLA_DIR
URL_USOS = "https://archivos-datos.transporte.gob.ar/upload/Dat_Ab_Usos/dat-ab-usos-{anio}.csv"
ANIOS = range(2020, 2027)

# columna de usuarios -> columna de transacciones equivalente
PARES = {'total_amba': 'total_usos', 'colectivo_amba': 'colectivo',
         'subte_amba': 'subte', 'tren_amba': 'tren'}


def descargar_usos(anios=ANIOS, forzar=False):
    os.makedirs(RAW_DIR, exist_ok=True)
    for a in anios:
        destino = os.path.join(RAW_DIR, f"dat-ab-usos-{a}.csv")
        if os.path.exists(destino) and not forzar:
            continue
        print(f"Descargando {a}...")
        req = urllib.request.Request(URL_USOS.format(anio=a), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as resp, open(destino, "wb") as f:
            f.write(resp.read())


def agregar_usos(anios=ANIOS):
    """Transacciones por día y serie. Colectivo y tren: solo líneas marcadas AMBA; subte: todo (CABA).

    Las filas del subte vienen sin jurisdicción, provincia ni marca AMBA.
    """
    partes = []
    for a in anios:
        d = pd.read_csv(os.path.join(RAW_DIR, f"dat-ab-usos-{a}.csv"), parse_dates=['DIA_TRANSPORTE'],
                        usecols=['DIA_TRANSPORTE', 'AMBA', 'TIPO_TRANSPORTE', 'JURISDICCION', 'PROVINCIA',
                                 'CANTIDAD'])
        for c in ('AMBA', 'JURISDICCION', 'PROVINCIA'):
            d[c] = d[c].fillna('SIN_DATO')
        es_subte = d['TIPO_TRANSPORTE'] == 'SUBTE'
        es_amba = (d['AMBA'] == 'SI') & d['TIPO_TRANSPORTE'].isin(['COLECTIVO', 'TREN'])
        d = d[es_subte | es_amba].copy()
        t, j, p = d['TIPO_TRANSPORTE'], d['JURISDICCION'], d['PROVINCIA']
        d['serie'] = np.select(
            [t == 'SUBTE', t == 'TREN', j == 'NACIONAL', j == 'PROVINCIAL', (j == 'C.A.B.A') | p.str.startswith('C')],
            ['subte', 'tren', 'colectivo_nacional', 'colectivo_provincial', 'colectivo_caba'],
            default='colectivo_municipal')
        partes.append(d.groupby(['DIA_TRANSPORTE', 'serie'], as_index=False)['CANTIDAD'].sum())
    a = pd.concat(partes)
    w = a.pivot_table(index='DIA_TRANSPORTE', columns='serie', values='CANTIDAD', aggfunc='sum').fillna(0)
    w.index.name = 'fecha'
    w['colectivo'] = w[[c for c in w.columns if c.startswith('colectivo_')]].sum(axis=1)
    w['total_usos'] = w[['colectivo', 'tren', 'subte']].sum(axis=1)
    return w.asfreq('D')


def _tipo_dia(idx):
    """0 = día hábil, 1 = sábado, 2 = domingo."""
    return np.where(idx.day_of_week < 5, 0, np.where(idx.day_of_week == 5, 1, 2))


def reconstruir_hueco(usos, usuarios, ini, fin, ventana=28):
    """Usuarios = transacciones x razón usuarios/transacciones, interpolada entre los bordes del hueco.

    La razón se toma por tipo de día (hábil, sábado, domingo) como mediana de los `ventana` días
    previos y posteriores al hueco.
    """
    ini, fin = pd.Timestamp(ini), pd.Timestamp(fin)
    idx = pd.date_range(ini, fin)
    razon = (usuarios / usos)
    izq = razon.loc[ini - pd.Timedelta(days=ventana):ini - pd.Timedelta(days=1)].dropna()
    der = razon.loc[fin + pd.Timedelta(days=1):fin + pd.Timedelta(days=ventana)].dropna()
    out = []
    for k, d in enumerate(idx):
        t = _tipo_dia(pd.DatetimeIndex([d]))[0]
        r_izq = izq[_tipo_dia(izq.index) == t].median()
        r_der = der[_tipo_dia(der.index) == t].median()
        lam = (k + 1) / (len(idx) + 1)
        out.append(usos.loc[d] * (r_izq + (r_der - r_izq) * lam))
    return pd.Series(out, index=idx)


def reconstruir_serie(crudo, usos):
    """Rellena cada hueco de cada columna de usuarios y marca los días reconstruidos."""
    out = crudo.copy()
    out['imputado'] = crudo['total_amba'].isna()
    huecos = cd.tabla_huecos(crudo)
    for _, h in huecos.iterrows():
        for col, uc in PARES.items():
            est = reconstruir_hueco(usos[uc], crudo[col], h['inicio'], h['fin'])
            out.loc[est.index, col] = est.round(0)
    return out


def validar(crudo, usos, largo=31, paso_dias=14, margen=35):
    """Oculta bloques de datos reales y compara la reconstrucción con la interpolación por día de semana."""
    filas = []
    inicios = pd.date_range('2022-10-01', '2026-07-31', freq=f'{paso_dias}D')
    for ini in inicios:
        fin = ini + pd.Timedelta(days=largo - 1)
        if crudo['total_amba'].loc[ini - pd.Timedelta(days=margen):fin + pd.Timedelta(days=margen)].isna().any():
            continue
        for col, uc in PARES.items():
            real = crudo.loc[ini:fin, col]
            oculto = crudo[col].copy()
            oculto.loc[ini:fin] = np.nan
            ventana = oculto.loc[ini - pd.Timedelta(days=60):fin + pd.Timedelta(days=60)]
            estimaciones = {
                'reconstruccion_desde_transacciones': reconstruir_hueco(usos[uc], oculto, ini, fin),
                'lineal_por_dia_semana': cd.interp_lineal_por_dia_semana(ventana).loc[ini:fin],
            }
            for metodo, est in estimaciones.items():
                err = est - real
                filas.append({'inicio': ini.date(), 'serie': col, 'metodo': metodo,
                              'MAPE (%)': (err.abs() / real).mean() * 100,
                              'sesgo (%)': err.mean() / real.mean() * 100})
    return pd.DataFrame(filas)


def validar_meses_vacaciones(crudo, usos):
    """Mismo experimento sobre eneros y julios completos, los meses más difíciles."""
    casos = {'ene-2025': ('2025-01-01', '2025-01-31'), 'ene-2026': ('2026-01-01', '2026-01-31'),
             'jul-2025': ('2025-07-01', '2025-07-31'), 'jul-2026': ('2026-07-01', '2026-07-31')}
    filas = []
    for nombre, (a, b) in casos.items():
        real = crudo.loc[a:b, 'total_amba']
        oculto = crudo['total_amba'].copy()
        oculto.loc[a:b] = np.nan
        ventana = oculto.loc[pd.Timestamp(a) - pd.Timedelta(days=60):pd.Timestamp(b) + pd.Timedelta(days=60)]
        for metodo, est in {'reconstruccion_desde_transacciones': reconstruir_hueco(usos['total_usos'], oculto, a, b),
                            'lineal_por_dia_semana': cd.interp_lineal_por_dia_semana(ventana).loc[a:b]}.items():
            err = est - real
            filas.append({'mes': nombre, 'metodo': metodo, 'MAPE (%)': round((err.abs() / real).mean() * 100, 2),
                          'sesgo (%)': round(err.mean() / real.mean() * 100, 2)})
    return pd.DataFrame(filas)


def graficar(crudo, usos, serie_rec, sim):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), gridspec_kw={'width_ratios': [1.3, 1.3, 1]})
    for ax, (ini, fin, tit) in zip(axes[:2], [('2022-07-01', '2022-10-01', 'Agosto de 2022'),
                                              ('2023-12-01', '2024-03-01', 'Enero de 2024')]):
        real = crudo.loc[ini:fin, 'total_amba'] / 1e6
        rec = serie_rec.loc[ini:fin, 'total_amba'] / 1e6
        ax.plot(rec.index, rec, color='#27ae60', lw=1.4, label='Reconstruido desde transacciones')
        ax.plot(real.index, real, color='k', lw=1.6, label='Observado')
        ax.set_title(f'{tit}: usuarios totales', fontweight='bold')
        ax.set_ylabel('Millones de usuarios')
        ax.legend(loc='lower right')
    ax = axes[2]
    s = sim[sim.serie == 'total_amba']
    metodos = ['lineal_por_dia_semana', 'reconstruccion_desde_transacciones']
    bp = ax.boxplot([s.loc[s.metodo == m, 'MAPE (%)'] for m in metodos],
                    tick_labels=['interpolación\npor día de semana', 'reconstrucción\ndesde transacciones'],
                    patch_artist=True)
    for patch, c in zip(bp['boxes'], ['#e67e22', '#27ae60']):
        patch.set_facecolor(c); patch.set_alpha(0.5)
    ax.set_title('Error al ocultar bloques de 31 días reales', fontweight='bold')
    ax.set_ylabel('MAPE (%)')
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'fig12_reconstruccion_huecos.png'), dpi=200)
    plt.close()


def main():
    print(">>> Transacciones diarias de SUBE y reconstrucción de huecos")
    descargar_usos()
    usos = agregar_usos()
    usos.to_csv(os.path.join(PROC_DIR, 'usos_diarios_amba.csv'), index_label='fecha')
    print(f"Transacciones: {usos.index.min().date()} a {usos.index.max().date()}, "
          f"{int(usos['total_usos'].isna().sum())} días sin dato")

    crudo = cd.cargar_serie_cruda()
    crudo = crudo.loc[:usos.index.max()]
    serie = reconstruir_serie(crudo, usos)
    serie.to_csv(os.path.join(PROC_DIR, 'serie_sube_diaria_reconstruida.csv'), index_label='fecha')
    rec = serie[serie['imputado']]
    print(f"Días reconstruidos: {len(rec)}")
    modos = serie[['colectivo_amba', 'subte_amba', 'tren_amba']]
    incoherentes = ((serie['total_amba'] > modos.sum(axis=1)) | (serie['total_amba'] < modos.max(axis=1))).sum()
    print(f"Días con total fuera de [máx. de modos, suma de modos]: {int(incoherentes)} (en todos los días de la serie)")

    sim = validar(crudo, usos)
    resumen = (sim.groupby(['serie', 'metodo'])
                  .agg(ventanas=('inicio', 'nunique'), MAPE_mediano=('MAPE (%)', 'median'),
                       MAPE_p90=('MAPE (%)', lambda x: x.quantile(0.9)), sesgo_mediano=('sesgo (%)', 'median'),
                       sesgo_abs_p90=('sesgo (%)', lambda x: x.abs().quantile(0.9)))
                  .round(2))
    resumen.to_csv(os.path.join(TABLA_DIR, 'tabla_reconstruccion_usuarios.csv'))
    print(resumen.to_string())
    vac = validar_meses_vacaciones(crudo, usos)
    vac.to_csv(os.path.join(TABLA_DIR, 'tabla_reconstruccion_meses_vacaciones.csv'), index=False)
    print("Meses de vacaciones (total):")
    print(vac.to_string(index=False))
    graficar(crudo, usos, serie, sim)


if __name__ == '__main__':
    main()
