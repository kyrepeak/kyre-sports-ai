"""NBA Over/Under Step 2 — NBA-only data source and API foundation.

This layer normalizes game identity, records, venue/time context, and totals
market inputs for later NBA Over/Under steps. It does not render Streamlit,
activate a route, project a score, rank a pick, or let sportsbook data influence
any model. Network transport is injected so the contract is deterministic and
fail-closed in tests.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, Protocol, Sequence
from zoneinfo import ZoneInfo

MODEL_VERSION = "NBA_OVER_UNDER_STEP2_DATA_FOUNDATION_V1"
SPORT = "NBA"
PAGE_SCOPE = "NBA_OVER_UNDER"
PHOENIX_TIMEZONE = "America/Phoenix"
PHOENIX_TZ = ZoneInfo(PHOENIX_TIMEZONE)

NBA_OFFICIAL_SCHEDULE_URL = (
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
)
ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
)
THE_ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
ODDS_SPORT_KEY = "basketball_nba"
ODDS_MARKET = "totals"

MAY_RENDER_UI = False
MAY_ACTIVATE_ROUTER = False
MAY_MODIFY_SHARED_APIS = False
MAY_MODIFY_OTHER_SPORTS = False
MODEL_PROJECTION_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

NBA_TEAM_ABBREVIATIONS = frozenset(
    {
        "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET",
        "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN",
        "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS",
        "TOR", "UTA", "WAS",
    }
)


class NBADataSourceError(RuntimeError):
    """Raised when the NBA data boundary cannot return trustworthy data."""


class JSONTransport(Protocol):
    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: int | float = 8,
    ) -> Any: ...


class RequestsJSONTransport:
    """Small production transport kept outside the normalization rules."""

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: int | float = 8,
    ) -> Any:
        import requests

        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        text = (response.text or "").lstrip()
        if not text or not text.startswith(("{", "[")):
            raise NBADataSourceError(f"non-JSON response from {url}")
        return response.json()


def source_contract() -> dict[str, Any]:
    return {
        "version": MODEL_VERSION,
        "sport": SPORT,
        "page_scope": PAGE_SCOPE,
        "schedule_primary": "NBA_OFFICIAL_CDN",
        "schedule_fallback": "ESPN_NBA_SCOREBOARD",
        "odds_provider": "THE_ODDS_API",
        "odds_sport_key": ODDS_SPORT_KEY,
        "odds_market": ODDS_MARKET,
        "timezone": PHOENIX_TIMEZONE,
        "projection_influence": MODEL_PROJECTION_INFLUENCE,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "other_sports_allowed": MAY_MODIFY_OTHER_SPORTS,
        "ui_activation": MAY_RENDER_UI,
        "router_activation": MAY_ACTIVATE_ROUTER,
        "shared_api_mutation": MAY_MODIFY_SHARED_APIS,
    }


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise NBADataSourceError("game time is required")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise NBADataSourceError(f"invalid game time: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _day_text(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        raise NBADataSourceError("selected date is required")
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise NBADataSourceError(f"invalid selected date: {value!r}") from exc


def to_phoenix_time(value: Any) -> str:
    return _parse_datetime(value).astimezone(PHOENIX_TZ).isoformat(timespec="seconds")


def _phoenix_date(value: Any) -> str:
    return _parse_datetime(value).astimezone(PHOENIX_TZ).date().isoformat()


def _status_official(game_status: Any, status_text: Any = "") -> str:
    try:
        code = int(game_status)
    except (TypeError, ValueError):
        code = 0
    text = str(status_text or "").lower()
    if code == 3 or "final" in text:
        return "FINAL"
    if code == 2 or any(token in text for token in ("quarter", "half", "ot", "live")):
        return "LIVE"
    return "UPCOMING"


def _status_espn(state: Any, description: Any = "") -> str:
    state_text = str(state or "").strip().lower()
    description_text = str(description or "").lower()
    if state_text in {"post", "final"} or "final" in description_text:
        return "FINAL"
    if state_text in {"in", "live"}:
        return "LIVE"
    return "UPCOMING"


def _is_nba_pair(home_abbr: Any, away_abbr: Any) -> bool:
    home = str(home_abbr or "").strip().upper()
    away = str(away_abbr or "").strip().upper()
    return home in NBA_TEAM_ABBREVIATIONS and away in NBA_TEAM_ABBREVIATIONS and home != away


def _official_team_name(team: Mapping[str, Any]) -> str:
    city = str(team.get("teamCity") or "").strip()
    name = str(team.get("teamName") or team.get("teamTricode") or "").strip()
    return " ".join(part for part in (city, name) if part).strip()


def _official_record(team: Mapping[str, Any]) -> str:
    wins = team.get("wins")
    losses = team.get("losses")
    if wins is None or losses is None:
        return ""
    return f"{wins}-{losses}"


def normalize_official_schedule(
    payload: Mapping[str, Any], selected_date: str | date | datetime
) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise NBADataSourceError("official schedule payload must be an object")
    league = payload.get("leagueSchedule")
    if not isinstance(league, Mapping):
        raise NBADataSourceError("official schedule missing leagueSchedule")
    game_dates = league.get("gameDates")
    if not isinstance(game_dates, list):
        raise NBADataSourceError("official schedule missing gameDates")

    target = _day_text(selected_date)
    rows: list[dict[str, Any]] = []
    for block in game_dates:
        if not isinstance(block, Mapping):
            continue
        games = block.get("games") or []
        if not isinstance(games, list):
            continue
        for game in games:
            if not isinstance(game, Mapping):
                continue
            home = game.get("homeTeam") or {}
            away = game.get("awayTeam") or {}
            if not isinstance(home, Mapping) or not isinstance(away, Mapping):
                continue
            home_abbr = str(home.get("teamTricode") or "").strip().upper()
            away_abbr = str(away.get("teamTricode") or "").strip().upper()
            if not _is_nba_pair(home_abbr, away_abbr):
                continue
            raw_tip = game.get("gameDateTimeUTC")
            if not raw_tip:
                continue
            try:
                game_day = _phoenix_date(raw_tip)
                phoenix_tip = to_phoenix_time(raw_tip)
            except NBADataSourceError:
                continue
            if game_day != target:
                continue
            rows.append(
                {
                    "game_id": str(game.get("gameId") or ""),
                    "game_date_phoenix": game_day,
                    "start_time_utc": str(raw_tip),
                    "tip_phoenix": phoenix_tip,
                    "status": _status_official(
                        game.get("gameStatus"), game.get("gameStatusText")
                    ),
                    "status_text": str(game.get("gameStatusText") or ""),
                    "home_team_id": int(home.get("teamId") or 0),
                    "home_team": _official_team_name(home),
                    "home_abbr": home_abbr,
                    "home_record": _official_record(home),
                    "away_team_id": int(away.get("teamId") or 0),
                    "away_team": _official_team_name(away),
                    "away_abbr": away_abbr,
                    "away_record": _official_record(away),
                    "arena": str(game.get("arenaName") or "").strip(),
                    "city": str(game.get("arenaCity") or "").strip(),
                    "source": "NBA_OFFICIAL_CDN",
                }
            )
    return rows


def _espn_record(competitor: Mapping[str, Any]) -> str:
    records = competitor.get("records") or []
    if not isinstance(records, list):
        return ""
    preferred = next(
        (
            record
            for record in records
            if isinstance(record, Mapping) and str(record.get("type") or "").lower() == "total"
        ),
        None,
    )
    record = preferred or next((item for item in records if isinstance(item, Mapping)), None)
    return str((record or {}).get("summary") or "")


def normalize_espn_schedule(
    payload: Mapping[str, Any], selected_date: str | date | datetime
) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise NBADataSourceError("ESPN schedule payload must be an object")
    events = payload.get("events")
    if not isinstance(events, list):
        raise NBADataSourceError("ESPN schedule missing events")

    target = _day_text(selected_date)
    rows: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        competitions = event.get("competitions") or []
        if not isinstance(competitions, list) or not competitions:
            continue
        competition = competitions[0]
        if not isinstance(competition, Mapping):
            continue
        sides: dict[str, Mapping[str, Any]] = {}
        for competitor in competition.get("competitors") or []:
            if isinstance(competitor, Mapping):
                sides[str(competitor.get("homeAway") or "").lower()] = competitor
        home_comp = sides.get("home") or {}
        away_comp = sides.get("away") or {}
        home_team = home_comp.get("team") or {}
        away_team = away_comp.get("team") or {}
        if not isinstance(home_team, Mapping) or not isinstance(away_team, Mapping):
            continue
        home_abbr = str(home_team.get("abbreviation") or "").strip().upper()
        away_abbr = str(away_team.get("abbreviation") or "").strip().upper()
        if not _is_nba_pair(home_abbr, away_abbr):
            continue
        raw_tip = event.get("date") or competition.get("date")
        if not raw_tip:
            continue
        try:
            game_day = _phoenix_date(raw_tip)
            phoenix_tip = to_phoenix_time(raw_tip)
        except NBADataSourceError:
            continue
        if game_day != target:
            continue
        status_type = ((event.get("status") or {}).get("type") or {})
        if not isinstance(status_type, Mapping):
            status_type = {}
        venue = competition.get("venue") or {}
        if not isinstance(venue, Mapping):
            venue = {}
        address = venue.get("address") or {}
        if not isinstance(address, Mapping):
            address = {}
        rows.append(
            {
                "game_id": str(event.get("id") or ""),
                "game_date_phoenix": game_day,
                "start_time_utc": str(raw_tip),
                "tip_phoenix": phoenix_tip,
                "status": _status_espn(
                    status_type.get("state"),
                    status_type.get("description") or status_type.get("detail"),
                ),
                "status_text": str(
                    status_type.get("shortDetail")
                    or status_type.get("detail")
                    or status_type.get("description")
                    or ""
                ),
                "home_team_id": int(home_team.get("id") or 0),
                "home_team": str(
                    home_team.get("displayName") or home_team.get("shortDisplayName") or home_abbr
                ),
                "home_abbr": home_abbr,
                "home_record": _espn_record(home_comp),
                "away_team_id": int(away_team.get("id") or 0),
                "away_team": str(
                    away_team.get("displayName") or away_team.get("shortDisplayName") or away_abbr
                ),
                "away_abbr": away_abbr,
                "away_record": _espn_record(away_comp),
                "arena": str(venue.get("fullName") or "").strip(),
                "city": str(address.get("city") or "").strip(),
                "source": "ESPN_NBA_SCOREBOARD",
            }
        )
    return rows


def _numeric(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def normalize_totals_odds(payload: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise NBADataSourceError("odds payload must be a list")
    rows: list[dict[str, Any]] = []
    for event in payload:
        if not isinstance(event, Mapping):
            continue
        if str(event.get("sport_key") or "") != ODDS_SPORT_KEY:
            continue
        raw_tip = event.get("commence_time")
        if not raw_tip:
            continue
        try:
            phoenix_tip = to_phoenix_time(raw_tip)
        except NBADataSourceError:
            continue
        for bookmaker in event.get("bookmakers") or []:
            if not isinstance(bookmaker, Mapping):
                continue
            for market in bookmaker.get("markets") or []:
                if not isinstance(market, Mapping) or market.get("key") != ODDS_MARKET:
                    continue
                outcomes = market.get("outcomes") or []
                over = next(
                    (item for item in outcomes if isinstance(item, Mapping) and item.get("name") == "Over"),
                    None,
                )
                under = next(
                    (item for item in outcomes if isinstance(item, Mapping) and item.get("name") == "Under"),
                    None,
                )
                if not over or not under:
                    continue
                over_point = _numeric(over.get("point"))
                under_point = _numeric(under.get("point"))
                if over_point is None or under_point is None or over_point != under_point:
                    continue
                over_price = _numeric(over.get("price"))
                under_price = _numeric(under.get("price"))
                if over_price is None or under_price is None:
                    continue
                rows.append(
                    {
                        "event_id": str(event.get("id") or ""),
                        "home_team": str(event.get("home_team") or ""),
                        "away_team": str(event.get("away_team") or ""),
                        "commence_time_utc": str(raw_tip),
                        "tip_phoenix": phoenix_tip,
                        "bookmaker_key": str(bookmaker.get("key") or ""),
                        "bookmaker": str(bookmaker.get("title") or ""),
                        "market_total": over_point,
                        "over_price": over_price,
                        "under_price": under_price,
                        "last_update": str(
                            market.get("last_update")
                            or bookmaker.get("last_update")
                            or event.get("last_update")
                            or ""
                        ),
                        "source": "THE_ODDS_API",
                    }
                )
    return rows


class NBADataClient:
    def __init__(self, transport: JSONTransport | None = None, *, timeout: int | float = 8):
        self.transport = transport or RequestsJSONTransport()
        self.timeout = timeout

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}

    def schedule_for_date(self, selected_date: str | date | datetime) -> list[dict[str, Any]]:
        day = _day_text(selected_date)
        try:
            official = self.transport.get_json(
                NBA_OFFICIAL_SCHEDULE_URL,
                headers=self._headers(),
                timeout=self.timeout,
            )
            # A valid official feed with no selected-day games is a real off-day.
            return normalize_official_schedule(official, day)
        except Exception as primary_error:
            try:
                fallback = self.transport.get_json(
                    ESPN_SCOREBOARD_URL,
                    params={"dates": day.replace("-", ""), "limit": 100},
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                return normalize_espn_schedule(fallback, day)
            except Exception as fallback_error:
                raise NBADataSourceError(
                    f"NBA schedule unavailable from primary and fallback sources: {primary_error}"
                ) from fallback_error

    def totals_odds(self, api_key: str) -> list[dict[str, Any]]:
        key = str(api_key or "").strip()
        if not key:
            raise NBADataSourceError("The Odds API key is required")
        try:
            payload = self.transport.get_json(
                THE_ODDS_API_URL,
                params={
                    "apiKey": key,
                    "regions": "us",
                    "markets": ODDS_MARKET,
                    "oddsFormat": "american",
                    "dateFormat": "iso",
                },
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
            return normalize_totals_odds(payload)
        except NBADataSourceError:
            raise
        except Exception as exc:
            raise NBADataSourceError(f"NBA totals odds unavailable: {exc}") from exc


__all__ = [
    "MODEL_VERSION",
    "SPORT",
    "PAGE_SCOPE",
    "PHOENIX_TIMEZONE",
    "NBA_OFFICIAL_SCHEDULE_URL",
    "ESPN_SCOREBOARD_URL",
    "THE_ODDS_API_URL",
    "ODDS_SPORT_KEY",
    "ODDS_MARKET",
    "NBA_TEAM_ABBREVIATIONS",
    "NBADataSourceError",
    "JSONTransport",
    "RequestsJSONTransport",
    "source_contract",
    "to_phoenix_time",
    "normalize_official_schedule",
    "normalize_espn_schedule",
    "normalize_totals_odds",
    "NBADataClient",
]
