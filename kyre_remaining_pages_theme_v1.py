"""Universal compatibility skin for all remaining active pages V1.

Rollout Step 4. CSS is scoped to one keyed Streamlit container so already
frozen Passing Yards, NFL Moneyline, and CFB Game Total presentations are not
restyled by this layer.
"""
from __future__ import annotations

from kyre_universal_components_v1 import build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

REMAINING_PAGES_THEME_VERSION = "KYRE REMAINING PAGES UNIVERSAL THEME V1 • BLACK + GLACIER BLUE"
REMAINING_PAGES_CONTAINER_KEY = "kyre_universal_remaining_pages"
REMAINING_PAGES_CONTAINER_CLASS = f"st-key-{REMAINING_PAGES_CONTAINER_KEY}"

EXCLUDED_FROZEN_ROUTES = frozenset({
    ("NFL", "Passing Yards"),
    ("NFL", "Moneyline"),
    ("CFB", "Game Total"),
})

def should_theme_route(sport: str, market: str) -> bool:
    sport = str(sport or "").strip().upper()
    market = str(market or "").strip()
    return bool(sport and market and (sport, market) not in EXCLUDED_FROZEN_ROUTES)

_COMPAT_CSS = f"""
<style data-kyre-remaining-pages-theme="v1">
.{REMAINING_PAGES_CONTAINER_CLASS} {{
  color:var(--kyre-text-primary);
  min-width:0;
  max-width:100%;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} h1,
.{REMAINING_PAGES_CONTAINER_CLASS} h2,
.{REMAINING_PAGES_CONTAINER_CLASS} h3,
.{REMAINING_PAGES_CONTAINER_CLASS} h4 {{
  color:var(--kyre-text-primary)!important;
  letter-spacing:-.025em;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} p,
.{REMAINING_PAGES_CONTAINER_CLASS} small,
.{REMAINING_PAGES_CONTAINER_CLASS} label {{
  color:var(--kyre-text-secondary);
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [data-testid="stMetric"] {{
  border:1px solid rgba(88,201,255,.16);
  border-radius:var(--kyre-radius-lg);
  background:linear-gradient(145deg,var(--kyre-surface-raised),var(--kyre-surface));
  box-shadow:var(--kyre-shadow-card);
  padding:12px 14px;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [data-testid="stMetricValue"] {{
  color:var(--kyre-text-primary)!important;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [data-testid="stMetricLabel"] {{
  color:var(--kyre-text-muted)!important;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} .stButton button,
.{REMAINING_PAGES_CONTAINER_CLASS} .stDownloadButton button {{
  min-height:40px;
  border:1px solid rgba(88,201,255,.24)!important;
  border-radius:var(--kyre-radius-md)!important;
  background:linear-gradient(145deg,rgba(31,174,255,.11),rgba(88,201,255,.04))!important;
  color:var(--kyre-glacier-soft)!important;
  box-shadow:var(--kyre-glow-soft)!important;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [data-baseweb="select"]>div,
.{REMAINING_PAGES_CONTAINER_CLASS} [data-baseweb="input"],
.{REMAINING_PAGES_CONTAINER_CLASS} [data-baseweb="textarea"] {{
  border-color:rgba(88,201,255,.18)!important;
  background:#08131d!important;
  color:var(--kyre-text-primary)!important;
  border-radius:var(--kyre-radius-md)!important;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [data-testid="stExpander"] {{
  border:1px solid rgba(88,201,255,.16)!important;
  border-radius:var(--kyre-radius-lg)!important;
  background:linear-gradient(145deg,var(--kyre-surface),#08111a)!important;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [data-testid="stDataFrame"],
.{REMAINING_PAGES_CONTAINER_CLASS} [data-testid="stTable"] {{
  border:1px solid rgba(88,201,255,.14);
  border-radius:var(--kyre-radius-lg);
  overflow:hidden;
  box-shadow:var(--kyre-shadow-card);
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [data-testid="stAlert"] {{
  border-radius:var(--kyre-radius-lg)!important;
  border-color:rgba(88,201,255,.18)!important;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [data-baseweb="tab-list"] {{
  gap:6px;
  border-bottom:1px solid rgba(88,201,255,.12);
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [data-baseweb="tab"] {{
  border-radius:var(--kyre-radius-md)!important;
  color:var(--kyre-text-secondary)!important;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [aria-selected="true"][data-baseweb="tab"] {{
  color:var(--kyre-glacier-soft)!important;
  background:rgba(31,174,255,.12)!important;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} hr {{
  border-color:rgba(88,201,255,.12)!important;
}}
/* Conservative legacy HTML compatibility: visual properties only. */
.{REMAINING_PAGES_CONTAINER_CLASS} [class*="hero"],
.{REMAINING_PAGES_CONTAINER_CLASS} [class*="panel"],
.{REMAINING_PAGES_CONTAINER_CLASS} [class*="card"],
.{REMAINING_PAGES_CONTAINER_CLASS} [class*="section"],
.{REMAINING_PAGES_CONTAINER_CLASS} [class*="summary"] {{
  border-color:rgba(88,201,255,.18)!important;
}}
.{REMAINING_PAGES_CONTAINER_CLASS} [class*="chip"],
.{REMAINING_PAGES_CONTAINER_CLASS} [class*="badge"],
.{REMAINING_PAGES_CONTAINER_CLASS} [class*="pill"] {{
  border-color:rgba(88,201,255,.24)!important;
}}
@media(max-width:720px) {{
  .{REMAINING_PAGES_CONTAINER_CLASS} .stButton button,
  .{REMAINING_PAGES_CONTAINER_CLASS} .stDownloadButton button {{
    min-height:44px;
  }}
  .{REMAINING_PAGES_CONTAINER_CLASS} [data-testid="stMetric"] {{
    padding:10px 11px;
  }}
}}
</style>
"""

def build_remaining_pages_theme_css() -> str:
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + _COMPAT_CSS
    )

__all__ = [
    "EXCLUDED_FROZEN_ROUTES",
    "REMAINING_PAGES_CONTAINER_CLASS",
    "REMAINING_PAGES_CONTAINER_KEY",
    "REMAINING_PAGES_THEME_VERSION",
    "build_remaining_pages_theme_css",
    "should_theme_route",
]
