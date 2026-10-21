"""
Build the compact data files the dashboard reads at runtime.

Run once from the repository root (needs geopandas and the Phase 1 pickle):
    python tools/prepare_data.py path/to/phase1_baseline.pkl

Outputs in data/:
    model_structure.npz   assignment triples and per-subpoint arrays (exactly the paper's model inputs)
    model_meta.json       sites, ZIP attributes, constants
    outlets.parquet       existing food outlets with ZIP codes (7 categories)
    zips.geojson          ZIP polygons in latitude and longitude, lightly simplified
    zip_profile.csv       ZIP-level indicators used on the landing page
"""
import json
import math
import os
import pickle
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fastmodel as fm  # noqa: E402

R_EARTH = 6378137.0


def merc_to_latlon(x, y):
    lon = math.degrees(x / R_EARTH)
    lat = math.degrees(2 * math.atan(math.exp(y / R_EARTH)) - math.pi / 2)
    return lat, lon


def main(pkl):
    import geopandas as gpd
    out = os.path.join(ROOT, "data")
    os.makedirs(out, exist_ok=True)
    ph = pickle.load(open(pkl, "rb"))
    S = fm.build_structure(ph)

    # ---------- model structure
    xy = {dp["i"]: (dp["x"], dp["y"]) for dp in ph["demand_points"]}
    sub_xy = np.array([xy[i] for i in S.sub_ids])
    sub_ll = np.array([merc_to_latlon(x, y) for x, y in sub_xy])
    relaxed = set(int(r["i"]) for r in ph.get("walk_relaxed_subs", []) if "i" in r)
    np.savez_compressed(
        os.path.join(out, "model_structure.npz"),
        sub_ids=S.sub_ids, sub_zip=S.sub_zip.astype("U5"), pop_i=S.pop_i, w_i=S.w_i,
        sub_lat=sub_ll[:, 0], sub_lon=sub_ll[:, 1], sub_x=sub_xy[:, 0], sub_y=sub_xy[:, 1],
        sub_relaxed=np.array([i in relaxed for i in S.sub_ids]),
        jk_site=S.jk_site, jk_type=S.jk_type, jk_inc=S.jk_inc, site_of_jk=S.site_of_jk,
        arc_i=S.arc_i, arc_jk=S.arc_jk, arc_walk=S.arc_walk, arc_decay=S.arc_decay,
    )
    sites = []
    for s in ph["J"]:
        lat, lon = merc_to_latlon(s["x"], s["y"])
        sites.append(dict(j=int(s["j"]), site_type=s["site_type"], zip=str(s["zip"]),
                          lat=lat, lon=lon, x=s["x"], y=s["y"]))
    meta = dict(
        n_sites=S.n_sites, inc_median=S.inc_median,
        noveh={str(k): float(v) for k, v in ph["NoVeh"].items()},
        pop_zip={str(k): float(v) for k, v in ph["Pop_ZIP"].items()},
        w_zip={str(k): float(v) for k, v in ph["w_ZIP"].items()},
        inc={str(k): float(v) for k, v in ph["Inc"].items()},
        sites=sites,
        constants=dict(beta=float(ph["BETA_CVD"]), ceil_factor=float(ph["CEIL_FACTOR"]),
                       gamma=float(ph["GAMMA"]), walk_m=float(ph["STD_D_WALK"]),
                       drive_m=float(ph["STD_D_DRIVE"]), spacing_m=float(ph["SUBPOINT_SPACING"]),
                       nv_threshold=float(ph["NV_THRESHOLD"]),
                       cost=ph["C_base"], cap=ph["Cap_base"],
                       dfa=ph["delta_FA_base"], du=ph["delta_U_base"]),
    )
    json.dump(meta, open(os.path.join(out, "model_meta.json"), "w"))

    # ---------- ZIP polygons
    gdf = gpd.read_file(os.path.join(ROOT, "zip_codes.shp"))
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=3857)
    zcol = next(c for c in ["zipcode", "ZIP", "Zipcode", "ZCTA5CE10", "zip"] if c in gdf.columns)
    gdf["ZIP"] = gdf[zcol].astype(str).str.zfill(5)
    gdf = gdf[["ZIP", "geometry"]].dissolve(by="ZIP", as_index=False).to_crs(epsg=3857)
    gdf["geometry"] = gdf.geometry.simplify(15)
    gdf = gdf.to_crs(epsg=4326)
    gdf = gdf[gdf["ZIP"].isin({str(k) for k in ph["Pop_ZIP"]})]
    gdf.to_file(os.path.join(out, "zips.geojson"), driver="GeoJSON")

    # ---------- outlets
    specs = {
        "Grocery Store": ("Grocery Store_Zip Code.xlsx", "dfm-stores-master-dfm_grocery_2", "Latitude", "Longitude"),
        "Farmers Market": ("Farmers Market_ZIP Code.xlsx", 0, "Latitude", "Longitude"),
        "Food Pantry": ("Food Pantries__Zip Code.xlsx", "Food_Pantries_in_Michigan_2016.", "Y", "X"),
        "SNAP Retailer": ("SNAP_Zip Code.xlsx", "SNAP Retailer Locations", "Latitude", "Longitude"),
        "Gas Station": ("Gas Station_Zip Code.xlsx", "Gas Station", "Latitude", "Longitude"),
        "Liquor Store": ("Liqour_Zip Cod.xlsx", "Liqoure", "Latitude", "Longitude"),
        "Restaurant": ("Restaurant _Zip Code..xlsx", "Restaurant", "lat", "lon"),
    }
    rows = []
    for name, (fn, sheet, la, lo) in specs.items():
        df = pd.read_excel(os.path.join(ROOT, fn), sheet_name=sheet)
        if name == "Restaurant" and "status" in df.columns:
            df = df[df["status"].astype(str).str.strip().str.lower() != "permanently closed"]
        df["lat"] = pd.to_numeric(df[la], errors="coerce")
        df["lon"] = pd.to_numeric(df[lo], errors="coerce")
        df = df.dropna(subset=["lat", "lon"])
        df = df[df["lat"].between(42.25, 42.46) & df["lon"].between(-83.30, -82.90)].copy()
        ncol = next((c for c in ["Store Name", "Name", "NAME", "name", "RETAILER", "store_name"] if c in df.columns), None)
        acol = next((c for c in ["Address", "ADDRESS", "address", "street", "Street"] if c in df.columns), None)
        df["name"] = df[ncol].astype(str).str.strip() if ncol else name
        df["address"] = df[acol].astype(str).str.strip() if acol else ""
        df["category"] = name
        rows.append(df[["category", "name", "address", "lat", "lon"]])
    outl = pd.concat(rows, ignore_index=True)
    pts = gpd.GeoDataFrame(outl, geometry=gpd.points_from_xy(outl.lon, outl.lat), crs="EPSG:4326")
    j = gpd.sjoin(pts, gdf[["ZIP", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    outl["zip"] = j["ZIP"].fillna("").values
    outl = outl[outl["zip"] != ""].reset_index(drop=True)
    outl.to_parquet(os.path.join(out, "outlets.parquet"), index=False)

    # ---------- ZIP profile
    d = pd.read_excel(os.path.join(ROOT, "final_detroit_food_health_dataset.xlsx"), sheet_name="data_set")
    n = pd.read_excel(os.path.join(ROOT, "need_index_by_zip.xlsx"), sheet_name="need_index")
    d["ZIP"] = d["ZIP"].astype(int).astype(str); n["ZIP"] = n["ZIP"].astype(int).astype(str)
    prof = d.merge(n[["ZIP", "NeedIndex_0_100", "NeedRank"]], on="ZIP", how="left")
    keep = ["ZIP", "Population", "MedianIncome", "PovertyRate", "NoVehicleRate", "Black_pct",
            "Diabetes", "Obesity", "Coronary Heart Disease", "Stroke", "High Cholesterol",
            "healthy_count", "unhealthy_count", "healthy_per_10k", "unhealthy_per_10k",
            "FoodAccessScore", "NeedIndex_0_100", "NeedRank"]
    prof[keep].to_csv(os.path.join(out, "zip_profile.csv"), index=False)
    print("done:", {f: os.path.getsize(os.path.join(out, f)) for f in os.listdir(out)})


if __name__ == "__main__":
    main(sys.argv[1])
