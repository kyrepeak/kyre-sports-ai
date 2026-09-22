"""Step 6H verified live transport for official roster + slate reconciliation.

The reconciliation core remains evidence-only.  Live DraftKings reads reuse the
exact Step 6D/6G GET transport that already passed shadow CI.  Official slate
reads reuse the established WNBA schedule collector.  Current roster membership
is verified against official WNBA team roster pages, avoiding dependence on the
stats.wnba.com endpoint when that service blocks or times out on hosted runners.

No production feed is written.  No scheduler/runtime flag is changed, no
sportsbook authentication/cookies are used, and no Monte Carlo or wager action
is performed.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date as date_type, timedelta
from html.parser import HTMLParser
import hashlib
import json
from typing import Any
from urllib.parse import urlparse

import httpx

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
from sports_api.wnba_schedule import get_daily_schedule_dataset

MODEL_SOURCE = "Kyre Sports API WNBA Step 6H verified live transport adapter"
MODEL_VERSION = "wnba_step_6h_verified_live_transport_v2"
MAX_SCHEDULE_LOOKAHEAD_DAYS = 4
MAX_ROSTER_PAGE_BYTES = 5_000_000

TEAM_ROSTER_HOSTS = {
    "atlanta dream": "dream.wnba.com",
    "chicago sky": "sky.wnba.com",
    "connecticut sun": "sun.wnba.com",
    "dallas wings": "wings.wnba.com",
    "golden state valkyries": "valkyries.wnba.com",
    "indiana fever": "fever.wnba.com",
    "las vegas aces": "aces.wnba.com",
    "los angeles sparks": "sparks.wnba.com",
    "minnesota lynx": "lynx.wnba.com",
    "new york liberty": "liberty.wnba.com",
    "phoenix mercury": "mercury.wnba.com",
    "portland fire": "fire.wnba.com",
    "seattle storm": "storm.wnba.com",
    "toronto tempo": "tempo.wnba.com",
    "washington mystics": "mystics.wnba.com",
}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data).strip()
        if text:
            self.parts.append(text)


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _team_registry(season: int) -> list[dict[str, Any]]:
    return [dict(row) for row in get_wnba_teams(int(season))]


def _team_by_name(season: int) -> dict[str, dict[str, Any]]:
    return {_name_key(row["full_name"]): row for row in _team_registry(season)}


def _official_roster_url(team_name: str) -> str:
    key = _name_key(team_name)
    host = TEAM_ROSTER_HOSTS.get(key)
    if not host:
        raise RuntimeError(f"No official WNBA roster host is registered for {team_name!r}.")
    return f"https://{host}/roster"


def _fetch_official_roster_text(team_name: str, *, timeout_seconds: float) -> dict[str, Any]:
    url = _official_roster_url(team_name)
    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (compatible; kyre-sports-api/wnba-step6h; +official-roster-verification)",
    }
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        raise RuntimeError(f"Official WNBA roster page GET failed for {team_name}.") from exc
    if response.status_code != 200:
        raise RuntimeError(f"Official WNBA roster page returned HTTP {response.status_code} for {team_name}.")
    raw = response.content
    if len(raw) <= 0 or len(raw) > MAX_ROSTER_PAGE_BYTES:
        raise RuntimeError(f"Official WNBA roster page size was invalid for {team_name}.")
    parser = _VisibleTextParser()
    parser.feed(response.text)
    normalized = _name_key(" ".join(parser.parts))
    marker = _name_key("2026 Team Roster")
    start = normalized.find(marker)
    if start < 0:
        raise RuntimeError(f"Official WNBA roster marker was not found for {team_name}.")
    end_marker = _name_key("Coaching Staff")
    end = normalized.find(end_marker, start + len(marker))
    roster_text = normalized[start:end if end >= 0 else None]
    if len(roster_text) < 40:
        raise RuntimeError(f"Official WNBA roster section was unexpectedly short for {team_name}.")
    return {
        "team_name": team_name,
        "host": urlparse(url).hostname,
        "url": url,
        "http_status": 200,
        "roster_text": f" {roster_text} ",
        "content_sha256": hashlib.sha256(raw).hexdigest(),
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
    if not events_by_id:
        raise RuntimeError("Verified DraftKings transport returned no event metadata.")

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


def _fetch_verified_schedule(*, date: str, season: int) -> dict[str, Any]:
    target = date_type.fromisoformat(str(date))
    registry = _team_by_name(season)
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
            home_name = home.get("full_name")
            away_name = away.get("full_name")
            if not game_id or not home_name or not away_name:
                continue
            home_registry = registry.get(_name_key(home_name))
            away_registry = registry.get(_name_key(away_name))
            if not home_registry or not away_registry:
                continue
            if home.get("official_team_id") is None or away.get("official_team_id") is None:
                continue
            games_by_id[str(game_id)] = {
                "game_id": str(game_id),
                "game_date": game_date,
                "home_team_id": str(home["official_team_id"]),
                "home_team_name": home_registry["full_name"],
                "home_team_key": _name_key(home_registry["full_name"]),
                "away_team_id": str(away["official_team_id"]),
                "away_team_name": away_registry["full_name"],
                "away_team_key": _name_key(away_registry["full_name"]),
                "status_category": (row.get("status") or {}).get("category"),
                "playable_pregame": bool((row.get("verification") or {}).get("playable_pregame")),
                "schedule_changed": bool((row.get("schedule_change") or {}).get("schedule_changed")),
            }
    if not games_by_id:
        raise RuntimeError("Official WNBA schedule collector returned no near-term games.")
    return {
        "games": sorted(games_by_id.values(), key=lambda row: (row["game_date"], row["game_id"])),
        "source_summary": schedule_sources,
    }


def fetch_verified_official_snapshot(*, date: str, season: int, draftkings: dict[str, Any], env=None) -> dict[str, Any]:
    """Verify only the official teams/players actually present on the DK board."""
    environment = {} if env is None else env
    timeout_seconds = _timeout(environment)
    schedule = _fetch_verified_schedule(date=date, season=season)
    games = schedule["games"]
    registry = _team_by_name(season)

    official_team_id_by_key: dict[str, str] = {}
    for game in games:
        official_team_id_by_key[game["home_team_key"]] = game["home_team_id"]
        official_team_id_by_key[game["away_team_key"]] = game["away_team_id"]

    needed_team_keys: set[str] = set()
    event_teams: dict[str, list[str]] = {}
    for event in draftkings.get("source_events") or []:
        event_id = str(event.get("source_event_id") or "")
        resolved: list[str] = []
        for participant in event.get("participants") or []:
            key = _name_key(participant)
            if key in registry:
                resolved.append(key)
                needed_team_keys.add(key)
        event_teams[event_id] = sorted(set(resolved))

    if not needed_team_keys:
        raise RuntimeError("DraftKings events could not be mapped to official WNBA team names.")

    roster_pages: dict[str, dict[str, Any]] = {}
    for team_key in sorted(needed_team_keys):
        team = registry[team_key]
        roster_pages[team_key] = _fetch_official_roster_text(team["full_name"], timeout_seconds=timeout_seconds)

    players_for_event: dict[str, set[str]] = defaultdict(set)
    display_name_by_key: dict[str, str] = {}
    for offer in draftkings.get("offers") or []:
        event_id = str(offer.get("source_event_id") or "")
        player_name = str(offer.get("player_name") or "").strip()
        key = _name_key(player_name)
        if event_id and key:
            players_for_event[event_id].add(key)
            display_name_by_key.setdefault(key, player_name)

    player_team_matches: dict[str, set[str]] = defaultdict(set)
    for event_id, player_keys in players_for_event.items():
        candidate_teams = event_teams.get(event_id) or []
        if len(candidate_teams) != 2:
            raise RuntimeError(f"DraftKings event {event_id} did not resolve to exactly two official WNBA teams.")
        for player_key in player_keys:
            needle = f" {player_key} "
            for team_key in candidate_teams:
                if needle in roster_pages[team_key]["roster_text"]:
                    player_team_matches[player_key].add(team_key)

    players: list[dict[str, Any]] = []
    roster_mismatches: list[dict[str, Any]] = []
    for player_key, player_name in sorted(display_name_by_key.items()):
        matches = sorted(player_team_matches.get(player_key) or [])
        if len(matches) != 1:
            roster_mismatches.append(
                {
                    "player_name": player_name,
                    "official_team_match_count": len(matches),
                    "candidate_team_keys": matches,
                }
            )
            continue
        team_key = matches[0]
        team = registry[team_key]
        official_team_id = official_team_id_by_key.get(_name_key(team["full_name"]))
        if not official_team_id:
            roster_mismatches.append(
                {"player_name": player_name, "official_team_match_count": 1, "reason": "official_team_id_missing"}
            )
            continue
        players.append(
            {
                "player_id": None,
                "player_name": player_name,
                "player_key": player_key,
                "team_id": official_team_id,
                "team_name": team["full_name"],
                "team_key": _name_key(team["full_name"]),
                "team_abbreviation": team.get("abbreviation"),
                "roster_status": 1,
                "roster_source": "official_wnba_team_roster_page",
            }
        )

    if roster_mismatches:
        names = ", ".join(row["player_name"] for row in roster_mismatches[:8])
        raise RuntimeError(f"Official WNBA roster-page verification failed for {len(roster_mismatches)} player(s): {names}")
    if not players:
        raise RuntimeError("Official WNBA roster pages verified no DraftKings players.")

    return {
        "season": int(season),
        "players": players,
        "games": games,
        "source_summary": {
            "roster": [
                {
                    "team_name": registry[key]["full_name"],
                    "host": roster_pages[key]["host"],
                    "http_status": roster_pages[key]["http_status"],
                    "content_sha256": roster_pages[key]["content_sha256"],
                }
                for key in sorted(roster_pages)
            ],
            "verified_draftkings_player_count": len(players),
            "schedule": schedule["source_summary"],
        },
    }


def run_live_official_reconciliation(*, date: str, season: int, env=None) -> dict[str, Any]:
    draftkings = fetch_verified_draftkings_snapshot(date=date, season=season, env=env)
    official = fetch_verified_official_snapshot(date=date, season=season, draftkings=draftkings, env=env)
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
