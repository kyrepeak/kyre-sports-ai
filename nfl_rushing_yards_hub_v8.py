from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st
import nfl_rushing_yards_hub_v7 as prior

MODEL_VERSION = "NFL RUSHING YARDS V8 • PAGE BUILD STEP 5 • PROJECTION RECIPE"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v7"
PAGE_BUILD_STEP = 5
PAGE_BUILD_TOTAL = 6

_ORIGINAL_COMPACT_PLAYER_CARD_V7 = prior._compact_player_card_v7

_RECIPE_CSS = r'''
<style>
.krush8-recipe{border:1px solid #4a3b22;border-radius:11px;background:#171108;padding:7px 8px 8px;margin:0 2px 2px;min-width:0}
.krush8-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:6px}
.krush8-title{color:#f2e6c7;font-size:.54rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}
.krush8-meta{color:#9b8760;font-size:.42rem;font-weight:850;line-height:1.25;margin-top:2px}
.krush8-coverage{display:inline-flex;align-items:center;border:1px solid #6b5730;border-radius:999px;background:#241a0b;color:#e1c677;padding:2px 6px;font-size:.39rem;font-weight:950;text-transform:uppercase;white-space:nowrap}
.krush8-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-bottom:5px}
.krush8-box{min-width:0;border-top:1px solid #3a2d18;padding:6px 4px 2px}
.krush8-box b{display:block;color:#fff6de;font-size:.62rem;line-height:1.15;overflow:hidden;text-overflow:ellipsis}
.krush8-box span{display:block;color:#8d7954;font-size:.37rem;font-weight:900;text-transform:uppercase;margin-top:3px}
.krush8-components{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}
.krush8-component{border:1px solid #342817;border-radius:8px;background:#100c06;padding:6px 7px;min-width:0}
.krush8-component b{display:block;color:#f6ead0;font-size:.58rem;line-height:1.1}
.krush8-component span{display:block;color:#8f7b58;font-size:.38rem;font-weight:850;margin-top:3px}
@media(max-width:760px){.krush8-head{flex-direction:column;gap:3px}.krush8-grid,.krush8-components{grid-template-columns:1fr}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _number(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _fmt(value: Any, digits: int = 2) -> str:
    number = _number(value)
    if not math.isfinite(number):
        return "—"
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if digits else text


def _pct(value: Any) -> str:
    number = _number(value)
    return f"{number * 100.0:.0f}%" if math.isfinite(number) else "—"


def _recipe_components(projection_row: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    raw = projection_row.get("efficiency_components") or []
    if not isinstance(raw, list):
        return ()
    allowed = {"player_yards_per_carry", "opponent_yards_per_carry_allowed"}
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        key = _safe(row.get("key"), "")
        if key not in allowed:
            continue
        out.append(row)
    return tuple(out[:2])


def _projection_recipe_html(projection_row: dict[str, Any]) -> str:
    if projection_row.get("ready") is not True:
        return ""

    formula = _safe(projection_row.get("formula"))
    workload_source = _safe(projection_row.get("workload_source"))
    efficiency_source = _safe(projection_row.get("player_efficiency_source"))
    coverage = _pct(projection_row.get("efficiency_coverage"))
    grade = _safe(projection_row.get("coverage_grade"), "CHECK").upper()
    basis = _safe(projection_row.get("coverage_basis"))
    components = _recipe_components(projection_row)

    component_html = "".join(
        (
            '<div class="krush8-component">'
            f'<b>{escape("Player YPC" if _safe(row.get("key"), "") == "player_yards_per_carry" else "Opponent YPC Allowed")}: {_fmt(row.get("value"), 2)}</b>'
            f'<span>Certified blend weight {_pct(row.get("normalized_weight"))}</span>'
            '</div>'
        )
        for row in components
    )

    return (
        '<section class="krush8-recipe" aria-label="Projection recipe">'
        '<div class="krush8-head"><div>'
        '<div class="krush8-title">Projection Recipe • Why This Number?</div>'
        f'<div class="krush8-meta">{escape(basis)}</div>'
        '</div>'
        f'<span class="krush8-coverage">{escape(grade)} • {escape(coverage)} coverage</span></div>'
        '<div class="krush8-grid">'
        f'<div class="krush8-box"><b>{escape(formula)}</b><span>Certified Formula</span></div>'
        f'<div class="krush8-box"><b>{escape(workload_source)}</b><span>Workload Source</span></div>'
        f'<div class="krush8-box"><b>{escape(efficiency_source)}</b><span>Player Efficiency Source</span></div>'
        f'<div class="krush8-box"><b>{escape(_fmt(projection_row.get("expected_yards_per_carry"), 2))}</b><span>Certified Expected YPC</span></div>'
        '</div>'
        f'<div class="krush8-components">{component_html}</div>'
        '</section>'
    )


def _compact_player_card_v8(projection_row: dict[str, Any], team: dict[str, Any], opponent: dict[str, Any], market_row: dict[str, Any]) -> str:
    stack = _ORIGINAL_COMPACT_PLAYER_CARD_V7(projection_row, team, opponent, market_row)
    recipe = _projection_recipe_html(projection_row)
    return f'<div class="krush8-player">{stack}{recipe}</div>' if recipe else stack


def render_nfl_rushing_yards_hub() -> None:
    st.markdown(_RECIPE_CSS, unsafe_allow_html=True)
    original_card = prior._compact_player_card_v7
    prior._compact_player_card_v7 = _compact_player_card_v8
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        prior._compact_player_card_v7 = original_card


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V8 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()
