"""Offline precomputation for the dashboard.

job 'floors'  : minimum-cost feasible portfolios for every distinct car-light set
                (no-vehicle cutoff 20..40 percent) and coverage target 0.75..1.00.
job 'library' : full-model solutions for common budget x cutoff scenarios.
Both are resumable: finished entries are skipped.
"""
import json, os, pickle, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fastmodel as fm

PKL = sys.argv[2]
OUT = sys.argv[3]
os.makedirs(OUT, exist_ok=True)
ph = pickle.load(open(PKL, 'rb'))
S = fm.build_structure(ph)
noveh = ph['NoVeh']


def carlight_key(c):
    return tuple(sorted(z for z, r in noveh.items() if r > c))


def floors():
    path = os.path.join(OUT, 'floors.json')
    db = json.load(open(path)) if os.path.exists(path) else {}
    seen = {}
    for pct in range(20, 41):
        key = carlight_key(pct / 100)
        seen.setdefault(key, pct)
    for key, pct in sorted(seen.items(), key=lambda kv: kv[1]):
        for th in (1.00, 0.95, 0.90, 0.85, 0.80, 0.75):
            name = f'{pct}_{th:.2f}'
            if name in db:
                continue
            p = dict(fm.DEFAULTS); p['nv_threshold'] = pct / 100; p['theta'] = th
            lp, info = fm.build_lp(S, p, noveh, 'mincost', link_rows=False)
            h = fm._new_highs(150, 0.01); h.passModel(lp); t = time.time(); h.run()
            inf = h.getInfo()
            if inf.primal_solution_status != 2:
                db[name] = None
            else:
                x = np.array(h.getSolution().col_value)[:info['n_jk']] > 0.5
                db[name] = dict(cutoff_pct=pct, theta=th, carlight=list(key),
                                jk=np.flatnonzero(x).tolist(), cost=float(info['cost'][x].sum()),
                                bound=float(inf.mip_dual_bound), seconds=round(time.time() - t, 1))
            json.dump(db, open(path, 'w'))
            print(name, None if db[name] is None else round(db[name]['cost'] / 1e6, 3), flush=True)


def library():
    import pandas as pd
    base = pd.read_excel(sys.argv[4], sheet_name='selected_facilities')
    x0 = np.zeros(len(S.jk_site))
    for j, k in zip(base.site_id, base.intervention_type):
        x0[S.jk_lookup[(int(j), k)]] = 1
    path = os.path.join(OUT, 'library.json')
    db = json.load(open(path)) if os.path.exists(path) else {}
    prev = {}
    for nv in (25, 30, 35, 40):
        start = x0
        for b in (40, 45, 50, 55, 60, 65, 70, 80, 90, 100):
            name = f'B{b}_nv{nv}'
            if name in db:
                if db[name]:
                    start = np.zeros(len(S.jk_site)); start[db[name]['jk']] = 1
                continue
            p = dict(fm.DEFAULTS); p['budget'] = b * 1e6; p['nv_threshold'] = nv / 100
            r = fm.solve(S, p, noveh, time_limit=240, gap=0.01, start_x=start, link_rows=False)
            if not r.get('feasible'):
                db[name] = None
            else:
                db[name] = dict(budget=b, cutoff_pct=nv, jk=np.flatnonzero(r['x_on']).tolist(),
                                objective=r['objective'], gap=r['gap'], cost=r['cost_total'],
                                status=r['status'], seconds=round(r['total_s'], 1),
                                coverage=np.round(r['coverage'], 4).tolist())
                start = r['x_on'].astype(float)
            json.dump(db, open(path, 'w'))
            print(name, r['status'], round(r.get('objective', 0), 2), round(100 * r.get('gap', 0), 2), round(r['total_s'], 1), flush=True)
            print('MORE', flush=True)
            return


if __name__ == '__main__':
    {'floors': floors, 'library': library}[sys.argv[1]]()
