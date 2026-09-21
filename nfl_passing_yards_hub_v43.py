"""NFL Passing Yards V43 — layered production presentation.

Presentation-only wrapper over frozen V42. It reuses V34's certified capture
pipeline and swaps only the final composition into the approved layered hub.
No projection, probability, identity, market, API, or sportsbook-influence
calculation is changed.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any

import streamlit as st
import nfl_passing_yards_hub_v16 as legacy_visual
import nfl_passing_yards_hub_v34 as composition
import nfl_passing_yards_hub_v35 as pre_compact
import nfl_passing_yards_hub_v36 as compact
import nfl_passing_yards_hub_v42 as prior

MODEL_VERSION = "NFL PASSING YARDS V43 • LAYERED PRODUCTION HUB"
FROZEN_PRIOR = "nfl_passing_yards_hub_v42"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_LAYERED_CSS = r"""
<style data-live-passing-layered-css="true">
.ks-live-py,.ks-live-py *{box-sizing:border-box}
.ks-live-py{color:#edf7ff;margin:8px 0 18px}
.kpass29-build{display:none!important}
.ks-live-py-head{position:relative;overflow:hidden;border:1px solid rgba(63,167,235,.34);
 border-radius:24px;padding:24px;background:
 radial-gradient(circle at 88% 0%,rgba(56,189,248,.18),transparent 32%),
 linear-gradient(135deg,#0a2034 0%,#071827 60%,#092631 100%);
 box-shadow:0 20px 60px rgba(0,0,0,.24)}
.ks-live-py-headrow{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}
.ks-live-py-kicker{color:#63c7ff;font-size:.62rem;font-weight:950;letter-spacing:.14em;text-transform:uppercase}
.ks-live-py-title{margin:5px 0 0;font-size:clamp(2rem,4vw,3.25rem);line-height:1;font-weight:950;letter-spacing:-.05em}
.ks-live-py-sub{max-width:720px;margin-top:10px;color:#95acc0;font-size:.8rem;line-height:1.55;font-weight:650}
.ks-live-py-badge{flex:0 0 auto;border:1px solid #2f765f;background:#0c2d25;color:#83efc3;border-radius:999px;padding:8px 11px;font-size:.58rem;font-weight:950;letter-spacing:.04em}
.ks-live-py-tabs{display:flex;gap:7px;overflow-x:auto;scrollbar-width:none;margin:14px 0 15px;padding:3px 1px}
.ks-live-py-tabs::-webkit-scrollbar{display:none}
.ks-live-py-tab{flex:0 0 auto;border:1px solid #214b68;background:#091c2b;color:#82a5bd;border-radius:11px;padding:9px 12px;font-size:.62rem;font-weight:900;text-decoration:none}
.ks-live-py-tab.active{border-color:#3596d6;color:#f4fbff;background:#0f3551}
.ks-live-py-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}
.ks-live-py-card{min-width:0;border:1px solid #1d4662;border-radius:20px;background:linear-gradient(145deg,#091a29,#07131f);overflow:hidden;box-shadow:0 14px 36px rgba(0,0,0,.2)}
.ks-live-py-cardhead{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 13px;border-bottom:1px solid #19354a}
.ks-live-py-cardhead b{font-size:.62rem;color:#8ed2ff;letter-spacing:.08em;text-transform:uppercase}
.ks-live-py-cardbody{padding:12px}
.ks-live-py-result{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}
.ks-live-py-panel{min-width:0;border:1px solid #263f53;border-radius:13px;background:#081521;padding:9px}
.ks-live-py-panel strong{display:block;color:#d8edfb;font-size:.57rem;margin-bottom:6px;text-transform:uppercase;letter-spacing:.055em}
.ks-live-py-previews{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:10px}
.ks-live-py-preview{min-width:0;border:1px solid #233f53;border-radius:12px;background:#081521;padding:9px}
.ks-live-py-preview b{display:block;color:#eff8ff;font-size:.57rem;margin-bottom:5px}
.ks-live-py-preview span{color:#6f8da2;font-size:.48rem;line-height:1.35}
.ks-live-py-deep{margin-top:9px}
.ks-live-py-deep summary{cursor:pointer;color:#79c8f6;font-size:.55rem;font-weight:900}
.ks-live-py-deepbody{margin-top:7px}
@media(max-width:820px){.ks-live-py-grid{grid-template-columns:1fr}.ks-live-py-headrow{flex-direction:column}.ks-live-py-result{grid-template-columns:1fr 1fr}}
@media(max-width:520px){.ks-live-py-head{padding:17px;border-radius:18px}.ks-live-py-result,.ks-live-py-previews{grid-template-columns:1fr}.ks-live-py-title{font-size:2rem}.ks-live-py-tab{min-height:40px;display:inline-flex;align-items:center}}
</style>
"""

def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""

def _preview(title: str, subtitle: str, content: str) -> str:
    return (
        '<div class="ks-live-py-preview">'
        f'<b>{escape(title)}</b><span>{escape(subtitle)}</span>'
        f'<details class="ks-live-py-deep"><summary>Open Full Breakdown →</summary>'
        f'<div class="ks-live-py-deepbody">{content or "<div>Unavailable</div>"}</div></details>'
        '</div>'
    )

def _player(captured: dict[str, list[str]], index: int) -> str:
    identity = _piece(captured, "identity", index)
    projection = _piece(captured, "projection", index)
    market = _piece(captured, "market", index)
    profile = _piece(captured, "profile", index)
    defense = _piece(captured, "defense", index)
    pressure = _piece(captured, "pressure", index)
    personnel = _piece(captured, "personnel", index)
    environment = _piece(captured, "environment", index)
    context = _piece(captured, "context", index)
    distribution = _piece(captured, "distribution", index)

    return "".join([
        f'<article class="ks-live-py-card" data-live-qb-card="{index}">',
        '<div class="ks-live-py-cardhead"><b>Quarterback Analysis</b><span class="ks-live-py-badge">LIVE CERTIFIED DATA</span></div>',
        '<div class="ks-live-py-cardbody">',
        identity or '<div>Quarterback identity unavailable.</div>',
        '<div class="ks-live-py-result">',
        '<section class="ks-live-py-panel"><strong>Monster Projection</strong>', projection or '<div>Unavailable</div>', '</section>',
        '<section class="ks-live-py-panel"><strong>Market + Edge</strong>', market or '<div>Unavailable</div>', '</section>',
        '</div>',
        '<div class="ks-live-py-previews">',
        _preview("Why", "Profile + matchup drivers", (profile or "") + (defense or "")),
        _preview("Trends", "Pressure + personnel + environment", (pressure or "") + (personnel or "") + (environment or "")),
        _preview("Deep Data", "Context + distribution", (context or "") + (distribution or "")),
        '</div></div></article>',
    ])

def _layered_player_cards_html(captured: dict[str, list[str]]) -> str:
    return (
        _LAYERED_CSS
        + '<section class="ks-live-py" data-live-passing-layered="true">'
        + '<header class="ks-live-py-head"><div class="ks-live-py-headrow"><div>'
        + '<div class="ks-live-py-kicker">NFL PLAYER PROPS</div>'
        + '<h1 class="ks-live-py-title">Passing Yards</h1>'
        + '<div class="ks-live-py-sub">Live quarterback projection hub using the existing certified Passing Yards model, identity, matchup, probability, and market outputs.</div>'
        + '</div><span class="ks-live-py-badge">LIVE DATA • MODEL FROZEN</span></div></header>'
        + '<nav class="ks-live-py-tabs" aria-label="Passing Yards analysis layers">'
        + '<a class="ks-live-py-tab active" href="#py-overview">Overview</a>'
        + '<a class="ks-live-py-tab" href="#py-why">Why</a>'
        + '<a class="ks-live-py-tab" href="#py-matchup">Matchup</a>'
        + '<a class="ks-live-py-tab" href="#py-trends">Trends</a>'
        + '<a class="ks-live-py-tab" href="#py-market">Market</a>'
        + '<a class="ks-live-py-tab" href="#py-deep">Deep Data</a></nav>'
        + '<div class="ks-live-py-grid" id="py-overview">'
        + _player(captured, 0) + _player(captured, 1)
        + '</div></section>'
    )

def _no_legacy_banner() -> str:
    return ""


_STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)


def _style_blocks_only(body: Any) -> tuple[str, ...]:
    """Preserve CSS from the frozen renderer while suppressing its visible markup."""
    if not isinstance(body, str):
        return ()
    return tuple(_STYLE_BLOCK_RE.findall(body))


def render_nfl_passing_yards_hub() -> None:
    """Capture the frozen live data pipeline but replace its visible page composition."""
    original_cards = composition._combined_player_cards_html
    original_banner = composition._visual_build_banner_v34
    original_markdown = st.markdown
    original_matchup_html = legacy_visual._matchup_html
    original_why_html = legacy_visual._why_html
    original_compact_render = compact.render_nfl_passing_yards_hub

    def capture_only_markdown(body: Any, *args: Any, **kwargs: Any):
        # V34/V42 must still execute so their certified data, selectors, and model
        # pipeline remain intact. Only their legacy visible markdown is suppressed.
        # Any CSS embedded in those calls is preserved for the captured card HTML.
        for style in _style_blocks_only(body):
            original_markdown(style, unsafe_allow_html=True)
        return None

    legacy_visual._matchup_html = lambda *args, **kwargs: ""
    legacy_visual._why_html = lambda *args, **kwargs: ""
    composition._combined_player_cards_html = _layered_player_cards_html
    composition._visual_build_banner_v34 = _no_legacy_banner
    compact.render_nfl_passing_yards_hub = pre_compact.render_nfl_passing_yards_hub
    st.markdown = capture_only_markdown
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        st.markdown = original_markdown
        legacy_visual._matchup_html = original_matchup_html
        legacy_visual._why_html = original_why_html
        compact.render_nfl_passing_yards_hub = original_compact_render
        composition._combined_player_cards_html = original_cards
        composition._visual_build_banner_v34 = original_banner

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V43 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY","FROZEN_PRIOR","MODEL_VERSION","SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED","_layered_player_cards_html","render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
