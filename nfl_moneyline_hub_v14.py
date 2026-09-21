"""NFL Moneyline V14 — visual upgrade Step 1: compact top controls.

Presentation-only wrapper over frozen V13. This revision tightens the first
screen, replaces the legacy hero copy with a compact command header, and
polishes the existing slate-date control without changing its key, value, date
sync, engine execution, matchup set, model math, market semantics, or grading.

Frozen V12/V11/V10/V9/V8 analytical ownership remains authoritative.
"""
from __future__ import annotations

from typing import Any, Callable

import nfl_moneyline_hub_v9 as presentation
import nfl_moneyline_hub_v13 as prior

MODEL_VERSION = "NFL MONEYLINE V14 • VISUAL STEP 1 • COMPACT TOP CONTROL"
FROZEN_PRIOR = "nfl_moneyline_hub_v13"
FROZEN_PRESENTATION = "nfl_moneyline_hub_v9"
VISUAL_UPGRADE_STEP = 1
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000

_STEP1_CSS = r"""
<style data-nfl-moneyline-visual-step="1">
.kml9-page{max-width:1240px!important}
.kml9-hero{
  margin:.2rem 0 .58rem!important;
  padding:.82rem .95rem!important;
  border-radius:16px!important;
  border:1px solid rgba(88,201,255,.22)!important;
  background:radial-gradient(circle at 92% 4%,rgba(88,201,255,.11),transparent 28%),
             linear-gradient(145deg,#091522,#07111a)!important;
  box-shadow:0 12px 34px rgba(0,0,0,.18),0 0 22px rgba(46,168,255,.05)!important;
}
.kml9-title{
  font-size:clamp(1.16rem,2vw,1.55rem)!important;
  line-height:1.08!important;
  letter-spacing:-.025em!important;
}
.kml9-sub{
  max-width:860px!important;
  margin-top:.28rem!important;
  font-size:.66rem!important;
  line-height:1.4!important;
}
.kml9-chips{margin-top:.6rem!important;gap:5px!important}
.kml9-chip{padding:3px 7px!important;font-size:.48rem!important;letter-spacing:.025em!important}
[data-testid="stElementContainer"]:has([data-testid="stDateInput"]){
  margin:.08rem 0 .62rem!important;
  padding:.66rem .78rem .72rem!important;
  border:1px solid rgba(88,201,255,.18)!important;
  border-radius:14px!important;
  background:linear-gradient(145deg,rgba(10,25,39,.97),rgba(7,17,27,.97))!important;
  box-shadow:0 10px 28px rgba(0,0,0,.14)!important;
}
[data-testid="stElementContainer"]:has([data-testid="stDateInput"])::before{
  content:"SLATE CONTROL";
  display:block;
  margin:0 0 .36rem;
  color:#58c9ff;
  font-size:.56rem;
  line-height:1;
  font-weight:950;
  letter-spacing:.11em;
}
[data-testid="stDateInput"] label{
  color:#c7ecff!important;
  font-size:.66rem!important;
  font-weight:850!important;
}
[data-testid="stDateInput"] [data-baseweb="input"]{
  min-height:44px!important;
  border-radius:11px!important;
  border-color:rgba(88,201,255,.18)!important;
  background:#081522!important;
}
.kml9-summary{margin:.48rem 0 .68rem!important;gap:7px!important}
.kml9-summary>div{
  padding:8px 9px!important;
  border-color:rgba(88,201,255,.16)!important;
  background:rgba(7,18,29,.94)!important;
}
[data-testid="stAppViewContainer"] .main .block-container{padding-top:1rem!important}
[data-testid="stAppViewContainer"] .main .block-container > [data-testid="stVerticalBlock"]{
  gap:.66rem!important;
}
@media(max-width:620px){
  .kml9-hero{padding:.72rem!important;border-radius:14px!important}
  [data-testid="stElementContainer"]:has([data-testid="stDateInput"]){
    padding:.58rem!important;border-radius:12px!important
  }
}
</style>
"""

_COMPACT_HERO = (
    '<div class="kml9-page"><div class="kml9-hero">'
    '<div class="kml9-title">💰 NFL Moneyline <span>Command Center</span></div>'
    '<div class="kml9-sub">Verified pregame slate • calibrated win probability • '
    'live market comparison • 5M Monte Carlo • edge/EV • frozen final grading.</div>'
    '<div class="kml9-chips">'
    '<span class="kml9-chip">PREGAME VERIFIED</span>'
    '<span class="kml9-chip">MODEL / MARKET FIREWALL</span>'
    '<span class="kml9-chip">5M MONTE CARLO</span>'
    '<span class="kml9-chip">STAKE SIZING OFF</span>'
    '</div></div></div>'
)

def _step1_css(base: str) -> str:
    return str(base or "") + _STEP1_CSS

def _markdown_proxy(original: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(body: Any, *args: Any, **kwargs: Any):
        text = str(body or "")
        if "kml9-hero" in text and "NFL Moneyline" in text and "kml9-title" in text:
            body = _COMPACT_HERO
        return original(body, *args, **kwargs)
    return wrapped

def _date_input_proxy(original: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(label: Any, *args: Any, **kwargs: Any):
        if str(label) == "📅 Moneyline slate date":
            label = "Slate date"
            kwargs.setdefault("help", "Choose the verified NFL pregame slate.")
        return original(label, *args, **kwargs)
    return wrapped

def render_nfl_hub(market: str = "Moneyline"):
    if str(market or "Moneyline") != "Moneyline":
        raise RuntimeError("Moneyline V14 direct handler is Moneyline only.")

    original_css = presentation._CSS
    original_markdown = presentation.st.markdown
    original_date_input = presentation.st.date_input

    presentation._CSS = _step1_css(original_css)
    presentation.st.markdown = _markdown_proxy(original_markdown)
    presentation.st.date_input = _date_input_proxy(original_date_input)
    try:
        return prior.render_nfl_hub(market)
    finally:
        presentation.st.date_input = original_date_input
        presentation.st.markdown = original_markdown
        presentation._CSS = original_css

__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRESENTATION",
    "FROZEN_PRIOR",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "MONTE_CARLO_SIMULATIONS",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_UPGRADE_STEP",
    "_date_input_proxy",
    "_markdown_proxy",
    "_step1_css",
    "render_nfl_hub",
]
