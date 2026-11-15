"""Sensibilidad de PatchTST a la semilla y a los hiperparámetros (P-2, total AMBA, 28 días, 42 cortes).

Pregunta: la ventaja de PatchTST sobre el Gradient Boosting (MASE 0,547 contra 0,568 en la corrida de Arey14) ¿se
mantiene con otras semillas y otros hiperparámetros, o depende de la combinación elegida?

Diseño (fijado antes de correr):
  - Mismos 42 cortes, misma serie reconstruida y mismas métricas que `evaluacion_pronosticos.py` y
    `analisis_pronosticos_p2.py` (MAE y MASE sin los días de paro ni de elección, 1.161 días).
  - A. Semillas: hiperparámetros originales (150 épocas, tasa 4e-3, d_model 32, 2 capas, 8 parches) con 5 semillas
    (la 42 es la de la corrida original; sirve para comprobar que aquí se reproduce el resultado).
  - B. Hiperparámetros: una variación a la vez alrededor de los originales (épocas, tasa de aprendizaje, d_model,
    capas, cantidad de parches), con la semilla 42.
  - Los cortes de evaluación son los mismos que se usaron para comparar modelos. Por eso este análisis se informa como
    SENSIBILIDAD (rango y mediana), no para elegir la mejor combinación: elegir la mejor mirando estos 42 cortes daría
    un resultado optimista.
  - Referencia: el Gradient Boosting de `pronosticos_p2_folds.csv`.

Uso:  python sensibilidad_patchtst_p2.py [parte=i/n]   (reparte las configuraciones entre n procesos; se puede retomar)
Salida: data/procesado/pronosticos_p2_patchtst_sensibilidad.csv y resultados/tablas/tabla_p2_patchtst_sensibilidad.csv
"""

import os
import sys
import time
import warnings
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pronosticos_p2 as P   # noqa: E402
import evaluacion_pronosticos as E   # noqa: E402

warnings.filterwarnings('ignore')
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIR_SALIDA = os.path.join(BASE_DIR, "data", "procesado")
PREFIJO = "pronosticos_p2_patchtst_sensibilidad"   # un archivo por proceso: pronosticos_p2_patchtst_sensibilidad_<i>.csv
TABLA = os.path.join(BASE_DIR, "resultados", "tablas", "tabla_p2_patchtst_sensibilidad.csv")
FOLDS = os.path.join(BASE_DIR, "data", "procesado", "pronosticos_p2_folds.csv")
EVT = os.path.join(BASE_DIR, "data", "hitos", "hitos_paros_elecciones.csv")

ORIG = dict(epochs=150, lr=4e-3, d_model=32, num_layers=2, n_patches=8, seed=42)
CONFIGS = {}
for s in (42, 0, 1, 2, 3, 4):
    CONFIGS[f'semilla_{s}'] = {**ORIG, 'seed': s}
for k, vals in [('epochs', (50, 100, 300)), ('lr', (1e-3, 2e-3, 8e-3)), ('d_model', (16, 64)),
                ('num_layers', (1, 3)), ('n_patches', (4, 12))]:
    for v in vals:
        CONFIGS[f'{k}_{v}'] = {**ORIG, k: v}

_NET_ORIG = P._PatchTSTNet


def pronostico(serie, corte, cfg):
    """PatchTST con los hiperparámetros de `cfg` (d_model y capas se pasan por el constructor de la red)."""
    d_model, capas = cfg['d_model'], cfg['num_layers']
    P._PatchTSTNet = lambda **kw: _NET_ORIG(d_model=d_model, num_layers=capas, **kw)
    try:
        return P.patchtst(serie, corte, 28, n_patches=cfg['n_patches'], epochs=cfg['epochs'], lr=cfg['lr'], seed=cfg['seed'])
    finally:
        P._PatchTSTNet = _NET_ORIG


