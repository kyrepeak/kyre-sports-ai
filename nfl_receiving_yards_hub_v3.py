"""NFL Receiving Yards V3 — Page Build Step 3 summary metrics.

Visual-only additive wrapper over certified Receiving Yards V2. V3 preserves
V2 receiver identity cards byte-for-byte via delegation and appends a compact
summary strip using only already-validated receiving fields from the certified
production context API.

Step 3 is descriptive only. It does not introduce volume/efficiency
interpretation, opponent pass-defense presentation, player-vs-team history,
projection math, sportsbook markets, probability, EV, Monte Carlo, ranking,
recommendations, staking, or wager actions.

Permanent safety:
- V2/V1 remain unchanged;
- exact ESPN event/team/athlete identity remains owned by certified prior layers;
- names/headshots/logos remain display-only;
- no fuzzy matching or synthetic IDs;
- targets render only when targets_data_available is explicitly true;
- sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_receiving_yards_hub_v2 as prior

MODEL_VERSION = "NFL RECEIVING YARDS V3 • PAGE BUILD STEP 3 • SUMMARY METRICS"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v2"
PAGE_BUILD_STEP = 3
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_PLAYER_CARD_V2 = prior._player_card
_ORIGINAL_MARKDOWN = st.markdown

_SUMMARY_CSS = r'''
<style>
.krecv-progress .krecv-fill{width:30%!important}
.krecv3-player{min-width:0;display:flex;flex-direction:column;gap:6px}
.krecv3-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;padding:0 2px 2px}
.krecv3-box{min-width:0;border:1px solid #203a2b;border-radius:9px;background:linear-gradient(180deg,#0a1711 0%,#08120e 100%);padding:6px 7px}
.krecv3-box b{display:block;color:#edf7f0;font-size:.67rem;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krecv3-box span{display:block;color:#657b6d;font-size:.38rem;font-weight:900;letter-spacing:.035em;text-transform:uppercase;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krecv3-box.target{border-color:#2f4e63}.krecv3-box.target b{color:#a8cce5}
.krecv3-box.off{border-color:#514b31}.krecv3-box.off b{color:#d9c273}
@media(max-width:760px){.krecv3-summary{grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.krecv3-box{padding:6px 7px}}
</style>
'''


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


def _summary_metrics_html(player: dict[str, Any]) -> str:
    """Render six descriptive boxes from the certified Receiving context row."""
    targets_live = player.get("targets_data_available") is True
    target_value = _fmt(player.get("targets_per_game"), 1) if targets_live else "—"
    target_class = "target" if targets_live else "off"

    boxes = (
        ("Receptions", _fmt(player.get("receptions"), 0), ""),
        ("Receiving Yards", _fmt(player.get("receiving_yards"), 0), ""),
        ("Rec Yds / Game", _fmt(player.get("receiving_yards_per_game"), 1), ""),
        ("Yards / Reception", _fmt(player.get("yards_per_reception"), 2), ""),
        ("Receiving TD", _fmt(player.get("receiving_touchdowns"), 0), ""),
        ("Targets / Game", target_value, target_class),
    )
    return (
        '<div class="krecv3-summary" aria-label="Receiving yards summary metrics">'
        + "".join(
            f'<div class="krecv3-box{(" " + css_class) if css_class else ""}"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
            for label, value, css_class in boxes
        )
        + "</div>"
    )


def _player_card_v3(
    player: dict[str, Any],
    team: dict[str, Any],
    opponent: dict[str, Any],
) -> str:
    """Delegate the frozen V2 card, then append Step 3 descriptive metrics."""
    card = _ORIGINAL_PLAYER_CARD_V2(player, team, opponent)
    summary = _summary_metrics_html(player)
    return f'<div class="krecv3-player">{card}{summary}</div>'


def _advance_step3_copy(body: Any) -> Any:
    """Advance only V2 presentation copy while V3 owns the render."""
    if not isinstance(body, str):
        return body
    replacements = (
        (
            "Step 2 connects the certified Kyre Sports API and adds exact-ID receiver cards with player headshots, team logos and verified baseline identity. Summary metrics, opponent defense, player-vs-team history, projections and FanDuel markets remain locked for their own steps.",
            "Step 3 adds compact receiving summary metrics beneath the certified exact-ID receiver cards. Volume/efficiency interpretation, opponent defense, player-vs-team history, projections and FanDuel markets remain locked for their own steps.",
        ),
        (
            '<span class="krecv-chip lock">🔒 SUMMARY METRICS NEXT</span>',
            '<span class="krecv-chip">✅ SUMMARY METRICS</span>',
        ),
        (
            '<div class="krecv-tool"><div class="icon">📊</div><b>Summary Metrics</b><span>Receptions, yards and efficiency arrive in Step 3.</span></div>',
            '<div class="krecv-tool live"><div class="icon">📊</div><b>Summary Metrics ✅</b><span>Receptions, yards, yards/game, YPR, TDs and explicit targets.</span></div>',
        ),
        ("STEP 2 OF 10 • PLAYER CARDS LIVE", "STEP 3 OF 10 • SUMMARY LIVE"),
        ('<span class="krecv-stage">3 • SUMMARY</span>', '<span class="krecv-stage on">3 • SUMMARY ✅</span>'),
        (
            "✅ The certified production Receiving Yards API is now connected to this page. Select a verified matchup to load current-roster WR/TE/RB/FB identities, ESPN headshots, team logos and baseline sample labels. Summary statistics stay reserved for Step 3.",
            "✅ Step 3 keeps the certified exact-ID receiver cards and adds descriptive receiving totals/rates directly from the validated production API payload. Targets remain explicit-only and are never inferred.",
        ),
        (
            "<strong>Step 2 safety lock:</strong> Receiving player cards are read-only exact-ID context. Summary metrics, volume/efficiency interpretation, opponent pass-defense presentation, player-vs-team history, projection, live markets, probability, EV, Monte Carlo, rankings, recommendations, staking and wager actions remain OFF. Sportsbook projection influence: <strong>0.0%</strong>.",
            "<strong>Step 3 safety lock:</strong> Receiving summary metrics are descriptive read-only context from the certified exact-ID API. Volume/efficiency interpretation, opponent pass-defense presentation, player-vs-team history, projection, live markets, probability, EV, Monte Carlo, rankings, recommendations, staking and wager actions remain OFF. Sportsbook projection influence: <strong>0.0%</strong>.",
        ),
    )
    out = body
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def _markdown_v3(body: Any, *args: Any, **kwargs: Any):
    return _ORIGINAL_MARKDOWN(_advance_step3_copy(body), *args, **kwargs)


def render_nfl_receiving_yards_hub() -> None:
    """Render certified V2 with additive Step 3 summary metrics only."""
    _ORIGINAL_MARKDOWN(_SUMMARY_CSS, unsafe_allow_html=True)
    original_card = prior._player_card
    original_markdown = prior.st.markdown
    prior._player_card = _player_card_v3
    prior.st.markdown = _markdown_v3
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        prior._player_card = original_card
        prior.st.markdown = original_markdown


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V3 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_advance_step3_copy",
    "_player_card_v3",
    "_summary_metrics_html",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
