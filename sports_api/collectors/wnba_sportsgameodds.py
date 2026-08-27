"""WNBA Step 5O: concrete SportsGameOdds onboarding and canonical prop adapter.

This module is intentionally additive. Frozen Step 5N remains authoritative for
HTTPS transport/security and frozen Step 5M remains authoritative for market
integrity. Step 5O contributes a concrete provider profile plus a deterministic
translation from SportsGameOdds v2 event/odds JSON into Step-5M canonical offers.

No API key is stored in source. Deployment supplies SPORTSGAMEODDS_API_KEY.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any

from sports_api.collectors.wnba_prop_feed_collector import (
    DEFAULT_PROVIDER_ENV,
    PROVIDERS_ENV,
    collect_provider_feed,
)
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_prop_line_feed_adapter import CANONICAL_FEED_FORMAT

MODEL_SOURCE = "Kyre Sports API WNBA Step 5O SportsGameOdds adapter"
MODEL_VERSION = "wnba_step_5o_sportsgameodds_adapter_v1"
SCHEMA_VERSION = "wnba_step_5o_sportsgameodds_canonical_feed_v1"
MODEL_FAMILY = "concrete_provider_onboarding_and_canonical_market_translation"

SPORTSGAMEODDS_PROVIDER_ID = "sportsgameodds"
SPORTSGAMEODDS_FEED_SOURCE = "SportsGameOdds WNBA"
SPORTSGAMEODDS_EVENTS_URL = "https://api.sportsgameodds.com/v2/events"
SPORTSGAMEODDS_API_KEY_ENV = "SPORTSGAMEODDS_API_KEY"
WNBA_SPORTSGAMEODDS_API_KEY_ENV = "WNBA_SPORTSGAMEODDS_API_KEY"
SPORTSGAMEODDS_DOCS = "https://sportsgameodds.com/docs/endpoints/getEvents"

MAX_EVENTS = 100
MAX_ODDS_PER_EVENT = 20_000
MAX_BOOKMAKERS_PER_ODD = 250
MAX_ALT_LINES_PER_BOOKMAKER = 250

_TEAM_ENTITY_IDS = frozenset({"all", "home", "away"})
_SIDE_IDS = frozenset({"over", "under"})
_STAT_ALIASES = {
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "pra": "pra",
    "points+rebounds+assists": "pra",
    "points_rebounds_assists": "pra",
    "pointsreboundsassists": "pra",
    "pointsReboundsAssists": "pra",
}
_BOOK_DISPLAY = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "espnbet": "ESPN BET",
    "bet365": "bet365",
    "fanatics": "Fanatics",
    "circa": "Circa",
    "pinnacle": "Pinnacle",
    "betrivers": "BetRivers",
    "bovada": "Bovada",
}


class WNBASportsGameOddsAdapterError(ValueError):
    pass


def _utc_now_iso() -> str:
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


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def sportsgameodds_ready(env: Mapping[str, str] | None = None) -> bool:
    environment = _environment(env)
    return bool(_clean(environment.get(SPORTSGAMEODDS_API_KEY_ENV)) or _clean(environment.get(WNBA_SPORTSGAMEODDS_API_KEY_ENV)))


def build_sportsgameodds_step5n_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build an in-memory Step-5N registry for the built-in SportsGameOdds profile.

    The returned registry contains only an environment-variable *reference* to
    the credential. The secret value itself is copied only into the ephemeral
    environment mapping used for the request and is never placed in provider JSON.
    """
    environment = dict(_environment(env))
    if not _clean(environment.get(SPORTSGAMEODDS_API_KEY_ENV)):
        fallback = _clean(environment.get(WNBA_SPORTSGAMEODDS_API_KEY_ENV))
        if fallback:
            environment[SPORTSGAMEODDS_API_KEY_ENV] = fallback

    provider = {
        "provider_id": SPORTSGAMEODDS_PROVIDER_ID,
        "enabled": True,
        "url": SPORTSGAMEODDS_EVENTS_URL,
        "feed_source": SPORTSGAMEODDS_FEED_SOURCE,
        "feed_format": "bookmaker_event_markets_v1",
        "odds_format": "american",
        "timeout_seconds": 15,
        "max_response_bytes": 10_000_000,
        "query_params": {
            "leagueID": "WNBA",
            "oddsAvailable": "true",
            "started": "false",
            "ended": "false",
            "cancelled": "false",
            "includeOpposingOdds": "true",
            "includeAltLines": "true",
            "limit": str(MAX_EVENTS),
        },
        "secret_header_env": {"x-api-key": SPORTSGAMEODDS_API_KEY_ENV},
        "response_json_path": ["data"],
        "list_wrapper_key": "events",
    }
    environment[PROVIDERS_ENV] = json.dumps(
        {"providers": [provider], "default_provider_id": SPORTSGAMEODDS_PROVIDER_ID},
        separators=(",", ":"),
    )
    environment[DEFAULT_PROVIDER_ENV] = SPORTSGAMEODDS_PROVIDER_ID
    return environment


