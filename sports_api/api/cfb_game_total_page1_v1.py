"""Kyre Sports API CFB Game Total Page 1 contract.

Application-facing Game Total discovery data is delivered only through Kyre
Sports API. NCAA owns canonical schedule/team identity and official logo assets.
Sportsbook quotes remain book-specific; exact-line consensus is a safe derived
field and is never an average. Opening/current lines remain separate and line
movement is emitted only when a true opener is independently verified.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import os
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

import cfb_schedule_v3 as ncaa_schedule
from sports_api.collectors.cfb_game_total_market_v1 import (
    collect_fanduel_game_markets,
    collect_the_odds_api_game_markets,
    match_market_rows_to_ncaa_games,
)
from sports_api.collectors.cfb_action_network_game_markets_v1 import (
    collect_action_network_game_markets,
    match_action_rows_to_games,
)

router = APIRouter(prefix="/api/v1/cfb/game-total", tags=["cfb"])
MODEL_VERSION = "CFB GAME TOTAL PAGE1 API V1 • KYRE SPORTS API • UPCOMING RAIL STEP1 R1"
SCHEMA_VERSION = "cfb_game_total_page1_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PHOENIX = ZoneInfo("America/Phoenix")
MAX_AUTO_SCAN_DAYS = 14
FORBIDDEN_PROVIDERS = ["SGO", "ESPN", "ESPN BET"]
NCAA_LOGO_TEMPLATE = "https://www.ncaa.com/sites/default/files/images/logos/schools/bgl/{slug}.svg"
_STARTED_OR_TERMINAL_STATES = (
    "in progress",
    "inprogress",
    "live",
    "halftime",
    "final",
    "completed",
    "complete",
    "closed",
    "ended",
    "game over",
    "canceled",
    "cancelled",
    "postponed",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _kickoff(game: Mapping[str, Any]) -> datetime | None:
    text = _clean(game.get("kickoff_iso") or game.get("start_time_utc"))
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _status_text(game: Mapping[str, Any]) -> str:
    values: list[str] = []
    for key in ("status", "game_status", "state", "status_state", "game_state"):
        value = game.get(key)
        if isinstance(value, Mapping):
            for nested_key in ("state", "type", "name", "description", "detail", "short_detail", "shortDetail"):
                nested = _clean(value.get(nested_key))
                if nested:
                    values.append(nested)
        else:
            text = _clean(value)
            if text:
                values.append(text)
    return " ".join(values).casefold().replace("_", " ").replace("-", " ")


def _is_upcoming_game(game: Mapping[str, Any], now: datetime) -> bool:
    """Return True only while a game is still actionable as a pregame matchup."""
    status = _status_text(game)
    if any(marker in status for marker in _STARTED_OR_TERMINAL_STATES):
        return False

    current = now
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    kickoff = _kickoff(game)
    if kickoff is not None and kickoff <= current.astimezone(timezone.utc):
        return False
    return True


def _load_ncaa_games(day: str) -> list[dict[str, Any]]:
    selected = date.fromisoformat(day).isoformat()
    payload, _attempts = ncaa_schedule._fetch_ncaa_scoreboard_payload(selected)
    if not payload:
        return []
    games, _diag = ncaa_schedule._official_scoreboard_games(payload, selected)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in games:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        game_id = _clean(row.get("game_id") or row.get("identity_key"))
        if not game_id or game_id in seen:
            continue
        if row.get("identity_verified") is not True or row.get("date_matches_query") is not True:
            continue
        seen.add(game_id)
        out.append(row)
    out.sort(key=lambda game: (_clean(game.get("kickoff_iso")), _clean(game.get("game_id"))))
    return out


def _dedupe_games(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for raw in games:
        row = dict(raw)
        game_id = _clean(row.get("game_id") or row.get("identity_key"))
        if not game_id or game_id in seen:
            continue
        seen.add(game_id)
        out.append(row)
    return out


def _resolve_slate_date(*, requested: str | None, now: datetime) -> tuple[str, list[dict[str, Any]]]:
    if requested:
        selected = date.fromisoformat(requested).isoformat()
        return selected, _load_ncaa_games(selected)
    local_now = now.astimezone(PHOENIX)
    for offset in range(MAX_AUTO_SCAN_DAYS + 1):
        day = (local_now.date() + timedelta(days=offset)).isoformat()
        games = _load_ncaa_games(day)
        if not games:
            continue
        upcoming = [game for game in games if _is_upcoming_game(game, now)]
        if upcoming:
            return day, upcoming
    return local_now.date().isoformat(), []


def collect_primary_market_rows() -> list[dict[str, Any]]:
    try:
        return collect_fanduel_game_markets()
    except Exception:
        return []


def collect_secondary_market_rows(missing_games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not missing_games:
        return []
    accepted: list[dict[str, Any]] = []
    remaining = list(missing_games)

    if _clean(os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")):
        try:
            odds_rows = collect_the_odds_api_game_markets()
        except Exception:
            odds_rows = []
        odds_matched = match_market_rows_to_ncaa_games(remaining, odds_rows)
        odds_alias_matched = match_action_rows_to_games(remaining, odds_rows)
        covered: set[str] = set()
        for game in remaining:
            game_id = _clean(game.get("game_id") or game.get("identity_key"))
            quotes = odds_matched.get(game_id, []) or odds_alias_matched.get(game_id, [])
            if quotes:
                covered.add(game_id)
                for raw in quotes:
                    row = dict(raw)
                    row["source_provider"] = "The Odds API"
                    accepted.append(row)
        if covered:
            remaining = [game for game in remaining if _clean(game.get("game_id") or game.get("identity_key")) not in covered]

    if remaining:
        try:
            action_rows = collect_action_network_game_markets()
        except Exception:
            action_rows = []
        action_matched = match_action_rows_to_games(remaining, action_rows)
        for game in remaining:
            game_id = _clean(game.get("game_id") or game.get("identity_key"))
            for raw in action_matched.get(game_id, []):
                row = dict(raw)
                row["source_provider"] = "Action Network"
                accepted.append(row)
    return accepted


def _market_state(games: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    consulted: list[str] = ["FanDuel"]
    primary_rows = collect_primary_market_rows()
    matched = match_market_rows_to_ncaa_games(games, primary_rows)
    primary_alias = match_action_rows_to_games(games, primary_rows)
    for game_id, quotes in primary_alias.items():
        matched.setdefault(game_id, []).extend(
            dict(row) for row in quotes
            if all(
                (_clean(row.get("sportsbook")), _clean(row.get("provider_event_id")), _clean(row.get("provider_market_id")))
                != (_clean(existing.get("sportsbook")), _clean(existing.get("provider_event_id")), _clean(existing.get("provider_market_id")))
                for existing in matched.get(game_id, [])
            )
        )
    missing = [game for game in games if _clean(game.get("game_id") or game.get("identity_key")) not in matched]
    if missing:
        secondary_rows = collect_secondary_market_rows(missing)
        for provider in ("The Odds API", "Action Network"):
            if any(_clean(row.get("source_provider")) == provider for row in secondary_rows):
                consulted.append(provider)
        if secondary_rows:
            secondary = match_market_rows_to_ncaa_games(missing, secondary_rows)
            action_secondary = match_action_rows_to_games(missing, secondary_rows)
            for game in missing:
                game_id = _clean(game.get("game_id") or game.get("identity_key"))
                quotes = secondary.get(game_id, []) or action_secondary.get(game_id, [])
                if quotes:
                    matched.setdefault(game_id, []).extend(dict(row) for row in quotes)
    return matched, consulted


def collect_consensus_market_rows(games: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Collect only the extra verification rows needed for exact-book consensus.

    Action Network is an approved verification source. It is called once for the
    consensus field family; failures are isolated and never break Page 1.
    """
    if not games:
        return {}, []
    try:
        rows = collect_action_network_game_markets()
    except Exception:
        return {}, []
    matched = match_action_rows_to_games(games, rows)
    if not matched:
        return {}, []
    return matched, ["Action Network"]


