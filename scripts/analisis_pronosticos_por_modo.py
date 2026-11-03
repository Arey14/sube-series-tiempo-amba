"""
Pronóstico por modo (P-2): colectivo, tren y subte, con el mismo origen móvil que el total (42 cortes, horizonte de
28 días). Compara los métodos modo por modo y si el mejor para el total sigue siéndolo en cada modo.

Serie de cada modo: usuarios distintos por día en ese modo (columnas colectivo_amba, tren_amba y subte_amba de la
serie reconstruida). Días excluidos de las métricas "sin atípicos": paros y elecciones del archivo de hitos y, para
el subte, el cierre de la línea D (8-ene a 6-mar de 2024), que nadie podía anticipar con el calendario.

Entradas: data/procesado/pronosticos_p2_{colectivo,tren,subte}_amba.csv, data/procesado/serie_sube_diaria_reconstruida.csv,
          data/hitos/hitos_paros_elecciones.csv
Salidas:  resultados/tablas/tabla_p2_modo_metricas.csv, tabla_p2_modo_tipo_dia.csv, tabla_p2_modo_diebold_mariano.csv
          resultados/figuras/fig22_p2_mase_por_modo.png
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

BASE_DIR = A.BASE_DIR
MODOS = ['colectivo_amba', 'tren_amba', 'subte_amba']
ORDEN = ['naive_7', 'naive_364', 'sarimax', 'sarimax_en_logs', 'prophet', 'gradient_boosting']


def preparar(col, serie_total, evt):
    d = pd.read_csv(os.path.join(BASE_DIR, "data", "procesado", f"pronosticos_p2_{col}.csv"), parse_dates=['origen', 'fecha'])
    d['error'] = d['pronostico'] - d['real']; d['abs_error'] = d['error'].abs(); d['pct_error'] = d['abs_error'] / d['real'] * 100
    fer = [pd.Timestamp(f) for f in holidays.Argentina(years=range(2022, 2027))]
    d['tipo_dia'] = np.where(d.fecha.isin(fer), 'feriado', np.where(d.fecha.dt.dayofweek == 5, 'sábado',
                             np.where(d.fecha.dt.dayofweek == 6, 'domingo', 'hábil')))
    d['atipico'] = d.fecha.isin(evt['fecha'])
    if col == 'subte_amba':
        d['atipico'] |= (d.fecha >= '2024-01-08') & (d.fecha <= '2024-03-06')
    escala = {o: serie_total[col].loc[:o].diff(7).abs().mean() / 1e6 for o in d['origen'].unique()}
    d['ase'] = d['abs_error'] / d['origen'].map(escala)
    return d


def main():
    serie = pd.read_csv(A.SERIE, parse_dates=['fecha']).set_index('fecha').asfreq('D')
    evt = pd.read_csv(A.EVT, parse_dates=['fecha'])
    met, tip, dm = [], [], []
    for col in MODOS:
        d = preparar(col, serie, evt)
        sub = d[~d.atipico]
        for m, g in sub.groupby('modelo'):
            r = A.metricas(g); r['modo'] = col; r['modelo'] = m; met.append(r)
        for (t, m), g in sub.groupby(['tipo_dia', 'modelo']):
            r = A.metricas(g); r['modo'] = col; r['modelo'] = m; r['tipo_dia'] = t; tip.append(r)
        mejor = sub.groupby('modelo').abs_error.mean().drop(labels=['naive_7', 'naive_364'], errors='ignore').idxmin()
        for m in sub.modelo.unique():
            for b in ['naive_7', mejor]:
                if m == b:
                    continue
                dif, ee, p, n = A.dm_test(sub, m, b)
                dm.append({'modo': col, 'modelo': m, 'contra': b, 'dif_MAE': round(dif, 4), 'error_std_HAC': round(ee, 4), 'p_valor': round(p, 4), 'dias': n})
    t_met = pd.DataFrame(met)[['modo', 'modelo', 'dias', 'MAE', 'RMSE', 'MAPE_pct', 'sesgo', 'MASE']].round(3)
    t_met.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_modo_metricas.csv'), index=False)
    t_tip = pd.DataFrame(tip)[['modo', 'tipo_dia', 'modelo', 'dias', 'MAE', 'MAPE_pct', 'MASE']].round(3)
    t_tip.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_modo_tipo_dia.csv'), index=False)
    t_dm = pd.DataFrame(dm); t_dm.to_csv(os.path.join(A.TABLA_DIR, 'tabla_p2_modo_diebold_mariano.csv'), index=False)
    for col in MODOS:
        print(f"\n{col} (sin atípicos)")
        print(t_met[t_met.modo == col].drop(columns='modo').set_index('modelo').loc[ORDEN].to_string())
    print('\nMAE por tipo de día');
    for col in MODOS:
        print(col); print(t_tip[t_tip.modo == col].pivot(index='modelo', columns='tipo_dia', values='MAE').loc[ORDEN].to_string())
    print('\nMAPE por tipo de día')
    for col in MODOS:
        print(col); print(t_tip[t_tip.modo == col].pivot(index='modelo', columns='tipo_dia', values='MAPE_pct').loc[ORDEN].to_string())
    print('\nDiebold-Mariano'); print(t_dm.to_string(index=False))
    piv = t_met.pivot(index='modelo', columns='modo', values='MASE').loc[ORDEN][MODOS]
    piv.plot(kind='bar', figsize=(10, 4.5), width=0.8); plt.axhline(1, color='k', lw=0.8, ls='--')
    plt.ylabel('MASE (menor a 1 = mejor que el naive de 7 días)'); plt.xticks(rotation=20)
    plt.title('Pronóstico por modo, horizonte de 28 días (sin atípicos)', fontweight='bold')
    plt.tight_layout(); plt.savefig(os.path.join(A.FIG_DIR, 'fig22_p2_mase_por_modo.png'), dpi=200); plt.close()


if __name__ == '__main__':
    main()
