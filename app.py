"""
Detroit Food Access Optimization Dashboard
Wayne State University - Health Services Research Lab

Two-tab Streamlit application:
  1. Food Access Explorer - interactive view of 7 outlet categories
  2. Optimization Model   - live MILP solver with parameter controls

This file is the application entry point for both Colab+cloudflared and
for cloud deployment (Streamlit Cloud / Hugging Face Spaces).
"""

import os
import math
import time
import pickle
import warnings
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from shapely.geometry import Point

warnings.filterwarnings("ignore")

# ============================================================
# CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Detroit Food Access Optimization",
    layout="wide",
    initial_sidebar_state="expanded",
)

DRIVE_BASE = "/content/drive/MyDrive/Food Access Optimization Model"
LOCAL_BASE = str(Path(__file__).parent if "__file__" in globals() else ".")
DATA_DIR = DRIVE_BASE if os.path.exists(DRIVE_BASE) else LOCAL_BASE
OUT_DIR = os.path.join(DATA_DIR, "outputs")
SENS_DIR = os.path.join(OUT_DIR, "sensitivity")
PHASE1_PKL = os.path.join(SENS_DIR, "phase1_baseline.pkl")
BASELINE_XLSX = os.path.join(OUT_DIR, "baseline_results.xlsx")

# ------------------------------------------------------------
# Large data file (phase1_baseline.pkl, ~26 MB) is hosted on Google Drive
# because it exceeds GitHub's 25 MB browser-upload limit. On first run the
# app downloads it into outputs/sensitivity/ if it is not already present.
# ------------------------------------------------------------
PHASE1_DRIVE_ID = "1-4we2kyh-Jr1gJSCDrty2tHLbQnKbizX"

def _ensure_phase1_file():
    """Download phase1_baseline.pkl from Google Drive if it is missing."""
    if os.path.exists(PHASE1_PKL):
        return
    try:
        os.makedirs(os.path.dirname(PHASE1_PKL), exist_ok=True)
        import gdown
        gdown.download(id=PHASE1_DRIVE_ID, output=PHASE1_PKL, quiet=False)
    except Exception as e:
        print(f"[phase1] download failed: {e}")

# ============================================================
# COLOR PALETTE - Professional, conference-grade
# ============================================================
COLORS_STORE = {
    "Restaurant": "#C0392B",
    "Grocery Store": "#27AE60",
    "Farmers Market": "#16A085",
    "Food Pantry": "#2980B9",
    "Gas Station": "#D68910",
    "Liquor Store": "#7D6608",
    "SNAP Retailer": "#6C3483",
}
COLORS_OPT = {
    "grocery_new": "#0E6BA8",
    "grocery_upgrade": "#1E8449",
    "farmers_new": "#D68910",
    "farmers_upgrade": "#935116",
    "mobile_market": "#6C3483",
}
NAMES_OPT = {
    "grocery_new": "New Grocery Store",
    "grocery_upgrade": "Grocery Upgrade",
    "farmers_new": "New Farmers Market",
    "farmers_upgrade": "Farmers Market Upgrade",
    "mobile_market": "Mobile Market",
}