def _quote_quality(quote: Mapping[str, Any]) -> str:
    if quote.get("total_line") is None:
        return "UNAVAILABLE"
    complete = all(
        quote.get(key) is not None
        for key in (
            "sportsbook", "provider_event_id", "provider_market_id",
            "over_price", "under_price",
            "away_spread", "away_spread_price",
            "home_spread", "home_spread_price",
            "away_moneyline", "home_moneyline", "observed_at_utc",
        )
    )
    return "VERIFIED" if complete else "PARTIAL"


def _public_quote(raw: Mapping[str, Any]) -> dict[str, Any]:
    quote = {
        "sportsbook": _clean(raw.get("sportsbook")) or None,
        "market": _clean(raw.get("market")) or "game_total",
        "provider_event_id": _clean(raw.get("provider_event_id")) or None,
        "provider_market_id": _clean(raw.get("provider_market_id")) or None,
        "total_line": raw.get("total_line"),
        "over_price": raw.get("over_price"),
        "under_price": raw.get("under_price"),
        "away_spread": raw.get("away_spread"),
        "away_spread_price": raw.get("away_spread_price"),
        "home_spread": raw.get("home_spread"),
        "home_spread_price": raw.get("home_spread_price"),
        "away_moneyline": raw.get("away_moneyline"),
        "home_moneyline": raw.get("home_moneyline"),
        "observed_at_utc": _clean(raw.get("observed_at_utc")) or None,
        "line_status": _clean(raw.get("line_status")) or None,
        "source_provider": _clean(raw.get("source_provider")) or None,
    }
    if raw.get("opening_total_verified") is True and _num(raw.get("opening_total")) is not None:
        quote["opening_total"] = _num(raw.get("opening_total"))
        quote["opening_total_verified"] = True
        quote["opening_observed_at_utc"] = _clean(raw.get("opening_observed_at_utc")) or None
    quote["line_integrity"] = _quote_quality(quote)
    return quote


