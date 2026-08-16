# Detroit Food Access Optimization Dashboard

Interactive companion to the paper *A Spatial Optimization Framework for Equitable
Healthy Food Access Investment: Application to Detroit*. The app has four tabs:
a food access explorer, a live optimization model, a precomputed sensitivity
analysis, and documentation.

This folder is a self contained, deploy ready repository. Every data file the app
reads sits alongside `app.py`, so no Google Drive or Colab is required.

## What is here

```
app.py                                  application entry point
requirements.txt                        pinned Python dependencies
packages.txt                            system packages (intentionally empty)
.streamlit/config.toml                  server/theme settings
zip_codes.shp/.shx/.dbf/.prj/.cpg/.xml  ZIP boundary shapefile
final_detroit_food_health_dataset.xlsx  core ZIP dataset
need_index_by_zip.xlsx                  Need Index by ZIP
<seven>_Zip Code.xlsx                   the seven outlet layers
outputs/baseline_results.xlsx           precomputed baseline portfolio
outputs/sensitivity/phase1_baseline.pkl prebuilt model instance (~26 MB)
```

Total size is about 28 MB, which fits the free tier of both hosts below.

## Run locally

```
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (default http://localhost:8501).

## Deploy so journal readers can use it (Streamlit Community Cloud, free)

1. Create a new GitHub repository and push the entire contents of this folder to it.
   Keep the folder structure exactly as is; `outputs/sensitivity/phase1_baseline.pkl`
   must stay at that path.
2. Go to https://share.streamlit.io, sign in with GitHub, and click "New app."
3. Select your repository, branch `main`, and main file path `app.py`.
4. Click "Deploy." The first build takes several minutes while it installs geopandas.
5. You will get a permanent public URL of the form
   `https://<your-app>.streamlit.app`. Put that URL in the paper.

### Alternative: Hugging Face Spaces
Create a new Space, choose the "Streamlit" SDK, and upload these files (or link the
GitHub repo). Same result, a public URL.

## Make the link permanent for the paper (recommended)

A free host can sleep or change. Archive the exact code and data on Zenodo to get a
DOI that never breaks:

1. Sign in to https://zenodo.org with your GitHub account and enable the repository
   under Settings, then create a GitHub Release. Zenodo mints a DOI for that release.
2. Cite both in the paper: the live URL for interactive use and the Zenodo DOI as the
   permanent archive.

## Notes on the live optimization tab

The optimization tab solves a real MILP with HiGHS. A full city scale solve can take
several minutes and a large amount of memory, which is close to the ceiling of a free
host. The app already imposes a solver time limit and reports the achieved gap, so it
degrades gracefully, but for a public deployment keep the interactive time limit short
and the optimality gap relaxed. The definitive results in the paper come from an
offline solve at the full 0.5 percent gap; the app states this.

To disable live solving entirely on the public deployment (serving only the
precomputed baseline), replace the body of `solve_optimization(...)` in `app.py` with
an immediate `return None, "live-solving-disabled", 0.0`, or gate the solve button
behind a flag. The explorer, the precomputed baseline map, and the sensitivity tab all
work without any solving.

## Reproducibility note for reviewers

The model instance in `outputs/sensitivity/phase1_baseline.pkl` was built for Detroit's
32 ZIP codes (419 candidate sites, 2,706 demand subpoints). The baseline reference
median household income stored in the instance is $36,931.5; see the manuscript for the
value used in the reported cost calibration.
