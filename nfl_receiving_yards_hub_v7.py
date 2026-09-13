"""NFL Receiving Yards V7 — Page Build Step 7 support + concerns.

Additive visual-only explanation layer over certified Receiving Yards V6. V7
reuses the frozen Step 6 market-blind projection engine and explains only its
already-certified evidence. It does not change projection math, add market
inputs, or create betting grades/recommendations.

Sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v6 as prior
import nfl_receiving_yards_projection_v1 as projection_engine

MODEL_VERSION = "NFL RECEIVING YARDS V7 • PAGE BUILD STEP 7 • SUPPORT + CONCERNS"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v6"
FROZEN_PROJECTION_ENGINE = "nfl_receiving_yards_projection_v1"
PAGE_BUILD_STEP = 7
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_PLAYER_CARD_V6 = prior._player_card_v6
_ORIGINAL_ADVANCE_STEP6_COPY = prior._advance_step6_copy

_STEP7_CSS = r'''
<style>
.krecv-progress .krecv-track .krecv-fill{width:70%!important}
.krecv7-wrap{border:1px solid #304957;border-radius:11px;background:#09131a;padding:9px;margin:2px;min-width:0}
.krecv7-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:7px}.krecv7-title{color:#e8f1f7;font-size:.56rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}.krecv7-note{color:#718694;font-size:.39rem;font-weight:850;line-height:1.35;margin-top:2px}.krecv7-badge{border:1px solid #3b5968;border-radius:999px;background:#0d2029;color:#9fc9da;padding:3px 7px;font-size:.37rem;font-weight:950;text-transform:uppercase;white-space:nowrap}
.krecv7-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.krecv7-col{border:1px solid #20323b;border-radius:9px;background:#081117;padding:7px;min-width:0}.krecv7-col h4{margin:0 0 5px;font-size:.46rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.krecv7-col.support h4{color:#93daa9}.krecv7-col.concern h4{color:#dfbd75}.krecv7-item{border-top:1px solid #1a2931;padding:5px 1px;color:#dce8ed;font-size:.47rem;font-weight:800;line-height:1.38}.krecv7-item:first-of-type{border-top:0}
@media(max-width:760px){.krecv7-head{flex-direction:column;gap:3px}.krecv7-grid{grid-template-columns:1fr}}
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
    allowed = {"player_yards_per_reception", "opponent_yards_per_reception_allowed"}
    out: dict[str, float] = {}
    for row in projection_row.get("efficiency_components") or []:
        if not isinstance(row, dict):
            continue
        key = _safe(row.get("key"), "")
        value = _number(row.get("value"))
        if key in allowed and math.isfinite(value):
            out[key] = value
    return out


def _support_concern_rows(
    projection_row: dict[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Explain frozen Step 6 evidence without using market/price information."""
    if projection_row.get("ready") is not True:
        return (), ()

    supports: list[str] = []
    concerns: list[str] = []
    expected_ypr = _number(projection_row.get("expected_yards_per_reception"))
    expected_receptions = _number(projection_row.get("expected_receptions"))
    coverage = _number(projection_row.get("efficiency_coverage"))
    grade = _safe(projection_row.get("coverage_grade"), "CHECK").upper()
    basis = _safe(projection_row.get("coverage_basis"), "Evidence quality not supplied")

    if math.isfinite(expected_receptions):
        supports.append(
            f"Workload anchor: {_fmt(expected_receptions, 1)} expected receptions from "
            f"{_safe(projection_row.get('workload_source'), 'certified receiving workload evidence')}."
        )

    if math.isfinite(coverage) and coverage >= 0.999999:
        supports.append(
            "Efficiency coverage: all certified player + exact-opponent blend inputs are present."
        )
    elif math.isfinite(coverage):
        concerns.append(
            f"Efficiency coverage is only {coverage * 100.0:.0f}% of the certified blend inputs."
        )

    if grade == "GREEN":
        supports.append(f"Evidence quality: {basis}.")
    else:
        concerns.append(f"Evidence quality is {grade}: {basis}.")

    components = _component_values(projection_row)
    comparisons = (
        ("player_yards_per_reception", "Player efficiency input"),
        ("opponent_yards_per_reception_allowed", "Opponent YPR-allowed input"),
    )
    if math.isfinite(expected_ypr):
        for key, label in comparisons:
            value = components.get(key, math.nan)
            if not math.isfinite(value):
                continue
            sentence = (
                f"{label}: {_fmt(value, 2)} YPR vs {_fmt(expected_ypr, 2)} blended expected YPR."
            )
            if value >= expected_ypr:
                supports.append(sentence)
            else:
                concerns.append(sentence)

    if not supports:
        supports.append(
            "No additional support signal is exposed by the certified Step 6 projection fields."
        )
    if not concerns:
        concerns.append(
            "No concern/counterweight is flagged by the certified Step 6 projection fields."
        )
    return tuple(supports[:4]), tuple(concerns[:4])


