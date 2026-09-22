"""NFL Receiving Yards V4 — Page Build Step 4 volume + efficiency.

Visual-only additive wrapper over certified Receiving Yards V3. V4 preserves the
complete V3 exact-ID player-card + summary stack and appends a descriptive
volume/efficiency profile from the already-validated Receiving context payload.

Target-derived fields are shown only when ESPN explicitly published target data.
No target counts, target share, catch rate, or yards/target values are inferred
when that source field is unavailable.

Step 4 remains descriptive. It does not introduce opponent pass-defense
presentation, player-vs-team history, projection math, sportsbook markets,
probability, EV, Monte Carlo, ranking, recommendations, staking, or wager actions.

Permanent safety:
- V3/V2/V1 remain unchanged;
- exact ESPN event/team/athlete identity remains owned by certified prior layers;
- no fuzzy matching or synthetic IDs;
- targets and target-derived efficiency require targets_data_available is True;
- sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v3 as prior

MODEL_VERSION = "NFL RECEIVING YARDS V4 • PAGE BUILD STEP 4 • VOLUME + EFFICIENCY"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v3"
PAGE_BUILD_STEP = 4
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_PLAYER_CARD_V3 = prior._player_card_v3
_ORIGINAL_ADVANCE_STEP3_COPY = prior._advance_step3_copy

_PROFILE_CSS = r'''
<style>
.krecv-progress .krecv-track .krecv-fill{width:40%!important}
.krecv4-profile{border:1px solid #203729;border-radius:11px;background:#08130e;padding:7px 8px 8px;margin:0 2px 2px;min-width:0}
.krecv4-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px}
.krecv4-title{color:#dfeae2;font-size:.54rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase}
.krecv4-meta{color:#6f8477;font-size:.42rem;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krecv4-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}
.krecv4-stat{min-width:0;border-top:1px solid #1a2e22;padding:6px 4px 1px}
.krecv4-stat b{display:block;color:#eef6f0;font-size:.65rem;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krecv4-stat span{display:block;color:#607468;font-size:.37rem;font-weight:900;text-transform:uppercase;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krecv4-target{display:inline-flex;align-items:center;border:1px solid #365f49;border-radius:999px;background:#0d2117;color:#91d3a6;padding:2px 5px;font-size:.38rem;font-weight:950;text-transform:uppercase}
.krecv4-target.off{border-color:#625739;background:#211c11;color:#d9bd69}
@media(max-width:760px){.krecv4-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.krecv4-head{align-items:flex-start;flex-direction:column;gap:3px}}
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


def _fmt(value: Any, digits: int = 1) -> str:
    number = _number(value)
    if not math.isfinite(number):
        return "—"
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if digits else text


def _target_efficiency(player: dict[str, Any]) -> tuple[float, float]:
    """Return catch rate (%) and yards/target only from explicit ESPN targets."""
    if player.get("targets_data_available") is not True:
        return math.nan, math.nan
    targets = _number(player.get("targets"))
    receptions = _number(player.get("receptions"))
    yards = _number(player.get("receiving_yards"))
    if not math.isfinite(targets) or targets <= 0:
        return math.nan, math.nan
    catch_rate = receptions / targets * 100.0 if math.isfinite(receptions) and receptions >= 0 else math.nan
    yards_per_target = yards / targets if math.isfinite(yards) and yards >= 0 else math.nan
    return catch_rate, yards_per_target


def _volume_efficiency_html(player: dict[str, Any]) -> str:
    athlete_id = _safe(player.get("official_athlete_id"), "")
    if not athlete_id.isdigit():
        return ""
    season = _safe(player.get("baseline_season"))
    sample_games = _fmt(player.get("sample_games"), 0)
    targets_live = player.get("targets_data_available") is True
    catch_rate, yards_per_target = _target_efficiency(player)
    target_status = "EXPLICIT TARGETS" if targets_live else "TARGETS NOT PUBLISHED"
    target_class = "" if targets_live else " off"

    stats = (
        ("Receptions / Game", _fmt(player.get("receptions_per_game"), 1)),
        ("Rec Yards / Game", _fmt(player.get("receiving_yards_per_game"), 1)),
        ("Yards / Reception", _fmt(player.get("yards_per_reception"), 2)),
        ("Targets / Game", _fmt(player.get("targets_per_game"), 1) if targets_live else "—"),
        ("Catch Rate", f"{_fmt(catch_rate, 1)}%" if math.isfinite(catch_rate) else "—"),
        ("Yards / Target", _fmt(yards_per_target, 2)),
        ("Sample Games", sample_games),
    )
    return (
        '<section class="krecv4-profile" aria-label="Receiver volume and efficiency profile">'
        '<div class="krecv4-head"><div>'
        '<div class="krecv4-title">Volume + Efficiency Profile</div>'
        f'<div class="krecv4-meta">Verified baseline • season {escape(season)} • exact ESPN athlete {escape(athlete_id)}</div>'
        '</div>'
        f'<span class="krecv4-target{target_class}">{escape(target_status)}</span></div>'
        '<div class="krecv4-grid">'
        + "".join(f'<div class="krecv4-stat"><b>{escape(value)}</b><span>{escape(label)}</span></div>' for label, value in stats)
        + '</div></section>'
    )


def _player_card_v4(player: dict[str, Any], team: dict[str, Any], opponent: dict[str, Any]) -> str:
    """Delegate the full certified V3 stack, then append Step 4 context."""
    stack = _ORIGINAL_PLAYER_CARD_V3(player, team, opponent)
    profile = _volume_efficiency_html(player)
    return f'<div class="krecv4-player">{stack}{profile}</div>' if profile else stack


def _advance_step4_copy(body: Any) -> Any:
    """Run certified Step 3 copy advancement, then advance presentation to Step 4."""
    out = _ORIGINAL_ADVANCE_STEP3_COPY(body)
    if not isinstance(out, str):
        return out
    replacements = (
        (
            "Step 3 adds compact receiving summary metrics beneath the certified exact-ID receiver cards. Volume/efficiency interpretation, opponent defense, player-vs-team history, projections and FanDuel markets remain locked for their own steps.",
            "Step 4 adds a verified volume + efficiency profile beneath the certified receiver stack. Target-derived fields appear only when ESPN explicitly published targets. Opponent defense, player-vs-team history, projections and FanDuel markets remain locked for their own steps.",
        ),
        (
            '<span class="krecv-chip">✅ SUMMARY METRICS</span>',
            '<span class="krecv-chip">✅ SUMMARY METRICS</span><span class="krecv-chip">✅ VOLUME + EFFICIENCY</span>',
        ),
        (
            '<div class="krecv-tool live"><div class="icon">📊</div><b>Summary Metrics ✅</b><span>Receptions, yards, yards/game, YPR, TDs and explicit targets.</span></div>',
            '<div class="krecv-tool live"><div class="icon">⚙️</div><b>Volume + Efficiency ✅</b><span>Per-game volume, YPR and explicit-target efficiency.</span></div>',
        ),
        ("STEP 3 OF 10 • SUMMARY LIVE", "STEP 4 OF 10 • VOLUME + EFFICIENCY LIVE"),
        ('<span class="krecv-stage">4 • VOLUME</span>', '<span class="krecv-stage on">4 • VOLUME ✅</span>'),
        (
            "✅ Step 3 keeps the certified exact-ID receiver cards and adds descriptive receiving totals/rates directly from the validated production API payload. Targets remain explicit-only and are never inferred.",
            "✅ Step 4 adds descriptive volume + efficiency context from the same validated exact-ID API payload. Catch rate and yards/target remain unavailable unless ESPN explicitly published targets.",
        ),
        (
            "<strong>Step 3 safety lock:</strong> Receiving summary metrics are descriptive read-only context from the certified exact-ID API. Volume/efficiency interpretation, opponent pass-defense presentation, player-vs-team history, projection, live markets, probability, EV, Monte Carlo, rankings, recommendations, staking and wager actions remain OFF. Sportsbook projection influence: <strong>0.0%</strong>.",
            "<strong>Step 4 safety lock:</strong> Volume + efficiency is descriptive read-only exact-ID context. Opponent pass-defense presentation and player-vs-team history remain reserved for Step 5. Projection, live markets, probability, EV, Monte Carlo, rankings, recommendations, staking and wager actions remain OFF. Sportsbook projection influence: <strong>0.0%</strong>.",
        ),
    )
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def render_nfl_receiving_yards_hub() -> None:
    """Render certified V3 with additive Step 4 volume/efficiency context only."""
    st.markdown(_PROFILE_CSS, unsafe_allow_html=True)
    original_card = prior._player_card_v3
    original_advance = prior._advance_step3_copy
    prior._player_card_v3 = _player_card_v4
    prior._advance_step3_copy = _advance_step4_copy
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        prior._player_card_v3 = original_card
        prior._advance_step3_copy = original_advance


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V4 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_advance_step4_copy",
    "_player_card_v4",
    "_target_efficiency",
    "_volume_efficiency_html",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
