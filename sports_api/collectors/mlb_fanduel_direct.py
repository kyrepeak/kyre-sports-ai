"""Read-only FanDuel MLB game-odds collector with official MLB schedule reconciliation.

This module intentionally covers only canonical pregame game markets:
Moneyline, Run Line, and Total Runs. It performs anonymous GET requests only.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

FANDUEL_BASE_URL = "https://api.sportsbook.fanduel.com"
FANDUEL_PUBLIC_WEB_KEY = "FhMFpcPWXMeyZxOx"
MLB_STATSAPI_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
FANDUEL_REGION = "NJ"
MAX_RESPONSE_BYTES = 20_000_000
DEFAULT_TIMEOUT_SECONDS = 25
EASTERN = ZoneInfo("America/New_York")

FANDUEL_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-MLB/1.0; read-only)",
    "Origin": "https://sportsbook.fanduel.com",
    "Referer": "https://sportsbook.fanduel.com/",
    "x-sportsbook-region": FANDUEL_REGION,
}

CORE_MARKET_NAMES = {
    "moneyline": "Moneyline",
    "run_line": "Run Line",
    "total": "Total Runs",
}


class MLBMarketCollectorError(RuntimeError):
    """Raised when a live payload cannot be safely normalized."""


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        result: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("_attachment_key", str(key))
                result.append(row)
        return result
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _iso_utc(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise MLBMarketCollectorError("missing ISO timestamp")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise MLBMarketCollectorError(f"invalid ISO timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise MLBMarketCollectorError(f"timestamp must be timezone-aware: {value!r}")
    return parsed.astimezone(timezone.utc)


def _get_json(
    url: str,
    params: Mapping[str, Any],
    *,
    headers: Mapping[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    query = urlencode({str(k): str(v) for k, v in params.items()})
    request = Request(
        f"{url}?{query}",
        headers=dict(headers or {}),
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        status = int(getattr(response, "status", 0) or 0)
        if status != 200:
            raise MLBMarketCollectorError(f"GET {url} returned HTTP {status}")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise MLBMarketCollectorError(f"GET {url} exceeded {MAX_RESPONSE_BYTES} bytes")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MLBMarketCollectorError(f"GET {url} did not return valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise MLBMarketCollectorError(f"GET {url} did not return a JSON object")
    return payload


def fetch_fanduel_mlb_landing(*, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    return _get_json(
        f"{FANDUEL_BASE_URL}/sbapi/content-managed-page",
        {
            "_ak": FANDUEL_PUBLIC_WEB_KEY,
            "page": "CUSTOM",
            "customPageId": "mlb",
            "timezone": "America/New_York",
        },
        headers=FANDUEL_HEADERS,
        timeout=timeout,
    )


def fetch_fanduel_event_page(
    event_id: str | int,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return _get_json(
        f"{FANDUEL_BASE_URL}/sbapi/event-page",
        {"_ak": FANDUEL_PUBLIC_WEB_KEY, "eventId": str(event_id)},
        headers=FANDUEL_HEADERS,
        timeout=timeout,
    )


def fetch_mlb_schedule(
    slate_date: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return _get_json(
        MLB_STATSAPI_SCHEDULE_URL,
        {"sportId": "1", "date": slate_date},
        headers={"Accept": "application/json", "User-Agent": FANDUEL_HEADERS["User-Agent"]},
        timeout=timeout,
    )


def _event_id(event: Mapping[str, Any]) -> str:
    return str(
        event.get("eventId")
        or event.get("id")
        or event.get("_attachment_key")
        or ""
    ).strip()


def _event_name(event: Mapping[str, Any]) -> str:
    return str(
        event.get("name")
        or event.get("eventName")
        or event.get("displayName")
        or ""
    ).strip()


def _strip_pitcher_suffix(team: str) -> str:
    return re.sub(r"\s+\([^()]*\)\s*$", "", str(team or "")).strip()


def parse_fanduel_matchup(event_name: str) -> tuple[str, str]:
    text = str(event_name or "").strip()
    parts = text.split(" @ ")
    if len(parts) != 2:
        raise MLBMarketCollectorError(f"not a two-team MLB matchup: {event_name!r}")
    away = _strip_pitcher_suffix(parts[0])
    home = _strip_pitcher_suffix(parts[1])
    if not away or not home:
        raise MLBMarketCollectorError(f"missing team name in matchup: {event_name!r}")
    return away, home


def _normalize_team_name(name: str) -> str:
    text = str(name or "").casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _schedule_games(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for date_row in payload.get("dates") or []:
        if not isinstance(date_row, dict):
            continue
        for game in date_row.get("games") or []:
            if isinstance(game, dict):
                result.append(dict(game))
    return result


def _official_team(game: Mapping[str, Any], side: str) -> tuple[int | None, str]:
    teams = game.get("teams") or {}
    side_row = teams.get(side) or {} if isinstance(teams, dict) else {}
    team = side_row.get("team") or {} if isinstance(side_row, dict) else {}
    team_id = team.get("id") if isinstance(team, dict) else None
    team_name = str(team.get("name") or "") if isinstance(team, dict) else ""
    try:
        normalized_id = int(team_id) if team_id is not None else None
    except (TypeError, ValueError):
        normalized_id = None
    return normalized_id, team_name.strip()


def reconcile_official_game(
    schedule_payload: Mapping[str, Any],
    *,
    away_team: str,
    home_team: str,
    sportsbook_start_utc: str,
) -> tuple[dict[str, Any], str]:
    away_key = _normalize_team_name(away_team)
    home_key = _normalize_team_name(home_team)
    candidates: list[dict[str, Any]] = []
    for game in _schedule_games(schedule_payload):
        _, official_away = _official_team(game, "away")
        _, official_home = _official_team(game, "home")
        if (
            _normalize_team_name(official_away) == away_key
            and _normalize_team_name(official_home) == home_key
        ):
            candidates.append(game)

    if not candidates:
        raise MLBMarketCollectorError(
            f"no official MLB schedule match for {away_team} @ {home_team}"
        )
    if len(candidates) == 1:
        return candidates[0], "teams_exact"

    sportsbook_dt = _iso_utc(sportsbook_start_utc)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for game in candidates:
        game_date = str(game.get("gameDate") or "").strip()
        if not game_date:
            continue
        delta_seconds = abs((_iso_utc(game_date) - sportsbook_dt).total_seconds())
        ranked.append((delta_seconds, game))
    if not ranked:
        raise MLBMarketCollectorError(
            f"ambiguous official MLB schedule match for {away_team} @ {home_team}"
        )
    ranked.sort(key=lambda item: item[0])
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        raise MLBMarketCollectorError(
            f"ambiguous official MLB start-time match for {away_team} @ {home_team}"
        )
    if ranked[0][0] > 6 * 60 * 60:
        raise MLBMarketCollectorError(
            f"official MLB start-time mismatch exceeds six hours for {away_team} @ {home_team}"
        )
    return ranked[0][1], "teams_and_nearest_start"


def _market_name(market: Mapping[str, Any]) -> str:
    return str(
        market.get("marketName")
        or market.get("name")
        or market.get("displayName")
        or ""
    ).strip()


def _market_is_open_pregame(market: Mapping[str, Any]) -> bool:
    status = str(market.get("marketStatus") or market.get("status") or "").strip().upper()
    if status != "OPEN":
        return False
    return market.get("inPlay") is not True


def _find_core_market(
    markets: list[dict[str, Any]],
    exact_name: str,
) -> dict[str, Any] | None:
    candidates = [
        market
        for market in markets
        if _market_name(market) == exact_name and _market_is_open_pregame(market)
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda market: (
            int(market.get("sortPriority") or 10_000),
            str(market.get("marketId") or market.get("_attachment_key") or ""),
        )
    )
    return candidates[0]


def _american_odds(runner: Mapping[str, Any]) -> int:
    win = runner.get("winRunnerOdds") or {}
    display = win.get("americanDisplayOdds") or {} if isinstance(win, dict) else {}
    value = (
        display.get("americanOddsInt")
        if isinstance(display, dict)
        else None
    )
    if value is None and isinstance(display, dict):
        value = display.get("americanOdds")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise MLBMarketCollectorError(
            f"runner {runner.get('runnerName')!r} has no valid American odds"
        ) from exc


def _runner_role(runner: Mapping[str, Any]) -> str:
    result = runner.get("result") or {}
    role = result.get("type") if isinstance(result, dict) else None
    return str(role or "").strip().upper()


def _active_runners(market: Mapping[str, Any]) -> list[dict[str, Any]]:
    runners = _rows(market.get("runners"))
    return [
        runner
        for runner in runners
        if str(runner.get("runnerStatus") or "").strip().upper() in {"", "ACTIVE"}
    ]


def _role_runner(market: Mapping[str, Any], role: str) -> dict[str, Any]:
    matches = [runner for runner in _active_runners(market) if _runner_role(runner) == role]
    if len(matches) != 1:
        raise MLBMarketCollectorError(
            f"market {_market_name(market)!r} expected one {role} runner, found {len(matches)}"
        )
    return matches[0]


def _market_id(market: Mapping[str, Any]) -> str:
    return str(market.get("marketId") or market.get("_attachment_key") or "").strip()


def _normalize_moneyline(market: Mapping[str, Any]) -> dict[str, Any]:
    away = _role_runner(market, "AWAY")
    home = _role_runner(market, "HOME")
    return {
        "market_id": _market_id(market),
        "market_time_utc": str(market.get("marketTime") or "").strip() or None,
        "away_odds": _american_odds(away),
        "home_odds": _american_odds(home),
        "away_selection_id": away.get("selectionId"),
        "home_selection_id": home.get("selectionId"),
    }


def _float_handicap(runner: Mapping[str, Any]) -> float:
    try:
        return float(runner.get("handicap"))
    except (TypeError, ValueError) as exc:
        raise MLBMarketCollectorError(
            f"runner {runner.get('runnerName')!r} has invalid handicap"
        ) from exc


def _normalize_run_line(market: Mapping[str, Any]) -> dict[str, Any]:
    away = _role_runner(market, "AWAY")
    home = _role_runner(market, "HOME")
    return {
        "market_id": _market_id(market),
        "market_time_utc": str(market.get("marketTime") or "").strip() or None,
        "away_line": _float_handicap(away),
        "away_odds": _american_odds(away),
        "home_line": _float_handicap(home),
        "home_odds": _american_odds(home),
        "away_selection_id": away.get("selectionId"),
        "home_selection_id": home.get("selectionId"),
    }


def _normalize_total(market: Mapping[str, Any]) -> dict[str, Any]:
    over = _role_runner(market, "OVER")
    under = _role_runner(market, "UNDER")
    over_line = _float_handicap(over)
    under_line = _float_handicap(under)
    if over_line != under_line:
        raise MLBMarketCollectorError(
            f"Total Runs market has mismatched lines: {over_line} vs {under_line}"
        )
    return {
        "market_id": _market_id(market),
        "market_time_utc": str(market.get("marketTime") or "").strip() or None,
        "line": over_line,
        "over_odds": _american_odds(over),
        "under_odds": _american_odds(under),
        "over_selection_id": over.get("selectionId"),
        "under_selection_id": under.get("selectionId"),
    }


def normalize_core_markets(markets: list[dict[str, Any]]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    moneyline = _find_core_market(markets, CORE_MARKET_NAMES["moneyline"])
    run_line = _find_core_market(markets, CORE_MARKET_NAMES["run_line"])
    total = _find_core_market(markets, CORE_MARKET_NAMES["total"])
    if moneyline is not None:
        normalized["moneyline"] = _normalize_moneyline(moneyline)
    if run_line is not None:
        normalized["run_line"] = _normalize_run_line(run_line)
    if total is not None:
        normalized["total"] = _normalize_total(total)
    return normalized


def _game_status(game: Mapping[str, Any]) -> str | None:
    status = game.get("status") or {}
    if not isinstance(status, dict):
        return None
    return str(status.get("detailedState") or status.get("abstractGameState") or "").strip() or None


def _normalize_game(
    *,
    event: Mapping[str, Any],
    event_page: Mapping[str, Any],
    schedule_payload: Mapping[str, Any],
) -> dict[str, Any]:
    event_name = _event_name(event)
    away_name, home_name = parse_fanduel_matchup(event_name)
    event_start = str(event.get("openDate") or "").strip()
    if not event_start:
        raise MLBMarketCollectorError(f"FanDuel event {_event_id(event)} has no openDate")

    official_game, match_method = reconcile_official_game(
        schedule_payload,
        away_team=away_name,
        home_team=home_name,
        sportsbook_start_utc=event_start,
    )
    official_away_id, official_away_name = _official_team(official_game, "away")
    official_home_id, official_home_name = _official_team(official_game, "home")

    attachments = event_page.get("attachments") or {}
    if not isinstance(attachments, dict):
        raise MLBMarketCollectorError(f"FanDuel event {_event_id(event)} has no attachments")
    markets = _rows(attachments.get("markets"))
    core = normalize_core_markets(markets)
    if not core:
        raise MLBMarketCollectorError(f"FanDuel event {_event_id(event)} has no open core markets")

    game_pk = official_game.get("gamePk")
    try:
        official_game_id = int(game_pk)
    except (TypeError, ValueError) as exc:
        raise MLBMarketCollectorError("official MLB schedule game is missing gamePk") from exc

    return {
        "official_game_id": official_game_id,
        "sportsbook_event_id": _event_id(event),
        "sportsbook_event_name": event_name,
        "official_schedule_match": match_method,
        "scheduled_start_utc": str(official_game.get("gameDate") or event_start),
        "sportsbook_start_utc": event_start,
        "game_status": _game_status(official_game),
        "away_team": {"id": official_away_id, "name": official_away_name},
        "home_team": {"id": official_home_id, "name": official_home_name},
        "sportsbook": "FanDuel",
        "sportsbook_region": FANDUEL_REGION,
        "markets": core,
        "market_availability": {
            "moneyline": "moneyline" in core,
            "run_line": "run_line" in core,
            "total": "total" in core,
        },
        "fully_priced": all(key in core for key in ("moneyline", "run_line", "total")),
    }


def collect_live_mlb_game_odds(
    *,
    now_utc: datetime | None = None,
    max_events: int = 30,
    landing_fetcher: Callable[[], Mapping[str, Any]] | None = None,
    event_fetcher: Callable[[str], Mapping[str, Any]] | None = None,
    schedule_fetcher: Callable[[str], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Collect and normalize live FanDuel pregame MLB game odds.

    The collector fails closed per event: a sportsbook event is included only when it
    can be reconciled to the official MLB schedule and at least one canonical core
    market can be normalized.
    """

    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if max_events <= 0:
        raise ValueError("max_events must be positive")

    get_landing = landing_fetcher or fetch_fanduel_mlb_landing
    get_event = event_fetcher or (lambda event_id: fetch_fanduel_event_page(event_id))
    get_schedule = schedule_fetcher or fetch_mlb_schedule

    landing = dict(get_landing())
    attachments = landing.get("attachments") or {}
    if not isinstance(attachments, dict):
        raise MLBMarketCollectorError("FanDuel MLB landing page has no attachments object")
    landing_events = _rows(attachments.get("events"))

    candidates: list[dict[str, Any]] = []
    for event in landing_events:
        name = _event_name(event)
        if " @ " not in name:
            continue
        start_text = str(event.get("openDate") or "").strip()
        if not start_text:
            continue
        try:
            start_utc = _iso_utc(start_text)
        except MLBMarketCollectorError:
            continue
        if start_utc <= now:
            continue
        candidates.append(event)
    candidates.sort(key=lambda event: str(event.get("openDate") or ""))
    candidates = candidates[:max_events]

    schedule_cache: dict[str, Mapping[str, Any]] = {}
    normalized_games: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for event in candidates:
        event_id = _event_id(event)
        try:
            start_utc = _iso_utc(str(event.get("openDate") or ""))
            slate_date = start_utc.astimezone(EASTERN).date().isoformat()
            if slate_date not in schedule_cache:
                schedule_cache[slate_date] = dict(get_schedule(slate_date))
            event_page = dict(get_event(event_id))
            normalized_games.append(
                _normalize_game(
                    event=event,
                    event_page=event_page,
                    schedule_payload=schedule_cache[slate_date],
                )
            )
        except Exception as exc:  # event-level fail-closed boundary
            rejected.append(
                {
                    "sportsbook_event_id": event_id or None,
                    "sportsbook_event_name": _event_name(event) or None,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )

    fully_priced_count = sum(1 for game in normalized_games if game.get("fully_priced") is True)
    return {
        "data_type": "mlb_live_game_odds_snapshot_v1",
        "schema_version": 1,
        "collected_at_utc": now.isoformat(),
        "provider": "FanDuel",
        "transport": "anonymous_public_get_only",
        "http_methods": ["GET"],
        "sportsbook_region": FANDUEL_REGION,
        "landing_event_count": len(landing_events),
        "candidate_pregame_event_count": len(candidates),
        "matched_game_count": len(normalized_games),
        "fully_priced_game_count": fully_priced_count,
        "official_schedule_dates": sorted(schedule_cache),
        "games": normalized_games,
        "rejected_events": rejected,
    }


__all__ = [
    "CORE_MARKET_NAMES",
    "FANDUEL_REGION",
    "MLBMarketCollectorError",
    "collect_live_mlb_game_odds",
    "fetch_fanduel_event_page",
    "fetch_fanduel_mlb_landing",
    "fetch_mlb_schedule",
    "normalize_core_markets",
    "parse_fanduel_matchup",
    "reconcile_official_game",
]
