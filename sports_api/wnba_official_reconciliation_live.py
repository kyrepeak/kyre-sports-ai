"""Step 6H live transport adapter using already-vetted WNBA/DraftKings collectors.

The Step 6H reconciliation core is deliberately pure/evidence-only.  This
adapter fixes live transport drift by reusing the exact DraftKings GET transport
that already passed Step 6G and the official WNBA roster/schedule collectors
introduced earlier in the API build.

No production market feed is written here.  No scheduler/runtime flag is
changed, no sportsbook authentication/cookies are used, and no Monte Carlo or
wager action is performed.
"""
from __future__ import annotations

from datetime import date as date_type, timedelta
import hashlib
import json
from typing import Any
from urllib.parse import urlparse

from sports_api.collectors.wnba_draftkings_direct import (
    _get as _draftkings_get,
    _response_json as _draftkings_response_json,
    normalize_draftkings_document,
)
from sports_api.wnba_draftkings_shadow_ingestion import frozen_draftkings_urls
from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_official_reconciliation import (
    _iso_now,
    _name_key,
    _timeout,
    extract_draftkings_events,
    reconcile_snapshot,
)
from sports_api.wnba_rosters import get_current_players_dataset
from sports_api.wnba_schedule import get_daily_schedule_dataset

MODEL_SOURCE = "Kyre Sports API WNBA Step 6H verified live transport adapter"
MODEL_VERSION = "wnba_step_6h_verified_live_transport_v1"
MAX_SCHEDULE_LOOKAHEAD_DAYS = 4


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _official_team_map(season: int) -> dict[str, dict[str, Any]]:
    return {str(row["team_key"]): dict(row) for row in get_wnba_teams(season)}


def fetch_verified_official_snapshot(*, date: str, season: int) -> dict[str, Any]:
    """Read official current rosters and the bounded near-term official slate."""
    target = date_type.fromisoformat(str(date))
    team_map = _official_team_map(int(season))

    roster = get_current_players_dataset(int(season), current_roster_only=True)
    players: list[dict[str, Any]] = []
    for row in roster.get("players") or []:
        team_key = row.get("team_key")
        team = team_map.get(str(team_key)) if team_key else None
        player_name = row.get("full_name")
        player_id = row.get("player_id")
        team_id = row.get("official_team_id")
        if not player_name or player_id is None or team_id is None or not team:
            continue
        players.append(
            {
                "player_id": str(player_id),
                "player_name": str(player_name),
                "player_key": _name_key(player_name),
                "team_id": str(team_id),
                "team_name": team["full_name"],
                "team_key": _name_key(team["full_name"]),
                "team_abbreviation": team.get("abbreviation"),
                "roster_status": 1,
            }
        )

    games_by_id: dict[str, dict[str, Any]] = {}
    schedule_sources: list[dict[str, Any]] = []
    for offset in range(MAX_SCHEDULE_LOOKAHEAD_DAYS + 1):
        game_date = (target + timedelta(days=offset)).isoformat()
        dataset = get_daily_schedule_dataset(game_date, int(season))
        schedule_sources.append(
            {
                "date": game_date,
                "source": dataset.get("source"),
                "source_variant": dataset.get("source_variant"),
                "source_game_count": dataset.get("source_game_count"),
                "normalized_game_count": dataset.get("game_count"),
            }
        )
        for row in dataset.get("games") or []:
            game_id = row.get("game_id")
            home = row.get("home") or {}
            away = row.get("away") or {}
            if not game_id or not home.get("official_team_id") or not away.get("official_team_id"):
                continue
            home_team = team_map.get(str(home.get("team_key")))
            away_team = team_map.get(str(away.get("team_key")))
            if not home_team or not away_team:
                continue
            games_by_id[str(game_id)] = {
                "game_id": str(game_id),
                "game_date": game_date,
                "home_team_id": str(home["official_team_id"]),
                "home_team_name": home_team["full_name"],
                "home_team_key": _name_key(home_team["full_name"]),
                "away_team_id": str(away["official_team_id"]),
                "away_team_name": away_team["full_name"],
                "away_team_key": _name_key(away_team["full_name"]),
                "status_category": (row.get("status") or {}).get("category"),
                "playable_pregame": bool((row.get("verification") or {}).get("playable_pregame")),
                "schedule_changed": bool((row.get("schedule_change") or {}).get("schedule_changed")),
            }

    if not players:
        raise RuntimeError("Verified WNBA roster collector returned no active players.")
    if not games_by_id:
        raise RuntimeError("Verified WNBA schedule collector returned no near-term games.")

    return {
        "season": int(season),
        "players": players,
        "games": sorted(games_by_id.values(), key=lambda row: (row["game_date"], row["game_id"])),
        "source_summary": {
            "roster": {
                "source": roster.get("source"),
                "source_endpoint": roster.get("source_endpoint"),
                "retrieved_at_utc": roster.get("retrieved_at_utc"),
                "active_player_count": len(players),
            },
            "schedule": schedule_sources,
        },
    }


