"""
Detroit Food Access Optimization Dashboard
Health Services Research Lab, Department of Industrial and Systems Engineering,
Wayne State University.

Companion application to the paper "A Spatial Optimization Framework for
Equitable Healthy Food Access Investment: Application to Detroit".

Design notes
- Each tab is an st.fragment, so a change inside one tab reruns only that tab.
- Every control panel is an st.form: nothing updates until "Apply changes"
  (or "Run optimization") is pressed.
- All data are read from the compact files in data/ (built by
  tools/prepare_data.py), so the app starts in a few seconds.
- The optimization model is built directly in HiGHS (fastmodel.py) with the
  same formulation as the paper.
"""
from __future__ import annotations

import io
import json
import math
import os
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

st.set_page_config(
    page_title="Detroit Food Access Optimization",
    page_icon=":material/storefront:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import app_theme as T  # noqa: E402  (after set_page_config)
import fastmodel as fm  # noqa: E402
import sens_data as SD  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "outputs")
APP_URL = "https://detroit-food-access-dashboard-gurx9yq65mt7ewrbk3qypx.streamlit.app"
REPO_URL = "https://github.com/Shayan9574/detroit-food-access-dashboard"

st.markdown(T.CSS, unsafe_allow_html=True)


# =====================================================================
# DATA (loaded once per server process)
# =====================================================================
@st.cache_resource(show_spinner="Loading data")
def load_all():
    meta = json.load(open(os.path.join(DATA, "model_meta.json")))
    S = fm.load_structure(os.path.join(DATA, "model_structure.npz"))
    S.inc_median = float(meta["inc_median"])
    npz = np.load(os.path.join(DATA, "model_structure.npz"))
    subs = pd.DataFrame(dict(lat=npz["sub_lat"], lon=npz["sub_lon"], x=npz["sub_x"], y=npz["sub_y"],
                             zip=npz["sub_zip"].astype(str), pop=npz["pop_i"], relaxed=npz["sub_relaxed"]))
    sites = pd.DataFrame(meta["sites"]).set_index("j", drop=False)
    outlets = pd.read_parquet(os.path.join(DATA, "outlets.parquet"))
    geo = json.load(open(os.path.join(DATA, "zips.geojson")))
    prof = pd.read_csv(os.path.join(DATA, "zip_profile.csv"), dtype={"ZIP": str})
    prof["NoVehicleRate"] = prof["NoVehicleRate"].astype(float)

    # ZIP centroids from polygon vertices (for map focus)
    cent = {}
    for f in geo["features"]:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        ring = max((np.array(pl[0]) for pl in polys), key=len)
        cent[f["properties"]["ZIP"]] = (float(ring[:, 1].mean()), float(ring[:, 0].mean()))

    # walking-distance statistic: share of subpoints beyond the walking standard
    # from any existing full-service grocery store (projected meters, as in the model)
    groc = sites[sites.site_type == "existing_grocery"][["x", "y"]].to_numpy()
    d = np.sqrt(((subs[["x", "y"]].to_numpy()[:, None, :] - groc[None, :, :]) ** 2).sum(-1)).min(1)
    subs["dist_grocery"] = d
    walk_m = meta["constants"]["walk_m"]
    far = d > walk_m
    lead = dict(share_pop=float((subs["pop"] * far).sum() / subs["pop"].sum()),
                share_pts=float(far.mean()), median_m=float(np.median(d)))
    tmp = subs.assign(farpop=subs["pop"] * far)
    zfar = tmp.groupby("zip")["farpop"].sum() / tmp.groupby("zip")["pop"].sum()
    prof["share_far"] = prof["ZIP"].map(zfar)

    # reference plan (paper baseline portfolio)
    base = pd.read_excel(os.path.join(OUT, "baseline_results.xlsx"), sheet_name="selected_facilities")
    x_ref = np.zeros(len(S.jk_site))
    for j, k in zip(base.site_id, base.intervention_type):
        x_ref[S.jk_lookup[(int(j), k)]] = 1

    pre = os.path.join(OUT, "precomputed")
    floors = json.load(open(os.path.join(pre, "floors.json"))) if os.path.exists(os.path.join(pre, "floors.json")) else {}
    library = json.load(open(os.path.join(pre, "library.json"))) if os.path.exists(os.path.join(pre, "library.json")) else {}
    s11_path = os.path.join(OUT, "sensitivity", "sweep11_impact.xlsx")
    s11 = pd.read_excel(s11_path, sheet_name="comparison") if os.path.exists(s11_path) else None
    return dict(meta=meta, S=S, subs=subs, sites=sites, outlets=outlets, geo=geo, prof=prof,
                cent=cent, lead=lead, x_ref=x_ref, floors=floors, library=library, s11=s11)


D = load_all()
META, S, SUBS, SITES, PROF = D["meta"], D["S"], D["subs"], D["sites"], D["prof"]
NOVEH = META["noveh"]
C0 = META["constants"]

# map of jk column -> site and type (for result tables)
JK = pd.DataFrame(dict(site=S.jk_site, type=[fm.TYPES[t] for t in S.jk_type]))
JK = JK.join(SITES[["site_type", "zip", "lat", "lon"]], on="site")


# =====================================================================
# HELPERS
# =====================================================================
def fmt_money(v, digits=1):
    return f"${v / 1e6:,.{digits}f}M"


def H(s):
    """Flatten an HTML snippet so Markdown never treats indented lines as code."""
    return " ".join(line.strip() for line in s.splitlines() if line.strip())


def note(text, kind=""):
    st.markdown(f'<div class="note-box {kind}">{text}</div>', unsafe_allow_html=True)


def metrics_row(items):
    html = '<div class="metrics">' + "".join(
        f'<div class="metric"><div class="v">{v}</div><div class="k">{k}</div></div>' for k, v in items) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def zip_layers(fill_by=None, highlight=None, carlight=None, alpha=150):
    """ZIP polygons: a filled layer with tooltips, plus outline layers for
    walking-equity ZIP codes and the focused ZIP code."""
    gj = json.loads(json.dumps(D["geo"]))
    gj.pop("crs", None)
    vals = None
    if fill_by is not None:
        s = PROF.set_index("ZIP")[fill_by].astype(float)
        lo, hi = float(s.min()), float(s.max())
        vals = {z: (v - lo) / (hi - lo) if hi > lo else 0.5 for z, v in s.items()}
    P = PROF.set_index("ZIP")
    for f in gj["features"]:
        z = f["properties"]["ZIP"]
        pr = f["properties"]
        pr["fill"] = T.seq_color(vals.get(z, 0), alpha) if vals is not None else [255, 255, 255, 1]
        pr["title"] = f"ZIP {z}"
        if z in P.index:
            r = P.loc[z]
            pr["l1"] = f"Need Index {r.NeedIndex_0_100:.0f} (rank {int(r.NeedRank)} of 32)"
            pr["l2"] = f"{r.NoVehicleRate * 100:.1f}% of households without a vehicle"
        else:
            pr["l1"] = ""; pr["l2"] = ""
    layers = [pdk.Layer("GeoJsonLayer", gj, pickable=True, stroked=True, filled=True,
                        get_fill_color="properties.fill", get_line_color=[255, 255, 255, 235],
                        line_width_min_pixels=1.2)]
    if carlight:
        sub = dict(type="FeatureCollection", features=[f for f in gj["features"] if f["properties"]["ZIP"] in carlight])
        layers.append(pdk.Layer("GeoJsonLayer", sub, pickable=False, stroked=True, filled=False,
                                get_line_color=T.hex_rgb(T.TEAL, 255), line_width_min_pixels=2.6))
    if highlight:
        sub = dict(type="FeatureCollection", features=[f for f in gj["features"] if f["properties"]["ZIP"] == highlight])
        layers.append(pdk.Layer("GeoJsonLayer", sub, pickable=False, stroked=True, filled=False,
                                get_line_color=T.hex_rgb(T.INK, 255), line_width_min_pixels=3.5))
    return layers


TOOLTIP = {"html": "<b>{title}</b><br/>{l1}<br/>{l2}",
           "style": {"backgroundColor": "#FFFFFF", "color": T.INK, "fontFamily": "Public Sans, sans-serif",
                     "fontSize": "12px", "border": f"1px solid {T.LINE}", "borderRadius": "6px", "padding": "8px 10px"}}


def deck(layers, lat=42.37, lon=-83.10, zoom=10.05, height=600):
    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom, pitch=0),
        map_provider="carto", map_style=pdk.map_styles.CARTO_LIGHT,
        tooltip=TOOLTIP, height=height,
    )


