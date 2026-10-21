"""Visual identity for the dashboard: palette, type, Plotly template, CSS."""
import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------- palette
INK = "#1D2B36"        # text and primary lines
SLATE = "#56636D"      # secondary text
LINE = "#DCE3E1"       # rules and borders
PAPER = "#F4F6F5"      # page background
SURFACE = "#FFFFFF"    # panels
TEAL = "#0E6E73"       # primary accent (actions, focus)
OCHRE = "#B7791F"      # need and attention
TEAL_SOFT = "#E3F0EF"

# Okabe-Ito based, colorblind safe. Interventions.
TYPES = ["grocery_new", "grocery_upgrade", "farmers_new", "farmers_upgrade", "mobile_market"]
TYPE_NAME = {
    "grocery_new": "New grocery store",
    "grocery_upgrade": "Grocery upgrade",
    "farmers_new": "New farmers market",
    "farmers_upgrade": "Farmers market upgrade",
    "mobile_market": "Mobile market",
}
TYPE_SHORT = {"grocery_new": "NG", "grocery_upgrade": "UG", "farmers_new": "NF",
              "farmers_upgrade": "UF", "mobile_market": "M"}
TYPE_COLOR = {
    "grocery_new": "#0072B2",
    "grocery_upgrade": "#56B4E9",
    "farmers_new": "#009E73",
    "farmers_upgrade": "#E69F00",
    "mobile_market": "#CC79A7",
}

# Existing outlets: cool hues for healthful sources, warm hues for less healthful.
OUTLETS = ["Grocery Store", "Farmers Market", "Food Pantry", "SNAP Retailer",
           "Gas Station", "Liquor Store", "Restaurant"]
OUTLET_COLOR = {
    "Grocery Store": "#009E73",
    "Farmers Market": "#3A9D3A",
    "Food Pantry": "#0072B2",
    "SNAP Retailer": "#56B4E9",
    "Gas Station": "#E69F00",
    "Liquor Store": "#D55E00",
    "Restaurant": "#CC79A7",
}

# Sequential scale for ZIP shading (light to deep), colorblind friendly.
SEQ = ["#F7F4EA", "#EAD9A6", "#D9B562", "#B7791F", "#7E4E12", "#4A2C08"]


def hex_rgb(h, a=255):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [a]


def seq_color(t, alpha=170):
    """t in [0,1] -> RGBA on the sequential ramp."""
    t = 0.0 if t != t else max(0.0, min(1.0, float(t)))
    pos = t * (len(SEQ) - 1)
    i = min(int(pos), len(SEQ) - 2)
    f = pos - i
    a = hex_rgb(SEQ[i]); b = hex_rgb(SEQ[i + 1])
    return [round(a[c] + (b[c] - a[c]) * f) for c in range(3)] + [alpha]


# ---------------------------------------------------------------- plotly
FONT = "Public Sans, Segoe UI, Helvetica Neue, Arial, sans-serif"
pio.templates["detroit"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family=FONT, size=13, color=INK),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=[TYPE_COLOR[t] for t in TYPES],
        xaxis=dict(gridcolor="#E7ECEA", zerolinecolor=LINE, linecolor=LINE, ticks="", title_font=dict(size=12, color=SLATE)),
        yaxis=dict(gridcolor="#E7ECEA", zerolinecolor=LINE, linecolor=LINE, ticks="", title_font=dict(size=12, color=SLATE)),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=LINE, font=dict(family=FONT, color=INK, size=12)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        margin=dict(l=10, r=10, t=30, b=10),
    )
)
pio.templates.default = "detroit"

# ---------------------------------------------------------------- CSS
_CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select {{
  font-family: 'Public Sans', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif !important;
  font-variant-numeric: tabular-nums;
}}
.stApp {{ background: {PAPER}; }}
.block-container {{ padding-top: 1.6rem !important; padding-bottom: 2rem !important; max-width: 1480px; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display: none; }}
#MainMenu, footer {{ visibility: hidden; }}
h1, h2, h3, h4 {{ color: {INK}; letter-spacing: -0.01em; }}
h3 {{ font-size: 1.15rem !important; font-weight: 700 !important; margin: 0.4rem 0 0.2rem 0 !important; }}
h4 {{ font-size: 1.0rem !important; font-weight: 700 !important; }}
p, li {{ color: {INK}; }}

/* masthead */
.mast {{ display:flex; justify-content:space-between; align-items:flex-end; gap:24px;
        border-bottom: 3px solid {INK}; padding-bottom: 14px; margin-bottom: 6px; flex-wrap: wrap; }}
.mast h1 {{ font-size: 2.05rem; font-weight: 800; margin: 0; line-height: 1.05; }}
.mast .sub {{ color: {SLATE}; font-size: 0.98rem; margin-top: 6px; max-width: 760px; }}
.mast .org {{ color: {SLATE}; font-size: 0.85rem; text-align: right; line-height: 1.45; }}

/* tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 2px; border-bottom: 1px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{ height: 46px; padding: 0 20px; font-weight: 600; font-size: 0.95rem; color: {SLATE}; background: transparent; }}
.stTabs [aria-selected="true"] {{ color: {INK} !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: {TEAL}; height: 3px; }}

/* lead statement on the landing tab */
.lead {{ display:grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 28px; align-items: center;
        background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px; padding: 22px 26px; margin: 14px 0 18px 0; }}
.lead .big {{ font-size: 4.2rem; font-weight: 800; color: {TEAL}; line-height: 0.95; letter-spacing: -0.03em; }}
.lead .say {{ font-size: 1.22rem; font-weight: 600; line-height: 1.35; margin-top: 8px; max-width: 34ch; }}
.lead .note {{ color: {SLATE}; font-size: 0.82rem; margin-top: 10px; max-width: 60ch; }}
.facts {{ display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 0; border-left: 1px solid {LINE}; }}
.fact {{ padding: 10px 18px; border-bottom: 1px solid {LINE}; }}
.fact:nth-last-child(-n+2) {{ border-bottom: none; }}
.fact .v {{ font-size: 1.55rem; font-weight: 700; color: {INK}; line-height: 1.1; }}
.fact .k {{ font-size: 0.82rem; color: {SLATE}; margin-top: 2px; line-height: 1.3; }}
@media (max-width: 900px) {{ .lead {{ grid-template-columns: 1fr; }} .facts {{ border-left: none; border-top: 1px solid {LINE}; }} .lead .big {{ font-size: 3.2rem; }} }}

/* panels */
.panel {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px; padding: 16px 18px; }}
.panel h4 {{ margin: 0 0 8px 0; }}
.muted {{ color: {SLATE}; font-size: 0.85rem; }}
.kv {{ display:flex; justify-content:space-between; gap: 12px; padding: 7px 0; border-bottom: 1px solid #EEF2F0; font-size: 0.92rem; }}
.kv:last-child {{ border-bottom: none; }}
.kv b {{ font-weight: 700; }}
.rankbar {{ height: 6px; background: #EEF2F0; border-radius: 3px; margin-top: 4px; overflow: hidden; }}
.rankbar span {{ display:block; height: 100%; background: {OCHRE}; }}

/* metrics row */
.metrics {{ display:grid; grid-template-columns: repeat(6, minmax(0,1fr)); background: {SURFACE};
           border: 1px solid {LINE}; border-radius: 10px; margin: 6px 0 14px 0; }}
.metric {{ padding: 12px 16px; border-right: 1px solid {LINE}; }}
.metric:last-child {{ border-right: none; }}
.metric .v {{ font-size: 1.45rem; font-weight: 700; color: {INK}; line-height: 1.15; }}
.metric .k {{ font-size: 0.8rem; color: {SLATE}; }}
@media (max-width: 1000px) {{ .metrics {{ grid-template-columns: repeat(2, minmax(0,1fr)); }} .metric {{ border-bottom: 1px solid {LINE}; }} }}

/* legend */
.legend {{ display:flex; flex-wrap:wrap; gap: 6px 16px; font-size: 0.82rem; color: {INK}; margin: 8px 2px 0 2px; }}
.legend i {{ display:inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 6px; vertical-align: -1px; }}
.legend .sq {{ border-radius: 2px; }}
.ramp {{ display:inline-block; width: 120px; height: 10px; border-radius: 2px; vertical-align: -1px; margin: 0 6px;
        background: linear-gradient(90deg, {", ".join(SEQ)}); }}

/* notices */
.note-box {{ border-left: 4px solid {TEAL}; background: {TEAL_SOFT}; padding: 10px 14px; border-radius: 4px; font-size: 0.9rem; color: {INK}; margin: 6px 0 10px 0; }}
.note-box.warn {{ border-left-color: {OCHRE}; background: #FBF3E4; }}
.note-box.bad {{ border-left-color: #B42318; background: #FDECEA; }}

/* forms and buttons */
[data-testid="stForm"] {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px; padding: 14px 16px 16px 16px; }}
.stButton button, [data-testid="stFormSubmitButton"] button, .stDownloadButton button {{
  border-radius: 6px; font-weight: 600; }}
[data-testid="stFormSubmitButton"] button {{ background: {TEAL}; color: #fff; border: 1px solid {TEAL}; width: 100%; height: 44px; }}
[data-testid="stFormSubmitButton"] button p {{ color: #fff !important; font-weight: 600; }}
[data-testid="stFormSubmitButton"] button:hover {{ background: #0B5A5E; border-color: #0B5A5E; color: #fff; }}
button:focus-visible, input:focus-visible {{ outline: 3px solid {TEAL} !important; outline-offset: 2px; }}
[data-testid="stExpander"] {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px; }}
[data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 8px; }}
.stPlotlyChart {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px; padding: 6px 6px 2px 6px; }}
[data-testid="stDeckGlJsonChart"] {{ border: 1px solid {LINE}; border-radius: 10px; overflow: hidden; }}
.cite {{ font-size: 0.9rem; background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px; padding: 12px 14px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}
</style>
"""

import re as _re
CSS = _re.sub(r"\n\s*\n", "\n", _CSS)
