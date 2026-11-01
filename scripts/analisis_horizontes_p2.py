"""
Horizontes de pronóstico (P-2): ¿el mejor método a 28 días lo sigue siendo a 7 y a 90 días?

Mismo origen móvil, total AMBA, mismas definiciones que los bloques 11 a 13, pero con bloques de prueba de 7, 28 o 90
días (cortes cada 7, 28 o 90 días desde el 30-jun-2023; el horizonte de 90 días termina en el último corte que deja
90 días completos hasta el 30-sep-2026, por eso cubre menos días finales). Se comparan sin atípicos, con MASE escalado
por el naive de 7 días de cada corte (comparable entre horizontes) y Diebold-Mariano (HAC con 27 rezagos; con 7 días
los errores de cortes consecutivos están muy correlacionados, el HAC lo contempla).

Entradas: data/procesado/pronosticos_p2_h7.csv, pronosticos_p2_folds.csv (28 días), pronosticos_p2_h90.csv
Salidas:  resultados/tablas/tabla_p2_horizontes_metricas.csv, tabla_p2_horizontes_dm.csv, tabla_p2_horizontes_por_tramo.csv
          resultados/figuras/fig24_p2_horizontes.png
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import holidays
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analisis_pronosticos_p2 as A   # noqa: E402

warnings.filterwarnings('ignore')
plt.style.use('seaborn-v0_8-whitegrid')

PROC = os.path.join(A.BASE_DIR, "data", "procesado")
ARCHIVOS = {7: 'pronosticos_p2_h7.csv', 28: 'pronosticos_p2_folds.csv', 90: 'pronosticos_p2_h90.csv'}
MODELOS = ['naive_7', 'naive_364', 'sarimax', 'prophet', 'gradient_boosting']


def preparar(h, serie, evt):
    d = pd.read_csv(os.path.join(PROC, ARCHIVOS[h]), parse_dates=['origen', 'fecha'])
    d = d[d.modelo.isin(MODELOS)].copy()
    d['error'] = d.pronostico - d.real; d['abs_error'] = d.error.abs(); d['pct_error'] = d.abs_error / d.real * 100
    fer = [pd.Timestamp(f) for f in holidays.Argentina(years=range(2022, 2027))]
    d['tipo_dia'] = np.where(d.fecha.isin(fer), 'feriado', np.where(d.fecha.dt.dayofweek == 5, 'sábado',
                             np.where(d.fecha.dt.dayofweek == 6, 'domingo', 'hábil')))
    d['atipico'] = d.fecha.isin(evt.fecha)
    escala = {o: serie.loc[:o].diff(7).abs().mean() for o in d.origen.unique()}
    d['ase'] = d.abs_error / d.origen.map(escala)
    d['horizonte'] = h
    return d


def main():
    serie = pd.read_csv(A.SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')['total_amba'] / 1e6
    evt = pd.read_csv(A.EVT, parse_dates=['fecha'])
    hs = [h for h in ARCHIVOS if os.path.exists(os.path.join(PROC, ARCHIVOS[h]))]
    met, dm, tramo = [], [], []
    for h in hs:
        d = preparar(h, serie, evt)
        n_cortes = d.origen.nunique()
        sub = d[~d.atipico]
        for m, g in sub.groupby('modelo'):
            r = A.metricas(g); r['horizonte'] = h; r['modelo'] = m; r['cortes'] = n_cortes; met.append(r)
        mejor = sub[sub.modelo.isin(MODELOS[2:])].groupby('modelo').abs_error.mean().idxmin()
        for a in MODELOS:
            for b in ['naive_7', mejor]:
                if a != b:
                    dif, ee, p, n = A.dm_test(sub, a, b)
                    dm.append({'horizonte': h, 'modelo': a, 'contra': b, 'dif_MAE': round(dif, 4), 'error_std_HAC': round(ee, 4), 'p_valor': round(p, 4), 'dias': n})
        cortes_tramo = [0, 7, 28, 60, 90] if h == 90 else ([0, 7] if h == 7 else [0, 7, 14, 21, 28])
        sub = sub.assign(tramo=pd.cut(sub.h, cortes_tramo))
        for (t, m), g in sub.groupby(['tramo', 'modelo']):
            if len(g):
                tramo.append({'horizonte': h, 'dias_adelante': f'{int(t.left) + 1}-{int(t.right)}', 'modelo': m, 'dias': len(g), 'MAE': g.abs_error.mean(), 'MASE': g.ase.mean()})
    t_met = pd.DataFrame(met)[['horizonte', 'cortes', 'modelo', 'dias', 'MAE', 'RMSE', 'MAPE_pct', 'sesgo', 'MASE']].round(3)
    t_met.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_horizontes_metricas.csv'), index=False)
    t_dm = pd.DataFrame(dm); t_dm.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_horizontes_dm.csv'), index=False)
    t_tr = pd.DataFrame(tramo).round(3); t_tr.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_horizontes_por_tramo.csv'), index=False)

    for h in hs:
        print(f'\nHorizonte {h} días (sin atípicos)'); print(t_met[t_met.horizonte == h].drop(columns='horizonte').set_index('modelo').loc[MODELOS].to_string())
    print('\nMASE por horizonte'); piv = t_met.pivot(index='modelo', columns='horizonte', values='MASE').loc[MODELOS]; print(piv.to_string())
    print('\nMAPE por horizonte'); print(t_met.pivot(index='modelo', columns='horizonte', values='MAPE_pct').loc[MODELOS].to_string())
    print('\nPor tramo de días adelante (MASE)'); print(t_tr.pivot_table(index=['horizonte', 'dias_adelante'], columns='modelo', values='MASE').to_string())
    print('\nDiebold-Mariano'); print(t_dm.to_string(index=False))
    piv.plot(kind='bar', figsize=(10, 4.5), width=0.8); plt.axhline(1, color='k', lw=0.8, ls='--')
    plt.ylabel('MASE (menor a 1 = mejor que el naive de 7 días)'); plt.xticks(rotation=0); plt.legend(title='horizonte (días)')
    plt.title('Total AMBA según horizonte de pronóstico (sin atípicos)', fontweight='bold')
    plt.tight_layout(); plt.savefig(os.path.join(A.FIG_DIR, 'fig24_p2_horizontes.png'), dpi=200); plt.close()


if __name__ == '__main__':
    main()
