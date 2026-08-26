"""WNBA Step 5M: real prop-line feed normalization and Step-5L handoff.

Step 5M is a provider-adapter layer, not a sportsbook scraper. It consumes a
real external feed payload supplied by a collector/provider, resolves player
identity against the official current WNBA roster, verifies that the player's
team belongs to exactly one playable game on the official daily slate,
normalizes supported player-prop markets, and creates the exact player/stat/line
records consumed by frozen Step 5L.

Critical integrity rules:
- sportsbook lines are never invented or inferred from projections;
- Over and Under prices are paired only from the same sportsbook and exact line;
- stale/future/malformed/conflicting offers remain visible in the audit trail but
  are excluded from the normalized board by default;
- different lines are never merged;
- one-sided markets may establish a real line for probability modeling, but they
  are never misrepresented as a two-way sportsbook quote;
- the adapter never changes Step 5F probabilities or Step 5K ranking semantics.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
import re
import unicodedata
from typing import Any, Callable

from sports_api.wnba_daily_slate_top_five import build_daily_slate_top_five
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_prop_threshold_probability import MAX_PROP_LINE, SUPPORTED_STATS
from sports_api.wnba_rosters import WNBAStatsUpstreamError, get_current_players_dataset
from sports_api.wnba_schedule import ARIZONA_TZ, WNBAScheduleUpstreamError, verify_daily_slate_dataset
from sports_api.wnba_sportsbook_market_edge import (
    DEFAULT_MAX_MARKET_AGE_MINUTES,
    MARKET_FUTURE_TOLERANCE_SECONDS,
    MAX_ABS_AMERICAN_ODDS,
    MAX_MARKET_AGE_MINUTES,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5M real prop-line feed adapter"
MODEL_VERSION = "wnba_step_5m_real_prop_line_feed_adapter_v1"
SCHEMA_VERSION = "wnba_step_5m_real_prop_line_feed_board_v1"
MODEL_FAMILY = "provider_feed_normalization_and_verified_step_5l_handoff"

CANONICAL_FEED_FORMAT = "canonical_offers_v1"
BOOKMAKER_EVENT_FEED_FORMAT = "bookmaker_event_markets_v1"
SUPPORTED_FEED_FORMATS = (CANONICAL_FEED_FORMAT, BOOKMAKER_EVENT_FEED_FORMAT)
SUPPORTED_ODDS_FORMATS = ("american", "decimal")

MIN_RAW_OFFERS = 1
MAX_RAW_OFFERS = 5_000
MAX_NORMALIZED_LINES = 1_000
DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS = 120
MAX_SIDE_PAIR_SKEW_SECONDS = 3_600
MAX_FEED_SOURCE_LENGTH = 160

STAT_ALIASES = {
    "points": "points",
    "point": "points",
    "pts": "points",
    "player_points": "points",
    "player points": "points",
    "rebounds": "rebounds",
    "rebound": "rebounds",
    "reb": "rebounds",
    "rebs": "rebounds",
    "player_rebounds": "rebounds",
    "player rebounds": "rebounds",
    "assists": "assists",
    "assist": "assists",
    "ast": "assists",
    "asts": "assists",
    "player_assists": "assists",
    "player assists": "assists",
    "pra": "pra",
    "points+rebounds+assists": "pra",
    "points rebounds assists": "pra",
    "player_points_rebounds_assists": "pra",
    "player points rebounds assists": "pra",
}
SIDE_ALIASES = {
    "over": "over",
    "o": "over",
    "under": "under",
    "u": "under",
}


class WNBAPropLineFeedNotReadyError(RuntimeError):
    pass


class WNBAPropLineFeedUpstreamError(RuntimeError):
    pass


class WNBAPropLineFeedModelInputError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _choice(value: Any, allowed: tuple[str, ...], label: str) -> str:
    text = (_clean(value) or "").casefold()
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(text)
    if result is None:
        raise ValueError(
            f"WNBA Step 5M unsupported {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return result


def _target_date(value: str | None) -> str:
    if value is None:
        return datetime.now(ARIZONA_TZ).date().isoformat()
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("WNBA Step 5M date must use YYYY-MM-DD format.") from exc
    return text


def _feed_source(value: Any) -> str:
    text = _clean(value)
    if not text or len(text) > MAX_FEED_SOURCE_LENGTH:
        raise ValueError(
            f"WNBA Step 5M feed_source must be a non-empty string of at most {MAX_FEED_SOURCE_LENGTH} characters."
        )
    return " ".join(text.split())


def _positive_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _line_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or not 0.0 <= number <= MAX_PROP_LINE:
        return None
    return round(number, 6)


def _stat_or_none(value: Any) -> str | None:
    text = " ".join((_clean(value) or "").casefold().replace("-", " ").split())
    result = STAT_ALIASES.get(text)
    return result if result in SUPPORTED_STATS else None


def _side_or_none(value: Any) -> str | None:
    text = " ".join((_clean(value) or "").casefold().split())
    return SIDE_ALIASES.get(text)


def _parse_timestamp(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _american_from_decimal(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        decimal = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(decimal) or decimal <= 1.0:
        return None
    if decimal >= 2.0:
        american = int(round((decimal - 1.0) * 100.0))
    else:
        american = -int(round(100.0 / (decimal - 1.0)))
    if abs(american) < 100:
        american = 100 if american >= 0 else -100
    if abs(american) > MAX_ABS_AMERICAN_ODDS:
        return None
    return american


def _american_or_none(value: Any, odds_format: str) -> int | None:
    if odds_format == "decimal":
        return _american_from_decimal(value)
    if isinstance(value, bool):
        return None
    try:
        number_float = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number_float) or not number_float.is_integer():
        return None
    number = int(number_float)
    if abs(number) < 100 or abs(number) > MAX_ABS_AMERICAN_ODDS:
        return None
    return number


def _name_key(value: Any) -> str | None:
    text = _clean(value)
    if not text:
        return None
    decomposed = unicodedata.normalize("NFKD", text)
    asciiish = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    asciiish = asciiish.casefold().replace("’", "'")
    tokens = re.findall(r"[a-z0-9]+", asciiish)
    return " ".join(tokens) or None


def _sportsbook_or_none(value: Any) -> str | None:
    text = _clean(value)
    if not text or len(text) > 80:
        return None
    return " ".join(text.split())


def _event_team_key(value: Any) -> str | None:
    return _name_key(value)


def _flatten_canonical(raw_feed: dict[str, Any], feed_captured_at: str | None) -> list[dict[str, Any]]:
    offers = raw_feed.get("offers")
    if not isinstance(offers, list):
        raise WNBAPropLineFeedModelInputError(
            "WNBA Step 5M canonical_offers_v1 raw_feed must contain an offers list."
        )
    flattened: list[dict[str, Any]] = []
    for index, row in enumerate(offers):
        if not isinstance(row, dict):
            flattened.append({"source_index": str(index), "structural_error": "offer_not_object"})
            continue
        flattened.append(
            {
                "source_index": str(index),
                "sportsbook": row.get("sportsbook"),
                "player_id": row.get("player_id"),
                "player_name": row.get("player_name"),
                "stat": row.get("stat") if row.get("stat") is not None else row.get("market_key"),
                "side": row.get("side"),
                "line": row.get("line") if row.get("line") is not None else row.get("point"),
                "odds": (
                    row.get("american_odds")
                    if row.get("american_odds") is not None
                    else row.get("decimal_odds")
                    if row.get("decimal_odds") is not None
                    else row.get("price")
                ),
                "market_captured_at_utc": (
                    row.get("market_captured_at_utc")
                    or row.get("last_update")
                    or feed_captured_at
                ),
                "source_event_id": row.get("source_event_id") or row.get("event_id"),
                "source_market_id": row.get("source_market_id") or row.get("market_id"),
                "source_offer_id": row.get("source_offer_id") or row.get("offer_id"),
                "home_team": row.get("home_team"),
                "away_team": row.get("away_team"),
            }
        )
    return flattened


def _flatten_bookmaker_events(raw_feed: dict[str, Any], feed_captured_at: str | None) -> list[dict[str, Any]]:
    events = raw_feed.get("events")
    if events is None and isinstance(raw_feed.get("data"), list):
        events = raw_feed.get("data")
    if not isinstance(events, list):
        raise WNBAPropLineFeedModelInputError(
            "WNBA Step 5M bookmaker_event_markets_v1 raw_feed must contain an events list (or data list)."
        )
    flattened: list[dict[str, Any]] = []
    source_index = 0
    for event_index, event in enumerate(events):
        if not isinstance(event, dict):
            flattened.append(
                {"source_index": f"event:{event_index}", "structural_error": "event_not_object"}
            )
            source_index += 1
            continue
        event_id = event.get("id") or event.get("event_id")
        home_team = event.get("home_team") or event.get("home")
        away_team = event.get("away_team") or event.get("away")
        bookmakers = event.get("bookmakers")
        if not isinstance(bookmakers, list):
            flattened.append(
                {
                    "source_index": f"event:{event_index}",
                    "structural_error": "bookmakers_not_list",
                    "source_event_id": event_id,
                }
            )
            source_index += 1
            continue
        for book_index, bookmaker in enumerate(bookmakers):
            if not isinstance(bookmaker, dict):
                flattened.append(
                    {
                        "source_index": f"event:{event_index}/book:{book_index}",
                        "structural_error": "bookmaker_not_object",
                        "source_event_id": event_id,
                    }
                )
                source_index += 1
                continue
            sportsbook = bookmaker.get("title") or bookmaker.get("name") or bookmaker.get("key")
            book_timestamp = bookmaker.get("last_update") or feed_captured_at
            markets = bookmaker.get("markets")
            if not isinstance(markets, list):
                flattened.append(
                    {
                        "source_index": f"event:{event_index}/book:{book_index}",
                        "structural_error": "markets_not_list",
                        "source_event_id": event_id,
                        "sportsbook": sportsbook,
                    }
                )
                source_index += 1
                continue
            for market_index, market in enumerate(markets):
                if not isinstance(market, dict):
                    flattened.append(
                        {
                            "source_index": f"event:{event_index}/book:{book_index}/market:{market_index}",
                            "structural_error": "market_not_object",
                            "source_event_id": event_id,
                            "sportsbook": sportsbook,
                        }
                    )
                    source_index += 1
                    continue
                market_key = market.get("key") or market.get("market_key") or market.get("name")
                market_id = market.get("id") or market.get("market_id")
                market_timestamp = market.get("last_update") or book_timestamp
                outcomes = market.get("outcomes")
                if not isinstance(outcomes, list):
                    flattened.append(
                        {
                            "source_index": f"event:{event_index}/book:{book_index}/market:{market_index}",
                            "structural_error": "outcomes_not_list",
                            "source_event_id": event_id,
                            "source_market_id": market_id,
                            "sportsbook": sportsbook,
                            "stat": market_key,
                        }
                    )
                    source_index += 1
                    continue
                for outcome_index, outcome in enumerate(outcomes):
                    index_label = (
                        f"event:{event_index}/book:{book_index}/market:{market_index}/outcome:{outcome_index}"
                    )
                    if not isinstance(outcome, dict):
                        flattened.append(
                            {
                                "source_index": index_label,
                                "structural_error": "outcome_not_object",
                                "source_event_id": event_id,
                                "source_market_id": market_id,
                                "sportsbook": sportsbook,
                                "stat": market_key,
                            }
                        )
                        source_index += 1
                        continue
                    flattened.append(
                        {
                            "source_index": index_label,
                            "sportsbook": sportsbook,
                            "player_id": outcome.get("player_id"),
                            "player_name": (
                                outcome.get("description")
                                or outcome.get("player_name")
                                or outcome.get("participant")
                            ),
                            "stat": market_key,
                            "side": outcome.get("name") or outcome.get("side"),
                            "line": outcome.get("point") if outcome.get("point") is not None else outcome.get("line"),
                            "odds": (
                                outcome.get("price")
                                if outcome.get("price") is not None
                                else outcome.get("odds")
                            ),
                            "market_captured_at_utc": outcome.get("last_update") or market_timestamp,
                            "source_event_id": event_id,
                            "source_market_id": market_id,
                            "source_offer_id": outcome.get("id") or outcome.get("offer_id"),
                            "home_team": home_team,
                            "away_team": away_team,
                        }
                    )
                    source_index += 1
    return flattened


def _flatten_feed(
    raw_feed: dict[str, Any],
    *,
    feed_format: str,
    feed_captured_at: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(raw_feed, dict):
        raise WNBAPropLineFeedModelInputError("WNBA Step 5M raw_feed must be an object.")
    if feed_format == CANONICAL_FEED_FORMAT:
        flattened = _flatten_canonical(raw_feed, feed_captured_at)
    elif feed_format == BOOKMAKER_EVENT_FEED_FORMAT:
        flattened = _flatten_bookmaker_events(raw_feed, feed_captured_at)
    else:  # validated before call; defensive only
        raise WNBAPropLineFeedModelInputError(f"Unsupported Step 5M feed format {feed_format!r}.")
    if not MIN_RAW_OFFERS <= len(flattened) <= MAX_RAW_OFFERS:
        raise WNBAPropLineFeedModelInputError(
            f"WNBA Step 5M feed must expand to {MIN_RAW_OFFERS} through {MAX_RAW_OFFERS} offer records."
        )
    return flattened


def _validate_slate(slate: dict[str, Any], *, target_date: str, season: int) -> list[dict[str, Any]]:
    if not isinstance(slate, dict):
        raise WNBAPropLineFeedUpstreamError("Step 5M official slate payload is malformed.")
    if slate.get("date") != target_date or int(slate.get("season", -1)) != season:
        raise WNBAPropLineFeedUpstreamError("Step 5M official slate date/season identity mismatch.")
    summary = slate.get("slate")
    games = slate.get("games")
    if not isinstance(summary, dict) or not isinstance(games, list):
        raise WNBAPropLineFeedUpstreamError("Step 5M official slate verification fields are missing.")
    if summary.get("slate_integrity_pass") is not True:
        reasons = summary.get("blocking_reasons") or []
        raise WNBAPropLineFeedNotReadyError(
            "Step 5M requires verified daily-slate integrity; blocking reasons: "
            + (", ".join(map(str, reasons)) if reasons else "unknown")
        )
    return [
        game
        for game in games
        if isinstance(game, dict)
        and isinstance(game.get("verification"), dict)
        and game["verification"].get("playable_pregame") is True
    ]


def _roster_indexes(roster: dict[str, Any], *, season: int) -> tuple[dict[int, dict[str, Any]], dict[str, list[int]]]:
    if not isinstance(roster, dict) or int(roster.get("season", -1)) != season:
        raise WNBAPropLineFeedUpstreamError("Step 5M current-roster payload is malformed or wrong season.")
    players = roster.get("players")
    if not isinstance(players, list):
        raise WNBAPropLineFeedUpstreamError("Step 5M current-roster player list is missing.")
    by_id: dict[int, dict[str, Any]] = {}
    by_name: dict[str, list[int]] = {}
    for row in players:
        if not isinstance(row, dict):
            continue
        player_id = _positive_int_or_none(row.get("player_id"))
        if player_id is None:
            continue
        if player_id in by_id:
            raise WNBAPropLineFeedUpstreamError(
                f"Step 5M current roster contains duplicate player_id {player_id}."
            )
        by_id[player_id] = row
        for field in ("full_name", "display_last_comma_first"):
            key = _name_key(row.get(field))
            if key:
                by_name.setdefault(key, []).append(player_id)
    return by_id, by_name


def _team_game_index(playable_games: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for game in playable_games:
        for side in ("away", "home"):
            team = game.get(side)
            if not isinstance(team, dict):
                continue
            team_key = _clean(team.get("team_key"))
            if team_key:
                result.setdefault(team_key, []).append(game)
    return result


def _team_alias_index(playable_games: list[dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    ambiguous: set[str] = set()
    for game in playable_games:
        for side in ("away", "home"):
            team = game.get(side)
            if not isinstance(team, dict):
                continue
            team_key = _clean(team.get("team_key"))
            if not team_key:
                continue
            values = [
                team_key,
                team.get("full_name"),
                team.get("team_tricode"),
                team.get("team_name"),
                (
                    f"{team.get('team_city')} {team.get('team_name')}"
                    if team.get("team_city") and team.get("team_name")
                    else None
                ),
            ]
            for value in values:
                key = _event_team_key(value)
                if not key:
                    continue
                existing = aliases.get(key)
                if existing is not None and existing != team_key:
                    ambiguous.add(key)
                else:
                    aliases[key] = team_key
    for key in ambiguous:
        aliases.pop(key, None)
    return aliases


def _resolve_player(
    offer: dict[str, Any],
    *,
    roster_by_id: dict[int, dict[str, Any]],
    roster_by_name: dict[str, list[int]],
) -> tuple[dict[str, Any] | None, str | None]:
    supplied_id = _positive_int_or_none(offer.get("player_id"))
    supplied_name_key = _name_key(offer.get("player_name"))

    by_id = roster_by_id.get(supplied_id) if supplied_id is not None else None
    name_matches = roster_by_name.get(supplied_name_key, []) if supplied_name_key else []

    if supplied_id is not None and by_id is None:
        return None, "player_id_not_on_current_official_roster"
    if supplied_name_key and not name_matches and supplied_id is None:
        return None, "player_name_not_on_current_official_roster"
    if supplied_id is None and not supplied_name_key:
        return None, "player_identity_missing"
    if supplied_id is None:
        unique = sorted(set(name_matches))
        if len(unique) != 1:
            return None, "player_name_ambiguous_on_current_roster"
        return roster_by_id.get(unique[0]), None
    if supplied_name_key:
        unique = sorted(set(name_matches))
        if unique and supplied_id not in unique:
            return None, "player_id_name_identity_mismatch"
    return by_id, None


def _normalize_offer(
    offer: dict[str, Any],
    *,
    odds_format: str,
    now_utc: datetime,
    max_market_age_minutes: int,
    exclude_stale_quotes: bool,
    roster_by_id: dict[int, dict[str, Any]],
    roster_by_name: dict[str, list[int]],
    team_games: dict[str, list[dict[str, Any]]],
    team_aliases: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    audit: dict[str, Any] = {
        "source_index": offer.get("source_index"),
        "source_event_id": _clean(offer.get("source_event_id")),
        "source_market_id": _clean(offer.get("source_market_id")),
        "source_offer_id": _clean(offer.get("source_offer_id")),
        "status": "excluded",
        "reason_codes": [],
    }
    if offer.get("structural_error"):
        audit["reason_codes"].append(str(offer["structural_error"]))
        return audit, None

    sportsbook = _sportsbook_or_none(offer.get("sportsbook"))
    stat = _stat_or_none(offer.get("stat"))
    side = _side_or_none(offer.get("side"))
    line = _line_or_none(offer.get("line"))
    odds = _american_or_none(offer.get("odds"), odds_format)
    captured = _parse_timestamp(offer.get("market_captured_at_utc"))
    player, player_reason = _resolve_player(
        offer,
        roster_by_id=roster_by_id,
        roster_by_name=roster_by_name,
    )

    if sportsbook is None:
        audit["reason_codes"].append("sportsbook_missing_or_invalid")
    if stat is None:
        audit["reason_codes"].append("unsupported_or_missing_prop_stat")
    if side is None:
        audit["reason_codes"].append("unsupported_or_missing_side")
    if line is None:
        audit["reason_codes"].append("prop_line_missing_or_invalid")
    if odds is None:
        audit["reason_codes"].append("odds_missing_or_invalid")
    if captured is None:
        audit["reason_codes"].append("market_timestamp_missing_or_invalid")
    if player_reason:
        audit["reason_codes"].append(player_reason)

    game = None
    team_key = _clean(player.get("team_key")) if player else None
    if player is not None:
        if not team_key:
            audit["reason_codes"].append("official_roster_team_key_missing")
        else:
            games = team_games.get(team_key, [])
            if len(games) == 0:
                audit["reason_codes"].append("player_team_not_on_playable_pregame_slate")
            elif len(games) > 1:
                audit["reason_codes"].append("player_team_maps_to_multiple_playable_games")
            else:
                game = games[0]

    event_verification = {
        "home_team_supplied": _clean(offer.get("home_team")),
        "away_team_supplied": _clean(offer.get("away_team")),
        "mapped_home_team_key": None,
        "mapped_away_team_key": None,
        "event_team_context_verified": False,
    }
    mapped_event_teams: set[str] = set()
    for field, output_field in (("home_team", "mapped_home_team_key"), ("away_team", "mapped_away_team_key")):
        alias = _event_team_key(offer.get(field))
        mapped = team_aliases.get(alias) if alias else None
        event_verification[output_field] = mapped
        if mapped:
            mapped_event_teams.add(mapped)
    if mapped_event_teams:
        event_verification["event_team_context_verified"] = True
        if team_key and team_key not in mapped_event_teams:
            audit["reason_codes"].append("feed_event_team_mismatch")
        if game is not None and len(mapped_event_teams) == 2:
            official_teams = {
                _clean((game.get("away") or {}).get("team_key")),
                _clean((game.get("home") or {}).get("team_key")),
            }
            official_teams.discard(None)
            if mapped_event_teams != official_teams:
                audit["reason_codes"].append("feed_event_game_mismatch")

    age_seconds = None
    stale = None
    future_seconds = None
    if captured is not None:
        age_seconds = (now_utc - captured).total_seconds()
        future_seconds = max(0.0, -age_seconds)
        stale = age_seconds > max_market_age_minutes * 60.0
        if future_seconds > MARKET_FUTURE_TOLERANCE_SECONDS:
            audit["reason_codes"].append("market_timestamp_too_far_in_future")
        if exclude_stale_quotes and stale:
            audit["reason_codes"].append("market_quote_stale")

    audit.update(
        {
            "sportsbook": sportsbook,
            "player_id": player.get("player_id") if player else _positive_int_or_none(offer.get("player_id")),
            "player_name": player.get("full_name") if player else _clean(offer.get("player_name")),
            "team_key": team_key,
            "game_id": _clean(game.get("game_id")) if game else None,
            "stat": stat,
            "side": side,
            "line": line,
            "american_odds": odds,
            "market_captured_at_utc": captured.isoformat() if captured else None,
            "market_age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
            "market_future_seconds": round(future_seconds, 3) if future_seconds is not None else None,
            "stale": stale,
            "event_verification": event_verification,
        }
    )
    if audit["reason_codes"]:
        return audit, None

    opponent_team_key = None
    if game is not None and team_key:
        away_key = _clean((game.get("away") or {}).get("team_key"))
        home_key = _clean((game.get("home") or {}).get("team_key"))
        opponent_team_key = home_key if team_key == away_key else away_key

    normalized = {
        "source_index": offer.get("source_index"),
        "source_event_id": _clean(offer.get("source_event_id")),
        "source_market_id": _clean(offer.get("source_market_id")),
        "source_offer_id": _clean(offer.get("source_offer_id")),
        "sportsbook": sportsbook,
        "sportsbook_key": sportsbook.casefold(),
        "player_id": int(player["player_id"]),
        "player_name": _clean(player.get("full_name")),
        "team_key": team_key,
        "opponent_team_key": opponent_team_key,
        "game_id": _clean(game.get("game_id")) if game else None,
        "stat": stat,
        "side": side,
        "line": line,
        "american_odds": odds,
        "market_captured_at_utc": captured.isoformat(),
        "captured_datetime": captured,
        "stale": stale,
    }
    audit["status"] = "eligible"
    return audit, normalized


def _select_latest_side_offers(
    offers: list[dict[str, Any]],
) -> tuple[dict[tuple[Any, ...], dict[str, Any]], list[dict[str, Any]]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for offer in offers:
        key = (
            offer["player_id"],
            offer["game_id"],
            offer["stat"],
            offer["line"],
            offer["sportsbook_key"],
            offer["side"],
        )
        buckets.setdefault(key, []).append(offer)

    selected: dict[tuple[Any, ...], dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    for key, rows in buckets.items():
        latest_time = max(row["captured_datetime"] for row in rows)
        latest = [row for row in rows if row["captured_datetime"] == latest_time]
        distinct_odds = sorted({row["american_odds"] for row in latest})
        if len(distinct_odds) > 1:
            conflicts.append(
                {
                    "player_id": key[0],
                    "game_id": key[1],
                    "stat": key[2],
                    "line": key[3],
                    "sportsbook_key": key[4],
                    "side": key[5],
                    "market_captured_at_utc": latest_time.isoformat(),
                    "conflicting_american_odds": distinct_odds,
                    "reason": "same_timestamp_conflicting_same_book_side_price",
                }
            )
            continue
        latest.sort(key=lambda row: str(row.get("source_index")))
        selected[key] = latest[0]
    return selected, conflicts


def _pair_two_way_quotes(
    selected: dict[tuple[Any, ...], dict[str, Any]],
    *,
    max_side_pair_skew_seconds: int,
) -> tuple[dict[tuple[int, str, float], list[dict[str, Any]]], list[dict[str, Any]]]:
    book_groups: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = {}
    for key, offer in selected.items():
        base = key[:5]
        book_groups.setdefault(base, {})[offer["side"]] = offer

    quotes_by_line: dict[tuple[int, str, float], list[dict[str, Any]]] = {}
    pair_audit: list[dict[str, Any]] = []
    for base, sides in book_groups.items():
        player_id, game_id, stat, line, sportsbook_key = base
        over = sides.get("over")
        under = sides.get("under")
        sportsbook = (over or under or {}).get("sportsbook")
        row = {
            "player_id": player_id,
            "game_id": game_id,
            "stat": stat,
            "line": line,
            "sportsbook": sportsbook,
            "sportsbook_key": sportsbook_key,
            "has_over": over is not None,
            "has_under": under is not None,
            "paired": False,
            "reason": None,
            "side_timestamp_skew_seconds": None,
        }
        if over is None or under is None:
            row["reason"] = "one_sided_market_not_two_way_quote"
            pair_audit.append(row)
            continue
        skew = abs((over["captured_datetime"] - under["captured_datetime"]).total_seconds())
        row["side_timestamp_skew_seconds"] = round(skew, 3)
        if skew > max_side_pair_skew_seconds:
            row["reason"] = "over_under_capture_skew_above_maximum"
            pair_audit.append(row)
            continue
        quote_time = max(over["captured_datetime"], under["captured_datetime"])
        quote = {
            "sportsbook": sportsbook,
            "over_odds": over["american_odds"],
            "under_odds": under["american_odds"],
            "market_captured_at_utc": quote_time.isoformat(),
        }
        quotes_by_line.setdefault((player_id, stat, line), []).append(quote)
        row["paired"] = True
        row["reason"] = "paired_same_book_same_line"
        pair_audit.append(row)

    for values in quotes_by_line.values():
        values.sort(key=lambda quote: (quote["sportsbook"].casefold(), quote["sportsbook"]))
    pair_audit.sort(
        key=lambda row: (
            row["player_id"], row["stat"], row["line"], row["sportsbook_key"]
        )
    )
    return quotes_by_line, pair_audit


def _line_board(
    selected: dict[tuple[Any, ...], dict[str, Any]],
    quotes_by_line: dict[tuple[int, str, float], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    logical: dict[tuple[int, str, float], dict[str, Any]] = {}
    books: dict[tuple[int, str, float], set[str]] = {}
    sides: dict[tuple[int, str, float], set[str]] = {}
    for offer in selected.values():
        key = (offer["player_id"], offer["stat"], offer["line"])
        if key not in logical:
            logical[key] = offer
        books.setdefault(key, set()).add(offer["sportsbook_key"])
        sides.setdefault(key, set()).add(offer["side"])
    rows: list[dict[str, Any]] = []
    for key, identity in logical.items():
        quotes = deepcopy(quotes_by_line.get(key, []))
        rows.append(
            {
                "player_id": key[0],
                "player_name": identity.get("player_name"),
                "game_id": identity.get("game_id"),
                "team_key": identity.get("team_key"),
                "opponent_team_key": identity.get("opponent_team_key"),
                "stat": key[1],
                "line": key[2],
                "source_book_count": len(books.get(key, set())),
                "source_sides_present": sorted(sides.get(key, set())),
                "two_way_sportsbook_quote_count": len(quotes),
                "sportsbook_quotes": quotes,
                "step_5l_prop_line": {
                    "player_id": key[0],
                    "stat": key[1],
                    "line": key[2],
                    "sportsbook_quotes": quotes if quotes else None,
                },
            }
        )
    rows.sort(key=lambda row: (row["game_id"] or "", row["player_id"], row["stat"], row["line"]))
    if len(rows) > MAX_NORMALIZED_LINES:
        raise WNBAPropLineFeedModelInputError(
            f"WNBA Step 5M normalized line board cannot exceed {MAX_NORMALIZED_LINES} lines."
        )
    return rows


def build_prop_line_feed_board(
    raw_feed: dict[str, Any],
    *,
    feed_source: str,
    feed_format: str = CANONICAL_FEED_FORMAT,
    odds_format: str = "american",
    feed_captured_at_utc: str | None = None,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    exclude_stale_quotes: bool = True,
    max_side_pair_skew_seconds: int = DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
    now_utc: datetime | None = None,
    slate_getter: Callable[..., dict[str, Any]] = verify_daily_slate_dataset,
    roster_getter: Callable[..., dict[str, Any]] = get_current_players_dataset,
) -> dict[str, Any]:
    feed_source = _feed_source(feed_source)
    feed_format = _choice(feed_format, SUPPORTED_FEED_FORMATS, "feed_format")
    odds_format = _choice(odds_format, SUPPORTED_ODDS_FORMATS, "odds_format")
    target_date = _target_date(date)
    if not isinstance(season, int) or isinstance(season, bool) or season <= 0:
        raise ValueError("WNBA Step 5M season must be a positive integer.")
    if (
        not isinstance(max_market_age_minutes, int)
        or isinstance(max_market_age_minutes, bool)
        or not 1 <= max_market_age_minutes <= MAX_MARKET_AGE_MINUTES
    ):
        raise ValueError("WNBA Step 5M max_market_age_minutes must be an integer from 1 through 1440.")
    if not isinstance(exclude_stale_quotes, bool):
        raise ValueError("WNBA Step 5M exclude_stale_quotes must be boolean.")
    if (
        not isinstance(max_side_pair_skew_seconds, int)
        or isinstance(max_side_pair_skew_seconds, bool)
        or not 0 <= max_side_pair_skew_seconds <= MAX_SIDE_PAIR_SKEW_SECONDS
    ):
        raise ValueError(
            f"WNBA Step 5M max_side_pair_skew_seconds must be an integer from 0 through {MAX_SIDE_PAIR_SKEW_SECONDS}."
        )
    parsed_feed_capture = None
    if feed_captured_at_utc is not None:
        parsed_feed_capture = _parse_timestamp(feed_captured_at_utc)
        if parsed_feed_capture is None:
            raise ValueError(
                "WNBA Step 5M feed_captured_at_utc must be timezone-aware ISO-8601 when supplied."
            )
        feed_captured_at_utc = parsed_feed_capture.isoformat()

    flattened = _flatten_feed(
        raw_feed,
        feed_format=feed_format,
        feed_captured_at=feed_captured_at_utc,
    )
    try:
        slate = slate_getter(target_date, season)
    except WNBAScheduleUpstreamError as exc:
        raise WNBAPropLineFeedUpstreamError(f"Step 5M official slate lookup failed: {exc}") from exc
    playable_games = _validate_slate(slate, target_date=target_date, season=season)

    try:
        roster = roster_getter(season, current_roster_only=True)
    except WNBAStatsUpstreamError as exc:
        raise WNBAPropLineFeedUpstreamError(f"Step 5M official roster lookup failed: {exc}") from exc
    roster_by_id, roster_by_name = _roster_indexes(roster, season=season)
    team_games = _team_game_index(playable_games)
    team_aliases = _team_alias_index(playable_games)

    current = now_utc or _utc_now()
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("WNBA Step 5M now_utc test override must be timezone-aware.")
    current = current.astimezone(timezone.utc)

    audits: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for offer in flattened:
        audit, normalized = _normalize_offer(
            offer,
            odds_format=odds_format,
            now_utc=current,
            max_market_age_minutes=max_market_age_minutes,
            exclude_stale_quotes=exclude_stale_quotes,
            roster_by_id=roster_by_id,
            roster_by_name=roster_by_name,
            team_games=team_games,
            team_aliases=team_aliases,
        )
        audits.append(audit)
        if normalized is not None:
            eligible.append(normalized)

    selected, conflicts = _select_latest_side_offers(eligible)
    conflict_keys = {
        (
            row["player_id"], row["game_id"], row["stat"], row["line"], row["sportsbook_key"], row["side"]
        )
        for row in conflicts
    }
    for audit in audits:
        key = (
            audit.get("player_id"), audit.get("game_id"), audit.get("stat"), audit.get("line"),
            (audit.get("sportsbook") or "").casefold(), audit.get("side")
        )
        if audit.get("status") == "eligible" and key in conflict_keys:
            audit["status"] = "excluded"
            audit["reason_codes"] = ["same_timestamp_conflicting_same_book_side_price"]

    quotes_by_line, pair_audit = _pair_two_way_quotes(
        selected,
        max_side_pair_skew_seconds=max_side_pair_skew_seconds,
    )
    lines = _line_board(selected, quotes_by_line)
    step_5l_prop_lines = [deepcopy(row["step_5l_prop_line"]) for row in lines]

    config = {
        "feed_format": feed_format,
        "odds_format": odds_format,
        "max_market_age_minutes": max_market_age_minutes,
        "exclude_stale_quotes": exclude_stale_quotes,
        "max_side_pair_skew_seconds": max_side_pair_skew_seconds,
        "market_future_tolerance_seconds": MARKET_FUTURE_TOLERANCE_SECONDS,
        "supported_stats": list(SUPPORTED_STATS),
        "different_lines_never_merged": True,
        "two_way_quotes_require_same_sportsbook": True,
    }
    fingerprint_payload = {
        "feed_source": feed_source,
        "feed_captured_at_utc": feed_captured_at_utc,
        "date": target_date,
        "season": season,
        "model_config": config,
        "line_board": lines,
        "offer_audit": audits,
        "duplicate_conflicts": conflicts,
        "pair_audit": pair_audit,
    }
    fingerprint = _hash(fingerprint_payload)
    paired_quote_count = sum(row["two_way_sportsbook_quote_count"] for row in lines)
    stale_count = sum(audit.get("stale") is True for audit in audits)
    excluded_count = sum(audit.get("status") != "eligible" for audit in audits)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_real_prop_line_feed_normalized_daily_board",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": _utc_now_iso(),
        "line_board_id": f"wnba-5m-lines-{fingerprint[:20]}",
        "line_board_fingerprint_sha256": fingerprint,
        "feed_source": feed_source,
        "feed_format": feed_format,
        "odds_format": odds_format,
        "feed_captured_at_utc": feed_captured_at_utc,
        "season": season,
        "date": target_date,
        "official_slate_reference": {
            "verified_at_utc": slate.get("verified_at_utc"),
            "source_retrieved_at_utc": slate.get("source_retrieved_at_utc"),
            "playable_game_ids": [game.get("game_id") for game in playable_games],
        },
        "official_roster_reference": {
            "retrieved_at_utc": roster.get("retrieved_at_utc"),
            "player_count": roster.get("player_count"),
        },
        "raw_offer_count": len(flattened),
        "eligible_offer_count_before_latest_selection": len(eligible),
        "excluded_offer_count": excluded_count,
        "stale_offer_count": stale_count,
        "duplicate_conflict_count": len(conflicts),
        "normalized_line_count": len(lines),
        "paired_two_way_quote_count": paired_quote_count,
        "line_board": lines,
        "step_5l_prop_lines": step_5l_prop_lines,
        "offer_audit": audits,
        "duplicate_conflicts": conflicts,
        "two_way_pair_audit": pair_audit,
        "model_config": config,
        "adapter_semantics": {
            "sportsbook_lines_are_never_invented": True,
            "player_identity_verified_against_current_official_roster": True,
            "player_game_identity_derived_from_official_playable_slate": True,
            "different_prop_lines_are_never_merged": True,
            "over_under_prices_must_share_sportsbook_and_exact_line": True,
            "one_sided_offer_can_establish_real_line_but_not_two_way_quote": True,
            "stale_quotes_excluded_by_default": True,
            "same_timestamp_price_conflicts_fail_closed": True,
            "feed_market_data_cannot_modify_model_probability": True,
        },
    }


def build_feed_daily_top_five(
    raw_feed: dict[str, Any],
    *,
    feed_source: str,
    feed_format: str = CANONICAL_FEED_FORMAT,
    odds_format: str = "american",
    feed_captured_at_utc: str | None = None,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    exclude_stale_quotes: bool = True,
    max_side_pair_skew_seconds: int = DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
    line_board_builder: Callable[..., dict[str, Any]] = build_prop_line_feed_board,
    daily_builder: Callable[..., dict[str, Any]] = build_daily_slate_top_five,
    **daily_kwargs: Any,
) -> dict[str, Any]:
    line_board = line_board_builder(
        raw_feed,
        feed_source=feed_source,
        feed_format=feed_format,
        odds_format=odds_format,
        feed_captured_at_utc=feed_captured_at_utc,
        date=date,
        season=season,
        max_market_age_minutes=max_market_age_minutes,
        exclude_stale_quotes=exclude_stale_quotes,
        max_side_pair_skew_seconds=max_side_pair_skew_seconds,
    )
    prop_lines = line_board.get("step_5l_prop_lines") or []
    if not prop_lines:
        daily_result = None
        probability_board = []
        value_board = []
    else:
        daily_result = daily_builder(
            prop_lines,
            date=line_board["date"],
            season=season,
            max_market_age_minutes=max_market_age_minutes,
            exclude_stale_quotes=exclude_stale_quotes,
            **daily_kwargs,
        )
        probability_board = deepcopy(daily_result.get("probability_board") or [])
        value_board = deepcopy(daily_result.get("value_board") or [])

    fingerprint = _hash(
        {
            "line_board_fingerprint_sha256": line_board["line_board_fingerprint_sha256"],
            "step_5l_daily_board_fingerprint_sha256": (
                daily_result.get("daily_board_fingerprint_sha256") if daily_result else None
            ),
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_real_feed_to_daily_top_five_pipeline",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "feed_pipeline_id": f"wnba-5m-pipeline-{fingerprint[:20]}",
        "feed_pipeline_fingerprint_sha256": fingerprint,
        "line_board_reference": {
            "line_board_id": line_board["line_board_id"],
            "line_board_fingerprint_sha256": line_board["line_board_fingerprint_sha256"],
            "normalized_line_count": line_board["normalized_line_count"],
            "paired_two_way_quote_count": line_board["paired_two_way_quote_count"],
        },
        "line_board": line_board,
        "step_5l_daily_top_five": daily_result,
        "probability_board_count": len(probability_board),
        "value_board_count": len(value_board),
        "probability_board": probability_board,
        "value_board": value_board,
        "pipeline_semantics": {
            "real_feed_normalized_before_projection": True,
            "step_5l_remains_frozen_and_authoritative_for_daily_candidate_generation": True,
            "step_5k_remains_authoritative_for_probability_rank": True,
            "no_market_data_can_move_primary_probability_rank": True,
        },
    }