# =====================================================================
# MASTHEAD
# =====================================================================
st.markdown(
    '<div class="mast"><div><h1>Detroit Food Access Optimization</h1>'
    '<div class="sub">Where should a city invest a fixed budget so that every neighborhood, and especially '
    'households without a car, can reach healthy food? Explore the food environment, run the optimization '
    'model, and test how the plan responds to its assumptions.</div></div>'
    '<div class="org">Health Services Research Lab<br>Industrial and Systems Engineering<br>Wayne State University</div></div>',
    unsafe_allow_html=True,
)

tab_explore, tab_opt, tab_sens, tab_about = st.tabs(
    ["Food access explorer", "Optimization model", "Sensitivity analysis", "About"])


# =====================================================================
# TAB 1: FOOD ACCESS EXPLORER
# =====================================================================
SHADE_OPTIONS = {
    "Need Index": ("NeedIndex_0_100", "{:.0f}"),
    "Households without a vehicle": ("NoVehicleRate", "{:.0%}"),
    "Poverty rate": ("PovertyRate", "{:.0%}"),
    "Diagnosed diabetes": ("Diabetes", "{:.1f}%"),
    "Residents beyond a 10-minute walk of a grocery": ("share_far", "{:.0%}"),
    "No shading": (None, ""),
}


@st.cache_data(show_spinner=False)
def outlet_points(categories: tuple, zip_focus: str):
    o = D["outlets"]
    o = o[o["category"].isin(categories)]
    if zip_focus != "All of Detroit":
        o = o[o["zip"] == zip_focus]
    o = o.copy()
    rgb = {c: T.hex_rgb(T.OUTLET_COLOR[c], 225) for c in T.OUTLETS}
    o["color"] = o["category"].map(rgb)
    order = {c: i for i, c in enumerate(reversed(T.OUTLETS))}  # draw restaurants first, groceries on top
    o = o.iloc[o["category"].map(order).argsort(kind="stable")]
    o["title"] = o["name"].fillna("").str.title()
    o["l1"] = o["category"]
    o["l2"] = o["address"].fillna("").str.title() + "  ZIP " + o["zip"]
    return o


