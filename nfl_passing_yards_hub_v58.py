"""NFL Passing Yards V58 — quarterback drill-down selection screen.

First architecture step after the frozen V51-V57 visual rollout. V58 changes
only the presentation/navigation composition of the already-captured quarterback
payloads. The landing screen is a compact quarterback picker; the prior full
analysis board is not rendered there.

Projection, probability, market math, data providers, sportsbook influence,
widget keys, and the frozen V51-V57 product chain remain unchanged.
"""
from __future__ import annotations

from datetime import date
from html import escape
from urllib.parse import urlencode

import streamlit as st

import nfl_passing_yards_hub_v46 as controls
import nfl_passing_yards_hub_v48 as evidence
import nfl_passing_yards_hub_v57 as prior
from kyre_universal_components_v1 import build_badge, build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

MODEL_VERSION = "NFL PASSING YARDS V58 • QB DRILL-DOWN STEP 1"
FROZEN_PRIOR = "nfl_passing_yards_hub_v57"
DRILLDOWN_STEP = 1
SELECTION_SYSTEM_VERSION = "v58"
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_QB_SLOT_PARAM = "ks_qb_slot"
_DATE_PARAM = "ks_py_date"
_MATCHUP_PARAM = "ks_py_matchup"

_SELECTION_CSS = r"""
<style data-passing-yards-qb-selection="v58">
.ks-py58,.ks-py58 *{box-sizing:border-box}
.ks-py58{margin:.55rem 0 1.2rem;color:var(--kyre-sem-text-primary)}
.ks-py58-head{
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  margin-bottom:var(--kyre-space-4);padding:var(--kyre-space-4) var(--kyre-space-5);
  border:1px solid var(--kyre-sem-border-medium);border-radius:var(--kyre-sem-radius-card);
  background:linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)
}
.ks-py58-kicker{
  color:var(--kyre-sem-text-accent-soft);font-size:.64rem;font-weight:950;
  letter-spacing:.12em;text-transform:uppercase
}
.ks-py58-title{margin:.18rem 0 0;font-size:clamp(1.28rem,2.3vw,1.78rem);font-weight:950;line-height:1.08}
.ks-py58-sub{margin:.34rem 0 0;color:var(--kyre-sem-text-muted);font-size:.72rem;line-height:1.45}
.ks-py58-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--kyre-space-4)}
.ks-py58-cardlink{display:block;min-width:0;color:inherit!important;text-decoration:none!important}
.ks-py58-card{
  min-width:0;height:100%;padding:var(--kyre-space-4);
  border:1px solid var(--kyre-sem-border-medium);border-radius:var(--kyre-sem-radius-card);
  background:radial-gradient(circle at top right,var(--kyre-sem-accent-wash-soft),transparent 32%),
             linear-gradient(155deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
  box-shadow:var(--kyre-sem-shadow-card);
  transition:transform .14s ease,border-color .14s ease,box-shadow .14s ease
}
.ks-py58-cardlink:hover .ks-py58-card,
.ks-py58-cardlink:focus-visible .ks-py58-card{
  transform:translateY(-2px);border-color:var(--kyre-sem-border-strong);
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)
}
.ks-py58-slot{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  margin-bottom:var(--kyre-space-3);color:var(--kyre-sem-text-accent-soft);
  font-size:.59rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase
}
.ks-py58-identity .kpass29-card{
  margin:0!important;padding:0!important;border:0!important;background:transparent!important;
  box-shadow:none!important
}
.ks-py58-identity .kpass29-card:after,
.ks-py58-identity .kpass29-main,
.ks-py58-identity .kpass29-foot,
.ks-py58-identity .kpass29-badges{display:none!important}
.ks-py58-identity .kpass29-top{align-items:center!important}
.ks-py58-identity .kpass29-name{font-size:1.08rem!important}
.ks-py58-identity .kpass29-meta{white-space:normal!important;overflow:visible!important;text-overflow:clip!important}
.ks-py58-cta{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  margin-top:var(--kyre-space-4);padding:12px 14px;min-height:48px;
  border:1px solid var(--kyre-sem-border-strong);border-radius:var(--kyre-sem-radius-section);
  background:var(--kyre-sem-accent-wash-soft);color:var(--kyre-sem-text-accent-soft);
  font-size:.74rem;font-weight:950
}
.ks-py58-selected{
  padding:var(--kyre-space-4);border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-card);
  background:linear-gradient(155deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel))
}
.ks-py58-back{
  display:inline-flex;align-items:center;min-height:48px;margin-bottom:var(--kyre-space-4);
  padding:10px 14px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-section);color:var(--kyre-sem-text-accent-soft)!important;
  text-decoration:none!important;font-size:.72rem;font-weight:900
}
.ks-py58-selected-note{
  margin-top:var(--kyre-space-4);padding:var(--kyre-space-3);
  border:1px solid var(--kyre-sem-border-soft);border-radius:var(--kyre-sem-radius-section);
  color:var(--kyre-sem-text-muted);font-size:.72rem;line-height:1.5
}
@media(max-width:900px){.ks-py58-grid{grid-template-columns:1fr}}
@media(max-width:680px){
  .ks-py58-head{align-items:flex-start;flex-direction:column;padding:var(--kyre-space-4)}
  .ks-py58-card{padding:var(--kyre-space-3)}
  .ks-py58-cta{width:100%}
}
</style>
"""

