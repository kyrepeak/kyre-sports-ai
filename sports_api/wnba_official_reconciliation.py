"""WNBA Step 6H official roster + slate reconciliation gate.

Step 6G proved the frozen DraftKings WNBA player-prop endpoints can be
normalized into Kyre's canonical feed without touching production. Step 6H
adds a second read-only gate: every DraftKings player must exist on the current
official WNBA roster and every DraftKings event must reconcile to the official
WNBA schedule before automatic syncing can be considered activation-ready.

This module is evidence-only. It never writes the production market feed,
enables a scheduler/runtime, places a wager, or runs Monte Carlo.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import date as date_type, datetime, timedelta, timezone
import hashlib
import json
import os
import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

import httpx

from sports_api.collectors.wnba_draftkings_direct import normalize_draftkings_document
from sports_api.wnba_draftkings_shadow_ingestion import (
    REQUIRED_STATS,
    frozen_draftkings_urls,
    validate_shadow_feed,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6H official roster + slate reconciliation"
MODEL_VERSION = "wnba_step_6h_official_reconciliation_v1"
SCHEMA_VERSION = MODEL_VERSION
WNBA_LEAGUE_ID = "10"
OFFICIAL_SCHEDULE_URL = "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json"
OFFICIAL_PLAYERS_BASE_URL = "https://stats.wnba.com/stats/commonallplayers"
TIMEOUT_ENV = "WNBA_OFFICIAL_RECONCILIATION_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_RESPONSE_BYTES = 20_000_000
MAX_SCHEDULE_LOOKAHEAD_DAYS = 4
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class WNBAOfficialReconciliationError(RuntimeError):
    pass


class WNBAOfficialReconciliationInputError(WNBAOfficialReconciliationError):
    pass


class WNBAOfficialReconciliationUpstreamError(WNBAOfficialReconciliationError):
    pass


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _name_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean(value) or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _date(value: Any) -> str | None:
    text = _clean(value)
    if not text:
        return None
    if _DATE_RE.fullmatch(text[:10]):
        return text[:10]
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except ValueError:
        return None


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _timeout(env: Mapping[str, str]) -> float:
    raw = _clean(env.get(TIMEOUT_ENV))
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError as exc:
        raise WNBAOfficialReconciliationInputError(f"{TIMEOUT_ENV} must be numeric.") from exc
    if not 0.5 <= value <= MAX_TIMEOUT_SECONDS:
        raise WNBAOfficialReconciliationInputError(
            f"{TIMEOUT_ENV} must be between 0.5 and {MAX_TIMEOUT_SECONDS} seconds."
        )
    return value


def _official_players_url(season: int) -> str:
    # Parameter order is intentional: this matches the WNBA Stats client.
    return (
        f"{OFFICIAL_PLAYERS_BASE_URL}?"
        f"IsOnlyCurrentSeason=1&LeagueID={WNBA_LEAGUE_ID}&Season={int(season)}"
    )


def _headers(url: str) -> dict[str, str]:
    host = (urlparse(url).hostname or "").casefold()
    referer = "https://www.wnba.com/"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": referer,
        "Origin": "https://www.wnba.com",
    }
    if host.endswith("draftkings.com"):
        headers["Referer"] = "https://sportsbook.draftkings.com/leagues/basketball/wnba"
        headers.pop("Origin", None)
    return headers


def _get_json(
    url: str,
    *,
    requester: Callable[..., Any] | None,
    timeout_seconds: float,
) -> Any:
    try:
        if requester is not None:
            try:
                response = requester(url, headers=_headers(url), timeout=timeout_seconds)
            except TypeError:
                response = requester("GET", url, headers=_headers(url), timeout=timeout_seconds)
        else:
            with httpx.Client(timeout=timeout_seconds, follow_redirects=False, headers=_headers(url)) as client:
                response = client.get(url)
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        raise WNBAOfficialReconciliationUpstreamError(f"GET failed for {urlparse(url).hostname}.") from exc
    status = getattr(response, "status_code", None)
    if status != 200:
        raise WNBAOfficialReconciliationUpstreamError(
            f"GET returned HTTP {status if status is not None else 'unknown'} for {urlparse(url).hostname}."
        )
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)) and len(content) > MAX_RESPONSE_BYTES:
        raise WNBAOfficialReconciliationUpstreamError("Official reconciliation response exceeded size limit.")
    try:
        document = response.json()
    except Exception as exc:
        raise WNBAOfficialReconciliationUpstreamError("Official reconciliation endpoint returned invalid JSON.") from exc
    if not isinstance(document, dict):
        raise WNBAOfficialReconciliationUpstreamError("Official reconciliation endpoint returned a non-object JSON payload.")
    return document


def _result_set_rows(document: Mapping[str, Any], wanted_name: str) -> list[dict[str, Any]]:
    result_sets = document.get("resultSets") or document.get("resultSet") or []
    if isinstance(result_sets, dict):
        result_sets = [result_sets]
    if not isinstance(result_sets, list):
        return []
    for result in result_sets:
        if not isinstance(result, dict):
            continue
        if _name_key(result.get("name")) != _name_key(wanted_name):
            continue
        headers = result.get("headers") or []
        rows = result.get("rowSet") or result.get("rows") or []
        if not isinstance(headers, list) or not isinstance(rows, list):
            return []
        output: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, list):
                output.append({str(headers[i]): row[i] if i < len(row) else None for i in range(len(headers))})
            elif isinstance(row, dict):
                output.append(dict(row))
        return output
    return []


def parse_official_players(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _result_set_rows(document, "CommonAllPlayers")
    players: list[dict[str, Any]] = []
    for row in rows:
        player_name = _clean(row.get("DISPLAY_FIRST_LAST") or row.get("PLAYER") or row.get("PLAYER_NAME"))
        player_id = _clean(row.get("PERSON_ID") or row.get("PLAYER_ID"))
        team_id = _clean(row.get("TEAM_ID") or row.get("TeamID"))
        team_name = _clean(row.get("TEAM_NAME"))
        roster_status = row.get("ROSTERSTATUS", row.get("ROSTER_STATUS"))
        if roster_status is not None and str(roster_status).strip().casefold() not in {"1", "true", "active"}:
            continue
        if not player_name or not player_id or not team_id or team_id == "0" or not team_name:
            continue
        players.append(
            {
                "player_id": player_id,
                "player_name": player_name,
                "player_key": _name_key(player_name),
                "team_id": team_id,
                "team_name": team_name,
                "team_key": _name_key(team_name),
                "team_abbreviation": _clean(row.get("TEAM_ABBREVIATION")),
                "roster_status": 1,
            }
        )
    return players


def _team_from_schedule(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    team_id = _clean(value.get("teamId") or value.get("teamID") or value.get("id"))
    city = _clean(value.get("teamCity") or value.get("city"))
    name = _clean(value.get("teamName") or value.get("name"))
    full = " ".join(part for part in (city, name) if part).strip()
    if not full:
        full = _clean(value.get("teamFullName") or value.get("fullName")) or ""
    if not team_id or not full:
        return None
    return {
        "team_id": team_id,
        "team_name": full,
        "team_key": _name_key(full),
        "team_abbreviation": _clean(value.get("teamTricode") or value.get("teamAbbreviation")),
    }


def parse_official_schedule(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    league = document.get("leagueSchedule")
    if not isinstance(league, dict):
        return []
    game_dates = league.get("gameDates") or []
    if not isinstance(game_dates, list):
        return []
    games: list[dict[str, Any]] = []
    seen: set[str] = set()
    for date_group in game_dates:
        if not isinstance(date_group, dict):
            continue
        group_date = _date(date_group.get("gameDate"))
        for game in date_group.get("games") or []:
            if not isinstance(game, dict):
                continue
            game_id = _clean(game.get("gameId") or game.get("gameID") or game.get("id"))
            home = _team_from_schedule(game.get("homeTeam"))
            away = _team_from_schedule(game.get("awayTeam"))
            game_date = (
                group_date
                or _date(game.get("gameDateEst"))
                or _date(game.get("gameDateTimeEst"))
                or _date(game.get("gameDateTimeUTC"))
            )
            if not game_id or not home or not away or not game_date or game_id in seen:
                continue
            seen.add(game_id)
            games.append(
                {
                    "game_id": game_id,
                    "game_date": game_date,
                    "home_team_id": home["team_id"],
                    "home_team_name": home["team_name"],
                    "home_team_key": home["team_key"],
                    "away_team_id": away["team_id"],
                    "away_team_name": away["team_name"],
                    "away_team_key": away["team_key"],
                }
            )
    return games


def _participant_name(value: Any) -> str | None:
    if isinstance(value, str):
        return _clean(value)
    if isinstance(value, dict):
        return _clean(value.get("name") or value.get("fullName") or value.get("participantName"))
    return None


def extract_draftkings_events(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    containers = [document]
    if isinstance(document.get("eventGroup"), dict):
        containers.append(document["eventGroup"])
    for source in containers:
        events = source.get("events") if isinstance(source, dict) else None
        if isinstance(events, list):
            candidates.extend(events)
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in candidates:
        if not isinstance(row, dict):
            continue
        event_id = _clean(row.get("id") or row.get("eventId"))
        if not event_id or event_id in seen:
            continue
        participants = []
        for participant in row.get("participants") or []:
            name = _participant_name(participant)
            if name:
                participants.append(name)
        event_date = None
        for field in (
            "startEventDate",
            "startDate",
            "startDateTime",
            "startTime",
            "eventDate",
            "date",
        ):
            event_date = _date(row.get(field))
            if event_date:
                break
        seen.add(event_id)
        output.append(
            {
                "source_event_id": event_id,
                "event_name": _clean(row.get("name") or row.get("eventName")),
                "event_date": event_date,
                "participants": participants,
                "participant_keys": sorted({_name_key(name) for name in participants if _name_key(name)}),
            }
        )
    return output


def get_reconciliation_readiness() -> dict[str, Any]:
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6h_official_reconciliation_readiness",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "official_sources": [
            {"role": "slate", "host": "cdn.wnba.com", "endpoint": "/static/json/staticData/scheduleLeagueV2.json"},
            {"role": "current_roster", "host": "stats.wnba.com", "endpoint": "/stats/commonallplayers"},
        ],
        "required_checks": [
            "step6g_shadow_feed_valid",
            "official_player_identity",
            "official_current_roster_membership",
            "official_event_team_pair",
            "official_event_date_or_unique_near_term_match",
            "market_player_game_consistency",
        ],
        "automatic_sync_enabled_by_step6h": False,
        "production_runtime_enabled_by_step6h": False,
        "scheduler_enabled_by_step6h": False,
        "safety": {
            "http_methods": ["GET"],
            "authentication_used": False,
            "cookies_used": False,
            "wager_action_performed": False,
            "production_feed_written": False,
            "paid_odds_vendor_used": False,
            "monte_carlo_run": False,
        },
    }


def fetch_official_snapshot(
    *,
    season: int,
    requester: Callable[..., Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    try:
        season_int = int(season)
    except (TypeError, ValueError) as exc:
        raise WNBAOfficialReconciliationInputError("Step 6H season must be an integer.") from exc
    environment = _environment(env)
    timeout_seconds = _timeout(environment)
    schedule_doc = _get_json(OFFICIAL_SCHEDULE_URL, requester=requester, timeout_seconds=timeout_seconds)
    league_schedule = schedule_doc.get("leagueSchedule") if isinstance(schedule_doc.get("leagueSchedule"), dict) else {}
    schedule_season = _clean(league_schedule.get("seasonYear"))
    if schedule_season and schedule_season[:4].isdigit() and int(schedule_season[:4]) != season_int:
        raise WNBAOfficialReconciliationUpstreamError(
            f"Official WNBA CDN schedule season {schedule_season!r} does not match requested season {season_int}."
        )
    players_url = _official_players_url(season_int)
    players_doc = _get_json(players_url, requester=requester, timeout_seconds=timeout_seconds)
    games = parse_official_schedule(schedule_doc)
    players = parse_official_players(players_doc)
    if not games:
        raise WNBAOfficialReconciliationUpstreamError("Official WNBA schedule returned no parseable games.")
    if not players:
        raise WNBAOfficialReconciliationUpstreamError("Official WNBA current-player endpoint returned no active roster players.")
    return {
        "season": season_int,
        "players": players,
        "games": games,
        "source_summary": [
            {"role": "slate", "host": "cdn.wnba.com", "http_status": 200, "game_count": len(games)},
            {"role": "current_roster", "host": "stats.wnba.com", "http_status": 200, "player_count": len(players)},
        ],
    }


def fetch_draftkings_shadow_snapshot(
    *,
    date: str,
    season: int,
    requester: Callable[..., Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not _DATE_RE.fullmatch(str(date)):
        raise WNBAOfficialReconciliationInputError("Step 6H date must use YYYY-MM-DD.")
    environment = _environment(env)
    timeout_seconds = _timeout(environment)
    captured = _iso_now()
    offers: list[dict[str, Any]] = []
    events_by_id: dict[str, dict[str, Any]] = {}
    source_summary: list[dict[str, Any]] = []
    for index, url in enumerate(frozen_draftkings_urls()):
        document = _get_json(url, requester=requester, timeout_seconds=timeout_seconds)
        normalized = normalize_draftkings_document(document, captured_at_utc=captured)
        for event in extract_draftkings_events(document):
            existing = events_by_id.get(event["source_event_id"])
            if existing is None or len(event["participant_keys"]) > len(existing.get("participant_keys") or []):
                events_by_id[event["source_event_id"]] = event
        offers.extend(normalized)
        source_summary.append(
            {
                "source_index": index,
                "host": (urlparse(url).hostname or "").casefold(),
                "normalized_offer_count": len(normalized),
                "http_status": 200,
            }
        )
    deduped: list[dict[str, Any]] = []
    seen_offer_ids: set[str] = set()
    for offer in offers:
        offer_id = _clean(offer.get("source_offer_id"))
        key = offer_id or _hash(offer)
        if key not in seen_offer_ids:
            deduped.append(offer)
            seen_offer_ids.add(key)
    if not deduped:
        raise WNBAOfficialReconciliationUpstreamError("Frozen DraftKings endpoints returned no supported WNBA offers.")
    return {
        "schema_version": "wnba_step_6c_owned_market_feed_v1",
        "date": str(date),
        "season": int(season),
        "captured_at_utc": captured,
        "feed_source": "DraftKings public sportsbook JSON -> Step 6H shadow snapshot",
        "feed_format": "canonical_offers_v1",
        "odds_format": "american",
        "offers": deduped,
        "source_events": sorted(events_by_id.values(), key=lambda row: row["source_event_id"]),
        "source_summary": source_summary,
    }


def _games_for_event(
    event: Mapping[str, Any],
    official_games: list[dict[str, Any]],
    *,
    feed_date: str,
) -> list[dict[str, Any]]:
    participant_keys = set(event.get("participant_keys") or [])
    event_date = _clean(event.get("event_date"))
    candidates = official_games
    if len(participant_keys) >= 2:
        candidates = [
            game for game in candidates
            if {game["home_team_key"], game["away_team_key"]}.issubset(participant_keys)
            or participant_keys.issubset({game["home_team_key"], game["away_team_key"]})
        ]
    if event_date:
        exact = [game for game in candidates if game["game_date"] == event_date]
        if exact:
            candidates = exact
        else:
            event_day = date_type.fromisoformat(event_date)
            candidates = [
                game for game in candidates
                if abs((date_type.fromisoformat(game["game_date"]) - event_day).days) <= 1
            ]
    elif candidates:
        start = date_type.fromisoformat(feed_date)
        end = start + timedelta(days=MAX_SCHEDULE_LOOKAHEAD_DAYS)
        near = [
            game for game in candidates
            if start <= date_type.fromisoformat(game["game_date"]) <= end
        ]
        if near:
            candidates = near
    return candidates


def reconcile_snapshot(
    feed: Mapping[str, Any],
    *,
    official_players: list[dict[str, Any]],
    official_games: list[dict[str, Any]],
    draftkings_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    shadow = validate_shadow_feed(feed)
    offers = list(feed.get("offers") or [])
    event_rows = draftkings_events if draftkings_events is not None else list(feed.get("source_events") or [])
    event_meta = {str(row.get("source_event_id")): dict(row) for row in event_rows if row.get("source_event_id")}
    players_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in official_players:
        key = _name_key(row.get("player_name"))
        if key:
            players_by_key[key].append(dict(row))
    games_by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for game in official_games:
        for team_id in (str(game.get("home_team_id") or ""), str(game.get("away_team_id") or "")):
            if team_id:
                games_by_team[team_id].append(dict(game))

    blockers: list[str] = []
    mismatch_details: list[dict[str, Any]] = []
    if not shadow.get("ready_for_auto_sync"):
        blockers.append("step6g_shadow_validation_failed")

    player_verifications: dict[str, dict[str, Any]] = {}
    source_event_players: dict[str, set[str]] = defaultdict(set)
    for offer in offers:
        player_name = _clean(offer.get("player_name")) or ""
        player_key = _name_key(player_name)
        event_id = _clean(offer.get("source_event_id")) or ""
        if event_id and player_key:
            source_event_players[event_id].add(player_key)
        if not player_key or player_key in player_verifications:
            continue
        matches = players_by_key.get(player_key, [])
        if len(matches) == 0:
            blockers.append("unverified_official_player")
            mismatch_details.append({"type": "unverified_player", "player_name": player_name})
            player_verifications[player_key] = {"player_name": player_name, "verified": False}
        elif len(matches) > 1:
            blockers.append("ambiguous_official_player_identity")
            mismatch_details.append({"type": "ambiguous_player", "player_name": player_name, "match_count": len(matches)})
            player_verifications[player_key] = {"player_name": player_name, "verified": False}
        else:
            match = matches[0]
            player_verifications[player_key] = {
                "player_name": player_name,
                "verified": True,
                "official_player_id": match.get("player_id"),
                "official_team_id": match.get("team_id"),
                "official_team_name": match.get("team_name"),
            }

    event_verifications: dict[str, dict[str, Any]] = {}
    feed_date = str(feed.get("date") or "")
    for event_id, player_keys in sorted(source_event_players.items()):
        metadata = event_meta.get(event_id, {"source_event_id": event_id, "participant_keys": []})
        candidates = _games_for_event(metadata, official_games, feed_date=feed_date)
        verified_players = [player_verifications.get(key) for key in player_keys]
        team_ids = {
            str(row.get("official_team_id"))
            for row in verified_players
            if row and row.get("verified") and row.get("official_team_id")
        }
        if candidates and team_ids:
            candidates = [
                game for game in candidates
                if team_ids.issubset({str(game.get("home_team_id")), str(game.get("away_team_id"))})
            ]
        elif not candidates and team_ids:
            game_sets = [
                {game["game_id"] for game in games_by_team.get(team_id, [])}
                for team_id in sorted(team_ids)
            ]
            common_ids = set.intersection(*game_sets) if game_sets else set()
            candidates = [game for game in official_games if game["game_id"] in common_ids]
            start = date_type.fromisoformat(feed_date)
            end = start + timedelta(days=MAX_SCHEDULE_LOOKAHEAD_DAYS)
            near = [game for game in candidates if start <= date_type.fromisoformat(game["game_date"]) <= end]
            if near:
                candidates = near
        if len(candidates) == 1:
            game = candidates[0]
            event_verifications[event_id] = {
                "source_event_id": event_id,
                "verified": True,
                "official_game_id": game["game_id"],
                "official_game_date": game["game_date"],
                "home_team_name": game["home_team_name"],
                "away_team_name": game["away_team_name"],
            }
        else:
            reason = "official_game_not_found" if len(candidates) == 0 else "ambiguous_official_game_match"
            blockers.append(reason)
            mismatch_details.append(
                {
                    "type": reason,
                    "source_event_id": event_id,
                    "event_name": metadata.get("event_name"),
                    "event_date": metadata.get("event_date"),
                    "candidate_count": len(candidates),
                }
            )
            event_verifications[event_id] = {"source_event_id": event_id, "verified": False}

    # Every official roster-verified player's team must equal one side of the
    # official game assigned to that DraftKings event.
    for event_id, player_keys in source_event_players.items():
        event_verification = event_verifications.get(event_id) or {}
        if not event_verification.get("verified"):
            continue
        game = next(
            (row for row in official_games if row.get("game_id") == event_verification.get("official_game_id")),
            None,
        )
        if not game:
            continue
        allowed_team_ids = {str(game.get("home_team_id")), str(game.get("away_team_id"))}
        for player_key in player_keys:
            player = player_verifications.get(player_key) or {}
            if player.get("verified") and str(player.get("official_team_id")) not in allowed_team_ids:
                blockers.append("player_game_team_mismatch")
                mismatch_details.append(
                    {
                        "type": "player_game_team_mismatch",
                        "player_name": player.get("player_name"),
                        "source_event_id": event_id,
                        "official_team_id": player.get("official_team_id"),
                        "official_game_id": game.get("game_id"),
                    }
                )

    unique_markets = {str(row.get("source_market_id")) for row in offers if row.get("source_market_id")}
    verified_player_count = sum(1 for row in player_verifications.values() if row.get("verified"))
    verified_event_count = sum(1 for row in event_verifications.values() if row.get("verified"))
    all_events_verified = bool(event_verifications) and verified_event_count == len(event_verifications)
    all_players_verified = bool(player_verifications) and verified_player_count == len(player_verifications)
    ready = bool(shadow.get("ready_for_auto_sync")) and all_players_verified and all_events_verified and not blockers

    fingerprint_identity = {
        "date": feed_date,
        "season": int(feed.get("season") or 0),
        "source_offer_ids": sorted(str(row.get("source_offer_id")) for row in offers if row.get("source_offer_id")),
        "players": sorted(
            (
                key,
                row.get("verified"),
                row.get("official_player_id"),
                row.get("official_team_id"),
            )
            for key, row in player_verifications.items()
        ),
        "events": sorted(
            (
                event_id,
                row.get("verified"),
                row.get("official_game_id"),
                row.get("official_game_date"),
            )
            for event_id, row in event_verifications.items()
        ),
        "blockers": sorted(set(blockers)),
        "ready_for_auto_sync": ready,
    }
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6h_official_reconciliation",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "date": feed_date,
        "season": int(feed.get("season") or 0),
        "offer_side_count": len(offers),
        "market_count": len(unique_markets),
        "draftkings_event_count": len(source_event_players),
        "official_active_player_count": len(official_players),
        "official_schedule_game_count": len(official_games),
        "verified_player_count": verified_player_count,
        "verified_roster_membership_count": verified_player_count,
        "verified_event_count": verified_event_count,
        "verified_market_count": len(unique_markets) if ready else 0,
        "player_verifications": sorted(player_verifications.values(), key=lambda row: _name_key(row.get("player_name"))),
        "event_verifications": [event_verifications[key] for key in sorted(event_verifications)],
        "mismatch_details": mismatch_details,
        "blockers": sorted(set(blockers)),
        "step6g_shadow_ready": bool(shadow.get("ready_for_auto_sync")),
        "step6g_blockers": list(shadow.get("blockers") or []),
        "ready_for_auto_sync": ready,
        "reconciliation_fingerprint_sha256": _hash(fingerprint_identity),
        "safety": {
            "production_feed_written": False,
            "direct_sync_enablement_changed": False,
            "production_runtime_enablement_changed": False,
            "scheduler_enablement_changed": False,
            "authentication_used": False,
            "cookies_used": False,
            "wager_action_performed": False,
            "paid_odds_vendor_used": False,
            "monte_carlo_run": False,
        },
    }


def run_official_reconciliation(
    *,
    date: str,
    season: int,
    draftkings_requester: Callable[..., Any] | None = None,
    official_requester: Callable[..., Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    draftkings = fetch_draftkings_shadow_snapshot(
        date=date,
        season=season,
        requester=draftkings_requester,
        env=env,
    )
    official = fetch_official_snapshot(season=season, requester=official_requester, env=env)
    report = reconcile_snapshot(
        draftkings,
        official_players=official["players"],
        official_games=official["games"],
        draftkings_events=draftkings["source_events"],
    )
    report["draftkings_source_summary"] = list(draftkings.get("source_summary") or [])
    report["official_source_summary"] = list(official.get("source_summary") or [])
    report["safety"]["http_methods"] = ["GET"]
    return report