# ============================================================
# GLOBAL CSS - Professional styling
# ============================================================
st.markdown("""
<style>
/* Base typography */
html, body, [class*="css"] {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}

/* Title */
.dashboard-title {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: #1A2B47;
    letter-spacing: -0.5px;
    margin-top: 0;
    margin-bottom: 4px;
    padding-top: 0;
}
.dashboard-subtitle {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 14px;
    color: #4B5563;
    margin-bottom: 16px;
    font-weight: 400;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 2px solid #E5E7EB;
}
.stTabs [data-baseweb="tab"] {
    height: 40px;
    padding: 0 24px;
    background: transparent;
    border-radius: 4px 4px 0 0;
    font-size: 14px;
    font-weight: 600;
    color: #4B5563;
}
.stTabs [aria-selected="true"] {
    background: #1A2B47;
    color: #FFFFFF;
}

/* Buttons */
.stButton button {
    font-weight: 600;
    border-radius: 4px;
    font-size: 14px;
}
.stButton button[kind="primary"] {
    background-color: #1A2B47;
    color: #FFFFFF;
}
.stButton button[kind="primary"]:hover {
    background-color: #2C3E5D;
}

/* Tooltips - rewrite to remove italics, fix spacing */
.stTooltipContent, [data-testid="stTooltipContent"] {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif !important;
    font-size: 13px !important;
    line-height: 1.55 !important;
    font-style: normal !important;
    padding: 12px 14px !important;
    max-width: 380px !important;
    background-color: #1F2937 !important;
    color: #F9FAFB !important;
}

/* Tooltip text */
[role="tooltip"] {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif !important;
    font-size: 13px !important;
    line-height: 1.55 !important;
    font-style: normal !important;
}

/* Metric cards */
[data-testid="stMetricLabel"] {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #4B5563 !important;
}
[data-testid="stMetricValue"] {
    font-size: 26px !important;
    font-weight: 700 !important;
    color: #1A2B47 !important;
}

/* Section headers */
h3 {
    color: #1A2B47;
    font-weight: 600;
    margin-top: 1.2rem;
    margin-bottom: 0.5rem;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #F9FAFB;
}
[data-testid="stSidebar"] h3 {
    color: #1A2B47;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #D1D5DB;
    padding-bottom: 6px;
}

/* Info banner */
.banner-info {
    background: #EFF6FF;
    border-left: 3px solid #2563EB;
    padding: 10px 14px;
    border-radius: 4px;
    color: #1E3A8A;
    font-size: 13px;
}
.banner-success {
    background: #F0FDF4;
    border-left: 3px solid #16A34A;
    padding: 10px 14px;
    border-radius: 4px;
    color: #14532D;
    font-size: 13px;
}
.banner-warn {
    background: #FFFBEB;
    border-left: 3px solid #F59E0B;
    padding: 10px 14px;
    border-radius: 4px;
    color: #78350F;
    font-size: 13px;
}

/* Folium legend positioning fix */
.leaflet-control-layers {
    margin-right: 12px !important;
    margin-top: 12px !important;
    max-height: 75vh !important;
    overflow-y: auto !important;
}

/* Vertical padding - leave enough room for header above title */
.block-container {
    padding-top: 3rem !important;
    padding-bottom: 1rem !important;
}

/* Hide Streamlit's default running banner that can overlap content */
[data-testid="stStatusWidget"] {
    display: none;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# CACHED DATA LOADERS
# ============================================================
@st.cache_data(show_spinner=False)
def load_zip_polygons():
    """Load ZIP polygons in lat/lon for folium."""
    shp = os.path.join(DATA_DIR, "zip_codes.shp")
    gdf = gpd.read_file(shp)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=3857)
    gdf = gdf.to_crs(epsg=4326)
    zip_col = next((c for c in ["zipcode", "ZIP", "Zipcode", "ZCTA5CE10", "zip"] if c in gdf.columns), None)
    gdf["ZIP"] = gdf[zip_col].astype(str).str.zfill(5)
    return gdf

@st.cache_data(show_spinner=False)
def load_need_weights():
    """Per-ZIP need weights and demographics."""
    try:
        df = pd.read_excel(os.path.join(DATA_DIR, "final_detroit_food_health_dataset.xlsx"), sheet_name="data_set")
        nd = pd.read_excel(os.path.join(DATA_DIR, "need_index_by_zip.xlsx"), sheet_name="need_index")
        df["ZIP"] = df["ZIP"].astype(int).astype(str)
        nd["ZIP"] = nd["ZIP"].astype(int).astype(str)
        out = df.merge(nd[["ZIP", "NeedIndex_0_100"]], on="ZIP", how="left")
        return out[["ZIP", "Population", "MedianIncome", "NoVehicleRate", "NeedIndex_0_100"]].copy()
    except Exception:
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def load_outlets():
    """All 7 outlet types for the Explorer tab."""
    specs = {
        "Grocery Store":   ("Grocery Store_Zip Code.xlsx", "dfm-stores-master-dfm_grocery_2", "Latitude", "Longitude"),
        "Farmers Market":  ("Farmers Market_ZIP Code.xlsx", 0, "Latitude", "Longitude"),
        "Food Pantry":     ("Food Pantries__Zip Code.xlsx", "Food_Pantries_in_Michigan_2016.", "Y", "X"),
        "SNAP Retailer":   ("SNAP_Zip Code.xlsx", "SNAP Retailer Locations", "Latitude", "Longitude"),
        "Gas Station":     ("Gas Station_Zip Code.xlsx", "Gas Station", "Latitude", "Longitude"),
        "Liquor Store":    ("Liqour_Zip Cod.xlsx", "Liqoure", "Latitude", "Longitude"),
        "Restaurant":      ("Restaurant _Zip Code..xlsx", "Restaurant", "lat", "lon"),
    }
    rows = []
    for name, (fn, sheet, lat_col, lon_col) in specs.items():
        try:
            df = pd.read_excel(os.path.join(DATA_DIR, fn), sheet_name=sheet)
            if name == "Restaurant" and "status" in df.columns:
                df = df[df["status"].astype(str).str.strip().str.lower() != "permanently closed"]
            df = df.dropna(subset=[lat_col, lon_col]).copy()
            df["lat"] = pd.to_numeric(df[lat_col], errors="coerce")
            df["lon"] = pd.to_numeric(df[lon_col], errors="coerce")
            df = df.dropna(subset=["lat", "lon"])
            df = df[df["lat"].between(42.25, 42.46) & df["lon"].between(-83.30, -82.90)]
            df["store_type"] = name
            name_col = next((c for c in ["Store Name","Name","NAME","name","RETAILER","store_name"] if c in df.columns), None)
            df["store_name"] = df[name_col].astype(str) if name_col else name
            addr_col = next((c for c in ["Address","ADDRESS","address","street","Street"] if c in df.columns), None)
            df["address"] = df[addr_col].astype(str) if addr_col else ""
            rows.append(df[["store_type","store_name","address","lat","lon"]])
        except Exception:
            pass
    if rows:
        return pd.concat(rows, ignore_index=True)
    return pd.DataFrame(columns=["store_type","store_name","address","lat","lon"])

@st.cache_resource(show_spinner=False)
def load_phase1():
    """Load Phase 1 optimization data once and pin in memory."""
    _ensure_phase1_file()
    if not os.path.exists(PHASE1_PKL):
        return None
    with open(PHASE1_PKL, "rb") as f:
        return pickle.load(f)

@st.cache_data(show_spinner=False)
def load_baseline_solution():
    """Baseline selected facilities for warm-start and initial display."""
    if not os.path.exists(BASELINE_XLSX):
        return None
    try:
        return pd.read_excel(BASELINE_XLSX, sheet_name="selected_facilities")
    except Exception:
        return None

# ============================================================
# UTILITY
# ============================================================
R_EARTH = 6378137.0
def merc_to_latlon(x, y):
    lon = math.degrees(x / R_EARTH)
    lat = math.degrees(2 * math.atan(math.exp(y / R_EARTH)) - math.pi/2)
    return lat, lon

# ============================================================
# MILP SOLVER - WITH PROPER TIME-LIMIT HANDLING
# ============================================================
def solve_optimization(phase1, params, time_limit, mip_gap, warm_start_df=None):
    """Solve the MILP. Returns (result_dict_or_None, termination_str, elapsed_seconds)."""
    import pyomo.environ as pyo

    t0 = time.time()

    # Unpack Phase 1
    I_subpoints = phase1["I_subpoints"]
    J = phase1["J"]
    K = phase1["K"]; K_walk = phase1["K_walk"]
    J_k = phase1["J_k"]
    A_eff = phase1["A_eff"]
    Pop_i = phase1["Pop_i"]; w_i = phase1["w_i"]
    delta_FA = phase1["delta_FA"]; delta_U = phase1["delta_U"]; delta_HB = phase1["delta_HB"]
    A_ceil = phase1["A_ceil"]; R_ceil = phase1["R_ceil"]; Q_ceil = phase1["Q_ceil"]
    Cap_jk = phase1["Cap_jk"]
    Inc = phase1["Inc"]; Inc_median = phase1["Inc_median"]
    C_base_default = phase1["C_base"]
    NoVeh = phase1["NoVeh"]
    demand_points = phase1["demand_points"]

    # User parameters
    BUDGET = params["budget"]
    THETA = params["theta"]
    OMEGA_A = params["omega_A"]; OMEGA_R = params["omega_R"]; OMEGA_Q = params["omega_Q"]
    LAMBDA = params["lambda"]
    GAMMA = params["gamma"]
    NV_THR = params["nv_threshold"]
    APPLY_WALKING = params.get("apply_walking", True)
    C_base = {**C_base_default, **params.get("cost_overrides", {})}

    # Recompute I_walk
    I_walk = sorted([dp["i"] for dp in demand_points if NoVeh[dp["zip"]] > NV_THR])

    # Recompute C_jk
    C_jk = {}
    for site in J:
        for k in K:
            if site["j"] in J_k[k]:
                z = site["zip"]; inc = Inc.get(z, Inc_median)
                factor = 1.0 + GAMMA * (inc - Inc_median) / Inc_median
                C_jk[(site["j"], k)] = C_base[k] * factor

    # Build lookups
    A_by_i = {i: [] for i in I_subpoints}
    A_by_jk = {(j, k): [] for k in K for j in J_k[k]}
    A_walk_by_i = {i: [] for i in I_subpoints}
    for (i, j, k) in A_eff:
        A_by_i[i].append((j, k))
        A_by_jk[(j, k)].append(i)
        if k in K_walk:
            A_walk_by_i[i].append((j, k))

    I_walk_eff = [i for i in I_walk if A_walk_by_i[i]]

    # Model
    m = pyo.ConcreteModel()
    m.I = pyo.Set(initialize=I_subpoints)
    m.JK = pyo.Set(initialize=[(j, k) for k in K for j in J_k[k]], dimen=2)
    m.A = pyo.Set(initialize=list(A_eff), dimen=3)
    m.x = pyo.Var(m.JK, within=pyo.Binary)
    m.z = pyo.Var(m.A, within=pyo.NonNegativeReals, bounds=(0, 1))
    m.A_i = pyo.Var(m.I, within=pyo.NonNegativeReals)
    m.R_i = pyo.Var(m.I, within=pyo.NonNegativeReals)
    m.Q_i = pyo.Var(m.I, within=pyo.NonNegativeReals)

    # Warm-start
    if warm_start_df is not None and len(warm_start_df) > 0 and "site_id" in warm_start_df.columns:
        ws = set(zip(warm_start_df["site_id"].astype(int), warm_start_df["intervention_type"].astype(str)))
        for (j, k) in m.JK:
            m.x[(j, k)].value = 1.0 if (j, k) in ws else 0.0

    def obj_rule(mo):
        b = sum(w_i[i] * (OMEGA_A*mo.A_i[i]/A_ceil + OMEGA_R*mo.R_i[i]/R_ceil + OMEGA_Q*mo.Q_i[i]/Q_ceil) for i in I_subpoints)
        if LAMBDA > 0:
            cp = LAMBDA * sum(C_jk[(j,k)]/BUDGET * mo.x[(j,k)] for (j,k) in mo.JK)
            return b - cp
        return b
    m.obj = pyo.Objective(rule=obj_rule, sense=pyo.maximize)

    def c1(mo, i):
        t = A_by_i[i]
        if not t: return pyo.Constraint.Skip
        return sum(mo.z[(i,j,k)] for (j,k) in t) >= THETA
    m.C1 = pyo.Constraint(m.I, rule=c1)

    if APPLY_WALKING and len(I_walk_eff) > 0:
        m.I_walk_eff = pyo.Set(initialize=I_walk_eff)
        def c2(mo, i):
            t = A_walk_by_i[i]
            if not t: return pyo.Constraint.Skip
            return sum(mo.z[(i,j,k)] for (j,k) in t) >= THETA
        m.C2 = pyo.Constraint(m.I_walk_eff, rule=c2)

    def c3(mo, i, j, k): return mo.z[(i,j,k)] <= mo.x[(j,k)]
    m.C3 = pyo.Constraint(m.A, rule=c3)

    sites_to_jks = {}
    for (j, k) in m.JK: sites_to_jks.setdefault(j, []).append(k)
    def c4(mo, j): return sum(mo.x[(j,k)] for k in sites_to_jks[j]) <= 1
    m.C4 = pyo.Constraint(list(sites_to_jks.keys()), rule=c4)

    def c7(mo, j, k):
        if not A_by_jk.get((j,k)): return pyo.Constraint.Skip
        return sum(Pop_i[i]*mo.z[(i,j,k)] for i in A_by_jk[(j,k)]) <= Cap_jk[(j,k)] * mo.x[(j,k)]
    m.C7 = pyo.Constraint(m.JK, rule=c7)
    m.C8 = pyo.Constraint(expr=sum(C_jk[(j,k)]*m.x[(j,k)] for (j,k) in m.JK) <= BUDGET)

    def c9a(mo, i):
        t = A_by_i[i]
        if not t: return mo.A_i[i] <= 0
        return mo.A_i[i] <= sum(delta_FA[(i,j,k)]*mo.z[(i,j,k)] for (j,k) in t)
    def c9b(mo, i): return mo.A_i[i] <= A_ceil
    m.C9a = pyo.Constraint(m.I, rule=c9a); m.C9b = pyo.Constraint(m.I, rule=c9b)

    def c10a(mo, i):
        t = A_by_i[i]
        if not t: return mo.R_i[i] <= 0
        return mo.R_i[i] <= sum(delta_U[(i,j,k)]*mo.z[(i,j,k)] for (j,k) in t)
    def c10b(mo, i): return mo.R_i[i] <= R_ceil
    m.C10a = pyo.Constraint(m.I, rule=c10a); m.C10b = pyo.Constraint(m.I, rule=c10b)

    def c11a(mo, i):
        t = A_by_i[i]
        if not t: return mo.Q_i[i] <= 0
        return mo.Q_i[i] <= sum(delta_HB[(i,j,k)]*mo.z[(i,j,k)] for (j,k) in t)
    def c11b(mo, i): return mo.Q_i[i] <= Q_ceil
    m.C11a = pyo.Constraint(m.I, rule=c11a); m.C11b = pyo.Constraint(m.I, rule=c11b)

    # --------------------------------------------------------
    # SOLVER SETUP
    # The only option-setting path HiGHS itself respects is .highs_options
    # (a dict that gets passed directly to the HiGHS engine). Pyomo's .config
    # and .options on LegacySolver do NOT necessarily propagate to HiGHS.
    # --------------------------------------------------------
    solver = None
    solver_name = None
    # Prefer legacy 'highs' solver. The 'appsi_highs' wrapper has a known
    # hang bug after HiGHS finishes inside Streamlit subprocesses.
    for name in ["highs", "appsi_highs"]:
        try:
            s = pyo.SolverFactory(name)
            if s.available(exception_flag=False):
                solver = s
                solver_name = name
                break
        except Exception:
            continue
    if solver is None:
        return None, "no-solver-available", time.time() - t0

    # Set HiGHS options - the dict that gets passed directly to the engine
    try:
        solver.highs_options = {
            "time_limit": float(time_limit),
            "mip_rel_gap": float(mip_gap),
            "presolve": "on",
        }
        print(f"[solver] highs_options set: time_limit={time_limit}s, mip_rel_gap={mip_gap}")
    except Exception as e:
        print(f"[solver] WARNING: could not set highs_options: {e}")

    # Belt-and-suspenders for older API versions
    try:
        solver.config.time_limit = float(time_limit)
        solver.config.mip_gap = float(mip_gap)
    except Exception:
        pass
    try:
        solver.options["time_limit"] = float(time_limit)
        solver.options["mip_rel_gap"] = float(mip_gap)
    except Exception:
        pass

    # Solve - clean simple version
    t_solve = time.time()
    res = solver.solve(m, tee=False, load_solutions=False)
    elapsed = time.time() - t_solve
    tc = str(res.solver.termination_condition).lower()
    print(f"[solver] returned {elapsed:.1f}s tc={tc}")

    # Get upper bound for gap calculation
    upper_bound = None
    try:
        upper_bound = float(res.problem.upper_bound)
    except Exception:
        pass

    # Load solution - the allow_consistent flag handles maxTimeLimit/aborted results
    try:
        m.solutions.load_from(res, allow_consistent_values_for_fixed_vars=True)
    except Exception as e:
        print(f"[solver] load failed: {e}")
        return None, f"load-failed ({tc})", elapsed

    # Extract selected facilities
    selected = []
    for (j, k) in m.JK:
        if pyo.value(m.x[(j, k)]) > 0.5:
            site = J[j]
            lat, lon = merc_to_latlon(site["x"], site["y"])
            selected.append({
                "site_id": j, "intervention_type": k,
                "site_type": site["site_type"], "site_zip": site["zip"],
                "x_merc": site["x"], "y_merc": site["y"],
                "latitude": lat, "longitude": lon,
                "cost": C_jk[(j, k)], "capacity": Cap_jk[(j, k)],
            })

    type_counts = {}
    for s in selected:
        type_counts[s["intervention_type"]] = type_counts.get(s["intervention_type"], 0) + 1
    total_cost = sum(s["cost"] for s in selected)

    obj_value = float(pyo.value(m.obj))
    achieved_gap = None
    if upper_bound is not None and abs(obj_value) > 1e-9:
        achieved_gap = abs(upper_bound - obj_value) / abs(obj_value)
    hit_time_limit = "maxtimelimit" in tc or "timelimit" in tc

    result = {
        "selected": pd.DataFrame(selected),
        "objective": obj_value,
        "n_facilities": len(selected),
        "total_cost": total_cost,
        "budget_used_pct": 100 * total_cost / BUDGET,
        "type_counts": type_counts,
        "termination": tc,
        "I_walk_size": len(I_walk),
        "I_walk_eff_size": len(I_walk_eff),
        "elapsed": time.time() - t0,
        "solver_used": solver_name,
        "params_snapshot": dict(params),
        "achieved_gap": achieved_gap,
        "upper_bound": upper_bound,
        "hit_time_limit": hit_time_limit,
    }
    return result, tc, time.time() - t0

# ============================================================
# MAP RENDERING
# ============================================================
def render_explorer_map(filtered_df, zip_gdf, show_boundaries=True,
                       need_df=None, show_need_shading=False, cluster=True):
    m = folium.Map(location=[42.36, -83.10], zoom_start=11, tiles="cartodbpositron", prefer_canvas=True)
    if show_need_shading and need_df is not None and len(need_df) > 0:
        gdf_need = zip_gdf.merge(need_df[["ZIP","NeedIndex_0_100"]], on="ZIP", how="left")
        folium.Choropleth(
            geo_data=gdf_need.__geo_interface__,
            data=gdf_need, columns=["ZIP","NeedIndex_0_100"],
            key_on="feature.properties.ZIP",
            fill_color="YlOrBr", fill_opacity=0.55, line_opacity=0.0,
            nan_fill_opacity=0.0, legend_name="Need Index (0-100)"
        ).add_to(m)
    if show_boundaries:
        folium.GeoJson(
            zip_gdf.__geo_interface__,
            style_function=lambda x: {"fillColor":"none","color":"#4B5563","weight":1.0,"fillOpacity":0},
            tooltip=folium.GeoJsonTooltip(fields=["ZIP"], aliases=["ZIP:"]),
        ).add_to(m)
    if cluster:
        from folium.plugins import MarkerCluster
        for st_name, color in COLORS_STORE.items():
            sub = filtered_df[filtered_df["store_type"] == st_name]
            if len(sub) == 0: continue
            mc = MarkerCluster(name=st_name).add_to(m)
            for _, r in sub.iterrows():
                folium.CircleMarker(
                    location=[r["lat"], r["lon"]],
                    radius=4, color=color, fill=True, fillColor=color, fillOpacity=0.85, weight=1,
                    popup=folium.Popup(
                        f"<b>{r['store_name']}</b><br>{r['store_type']}<br>{r.get('address','')}",
                        max_width=300),
                ).add_to(mc)
    else:
        for _, r in filtered_df.iterrows():
            color = COLORS_STORE.get(r["store_type"], "#666666")
            folium.CircleMarker(
                location=[r["lat"], r["lon"]],
                radius=3, color=color, fill=True, fillColor=color, fillOpacity=0.85, weight=0.5,
                popup=folium.Popup(
                    f"<b>{r['store_name']}</b><br>{r['store_type']}<br>{r.get('address','')}",
                    max_width=300),
            ).add_to(m)
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m

def render_optimization_map(selected_df, zip_gdf, phase1, nv_threshold, show_need_shading=True):
    """Faster version using MarkerCluster + lighter popups. The cluster
    expands/collapses smoothly as the user zooms — the same animation as Tab 1.
    Selected facilities pulse via CSS to draw attention."""
    from folium.plugins import MarkerCluster

    m = folium.Map(location=[42.36, -83.10], zoom_start=11, tiles="cartodbpositron", prefer_canvas=True)

    NoVeh = phase1["NoVeh"]
    walk_relaxed = phase1.get("walk_relaxed_subs", [])

    # Inject pulsing animation CSS into the map iframe
    pulse_css = """
    <style>
    @keyframes mappulse {
        0%   { transform: scale(1);   opacity: 0.95; }
        50%  { transform: scale(1.18); opacity: 0.65; }
        100% { transform: scale(1);   opacity: 0.95; }
    }
    .leaflet-marker-icon.pulse-marker {
        animation: mappulse 1.8s ease-in-out infinite;
        transform-origin: center center;
    }
    </style>
    """
    m.get_root().html.add_child(folium.Element(pulse_css))

    zip_gdf2 = zip_gdf.copy()
    zip_gdf2["NoVehicleRate"] = zip_gdf2["ZIP"].map(NoVeh)
    zip_gdf2["is_walking_required"] = zip_gdf2["NoVehicleRate"].fillna(0) > nv_threshold
    relaxed_zips = set()
    if len(walk_relaxed) > 0:
        relaxed_zips = set(pd.DataFrame(walk_relaxed)["zip"].astype(str).str.zfill(5))
    zip_gdf2["has_relaxed_subpoint"] = zip_gdf2["ZIP"].isin(relaxed_zips)

    if show_need_shading:
        need_df = load_need_weights()
        if len(need_df) > 0:
            gdf_need = zip_gdf2.merge(need_df[["ZIP","NeedIndex_0_100"]], on="ZIP", how="left")
            folium.Choropleth(
                geo_data=gdf_need.__geo_interface__,
                data=gdf_need, columns=["ZIP","NeedIndex_0_100"],
                key_on="feature.properties.ZIP",
                fill_color="YlOrBr", fill_opacity=0.55, line_opacity=0.0,
                legend_name="Need Index (0-100)"
            ).add_to(m)

    folium.GeoJson(
        zip_gdf2.__geo_interface__,
        style_function=lambda x: {"fillColor":"none","color":"#666666","weight":0.8,"fillOpacity":0},
        tooltip=folium.GeoJsonTooltip(
            fields=["ZIP","NoVehicleRate"],
            aliases=["ZIP:", "No-Vehicle Rate:"], localize=True,
        ),
    ).add_to(m)

    walking_zips = zip_gdf2[zip_gdf2["is_walking_required"]]
    if len(walking_zips) > 0:
        folium.GeoJson(
            walking_zips.__geo_interface__,
            style_function=lambda x: {"fillColor":"none","color":"#2563EB","weight":2.5,"fillOpacity":0},
        ).add_to(m)
    relaxed_zips_gdf = zip_gdf2[zip_gdf2["has_relaxed_subpoint"]]
    if len(relaxed_zips_gdf) > 0:
        folium.GeoJson(
            relaxed_zips_gdf.__geo_interface__,
            style_function=lambda x: {"fillColor":"none","color":"#111827","weight":1.6,"fillOpacity":0,"dashArray":"5,5"},
        ).add_to(m)

    # ONE MarkerCluster per intervention type. As the user zooms, clusters
    # expand smoothly (this is the "dynamic" animation behavior of Tab 1).
    if selected_df is not None and len(selected_df) > 0:
        for k, color in COLORS_OPT.items():
            sub = selected_df[selected_df["intervention_type"] == k]
            if len(sub) == 0:
                continue
            cluster = MarkerCluster(name=NAMES_OPT[k], show=True).add_to(m)
            # Lightweight DivIcon: pulsing colored dot
            for _, r in sub.iterrows():
                html = (
                    f'<div class="pulse-marker" style="width:14px;height:14px;'
                    f'background:{color};border:2px solid #fff;border-radius:50%;'
                    f'box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>'
                )
                icon = folium.DivIcon(html=html, icon_size=(14, 14), icon_anchor=(7, 7))
                popup_text = (
                    f"<b>{NAMES_OPT[k]}</b><br>"
                    f"ZIP: {r['site_zip']}<br>"
                    f"Cost: ${r['cost']:,.0f}<br>"
                    f"Capacity: {int(r['capacity']):,}"
                )
                folium.Marker(
                    location=[r["latitude"], r["longitude"]],
                    icon=icon,
                    popup=folium.Popup(popup_text, max_width=260),
                ).add_to(cluster)

    # Existing-but-not-selected facilities: cluster them together (faster than
    # 150+ individual CircleMarkers, AND not visually distracting).
    J = phase1["J"]
    if selected_df is not None and len(selected_df) > 0:
        sel_groc_ids = set(selected_df[selected_df["intervention_type"]=="grocery_upgrade"]["site_id"].astype(int).tolist())
        sel_farm_ids = set(selected_df[selected_df["intervention_type"]=="farmers_upgrade"]["site_id"].astype(int).tolist())
    else:
        sel_groc_ids = set(); sel_farm_ids = set()

    not_upgraded_cluster = MarkerCluster(name="Existing facilities (not upgraded)", show=False).add_to(m)
    for s in J:
        if s["site_type"] == "existing_grocery" and s["j"] not in sel_groc_ids:
            lat, lon = merc_to_latlon(s["x"], s["y"])
            html = '<div style="width:8px;height:8px;border:1.5px solid #1E8449;border-radius:50%;background:transparent;"></div>'
            folium.Marker(location=[lat, lon],
                icon=folium.DivIcon(html=html, icon_size=(8, 8), icon_anchor=(4, 4)),
                popup=f"Existing Grocery (not upgraded)<br>ZIP: {s['zip']}").add_to(not_upgraded_cluster)
        elif s["site_type"] == "existing_farmers" and s["j"] not in sel_farm_ids:
            lat, lon = merc_to_latlon(s["x"], s["y"])
            html = '<div style="width:8px;height:8px;border:1.5px solid #16A085;border-radius:50%;background:transparent;"></div>'
            folium.Marker(location=[lat, lon],
                icon=folium.DivIcon(html=html, icon_size=(8, 8), icon_anchor=(4, 4)),
                popup=f"Existing Farmers Market (not upgraded)<br>ZIP: {s['zip']}").add_to(not_upgraded_cluster)

    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m

# ============================================================
# HEADER
# ============================================================
st.markdown(
    '<div class="dashboard-title">Detroit Food Access Optimization</div>'
    '<div class="dashboard-subtitle">Spatial decision support for healthy food access investment '
    'across 32 Detroit ZIP codes</div>',
    unsafe_allow_html=True
)

# ============================================================
# SESSION STATE INIT
# ============================================================
if "opt_result" not in st.session_state:
    st.session_state.opt_result = None
if "opt_run_count" not in st.session_state:
    st.session_state.opt_run_count = 0

# ============================================================
# SENSITIVITY ANALYSIS DATA  (advanced 5-type model)
# ------------------------------------------------------------
# Pre-computed results transcribed verbatim from the advanced
# "Sensitivity Analysis of the Detroit Food Access Optimization
# Model" report (9 completed sweeps, 59 MILP re-solves, 0.5% gap
# target, 1800 s time limit). Portfolio counts are the five
# advanced intervention types. No solver runs in this tab.
# ============================================================
ADV_TYPE_KEYS = ["grocery_new", "grocery_upgrade", "mobile_market",
                 "farmers_new", "farmers_upgrade"]

# Per-parameter sweeps. Each "row" that is feasible carries the full
# five-type portfolio; infeasible / no-solution rows carry objective=None.
SENS_ADV = {
    "Budget (B)": {
        "label": "Budget", "unit": "$M", "baseline": 40,
        "description": (
            "The budget B caps total expenditure on the selected portfolio. The baseline "
            "$40M is the smallest budget for which full coverage with walking equity is "
            "feasible. The sweep tests two budgets below the baseline (to confirm "
            "infeasibility) and four above (to map the diminishing-returns frontier)."
        ),
        "rows": [
            {"value": 30, "label": "$30M", "status": "Infeasible", "objective": None},
            {"value": 35, "label": "$35M", "status": "Infeasible", "objective": None},
            {"value": 40, "label": "$40M", "status": "Optimal", "objective": 187.96, "gap": 0.50,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 45, "label": "$45M", "status": "Optimal", "objective": 233.07, "gap": 0.08, "marginal": 9.02,
             "grocery_new": 4, "grocery_upgrade": 21, "mobile_market": 110, "farmers_new": 153, "farmers_upgrade": 25, "total": 313},
            {"value": 50, "label": "$50M", "status": "Optimal", "objective": 269.82, "gap": 0.19, "marginal": 7.35,
             "grocery_new": 4, "grocery_upgrade": 23, "mobile_market": 143, "farmers_new": 134, "farmers_upgrade": 26, "total": 330},
            {"value": 60, "label": "$60M", "status": "Optimal", "objective": 326.60, "gap": 0.27, "marginal": 5.68,
             "grocery_new": 4, "grocery_upgrade": 32, "mobile_market": 197, "farmers_new": 108, "farmers_upgrade": 26, "total": 367},
            {"value": 70, "label": "$70M", "status": "Optimal", "objective": 368.71, "gap": 0.23, "marginal": 4.21,
             "grocery_new": 4, "grocery_upgrade": 58, "mobile_market": 232, "farmers_new": 87, "farmers_upgrade": 30, "total": 411},
        ],
        "tradeoff": {
            "kind": "benefit_efficiency",
            "label_a": "Objective (benefit)",
            "label_b": "Marginal objective per $1M (efficiency)",
            "field_a": "objective", "field_b": "marginal",
            "story": ("As the budget rises the objective grows (benefit up) but the marginal "
                      "return per additional million dollars falls from $9.02 of objective at "
                      "$40M-$45M to $4.21 at $60M-$70M (efficiency down). The crossing marks the "
                      "natural diminishing-returns region."),
        },
        "findings": [
            "$40M is the structural minimum budget for full coverage with walking equity: the problem is provably infeasible at $30M and $35M.",
            "Above the baseline the objective grows monotonically (187.96 to 368.71, +96%), while budget utilization stays above 99.7% at every feasible level, so the budget constraint binds tightly throughout.",
            "Marginal benefit per additional $1M declines from +9.02 objective units ($40M-$45M) to +4.21 ($60M-$70M): each extra dollar at $40M is worth more than twice each extra dollar at $70M.",
            "Composition shifts substantially with budget: mobile markets nearly triple (80 to 232), new farmers markets nearly halve (165 to 87), grocery upgrades triple (19 to 58), while new grocery stores stay at 4. Policy guidance must specify a budget context.",
        ],
    },

    "Walking threshold (d_walk)": {
        "label": "d_walk", "unit": "m", "baseline": 833,
        "description": (
            "The default maximum walking distance from a sub-point to a walking-eligible "
            "facility, before per-sub-point relaxation. Baseline 833 m (a 10-minute walk at "
            "5 km/h). The sweep spans a 7-minute walk (600 m) to a 14-minute walk (1200 m)."
        ),
        "rows": [
            {"value": 600, "label": "600 m", "status": "Infeasible", "objective": None, "aeff": 87903, "relaxed": 1305},
            {"value": 750, "label": "750 m", "status": "Time limit", "objective": 156.77, "gap": 1.09, "aeff": 88840, "relaxed": 922,
             "grocery_new": 4, "grocery_upgrade": 22, "mobile_market": 77, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 833, "label": "833 m", "status": "Optimal", "objective": 187.96, "gap": 0.50, "aeff": 89626, "relaxed": 763,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 1000, "label": "1000 m", "status": "Time limit", "objective": 245.23, "gap": 0.58, "aeff": 91751, "relaxed": 480,
             "grocery_new": 4, "grocery_upgrade": 20, "mobile_market": 73, "farmers_new": 178, "farmers_upgrade": 27, "total": 302},
            {"value": 1200, "label": "1200 m", "status": "Optimal", "objective": 329.35, "gap": 0.15, "aeff": 94716, "relaxed": 279,
             "grocery_new": 4, "grocery_upgrade": 35, "mobile_market": 46, "farmers_new": 209, "farmers_upgrade": 24, "total": 318},
        ],
        "tradeoff": {
            "label_a": "Objective (benefit)", "label_b": "Mobile markets (driving-coverage reliance)",
            "field_a": "objective", "field_b": "mobile_market",
            "story": ("As the walking radius grows the achievable objective rises (benefit up) while the "
                      "model leans less on mobile markets for driving coverage (down): mobile markets and "
                      "walking radius are partial substitutes. The crossing marks the walking distance "
                      "where rising benefit overtakes the shrinking reliance on mobile coverage."),
        },
        "findings": [
            "This is the largest objective swing of any non-budget parameter: from 750 m to 1200 m the objective more than doubles (156.77 to 329.35, +110%).",
            "A 7-minute (600 m) walking standard is infeasible at $40M even with the largest relaxation count of any sweep value (1,305 sub-points). This is a real finding about Detroit's geography, not a modeling artifact.",
            "The 833 m / 10-minute definition is the single most consequential modeling choice in the framework and must be defended explicitly in the paper.",
            "At 1200 m the mix shifts sharply (mobile 80 to 46, new farmers 165 to 209, grocery upgrades 19 to 35): mobile markets and walking radius are partial substitutes.",
        ],
    },

    "New farmers market cost": {
        "label": "farmers_new cost", "unit": "$K", "baseline": 100,
        "description": (
            "Unit cost of a new farmers market (baseline $100K), swept low/base/high at "
            "approximately +/-20% while all other type costs are held at baseline. This is "
            "the highest-count type in the baseline portfolio (165 of 294 facilities)."
        ),
        "rows": [
            {"value": 80, "label": "$80K", "status": "Optimal", "objective": 219.35,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 91, "farmers_new": 180, "farmers_upgrade": 25, "total": 319},
            {"value": 100, "label": "$100K", "status": "Optimal", "objective": 188.02,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 120, "label": "$120K", "status": "Optimal", "objective": 147.42,
             "grocery_new": 4, "grocery_upgrade": 20, "mobile_market": 66, "farmers_new": 159, "farmers_upgrade": 26, "total": 275},
        ],
        "tradeoff_note": ("This is a high-sensitivity parameter, but it has no clean two-metric crossing: "
                          "as the unit cost rises the objective falls and the portfolio simply sparsens "
                          "(319 facilities at $80K to 275 at $120K) rather than trading one metric off "
                          "against another. The sensitivity itself is the finding - see the key findings below."),
        "findings": [
            "Objective swings from 219.35 at $80K to 147.42 at $120K (+17% / -22%) - one of the two most cost-sensitive types in the model.",
            "The portfolio sparsens as cost rises: 319 facilities at $80K versus 275 at $120K, a swing of 44 facilities driven mostly by new farmers markets and mobile markets.",
            "New farmers markets are the cheapest walking-eligible new-build option, so their unit cost directly governs how cheaply the walking-equity constraint can be satisfied.",
            "Municipalities applying the framework should calibrate this cost carefully; partnerships that lower site-preparation expenses would tilt the portfolio meaningfully.",
        ],
    },

    "Mobile market cost": {
        "label": "mobile_market cost", "unit": "$K", "baseline": 200,
        "description": (
            "Unit cost of a mobile market (baseline $200K), swept low/base/high at "
            "approximately +/-20% with all other type costs held at baseline. Mobile markets "
            "are the second-highest-count type (80 of 294 facilities)."
        ),
        "rows": [
            {"value": 160, "label": "$160K", "status": "Optimal", "objective": 230.85,
             "grocery_new": 2, "grocery_upgrade": 19, "mobile_market": 134, "farmers_new": 127, "farmers_upgrade": 24, "total": 306},
            {"value": 200, "label": "$200K", "status": "Optimal", "objective": 188.02,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 240, "label": "$240K", "status": "Optimal", "objective": 162.20,
             "grocery_new": 4, "grocery_upgrade": 23, "mobile_market": 52, "farmers_new": 192, "farmers_upgrade": 27, "total": 298},
        ],
        "tradeoff": {
            "kind": "substitution",
            "label_a": "Mobile markets", "label_b": "New farmers markets",
            "field_a": "mobile_market", "field_b": "farmers_new",
            "story": ("As mobile cost rises, mobile deployments fall (134 to 52) and new farmers "
                      "markets rise (127 to 192) in a roughly one-for-one substitution. The "
                      "crossing marks the cost at which the two types are equally attractive."),
        },
        "findings": [
            "Objective swings from 230.85 at $160K to 162.20 at $240K (+23% / -14%) - the other high-sensitivity unit cost alongside new farmers markets.",
            "Mobile markets and new farmers markets behave as near-perfect substitutes: at $160K mobile nearly doubles (80 to 134) and new farmers drop 38; at $240K mobile falls 28 and new farmers rise 27.",
            "The two dominate the portfolio because they are the most cost-effective among the types with abundant candidate-site supply (292 grid sites for new farmers; 324 grid+centroid sites for mobile).",
            "The choice between them is driven primarily by relative cost; both should be disclosed and discussed explicitly in the paper.",
        ],
    },

    "No-vehicle ZIP cutoff": {
        "label": "No-vehicle cutoff", "unit": "", "baseline": 0.25,
        "description": (
            "ZIPs whose no-vehicle household rate exceeds this cutoff are car-light, and every "
            "sub-point in them must have walking access to a walking-eligible facility. Baseline "
            "0.25. The sweep tests a stricter 0.20 and looser 0.30 and 0.35."
        ),
        "rows": [
            {"value": 0.20, "label": "> 20%", "status": "No solution", "objective": None, "iwalk": 1651},
            {"value": 0.25, "label": "> 25%", "status": "Optimal", "objective": 188.02, "gap": 0.47, "iwalk": 727,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 0.30, "label": "> 30%", "status": "Optimal", "objective": 216.48, "gap": 0.33, "iwalk": 203,
             "grocery_new": 4, "grocery_upgrade": 10, "mobile_market": 109, "farmers_new": 125, "farmers_upgrade": 26, "total": 274},
            {"value": 0.35, "label": "> 35%", "status": "Optimal", "objective": 222.18, "gap": 0.47, "iwalk": 95,
             "grocery_new": 4, "grocery_upgrade": 8, "mobile_market": 117, "farmers_new": 113, "farmers_upgrade": 26, "total": 268},
        ],
        "tradeoff": {
            "kind": "equity_price",
            "label_a": "Objective (achievable benefit)",
            "label_b": "Walking-required sub-points (equity reach)",
            "field_a": "objective", "field_b": "iwalk",
            "story": ("Loosening the cutoff raises the achievable objective (fewer sub-points must "
                      "be walk-covered) but shrinks equity reach. The crossing is where extra "
                      "achievable benefit and equity coverage balance - the price of broad equity."),
        },
        "findings": [
            "At a 20% cutoff, 1,651 of 2,706 sub-points (61%) require walking access and no feasible solution was found within 30 minutes at $40M - a strong practical signal that broad equity needs more budget or looser thresholds.",
            "Each additional ~100 sub-points designated car-light costs about 5 objective units in the feasible regime; the relationship is roughly linear.",
            "Loosening the rule produces large mix shifts: grocery upgrades fall 19 to 8 (-58%), new farmers fall 165 to 113 (-31%), mobile markets rise 80 to 117 (+46%).",
            "This is the third independent confirmation (with the weight and walking-threshold sweeps) that the walking-equity constraint C2 is the dominant binding constraint.",
        ],
    },

    "Coverage target (theta)": {
        "label": "theta", "unit": "", "baseline": 1.00,
        "description": (
            "The minimum fraction of each sub-point's demand that must be served. Baseline "
            "1.00 (full coverage) plus walking access for car-light sub-points. The sweep "
            "tests five lower values to measure the equity-versus-impact tradeoff."
        ),
        "rows": [
            {"value": 0.75, "label": "0.75", "status": "Time limit", "objective": 215.81, "gap": 1.04,
             "grocery_new": 3, "grocery_upgrade": 18, "mobile_market": 94, "farmers_new": 148, "farmers_upgrade": 25, "total": 288},
            {"value": 0.80, "label": "0.80", "status": "Time limit", "objective": 209.21, "gap": 1.87,
             "grocery_new": 3, "grocery_upgrade": 18, "mobile_market": 88, "farmers_new": 159, "farmers_upgrade": 24, "total": 292},
            {"value": 0.85, "label": "0.85", "status": "Time limit", "objective": 205.58, "gap": 1.13,
             "grocery_new": 3, "grocery_upgrade": 19, "mobile_market": 88, "farmers_new": 158, "farmers_upgrade": 24, "total": 292},
            {"value": 0.90, "label": "0.90", "status": "Optimal", "objective": 201.34, "gap": 0.36,
             "grocery_new": 3, "grocery_upgrade": 19, "mobile_market": 89, "farmers_new": 156, "farmers_upgrade": 25, "total": 292},
            {"value": 0.95, "label": "0.95", "status": "Time limit", "objective": 193.86, "gap": 0.90,
             "grocery_new": 4, "grocery_upgrade": 20, "mobile_market": 82, "farmers_new": 160, "farmers_upgrade": 26, "total": 292},
            {"value": 1.00, "label": "1.00", "status": "Optimal", "objective": 187.96, "gap": 0.50,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
        ],
        "tradeoff": {
            "label_a": "Objective (achievable benefit)", "label_b": "Coverage guarantee (theta)",
            "field_a": "objective", "field_b": "value",
            "story": ("Raising the coverage guarantee theta serves more of every sub-point (equity up) but "
                      "lowers the achievable objective (benefit down). The crossing traces the equity-"
                      "versus-impact frontier: the coverage level where the guarantee and the achievable "
                      "benefit are in balance."),
        },
        "findings": [
            "Full coverage costs roughly 4% of achievable benefit relative to 95% coverage - the quantified price of the universal-coverage equity commitment.",
            "The plan structure is stable across theta (total facilities 288 to 294), with mild substitution between mobile markets and new farmers markets as theta relaxes.",
            "theta is a policy lever, not a technical parameter, and the paper should frame it that way.",
        ],
    },

    "Objective weights (omega)": {
        "label": "weight vector", "unit": "", "baseline": "equal",
        "description": (
            "The objective combines three normalized outcomes - food access (A), unhealthy-"
            "exposure reduction (R), and cardiovascular health burden (Q) - through weights "
            "summing to one. Baseline is equal (1/3 each). The sweep tests seven vectors "
            "spanning the corners and edges of the weight simplex."
        ),
        "rows": [
            {"value": "equal", "label": "equal", "status": "Optimal", "objective": 187.96, "gap": 0.50,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": "A_focus", "label": "A_focus", "status": "Time limit", "objective": 181.95, "gap": 0.85,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 164, "farmers_upgrade": 26, "total": 293},
            {"value": "R_focus", "label": "R_focus", "status": "Time limit", "objective": 196.11, "gap": 1.77,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 81, "farmers_new": 162, "farmers_upgrade": 26, "total": 292},
            {"value": "Q_focus", "label": "Q_focus", "status": "Optimal", "objective": 183.13, "gap": 0.22,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 81, "farmers_new": 163, "farmers_upgrade": 26, "total": 293},
            {"value": "A+Q", "label": "A+Q", "status": "Time limit", "objective": 173.65, "gap": 1.05,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 82, "farmers_new": 161, "farmers_upgrade": 26, "total": 292},
            {"value": "A+R", "label": "A+R", "status": "Optimal", "objective": 194.84, "gap": 0.43,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": "R+Q", "label": "R+Q", "status": "Optimal", "objective": 195.13, "gap": 0.28,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 81, "farmers_new": 163, "farmers_upgrade": 26, "total": 293},
        ],
        "findings": [
            "The recommended portfolio is essentially weight-invariant: facility counts vary by at most +/-2 of any type across the entire weight simplex.",
            "Two structural reasons: the coverage (C1) and walking-equity (C2) constraints dominate at the locked $40M budget, and the health-burden outcome Q is defined as beta_CVD times the food-access improvement, so Q moves in lockstep with A.",
            "The objective range (173.65 to 196.11, about +/-6%) is partly a normalization artifact rather than a real policy effect.",
            "A reviewer asking how the plan would change if cardiovascular outcomes were prioritized over food access can be told, with full empirical backing, that it would not meaningfully change.",
        ],
    },

    "Driving threshold (d_drive)": {
        "label": "d_drive", "unit": "m", "baseline": 5000,
        "description": (
            "The maximum driving distance for mobile-market service. Baseline 5000 m (a "
            "10-minute drive at 30 km/h). The sweep tests +/-20% around the baseline."
        ),
        "rows": [
            {"value": 4000, "label": "4000 m", "status": "Time limit", "objective": 177.86, "gap": 1.24, "aeff": 62269,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 79, "farmers_new": 166, "farmers_upgrade": 26, "total": 294},
            {"value": 4500, "label": "4500 m", "status": "Time limit", "objective": 184.25, "gap": 0.53, "aeff": 75566,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 25, "total": 293},
            {"value": 5000, "label": "5000 m", "status": "Optimal", "objective": 187.96, "gap": 0.50, "aeff": 89626,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 5500, "label": "5500 m", "status": "Optimal", "objective": 191.78, "gap": 0.30, "aeff": 104720,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 166, "farmers_upgrade": 26, "total": 295},
            {"value": 6000, "label": "6000 m", "status": "Optimal", "objective": 195.25, "gap": 0.26, "aeff": 120901,
             "grocery_new": 3, "grocery_upgrade": 19, "mobile_market": 84, "farmers_new": 166, "farmers_upgrade": 26, "total": 298},
        ],
        "tradeoff_note": ("No meaningful trade-off: across the tested range the objective moves less than "
                          "10% and the portfolio is essentially invariant (all type counts within +/-4 "
                          "facilities). Driving access is plentiful in Detroit, so the driving radius is "
                          "not a binding scarce resource."),
        "findings": [
            "Objective ranges 177.86 to 195.25 (under 10%) across a 50% change in the parameter - a mild sensitivity, an order of magnitude smaller than the walking threshold.",
            "The portfolio is essentially invariant (all type counts within +/-4 facilities); only at 6000 m does the model drop one new grocery for four more mobile markets.",
            "The contrast with the walking threshold is informative: walking equity is structurally hard in Detroit, driving access is plentiful, so walking-eligible facilities - not mobile markets - are the binding scarce resource.",
            "Any value in [4500 m, 5500 m] produces effectively the same plan, so the 5000 m baseline is easy to defend.",
        ],
    },

    "Cost penalty (lambda)": {
        "label": "lambda", "unit": "", "baseline": 0.0,
        "description": (
            "A penalty term -lambda * sum(C_jk / B) * x_jk added to the objective to test "
            "whether the model would spend less than the full budget if encouraged to. "
            "Baseline lambda = 0 (no penalty)."
        ),
        "rows": [
            {"value": 0.0, "label": "0.0", "status": "Optimal", "objective": 188.02, "gap": 0.47, "budget_used": 99.93,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 0.5, "label": "0.5", "status": "Time limit", "objective": 186.58, "gap": 0.97, "budget_used": 99.95,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 79, "farmers_new": 167, "farmers_upgrade": 26, "total": 295},
            {"value": 1.0, "label": "1.0", "status": "Time limit", "objective": 186.84, "gap": 0.54, "budget_used": 99.90,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 2.0, "label": "2.0", "status": "Time limit", "objective": 185.14, "gap": 0.94, "budget_used": 99.95,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 79, "farmers_new": 167, "farmers_upgrade": 26, "total": 295},
            {"value": 3.0, "label": "3.0", "status": "Time limit", "objective": 183.77, "gap": 1.14, "budget_used": 99.96,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 79, "farmers_new": 167, "farmers_upgrade": 26, "total": 295},
            {"value": 5.0, "label": "5.0", "status": "Time limit", "objective": 181.97, "gap": 1.05, "budget_used": 99.86,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 79, "farmers_new": 167, "farmers_upgrade": 26, "total": 295},
        ],
        "findings": [
            "At every lambda tested the model still uses more than 99.85% of the budget: the cost penalty has essentially no effect on spending.",
            "The ~6-unit objective drop from lambda 0 to 5 is approximately equal to the penalty term itself (at lambda 5 the penalty is about 4.99 units), so it is a constant offset, not a change of plan.",
            "The penalty is ineffective because C1 (coverage) and C2 (walking equity) require a minimum ~294 facilities, and the budget is already a hard upper bound; dropping facilities to save money would violate the constraints.",
            "A useful null finding: it supports lambda = 0 in the baseline. lambda may become useful in Phase 2 uncertainty extensions as a way to encourage budget slack as a hedge.",
        ],
    },

    "Income-cost elasticity (gamma)": {
        "label": "gamma", "unit": "", "baseline": 0.3,
        "description": (
            "Controls how site costs scale with local median income: "
            "C = C_base * (1 + gamma * (Inc - Median) / Median). Baseline gamma = 0.3. "
            "The sweep tests gamma = 0 (no adjustment) up to gamma = 0.7 (strong elasticity)."
        ),
        "rows": [
            {"value": 0.0, "label": "0.0", "status": "Optimal", "objective": 190.18, "gap": 0.47,
             "grocery_new": 4, "grocery_upgrade": 20, "mobile_market": 79, "farmers_new": 166, "farmers_upgrade": 26, "total": 295},
            {"value": 0.1, "label": "0.1", "status": "Time limit", "objective": 187.58, "gap": 1.24,
             "grocery_new": 4, "grocery_upgrade": 21, "mobile_market": 79, "farmers_new": 164, "farmers_upgrade": 26, "total": 294},
            {"value": 0.3, "label": "0.3", "status": "Optimal", "objective": 188.02, "gap": 0.47,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 165, "farmers_upgrade": 26, "total": 294},
            {"value": 0.5, "label": "0.5", "status": "Time limit", "objective": 187.53, "gap": 0.60,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 166, "farmers_upgrade": 26, "total": 295},
            {"value": 0.7, "label": "0.7", "status": "Optimal", "objective": 187.86, "gap": 0.50,
             "grocery_new": 4, "grocery_upgrade": 19, "mobile_market": 80, "farmers_new": 167, "farmers_upgrade": 26, "total": 296},
        ],
        "findings": [
            "Objective varies only 187.5 to 190.2 across the full gamma range - a 1.4% swing, the smallest sensitivity of any parameter tested.",
            "Maximum variation across the grid is +/-2 facilities of any type; gamma is the most robust parameter in the entire model.",
            "Detroit ZIP incomes cluster near the citywide median ($36,932), so even at gamma = 0.7 the cost multiplier rarely exceeds +/-25%, and the tightly binding budget means the optimizer just fits the cheapest feasible configuration.",
            "Income-based cost adjustment is a refinement, not a load-bearing assumption; it can be reported at baseline 0.3 without lengthy justification.",
        ],
    },
}

# Display order: most consequential first (matches the tornado tiers)
SENS_ADV_ORDER = [
    "Walking threshold (d_walk)",
    "Budget (B)",
    "New farmers market cost",
    "Mobile market cost",
    "No-vehicle ZIP cutoff",
    "Coverage target (theta)",
    "Objective weights (omega)",
    "Driving threshold (d_drive)",
    "Cost penalty (lambda)",
    "Income-cost elasticity (gamma)",
]

# Tornado ranking transcribed from the report's cross-sweep table (objective
# swing %, all 13 parameters incl. the three low-sensitivity cost sweeps that
# the report reports as objective-only).
TORNADO_ADV = [
    {"param": "Walking threshold (d_walk)", "swing": 110.0, "tier": 1, "note": "mobile -43%, farmers +27%"},
    {"param": "Budget B",                   "swing": 96.0,  "tier": 1, "note": "mobile +190%, farmers -47%"},
    {"param": "Mobile market cost",         "swing": 23.0,  "tier": 2, "note": "1:1 substitution with farmers"},
    {"param": "New farmers market cost",    "swing": 22.0,  "tier": 2, "note": "+/-25 facilities"},
    {"param": "No-vehicle cutoff",          "swing": 18.0,  "tier": 2, "note": "farmers -31%, mobile +46%"},
    {"param": "Coverage target theta",      "swing": 15.0,  "tier": 3, "note": "288 to 294 facilities"},
    {"param": "Objective weights omega",    "swing": 12.0,  "tier": 3, "note": "+/-2 facilities (normalization)"},
    {"param": "Driving threshold d_drive",  "swing": 10.0,  "tier": 3, "note": "+/-4 facilities"},
    {"param": "Grocery upgrade cost",       "swing": 4.0,   "tier": 4, "note": "minor"},
    {"param": "New grocery cost",           "swing": 3.0,   "tier": 4, "note": "-2 grocery at high cost"},
    {"param": "Cost penalty lambda",        "swing": 3.0,   "tier": 4, "note": "penalty offset only"},
    {"param": "Income-cost elasticity gamma","swing": 1.4,  "tier": 4, "note": "+/-2 facilities"},
    {"param": "Farmers upgrade cost",       "swing": 1.0,   "tier": 4, "note": "supply-capped"},
]
TORNADO_TIER_COLOR = {1: "#7F1D1D", 2: "#B45309", 3: "#1A2B47", 4: "#6B7280"}


def _sens_feasible(block):
    """Rows with a numeric objective (feasible / time-limited)."""
    return [r for r in block["rows"] if r.get("objective") is not None]


def _sens_infeasible_note(block):
    bad = [r["label"] for r in block["rows"] if r.get("objective") is None]
    return bad


def _norm01(vals):
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def _first_crossing(xs, ya, yb):
    for i in range(len(xs) - 1):
        d1 = ya[i] - yb[i]
        d2 = ya[i + 1] - yb[i + 1]
        if d1 == 0:
            return xs[i]
        if d1 * d2 < 0:
            t = d1 / (d1 - d2)
            return xs[i] + t * (xs[i + 1] - xs[i])
    if ya[-1] == yb[-1]:
        return xs[-1]
    return None


def _intersection_xy(xs, ya, yb):
    """First intersection of two piecewise-linear curves over numeric xs.
    Returns (x_int, y_int) interpolated on both x and the y level, or None."""
    for i in range(len(xs) - 1):
        d1 = ya[i] - yb[i]
        d2 = ya[i + 1] - yb[i + 1]
        if d1 == 0:
            return xs[i], ya[i]
        if d1 * d2 < 0:
            t = d1 / (d1 - d2)              # fraction of the segment to the crossing
            x_int = xs[i] + t * (xs[i + 1] - xs[i])
            y_int = ya[i] + t * (ya[i + 1] - ya[i])
            return x_int, y_int
    if ya[-1] == yb[-1]:
        return xs[-1], ya[-1]
    return None


def _fmt_cross(x, unit, label):
    """Format a crossing x-value in the parameter's real units."""
    if unit == "$M":
        return f"${x:,.1f}M"
    if unit == "$K":
        return f"${x:,.0f}K"
    if unit == "m":
        return f"{x:,.0f} m"
    if label == "No-vehicle cutoff":
        return f"{x * 100:.0f}%"
    return f"{x:.2f}"


# ============================================================
# TABS
# ============================================================
tab_explorer, tab_opt, tab_sens, tab_about = st.tabs([
    "Food Access Explorer", "Optimization Model", "Sensitivity Analysis", "About"
])

# ============================================================
# TAB 1 - FOOD ACCESS EXPLORER
# ============================================================
with tab_explorer:
    zip_gdf = load_zip_polygons()
    outlets_df = load_outlets()
    need_df = load_need_weights()

    if len(outlets_df) == 0:
        st.error("Could not load outlet datasets. Verify that the seven outlet Excel files are in the data directory.")
        st.stop()

    with st.sidebar:
        st.markdown("### Explorer Filters")

        all_zips = sorted(zip_gdf["ZIP"].unique().tolist())
        zip_choice = st.multiselect("ZIP Code", ["All ZIPs"] + all_zips, default=["All ZIPs"], key="exp_zip")

        all_types = sorted(outlets_df["store_type"].unique().tolist())
        type_choice = st.multiselect("Store Type(s)", all_types, default=all_types, key="exp_type")

        st.markdown("---")

        cluster_mode = st.radio(
            "Marker Display Mode",
            ["Fast cluster", "Detailed individual markers"],
            index=0, key="exp_cluster",
            help="Cluster mode aggregates nearby markers for faster rendering. Detailed mode shows every store individually but is slower when thousands of markers are visible.",
        )
        show_zip_bounds = st.checkbox("Show ZIP boundaries", value=True, key="exp_bounds")
        show_need = st.checkbox(
            "Shade ZIPs by Need Index", value=False, key="exp_need",
            help="Color the background of each ZIP polygon according to its composite Need Index, on a 0 to 100 scale where higher values indicate greater disadvantage.",
        )
        show_table = st.checkbox("Show filtered data table", value=False, key="exp_table")

    # Filter
    f = outlets_df.copy()
    if "All ZIPs" not in zip_choice and zip_choice:
        sel_zips = set(zip_choice)
        gdf_pts = gpd.GeoDataFrame(f, geometry=gpd.points_from_xy(f["lon"], f["lat"]), crs="EPSG:4326")
        joined = gpd.sjoin(gdf_pts, zip_gdf[["ZIP","geometry"]], how="left", predicate="within")
        f = joined[joined["ZIP"].isin(sel_zips)].drop(columns=["geometry","index_right"], errors="ignore")
    if type_choice:
        f = f[f["store_type"].isin(type_choice)]

    # Metric row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stores Shown", f"{len(f):,}")
    c2.metric("Store Types", f"{f['store_type'].nunique()}")
    c3.metric("ZIPs in View", f"{len(all_zips) if 'All ZIPs' in zip_choice else len(zip_choice)}")
    c4.metric("Detroit Population", f"{int(need_df['Population'].sum()):,}" if len(need_df) else "—")

    # Layout
    map_col, side_col = st.columns([3, 1])
    with map_col:
        m = render_explorer_map(
            f, zip_gdf, show_boundaries=show_zip_bounds,
            need_df=need_df, show_need_shading=show_need,
            cluster=(cluster_mode == "Fast cluster"),
        )
        folium_static(m, height=560)

    with side_col:
        counts = f["store_type"].value_counts().reset_index()
        counts.columns = ["Store Type", "Count"]
        fig = px.bar(counts, y="Store Type", x="Count", orientation="h",
                     color="Store Type", color_discrete_map=COLORS_STORE, height=300)
        fig.update_layout(showlegend=False, margin=dict(l=0,r=0,t=10,b=0),
                          yaxis_title="", xaxis_title="", font=dict(family="Segoe UI"))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("**Store Type Counts**")
        st.dataframe(counts.set_index("Store Type"), use_container_width=True, height=260)

    cdl, _, _ = st.columns([1, 2, 2])
    with cdl:
        csv = f.to_csv(index=False).encode("utf-8")
        st.download_button("Download Filtered CSV", csv,
                          file_name="detroit_food_access_filtered.csv", mime="text/csv")
    if show_table:
        st.dataframe(f, use_container_width=True, height=300)

# ============================================================
# TAB 2 - OPTIMIZATION MODEL
# ============================================================
with tab_opt:
    phase1 = load_phase1()
    if phase1 is None:
        st.error(
            "Phase 1 optimization data not found. Run sweep_0_prepare.py once to generate phase1_baseline.pkl "
            "before using the Optimization Model tab."
        )
        st.stop()

    baseline_df = load_baseline_solution()
    zip_gdf_opt = load_zip_polygons()

    st.markdown("### Optimization Model")
    banner_text = (
        '<div class="banner-info">Adjust the parameters in the sidebar, then click <b>Run Optimization</b>. '
        'The previous result remains on screen while a new solve runs. The solver targets a 2% optimality gap '
        'and is capped at 90 seconds; the best feasible solution found within that time is loaded.</div>'
    )
    st.markdown(banner_text, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("---")
        st.markdown("### Optimization Parameters")

        if st.button("Reset to Baseline", use_container_width=True, key="opt_reset"):
            for k in list(st.session_state.keys()):
                if k.startswith("opt_p_") or k.startswith("opt_cost_") or k == "opt_omega_focus":
                    del st.session_state[k]
            st.session_state.opt_result = None
            st.rerun()

        st.markdown("#### Budget and Coverage")
        budget_M = st.slider(
            "Budget (million dollars)",
            min_value=40, max_value=100, value=40, step=1, key="opt_p_budget",
            help=(
                "Total investment budget in millions of dollars. "
                "Tested range from sensitivity analysis: $40 million is the minimum feasible budget for full coverage with walking equity. "
                "Below $40 million the problem is infeasible. "
                "Above $40 million the model achieves diminishing returns, from about 9 objective units per additional million at $40M down to about 4 units per million at $70M."
            ),
        )

        theta_pct = st.slider(
            "Coverage Target (%)",
            min_value=75, max_value=100, value=100, step=1, key="opt_p_theta",
            help=(
                "Minimum fraction of demand that must be served at every sub-point. "
                "100% requires full coverage everywhere. Relaxing to 95% costs approximately 4% of the achievable objective, "
                "while relaxing further to 75% can raise the achievable objective by approximately 15%. "
                "This is a policy lever rather than a technical parameter."
            ),
        )
        theta = theta_pct / 100.0

        st.markdown("#### Equity")
        nv_pct = st.slider(
            "No-Vehicle ZIP Cutoff (%)",
            min_value=20, max_value=40, value=25, step=1, key="opt_p_nv",
            help=(
                "ZIPs whose no-vehicle household rate exceeds this cutoff are designated car-light, "
                "and every sub-point in those ZIPs must have walking access to a walking-eligible facility. "
                "At 25% the baseline includes 727 walking-required sub-points across 10 ZIPs. "
                "Lowering to 20% expands the requirement to 1651 sub-points and is infeasible at $40 million. "
                "Raising to 30% reduces the requirement to 203 sub-points and increases achievable objective by approximately 15%."
            ),
        )
        nv_threshold = nv_pct / 100.0

        st.markdown("#### Objective Weights")
        omega_focus = st.radio(
            "Outcome Priority",
            ["Equal (1/3, 1/3, 1/3)", "Food Access focus", "Unhealthy-reduction focus", "CVD focus", "Custom"],
            index=0, key="opt_omega_focus",
            help=(
                "Choose how to weight the three outcomes in the objective function. "
                "The three outcomes are food access improvement (A), unhealthy food exposure reduction (R), "
                "and cardiovascular health burden improvement (Q). "
                "Sensitivity analysis shows that the recommended portfolio is essentially weight-invariant: "
                "facility counts vary by at most plus or minus 2 of any type across the full weight simplex, "
                "because the equity and coverage constraints dominate the model."
            ),
        )

        if omega_focus == "Custom":
            oA = st.slider("Weight on Food Access (A)", 0.0, 1.0, 1/3, 0.05, key="opt_p_oA")
            oR = st.slider("Weight on Unhealthy Reduction (R)", 0.0, 1.0, 1/3, 0.05, key="opt_p_oR")
            oQ = st.slider("Weight on CVD Burden (Q)", 0.0, 1.0, 1/3, 0.05, key="opt_p_oQ")
            total = oA + oR + oQ
            if total > 0:
                oA, oR, oQ = oA/total, oR/total, oQ/total
            st.caption(f"Normalized: A = {oA:.2f}, R = {oR:.2f}, Q = {oQ:.2f}")
        else:
            mapping = {
                "Equal (1/3, 1/3, 1/3)":      (1/3, 1/3, 1/3),
                "Food Access focus":          (0.60, 0.20, 0.20),
                "Unhealthy-reduction focus":  (0.20, 0.60, 0.20),
                "CVD focus":                  (0.20, 0.20, 0.60),
            }
            oA, oR, oQ = mapping[omega_focus]

        with st.expander("Advanced parameters"):
            gamma = st.slider(
                "Income-Cost Elasticity (gamma)",
                min_value=0.0, max_value=0.7, value=0.3, step=0.1, key="opt_p_gamma",
                help=(
                    "Site costs scale with local ZIP median income according to "
                    "Cost = Base x (1 + gamma x (Income - Median) / Median). "
                    "Baseline value is 0.3 (a 10% higher income produces a 3% cost premium). "
                    "Sensitivity analysis shows only a 1.4% objective swing across the full tested range, "
                    "making this the most robust parameter in the model."
                ),
            )
            lambda_pen = st.slider(
                "Cost Penalty (lambda)",
                min_value=0.0, max_value=5.0, value=0.0, step=0.5, key="opt_p_lambda",
                help=(
                    "Penalty applied to total spending: Objective minus lambda times (cost divided by budget). "
                    "Baseline value is zero (no penalty). "
                    "Sensitivity analysis shows that increasing lambda does not meaningfully reduce spending, "
                    "because the budget constraint already binds and the equity constraint forces a minimum portfolio size. "
                    "Larger lambda values simply offset the objective."
                ),
            )
            apply_walking = st.checkbox(
                "Enforce walking-equity constraint",
                value=True, key="opt_p_walk_eq",
                help=(
                    "When checked, every sub-point in a car-light ZIP must have walking access to at least one "
                    "walking-eligible facility (new or upgraded grocery, or new or upgraded farmers market). "
                    "Unchecking this removes the equity constraint and allows mobile markets alone to satisfy coverage; "
                    "use only for what-if analysis."
                ),
            )

        with st.expander("Per-type base costs"):
            st.caption("Tested ranges are based on the sensitivity analysis grid.")
            cost_grocery_new = st.number_input(
                "New Grocery Store ($)", value=750_000, min_value=600_000, max_value=900_000, step=50_000,
                key="opt_cost_grocery_new",
                help="Baseline value is $750,000. Tested range is $600,000 to $900,000.",
            )
            cost_grocery_upgrade = st.number_input(
                "Grocery Upgrade ($)", value=175_000, min_value=140_000, max_value=210_000, step=5_000,
                key="opt_cost_grocery_upgrade",
                help="Baseline value is $175,000. Tested range is $140,000 to $210,000.",
            )
            cost_mobile = st.number_input(
                "Mobile Market ($)", value=200_000, min_value=160_000, max_value=240_000, step=10_000,
                key="opt_cost_mobile",
                help=(
                    "Baseline value is $200,000. "
                    "Sensitivity analysis identifies this as a high-impact parameter: "
                    "mobile markets substitute approximately one-for-one with new farmers markets as relative costs change."
                ),
            )
            cost_farmers_new = st.number_input(
                "New Farmers Market ($)", value=100_000, min_value=80_000, max_value=120_000, step=5_000,
                key="opt_cost_farmers_new",
                help=(
                    "Baseline value is $100,000. "
                    "Sensitivity analysis identifies this as the highest-impact unit cost in the model "
                    "(approximately 38% objective swing across the tested range). "
                    "Lower farmers-market cost increases the achievable objective substantially because "
                    "this is the cheapest walking-eligible facility type."
                ),
            )
            cost_farmers_upgrade = st.number_input(
                "Farmers Market Upgrade ($)", value=40_000, min_value=32_000, max_value=48_000, step=2_000,
                key="opt_cost_farmers_upgrade",
                help=(
                    "Baseline value is $40,000. "
                    "Sensitivity is low because the model already upgrades nearly all 31 existing farmers markets at the baseline cost."
                ),
            )

        st.markdown("---")
        st.markdown("#### Solver Settings")
        time_limit = st.slider(
            "Time Limit (seconds)", min_value=30, max_value=180, value=90, step=10, key="opt_tl",
            help="Maximum wall-clock time for the solver. If reached before the optimality gap is met, the best feasible solution found is returned.",
        )
        mip_gap_pct = st.slider(
            "Optimality Gap Target (%)", min_value=1.0, max_value=10.0, value=2.0, step=0.5, key="opt_gap",
            help=(
                "Target relative gap between the best feasible solution and the best known bound. "
                "Smaller values produce more rigorous solutions but require longer solve times. "
                "The default 2% is appropriate for dashboard responsiveness."
            ),
        )
        mip_gap = mip_gap_pct / 100.0

    # Build parameter dict
    params = dict(
        budget=budget_M * 1_000_000,
        theta=theta,
        nv_threshold=nv_threshold,
        omega_A=oA, omega_R=oR, omega_Q=oQ,
        gamma=gamma,
        apply_walking=apply_walking,
        cost_overrides={
            "grocery_new": cost_grocery_new,
            "grocery_upgrade": cost_grocery_upgrade,
            "mobile_market": cost_mobile,
            "farmers_new": cost_farmers_new,
            "farmers_upgrade": cost_farmers_upgrade,
        },
    )
    params["lambda"] = lambda_pen

    # Run button and status
    run_col, status_col = st.columns([1, 4])
    with run_col:
        run_clicked = st.button(
            "Run Optimization",
            type="primary",
            use_container_width=True,
            key="opt_run_btn",
        )

    # ---------- SOLVE ----------
    if run_clicked:
        st.session_state.opt_run_count = st.session_state.get("opt_run_count", 0) + 1
        with st.spinner(f"Solving optimization model (up to {time_limit}s at {mip_gap_pct:.1f}% gap target)..."):
            try:
                result, status, elapsed = solve_optimization(
                    phase1, params,
                    time_limit=time_limit, mip_gap=mip_gap,
                    warm_start_df=baseline_df,
                )
            except Exception as e:
                st.error(f"Solver crashed: {e}")
                result, status, elapsed = None, "exception", 0

        if result is not None:
            st.session_state.opt_result = result
        else:
            st.error(
                f"Could not solve in {elapsed:.1f}s. Termination status: {status}. "
                "Try increasing the Time Limit, raising the budget, relaxing the Coverage Target, "
                "or loosening the No-Vehicle cutoff."
            )

    # Display results (last solved or baseline)
    if st.session_state.opt_result is not None:
        res = st.session_state.opt_result
        sel_df = res["selected"]
    else:
        sel_df = baseline_df if baseline_df is not None else pd.DataFrame()
        if sel_df is not None and len(sel_df) > 0 and "cost" in sel_df.columns:
            tc_baseline = dict(sel_df["intervention_type"].value_counts())
            cost_baseline = float(sel_df["cost"].sum())
        else:
            tc_baseline, cost_baseline = {}, 0.0
        res = {
            "objective": 187.96, "n_facilities": len(sel_df) if sel_df is not None else 0,
            "total_cost": cost_baseline,
            "budget_used_pct": 99.9 if cost_baseline > 0 else 0,
            "type_counts": tc_baseline,
            "I_walk_size": 727, "I_walk_eff_size": 727,
            "termination": "baseline (reference)",
            "elapsed": 0,
        }

    # FILL THE STATUS COLUMN BANNER NOW (after res is known).
    with status_col:
        if st.session_state.opt_result is None:
            st.markdown(
                '<div class="banner-info">Currently displaying the baseline reference result (294 facilities, '
                "$39.97 million, objective 187.96). Adjust the parameters in the sidebar and click "
                "<b>Run Optimization</b> to compute a new solution with your settings.</div>",
                unsafe_allow_html=True,
            )
        else:
            r = st.session_state.opt_result
            ps = r["params_snapshot"]
            hit_tl = r.get("hit_time_limit", False)
            achieved_gap = r.get("achieved_gap")
            gap_text = f" Achieved gap = {achieved_gap*100:.2f}%." if achieved_gap is not None else ""

            if hit_tl:
                st.markdown(
                    f'<div class="banner-warn"><b>Solve #{st.session_state.get("opt_run_count", 0)} hit the {r["elapsed"]:.0f}s time limit.</b><br>'
                    f"Parameters: Budget ${ps['budget']/1e6:.0f}M, "
                    f"Coverage {ps['theta']*100:.0f}%, "
                    f"No-Vehicle cutoff {ps['nv_threshold']*100:.0f}%, "
                    f"gamma {ps['gamma']:.1f}, lambda {ps['lambda']:.1f}.<br>"
                    f"<b>Best feasible result found: objective = {r['objective']:.2f}, facilities = {r['n_facilities']}, "
                    f"cost = ${r['total_cost']/1e6:.2f}M ({r['budget_used_pct']:.1f}% of budget).</b>{gap_text}<br>"
                    f"This is the best solution the solver found within the time limit, but the target optimality gap was not reached. "
                    f"To get a more optimal solution, increase the Time Limit slider in the sidebar (try 180s) and run again.</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="banner-success"><b>Solve #{st.session_state.get("opt_run_count", 0)} completed in {r["elapsed"]:.1f}s.</b><br>'
                    f"Parameters: Budget ${ps['budget']/1e6:.0f}M, "
                    f"Coverage {ps['theta']*100:.0f}%, "
                    f"No-Vehicle cutoff {ps['nv_threshold']*100:.0f}%, "
                    f"gamma {ps['gamma']:.1f}, lambda {ps['lambda']:.1f}.<br>"
                    f"<b>Result: objective = {r['objective']:.2f}, facilities = {r['n_facilities']}, "
                    f"cost = ${r['total_cost']/1e6:.2f}M ({r['budget_used_pct']:.1f}% of budget).</b>{gap_text} "
                    f"Termination: {r['termination']}.</div>",
                    unsafe_allow_html=True,
                )

    # Metrics
    st.markdown("### Solution Summary")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Objective Value", f"{res['objective']:.2f}")
    m2.metric("Total Facilities", f"{res['n_facilities']}")
    m3.metric("Total Cost", f"${res['total_cost']/1e6:.2f}M")
    m4.metric("Budget Utilization", f"{res['budget_used_pct']:.1f}%")
    m5.metric("Walking-Required Sub-points", f"{res['I_walk_size']}")

    # Map and portfolio
    st.markdown("### Selected Intervention Portfolio")
    map_col, mix_col = st.columns([3, 1])
    with map_col:
        active_nv = st.session_state.opt_result["params_snapshot"]["nv_threshold"] if st.session_state.opt_result else 0.25
        m_opt = render_optimization_map(sel_df, zip_gdf_opt, phase1, nv_threshold=active_nv, show_need_shading=True)
        folium_static(m_opt, height=600)
    with mix_col:
        mix_data = [{"Type": NAMES_OPT[k], "Count": res["type_counts"].get(k, 0)} for k in COLORS_OPT]
        mix_df = pd.DataFrame(mix_data)
        st.markdown("**Portfolio Composition**")
        st.dataframe(mix_df, use_container_width=True, hide_index=True, height=220)
        fig = px.bar(mix_df, x="Count", y="Type", orientation="h", color="Type",
                     color_discrete_map={NAMES_OPT[k]: c for k, c in COLORS_OPT.items()}, height=280)
        fig.update_layout(showlegend=False, margin=dict(l=0,r=10,t=10,b=0),
                          yaxis_title="", xaxis_title="", font=dict(family="Segoe UI"))
        st.plotly_chart(fig, use_container_width=True)

    # Locations table
    st.markdown("### Selected Facility Locations")
    if sel_df is not None and len(sel_df) > 0:
        display_cols = ["intervention_type", "site_zip", "latitude", "longitude",
                       "x_merc", "y_merc", "cost", "capacity", "site_id"]
        display_cols = [c for c in display_cols if c in sel_df.columns]
        sel_show = sel_df[display_cols].copy()
        if "intervention_type" in sel_show.columns:
            sel_show["intervention_type"] = sel_show["intervention_type"].map(lambda k: NAMES_OPT.get(k, k))
        if "cost" in sel_show.columns:
            sel_show["cost"] = sel_show["cost"].apply(lambda x: f"${x:,.0f}")
        if "capacity" in sel_show.columns:
            sel_show["capacity"] = sel_show["capacity"].apply(lambda x: f"{int(x):,}")
        if "latitude" in sel_show.columns:
            sel_show["latitude"] = sel_show["latitude"].round(6)
            sel_show["longitude"] = sel_show["longitude"].round(6)
        st.dataframe(sel_show, use_container_width=True, height=360, hide_index=True)
        csv = sel_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download Facility Locations (CSV)", csv,
                          file_name="optimization_selected_facilities.csv", mime="text/csv")

    with st.expander("Map legend"):
        st.markdown("""
- **Filled colored circles** represent selected interventions, color-coded by type:
    - Blue: New Grocery Store
    - Green: Grocery Upgrade
    - Amber: New Farmers Market
    - Dark Amber: Farmers Market Upgrade
    - Purple: Mobile Market
- **Hollow circles** represent existing groceries and farmers markets that were not selected for upgrade.
- **Blue boundary outline** indicates a walking-required ZIP (no-vehicle household rate above the current cutoff).
- **Dashed dark outline** indicates a ZIP with at least one sub-point whose walking threshold was relaxed because no walking-eligible facility was within the standard 833-meter distance.
- **Background shading** reflects the composite Need Index (0 to 100), with darker shading indicating greater disadvantage.
        """)

# ============================================================
# TAB 3 - SENSITIVITY ANALYSIS  (pre-computed; no solver runs)
# ============================================================
with tab_sens:
    # Local styles for the findings / story boxes (scoped, additive).
    st.markdown("""
    <style>
    .kf-box {background:#F9FAFB;border-left:4px solid #1A2B47;padding:14px 18px;
             border-radius:4px;margin:8px 0;font-size:13px;line-height:1.6;}
    .kf-title {font-weight:700;color:#1A2B47;margin-bottom:6px;font-size:14px;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("### Sensitivity Analysis")
    st.markdown(
        '<div class="banner-info">Pre-computed one-at-a-time (OAT) sensitivity results: '
        'nine completed sweeps, 59 individual MILP re-solves at a 0.5% gap target with an '
        '1800 s time limit. No solver runs in this tab; every value is transcribed from the '
        'sensitivity analysis report. The baseline plan is 294 facilities for $39.97M '
        '(objective 187.96).</div>',
        unsafe_allow_html=True,
    )

    # ---- Cross-parameter tornado (objective swing, all 13 parameters) ----
    st.markdown("#### Cross-Parameter Overview")
    st.caption("Objective swing across each parameter's tested range. Longer bars mark the "
               "parameters the recommended plan is most sensitive to. Colour denotes tier.")
    tor = sorted(TORNADO_ADV, key=lambda d: d["swing"])
    fig_tor = go.Figure()
    fig_tor.add_trace(go.Bar(
        y=[d["param"] for d in tor],
        x=[d["swing"] for d in tor],
        orientation="h",
        marker=dict(color=[TORNADO_TIER_COLOR[d["tier"]] for d in tor]),
        text=[f"{d['swing']:.0f}%" if d["swing"] >= 3 else f"{d['swing']:.1f}%" for d in tor],
        textposition="outside", textfont=dict(size=11, family="Segoe UI"),
        customdata=[d["note"] for d in tor],
        hovertemplate="%{y}<br>Objective swing: %{x:.1f}%<br>%{customdata}<extra></extra>",
    ))
    fig_tor.update_layout(
        height=430, margin=dict(l=10, r=60, t=10, b=10),
        xaxis_title="Objective swing across tested range (%)",
        yaxis_title="", font=dict(family="Segoe UI", size=12), plot_bgcolor="white",
    )
    fig_tor.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
    st.plotly_chart(fig_tor, use_container_width=True)
    st.caption("Tier 1 (dark red): structural drivers. Tier 2 (brown): composition drivers. "
               "Tier 3 (navy): measurable but composition-neutral. Tier 4 (grey): negligible.")

    st.markdown("---")
    st.markdown("#### Per-Parameter Inspector")

    param_choice = st.selectbox("Select a parameter to inspect", SENS_ADV_ORDER,
                                index=0, key="sens_adv_param")
    block = SENS_ADV[param_choice]
    unit = block.get("unit", "")
    xlabel = block["label"] + (f" ({unit})" if unit else "")

    st.markdown(f"**{param_choice}** &mdash; {block['description']}")

    feas = _sens_feasible(block)
    bad = _sens_infeasible_note(block)
    if bad:
        st.markdown(
            f'<div class="banner-warn">No feasible solution at: <b>{", ".join(bad)}</b>. '
            'These points are shown in the results table below but omitted from the charts.</div>',
            unsafe_allow_html=True,
        )

    labels = [r["label"] for r in feas]

    # ---- Hero figure: objective + total facilities, and portfolio mix ----
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.56, 0.44],
        vertical_spacing=0.09, specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
        subplot_titles=(f"Objective and facility count vs {block['label']}",
                        f"Portfolio composition vs {block['label']}"),
    )
    fig.add_trace(go.Scatter(
        x=labels, y=[r["objective"] for r in feas],
        mode="lines+markers+text", text=[f"{r['objective']:.1f}" for r in feas],
        textposition="top center", textfont=dict(size=10),
        line=dict(color="#1A2B47", width=2.5),
        marker=dict(size=10, color="#1A2B47", line=dict(color="white", width=1.5)),
        name="Objective",
        hovertemplate=f"{block['label']}=%{{x}}<br>Objective: %{{y:.2f}}<extra></extra>",
    ), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(
        x=labels, y=[r.get("total") for r in feas],
        mode="lines+markers",
        line=dict(color="#D68910", width=2, dash="dot"),
        marker=dict(size=9, color="#D68910", symbol="diamond", line=dict(color="white", width=1.2)),
        name="Total facilities",
        hovertemplate=f"{block['label']}=%{{x}}<br>Facilities: %{{y}}<extra></extra>",
    ), row=1, col=1, secondary_y=True)

    # baseline highlight
    base_lbl = None
    for r in feas:
        if r["value"] == block["baseline"]:
            base_lbl = r["label"]; base_obj = r["objective"]; break
    if base_lbl is not None:
        fig.add_trace(go.Scatter(
            x=[base_lbl], y=[base_obj], mode="markers",
            marker=dict(size=22, color="rgba(214,137,16,0)", line=dict(color="#D68910", width=3)),
            name="Baseline", hovertemplate="Baseline<extra></extra>",
        ), row=1, col=1, secondary_y=False)

    for k in ADV_TYPE_KEYS:
        fig.add_trace(go.Bar(
            x=labels, y=[r.get(k, 0) for r in feas],
            name=NAMES_OPT[k], marker_color=COLORS_OPT[k],
            text=[r.get(k, 0) for r in feas], textposition="inside",
            textfont=dict(color="white", size=10),
            hovertemplate=f"{block['label']}=%{{x}}<br>{NAMES_OPT[k]}: %{{y}}<extra></extra>",
        ), row=2, col=1)

    fig.update_xaxes(title_text=xlabel, row=2, col=1, showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(title_text="Objective", row=1, col=1, secondary_y=False, showgrid=True, gridcolor="#E5E7EB")
    fig.update_yaxes(title_text="Facilities", row=1, col=1, secondary_y=True, showgrid=False, color="#D68910")
    fig.update_yaxes(title_text="Facility count", row=2, col=1, showgrid=True, gridcolor="#E5E7EB")
    fig.update_layout(
        barmode="stack", height=640, font=dict(family="Segoe UI", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=70, b=40), plot_bgcolor="white", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ---- Achieved-gap panel (status-coloured) ----
    gap_vals = [r.get("gap") for r in feas]
    if any(g is not None for g in gap_vals):
        gcol = ["#C0392B" if (r.get("status", "").lower().startswith("time")) else "#1A2B47" for r in feas]
        fig_g = go.Figure()
        fig_g.add_trace(go.Bar(
            x=labels, y=[(g if g is not None else 0) for g in gap_vals],
            marker_color=gcol,
            text=[(f"{g:.2f}%" if g is not None else "-") for g in gap_vals],
            textposition="outside", textfont=dict(size=11),
            hovertemplate=f"{block['label']}=%{{x}}<br>Achieved gap: %{{y:.2f}}%<extra></extra>",
            showlegend=False,
        ))
        fig_g.add_hline(y=0.5, line=dict(color="#16A34A", width=1.5, dash="dash"),
                        annotation_text="0.5% target", annotation_position="top left")
        fig_g.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10),
                            font=dict(family="Segoe UI", size=12), plot_bgcolor="white",
                            yaxis_title="Achieved MIP gap (%)", xaxis_title=xlabel,
                            title=dict(text="Achieved optimality gap (navy = optimal, red = hit time limit)",
                                       font=dict(size=13)))
        fig_g.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
        fig_g.update_yaxes(showgrid=True, gridcolor="#E5E7EB")
        st.plotly_chart(fig_g, use_container_width=True)

    # ---- Trade-off / interpretation ----
    st.markdown("#### Trade-off Analysis")
    tcfg = block.get("tradeoff")
    if tcfg is not None:
        def _acc(field, r):
            return field(r) if callable(field) else r.get(field)
        pairs = [(r, _acc(tcfg["field_a"], r), _acc(tcfg["field_b"], r)) for r in feas]
        pairs = [(r, a, b) for (r, a, b) in pairs if a is not None and b is not None]

        if len(pairs) >= 2:
            rk = [p[0] for p in pairs]
            a_raw = [p[1] for p in pairs]
            b_raw = [p[2] for p in pairs]
            # Numeric x where the parameter is numeric (so the crossing marker can be
            # placed exactly); fall back to an index axis for categorical parameters.
            x_is_numeric = all(isinstance(r["value"], (int, float)) for r in rk)
            xs = [r["value"] for r in rk] if x_is_numeric else list(range(len(rk)))
            ticklabels = [r["label"] for r in rk]
            a_n = _norm01(a_raw)
            b_n = _norm01(b_raw)
            cross = _intersection_xy(xs, a_n, b_n)

            ft = go.Figure()
            ft.add_trace(go.Scatter(
                x=xs, y=a_n, mode="lines+markers", customdata=a_raw,
                line=dict(color="#1A2B47", width=3),
                marker=dict(size=11, color="#1A2B47", line=dict(color="white", width=1.5)),
                name=tcfg["label_a"],
                hovertemplate=tcfg["label_a"] + "<br>Raw: %{customdata:.2f}<extra></extra>"))
            ft.add_trace(go.Scatter(
                x=xs, y=b_n, mode="lines+markers", customdata=b_raw,
                line=dict(color="#D68910", width=3, dash="dot"),
                marker=dict(size=11, color="#D68910", symbol="diamond", line=dict(color="white", width=1.5)),
                name=tcfg["label_b"],
                hovertemplate=tcfg["label_b"] + "<br>Raw: %{customdata:.2f}<extra></extra>"))

            cross_str = None
            if cross is not None:
                x_int, y_int = cross
                if x_is_numeric:
                    cross_str = _fmt_cross(x_int, unit, block["label"])
                else:
                    lo = int(max(0, min(len(ticklabels) - 1, int(x_int))))
                    hi = min(len(ticklabels) - 1, lo + 1)
                    cross_str = (ticklabels[lo] if lo == hi
                                 else f"between {ticklabels[lo]} and {ticklabels[hi]}")
                # vertical guide, exact crossing circle, and arrow callout
                ft.add_shape(type="line", x0=x_int, x1=x_int, y0=0, y1=1.05,
                             xref="x", yref="paper",
                             line=dict(color="#16A34A", width=2.5, dash="dash"))
                ft.add_trace(go.Scatter(
                    x=[x_int], y=[y_int], mode="markers",
                    marker=dict(size=22, color="rgba(22,163,74,0)", line=dict(color="#16A34A", width=4)),
                    name="Trade-off point",
                    hovertemplate=f"<b>Trade-off point</b><br>{block['label']}: {cross_str}<extra></extra>"))
                ft.add_annotation(
                    x=x_int, y=y_int,
                    text=f"<b>Trade-off: {block['label']} \u2248 {cross_str}</b>",
                    showarrow=True, arrowhead=2, ax=45, ay=-55,
                    font=dict(size=13, color="#16A34A", family="Segoe UI"),
                    bgcolor="rgba(255,255,255,0.85)", bordercolor="#16A34A", borderwidth=1.5)

            layout_kw = dict(
                height=430, font=dict(family="Segoe UI", size=12),
                yaxis=dict(range=[-0.05, 1.12], title="Normalized [0, 1]"),
                xaxis_title=xlabel,
                legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="center", x=0.5),
                margin=dict(l=10, r=10, t=80, b=40), plot_bgcolor="white")
            ft.update_layout(**layout_kw)
            if not x_is_numeric:
                ft.update_xaxes(tickmode="array", tickvals=xs, ticktext=ticklabels)
            ft.update_xaxes(showgrid=True, gridcolor="#E5E7EB")
            ft.update_yaxes(showgrid=True, gridcolor="#E5E7EB")
            st.plotly_chart(ft, use_container_width=True)

            if cross_str is not None:
                body = (f"{tcfg['story']}<br><br><b>Trade-off point identified at "
                        f"{block['label']} \u2248 {cross_str}.</b>")
            else:
                body = tcfg.get("no_intersection_msg",
                                tcfg["story"] + "<br><br><b>The two curves do not cross within the "
                                "tested range.</b>")
            st.markdown(f'<div class="kf-box"><div class="kf-title">What the trade-off shows</div>{body}</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="kf-box">{tcfg.get("story", "")}</div>', unsafe_allow_html=True)

    elif block.get("tradeoff_note"):
        st.markdown(
            '<div class="kf-box"><div class="kf-title">Interpretation</div>'
            + block["tradeoff_note"] + "</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="kf-box"><div class="kf-title">Robust parameter</div>'
            'This parameter has no meaningful benefit-versus-cost trade-off: across its tested '
            'range the recommended portfolio is essentially unchanged (see the key findings below). '
            'The objective moves mainly through normalization or a constant penalty offset, not '
            'through a real shift in the plan.</div>', unsafe_allow_html=True)

    # ---- Sweep results table (all rows, incl. infeasible) ----
    st.markdown("#### Sweep Results")
    tbl_rows = []
    for r in block["rows"]:
        tbl_rows.append({
            "Value": r["label"],
            "Status": r.get("status", ""),
            "Objective": (f"{r['objective']:.2f}" if r.get("objective") is not None else "-"),
            "New Grocery": r.get("grocery_new", "-"),
            "Grocery Upg.": r.get("grocery_upgrade", "-"),
            "Mobile": r.get("mobile_market", "-"),
            "New Farmers": r.get("farmers_new", "-"),
            "Farmers Upg.": r.get("farmers_upgrade", "-"),
            "Total": r.get("total", "-"),
            "Gap %": (f"{r['gap']:.2f}" if r.get("gap") is not None else "-"),
        })
    st.dataframe(pd.DataFrame(tbl_rows), use_container_width=True, hide_index=True, height=260)

    # ---- Key findings ----
    st.markdown("#### Key Findings for this parameter")
    kf = '<div class="kf-box"><div class="kf-title">Insights from the ' \
         + str(len(_sens_feasible(block))) + ' feasible re-solves</div><ol style="margin:0;padding-left:18px;">'
    for f_ in block["findings"]:
        kf += f'<li style="margin-bottom:8px;">{f_}</li>'
    kf += "</ol></div>"
    st.markdown(kf, unsafe_allow_html=True)

    # ---- Cross-sweep synthesis ----
    with st.expander("Cross-sweep synthesis (all 59 runs)", expanded=False):
        st.markdown(
            "**Four conclusions from the full sensitivity analysis (59 MILP re-solves across nine parameters):**\n\n"
            "1. **Two structural parameters dominate.** The walking threshold (d_walk) and the budget (B) each "
            "shift the objective by roughly a factor of two across their tested ranges and reshape the portfolio "
            "dramatically. Model recommendations are only meaningful once a budget and a walking standard are fixed.\n\n"
            "2. **The recommended portfolio is remarkably robust to economic and weighting choices.** Objective "
            "weights, income-cost elasticity, the cost penalty, the driving threshold, and the grocery / farmers-"
            "upgrade unit costs each move the plan by at most +/-2 facilities of any type. The plan of 4 new "
            "groceries, 19 grocery upgrades, 80 mobile markets, 165 new farmers markets, and 26 farmers-market "
            "upgrades is essentially invariant to them.\n\n"
            "3. **The model is driven by its constraints, not its objective.** Small changes to the walking "
            "threshold or the no-vehicle cutoff (both of which reshape the binding walking-equity constraint C2) "
            "produce large objective changes, while a cost penalty does not reduce spending because C1, C2, and the "
            "budget already determine the minimum required plan. The feasible region is a tight corner; the "
            "objective merely selects among nearly indistinguishable points within it.\n\n"
            "4. **Infeasibility findings are substantive policy outputs.** Full coverage with walking equity is "
            "infeasible below $40M, a 7-minute (600 m) walking standard is infeasible at $40M, and a 20% no-vehicle "
            "cutoff (61% of sub-points made car-light) has no feasible solution in 30 minutes at $40M. All three "
            "trace to the same structural root: walking equity at the $40M budget level.\n\n"
            "**Implication for Phase 2:** scenario-based and robust-optimization extensions should focus on joint "
            "variation of budget, walking threshold, and the no-vehicle cutoff; jointly varying costs and weights "
            "yields little additional information about the recommended portfolio."
        )

# ============================================================
# TAB 4 - ABOUT
# ============================================================
with tab_about:
    st.markdown("### About This Dashboard")

    st.markdown(
        "This dashboard provides spatial decision support for the **Detroit Food Access Optimization Project**, "
        "developed in the **Health Services Research (HSR) Laboratory**, **Department of Industrial and Systems Engineering**, "
        "**Wayne State University**, under the supervision of **Dr. Melike Yildirim**. "
        "The project formulates the placement of healthy-food retail interventions as a mixed-integer linear program "
        "that maximizes a population-need-weighted, normalized measure of food access, unhealthy-food exposure reduction, "
        "and cardiovascular health burden improvement, subject to budget, capacity, accessibility, and equity constraints."
    )

    st.markdown("#### Dashboard tabs")
    st.markdown(
        "**Food Access Explorer** displays the existing food retail landscape of Detroit across seven outlet categories: "
        "grocery stores, farmers markets, food pantries, SNAP retailers, gas stations, liquor stores, and restaurants. "
        "Users can filter by ZIP code and store type, toggle ZIP boundaries and Need-Index shading, and download the filtered dataset."
    )
    st.markdown(
        "**Optimization Model** lets the user adjust model parameters (budget, coverage target, walking equity rule, "
        "objective weights, income-cost elasticity, cost penalty, and per-type base costs) and solves the optimization "
        "model live. The previously solved result is shown until a new run completes, so the dashboard remains usable "
        "during a solve. Each solve targets a 2% optimality gap and is capped at 90 seconds; the best feasible solution "
        "found within those bounds is loaded. For paper-grade rigor (0.5% gap), use the standalone Colab notebooks."
    )

    st.markdown("#### Methodology summary")
    st.markdown(
        "The model partitions each ZIP into 500-meter-spaced demand sub-points (2,706 in total), generates 419 candidate "
        "intervention sites from a filtered 1-kilometer grid plus existing groceries, farmers markets, and ZIP centroids, "
        "and applies a per-sub-point distance threshold with linear distance decay. "
        "Five intervention types are modeled: new grocery store, grocery upgrade, new farmers market, farmers market upgrade, "
        "and mobile market. A walking-equity constraint requires sub-points in car-light ZIPs to have walking access to at least one "
        "walking-eligible facility. The MILP is solved using the HiGHS open-source solver through Pyomo."
    )

    st.markdown("#### Data sources")
    st.markdown(
        "- 32 Detroit ZIP polygons (Detroit ZIP shapefile)\n"
        "- ZIP-level demographics from the American Community Survey (ACS) 5-year estimates\n"
        "- Chronic-disease prevalence data from the CDC PLACES dataset\n"
        "- Retailer location datasets for groceries, farmers markets, food pantries, SNAP retailers, gas stations, liquor stores, and restaurants\n"
        "- Composite Need Index derived from the project's ZIP-level analysis"
    )

    st.markdown("#### Project team and acknowledgments")
    st.markdown(
        "**Supervisor:** Dr. Melike Yildirim, Department of Industrial and Systems Engineering, Wayne State University.\n\n"
        "**Laboratory:** Health Services Research (HSR) Laboratory.\n\n"
        "This dashboard is part of an ongoing research effort to translate spatial food-access analysis "
        "into actionable, equity-aware investment recommendations for municipal and community partners. "
        "Research outputs from this project are intended for academic publication and policy translation."
    )
