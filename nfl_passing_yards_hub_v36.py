"""NFL Passing Yards V36 — compact dashboard presentation layer.

Additive UI-only wrapper over certified V35. V36 recomposes only already-rendered
certified presentation evidence from V34 into a cleaner customer-facing dashboard.
It does not recalculate, mutate, or replace Passing Yards analytical owners.

Frozen:
- V35 production transport + caption cleanup;
- V34 capture of certified identity/profile/defense/pressure/personnel/environment/
  projection/context/distribution/market HTML;
- V33/V28 analytical values and fail-closed rules;
- exact ESPN team-logo / QB-headshot identity contracts;
- sportsbook projection influence = 0.0%;
- stake sizing OFF.
"""
from __future__ import annotations

from html import escape
import re
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v34 as composition
import nfl_passing_yards_hub_v35 as prior


MODEL_VERSION = "NFL PASSING YARDS V36 • COMPACT DASHBOARD"
FROZEN_PRIOR = "nfl_passing_yards_hub_v35"
FROZEN_PASSING_ENGINE = "nfl_passing_yards_hub_v28"
COMPACT_DASHBOARD_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False


_COMPACT_DASHBOARD_CSS = r"""
<style>
/* V36 is presentation-only. Keep the old certification/build banner in the
   source chain but remove it from the customer-facing scan path. */
.kpass29-build{display:none!important}

.monster-pass-dashboard{width:100%;max-width:1180px;margin:0 auto 14px}
.monster-matchup-header{display:grid;grid-template-columns:58px minmax(0,1fr) 58px;align-items:center;gap:12px;border:1px solid #334155;border-radius:18px;background:linear-gradient(145deg,#101722,#0b111a);padding:12px 14px;margin:4px 0 12px;box-shadow:0 12px 28px rgba(0,0,0,.16)}
.monster-matchup-logo{width:54px;height:54px;border:1px solid #334155;border-radius:14px;background:#0b1118;padding:7px;box-sizing:border-box;display:flex;align-items:center;justify-content:center}
.monster-matchup-logo img{width:100%;height:100%;object-fit:contain;display:block}
.monster-matchup-center{text-align:center;min-width:0}.monster-matchup-kicker{color:#a78bfa;font-size:.48rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase}.monster-matchup-title{color:#f8fafc;font-size:1.02rem;font-weight:950;line-height:1.2;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.monster-matchup-time{color:#93a4b8;font-size:.55rem;font-weight:750;margin-top:4px}

.monster-qb-hero-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.monster-qb-hero{min-width:0;border:1px solid #344256;border-radius:18px;background:linear-gradient(150deg,#101722 0%,#0b1119 72%,#121526 100%);padding:12px;box-shadow:0 12px 28px rgba(0,0,0,.14)}
.monster-qb-hero .kpass29-top{gap:10px}.monster-qb-hero .kpass29-head{border-color:#46556a;background:#0a1018}.monster-qb-hero .kpass29-logo{border-color:#46556a;background:#0a1018}.monster-qb-hero .kpass29-name{font-size:.96rem}.monster-qb-hero .kpass29-meta{font-size:.55rem;color:#93a4b8}.monster-qb-hero .kpass29-badge{border-color:#435269;background:#111827;color:#c7d2e2}.monster-qb-hero .kpass29-main,.monster-qb-hero .kpass29-foot{display:none!important}
.monster-hero-divider{height:1px;background:#253245;margin:10px 0}
.monster-hero-label{display:flex;align-items:center;justify-content:space-between;gap:8px;color:#8999ad;font-size:.45rem;font-weight:950;letter-spacing:.10em;text-transform:uppercase;margin-bottom:6px}.monster-hero-label strong{color:#c4b5fd;font-size:.48rem}
.monster-qb-hero .kpy-projhero{display:block!important;margin:0}.monster-qb-hero .kpy-projhero>div{display:none!important}.monster-qb-hero .kpy-projhero>div:first-child{display:block!important;border:1px solid #5b4b89!important;background:#161329!important;border-radius:11px!important;padding:9px 10px!important}.monster-qb-hero .kpy-projhero b{font-size:1.28rem!important;color:#f4f0ff!important}.monster-qb-hero .kpy-projhero span{color:#a89bc8!important}
.monster-qb-hero .kpy10-hero{grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:6px!important;margin:7px 0 0!important}.monster-qb-hero .kpy10-hero>div{border-color:#304258!important;background:#0d1622!important;border-radius:10px!important;padding:8px!important}.monster-qb-hero .kpy10-hero b{font-size:.88rem!important}.monster-qb-hero .kpy10-hero span{color:#8495aa!important}
.monster-qb-hero .kpy10-metrics{display:block!important;margin-top:6px}.monster-qb-hero .kpy10-metrics>div{display:none!important}.monster-qb-hero .kpy10-metrics>div:nth-child(5){display:block!important;border:1px solid #304258!important;background:#0d1622!important;border-radius:10px!important;padding:8px!important;color:#8495aa!important}.monster-qb-hero .kpy10-metrics>div:nth-child(5) b{font-size:.78rem!important;color:#f1f5f9!important}
.monster-empty{border:1px dashed #475569;border-radius:11px;padding:9px;color:#94a3b8;font-size:.55rem;background:#0c131d}

/* Stable hooks reserved for the next approved presentation steps. */
.monster-why-projection{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.65rem}
.monster-deep-evidence{width:100%}

@media(max-width:760px){
  .monster-matchup-header{grid-template-columns:44px minmax(0,1fr) 44px;padding:10px;gap:8px}.monster-matchup-logo{width:42px;height:42px;border-radius:11px;padding:5px}.monster-matchup-title{font-size:.86rem}.monster-matchup-time{font-size:.49rem}
  .monster-qb-hero-grid,.monster-why-projection{grid-template-columns:1fr}.monster-qb-hero{padding:10px}.monster-qb-hero .kpy10-hero{grid-template-columns:repeat(3,minmax(0,1fr))!important}
}
</style>
"""