def describe_sportsgameodds_onboarding(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _environment(env)
    ready = sportsgameodds_ready(environment)
    return {
        "provider_id": SPORTSGAMEODDS_PROVIDER_ID,
        "provider_name": "SportsGameOdds",
        "ready": ready,
        "required_secret_env": SPORTSGAMEODDS_API_KEY_ENV,
        "accepted_fallback_secret_env": WNBA_SPORTSGAMEODDS_API_KEY_ENV,
        "endpoint": SPORTSGAMEODDS_EVENTS_URL,
        "league_id": "WNBA",
        "transport": "HTTPS GET via frozen Step 5N",
        "source_feed_format": "SportsGameOdds v2 Event.odds/byBookmaker",
        "step_5m_handoff_format": CANONICAL_FEED_FORMAT,
        "supported_model_stats": ["points", "rebounds", "assists", "pra"],
        "includes_alt_lines": True,
        "requires_available_bookmaker_offer": True,
        "docs": SPORTSGAMEODDS_DOCS,
        "secrets_returned": False,
    }


def _events(raw_feed: Any) -> list[dict[str, Any]]:
    if isinstance(raw_feed, dict):
        value = raw_feed.get("events")
        if value is None:
            value = raw_feed.get("data")
    else:
        value = raw_feed
    if not isinstance(value, list):
        raise WNBASportsGameOddsAdapterError(
            "WNBA Step 5O SportsGameOdds payload must contain an events/data list."
        )
    if len(value) > MAX_EVENTS:
        raise WNBASportsGameOddsAdapterError(
            f"WNBA Step 5O SportsGameOdds payload cannot exceed {MAX_EVENTS} events."
        )
    return [deepcopy(item) for item in value if isinstance(item, dict)]


def _team_name(event: dict[str, Any], side: str) -> str | None:
    team = (event.get("teams") or {}).get(side)
    if not isinstance(team, dict):
        return None
    names = team.get("names")
    if isinstance(names, dict):
        for key in ("long", "display", "medium", "short"):
            value = _clean(names.get(key))
            if value:
                return value
    for key in ("name", "fullName", "teamName"):
        value = _clean(team.get(key))
        if value:
            return value
    return None


def _player_name(event: dict[str, Any], player_id: str) -> str | None:
    players = event.get("players")
    player = None
    if isinstance(players, dict):
        player = players.get(player_id)
        if player is None:
            for candidate in players.values():
                if isinstance(candidate, dict) and _clean(candidate.get("playerID")) == player_id:
                    player = candidate
                    break
    elif isinstance(players, list):
        for candidate in players:
            if isinstance(candidate, dict) and _clean(candidate.get("playerID")) == player_id:
                player = candidate
                break
    if not isinstance(player, dict):
        return None
    direct = _clean(player.get("name")) or _clean(player.get("displayName"))
    if direct:
        return direct
    names = player.get("names")
    if isinstance(names, dict):
        direct = _clean(names.get("display")) or _clean(names.get("name"))
        if direct:
            return direct
        first = _clean(names.get("firstName"))
        last = _clean(names.get("lastName"))
    else:
        first = _clean(player.get("firstName"))
        last = _clean(player.get("lastName"))
    joined = " ".join(part for part in (first, last) if part)
    return joined or None


def _stat(value: Any) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    return _STAT_ALIASES.get(raw) or _STAT_ALIASES.get(raw.casefold())


def _book_name(bookmaker_id: Any) -> str | None:
    raw = _clean(bookmaker_id)
    if not raw:
        return None
    key = raw.casefold()
    return _BOOK_DISPLAY.get(key) or raw


def _offer(
    *,
    event: dict[str, Any],
    odd_id: str,
    odd: dict[str, Any],
    bookmaker_id: str,
    book: dict[str, Any],
    player_name: str,
    stat: str,
    side: str,
    fallback_captured_at_utc: str,
    alt_index: int | None = None,
) -> dict[str, Any] | None:
    if book.get("available") is not True:
        return None
    line = book.get("overUnder")
    odds = book.get("odds")
    if line in (None, "") or odds in (None, ""):
        return None
    timestamp = _clean(book.get("lastUpdatedAt")) or fallback_captured_at_utc
    source_offer_id = f"{odd_id}:{bookmaker_id}"
    if alt_index is not None:
        source_offer_id += f":alt:{alt_index}"
    return {
        "sportsbook": _book_name(bookmaker_id),
        "player_name": player_name,
        "stat": stat,
        "side": side,
        "line": line,
        "american_odds": odds,
        "market_captured_at_utc": timestamp,
        "source_event_id": _clean(event.get("eventID")) or _clean(event.get("id")),
        "source_market_id": odd_id,
        "source_offer_id": source_offer_id,
        "home_team": _team_name(event, "home"),
        "away_team": _team_name(event, "away"),
    }


def sportsgameodds_to_canonical(
    raw_feed: Any,
    *,
    feed_captured_at_utc: str | None = None,
) -> dict[str, Any]:
    captured = _clean(feed_captured_at_utc) or _utc_now_iso()
    offers: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    event_count = 0
    market_count = 0
    unavailable_book_offer_count = 0
    unsupported_market_count = 0
    missing_player_name_count = 0

    for event in _events(raw_feed):
        event_count += 1
        event_id = _clean(event.get("eventID")) or _clean(event.get("id")) or f"event:{event_count}"
        league_id = (_clean(event.get("leagueID")) or "WNBA").upper()
        status = event.get("status") if isinstance(event.get("status"), dict) else {}
        if league_id != "WNBA":
            audit.append({"event_id": event_id, "status": "excluded", "reason": "wrong_league"})
            continue
        if any(status.get(key) is True for key in ("started", "live", "ended", "cancelled", "finalized")):
            audit.append({"event_id": event_id, "status": "excluded", "reason": "event_not_pregame"})
            continue
        odds_map = event.get("odds")
        if not isinstance(odds_map, dict):
            audit.append({"event_id": event_id, "status": "excluded", "reason": "odds_not_object"})
            continue
        if len(odds_map) > MAX_ODDS_PER_EVENT:
            raise WNBASportsGameOddsAdapterError(
                f"WNBA Step 5O event {event_id!r} exceeds {MAX_ODDS_PER_EVENT} odds markets."
            )

        event_offer_start = len(offers)
        for odd_key, odd in odds_map.items():
            if not isinstance(odd, dict):
                continue
            market_count += 1
            odd_id = _clean(odd.get("oddID")) or _clean(odd_key) or f"market:{market_count}"
            stat = _stat(odd.get("statID"))
            entity_id = _clean(odd.get("statEntityID"))
            period = (_clean(odd.get("periodID")) or "").casefold()
            bet_type = (_clean(odd.get("betTypeID")) or "").casefold()
            side = (_clean(odd.get("sideID")) or "").casefold()
            if (
                stat is None
                or not entity_id
                or entity_id.casefold() in _TEAM_ENTITY_IDS
                or period != "game"
                or bet_type != "ou"
                or side not in _SIDE_IDS
                or odd.get("started") is True
                or odd.get("ended") is True
                or odd.get("cancelled") is True
            ):
                unsupported_market_count += 1
                continue
            player_name = _player_name(event, entity_id)
            if not player_name:
                missing_player_name_count += 1
                continue
            by_book = odd.get("byBookmaker")
            if not isinstance(by_book, dict) or len(by_book) > MAX_BOOKMAKERS_PER_ODD:
                continue
            for bookmaker_id, book in by_book.items():
                if not isinstance(book, dict):
                    continue
                primary = _offer(
                    event=event,
                    odd_id=odd_id,
                    odd=odd,
                    bookmaker_id=str(bookmaker_id),
                    book=book,
                    player_name=player_name,
                    stat=stat,
                    side=side,
                    fallback_captured_at_utc=captured,
                )
                if primary is not None:
                    offers.append(primary)
                elif book.get("available") is not True:
                    unavailable_book_offer_count += 1

                alt_lines = book.get("altLines")
                if alt_lines is None:
                    continue
                if not isinstance(alt_lines, list) or len(alt_lines) > MAX_ALT_LINES_PER_BOOKMAKER:
                    continue
                for alt_index, alt in enumerate(alt_lines):
                    if not isinstance(alt, dict):
                        continue
                    alt_offer = _offer(
                        event=event,
                        odd_id=odd_id,
                        odd=odd,
                        bookmaker_id=str(bookmaker_id),
                        book=alt,
                        player_name=player_name,
                        stat=stat,
                        side=side,
                        fallback_captured_at_utc=captured,
                        alt_index=alt_index,
                    )
                    if alt_offer is not None:
                        offers.append(alt_offer)
                    elif alt.get("available") is not True:
                        unavailable_book_offer_count += 1

        audit.append(
            {
                "event_id": event_id,
                "status": "processed",
                "canonical_offer_count": len(offers) - event_offer_start,
            }
        )

    canonical = {"offers": offers}
    fingerprint = _hash(
        {
            "feed_captured_at_utc": captured,
            "canonical": canonical,
            "event_count": event_count,
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_sportsgameodds_canonical_prop_feed",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _utc_now_iso(),
        "adapter_id": f"wnba-5o-sgo-{fingerprint[:20]}",
        "adapter_fingerprint_sha256": fingerprint,
        "provider_id": SPORTSGAMEODDS_PROVIDER_ID,
        "feed_source": SPORTSGAMEODDS_FEED_SOURCE,
        "feed_format": CANONICAL_FEED_FORMAT,
        "odds_format": "american",
        "feed_captured_at_utc": captured,
        "source_event_count": event_count,
        "source_market_count": market_count,
        "canonical_offer_count": len(offers),
        "unavailable_book_offer_count": unavailable_book_offer_count,
        "unsupported_market_count": unsupported_market_count,
        "missing_player_name_count": missing_player_name_count,
        "raw_feed_sha256": _hash(raw_feed),
        "canonical_feed_sha256": _hash(canonical),
        "raw_feed": canonical,
        "event_audit": audit,
        "adapter_semantics": {
            "only_pregame_wnba_events": True,
            "only_full_game_over_under_player_props": True,
            "only_available_bookmaker_offers": True,
            "alternate_lines_preserved": True,
            "provider_player_ids_are_not_treated_as_official_wnba_ids": True,
            "player_name_is_resolved_against_official_roster_by_frozen_step_5m": True,
            "market_probability_is_never_created_or_modified_here": True,
        },
    }


def collect_sportsgameodds_feed(
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
    collector: Callable[..., dict[str, Any]] = collect_provider_feed,
) -> dict[str, Any]:
    step5n_env = build_sportsgameodds_step5n_env(env)
    collection = collector(
        SPORTSGAMEODDS_PROVIDER_ID,
        date=date,
        season=season,
        env=step5n_env,
        requester=requester,
    )
    adapted = sportsgameodds_to_canonical(
        collection["raw_feed"],
        feed_captured_at_utc=collection["collected_at_utc"],
    )
    fingerprint = _hash(
        {
            "collection_fingerprint_sha256": collection["collection_fingerprint_sha256"],
            "adapter_fingerprint_sha256": adapted["adapter_fingerprint_sha256"],
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_sportsgameodds_collected_and_adapted_feed",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "provider_pipeline_id": f"wnba-5o-sgo-pipeline-{fingerprint[:20]}",
        "provider_pipeline_fingerprint_sha256": fingerprint,
        "provider_id": SPORTSGAMEODDS_PROVIDER_ID,
        "collection": collection,
        "adapter": adapted,
        "feed_source": adapted["feed_source"],
        "feed_format": adapted["feed_format"],
        "odds_format": adapted["odds_format"],
        "date": collection["date"],
        "season": collection["season"],
        "collected_at_utc": collection["collected_at_utc"],
        "raw_feed": adapted["raw_feed"],
    }
