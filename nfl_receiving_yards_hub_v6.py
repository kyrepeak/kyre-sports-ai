"""NFL Receiving Yards V6 — Page Build Step 6 projection recipe.

Additive visual/model wrapper over certified Receiving Yards V5. V6 preserves
the complete V5 exact-ID receiver, volume/efficiency, opponent pass-defense and
player-vs-team history stack, then adds the first market-blind Receiving Yards
baseline projection plus a transparent recipe panel.

Projection inputs are restricted to verified receiving workload and exact-ID
opponent pass-defense efficiency. Targets are not required or inferred.
Sportsbook lines/prices do not enter the projection. Sportsbook projection
influence remains exactly 0.0%.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v5 as prior
import nfl_receiving_yards_projection_v1 as projection_engine

MODEL_VERSION = "NFL RECEIVING YARDS V6 • PAGE BUILD STEP 6 • PROJECTION RECIPE"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v5"
PAGE_BUILD_STEP = 6
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_PLAYER_CARD_V5 = prior._player_card_v5
_ORIGINAL_ADVANCE_STEP5_COPY = prior._advance_step5_copy

_STEP6_CSS = r'''
<style>
.krecv-progress .krecv-track .krecv-fill{width:60%!important}
.krecv6-wrap{border:1px solid #31564a;border-radius:11px;background:linear-gradient(145deg,#0a1814,#0b1513);padding:9px;margin:2px;min-width:0}
.krecv6-head{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.krecv6-title{color:#eaf6ef;font-size:.56rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.krecv6-grade{border:1px solid #3d6a51;background:#102419;color:#94dfad;border-radius:999px;padding:3px 7px;font-size:.38rem;font-weight:950;white-space:nowrap}.krecv6-grade.watch{border-color:#776537;background:#261f0f;color:#e2c771}.krecv6-grade.check{border-color:#704545;background:#261313;color:#d99494}
.krecv6-main{display:grid;grid-template-columns:1.15fr .85fr .85fr;gap:6px;margin-top:7px}.krecv6-main div{border-top:1px solid #20392c;padding:6px 4px 1px;min-width:0}.krecv6-main b{display:block;color:#f5faf7;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv6-main span{display:block;color:#667b6d;font-size:.36rem;font-weight:900;text-transform:uppercase;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krecv6-formula{margin-top:7px;border:1px solid #234235;border-radius:8px;background:#0b1c14;padding:6px 7px;color:#91aa99;font-size:.43rem;line-height:1.45}.krecv6-formula strong{color:#bde5ca}.krecv6-components{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:6px}.krecv6-component{border:1px solid #20372b;border-radius:7px;padding:5px 6px;min-width:0}.krecv6-component b{color:#dce9e0;font-size:.47rem;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv6-component span{display:block;color:#65796c;font-size:.35rem;margin-top:2px;line-height:1.35}.krecv6-note{margin-top:6px;color:#708579;font-size:.38rem;line-height:1.45}.krecv6-empty{border:1px dashed #45544b;border-radius:8px;padding:7px;color:#8a9a90;font-size:.43rem;line-height:1.45}
@media(max-width:760px){.krecv6-main{grid-template-columns:1fr 1fr}.krecv6-main div:first-child{grid-column:1/-1}.krecv6-components{grid-template-columns:1fr}.krecv6-head{flex-direction:column;gap:4px}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _fmt(value: Any, digits: int = 1) -> str:
    number = _num(value)
    if not math.isfinite(number):
        return "—"
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if digits else text


def _weight_label(component: dict[str, Any]) -> str:
    weight = _num(component.get("normalized_weight"))
    return f"{weight * 100:.0f}%" if math.isfinite(weight) else "—"


def _projection_recipe_html(player: dict[str, Any], team: dict[str, Any]) -> str:
    event_id = _safe(player.get("official_event_id"), "")
    result = projection_engine.build_player_projection(
        official_event_id=event_id,
        team=team,
        player=player,
    )
    if result.get("ready") is not True:
        reason = _safe(result.get("reason"), "verified projection evidence incomplete")
        return (
            '<section class="krecv6-wrap" aria-label="Receiving Yards projection recipe">'
            '<div class="krecv6-title">Market-Blind Projection Recipe</div>'
            f'<div class="krecv6-empty">Projection withheld: {escape(reason)}. No market line, target estimate, name match, or synthetic fallback was used.</div>'
            '</section>'
        )

    grade = _safe(result.get("coverage_grade"), "CHECK").upper()
    grade_class = "" if grade == "GREEN" else ("watch" if grade == "WATCH" else "check")
    components = result.get("efficiency_components") or []
    component_rows: list[str] = []
    labels = {
        "player_yards_per_reception": "Player YPR",
        "opponent_yards_per_reception_allowed": "Opponent YPR Allowed",
    }
    for component in components:
        if not isinstance(component, dict):
            continue
        key = _safe(component.get("key"), "")
        component_rows.append(
            '<div class="krecv6-component">'
            f'<b>{escape(labels.get(key, key or "Efficiency input"))}: {escape(_fmt(component.get("value"), 2))}</b>'
            f'<span>{escape(_weight_label(component))} normalized blend weight</span>'
            '</div>'
        )

    formula = _safe(result.get("formula"), "expected_receptions × expected_yards_per_reception")
    workload_source = _safe(result.get("workload_source"), "verified receiving workload")
    efficiency_source = _safe(result.get("player_efficiency_source"), "verified receiving efficiency")
    grade_basis = _safe(result.get("coverage_basis"), "verified evidence")
    return (
        '<section class="krecv6-wrap" aria-label="Receiving Yards projection recipe">'
        '<div class="krecv6-head">'
        '<div><div class="krecv6-title">Market-Blind Projection Recipe</div>'
        f'<div class="krecv6-note">ESPN athlete {escape(_safe(result.get("official_athlete_id"), ""))} • event {escape(event_id)} • sportsbook influence 0.0%</div></div>'
        f'<span class="krecv6-grade {grade_class}">{escape(grade)} EVIDENCE</span>'
        '</div>'
        '<div class="krecv6-main">'
        f'<div><b>{escape(_fmt(result.get("projection_yards"), 1))} YDS</b><span>Baseline Receiving Projection</span></div>'
        f'<div><b>{escape(_fmt(result.get("expected_receptions"), 2))}</b><span>Expected Receptions</span></div>'
        f'<div><b>{escape(_fmt(result.get("expected_yards_per_reception"), 2))}</b><span>Expected YPR</span></div>'
        '</div>'
        f'<div class="krecv6-formula"><strong>Formula:</strong> {escape(formula)}<br>'
        f'<strong>Workload:</strong> {escape(workload_source)} • <strong>Player efficiency:</strong> {escape(efficiency_source)}</div>'
        '<div class="krecv6-components">' + "".join(component_rows) + '</div>'
        f'<div class="krecv6-note">{escape(grade_basis)} • targets used: NO • probabilities/EV/Monte Carlo/market prices: OFF</div>'
        '</section>'
    )


def _player_card_v6(player: dict[str, Any], team: dict[str, Any], opponent: dict[str, Any]) -> str:
    stack = _ORIGINAL_PLAYER_CARD_V5(player, team, opponent)
    recipe = _projection_recipe_html(player, team)
    return f'<div class="krecv6-player">{stack}{recipe}</div>'


def _advance_step6_copy(body: Any) -> Any:
    out = _ORIGINAL_ADVANCE_STEP5_COPY(body)
    if not isinstance(out, str):
        return out
    replacements = (
        (
            "Step 5 adds exact-ID opponent pass-defense context plus verified player-vs-team receiving game-book history. Projection math and FanDuel markets remain locked for later certified steps.",
            "Step 6 adds the first exact-ID market-blind Receiving Yards baseline projection and transparent projection recipe. FanDuel markets remain locked for Step 8; sportsbook influence on projection math is 0.0%.",
        ),
        (
            '<span class="krecv-chip">✅ VOLUME + EFFICIENCY</span><span class="krecv-chip">✅ DEFENSE + H2H</span>',
            '<span class="krecv-chip">✅ VOLUME + EFFICIENCY</span><span class="krecv-chip">✅ DEFENSE + H2H</span><span class="krecv-chip">✅ MARKET-BLIND PROJECTION</span>',
        ),
        ("STEP 5 OF 10 • DEFENSE + H2H LIVE", "STEP 6 OF 10 • PROJECTION RECIPE LIVE"),
        (
            '<span class="krecv-stage">6 • PROJECTION</span>',
            '<span class="krecv-stage on">6 • PROJECTION ✅</span>',
        ),
        (
            "✅ Step 5 presents the certified opponent pass-defense payload and exact-ID player-vs-team receiving history. Athlete/team/opponent IDs are authoritative; names remain display-only.",
            "✅ Step 6 adds a market-blind baseline projection from verified receptions workload plus a 65% player YPR / 35% exact-opponent YPR-allowed blend. Targets are not required or inferred.",
        ),
        (
            "<strong>Step 5 safety lock:</strong> Opponent pass defense and H2H are descriptive read-only exact-ID context. Projection, live markets, probability, EV, Monte Carlo, rankings, recommendations, staking and wager actions remain OFF. Player/team names are never matching keys. Sportsbook projection influence: <strong>0.0%</strong>.",
            "<strong>Step 6 safety lock:</strong> Receiving projection is market-blind exact-ID baseline math only. Live markets, probability, fair odds, EV, Monte Carlo, rankings, recommendations, staking and wager actions remain OFF. Targets are not inferred or required. Player/team names are never matching keys. Sportsbook projection influence: <strong>0.0%</strong>.",
        ),
    )
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def render_nfl_receiving_yards_hub() -> None:
    st.markdown(_STEP6_CSS, unsafe_allow_html=True)
    original_card = prior._player_card_v5
    original_advance = prior._advance_step5_copy
    prior._player_card_v5 = _player_card_v6
    prior._advance_step5_copy = _advance_step6_copy
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        prior._player_card_v5 = original_card
        prior._advance_step5_copy = original_advance


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V6 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_advance_step6_copy",
    "_player_card_v6",
    "_projection_recipe_html",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
