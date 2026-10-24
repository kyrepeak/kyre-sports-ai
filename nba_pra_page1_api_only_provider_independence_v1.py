"""NBA PRA Page 1 provider-independence overlay.

Keeps the frozen API-only snapshot path, but when sportsbook PRA is legitimately
absent it preserves verified current-season recent participants returned by the
Kyre Sports API. Those profiles are history evidence, not an official roster and
never create a sportsbook line, price, edge, or probability.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import nba_pra_page1_api_only_v1 as prior


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split())


def _slate_team_codes(games: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        _text(code).upper()
        for game in games
        for code in (game.get("away_tricode"), game.get("home_tricode"))
        if _text(code)
    }


def _participant_profiles(payload: Mapping[str, Any], games: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    teams = _slate_team_codes(games)
    rows = payload.get("recent_participant_profiles") or {}
    if not isinstance(rows, Mapping):
        return {}
    return {
        str(key): dict(row)
        for key, row in rows.items()
        if isinstance(row, Mapping) and _text(row.get("team")).upper() in teams
    }


def load_page1_snapshot_v2(
    *,
    now=None,
    schedule_loader=None,
    api_loader=None,
    player_context_loader=None,
    injury_loader=None,
    **compat,
):
    snapshot = prior.load_page1_snapshot_v2(
        now=now,
        schedule_loader=schedule_loader,
        api_loader=api_loader,
        player_context_loader=player_context_loader,
        injury_loader=injury_loader,
        **compat,
    )
    if snapshot.get("market") or snapshot.get("profiles") or not snapshot.get("games"):
        return snapshot

    sources = dict(snapshot.get("sources") or {})
    market_payload = dict(sources.get("kyre_sports_api") or {})
    profiles = _participant_profiles(market_payload, list(snapshot.get("games") or []))
    if not profiles:
        return snapshot

    snapshot["profiles"] = profiles
    source_state = str(market_payload.get("recent_participant_state") or "RECENT_PARTICIPANT_POOL")
    sources["kyre_player_context"] = {
        "source": "Kyre Sports API — current-season history participant pool",
        "verification": "PARTIAL",
        "diagnostic_state": source_state,
        "requested_players": 0,
        "verified_players": 0,
        "identified_players": len(profiles),
        "fabrication": False,
    }

    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_utc = now_utc.astimezone(timezone.utc)
    injury_impl = injury_loader or prior.load_kyre_sports_api_nba_injuries
    try:
        injuries = dict(injury_impl(list(snapshot.get("games") or []), now_utc=now_utc) or {})
    except Exception as exc:
        injuries = {
            "source": "Kyre Sports API — Vercel",
            "verification": "UNAVAILABLE",
            "diagnostic_state": f"INJURY_GATEWAY_ERROR:{type(exc).__name__}",
            "players": {},
            "fabrication": False,
        }
    snapshot["injury_players"] = {
        str(key): dict(row)
        for key, row in (injuries.get("players") or {}).items()
        if isinstance(row, Mapping)
    }
    sources["injuries"] = injuries
    snapshot["sources"] = sources
    return snapshot


__all__ = ["load_page1_snapshot_v2"]
