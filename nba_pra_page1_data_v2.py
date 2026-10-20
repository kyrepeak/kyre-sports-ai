"""NBA PRA Page 1 V2 — type-routed, upcoming-only snapshot."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable, Mapping

from nba_pra_page1_data_v1 import flatten_injury_players
from nba_pra_page1_history_v1 import build_player_profiles
from nba_pra_page1_sgo_v1 import load_sgo_pra_observations
from nba_pra_page1_sources_v2 import (
    build_sportsbook_board,
    load_approved_odds_api_pra_observations,
    load_nba_stats_profiles,
    route_player_profiles,
    select_featured_quote,
    select_next_upcoming_slate,
)

MODEL_VERSION = "NBA PRA PAGE 1 COMMAND CENTER V2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _default_schedule_loader(**kwargs):
    from nba_spread_schedule_provider_resilience_step2_r1 import load_verified_nba_schedule
    return load_verified_nba_schedule(**kwargs)


def _default_injury_loader(games, *, now_utc):
    from nba_spread_injury_availability_v1 import _fetch_official_rows, build_game_injury_features
    official_rows, meta = _fetch_official_rows(games, now_utc)
    available = bool(meta.get("available"))
    return build_game_injury_features(
        games,
        official_rows=official_rows if available else [],
        espn_rows=[],
        official_available=available,
        espn_available=False,
        fetched_at_utc=meta.get("reported_at_utc") if available else None,
        now_utc=now_utc,
    )


def _backup_loader_for(games, board):
    def load(names, slate_date):
        wanted = {"".join(ch for ch in str(name).casefold() if ch.isalnum()) for name in names}
        market = {key: {"player_name": entry.get("player_name")} for key, entry in board.items() if key in wanted}
        profiles = build_player_profiles(games, market, slate_date)
        for value in profiles.values():
            value["stats_source"] = "ESPN backup"
        return profiles
    return load


def load_page1_snapshot_v2(
    *,
    now: datetime | None = None,
    schedule_loader: Callable[..., Mapping[str, Any]] | None = None,
    sgo_loader: Callable[[date], Mapping[str, Any]] | None = None,
    odds_loader: Callable[[date], Mapping[str, Any]] | None = None,
    official_profile_loader: Callable[[date], Mapping[str, Any]] | None = None,
    backup_profile_loader=None,
    injury_loader=None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    schedule_loader = schedule_loader or _default_schedule_loader
    schedule = dict(schedule_loader(now_utc=now) or {})
    slate_text, games = select_next_upcoming_slate(list(schedule.get("games") or []), now)
    empty = {
        "verification": schedule.get("verification", "UNAVAILABLE"),
        "slate_date": slate_text,
        "games": games,
        "market": {},
        "profiles": {},
        "injury_players": {},
        "sources": {"schedule": schedule},
        "sportsbook_projection_influence": 0.0,
    }
    if not slate_text or not games:
        return empty
    slate_date = date.fromisoformat(slate_text)
    sgo_loader = sgo_loader or load_sgo_pra_observations
    odds_loader = odds_loader or load_approved_odds_api_pra_observations
    sgo, odds = dict(sgo_loader(slate_date) or {}), dict(odds_loader(slate_date) or {})
    board = build_sportsbook_board(sgo, odds)
    market = {}
    for key, entry in board.items():
        featured = select_featured_quote(entry)
        if featured is not None:
            market[key] = {**entry, "featured_quote": featured}
    if not market:
        return {**empty, "sources": {"schedule": schedule, "sgo": sgo, "odds_api": odds}}
    official_profile_loader = official_profile_loader or load_nba_stats_profiles
    backup_profile_loader = backup_profile_loader or _backup_loader_for(games, market)
    profiles = route_player_profiles(
        [entry["player_name"] for entry in market.values()],
        slate_date,
        official_loader=official_profile_loader,
        backup_loader=backup_profile_loader,
    )
    injury_loader = injury_loader or _default_injury_loader
    try:
        injury_payload = dict(injury_loader(games, now_utc=now) or {})
    except Exception:
        injury_payload = {"verification": "UNAVAILABLE", "features": []}
    return {
        "verification": schedule.get("verification", "UNAVAILABLE"),
        "slate_date": slate_text,
        "games": games,
        "market": market,
        "profiles": profiles,
        "injury_players": flatten_injury_players(injury_payload),
        "sources": {"schedule": schedule, "sgo": sgo, "odds_api": odds, "injuries": injury_payload},
        "sportsbook_projection_influence": 0.0,
    }
