# Detroit Food Access Optimization Dashboard

Interactive companion to the paper *A Spatial Optimization Framework for Equitable
Healthy Food Access Investment: Application to Detroit*. Live app:
https://detroit-food-access-dashboard-gurx9yq65mt7ewrbk3qypx.streamlit.app

The app has four tabs:

- **Food access explorer**: the existing food environment (seven outlet categories),
  ZIP-level need and health indicators, and a profile for any ZIP code.
- **Optimization model**: runs the paper's mixed-integer linear program with your
  settings and returns the plan on a map, by type and by ZIP code, with CSV and PDF downloads.
- **Sensitivity analysis**: the 71 precomputed solves (ten one-at-a-time sweeps).
- **About**: method, data sources, funding and citation.

## Run locally

```
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)

Push this folder to GitHub, then create the app at https://share.streamlit.io with
`app.py` as the main file. Every file the app needs is in the repository (about 5 MB),
so no Google Drive download is required.

## Repository layout

```
app.py                     the application
app_theme.py               colors, fonts, chart template and page styles
fastmodel.py               the optimization model built directly in HiGHS
sens_data.py               precomputed results of the first nine sensitivity sweeps
data/                      compact runtime data (built by tools/prepare_data.py)
outputs/baseline_results.xlsx            the paper's baseline portfolio ($40M, 295 interventions)
outputs/sensitivity/sweep11_impact.xlsx  impact-coefficient sweep (12 solves)
outputs/precomputed/       minimum-cost feasible plans and the scenario library
tools/prepare_data.py      rebuilds data/ from the source files and the Phase 1 pickle
tools/precompute.py        rebuilds outputs/precomputed/
*.xlsx, zip_codes.*        original source data
```

## How the app stays fast

- Each tab is a Streamlit fragment, and each control panel is a form. Nothing reruns
  until **Apply changes** or **Run optimization** is pressed, and then only that tab reruns.
- Data are read once from small binary files and kept in memory.
- Maps are drawn with deck.gl (pydeck), which renders thousands of points on the GPU.
- The model is built directly as a sparse HiGHS model in a fraction of a second.
  The redundant linking constraint z ≤ x is omitted because the capacity constraint
  implies it when populations are positive; the set of feasible plans is unchanged.
- Every solve starts from a feasible plan: a precomputed solution, the reference plan or
  a minimum-cost plan, extended greedily to use the remaining budget.
- Common scenarios (budgets from $40M to $100M at no-vehicle cutoffs of 25, 30, 35 and
  40 percent, other settings at baseline) load instantly from a precomputed library.
  Any setting that has been run before also returns instantly.

## Feasible settings only

The budget slider starts at $38M and cannot go below the smallest budget for which a feasible plan is
known under the applied settings. That minimum comes from precomputed minimum-cost
portfolios (one for each set of walking-equity ZIP codes and coverage target),
repriced at the chosen costs. If a change to the costs, coverage target or cutoff
raises the minimum, the budget is lifted to it automatically. Costs and impact
coefficients are limited to the ranges tested in the sensitivity analysis.

## Rebuilding the data

```
pip install geopandas pyogrio shapely
python tools/prepare_data.py path/to/phase1_baseline.pkl
python tools/precompute.py floors  path/to/phase1_baseline.pkl outputs/precomputed
python tools/precompute.py library path/to/phase1_baseline.pkl outputs/precomputed outputs/baseline_results.xlsx
```

## Funding

This study was partially funded by the ACHIEVE GreatER grant (National Institute on
Minority Health and Health Disparities, award 1P50MD017351-01) through the
NIMHD/Health Equity Action Network to support research on optimizing food access and
advancing cardiovascular health equity in Detroit.
