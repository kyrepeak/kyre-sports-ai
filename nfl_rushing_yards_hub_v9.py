from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st
import nfl_rushing_yards_hub_v8 as prior

MODEL_VERSION = "NFL RUSHING YARDS V9 • PAGE BUILD STEP 6 • SUPPORT + CONCERNS"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v8"
PAGE_BUILD_STEP = 6
PAGE_BUILD_TOTAL = 6

_ORIGINAL_COMPACT_PLAYER_CARD_V8 = prior._compact_player_card_v8

_FINAL_CSS = r'''
<style>
.krush9-final{border:1px solid #26384b;border-radius:11px;background:#08111b;padding:8px;margin:0 2px 2px}
.krush9-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:6px}
.krush9-title{color:#e5eef8;font-size:.55rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}
.krush9-note{color:#72849a;font-size:.40rem;font-weight:850;line-height:1.3;margin-top:2px}
.krush9-badge{border:1px solid #39516b;border-radius:999px;background:#0b1b2b;color:#9cc4eb;padding:2px 6px;font-size:.38rem;font-weight:950;text-transform:uppercase;white-space:nowrap}
.krush9-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
.krush9-col{border:1px solid #1e2c3a;border-radius:9px;background:#071019;padding:7px;min-width:0}
.krush9-col h4{margin:0 0 5px;font-size:.46rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
.krush9-col.support h4{color:#92d7a7}.krush9-col.concern h4{color:#e0bb72}
.krush9-item{border-top:1px solid #182532;padding:5px 1px;color:#dbe6ef;font-size:.48rem;font-weight:800;line-height:1.35}
.krush9-item:first-of-type{border-top:0}
@media(max-width:760px){.krush9-head{flex-direction:column;gap:3px}.krush9-grid{grid-template-columns:1fr}}
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


def _component_values(projection_row: dict[str, Any]) -> dict[str, float]:
    allowed = {"player_yards_per_carry", "opponent_yards_per_carry_allowed"}
    out: dict[str, float] = {}
    for row in projection_row.get("efficiency_components") or []:
        if not isinstance(row, dict):
            continue
        key = _safe(row.get("key"), "")
        value = _number(row.get("value"))
        if key in allowed and math.isfinite(value):
            out[key] = value
    return out


def _support_concern_rows(projection_row: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if projection_row.get("ready") is not True:
        return (), ()

    supports: list[str] = []
    concerns: list[str] = []
    expected_ypc = _number(projection_row.get("expected_yards_per_carry"))
    expected_carries = _number(projection_row.get("expected_carries"))
    coverage = _number(projection_row.get("efficiency_coverage"))
    grade = _safe(projection_row.get("coverage_grade"), "CHECK").upper()
    basis = _safe(projection_row.get("coverage_basis"), "Evidence quality not supplied")

    if math.isfinite(expected_carries):
        supports.append(
            f"Workload anchor: {_fmt(expected_carries, 1)} expected carries from {_safe(projection_row.get('workload_source'), 'certified workload evidence')}."
        )

    if math.isfinite(coverage) and coverage >= 0.999999:
        supports.append("Efficiency coverage: all certified player + opponent blend inputs are present.")
    elif math.isfinite(coverage):
        concerns.append(f"Efficiency coverage is only {coverage * 100.0:.0f}% of the certified blend inputs.")

    if grade == "GREEN":
        supports.append(f"Evidence quality: {basis}.")
    else:
        concerns.append(f"Evidence quality is {grade}: {basis}.")

    components = _component_values(projection_row)
    comparisons = (
        ("player_yards_per_carry", "Player efficiency input"),
        ("opponent_yards_per_carry_allowed", "Opponent YPC-allowed input"),
    )
    if math.isfinite(expected_ypc):
        for key, label in comparisons:
            value = components.get(key, math.nan)
            if not math.isfinite(value):
                continue
            sentence = f"{label}: {_fmt(value, 2)} YPC vs {_fmt(expected_ypc, 2)} blended expected YPC."
            if value >= expected_ypc:
                supports.append(sentence)
            else:
                concerns.append(sentence)

    if not supports:
        supports.append("No additional support signal is exposed by the certified projection fields.")
    if not concerns:
        concerns.append("No concern/counterweight is flagged by the certified projection fields.")
    return tuple(supports[:4]), tuple(concerns[:4])


def _support_concerns_html(projection_row: dict[str, Any]) -> str:
    supports, concerns = _support_concern_rows(projection_row)
    if not supports and not concerns:
        return ""

    support_html = "".join(f'<div class="krush9-item">{escape(item)}</div>' for item in supports)
    concern_html = "".join(f'<div class="krush9-item">{escape(item)}</div>' for item in concerns)
    return (
        '<section class="krush9-final" aria-label="Projection supports and concerns">'
        '<div class="krush9-head"><div>'
        '<div class="krush9-title">Support vs Concern • Projection Readout</div>'
        '<div class="krush9-note">Descriptive explanation only • not a betting grade • sportsbook projection influence remains 0.0%</div>'
        '</div><span class="krush9-badge">Final Page Step 6 / 6</span></div>'
        '<div class="krush9-grid">'
        f'<div class="krush9-col support"><h4>Supports</h4>{support_html}</div>'
        f'<div class="krush9-col concern"><h4>Concerns / Counterweights</h4>{concern_html}</div>'
        '</div></section>'
    )


def _compact_player_card_v9(projection_row: dict[str, Any], team: dict[str, Any], opponent: dict[str, Any], market_row: dict[str, Any]) -> str:
    stack = _ORIGINAL_COMPACT_PLAYER_CARD_V8(projection_row, team, opponent, market_row)
    final = _support_concerns_html(projection_row)
    return f'<div class="krush9-player">{stack}{final}</div>' if final else stack


def render_nfl_rushing_yards_hub() -> None:
    st.markdown(_FINAL_CSS, unsafe_allow_html=True)
    original_card = prior._compact_player_card_v8
    prior._compact_player_card_v8 = _compact_player_card_v9
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        prior._compact_player_card_v8 = original_card


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V9 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()
