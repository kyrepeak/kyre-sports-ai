"""API2 NBA PRA Page 2 history-only navigation successor.

Allows a verified Page 1 history participant to open Page 2 when no current
sportsbook PRA quote is posted. The overlay never invents a line, price, edge,
or probability and delegates every market-backed selection to the frozen
existing runtime unchanged.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping

import nba_pra_runtime_v2 as _runtime
from nba_pra_injury_api_v1 import load_kyre_sports_api_nba_injuries
from nba_pra_matchup_api_v1 import load_kyre_sports_api_nba_pra_matchup
from nba_pra_page1_api_only_v1 import _select_next_upcoming_slate
from nba_pra_page2_api_only_v1 import _game_for_team, _profile_for
from nba_pra_page2_command_center_v4 import _css, build_page2_html
from nba_pra_page2_data_completeness_v1 import enrich_role_availability_context
from nba_pra_page2_matchup_v1 import build_matchup_summary
from nba_pra_page2_v1 import _baseline_model
from nba_pra_player_context_api_v1 import load_kyre_sports_api_player_context
from nba_pra_schedule_api_v1 import load_kyre_sports_api_nba_schedule
from nba_pra_team_identity_v1 import resolve_nba_team_logo

VERSION = "API2_NBA_PRA_PAGE2_HISTORY_ONLY_NAVIGATION_R1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_ORIGINAL_RENDER = _runtime.render_nba_pra_runtime_v2


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def should_render_history_only(player_key: str, handoff: Mapping[str, Any] | None) -> bool:
    payload = dict(handoff or {})
    if not player_key or _text(payload.get("player_key")) != _text(player_key):
        return False
    quote = payload.get("quote") if isinstance(payload.get("quote"), Mapping) else {}
    return _number((quote or {}).get("line")) is None


def build_history_only_context(
    snapshot: Mapping[str, Any],
    selected_player_key: str,
    handoff: Mapping[str, Any] | None,
) -> dict[str, Any]:
    profiles = snapshot.get("profiles") if isinstance(snapshot.get("profiles"), Mapping) else {}
    profile_key, profile = _profile_for({"profiles": profiles}, selected_player_key)
    payload = dict(handoff or {})
    if not profile:
        return {"state": "player_unavailable", "selected_player_key": selected_player_key}

    handoff_team = _text(payload.get("team")).upper()
    team = _text(profile.get("team")).upper() or handoff_team
    if team and not _text(profile.get("team")):
        profile = {**profile, "team": team}
    game = _game_for_team([dict(row) for row in (snapshot.get("games") or []) if isinstance(row, Mapping)], team)
    if game is None:
        return {"state": "player_unavailable", "selected_player_key": selected_player_key, "player": profile}

    away = _text(game.get("away_tricode")).upper()
    home = _text(game.get("home_tricode")).upper()
    opponent = home if team == away else away if team == home else ""
    if not opponent:
        return {"state": "player_unavailable", "selected_player_key": selected_player_key, "player": profile}

    context: dict[str, Any] = {
        "state": "history_only",
        "selected_player_key": profile_key or selected_player_key,
        "slate_date": snapshot.get("slate_date"),
        "player": profile,
        "player_name": profile.get("player_name") or payload.get("player_name") or selected_player_key,
        "team": team,
        "team_logo": resolve_nba_team_logo(team),
        "opponent": opponent,
        "opponent_logo": resolve_nba_team_logo(opponent),
        "game": game,
        "market": {},
        "quotes": [],
        "selected_quote": {},
        "current_quote": {},
        "line_moved": False,
        "line_moved_label": "",
        "availability": "UNVERIFIED",
    }
    return enrich_role_availability_context(context, snapshot)


def _history_only_result() -> dict[str, Any]:
    return {
        "lean": "PASS",
        "confidence": "NO VERIFIED MARKET",
        "tier": "NO MARKET",
        "score": None,
        "edge": None,
        "over_probability": None,
        "under_probability": None,
    }


def build_history_only_page_html(context: Mapping[str, Any], *, matchup: Mapping[str, Any]) -> str:
    profile = context.get("player") if isinstance(context.get("player"), Mapping) else {}
    model = _baseline_model(profile)
    return build_page2_html(
        context,
        model,
        _history_only_result(),
        matchup,
        active_line=None,
    )


def _load_history_only_snapshot(
    selected_player_key: str,
    handoff: Mapping[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    schedule = dict(load_kyre_sports_api_nba_schedule(now_utc=now) or {})
    slate_text, games = _select_next_upcoming_slate(list(schedule.get("games") or []), now)
    if not slate_text or not games:
        return {
            "slate_date": slate_text,
            "games": [],
            "profiles": {},
            "injury_players": {},
            "sources": {"schedule": schedule},
        }

    player_name = _text(handoff.get("player_name")) or selected_player_key
    slate_date = date.fromisoformat(slate_text)
    team_codes = sorted(
        {
            _text(code).upper()
            for game in games
            for code in (game.get("away_tricode"), game.get("home_tricode"))
            if _text(code)
        }
    )
    player_context = dict(
        load_kyre_sports_api_player_context(
            slate_date,
            [player_name],
            team_codes=team_codes,
            include_usage=True,
        )
        or {}
    )
    profile_key, profile = _profile_for(player_context, selected_player_key)
    if not profile:
        profile_key, profile = _profile_for(player_context, player_name)
    if not profile:
        return {
            "slate_date": slate_text,
            "games": [],
            "profiles": {},
            "injury_players": {},
            "sources": {"schedule": schedule, "player_context": player_context},
        }

    handoff_team = _text(handoff.get("team")).upper()
    if handoff_team and not _text(profile.get("team")):
        profile = {**profile, "team": handoff_team}
    selected_game = _game_for_team([dict(row) for row in games if isinstance(row, Mapping)], profile.get("team"))
    selected_games = [selected_game] if selected_game else []
    try:
        injury = (
            dict(load_kyre_sports_api_nba_injuries(selected_games, now_utc=now) or {})
            if selected_games
            else {"verification": "UNAVAILABLE", "players": {}, "fabrication": False}
        )
    except Exception as exc:
        injury = {
            "verification": "UNAVAILABLE",
            "diagnostic_state": type(exc).__name__,
            "players": {},
            "fabrication": False,
        }
    injuries = {
        str(key): dict(row)
        for key, row in (injury.get("players") or {}).items()
        if isinstance(row, Mapping)
    }
    canonical_key = profile_key or selected_player_key
    return {
        "slate_date": slate_text,
        "games": selected_games,
        "profiles": {canonical_key: profile, selected_player_key: profile},
        "injury_players": injuries,
        "sources": {
            "schedule": schedule,
            "player_context": player_context,
            "injuries": injury,
        },
    }


def _render_history_only_page(st: Any, player_key: str, handoff: Mapping[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown('<a class="ks-p2-top" href="#ks-nba-pra-page2-top">↑ TOP</a>', unsafe_allow_html=True)
    if st.button("← Back to PRA Board", key="nba-pra-p2-history-only-back", use_container_width=False):
        _runtime.clear_page2_state(st.session_state)
        st.rerun()

    snapshot = _load_history_only_snapshot(player_key, handoff, now=now)
    context = build_history_only_context(snapshot, player_key, handoff)
    if context.get("state") != "history_only":
        st.warning("Verified player history is temporarily unavailable. Return to the PRA board.")
        return

    opponent = _text(context.get("opponent"))
    matchup_raw = load_kyre_sports_api_nba_pra_matchup(opponent, now_utc=now) if opponent else {}
    matchup = build_matchup_summary(matchup_raw)
    st.caption("HISTORY-ONLY ANALYSIS • No verified PRA line is currently posted • No line, price, edge, or probability was invented")
    st.markdown(
        '<div class="p2-wrap">' + build_history_only_page_html(context, matchup=matchup) + '</div>',
        unsafe_allow_html=True,
    )


def render_nba_pra_runtime_history_overlay() -> None:
    import streamlit as st

    nav_phase = _text(st.session_state.get(_runtime.SESSION_NAV_PHASE))
    player_key = _runtime.selected_player_key(st.session_state)
    handoff = st.session_state.get(_runtime.SESSION_ANALYSIS_HANDOFF)
    handoff_map = handoff if isinstance(handoff, Mapping) else None
    if nav_phase == "page2" and player_key and should_render_history_only(player_key, handoff_map):
        _render_history_only_page(st, player_key, dict(handoff_map or {}))
        return
    _ORIGINAL_RENDER()


def install() -> None:
    """Install the additive history-only runtime overlay idempotently."""
    _runtime.render_nba_pra_runtime_v2 = render_nba_pra_runtime_history_overlay


__all__ = [
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "VERSION",
    "build_history_only_context",
    "build_history_only_page_html",
    "install",
    "render_nba_pra_runtime_history_overlay",
    "should_render_history_only",
]