def _param(name: str) -> str:
    value = st.query_params.get(name)
    if isinstance(value, list):
        value = value[-1] if value else ""
    return str(value or "").strip()

def _restore_context_from_query() -> None:
    raw_day = _param(_DATE_PARAM)
    if raw_day:
        try:
            parsed = date.fromisoformat(raw_day)
        except ValueError:
            parsed = None
        if parsed is not None:
            st.session_state[controls.rolling.V8_DATE_KEY] = parsed
            st.session_state[controls.TOP_DATE_KEY] = parsed

    matchup = _param(_MATCHUP_PARAM)
    if matchup:
        st.session_state[controls.rolling.V8_MATCHUP_KEY] = matchup
        st.session_state[controls.navigation.VISIBLE_MATCHUP_KEY] = matchup

def _current_nav_url(slot: int | None = None) -> str:
    params = {
        "ks_jump_sport": "NFL",
        "ks_jump_market": "Passing Yards",
    }
    current_day = (
        st.session_state.get(controls.TOP_DATE_KEY)
        or st.session_state.get(controls.rolling.V8_DATE_KEY)
    )
    if hasattr(current_day, "isoformat"):
        params[_DATE_PARAM] = current_day.isoformat()

    matchup = (
        st.session_state.get(controls.navigation.VISIBLE_MATCHUP_KEY)
        or st.session_state.get(controls.rolling.V8_MATCHUP_KEY)
    )
    if matchup:
        params[_MATCHUP_PARAM] = str(matchup)
    if slot is not None:
        params[_QB_SLOT_PARAM] = str(slot)
    return "?" + urlencode(params)

def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""

def _selection_card(captured: dict[str, list[str]], index: int) -> str:
    identity = _piece(captured, "identity", index) or "<div>Quarterback identity unavailable.</div>"
    href = escape(_current_nav_url(index + 1), quote=True)
    return (
        f'<a class="ks-py58-cardlink" data-qb-select="{index + 1}" href="{href}">'
        f'<article class="ks-py58-card" data-qb-selection-card="{index + 1}">'
        '<div class="ks-py58-slot"><span>Quarterback</span>'
        + build_badge("VIEW PLAYER", tone="success")
        + '</div>'
        '<div class="ks-py58-identity">'
        + identity
        + '</div>'
        '<div class="ks-py58-cta"><span>View Analysis</span><span aria-hidden="true">→</span></div>'
        '</article></a>'
    )

def _selection_screen(captured: dict[str, list[str]]) -> str:
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + _SELECTION_CSS
        + '<section class="ks-py58" data-passing-yards-selection-screen="v58">'
        + '<header class="ks-py58-head"><div>'
        + '<div class="ks-py58-kicker">PASSING YARDS • QUARTERBACKS</div>'
        + '<h2 class="ks-py58-title">Choose a quarterback</h2>'
        + '<p class="ks-py58-sub">Tap a player to open a focused quarterback workspace. Full analysis is no longer dumped onto the matchup screen.</p>'
        + '</div>'
        + build_badge("2 QB • SELECT", tone="success")
        + '</header>'
        + '<div class="ks-py58-grid">'
        + _selection_card(captured, 0)
        + _selection_card(captured, 1)
        + '</div></section>'
    )

def _selected_shell(captured: dict[str, list[str]], slot: int) -> str:
    index = slot - 1
    identity = _piece(captured, "identity", index) or "<div>Quarterback identity unavailable.</div>"
    back = escape(_current_nav_url(None), quote=True)
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + _SELECTION_CSS
        + '<section class="ks-py58" data-passing-yards-selected-qb="'
        + str(slot)
        + '">'
        + f'<a class="ks-py58-back" data-qb-back="true" href="{back}">← Back to Quarterbacks</a>'
        + '<div class="ks-py58-selected">'
        + '<div class="ks-py58-kicker">SELECTED QUARTERBACK</div>'
        + '<div class="ks-py58-identity">'
        + identity
        + '</div>'
        + '<div class="ks-py58-selected-note">Quarterback workspace selected. The detailed player analysis layer attaches here in Drill-Down Step 2.</div>'
        + '</div></section>'
    )

def _qb_drilldown_html(captured: dict[str, list[str]]) -> str:
    raw = _param(_QB_SLOT_PARAM)
    if raw in {"1", "2"}:
        return _selected_shell(captured, int(raw))
    return _selection_screen(captured)

def render_nfl_passing_yards_hub() -> None:
    _restore_context_from_query()
    st.markdown(_SELECTION_CSS, unsafe_allow_html=True)
    original_builder = evidence._steps_7_9_command_center_html
    evidence._steps_7_9_command_center_html = _qb_drilldown_html
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        evidence._steps_7_9_command_center_html = original_builder

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V58 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "DRILLDOWN_STEP",
    "FROZEN_PRIOR",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SELECTION_SYSTEM_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_qb_drilldown_html",
    "_selection_screen",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
