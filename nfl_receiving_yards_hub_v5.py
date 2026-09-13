"""NFL Receiving Yards V5 — Page Build Step 5 defense + H2H.

Additive visual wrapper over certified Receiving Yards V4. V5 preserves the full
V4 receiver stack, presents the already-certified exact-ID opponent pass-defense
context, and appends read-only player-vs-opponent history from completed ESPN
game books matched strictly by official athlete/team/opponent IDs.

No projection, sportsbook market, probability, EV, Monte Carlo, ranking,
recommendation, staking or wager action is introduced. Sportsbook projection
influence remains exactly 0.0%.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_receiving_yards_history_v1 as history_api
import nfl_receiving_yards_hub_v4 as prior

MODEL_VERSION = "NFL RECEIVING YARDS V5 • PAGE BUILD STEP 5 • DEFENSE + H2H"
FROZEN_PRIOR = "nfl_receiving_yards_hub_v4"
PAGE_BUILD_STEP = 5
PAGE_BUILD_TOTAL = 10
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_ORIGINAL_PLAYER_CARD_V4 = prior._player_card_v4
_ORIGINAL_ADVANCE_STEP4_COPY = prior._advance_step4_copy

_STEP5_CSS = r'''
<style>
.krecv-progress .krecv-track .krecv-fill{width:50%!important}
.krecv5-wrap{border:1px solid #284235;border-radius:11px;background:#091610;padding:8px;margin:0 2px 2px;min-width:0}
.krecv5-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px}.krecv5-title{color:#e7f2ea;font-size:.55rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.krecv5-id{color:#657a6d;font-size:.40rem;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krecv5-defense{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px}.krecv5-stat{border-top:1px solid #1d3427;padding:6px 4px 2px;min-width:0}.krecv5-stat b{display:block;color:#f0f7f2;font-size:.62rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv5-stat span{display:block;color:#617568;font-size:.35rem;font-weight:900;text-transform:uppercase;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.krecv5-divider{height:1px;background:#1b2e23;margin:8px 0}.krecv5-h2h-title{display:flex;align-items:center;justify-content:space-between;gap:8px}.krecv5-h2h-title b{color:#dce9e0;font-size:.51rem;text-transform:uppercase}.krecv5-h2h-title span{color:#687d70;font-size:.38rem;font-weight:850}.krecv5-history{display:grid;gap:5px;margin-top:6px}.krecv5-game{display:grid;grid-template-columns:1.15fr .7fr .7fr .7fr .7fr;gap:5px;align-items:center;border:1px solid #1d3427;border-radius:8px;background:#0b1912;padding:5px 6px;min-width:0}.krecv5-game b{color:#e8f1ea;font-size:.48rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv5-game span{color:#6f8376;font-size:.37rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.krecv5-empty{border:1px dashed #33483c;border-radius:8px;padding:7px;color:#819487;font-size:.44rem;line-height:1.4;margin-top:6px}
@media(max-width:760px){.krecv5-defense{grid-template-columns:repeat(2,minmax(0,1fr))}.krecv5-game{grid-template-columns:1fr 1fr 1fr}.krecv5-game .wide{grid-column:1/-1}.krecv5-head{align-items:flex-start;flex-direction:column;gap:3px}}
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


@st.cache_data(ttl=300, show_spinner=False)
def _load_history(athlete_id: str, team_id: str, opponent_id: str, anchor_season: int) -> dict[str, Any]:
    return history_api.get_player_vs_team_history(athlete_id, team_id, opponent_id, anchor_season)


def _defense_context(team: dict[str, Any], opponent_id: str) -> dict[str, Any] | None:
    raw = team.get("opponent_pass_defense")
    if not isinstance(raw, dict):
        return None
    if _safe(raw.get("official_team_id"), "") != opponent_id:
        return None
    return raw


def _step5_context_html(player: dict[str, Any], team: dict[str, Any], opponent: dict[str, Any]) -> str:
    athlete_id = _safe(player.get("official_athlete_id"), "")
    team_id = _safe(player.get("official_team_id"), "")
    opponent_id = _safe(team.get("opponent_official_team_id"), "")
    if (
        not athlete_id.isdigit()
        or not team_id.isdigit()
        or not opponent_id.isdigit()
        or team_id == opponent_id
        or team_id != _safe(team.get("official_team_id"), "")
    ):
        return '<div class="krecv5-empty">Step 5 exact-ID identity failed closed. No opponent context or H2H values were guessed.</div>'

    opponent_abbr = _safe(opponent.get("team_abbreviation"), "OPP").upper()
    defense = _defense_context(team, opponent_id)
    if defense is None:
        defense_html = '<div class="krecv5-empty">Opponent pass-defense identity unavailable or mismatched. No defense values were inferred.</div>'
    else:
        targets_live = defense.get("targets_data_available") is True
        defense_stats = (
            ("Rec Allowed / G", _fmt(defense.get("receptions_allowed_per_game"), 1)),
            ("Rec Yds Allowed / G", _fmt(defense.get("receiving_yards_allowed_per_game"), 1)),
            ("YPR Allowed", _fmt(defense.get("yards_per_reception_allowed"), 2)),
            ("Rec TD Allowed / G", _fmt(defense.get("receiving_touchdowns_allowed_per_game"), 2)),
            ("Targets Allowed / G", _fmt(defense.get("targets_allowed_per_game"), 1) if targets_live else "—"),
        )
        defense_html = '<div class="krecv5-defense">' + "".join(
            f'<div class="krecv5-stat"><b>{escape(value)}</b><span>{escape(label)}</span></div>'
            for label, value in defense_stats
        ) + '</div>'

    anchor_raw = player.get("baseline_season") or team.get("player_baseline_season")
    try:
        anchor_season = int(anchor_raw)
    except (TypeError, ValueError):
        anchor_season = 0
    history = _load_history(athlete_id, team_id, opponent_id, anchor_season)
    games = history.get("games") if isinstance(history, dict) else []
    if not isinstance(games, list):
        games = []
    if history.get("ready") is not True:
        reason = _safe(history.get("reason"), "exact-ID history unavailable")
        history_html = f'<div class="krecv5-empty">Player vs {escape(opponent_abbr)} history unavailable: {escape(reason)}. No fallback was invented.</div>'
    elif not games:
        history_html = (
            f'<div class="krecv5-empty">No verified receiving game-book history found for this exact ESPN athlete ID vs {escape(opponent_abbr)} in the certified history window. Zero-stat appearances are not invented.</div>'
        )
    else:
        rows: list[str] = []
        for game in games:
            if not isinstance(game, dict):
                continue
            event_id = _safe(game.get("official_event_id"), "")
            if (
                _safe(game.get("official_athlete_id"), "") != athlete_id
                or _safe(game.get("official_team_id"), "") != team_id
                or _safe(game.get("opponent_official_team_id"), "") != opponent_id
                or not event_id.isdigit()
            ):
                continue
            targets = _fmt(game.get("targets"), 0) if game.get("targets_data_available") is True else "—"
            rows.append(
                '<div class="krecv5-game">'
                f'<b class="wide">{escape(_safe(game.get("date"), f"ESPN {event_id}"))}</b>'
                f'<span>{escape(_fmt(game.get("receptions"), 0))} REC</span>'
                f'<span>{escape(_fmt(game.get("receiving_yards"), 0))} YDS</span>'
                f'<span>{escape(_fmt(game.get("receiving_touchdowns"), 0))} TD</span>'
                f'<span>{escape(targets)} TGT</span>'
                '</div>'
            )
        history_html = ''.join(rows) if rows else '<div class="krecv5-empty">Exact-ID history rows failed validation, so Step 5 stayed closed.</div>'

    return (
        '<section class="krecv5-wrap" aria-label="Opponent pass defense and exact-ID player versus team history">'
        '<div class="krecv5-head">'
        '<div class="krecv5-title">Opponent Pass Defense + Player vs Team History</div>'
        f'<div class="krecv5-id">ESPN athlete {escape(athlete_id)} • team {escape(team_id)} • opponent {escape(opponent_id)}</div>'
        '</div>'
        + defense_html
        + '<div class="krecv5-divider"></div>'
        + '<div class="krecv5-h2h-title"><b>Exact-ID H2H Receiving Game Books</b>'
        f'<span>vs {escape(opponent_abbr)} • up to {history_api.HISTORY_SEASONS} seasons / {history_api.HISTORY_GAME_LIMIT} games</span></div>'
        + '<div class="krecv5-history">' + history_html + '</div>'
        + '</section>'
    )


def _player_card_v5(player: dict[str, Any], team: dict[str, Any], opponent: dict[str, Any]) -> str:
    stack = _ORIGINAL_PLAYER_CARD_V4(player, team, opponent)
    context = _step5_context_html(player, team, opponent)
    return f'<div class="krecv5-player">{stack}{context}</div>'


def _advance_step5_copy(body: Any) -> Any:
    out = _ORIGINAL_ADVANCE_STEP4_COPY(body)
    if not isinstance(out, str):
        return out
    replacements = (
        (
            "Step 4 adds a verified volume + efficiency profile beneath the certified receiver stack. Target-derived fields appear only when ESPN explicitly published targets. Opponent defense, player-vs-team history, projections and FanDuel markets remain locked for their own steps.",
            "Step 5 adds exact-ID opponent pass-defense context plus verified player-vs-team receiving game-book history. Projection math and FanDuel markets remain locked for later certified steps.",
        ),
        (
            '<span class="krecv-chip">✅ VOLUME + EFFICIENCY</span>',
            '<span class="krecv-chip">✅ VOLUME + EFFICIENCY</span><span class="krecv-chip">✅ DEFENSE + H2H</span>',
        ),
        ("STEP 4 OF 10 • VOLUME + EFFICIENCY LIVE", "STEP 5 OF 10 • DEFENSE + H2H LIVE"),
        ('<span class="krecv-stage">5 • DEFENSE + H2H</span>', '<span class="krecv-stage on">5 • DEFENSE + H2H ✅</span>'),
        (
            "✅ Step 4 adds descriptive volume + efficiency context from the same validated exact-ID API payload. Catch rate and yards/target remain unavailable unless ESPN explicitly published targets.",
            "✅ Step 5 presents the certified opponent pass-defense payload and exact-ID player-vs-team receiving history. Athlete/team/opponent IDs are authoritative; names remain display-only.",
        ),
        (
            "<strong>Step 4 safety lock:</strong> Volume + efficiency is descriptive read-only exact-ID context. Opponent pass-defense presentation and player-vs-team history remain reserved for Step 5. Projection, live markets, probability, EV, Monte Carlo, rankings, recommendations, staking and wager actions remain OFF. Sportsbook projection influence: <strong>0.0%</strong>.",
            "<strong>Step 5 safety lock:</strong> Opponent pass defense and H2H are descriptive read-only exact-ID context. Projection, live markets, probability, EV, Monte Carlo, rankings, recommendations, staking and wager actions remain OFF. Player/team names are never matching keys. Sportsbook projection influence: <strong>0.0%</strong>.",
        ),
    )
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def render_nfl_receiving_yards_hub() -> None:
    st.markdown(_STEP5_CSS, unsafe_allow_html=True)
    original_card = prior._player_card_v4
    original_advance = prior._advance_step4_copy
    prior._player_card_v4 = _player_card_v5
    prior._advance_step4_copy = _advance_step5_copy
    try:
        return prior.render_nfl_receiving_yards_hub()
    finally:
        prior._player_card_v4 = original_card
        prior._advance_step4_copy = original_advance


def render_nfl_hub(market: str = "Receiving Yards") -> None:
    if str(market or "Receiving Yards") != "Receiving Yards":
        raise ValueError("NFL Receiving Yards V5 only renders the Receiving Yards market.")
    return render_nfl_receiving_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PAGE_BUILD_STEP",
    "PAGE_BUILD_TOTAL",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_advance_step5_copy",
    "_defense_context",
    "_load_history",
    "_player_card_v5",
    "_step5_context_html",
    "render_nfl_hub",
    "render_nfl_receiving_yards_hub",
]