def fetch_verified_draftkings_snapshot(*, date: str, season: int, env=None) -> dict[str, Any]:
    """Use the exact Step 6D/6G DraftKings transport that passed live shadow CI."""
    environment = {} if env is None else env
    timeout_seconds = _timeout(environment)
    captured = _iso_now()
    offers: list[dict[str, Any]] = []
    events_by_id: dict[str, dict[str, Any]] = {}
    source_summary: list[dict[str, Any]] = []

    for index, url in enumerate(frozen_draftkings_urls()):
        response = _draftkings_get(url, timeout_seconds=timeout_seconds, requester=None)
        document = _draftkings_response_json(response, url=url)
        normalized = normalize_draftkings_document(document, captured_at_utc=captured)
        for event in extract_draftkings_events(document):
            existing = events_by_id.get(event["source_event_id"])
            if existing is None or len(event.get("participant_keys") or []) > len(existing.get("participant_keys") or []):
                events_by_id[event["source_event_id"]] = event
        offers.extend(normalized)
        source_summary.append(
            {
                "source_index": index,
                "host": (urlparse(url).hostname or "").casefold(),
                "http_status": 200,
                "normalized_offer_count": len(normalized),
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for offer in offers:
        source_offer_id = offer.get("source_offer_id")
        identity = str(source_offer_id) if source_offer_id else _hash(offer)
        if identity not in seen:
            deduped.append(offer)
            seen.add(identity)
    if not deduped:
        raise RuntimeError("Verified DraftKings transport returned no supported WNBA offers.")

    return {
        "schema_version": "wnba_step_6c_owned_market_feed_v1",
        "date": str(date),
        "season": int(season),
        "captured_at_utc": captured,
        "feed_source": "DraftKings Step 6D/6G verified public GET transport -> Step 6H shadow snapshot",
        "feed_format": "canonical_offers_v1",
        "odds_format": "american",
        "offers": deduped,
        "source_events": sorted(events_by_id.values(), key=lambda row: row["source_event_id"]),
        "source_summary": source_summary,
    }


def run_live_official_reconciliation(*, date: str, season: int, env=None) -> dict[str, Any]:
    draftkings = fetch_verified_draftkings_snapshot(date=date, season=season, env=env)
    official = fetch_verified_official_snapshot(date=date, season=season)
    report = reconcile_snapshot(
        draftkings,
        official_players=official["players"],
        official_games=official["games"],
        draftkings_events=draftkings["source_events"],
    )
    report["live_transport_source"] = MODEL_SOURCE
    report["live_transport_model_version"] = MODEL_VERSION
    report["draftkings_source_summary"] = draftkings["source_summary"]
    report["official_source_summary"] = official["source_summary"]
    report["safety"]["http_methods"] = ["GET"]
    report["safety"]["production_feed_written"] = False
    report["safety"]["direct_sync_enablement_changed"] = False
    report["safety"]["production_runtime_enablement_changed"] = False
    report["safety"]["scheduler_enablement_changed"] = False
    return report