_LOGO_RE = re.compile(r'<img\b[^>]*class="kpass29-logo"[^>]*>', re.IGNORECASE)


def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    return rows[index] if 0 <= index < len(rows) else ""


def _extract_one(body: str, tag: str, class_name: str) -> str:
    rows = composition._extract_elements_by_class(body, tag, class_name)
    return rows[0] if rows else ""


def _logo_from_identity(identity_html: str) -> str:
    match = _LOGO_RE.search(str(identity_html or ""))
    return match.group(0) if match else ""


def _matchup_header_html(captured: dict[str, list[str]]) -> str:
    """Build a customer header from already-selected matchup display state."""
    selected = str(st.session_state.get("nfl_passing_yards_v8_matchup") or "Verified NFL Matchup").strip()
    matchup, sep, clock = selected.partition("•")
    identity_left = _piece(captured, "identity", 0)
    identity_right = _piece(captured, "identity", 1)
    left_logo = _logo_from_identity(identity_left)
    right_logo = _logo_from_identity(identity_right)
    return (
        '<section class="monster-matchup-header">'
        f'<div class="monster-matchup-logo">{left_logo}</div>'
        '<div class="monster-matchup-center">'
        '<div class="monster-matchup-kicker">NFL • Passing Yards</div>'
        f'<div class="monster-matchup-title">{escape(matchup.strip() or "Verified NFL Matchup")}</div>'
        f'<div class="monster-matchup-time">{escape(clock.strip() if sep else "Verified matchup")}</div>'
        '</div>'
        f'<div class="monster-matchup-logo">{right_logo}</div>'
        '</section>'
    )


def _qb_hero_card_html(captured: dict[str, list[str]], index: int) -> str:
    """Recompose certified rendered identity/projection/market values only."""
    identity = _piece(captured, "identity", index)
    projection = _piece(captured, "projection", index)
    market = _piece(captured, "market", index)

    identity_top = _extract_one(identity, "div", "kpass29-top") or '<div class="monster-empty">Verified quarterback identity unavailable.</div>'
    projection_hero = _extract_one(projection, "div", "kpy-projhero") or '<div class="monster-empty">Monster projection unavailable.</div>'
    market_hero = _extract_one(market, "div", "kpy10-hero") or '<div class="monster-empty">Verified market line unavailable.</div>'
    market_metrics = _extract_one(market, "div", "kpy10-metrics") or '<div class="monster-empty">Market edge unavailable.</div>'

    return (
        f'<article class="monster-qb-hero" data-qb-index="{index}">'
        f'{identity_top}'
        '<div class="monster-hero-divider"></div>'
        '<div class="monster-hero-label"><span>Model read</span><strong>MONSTER PROJECTION</strong></div>'
        f'{projection_hero}'
        f'{market_hero}'
        f'{market_metrics}'
        '</article>'
    )


def _compact_dashboard_html(captured: dict[str, list[str]]) -> str:
    """Compose the V36 scan-first header + two QB heroes from certified HTML."""
    return (
        '<div class="monster-pass-dashboard">'
        f'{_matchup_header_html(captured)}'
        '<div class="monster-qb-hero-grid">'
        f'{_qb_hero_card_html(captured, 0)}'
        f'{_qb_hero_card_html(captured, 1)}'
        '</div>'
        '</div>'
    )


def _install_compact_dashboard_shell(streamlit_module: Any = st) -> None:
    """Install presentation-only V36 CSS; no data or model mutation occurs."""
    streamlit_module.markdown(_COMPACT_DASHBOARD_CSS, unsafe_allow_html=True)


def render_nfl_passing_yards_hub() -> None:
    """Render V35 while temporarily swapping only V34's final HTML composer."""
    _install_compact_dashboard_shell()
    original_composer = composition._combined_player_cards_html
    composition._combined_player_cards_html = _compact_dashboard_html
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        composition._combined_player_cards_html = original_composer


def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V36 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()


__all__ = [
    "COMPACT_DASHBOARD_ONLY",
    "FROZEN_PASSING_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