def _team_identity(game: Mapping[str, Any], side: str) -> dict[str, Any]:
    slug = _clean(game.get(f"{side}_team_slug")).strip("/")
    name = _clean(game.get(f"{side}_team")) or side.title()
    if not slug:
        initials = "".join(part[:1] for part in name.split()[:3]).upper() or "CFB"
        return {
            "kyre_team_id": None,
            "ncaa_school_slug": None,
            "logo_url": None,
            "logo_status": "TEAM_IDENTITY_PENDING",
            "fallback_monogram": initials,
        }
    initials = "".join(part[:1] for part in name.split()[:3]).upper() or slug[:3].upper()
    return {
        "kyre_team_id": f"KYRE-CFB-{slug}",
        "ncaa_school_slug": slug,
        "logo_url": NCAA_LOGO_TEMPLATE.format(slug=slug),
        "logo_status": "VERIFIED_NCAA_ASSET",
        "fallback_monogram": initials,
    }


def _dedupe_book_quotes(quotes: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for raw in quotes:
        book = _clean(raw.get("sportsbook"))
        line = _num(raw.get("total_line"))
        if not book or line is None:
            continue
        row = dict(raw)
        previous = latest.get(book)
        if previous is None or _clean(row.get("observed_at_utc")) >= _clean(previous.get("observed_at_utc")):
            latest[book] = row
    return [latest[key] for key in sorted(latest)]


def _market_consensus(quotes: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = _dedupe_book_quotes(quotes)
    public_rows = [
        {
            "sportsbook": _clean(row.get("sportsbook")),
            "total_line": _num(row.get("total_line")),
            "over_price": row.get("over_price"),
            "under_price": row.get("under_price"),
            "observed_at_utc": _clean(row.get("observed_at_utc")) or None,
        }
        for row in rows
    ]
    if not public_rows:
        return {
            "status": "MARKET_NOT_POSTED_YET",
            "consensus_line": None,
            "books_reporting": 0,
            "method": "EXACT_MODE_NO_AVERAGE",
            "book_lines": [],
        }
    counts = Counter(float(row["total_line"]) for row in public_rows if row["total_line"] is not None)
    ranked = counts.most_common()
    if len(public_rows) == 1:
        return {
            "status": "SINGLE_BOOK_ONLY",
            "consensus_line": public_rows[0]["total_line"],
            "books_reporting": 1,
            "method": "EXACT_MODE_NO_AVERAGE",
            "book_lines": public_rows,
        }
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        consensus_line = None
        status = "NO_CLEAR_CONSENSUS"
    else:
        consensus_line = ranked[0][0]
        status = "VERIFIED_EXACT_CLUSTER"
    return {
        "status": status,
        "consensus_line": consensus_line,
        "books_reporting": len(public_rows),
        "method": "EXACT_MODE_NO_AVERAGE",
        "book_lines": public_rows,
    }


def _line_movement(current_quote: Mapping[str, Any], quotes: list[Mapping[str, Any]]) -> dict[str, Any]:
    current_total = _num(current_quote.get("total_line"))
    if current_total is None:
        return {
            "status": "CURRENT_LINE_NOT_POSTED",
            "opening_total": None,
            "current_total": None,
            "move": None,
            "opening_observed_at_utc": None,
        }
    current_book = _clean(current_quote.get("sportsbook"))
    candidates = [current_quote] + [row for row in quotes if _clean(row.get("sportsbook")) == current_book]
    verified = next(
        (
            row for row in candidates
            if row.get("opening_total_verified") is True and _num(row.get("opening_total")) is not None
        ),
        None,
    )
    if verified is None:
        return {
            "status": "OPENING_LINE_NOT_VERIFIED",
            "opening_total": None,
            "current_total": current_total,
            "move": None,
            "opening_observed_at_utc": None,
        }
    opening_total = _num(verified.get("opening_total"))
    assert opening_total is not None
    return {
        "status": "VERIFIED_MOVEMENT",
        "opening_total": opening_total,
        "current_total": current_total,
        "move": round(current_total - opening_total, 1),
        "opening_observed_at_utc": _clean(verified.get("opening_observed_at_utc")) or None,
    }


def _public_game(
    game: Mapping[str, Any],
    quotes: list[dict[str, Any]],
    consensus_quotes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row = dict(game)
    for key in tuple(row):
        if str(key).casefold().startswith("espn"):
            row.pop(key, None)
    row["market_quotes"] = [_public_quote(quote) for quote in quotes]
    row["market_quote_count"] = len(row["market_quotes"])
    row["market_integrity"] = (
        "VERIFIED" if any(q["line_integrity"] == "VERIFIED" for q in row["market_quotes"])
        else "PARTIAL" if row["market_quotes"] else "UNAVAILABLE"
    )
    row["team_identity"] = {
        "away": _team_identity(row, "away"),
        "home": _team_identity(row, "home"),
    }
    extra = [_public_quote(quote) for quote in (consensus_quotes or [])]
    combined = list(row["market_quotes"]) + extra
    row["market_consensus"] = _market_consensus(combined)
    current_quote = next(
        (quote for quote in row["market_quotes"] if _num(quote.get("total_line")) is not None),
        {},
    )
    row["line_movement"] = _line_movement(current_quote, combined)
    return row


def build_page1_payload(*, game_date: str | None = None, now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict[str, Any]:
    now = now_provider()
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        selected_day, resolved_games = _resolve_slate_date(requested=game_date, now=now)
    except ValueError as exc:
        raise ValueError("game_date must be YYYY-MM-DD") from exc

    games = _dedupe_games([dict(game) for game in resolved_games if isinstance(game, Mapping)])
    games = [game for game in games if _is_upcoming_game(game, now)]
    market_map, consulted = _market_state(games)
    consensus_map, consensus_consulted = collect_consensus_market_rows(games)
    for provider in consensus_consulted:
        if provider not in consulted:
            consulted.append(provider)
    public_games: list[dict[str, Any]] = []
    for game in games:
        game_id = _clean(game.get("game_id") or game.get("identity_key"))
        public_games.append(
            _public_game(
                game,
                market_map.get(game_id, []),
                consensus_map.get(game_id, []),
            )
        )

    verified = sum(1 for game in public_games if game.get("market_integrity") == "VERIFIED")
    partial = sum(1 for game in public_games if game.get("market_integrity") == "PARTIAL")
    unavailable = sum(1 for game in public_games if game.get("market_integrity") == "UNAVAILABLE")
    return {
        "service": "Kyre Sports API",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "selected_date": selected_day,
        "generated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "games": public_games,
        "summary": {
            "games": len(public_games),
            "verified_market_games": verified,
            "partial_market_games": partial,
            "market_unavailable_games": unavailable,
        },
        "routing": {
            "application_gateway": "Kyre Sports API",
            "schedule_primary": "NCAA",
            "identity_primary": "NCAA",
            "team_logo_primary": "NCAA official school asset",
            "market_primary": "FanDuel",
            "market_secondary": ["The Odds API", "Action Network"],
            "consensus_verification": "Action Network exact current book lines when available",
            "provider_calls": consulted,
            "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_INFLUENCE,
            "consensus_averaging": False,
            "frontend_provider_selection": False,
            "line_movement_requires_verified_opener": True,
            "pregame_visibility": "UPCOMING_ONLY",
            "fabrication": False,
            "null_to_zero": False,
            "forbidden_providers": list(FORBIDDEN_PROVIDERS),
        },
    }


@router.get("/page1")
def page1(game_date: str | None = Query(None, min_length=10, max_length=10)) -> dict[str, Any]:
    try:
        return build_page1_payload(game_date=game_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = [
    "FORBIDDEN_PROVIDERS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NCAA_LOGO_TEMPLATE",
    "SCHEMA_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_is_upcoming_game",
    "_line_movement",
    "_market_consensus",
    "_public_game",
    "build_page1_payload",
    "collect_consensus_market_rows",
    "collect_primary_market_rows",
    "collect_secondary_market_rows",
    "page1",
    "router",
]