def correr(parte):
    serie = pd.read_csv(E.SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')['total_amba'].loc[E.INICIO:E.FIN] / 1e6
    cs = E.cortes(serie)
    nombres = list(CONFIGS)
    i, n = parte
    mias = [c for k, c in enumerate(nombres) if k % n == i]
    SALIDA = os.path.join(DIR_SALIDA, f"{PREFIJO}_{i}.csv")
    hechos = set()
    if os.path.exists(SALIDA):
        prev = pd.read_csv(SALIDA, parse_dates=['origen'])
        hechos = set(zip(prev['config'], prev['origen']))
    print(f'proceso {i}/{n}: {len(mias)} configuraciones, {len(cs)} cortes', flush=True)
    for cfg_nombre in mias:
        cfg = CONFIGS[cfg_nombre]
        t0 = time.time()
        for c in cs:
            if (cfg_nombre, c) in hechos:
                continue
            pred = pronostico(serie, c, cfg)
            filas = [{'config': cfg_nombre, 'origen': c, 'fecha': f, 'h': h, 'real': serie.loc[f], 'pronostico': p}
                     for h, (f, p) in enumerate(pred.items(), 1)]
            pd.DataFrame(filas).to_csv(SALIDA, mode='a', header=not os.path.exists(SALIDA), index=False)
        print(f'  {cfg_nombre} listo en {time.time() - t0:.0f} s', flush=True)


def resumir():
    import glob
    d = pd.concat([pd.read_csv(f, parse_dates=['origen', 'fecha']) for f in sorted(glob.glob(os.path.join(DIR_SALIDA, PREFIJO + '_*.csv')))],
                  ignore_index=True)
    serie = pd.read_csv(E.SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')['total_amba'] / 1e6
    evt = pd.read_csv(EVT, parse_dates=['fecha'])['fecha']
    escala = {o: serie.loc[:o].diff(7).abs().mean() for o in d['origen'].unique()}
    fo = pd.read_csv(FOLDS, parse_dates=['origen', 'fecha'])
    gb = fo[fo.modelo == 'gradient_boosting'].copy(); gb['config'] = 'gradient_boosting (referencia)'
    pt = fo[fo.modelo == 'patchtst'].copy(); pt['config'] = 'patchtst (corrida original de Arey14)'
    d = pd.concat([d, gb[['config', 'origen', 'fecha', 'h', 'real', 'pronostico']],
                   pt[['config', 'origen', 'fecha', 'h', 'real', 'pronostico']]], ignore_index=True)
    d['abs_error'] = (d['pronostico'] - d['real']).abs()
    d['ase'] = d['abs_error'] / d['origen'].map(escala)
    d['atipico'] = d['fecha'].isin(evt)
    ok = d[~d['atipico']]
    ncortes = d.groupby('config')['origen'].nunique()
    res = ok.groupby('config').agg(dias=('abs_error', 'size'), MAE=('abs_error', 'mean'), MASE=('ase', 'mean'))
    res['cortes'] = ncortes
    # comparación con el Gradient Boosting: diferencia de MAE y p de Diebold-Mariano (HAC)
    import statsmodels.api as sm
    ref = ok[ok.config == 'gradient_boosting (referencia)'].set_index('fecha')['abs_error']
    dif_mae, p_dm = {}, {}
    for cfg, g in ok.groupby('config'):
        if cfg.startswith('gradient'):
            continue
        x = g.set_index('fecha')['abs_error']
        dd = (x - ref).dropna().sort_index()
        if len(dd) < 100:
            continue
        r = sm.OLS(dd.values, np.ones(len(dd))).fit(cov_type='HAC', cov_kwds={'maxlags': 27})
        dif_mae[cfg] = r.params[0]; p_dm[cfg] = r.pvalues[0]
    res['dif_MAE_vs_GB'] = pd.Series(dif_mae)
    res['p_DM_vs_GB'] = pd.Series(p_dm)
    res = res.round(4)
    res.to_csv(TABLA)
    print(res.to_string())
    sem = res[res.index.str.startswith('semilla_')]
    print('\nSemillas: MASE min / mediana / max =', sem.MASE.min(), sem.MASE.median(), sem.MASE.max(),
          '| GB =', res.loc['gradient_boosting (referencia)', 'MASE'])
    hp = res[~res.index.str.startswith(('semilla_', 'gradient'))]
    print('Hiperparámetros (semilla 42): MASE min / mediana / max =', hp.MASE.min(), hp.MASE.median(), hp.MASE.max())
    print('Configuraciones con MASE menor que el Gradient Boosting:',
          int((res.drop(index='gradient_boosting (referencia)').MASE < res.loc['gradient_boosting (referencia)', 'MASE']).sum()),
          'de', len(res) - 1)


if __name__ == '__main__':
    if 'resumir' in sys.argv:
        resumir()
    else:
        arg = next((a.split('=')[1] for a in sys.argv if a.startswith('parte=')), '0/1')
        correr(tuple(int(x) for x in arg.split('/')))
        if arg == "0/1":
            resumir()