@st.fragment
def explorer():
    lead = D["lead"]
    P = PROF
    healthy = int(P["healthy_count"].sum()); unhealthy = int(P["unhealthy_count"].sum())
    n_neg = int((P["FoodAccessScore"] < 0).sum())
    carlight = int((P["NoVehicleRate"] > 0.25).sum())
    st.markdown(H(
        f'''<div class="lead"><div>
            <div class="big">{lead["share_pop"] * 100:.0f}%</div>
            <div class="say">of residents in Detroit's 32 ZIP codes live beyond a 10-minute walk of a full-service grocery store.</div>
            <div class="note">Share of residents, allocated evenly to the 2,706 demand points of a 500-meter grid, whose nearest
            of the city's 64 full-service grocery stores lies beyond the model's walking standard of 833 projected meters.
            Half of all demand points are more than {lead["median_m"] / 1000:.1f} km from one.</div></div>
            <div class="facts">
              <div class="fact"><div class="v">{unhealthy / healthy:.1f} to 1</div><div class="k">less healthful outlets for every healthful one, citywide</div></div>
              <div class="fact"><div class="v">{n_neg} of 32</div><div class="k">ZIP codes where less healthful outlets outnumber healthful ones</div></div>
              <div class="fact"><div class="v">{carlight} of 32</div><div class="k">ZIP codes where more than a quarter of households have no vehicle</div></div>
              <div class="fact"><div class="v">{len(D["outlets"]):,}</div><div class="k">food outlets mapped across seven categories</div></div>
            </div></div>'''),
        unsafe_allow_html=True,
    )

    ctl, mapc, side = st.columns([1.05, 2.75, 1.25], gap="medium")
    with ctl:
        with st.form("explorer_form", border=False):
            st.markdown("#### Map settings")
            zips = ["All of Detroit"] + sorted(P["ZIP"].tolist())
            zip_focus = st.selectbox("Focus on", zips, index=0,
                                     help="Zoom to one ZIP code and show its profile on the right.")
            shade = st.selectbox("Shade ZIP codes by", list(SHADE_OPTIONS), index=0)
            cats = st.multiselect("Outlet categories", T.OUTLETS, default=T.OUTLETS,
                                  help="Healthful sources use cool colors; less healthful sources use warm colors.")
            style = st.radio("Show outlets as", ["Individual points", "Density"], horizontal=True,
                             help="Density aggregates outlets into hexagons, which is easier to read when all categories are shown.")
            st.form_submit_button("Apply changes")

    pts = outlet_points(tuple(cats), zip_focus)
    with mapc:
        col, fmt = SHADE_OPTIONS[shade]
        layers = zip_layers(fill_by=col, highlight=None if zip_focus == "All of Detroit" else zip_focus,
                            alpha=120 if style == "Individual points" else 90)
        if style == "Individual points":
            layers.append(pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_fill_color="color",
                                    get_radius=40, radius_min_pixels=2.2, radius_max_pixels=7, pickable=True,
                                    stroked=True, get_line_color=[255, 255, 255, 200], line_width_min_pixels=0.5))
        else:
            layers.append(pdk.Layer("HexagonLayer", pts, get_position=["lon", "lat"], radius=450, opacity=0.75,
                                    extruded=False, coverage=0.92, pickable=False,
                                    color_range=[T.hex_rgb(c)[:3] for c in ["#E3F0EF", "#B5D8D6", "#7DB9B6", "#3F9692", "#0E6E73", "#0A4A4E"]]))
        if zip_focus != "All of Detroit" and zip_focus in D["cent"]:
            la, lo = D["cent"][zip_focus]; view = dict(lat=la, lon=lo, zoom=12.4)
        else:
            view = {}
        st.pydeck_chart(deck(layers, height=610, **view), use_container_width=True)
        leg = "".join(f'<span><i style="background:{T.OUTLET_COLOR[c]}"></i>{c}</span>' for c in cats) if style == "Individual points" \
            else '<span>Outlet density per hexagon <span class="ramp" style="background:linear-gradient(90deg,#E3F0EF,#0A4A4E)"></span></span>'
        if col:
            s = P[col].astype(float)
            leg += f'<span>{shade}: {fmt.format(s.min())}<span class="ramp"></span>{fmt.format(s.max())}</span>'
        st.markdown(f'<div class="legend">{leg}</div>', unsafe_allow_html=True)

    with side:
        if zip_focus == "All of Detroit":
            top = P.sort_values("NeedIndex_0_100", ascending=False).head(5)
            rows = "".join(
                f'<div class="kv"><span>ZIP {r.ZIP}</span><b>{r.NeedIndex_0_100:.0f}</b></div>' for r in top.itertuples())
            st.markdown(H(
                f'''<div class="panel"><h4>Detroit at a glance</h4>
                <div class="kv"><span>Residents in the 32 ZIP codes</span><b>{int(P.Population.sum()):,}</b></div>
                <div class="kv"><span>Full-service grocery stores</span><b>64</b></div>
                <div class="kv"><span>Farmers markets</span><b>31</b></div>
                <div class="kv"><span>Median diabetes prevalence</span><b>{P.Diabetes.median():.1f}%</b></div>
                <div class="kv"><span>Median obesity prevalence</span><b>{P.Obesity.median():.1f}%</b></div>
                <div class="kv"><span>Outlets in this view</span><b>{len(pts):,}</b></div>
                <h4 style="margin-top:14px">Highest Need Index</h4>{rows}
                <div class="muted" style="margin-top:8px">ZIP populations are for full ZIP code tabulation areas,
                some of which extend beyond the city limits.</div></div>'''),
                unsafe_allow_html=True)
        else:
            r = P.set_index("ZIP").loc[zip_focus]
            pos = (32 - int(r.NeedRank)) / 31 * 100
            st.markdown(H(
                f'''<div class="panel"><h4>ZIP {zip_focus}</h4>
                <div class="muted">Need Index {r.NeedIndex_0_100:.0f} of 100, rank {int(r.NeedRank)} of 32</div>
                <div class="rankbar"><span style="width:{r.NeedIndex_0_100:.0f}%"></span></div>
                <div style="height:10px"></div>
                <div class="kv"><span>Population</span><b>{int(r.Population):,}</b></div>
                <div class="kv"><span>Households without a vehicle</span><b>{r.NoVehicleRate:.1%}</b></div>
                <div class="kv"><span>Poverty rate</span><b>{r.PovertyRate:.1%}</b></div>
                <div class="kv"><span>Median household income</span><b>${r.MedianIncome:,.0f}</b></div>
                <div class="kv"><span>Diagnosed diabetes</span><b>{r.Diabetes:.1f}%</b></div>
                <div class="kv"><span>Coronary heart disease</span><b>{r["Coronary Heart Disease"]:.1f}%</b></div>
                <div class="kv"><span>Healthful outlets</span><b>{int(r.healthy_count)}</b></div>
                <div class="kv"><span>Less healthful outlets</span><b>{int(r.unhealthy_count)}</b></div>
                <div class="kv"><span>Residents beyond a 10-minute walk of a grocery</span><b>{r.share_far:.0%}</b></div>
                <div class="kv"><span>Walking-equity ZIP (above 25%)</span><b>{"Yes" if r.NoVehicleRate > 0.25 else "No"}</b></div>
                </div>'''), unsafe_allow_html=True)

    # ---------------- charts
    st.markdown("### Where need is concentrated")
    c1, c2 = st.columns([1.35, 1], gap="medium")
    with c1:
        Q = P.sort_values("NeedIndex_0_100")
        colors = ["rgba(%d,%d,%d,%.2f)" % tuple(T.seq_color(v / 100)[:3] + [1]) for v in Q.NeedIndex_0_100]
        if zip_focus != "All of Detroit":
            colors = [T.TEAL if z == zip_focus else c for z, c in zip(Q.ZIP, colors)]
        fig = go.Figure(go.Bar(
            x=Q.NeedIndex_0_100, y=Q.ZIP, orientation="h", marker_color=colors,
            customdata=np.c_[Q.NoVehicleRate * 100, Q.Diabetes, Q.PovertyRate * 100],
            hovertemplate="ZIP %{y}<br>Need Index %{x:.0f}<br>No vehicle %{customdata[0]:.1f}%"
                          "<br>Diabetes %{customdata[1]:.1f}%<br>Poverty %{customdata[2]:.0f}%<extra></extra>"))
        fig.update_layout(height=560, title=dict(text="Need Index by ZIP code (0 to 100)", font=dict(size=14)),
                          xaxis=dict(range=[0, 105]), yaxis=dict(type="category", tickfont=dict(size=11)), bargap=0.25)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with c2:
        fig = go.Figure()
        cl = P.NoVehicleRate > 0.25
        for flag, name, colr in [(False, "Other ZIP codes", "#9AA7AE"), (True, "More than 25% without a vehicle", T.TEAL)]:
            q = P[cl == flag]
            fig.add_trace(go.Scatter(
                x=q.NoVehicleRate * 100, y=q.NeedIndex_0_100, mode="markers", name=name,
                marker=dict(size=np.sqrt(q.Population) / 7, color=colr, opacity=0.85, line=dict(color="white", width=1)),
                text=q.ZIP, hovertemplate="ZIP %{text}<br>No vehicle %{x:.1f}%<br>Need Index %{y:.0f}<extra></extra>"))
        fig.add_vline(x=25, line=dict(color=T.TEAL, dash="dot", width=1.5))
        fig.update_layout(height=270, title=dict(text="Need and vehicle access (bubble size: population)", font=dict(size=14)),
                          xaxis_title="Households without a vehicle (%)", yaxis_title="Need Index",
                          legend=dict(orientation="h", y=-0.32, x=0))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        mix = pts["category"].value_counts().reindex(T.OUTLETS).dropna()
        fig = go.Figure(go.Bar(x=mix.values, y=mix.index, orientation="h",
                               marker_color=[T.OUTLET_COLOR[c] for c in mix.index],
                               text=[f"{int(v):,}" for v in mix.values], textposition="outside",
                               hovertemplate="%{y}: %{x:,}<extra></extra>"))
        where = "Detroit" if zip_focus == "All of Detroit" else f"ZIP {zip_focus}"
        fig.update_layout(height=270, title=dict(text=f"Outlets in view, {where}", font=dict(size=14)),
                          xaxis=dict(range=[0, max(1, mix.max()) * 1.22], showgrid=False, showticklabels=False),
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with st.expander(f"Outlet list ({len(pts):,} outlets in view)"):
        show = pts[["category", "title", "l2", "zip", "lat", "lon"]].rename(
            columns={"category": "Category", "title": "Name", "l2": "Address", "zip": "ZIP", "lat": "Latitude", "lon": "Longitude"})
        st.dataframe(show, use_container_width=True, hide_index=True, height=320)
        st.download_button("Download outlet list (CSV)", show.to_csv(index=False).encode(),
                           file_name="detroit_food_outlets.csv", mime="text/csv")


with tab_explore:
    explorer()


# =====================================================================
# TAB 2: OPTIMIZATION MODEL
# =====================================================================
PRIORITY = {
    "Equal weights": (1 / 3, 1 / 3, 1 / 3),
    "Food access focus": (0.6, 0.2, 0.2),
    "Unhealthy exposure focus": (0.2, 0.6, 0.2),
    "Cardiometabolic focus": (0.2, 0.2, 0.6),
}


def params_from_state(v: dict) -> dict:
    p = dict(fm.DEFAULTS)
    p["budget"] = float(v["budget"]) * 1e6
    p["theta"] = v["theta"] / 100
    p["nv_threshold"] = v["nv"] / 100
    p["apply_walking"] = bool(v["walk"])
    p["omega"] = tuple(v["omega"])
    p["gamma"] = float(v["gamma"]); p["lam"] = float(v["lam"])
    p["cost"] = {k: float(v["cost"][k]) for k in fm.TYPES}
    p["dfa"] = {k: float(v["dfa"][k]) for k in fm.TYPES}
    p["du"] = {k: float(v["du"][k]) for k in fm.TYPES}
    p["beta"] = C0["beta"]; p["ceil_factor"] = C0["ceil_factor"]
    p["cap"] = {k: float(C0["cap"][k]) for k in fm.TYPES}
    return p


BUDGET_MIN = 38.0   # $M; lowest budget offered on the slider

DEFAULT_V = dict(budget=40.0, theta=100, nv=25, walk=True, priority="Equal weights", omega=PRIORITY["Equal weights"],
                 gamma=0.3, lam=0.0, cost={k: float(C0["cost"][k]) for k in fm.TYPES},
                 dfa={k: float(C0["dfa"][k]) for k in fm.TYPES}, du={k: float(C0["du"][k]) for k in fm.TYPES},
                 tl=90, gap=2.0)


def carlight_set(nv):
    return {z for z, r in NOVEH.items() if r > nv}


def budget_floor(v: dict):
    """Smallest budget for which a feasible plan is known for these settings, using the
    precomputed minimum-cost portfolios repriced at the chosen costs. Returns (floor, x)."""
    p = params_from_state(v)
    cost = fm.site_costs(S, p["cost"], p["gamma"])
    need = carlight_set(p["nv_threshold"]) if p["apply_walking"] else set()
    best = (None, None)
    for e in D["floors"].values():
        if not e or e["theta"] + 1e-9 < p["theta"]:
            continue
        if not need.issubset(set(e["carlight"])):
            continue
        c = float(cost[e["jk"]].sum())
        if best[0] is None or c < best[0]:
            x = np.zeros(len(S.jk_site)); x[e["jk"]] = 1
            best = (c, x)
    return best


def library_hit(v: dict):
    """Precomputed solution when the settings match a library scenario exactly."""
    d = dict(DEFAULT_V)
    same = all(v[k] == d[k] for k in ("theta", "walk", "gamma", "lam", "cost", "dfa", "du")) and \
        tuple(round(w, 6) for w in v["omega"]) == tuple(round(w, 6) for w in d["omega"])
    if not same or float(v["budget"]) != round(float(v["budget"])):
        return None
    return D["library"].get(f"B{int(v['budget'])}_nv{int(v['nv'])}")


def assemble(p, x_on, full, status, gap, bound, seconds, source):
    if full is None:
        raise RuntimeError("Plan evaluation failed.")
    lp, info = fm.build_lp(S, p, NOVEH, "max", link_rows=False)
    obj = float(np.dot(np.array(lp.col_cost_), full))
    z = full[info["off_z"]:info["off_z"] + info["n_a"]]
    cov = np.bincount(S.arc_i, weights=z, minlength=S.n_i)
    wcov = np.bincount(S.arc_i[S.arc_walk], weights=z[S.arc_walk], minlength=S.n_i)
    return dict(x_on=x_on.astype(bool), objective=obj, cost=float(info["cost"][x_on.astype(bool)].sum()),
                jk_cost=info["cost"], coverage=cov, walk_cov=wcov, status=status, gap=gap, bound=bound,
                seconds=seconds, source=source, n_walk=info["n_walk"], n_carlight=info["n_carlight"],
                budget=p["budget"])


@st.cache_resource
def solver_lock():
    import threading
    return threading.Lock()


@st.cache_data(show_spinner=False, max_entries=300)
def solve_cached(key: str):
    with solver_lock():
        return _solve(key)


def _solve(key: str):
    v = json.loads(key)
    p = params_from_state(v)
    t0 = time.time()
    lib = library_hit(v)
    if lib:
        x = np.zeros(len(S.jk_site)); x[lib["jk"]] = 1
        full = fm.fixed_x_completion(S, p, NOVEH, x)
        if full is not None:
            return assemble(p, x, full, "Precomputed", lib["gap"], None, time.time() - t0, "precomputed")
    # warm-start candidates: library plan at the same cutoff and a lower budget, the
    # reference plan, and the minimum-cost portfolio (always feasible when budget >= floor)
    cands = []
    same_nv = [e for e in D["library"].values() if e and e["cutoff_pct"] == int(v["nv"]) and e["budget"] <= v["budget"]]
    if same_nv:
        e = max(same_nv, key=lambda e: e["budget"]); x = np.zeros(len(S.jk_site)); x[e["jk"]] = 1; cands.append(x)
    cands.append(D["x_ref"])
    fl = budget_floor(v)[1]
    if fl is not None:
        cands.append(fl)
    best = None
    lp, _ = fm.build_lp(S, p, NOVEH, "max", link_rows=False)
    cvec = np.array(lp.col_cost_)
    cost = fm.site_costs(S, p["cost"], p["gamma"])
    for x in cands:
        if cost[x.astype(bool)].sum() > p["budget"] + 1e-6:
            continue
        full = fm.fixed_x_completion(S, p, NOVEH, x)
        if full is None:
            continue
        # spend any remaining budget greedily, then keep whichever start is better
        xg = fm.greedy_fill(S, p, NOVEH, x.astype(bool), full)
        fg = fm.fixed_x_completion(S, p, NOVEH, xg.astype(float))
        for xx, ff in ((x, full), (xg.astype(float), fg)):
            if ff is not None:
                o = float(np.dot(cvec, ff))
                if best is None or o > best[0]:
                    best = (o, xx)
    r = fm.solve(S, p, NOVEH, time_limit=v["tl"], gap=v["gap"] / 100,
                 start_x=None if best is None else best[1], link_rows=False)
    if not r.get("feasible"):
        return dict(infeasible=True, status=r["status"], seconds=time.time() - t0)
    full = fm.fixed_x_completion(S, p, NOVEH, r["x_on"].astype(float))
    if full is None:
        return dict(infeasible=True, status="plan could not be evaluated", seconds=time.time() - t0)
    return assemble(p, r["x_on"], full, r["status"], r["gap"], r["bound"], time.time() - t0, "solved")


@st.cache_resource(show_spinner="Preparing the reference plan")
def reference_result():
    p = params_from_state(DEFAULT_V)
    full = fm.fixed_x_completion(S, p, NOVEH, D["x_ref"])
    if full is None:
        raise RuntimeError("The reference plan could not be evaluated; see the server log for the HiGHS status.")
    return assemble(p, D["x_ref"], full, "Reference", 0.00499, None, 0.0, "reference")


def result_tables(res):
    sel = JK[res["x_on"]].copy()
    sel["cost"] = res["jk_cost"][res["x_on"]]
    sel["Type"] = sel["type"].map(T.TYPE_NAME)
    comp = sel.groupby("type").agg(n=("site", "size"), spend=("cost", "sum")).reindex(T.TYPES).fillna(0)
    subs = SUBS.assign(cov=res["coverage"], wcov=res["walk_cov"])
    cl = carlight_set(res.get("nv", 0.25))
    z = subs.groupby("zip").agg(points=("cov", "size"), cov=("cov", "mean"), wcov=("wcov", "mean"))
    cnt = sel.pivot_table(index="zip", columns="type", values="site", aggfunc="count").reindex(columns=T.TYPES).fillna(0)
    z = z.join(cnt).fillna(0)
    z = z.join(PROF.set_index("ZIP")[["Population", "NoVehicleRate", "NeedIndex_0_100"]])
    z["carlight"] = z.index.isin(cl)
    return sel, comp, z


def make_pdf(v, res, comp, ztab):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from fpdf import FPDF

    fig, ax = plt.subplots(figsize=(6.4, 5.4), dpi=170)
    for f in D["geo"]["features"]:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            ring = np.array(poly[0])
            carl = f["properties"]["ZIP"] in carlight_set(v["nv"] / 100)
            ax.fill(ring[:, 0], ring[:, 1], color="#EEF2F0", zorder=1)
            ax.plot(ring[:, 0], ring[:, 1], color=T.TEAL if carl else "#AAB5BA", lw=1.4 if carl else 0.5, zorder=2)
    sel = JK[res["x_on"]]
    for k in T.TYPES:
        q = sel[sel.type == k]
        ax.scatter(q.lon, q.lat, s=10 if k != "grocery_new" else 34, color=T.TYPE_COLOR[k], label=T.TYPE_NAME[k],
                   edgecolor="white", linewidth=0.3, zorder=3)
    ax.set_axis_off(); ax.set_aspect(1 / math.cos(math.radians(42.36)))
    ax.legend(loc="lower left", fontsize=6.5, frameon=False)
    buf = io.BytesIO(); fig.savefig(buf, format="png", bbox_inches="tight"); plt.close(fig); buf.seek(0)

    pdf = FPDF(format="Letter", unit="mm")
    pdf.set_auto_page_break(True, 12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 8, "Detroit Food Access Optimization: scenario summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(86, 99, 109)
    pdf.cell(0, 5, f"Generated {time.strftime('%B %d, %Y')} from {APP_URL}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(29, 43, 54)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, "Settings", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    s = [f"Budget ${v['budget']:.1f}M; coverage target {v['theta']}%; no-vehicle cutoff {v['nv']}%; "
         f"walking equity {'enforced' if v['walk'] else 'not enforced'}",
         f"Outcome weights A/R/Q = {v['omega'][0]:.2f}/{v['omega'][1]:.2f}/{v['omega'][2]:.2f}; "
         f"income cost elasticity {v['gamma']:.1f}; cost penalty {v['lam']:.1f}",
         "Base costs ($): " + ", ".join(f"{T.TYPE_SHORT[k]} {v['cost'][k]:,.0f}" for k in T.TYPES),
         "Impact (dFA/dU): " + ", ".join(f"{T.TYPE_SHORT[k]} {v['dfa'][k]:.2f}/{v['du'][k]:.2f}" for k in T.TYPES)]
    for line in s:
        pdf.multi_cell(0, 4.6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, "Result", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 4.6, f"{int(res['x_on'].sum())} interventions, spend ${res['cost'] / 1e6:.2f}M "
                   f"({100 * res['cost'] / res['budget']:.1f}% of budget), objective {res['objective']:.2f}, "
                   f"{res['n_walk']} subpoints under the walking-equity rule. Status: {res['status']}.",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    y0 = pdf.get_y()
    pdf.image(buf, x=10, y=y0, w=118)
    pdf.set_xy(132, y0)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(42, 5, "Intervention type", border="B"); pdf.cell(14, 5, "Count", border="B", align="R")
    pdf.cell(18, 5, "Spend $M", border="B", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for k in T.TYPES:
        pdf.set_x(132)
        pdf.cell(42, 5, T.TYPE_NAME[k]); pdf.cell(14, 5, f"{int(comp.loc[k, 'n'])}", align="R")
        pdf.cell(18, 5, f"{comp.loc[k, 'spend'] / 1e6:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(max(pdf.get_y(), y0 + 100) + 4)
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, "By ZIP code", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 8)
    heads = [("ZIP", 16), ("Pop.", 18), ("No veh.", 16), ("Need", 13)] + [(T.TYPE_SHORT[k], 10) for k in T.TYPES] + [("Coverage", 18)]
    for h, w_ in heads:
        pdf.cell(w_, 5, h, border="B", align="R" if h != "ZIP" else "L")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for zc, r in ztab.sort_index().iterrows():
        cells = [(zc, 16, "L"), (f"{r.Population:,.0f}", 18, "R"), (f"{r.NoVehicleRate * 100:.1f}%", 16, "R"),
                 (f"{r.NeedIndex_0_100:.0f}", 13, "R")] + [(f"{int(r[k])}", 10, "R") for k in T.TYPES] + [(f"{r['cov']:.2f}", 18, "R")]
        for t_, w_, a_ in cells:
            pdf.cell(w_, 4.4, str(t_), align=a_)
        pdf.ln()
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.multi_cell(0, 3.8, "Live solves use a relaxed optimality gap and a time limit; see the paper for the 0.5 percent "
                   "baseline. NG, UG, NF, UF, M: new grocery, grocery upgrade, new farmers market, farmers market "
                   "upgrade, mobile market.", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


@st.cache_data(show_spinner=False, max_entries=50)
def pdf_cached(key: str, _res, _comp, _ztab):
    return make_pdf(json.loads(key), _res, _comp, _ztab)


@st.fragment
def optimizer():
    if "opt_v" not in st.session_state:
        st.session_state.opt_v = json.loads(json.dumps(DEFAULT_V))
        st.session_state.opt_key = None
    v0 = st.session_state.opt_v
    floor0, _ = budget_floor(v0)
    floor0 = max(BUDGET_MIN, math.ceil(floor0 / 5e5) / 2) if floor0 else 40.0

    left, right = st.columns([1.05, 3.6], gap="medium")
    with left:
        with st.form("opt_form", border=False):
            st.markdown("#### Plan settings")
            budget = st.slider("Capital budget ($ million)", min_value=float(min(floor0, 100.0)), max_value=100.0,
                               value=float(max(v0["budget"], floor0)), step=0.5,
                               help=f"The slider starts at ${floor0:.1f}M: $38M, or more if the settings last applied need a larger "
                                    "budget for a feasible plan. If other changes raise that minimum, the budget is lifted "
                                    "to it automatically when you run the model.")
            theta = st.select_slider("Coverage target (%)", options=[75, 80, 85, 90, 95, 100], value=v0["theta"],
                                     help="Minimum service level required at every demand point.")
            nv = st.slider("No-vehicle cutoff (%)", 21, 40, v0["nv"],
                           help="ZIP codes where more households than this lack a vehicle must have walking access "
                                "to a fixed-site facility at every demand point.")
            walk = st.checkbox("Enforce walking equity", value=v0["walk"])
            with st.expander("Outcome weights"):
                pr = st.radio("Priority", list(PRIORITY) + ["Custom"], index=(list(PRIORITY) + ["Custom"]).index(v0["priority"]))
                ca = st.slider("Food access", 0.0, 1.0, float(v0["omega"][0]), 0.05)
                cr = st.slider("Unhealthy exposure", 0.0, 1.0, float(v0["omega"][1]), 0.05)
                cq = st.slider("Cardiometabolic burden", 0.0, 1.0, float(v0["omega"][2]), 0.05)
                st.caption("The three custom sliders apply when Priority is Custom; they are rescaled to sum to one.")
            with st.expander("Costs"):
                gamma = st.slider("Income cost elasticity", 0.0, 0.7, float(v0["gamma"]), 0.1,
                                  help="Site cost = base cost x (1 + elasticity x (ZIP income − median) / median).")
                lam = st.slider("Cost penalty", 0.0, 5.0, float(v0["lam"]), 0.5,
                                help="Penalizes spending in the objective. Baseline 0.")
                cost = {}
                for k in T.TYPES:
                    b = float(C0["cost"][k])
                    cost[k] = st.number_input(f"{T.TYPE_NAME[k]} ($)", min_value=round(b * 0.8), max_value=round(b * 1.2),
                                              value=int(v0["cost"][k]), step=int(b * 0.05),
                                              help=f"Baseline ${b:,.0f}. Allowed range is the tested range, plus or minus 20 percent.")
            with st.expander("Intervention impacts (assumed)"):
                st.caption("Food access gain and unhealthy exposure reduction per intervention, on a 0 to 1 scale. "
                           "Allowed range is the tested range, plus or minus 30 percent of the baseline values.")
                dfa, du = {}, {}
                for k in T.TYPES:
                    a0, u0 = float(C0["dfa"][k]), float(C0["du"][k])
                    c_a, c_u = st.columns(2)
                    dfa[k] = c_a.number_input(f"{T.TYPE_SHORT[k]} access", min_value=round(a0 * 0.7, 3), max_value=round(a0 * 1.3, 3),
                                              value=float(v0["dfa"][k]), step=0.01, format="%.2f", help=T.TYPE_NAME[k])
                    du[k] = c_u.number_input(f"{T.TYPE_SHORT[k]} exposure", min_value=round(u0 * 0.7, 3), max_value=round(u0 * 1.3, 3),
                                             value=float(v0["du"][k]), step=0.01, format="%.2f", help=T.TYPE_NAME[k])
            with st.expander("Solver"):
                tl = st.slider("Time limit (seconds)", 30, 180, int(v0["tl"]), 10)
                gap = st.slider("Target optimality gap (%)", 0.5, 5.0, float(v0["gap"]), 0.5)
            run = st.form_submit_button("Run optimization")
        if st.button("Show reference plan", use_container_width=True):
            st.session_state.opt_v = json.loads(json.dumps(DEFAULT_V)); st.session_state.opt_key = None
            st.rerun(scope="fragment")

    msg = None
    if run:
        omega = PRIORITY.get(pr) if pr != "Custom" else None
        if omega is None:
            tot = ca + cr + cq
            omega = (ca / tot, cr / tot, cq / tot) if tot > 0 else PRIORITY["Equal weights"]
        v = dict(budget=float(budget), theta=int(theta), nv=int(nv), walk=bool(walk), priority=pr, omega=list(omega),
                 gamma=round(float(gamma), 2), lam=float(lam), cost={k: float(cost[k]) for k in T.TYPES},
                 dfa={k: round(float(dfa[k]), 4) for k in T.TYPES}, du={k: round(float(du[k]), 4) for k in T.TYPES},
                 tl=int(tl), gap=float(gap))
        fl, _ = budget_floor(v)
        if fl is None:
            msg = ("No feasible plan is known for this combination of coverage target and no-vehicle cutoff. "
                   "Raise the cutoff or lower the coverage target.", "bad")
        else:
            flr = max(BUDGET_MIN, math.ceil(fl / 5e5) / 2)
            if v["budget"] < flr:
                msg = (f"The budget was raised from ${v['budget']:.1f}M to ${flr:.1f}M, the smallest budget allowed "
                       "for these settings.", "warn")
                v["budget"] = flr
            st.session_state.opt_v = v
            st.session_state.opt_key = json.dumps(v, sort_keys=True)

    v = st.session_state.opt_v
    key = st.session_state.opt_key
    with right:
        if msg:
            note(*msg)
        if key is None:
            try:
                res = dict(reference_result())
            except Exception as e:  # show a readable message instead of a crash
                note(f"The reference plan could not be loaded on this server ({e}). Press Run optimization to compute a plan.", "bad")
                return
            res["nv"] = 0.25
            head = ("Reference plan: the paper's baseline portfolio at $40M (full coverage, walking equity in car-light "
                    "ZIP codes, solved offline to a 0.5 percent optimality gap). Change the settings and press "
                    "<b>Run optimization</b> to compute a new plan.")
        else:
            lib = library_hit(v)
            with st.spinner("Precomputed scenario found, loading" if lib else
                            f"Solving the model (up to {v['tl']} seconds at a {v['gap']:.1f}% target gap)"):
                res = solve_cached(key)
            if res.get("infeasible"):
                note(f"No feasible plan was found within the time limit ({res['status']}). Increase the budget or the time limit.", "bad")
                return
            res = dict(res); res["nv"] = v["nv"] / 100
            if res["source"] == "precomputed":
                head = "Loaded instantly from the library of precomputed scenarios (solved offline to a 1 percent gap)."
            else:
                gtxt = f"{res['gap'] * 100:.2f}%" if res["gap"] is not None else "n/a"
                head = (f"Solved in {res['seconds']:.0f} seconds. Status: {res['status']}; achieved gap {gtxt}. "
                        "Repeating the same settings returns this plan instantly.")
        note(head)
        sel, comp, ztab = result_tables(res)
        n = int(res["x_on"].sum())
        metrics_row([
            ("Objective", f"{res['objective']:.2f}"),
            ("Interventions", f"{n}"),
            ("Spend", f"{fmt_money(res['cost'], 2)}"),
            ("Budget used", f"{100 * res['cost'] / res['budget']:.1f}%"),
            ("Walking-equity demand points", f"{res['n_walk']:,}"),
            ("Mean coverage", f"{res['coverage'].mean():.2f}"),
        ])

        mc, cc = st.columns([2.25, 1], gap="medium")
        with mc:
            cl = carlight_set(res["nv"])
            layers = zip_layers(fill_by="NeedIndex_0_100", carlight=cl, alpha=80)
            ex = SITES[SITES.site_type.isin(["existing_grocery", "existing_farmers"])].copy()
            up_sites = set(sel.loc[sel.type.isin(["grocery_upgrade", "farmers_upgrade"]), "site"])
            ex = ex[~ex.j.isin(up_sites)].assign(title="Existing outlet, not upgraded",
                                                 l1=lambda d: d.site_type.map({"existing_grocery": "Grocery store",
                                                                               "existing_farmers": "Farmers market"}),
                                                 l2=lambda d: "ZIP " + d.zip)
            layers.append(pdk.Layer("ScatterplotLayer", ex, get_position=["lon", "lat"], filled=False, stroked=True,
                                    get_line_color=T.hex_rgb(T.SLATE, 220), line_width_min_pixels=1.2,
                                    get_radius=60, radius_min_pixels=3, pickable=True))
            pts = sel.assign(color=sel.type.map({k: T.hex_rgb(c, 235) for k, c in T.TYPE_COLOR.items()}),
                             r=sel.type.map({"grocery_new": 9, "grocery_upgrade": 6, "farmers_new": 4.5,
                                             "farmers_upgrade": 5, "mobile_market": 4.5}),
                             title=sel["Type"], l1=sel["cost"].map(lambda c: f"Cost ${c:,.0f}"), l2="ZIP " + sel["zip"])
            layers.append(pdk.Layer("ScatterplotLayer", pts, get_position=["lon", "lat"], get_fill_color="color",
                                    get_radius="r * 20", radius_min_pixels=3, radius_max_pixels=14, stroked=True,
                                    get_line_color=[255, 255, 255, 255], line_width_min_pixels=1, pickable=True))
            st.pydeck_chart(deck(layers, height=560), use_container_width=True)
            leg = "".join(f'<span><i style="background:{T.TYPE_COLOR[k]}"></i>{T.TYPE_NAME[k]}</span>' for k in T.TYPES)
            leg += (f'<span><i style="border:1.5px solid {T.SLATE};background:transparent"></i>Existing outlet, not upgraded</span>'
                    f'<span><i class="sq" style="border:2px solid {T.TEAL};background:transparent"></i>Walking-equity ZIP</span>'
                    '<span>Need Index<span class="ramp"></span></span>')
            st.markdown(f'<div class="legend">{leg}</div>', unsafe_allow_html=True)
        with cc:
            try:
                ref = result_tables(dict(reference_result(), nv=0.25))[1]
            except Exception:
                ref = comp.assign(n=0)
            fig = go.Figure()
            fig.add_trace(go.Bar(y=[T.TYPE_NAME[k] for k in T.TYPES], x=ref["n"], orientation="h", name="Reference plan",
                                 marker_color="rgba(29,43,54,0.12)", hovertemplate="Reference: %{x}<extra></extra>"))
            fig.add_trace(go.Bar(y=[T.TYPE_NAME[k] for k in T.TYPES], x=comp["n"], orientation="h", name="This plan",
                                 marker_color=[T.TYPE_COLOR[k] for k in T.TYPES],
                                 text=[f"{int(a)}  ({b / 1e6:.1f}M)" for a, b in zip(comp["n"], comp["spend"])],
                                 textposition="outside", cliponaxis=False,
                                 hovertemplate="%{y}: %{x}<extra></extra>"))
            fig.update_layout(barmode="overlay", height=300, title=dict(text="Portfolio by type (count and spend)", font=dict(size=14)),
                              yaxis=dict(autorange="reversed"), xaxis=dict(showgrid=False, showticklabels=False, range=[0, max(comp["n"].max(), ref["n"].max()) * 1.75]),
                              legend=dict(orientation="h", y=-0.12, x=0), bargap=0.35)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            spend = comp["spend"] / max(res["cost"], 1)
            fig = go.Figure(go.Pie(labels=[T.TYPE_NAME[k] for k in T.TYPES], values=comp["spend"], hole=0.62, sort=False,
                                   marker=dict(colors=[T.TYPE_COLOR[k] for k in T.TYPES], line=dict(color="white", width=2)),
                                   textinfo="percent", textposition="inside", insidetextorientation="horizontal",
                                   hovertemplate="%{label}<br>$%{value:,.0f}<extra></extra>"))
            fig.update_layout(height=270, showlegend=False, margin=dict(l=20, r=20, t=40, b=20),
                              title=dict(text="Share of spend", font=dict(size=14)),
                              annotations=[dict(text=fmt_money(res["cost"]), showarrow=False, font=dict(size=16, color=T.INK))])
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown("### Results by ZIP code")
        zt = ztab.reset_index().rename(columns={"zip": "ZIP"})
        zt = zt.assign(**{"Walking equity": np.where(zt.carlight, "Yes", "")})
        zt["NoVehicleRate"] = zt["NoVehicleRate"] * 100
        show = zt[["ZIP", "Population", "NoVehicleRate", "NeedIndex_0_100", "Walking equity"] + T.TYPES + ["cov", "wcov"]]
        show.columns = ["ZIP", "Population", "No vehicle", "Need Index", "Walking equity"] + \
            [T.TYPE_SHORT[k] for k in T.TYPES] + ["Coverage", "Walking coverage"]
        st.dataframe(
            show.sort_values("Need Index", ascending=False), use_container_width=True, hide_index=True, height=360,
            column_config={
                "Population": st.column_config.NumberColumn(format="%d"),
                "No vehicle": st.column_config.NumberColumn(format="%.1f%%", help="Households without a vehicle"),
                "Need Index": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                "Coverage": st.column_config.NumberColumn(format="%.2f", help="Mean total assignment per demand point"),
                "Walking coverage": st.column_config.NumberColumn(format="%.2f", help="Mean assignment to walking-eligible facilities"),
                **{T.TYPE_SHORT[k]: st.column_config.NumberColumn(T.TYPE_SHORT[k], help=T.TYPE_NAME[k], format="%d") for k in T.TYPES},
            })
        st.caption("NG new grocery store, UG grocery upgrade, NF new farmers market, UF farmers market upgrade, M mobile market.")
        zt_csv = show.copy(); zt_csv["No vehicle"] = zt_csv["No vehicle"].round(1)
        d1, d2, d3 = st.columns(3)
        sites_csv = sel[["Type", "site", "zip", "lat", "lon", "cost"]].rename(
            columns={"site": "site_id", "zip": "ZIP", "lat": "latitude", "lon": "longitude", "cost": "cost_usd"})
        d1.download_button("Download selected sites (CSV)", sites_csv.to_csv(index=False).encode(),
                           file_name="optimized_portfolio_sites.csv", mime="text/csv", use_container_width=True)
        d2.download_button("Download ZIP results (CSV)", zt_csv.to_csv(index=False).encode(),
                           file_name="optimized_portfolio_by_zip.csv", mime="text/csv", use_container_width=True)
        pkey = json.dumps(v, sort_keys=True) if key else json.dumps(DEFAULT_V, sort_keys=True)
        try:
            pdf = pdf_cached(pkey, res, comp, ztab)
            d3.download_button("Download scenario summary (PDF)", pdf, file_name="scenario_summary.pdf",
                               mime="application/pdf", use_container_width=True)
        except Exception as e:  # PDF is a convenience; never block the tab
            d3.caption(f"PDF summary unavailable: {e}")
        st.markdown(
            '<div class="muted" style="margin-top:8px">Live solves use the paper\'s formulation with a relaxed target gap and a '
            'time limit, so results can differ slightly from the 0.5 percent solutions reported in the paper. The redundant '
            'linking constraint z ≤ x is omitted in the app because the capacity constraint already implies it; the set of '
            'feasible plans is unchanged.</div>', unsafe_allow_html=True)


with tab_opt:
    optimizer()


# =====================================================================
# TAB 3: SENSITIVITY ANALYSIS
# =====================================================================
IMPACT_KEY = "Intervention impact coefficients"
TIER_COLOR = {1: T.INK, 2: T.OCHRE, 3: "#7F8C93", 4: "#B9C3C7"}
RUN_LABEL = {"base": "Baseline re-solve", "NG_minus30": "New grocery −30%", "NG_plus30": "New grocery +30%",
             "UG_minus30": "Grocery upgrade −30%", "UG_plus30": "Grocery upgrade +30%",
             "M_minus30": "Mobile market −30%", "M_plus30": "Mobile market +30%",
             "NF_minus30": "New farmers market −30%", "NF_plus30": "New farmers market +30%",
             "UF_minus30": "Farmers upgrade −30%", "UF_plus30": "Farmers upgrade +30%",
             "M_NF_swap": "Mobile and new farmers swapped"}


def sens_overview():
    tor = sorted(SD.TORNADO_ADV, key=lambda d: d["swing"])
    fig = go.Figure(go.Bar(
        y=[d["param"] for d in tor], x=[d["swing"] for d in tor], orientation="h",
        marker_color=[TIER_COLOR[d["tier"]] for d in tor],
        text=[f"{d['swing']:.0f}%" if d["swing"] >= 3 else f"{d['swing']:.1f}%" for d in tor], textposition="outside",
        customdata=[f"Tier {d['tier']}: {d['note']}" for d in tor],
        hovertemplate="%{y}<br>Objective swing %{x:.1f}%<br>%{customdata}<extra></extra>"))
    fig.update_layout(height=430, title=dict(text="Objective swing across each tested range, first nine sweeps", font=dict(size=14)),
                      xaxis=dict(title="Range of the objective divided by its smallest feasible value (%)", range=[0, 125]))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        '<div class="legend">'
        f'<span><i class="sq" style="background:{TIER_COLOR[1]}"></i>Tier 1, structural drivers</span>'
        f'<span><i class="sq" style="background:{TIER_COLOR[2]}"></i>Tier 2, composition drivers</span>'
        f'<span><i class="sq" style="background:{TIER_COLOR[3]}"></i>Tier 3, measurable effect</span>'
        f'<span><i class="sq" style="background:{TIER_COLOR[4]}"></i>Tier 4, negligible</span></div>',
        unsafe_allow_html=True)


def sens_impact():
    s11 = D["s11"]
    if s11 is None:
        note("The impact-coefficient results file is not available in this deployment.", "warn"); return
    q = s11.copy()
    q["Run"] = q["label"].map(RUN_LABEL)
    st.markdown(
        "Each run raises or lowers the assumed food access and unhealthy exposure values of one intervention type "
        "by 30 percent, together; one further run swaps the values of new farmers markets and mobile markets. "
        "Because the objective is normalized by ceilings that scale with the largest impact values, objective "
        "values are not comparable across these runs, so the sweep is summarized by the composition of the plan.")
    cols = {"grocery_new": "n_grocery_new", "grocery_upgrade": "n_grocery_upgrade", "farmers_new": "n_farmers_new",
            "farmers_upgrade": "n_farmers_upgrade", "mobile_market": "n_mobile_market"}
    fig = go.Figure()
    for k in T.TYPES:
        fig.add_trace(go.Bar(x=q["Run"], y=q[cols[k]], name=T.TYPE_NAME[k], marker_color=T.TYPE_COLOR[k],
                             hovertemplate="%{x}<br>" + T.TYPE_NAME[k] + ": %{y}<extra></extra>"))
    fig.update_layout(barmode="stack", height=420, title=dict(text="Plan composition in each run", font=dict(size=14)),
                      legend=dict(orientation="h", y=-0.42, x=0), xaxis=dict(tickangle=-30), yaxis_title="Interventions",
                      margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    fig = go.Figure(go.Bar(x=q["Run"], y=q["pct_baseline_sites_kept"], marker_color=T.TEAL,
                           text=[f"{v:.1f}%" for v in q["pct_baseline_sites_kept"]], textposition="outside",
                           hovertemplate="%{x}<br>%{y:.1f}% of baseline selections kept<extra></extra>"))
    fig.update_layout(height=300, title=dict(text="Share of baseline site and type selections kept", font=dict(size=14)),
                      yaxis=dict(range=[0, 110], title="%"), xaxis=dict(tickangle=-30))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    tbl = q[["Run", "termination", "n_facilities", "n_grocery_new", "n_grocery_upgrade", "n_farmers_new",
             "n_farmers_upgrade", "n_mobile_market", "pct_baseline_sites_kept", "achieved_gap"]]
    tbl.columns = ["Run", "Status", "Total", "NG", "UG", "NF", "UF", "M", "Kept (%)", "Gap"]
    tbl = tbl.assign(Status=tbl.Status.map({"optimal": "Optimal", "maxtimelimit": "Time limit"}).fillna(tbl.Status))
    st.dataframe(tbl, use_container_width=True, hide_index=True)
    st.markdown(
        '<div class="panel"><h4>Key findings</h4><ul style="margin:0;padding-left:18px">'
        "<li>Every run is feasible at $40M, with 287 to 311 interventions, and keeps 87.5 to 96.6 percent of the "
        "baseline selections.</li>"
        "<li>Four new grocery stores are selected in every run that changes a single type, and the upgrade "
        "categories move by at most four facilities.</li>"
        "<li>What responds is the balance between new farmers markets and mobile markets: with mobile markets 30 "
        "percent less effective there are 197 new farmers markets and 60 mobile markets.</li>"
        "<li>Even when the two types swap values, new farmers markets remain the largest category (139 against 98), "
        "because only walking-eligible facilities can satisfy the equity constraint in car-light ZIP codes.</li>"
        "<li>Seven of the twelve runs reached the 30-minute limit, with gaps between 0.93 and 1.78 percent.</li></ul></div>",
        unsafe_allow_html=True)


def sens_param(name):
    block = SD.SENS_ADV[name]
    unit = block.get("unit", "")
    xlabel = block["label"] + (f" ({unit})" if unit else "")
    st.markdown(block["description"])
    feas = SD._sens_feasible(block)
    bad = SD._sens_infeasible_note(block)
    if bad:
        note(f"No feasible plan was found at {', '.join(bad)}; these values appear in the table but not in the charts.", "warn")
    labels = [r["label"] for r in feas]
    fig = go.Figure()
    for k in T.TYPES:
        fig.add_trace(go.Bar(x=labels, y=[r.get(k, 0) for r in feas], name=T.TYPE_NAME[k], marker_color=T.TYPE_COLOR[k],
                             opacity=0.9, hovertemplate="%{x}<br>" + T.TYPE_NAME[k] + ": %{y}<extra></extra>"))
    fig.add_trace(go.Scatter(x=labels, y=[r["objective"] for r in feas], name="Objective", mode="lines+markers+text",
                             text=[f"{r['objective']:.1f}" for r in feas], textposition="top center", yaxis="y2",
                             textfont=dict(color=T.INK, size=12),
                             line=dict(color=T.INK, width=3), marker=dict(size=10, color=T.INK, line=dict(color="white", width=2)),
                             hovertemplate="%{x}<br>Objective %{y:.2f}<extra></extra>"))
    base_lbl = next((r["label"] for r in feas if r["value"] == block["baseline"]), None)
    if base_lbl is not None:
        i = labels.index(base_lbl)
        fig.add_vrect(x0=i - 0.48, x1=i + 0.48, fillcolor=T.TEAL, opacity=0.08, line_width=0,
                      annotation_text="baseline", annotation_position="top left")
    objs = [r["objective"] for r in feas]
    top = max(r.get("total", 0) or 0 for r in feas)
    fig.update_layout(
        barmode="stack", height=480, margin=dict(l=10, r=10, t=40, b=10),
        title=dict(text=f"Plan composition (bars) and objective (line) across {block['label']}", font=dict(size=14)),
        xaxis=dict(title=xlabel, type="category"),
        yaxis=dict(title="Interventions", range=[0, top * 1.9], showgrid=False),
        yaxis2=dict(title="Objective", overlaying="y", side="right", range=[min(objs) * 0.55, max(objs) * 1.12], gridcolor="#E7ECEA"),
        legend=dict(orientation="h", y=-0.22, x=0), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    rows = [{"Value": r["label"], "Status": r.get("status", ""),
             "Objective": f"{r['objective']:.2f}" if r.get("objective") is not None else "",
             "NG": r.get("grocery_new", ""), "UG": r.get("grocery_upgrade", ""), "NF": r.get("farmers_new", ""),
             "UF": r.get("farmers_upgrade", ""), "M": r.get("mobile_market", ""), "Total": r.get("total", ""),
             "Gap (%)": f"{r['gap']:.2f}" if r.get("gap") is not None else ""} for r in block["rows"]]
    a, b = st.columns([1.4, 1], gap="medium")
    with a:
        st.dataframe(pd.DataFrame(rows).astype(str), use_container_width=True, hide_index=True)
        tr = block.get("tradeoff")
        if tr:
            pairs = [(r, r.get(tr["field_a"]) if tr["field_a"] != "value" else r["value"],
                      r.get(tr["field_b"]) if tr["field_b"] != "value" else r["value"]) for r in feas]
            pairs = [q for q in pairs if q[1] is not None and q[2] is not None]
            cross_txt = ""
            if len(pairs) >= 2:
                numeric = all(isinstance(q[0]["value"], (int, float)) for q in pairs)
                xs = [q[0]["value"] for q in pairs] if numeric else list(range(len(pairs)))
                a_n = SD._norm01([q[1] for q in pairs]); b_n = SD._norm01([q[2] for q in pairs])
                cross = SD._intersection_xy(xs, a_n, b_n)
                ft = go.Figure()
                ft.add_trace(go.Scatter(x=xs, y=a_n, mode="lines+markers", name=tr["label_a"],
                                        line=dict(color=T.INK, width=3), marker=dict(size=9),
                                        customdata=[q[1] for q in pairs], hovertemplate="%{customdata:.2f}<extra></extra>"))
                ft.add_trace(go.Scatter(x=xs, y=b_n, mode="lines+markers", name=tr["label_b"],
                                        line=dict(color=T.OCHRE, width=3, dash="dot"), marker=dict(size=9, symbol="diamond"),
                                        customdata=[q[2] for q in pairs], hovertemplate="%{customdata:.2f}<extra></extra>"))
                if cross is not None:
                    xi, yi = cross
                    cs = SD._fmt_cross(xi, unit, block["label"]) if numeric else "between tested values"
                    ft.add_vline(x=xi, line=dict(color=T.TEAL, dash="dash", width=2))
                    ft.add_trace(go.Scatter(x=[xi], y=[yi], mode="markers", name="Crossing",
                                            marker=dict(size=16, color="rgba(0,0,0,0)", line=dict(color=T.TEAL, width=3)),
                                            hovertemplate=f"Crossing near {cs}<extra></extra>"))
                    cross_txt = f"<br><br><b>The two curves cross near {cs}.</b>"
                ft.update_layout(height=320, title=dict(text="Trade-off (both measures rescaled to 0 to 1)", font=dict(size=14)),
                                 yaxis=dict(range=[-0.05, 1.1]), xaxis=dict(title=xlabel),
                                 legend=dict(orientation="h", y=-0.3, x=0), margin=dict(l=10, r=10, t=40, b=10))
                if not numeric:
                    ft.update_xaxes(tickmode="array", tickvals=xs, ticktext=[q[0]["label"] for q in pairs])
                st.plotly_chart(ft, use_container_width=True, config={"displayModeBar": False})
            st.markdown(f'<div class="panel"><h4>Trade-off</h4>{tr["story"]}{cross_txt}</div>', unsafe_allow_html=True)
        elif block.get("tradeoff_note"):
            st.markdown(f'<div class="panel"><h4>Interpretation</h4>{block["tradeoff_note"]}</div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="panel"><h4>Key findings</h4><ul style="margin:0;padding-left:18px">'
                    + "".join(f"<li style='margin-bottom:6px'>{f}</li>" for f in block["findings"]) + "</ul></div>",
                    unsafe_allow_html=True)


@st.fragment
def sensitivity():
    st.markdown(
        '<div class="lead" style="grid-template-columns: minmax(0,1.3fr) minmax(0,1fr)"><div>'
        '<div class="say" style="max-width:48ch">The plan is shaped by its constraints, not by its objective weights.</div>'
        '<div class="note">Seventy-one solves of the model, each changing one assumption at a time: nine sweeps over '
        'policy levers, modeling choices, costs and weights (59 solves), and one sweep over the assumed intervention '
        'impacts (12 solves). Budgets below $40M, a 600 m walking standard and a 20 percent no-vehicle cutoff '
        'produced no feasible plan within the time limit.</div></div>'
        '<div class="facts">'
        '<div class="fact"><div class="v">110%</div><div class="k">objective swing across walking standards of 750 to 1,200 m</div></div>'
        '<div class="fact"><div class="v">96%</div><div class="k">objective gain from $40M to $70M</div></div>'
        '<div class="fact"><div class="v">±2</div><div class="k">largest change in any type across all outcome weights</div></div>'
        '<div class="fact"><div class="v">83.7%</div><div class="k">lowest share of baseline selections kept when impacts change</div></div>'
        '</div></div>', unsafe_allow_html=True)
    sens_overview()
    st.markdown("### Inspect one assumption")
    with st.form("sens_form", border=False):
        c1, c2 = st.columns([3, 1])
        choice = c1.selectbox("Assumption", SD.SENS_ADV_ORDER + [IMPACT_KEY], index=0, label_visibility="collapsed")
        c2.form_submit_button("Apply changes")
    if choice == IMPACT_KEY:
        sens_impact()
    else:
        sens_param(choice)


with tab_sens:
    sensitivity()


# =====================================================================
# TAB 4: ABOUT
# =====================================================================
with tab_about:
    a, b = st.columns([1.6, 1], gap="large")
    with a:
        st.markdown("### About this dashboard")
        st.markdown(
            "This dashboard accompanies a study that formulates healthy food investment in Detroit as a spatial "
            "mixed-integer linear program. The model chooses where to fund five kinds of intervention (new and upgraded "
            "grocery stores, new and upgraded farmers markets, and mobile markets) within a fixed capital budget. It "
            "maximizes need-weighted gains in food access and reductions in unhealthy food exposure, and it requires "
            "walking access to a fixed-site facility at every demand point in ZIP codes where many households lack a "
            "vehicle.")
        st.markdown("#### How to use it")
        st.markdown(
            "- **Food access explorer.** Map the existing food environment, shade ZIP codes by need or health "
            "indicators, and focus on one ZIP code to see its profile.\n"
            "- **Optimization model.** Set the budget, the coverage target, the equity rule, the weights, the costs "
            "and the assumed impacts, then run the model. The budget slider starts at $38M and never goes "
            "below the smallest budget with a guaranteed feasible plan. Common scenarios load instantly from a precomputed library, and any "
            "setting you have already run returns instantly.\n"
            "- **Sensitivity analysis.** See how the recommended plan responds to each assumption, from 71 solves "
            "computed offline.\n"
            "- Each panel updates only when you press **Apply changes** or **Run optimization**, and only that tab "
            "is recalculated.")
        st.markdown("#### Method in brief")
        st.markdown(
            "Each ZIP code is represented by demand points on a 500-meter grid (2,706 in all). There are 419 "
            "candidate sites: 292 filtered grid locations, 64 existing grocery stores, 31 existing farmers markets "
            "and 32 ZIP centroids. Walking access uses an 833-meter standard (a 10-minute walk at 5 km/h) and mobile "
            "markets a 5,000-meter driving standard, with linear distance decay and a per-point relaxation where "
            "no walking-eligible site is within reach. The model is solved with the open-source HiGHS solver.")
        st.markdown("#### Data sources")
        st.markdown(
            "- CDC PLACES 2024 release, retrieved through the Wayne State University PHOENIX platform\n"
            "- American Community Survey 5-year estimates (population, income, poverty, vehicle access)\n"
            "- Detroit Food Map (grocery stores, farmers markets)\n"
            "- City of Detroit Open Data Portal (SNAP retailers, restaurants, food pantries, liquor licenses, ZIP codes)\n"
            "- US Census Bureau TIGER/Line ZIP code tabulation areas")
    with b:
        st.markdown("### Funding")
        st.markdown(
            '<div class="cite">This study was partially funded by the ACHIEVE GreatER grant (National Institute on '
            'Minority Health and Health Disparities, award 1P50MD017351-01) through the NIMHD/Health Equity Action '
            'Network to support research on optimizing food access and advancing cardiovascular health equity in Detroit.</div>',
            unsafe_allow_html=True)
        st.markdown("### How to cite")
        st.markdown(
            '<div class="cite">Sharifi S, Vasheghani S, Dalkiran E, Yildirim M. A spatial optimization framework for '
            'equitable healthy food access investment: application to Detroit. Manuscript under review, 2026.'
            f'<br><br>Code and data: <a href="{REPO_URL}">{REPO_URL}</a>'
            '<br>Archived release: DOI to be added.</div>', unsafe_allow_html=True)
        st.markdown("### Team")
        st.markdown(
            "Health Services Research Lab, Department of Industrial and Systems Engineering, Wayne State University. "
            "Principal investigator: Dr. Melike Yildirim.")