def _support_concerns_html(projection_row: dict[str, Any]) -> str:
    supports, concerns = _support_concern_rows(projection_row)
    if not supports and not concerns:
        return ""

    support_html = "".join(
        f'<div class="krecv7-item">{escape(item)}</div>' for item in supports
    )
    concern_html = "".join(
        f'<div class="krecv7-item">{escape(item)}</div>' for item in concerns
    )
    return (
        '<section class="krecv7-wrap" aria-label="Projection supports and concerns">'
        '<div class="krecv7-head"><div>'
        '<div class="krecv7-title">Support vs Concern • Projection Readout</div>'
        '<div class="krecv7-note">Descriptive explanation only • not a betting grade • '
        'no sportsbook line/price used • projection math unchanged • sportsbook projection influence 0.0%</div>'
        '</div><span class="krecv7-badge">Page Step 7 / 10</span></div>'
        '<div class="krecv7-grid">'
        f'<div class="krecv7-col support"><h4>Supports</h4>{support_html}</div>'
        f'<div class="krecv7-col concern"><h4>Concerns / Counterweights</h4>{concern_html}</div>'
        '</div></section>'
    )


def _projection_row(player: dict[str, Any], team: dict[str, Any]) -> dict[str, Any]:
    """Reuse the frozen Step 6 engine; do not duplicate or alter projection math."""
    return projection_engine.build_player_projection(
        official_event_id=_safe(player.get("official_event_id"), ""),
        team=team,
        player=player,
    )


def _player_card_v7(
    player: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
) -> str:
    stack = _ORIGINAL_PLAYER_CARD_V6(player, team, opponent)
    projection_row = _projection_row(player, team)
    explanation = _support_concerns_html(projection_row)
    return f'<div class="krecv7-player">{stack}{explanation}</div>' if explanation else stack


def _advance_step7_copy(body: Any) -> Any:
    out = _ORIGINAL_ADVANCE_STEP6_COPY(body)
    if not isinstance(out, str):
        return out
    replacements = (
        (
            "Step 6 adds the first exact-ID market-blind Receiving Yards baseline projection and transparent projection recipe. FanDuel markets remain locked for Step 8; sportsbook influence on projection math is 0.0%.",
            "Step 7 adds descriptive Support + Concerns beneath the certified market-blind projection. It explains workload, evidence coverage, sample quality and player/opponent YPR counterweights without using a sportsbook line or changing projection math.",
        ),
        (
            '<span class="krecv-chip">✅ MARKET-BLIND PROJECTION</span>',
            '<span class="krecv-chip">✅ MARKET-BLIND PROJECTION</span><span class="krecv-chip">✅ SUPPORT + CONCERNS</span>',
        ),
        ("STEP 6 OF 10 • PROJECTION RECIPE LIVE", "STEP 7 OF 10 • SUPPORT + CONCERNS LIVE"),
        (
            '<span class="krecv-stage">7 • SUPPORT</span>',
            '<span class="krecv-stage on">7 • SUPPORT ✅</span>',
        ),
        (
            "✅ Step 6 adds a market-blind baseline projection from verified receptions workload plus a 65% player YPR / 35% exact-opponent YPR-allowed blend. Targets are not required or inferred.",
            "✅ Step 7 explains the frozen Step 6 projection with evidence-only supports and concerns. Workload, coverage grade and player/opponent YPR inputs are descriptive; sportsbook line/price remains excluded.",
        ),
        (
            "<strong>Step 6 safety lock:</strong> Receiving projection is market-blind exact-ID baseline math only. Live markets, probability, fair odds, EV, Monte Carlo, rankings, recommendations, staking and wager actions remain OFF. Targets are not inferred or required. Player/team names are never matching keys. Sportsbook projection influence: <strong>0.0%</strong>.",
            "<strong>Step 7 safety lock:</strong> Support + Concerns is descriptive explanation of the frozen Step 6 projection only. It does not change projection math and does not use sportsbook line/price. Live markets, probability, fair odds, EV, Monte Carlo, betting grades, rankings, recommendations, staking and wager actions remain OFF. Sportsbook projection influence: <strong>0.0%</strong>.",
        ),
    )
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def render_nfl_receiving_yards_hub() -> None:
    st.markdown(_STEP7_CSS, unsafe_allow_html=True)
    original_card = prior._player_card_v6
    original_advance = prior._advance_step6_copy
    prior._player_card_v6 = _player_card_v7
    prior._advance_step6_copy = _advance_step7_copy
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        prior._player_card_v6 = original_card
        prior._advance_step6_copy = original_advance


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V7 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "FROZEN_PROJECTION_ENGINE",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_advance_step7_copy",
    "_component_values",
    "_player_card_v7",
    "_projection_row",
    "_support_concern_rows",
    "_support_concerns_html",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
