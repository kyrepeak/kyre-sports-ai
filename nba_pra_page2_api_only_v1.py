'''NBA PRA Page 2 selected-player loader using Kyre Sports API only.'''
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping

from nba_pra_injury_api_v1 import load_kyre_sports_api_nba_injuries
from nba_pra_market_api_v1 import load_kyre_sports_api_pra_observations
from nba_pra_player_context_api_v1 import load_kyre_sports_api_player_context
from nba_pra_schedule_api_v1 import load_kyre_sports_api_nba_schedule
from nba_pra_page1_api_only_v1 import (
    _build_board,
    _filter_payload_to_games,
    _select_next_upcoming_slate,
)


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _find_key(rows: Mapping[str, Any], requested: str) -> str | None:
    if requested in rows:
        return requested
    target=_norm(requested)
    for key in rows:
        if _norm(key)==target:
            return str(key)
    return None


def _profile_for(context: Mapping[str, Any], selected_key: str) -> tuple[str | None, dict[str, Any]]:
    profiles=context.get("profiles") or {}
    key=_find_key(profiles,selected_key)
    if key is not None:
        return key, dict(profiles.get(key) or {})
    target=_norm(selected_key)
    for key,row in profiles.items():
        if _norm((row or {}).get("player_name"))==target:
            return str(key),dict(row or {})
    return None,{}


def _game_for_team(games: list[dict[str, Any]], team: str) -> dict[str, Any] | None:
    code=str(team or "").upper()
    if not code:
        return None
    for game in games:
        away=str(game.get("away_tricode") or "").upper()
        home=str(game.get("home_tricode") or "").upper()
        if code in {away,home}:
            return dict(game)
    return None


def load_page2_snapshot_v1(
    selected_player_key: str,
    *,
    now: datetime | None = None,
    selected_player_name: str | None = None,
    selected_team: str | None = None,
    selected_quote: Mapping[str, Any] | None = None,
    schedule_loader=None,
    api_loader=None,
    player_context_loader=None,
    injury_loader=None,
) -> dict[str, Any]:
    '''Load one selected NBA PRA player deeply; never request all-player history.'''
    now_utc=now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc=now_utc.replace(tzinfo=timezone.utc)
    now_utc=now_utc.astimezone(timezone.utc)
    schedule_impl=schedule_loader or load_kyre_sports_api_nba_schedule
    market_impl=api_loader or load_kyre_sports_api_pra_observations
    context_impl=player_context_loader or load_kyre_sports_api_player_context
    injury_impl=injury_loader or load_kyre_sports_api_nba_injuries

    schedule=dict(schedule_impl(now_utc=now_utc) or {})
    slate_text,games=_select_next_upcoming_slate(list(schedule.get("games") or []),now_utc)
    if not slate_text or not games:
        return {"slate_date":slate_text,"games":[],"market":{},"profiles":{},"injury_players":{},"sources":{"schedule":schedule}}

    slate_date=date.fromisoformat(slate_text)
    market_payload=_filter_payload_to_games(dict(market_impl(slate_date) or {}),games)
    board=_build_board(market_payload)
    market_key=_find_key(board,selected_player_key)
    if market_key is None:
        handoff_name=str(selected_player_name or "").strip()
        handoff_quote=dict(selected_quote or {}) if isinstance(selected_quote,Mapping) else {}
        handoff_book=str(handoff_quote.get("sportsbook") or "").strip()
        try:
            handoff_line=float(handoff_quote.get("line"))
        except (TypeError,ValueError):
            handoff_line=None
        if not handoff_name or not handoff_book or handoff_line is None:
            return {"slate_date":slate_text,"games":[],"market":{},"profiles":{},"injury_players":{},"sources":{"schedule":schedule,"kyre_sports_api":market_payload}}
        market_key=str(selected_player_key or "").strip()
        selected_market={
            "player_name":handoff_name,
            "quotes":[handoff_quote],
            "featured_quote":handoff_quote,
            "handoff_source":"VERIFIED_PAGE1_HANDOFF",
        }
        selected_name=handoff_name
    else:
        selected_market=dict(board[market_key])
        selected_name=str(selected_market.get("player_name") or selected_player_key).strip()
    team_codes=sorted({str(code).upper() for game in games for code in (game.get("away_tricode"),game.get("home_tricode")) if code})
    if player_context_loader is None:
        context=dict(context_impl(slate_date,[selected_name],team_codes=team_codes,include_usage=True) or {})
    else:
        context=dict(context_impl(slate_date,[selected_name],team_codes=team_codes) or {})
    profile_key,profile=_profile_for(context,market_key)
    if not profile:
        return {"slate_date":slate_text,"games":[],"market":{market_key:selected_market},"profiles":{},"injury_players":{},"sources":{"schedule":schedule,"kyre_sports_api":market_payload,"player_context":context}}
    handoff_team=str(selected_team or "").strip().upper()
    if handoff_team and not str(profile.get("team") or "").strip():
        profile={**profile,"team":handoff_team}
    selected_game=_game_for_team(games,profile.get("team"))
    selected_games=[selected_game] if selected_game else []
    try:
        injury=dict(injury_impl(selected_games,now_utc=now_utc) or {}) if selected_games else {"players":{}}
    except Exception as exc:
        injury={"verification":"UNAVAILABLE","diagnostic_state":type(exc).__name__,"players":{},"fabrication":False}
    injuries={str(k):dict(v) for k,v in (injury.get("players") or {}).items() if isinstance(v,Mapping)}
    canonical_profile_key=profile_key or market_key
    if canonical_profile_key != market_key:
        profile={**profile,"player_name":profile.get("player_name") or selected_name}
    return {
        "slate_date":slate_text,
        "games":selected_games,
        "market":{market_key:selected_market},
        "profiles":{market_key:profile},
        "injury_players":injuries,
        "sources":{"schedule":schedule,"kyre_sports_api":market_payload,"player_context":context,"injuries":injury},
    }
