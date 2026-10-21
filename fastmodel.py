"""
Fast MILP builder for the Detroit food access model.

Builds the exact formulation of the paper (constraints 4 to 16) directly as a
sparse HiGHS model, without Pyomo. The static structure (index arrays for the
89,626 assignment triples) is prepared once and reused; each solve only fills
in the parameter-dependent numbers.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import highspy

TYPES = ["grocery_new", "grocery_upgrade", "mobile_market", "farmers_new", "farmers_upgrade"]


@dataclass
class Structure:
    """Parameter-independent arrays derived from the Phase 1 pickle."""
    n_i: int
    sub_ids: np.ndarray            # subpoint id per row index
    sub_zip: np.ndarray            # ZIP (str) per subpoint index
    pop_i: np.ndarray
    w_i: np.ndarray
    jk_site: np.ndarray            # site id per (j,k) column
    jk_type: np.ndarray            # type index per (j,k) column
    jk_inc: np.ndarray             # ZIP income for the site of (j,k)
    arc_i: np.ndarray              # subpoint index per arc
    arc_jk: np.ndarray             # (j,k) column index per arc
    arc_walk: np.ndarray           # True if arc type is walking-eligible
    arc_decay: np.ndarray          # f(d) per arc
    site_of_jk: np.ndarray         # site index (0..n_sites-1) per (j,k)
    n_sites: int
    inc_median: float
    jk_lookup: dict = field(default_factory=dict)


def build_structure(ph) -> Structure:
    I = list(ph["I_subpoints"])
    idx_i = {i: n for n, i in enumerate(I)}
    dp_zip = {dp["i"]: str(dp["zip"]) for dp in ph["demand_points"]}
    J = ph["J"]
    site_by_id = {s["j"]: s for s in J}
    jks = [(j, k) for k in ph["K"] for j in ph["J_k"][k]]
    jk_lookup = {jk: n for n, jk in enumerate(jks)}
    tindex = {k: n for n, k in enumerate(TYPES)}
    inc = ph["Inc"]; inc_med = ph["Inc_median"]
    jk_site = np.array([j for j, _ in jks])
    jk_type = np.array([tindex[k] for _, k in jks])
    jk_inc = np.array([inc.get(site_by_id[j]["zip"], inc_med) for j, _ in jks], dtype=float)
    sites = sorted(set(jk_site.tolist()))
    sidx = {s: n for n, s in enumerate(sites)}
    site_of_jk = np.array([sidx[s] for s in jk_site])

    A = list(ph["A_eff"])
    A.sort()
    k_walk = set(ph["K_walk"])
    base_fa = ph["delta_FA_base"]
    arc_i = np.empty(len(A), dtype=np.int64)
    arc_jk = np.empty(len(A), dtype=np.int64)
    arc_walk = np.empty(len(A), dtype=bool)
    arc_decay = np.empty(len(A), dtype=float)
    dFA = ph["delta_FA"]
    for n, (i, j, k) in enumerate(A):
        arc_i[n] = idx_i[i]
        arc_jk[n] = jk_lookup[(j, k)]
        arc_walk[n] = k in k_walk
        arc_decay[n] = dFA[(i, j, k)] / base_fa[k]
    return Structure(
        n_i=len(I), sub_ids=np.array(I), sub_zip=np.array([dp_zip[i] for i in I]),
        pop_i=np.array([ph["Pop_i"][i] for i in I], dtype=float),
        w_i=np.array([ph["w_i"][i] for i in I], dtype=float),
        jk_site=jk_site, jk_type=jk_type, jk_inc=jk_inc,
        arc_i=arc_i, arc_jk=arc_jk, arc_walk=arc_walk, arc_decay=arc_decay,
        site_of_jk=site_of_jk, n_sites=len(sites), inc_median=float(inc_med),
        jk_lookup=jk_lookup,
    )


def load_structure(npz_path: str) -> Structure:
    d = np.load(npz_path)
    jk_site = d["jk_site"]; jk_type = d["jk_type"]
    lookup = {(int(j), TYPES[t]): n for n, (j, t) in enumerate(zip(jk_site, jk_type))}
    return Structure(
        n_i=len(d["sub_ids"]), sub_ids=d["sub_ids"], sub_zip=d["sub_zip"].astype(str),
        pop_i=d["pop_i"], w_i=d["w_i"], jk_site=jk_site, jk_type=jk_type, jk_inc=d["jk_inc"],
        arc_i=d["arc_i"], arc_jk=d["arc_jk"], arc_walk=d["arc_walk"], arc_decay=d["arc_decay"],
        site_of_jk=d["site_of_jk"], n_sites=int(d["site_of_jk"].max()) + 1,
        inc_median=0.0, jk_lookup=lookup,
    )


DEFAULTS = dict(
    budget=40e6, theta=1.0, nv_threshold=0.25, omega=(1/3, 1/3, 1/3), lam=0.0, gamma=0.3,
    apply_walking=True,
    cost={"grocery_new": 750_000, "grocery_upgrade": 175_000, "mobile_market": 200_000,
          "farmers_new": 100_000, "farmers_upgrade": 40_000},
    cap={"grocery_new": 15_000, "grocery_upgrade": 12_000, "mobile_market": 3_000,
         "farmers_new": 5_000, "farmers_upgrade": 3_000},
    dfa={"grocery_new": 1.00, "grocery_upgrade": 0.50, "mobile_market": 0.20,
         "farmers_new": 0.30, "farmers_upgrade": 0.15},
    du={"grocery_new": 0.40, "grocery_upgrade": 0.20, "mobile_market": 0.10,
        "farmers_new": 0.15, "farmers_upgrade": 0.08},
    beta=0.00781, ceil_factor=1.5,
)


def site_costs(S: Structure, cost: dict, gamma: float) -> np.ndarray:
    base = np.array([cost[TYPES[t]] for t in S.jk_type], dtype=float)
    return base * (1.0 + gamma * (S.jk_inc - S.inc_median) / S.inc_median)


def walk_required(S: Structure, noveh: dict, nv_threshold: float) -> np.ndarray:
    """Boolean per subpoint: car-light and has at least one walking arc."""
    carlight = np.array([noveh.get(z, 0.0) > nv_threshold for z in S.sub_zip])
    has_walk = np.zeros(S.n_i, dtype=bool)
    has_walk[S.arc_i[S.arc_walk]] = True
    return carlight & has_walk, carlight


def _csr(rows, cols, vals, n_rows):
    order = np.lexsort((cols, rows))
    rows, cols, vals = rows[order], cols[order], vals[order]
    start = np.zeros(n_rows + 1, dtype=np.int64)
    np.add.at(start, rows + 1, 1)
    start = np.cumsum(start)
    return start, cols.astype(np.int32), vals.astype(float)


def build_lp(S: Structure, p: dict, noveh: dict, mode: str = "max", link_rows: bool = True):
    """Return (HighsLp, info). mode='max' is the paper's model;
    mode='mincost' minimizes expenditure subject to coverage and equity only."""
    n_jk = len(S.jk_site); n_a = len(S.arc_i); n_i = S.n_i
    cost = site_costs(S, p["cost"], p["gamma"])
    cap = np.array([p["cap"][TYPES[t]] for t in S.jk_type], dtype=float)
    wreq, carlight = walk_required(S, noveh, p["nv_threshold"])
    if not p.get("apply_walking", True):
        wreq = np.zeros_like(wreq)

    with_out = mode == "max"
    # columns: x[jk] | z[arc] | (A,R,Q)[i]
    off_z = n_jk
    off_A = n_jk + n_a
    n_col = off_A + (3 * n_i if with_out else 0)

    col_lower = np.zeros(n_col)
    col_upper = np.ones(n_col)
    integ = np.zeros(n_col, dtype=np.int32)
    integ[:n_jk] = 1
    obj = np.zeros(n_col)

    t_arc = S.jk_type[S.arc_jk]
    if with_out:
        dfa_t = np.array([p["dfa"][k] for k in TYPES]); du_t = np.array([p["du"][k] for k in TYPES])
        a_ceil = p["ceil_factor"] * dfa_t.max()
        r_ceil = p["ceil_factor"] * du_t.max()
        q_ceil = p["ceil_factor"] * p["beta"] * dfa_t.max()
        oA, oR, oQ = p["omega"]
        col_upper[off_A:off_A + n_i] = a_ceil
        col_upper[off_A + n_i:off_A + 2 * n_i] = r_ceil
        col_upper[off_A + 2 * n_i:] = q_ceil
        obj[off_A:off_A + n_i] = S.w_i * oA / a_ceil
        obj[off_A + n_i:off_A + 2 * n_i] = S.w_i * oR / r_ceil
        obj[off_A + 2 * n_i:] = S.w_i * oQ / q_ceil
        if p.get("lam", 0) > 0:
            obj[:n_jk] = -p["lam"] * cost / p["budget"]
    else:
        obj[:n_jk] = cost

    rows = []; cols = []; vals = []; rlo = []; rup = []
    r = 0
    arc_idx = np.arange(n_a)
    # (4) coverage
    has_arc = np.zeros(n_i, dtype=bool); has_arc[S.arc_i] = True
    cov_row = -np.ones(n_i, dtype=np.int64)
    cov_row[has_arc] = r + np.arange(has_arc.sum())
    rows.append(cov_row[S.arc_i]); cols.append(off_z + arc_idx); vals.append(np.ones(n_a))
    nr = int(has_arc.sum()); rlo += [p["theta"]] * nr; rup += [highspy.kHighsInf] * nr; r += nr
    # (5) walking equity
    w_arcs = S.arc_walk & wreq[S.arc_i]
    w_row = -np.ones(n_i, dtype=np.int64)
    w_row[wreq] = r + np.arange(wreq.sum())
    rows.append(w_row[S.arc_i[w_arcs]]); cols.append(off_z + arc_idx[w_arcs]); vals.append(np.ones(w_arcs.sum()))
    nr = int(wreq.sum()); rlo += [p["theta"]] * nr; rup += [highspy.kHighsInf] * nr; r += nr
    # (6) z <= x  (implied by (8) when populations are positive; optional)
    if link_rows:
        rr = r + arc_idx
        rows += [rr, rr]; cols += [off_z + arc_idx, S.arc_jk]; vals += [np.ones(n_a), -np.ones(n_a)]
        rlo += [-highspy.kHighsInf] * n_a; rup += [0.0] * n_a; r += n_a
    # (7) one type per site
    rows.append(r + S.site_of_jk); cols.append(np.arange(n_jk)); vals.append(np.ones(n_jk))
    rlo += [-highspy.kHighsInf] * S.n_sites; rup += [1.0] * S.n_sites; r += S.n_sites
    # (8) capacity
    rows += [r + S.arc_jk, r + np.arange(n_jk)]
    cols += [off_z + arc_idx, np.arange(n_jk)]
    vals += [S.pop_i[S.arc_i], -cap]
    rlo += [-highspy.kHighsInf] * n_jk; rup += [0.0] * n_jk; r += n_jk
    # (9) budget (only in the paper's model)
    if with_out:
        rows.append(np.full(n_jk, r)); cols.append(np.arange(n_jk)); vals.append(cost)
        rlo.append(-highspy.kHighsInf); rup.append(p["budget"]); r += 1
        # (10),(12),(14) impact links: A_i - sum dFA_ijk z <= 0 etc.
        coefs = [np.array([p["dfa"][k] for k in TYPES])[t_arc] * S.arc_decay,
                 np.array([p["du"][k] for k in TYPES])[t_arc] * S.arc_decay,
                 p["beta"] * np.array([p["dfa"][k] for k in TYPES])[t_arc] * S.arc_decay]
        for o in range(3):
            base = r
            rows += [base + np.arange(n_i), base + S.arc_i]
            cols += [off_A + o * n_i + np.arange(n_i), off_z + arc_idx]
            vals += [np.ones(n_i), -coefs[o]]
            rlo += [-highspy.kHighsInf] * n_i; rup += [0.0] * n_i; r += n_i

    rows = np.concatenate(rows); cols = np.concatenate(cols); vals = np.concatenate(vals)
    start, index, value = _csr(rows, cols, vals, r)

    lp = highspy.HighsLp()
    lp.num_col_ = n_col
    lp.num_row_ = r
    lp.col_cost_ = obj
    lp.col_lower_ = col_lower
    lp.col_upper_ = col_upper
    lp.row_lower_ = np.array(rlo, dtype=float)
    lp.row_upper_ = np.array(rup, dtype=float)
    lp.sense_ = highspy.ObjSense.kMaximize if with_out else highspy.ObjSense.kMinimize
    lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    lp.a_matrix_.start_ = start
    lp.a_matrix_.index_ = index
    lp.a_matrix_.value_ = value
    lp.a_matrix_.num_col_ = n_col
    lp.a_matrix_.num_row_ = r
    lp.integrality_ = [highspy.HighsVarType.kInteger if v else highspy.HighsVarType.kContinuous for v in integ]
    info = dict(cost=cost, cap=cap, n_jk=n_jk, n_a=n_a, off_z=off_z, off_A=off_A,
                n_walk=int(wreq.sum()), n_carlight=int(carlight.sum()))
    return lp, info


def _new_highs(time_limit, gap, threads=None):
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", float(time_limit))
    h.setOptionValue("mip_rel_gap", float(gap))
    if threads:
        h.setOptionValue("threads", int(threads))
    return h


def fixed_x_completion(S: Structure, p: dict, noveh: dict, x_on: np.ndarray, time_limit=30):
    """Given a set of open (j,k) columns, solve the LP over z,A,R,Q with x fixed.
    Returns a full column vector usable as a MIP start, or None if infeasible."""
    lp, info = build_lp(S, p, noveh, "max")
    n_jk = info["n_jk"]
    lo = np.array(lp.col_lower_); up = np.array(lp.col_upper_)
    lo[:n_jk] = x_on; up[:n_jk] = x_on
    lp.col_lower_ = lo; lp.col_upper_ = up
    lp.integrality_ = [highspy.HighsVarType.kContinuous] * lp.num_col_
    h = _new_highs(time_limit, 1e-4)
    h.passModel(lp)
    h.run()
    if h.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        return None
    return np.array(h.getSolution().col_value)


def solve(S: Structure, p: dict, noveh: dict, time_limit=90, gap=0.02, start_x=None, threads=None, link_rows=True):
    t0 = time.time()
    lp, info = build_lp(S, p, noveh, "max", link_rows)
    t_build = time.time() - t0
    h = _new_highs(time_limit, gap, threads)
    h.passModel(lp)
    warm = False
    if start_x is not None:
        full = fixed_x_completion(S, p, noveh, start_x)
        if full is not None:
            sol = highspy.HighsSolution()
            sol.col_value = list(full)
            sol.value_valid = True
            h.setSolution(sol)
            warm = True
    t1 = time.time()
    h.run()
    t_solve = time.time() - t1
    status = h.getModelStatus()
    st = h.modelStatusToString(status)
    inf = h.getInfo()
    has_sol = inf.primal_solution_status == 2
    out = dict(status=st, build_s=t_build, solve_s=t_solve, total_s=time.time() - t0, warm=warm,
               n_walk=info["n_walk"], n_carlight=info["n_carlight"], feasible=has_sol)
    if not has_sol:
        return out
    x = np.array(h.getSolution().col_value)
    xs = x[:info["n_jk"]] > 0.5
    z = x[info["off_z"]:info["off_z"] + info["n_a"]]
    cov = np.bincount(S.arc_i, weights=z, minlength=S.n_i)
    out.update(
        objective=float(inf.objective_function_value),
        bound=float(inf.mip_dual_bound),
        gap=float(inf.mip_gap),
        x_on=xs,
        cost_total=float(info["cost"][xs].sum()),
        jk_cost=info["cost"], jk_cap=info["cap"],
        coverage=cov,
        A=x[info["off_A"]:info["off_A"] + S.n_i],
        R=x[info["off_A"] + S.n_i:info["off_A"] + 2 * S.n_i],
        Q=x[info["off_A"] + 2 * S.n_i:],
    )
    return out


def min_feasible_budget(S: Structure, p: dict, noveh: dict, time_limit=60, gap=0.005):
    """Smallest expenditure that satisfies coverage, walking equity, capacity and
    one-type-per-site. Returns (budget_lower_bound, best_found_budget, status)."""
    lp, info = build_lp(S, p, noveh, "mincost", link_rows=False)
    h = _new_highs(time_limit, gap)
    h.passModel(lp)
    h.run()
    inf = h.getInfo()
    st = h.modelStatusToString(h.getModelStatus())
    if inf.primal_solution_status != 2:
        return None, None, st
    return float(inf.mip_dual_bound), float(inf.objective_function_value), st


def greedy_fill(S: Structure, p: dict, noveh: dict, x_on: np.ndarray, full: np.ndarray):
    """Add facilities to a feasible plan while budget remains, ranked by a capacity-limited
    estimate of the objective gain per dollar. Adding facilities never breaks feasibility
    (coverage, equity and capacity only get easier), so the result is always feasible."""
    n_jk = len(S.jk_site); n_a = len(S.arc_i)
    cost = site_costs(S, p["cost"], p["gamma"])
    x_on = x_on.astype(bool).copy()
    spare = p["budget"] - cost[x_on].sum()
    if spare <= 0:
        return x_on
    dfa_t = np.array([p["dfa"][k] for k in TYPES]); du_t = np.array([p["du"][k] for k in TYPES])
    a_ceil = p["ceil_factor"] * dfa_t.max(); r_ceil = p["ceil_factor"] * du_t.max()
    oA, oR, oQ = p["omega"]
    off_A = n_jk + n_a
    A = full[off_A:off_A + S.n_i]; R = full[off_A + S.n_i:off_A + 2 * S.n_i]
    t = S.jk_type[S.arc_jk]
    gA = np.minimum(dfa_t[t] * S.arc_decay, np.maximum(a_ceil - A[S.arc_i], 0)) / a_ceil
    gR = np.minimum(du_t[t] * S.arc_decay, np.maximum(r_ceil - R[S.arc_i], 0)) / r_ceil
    gain = S.w_i[S.arc_i] * ((oA + oQ) * gA + oR * gR)
    pop = S.pop_i[S.arc_i]
    cap = np.array([p["cap"][TYPES[k]] for k in S.jk_type], dtype=float)
    # capacity-limited value per candidate: best arcs by gain per resident until capacity is used
    order = np.lexsort((-gain / pop, S.arc_jk))
    jk_sorted = S.arc_jk[order]; pop_sorted = pop[order]; gain_sorted = gain[order]
    starts = np.searchsorted(jk_sorted, np.arange(n_jk))
    cum = np.cumsum(pop_sorted)
    base = np.r_[0, cum][starts]
    within = (cum - base[jk_sorted]) <= cap[jk_sorted]
    value = np.bincount(jk_sorted[within], weights=gain_sorted[within], minlength=n_jk)
    used_site = np.zeros(S.n_sites, dtype=bool); used_site[S.site_of_jk[x_on]] = True
    score = np.where(x_on | used_site[S.site_of_jk], -1, value / cost)
    for c in np.argsort(-score):
        if score[c] <= 0:
            break
        if used_site[S.site_of_jk[c]] or cost[c] > spare:
            continue
        x_on[c] = True; used_site[S.site_of_jk[c]] = True; spare -= cost[c]
    return x_on
