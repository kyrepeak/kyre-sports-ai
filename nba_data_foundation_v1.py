"""NBA Over/Under Step 2 — NBA-only data and hosted API client foundation."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, Protocol, Sequence
from zoneinfo import ZoneInfo

MODEL_VERSION = "NBA_OVER_UNDER_STEP2_DATA_FOUNDATION_V1"
SPORT = "NBA"
PAGE_SCOPE = "NBA_OVER_UNDER"
PHOENIX_TIMEZONE = "America/Phoenix"
PHOENIX_TZ = ZoneInfo(PHOENIX_TIMEZONE)

KYRE_SPORTS_API_BASE_URL = "https://kyre-sports-api.onrender.com"
KYRE_NBA_SLATE_PATH = "/api/v1/nba/over-under/slate"
KYRE_NBA_SLATE_URL = KYRE_SPORTS_API_BASE_URL + KYRE_NBA_SLATE_PATH
NBA_OFFICIAL_SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
THE_ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
ODDS_SPORT_KEY = "basketball_nba"
ODDS_MARKET = "totals"

MAY_RENDER_UI = False
MAY_ACTIVATE_ROUTER = False
MAY_MODIFY_SHARED_APIS = False
MAY_MODIFY_OTHER_SPORTS = False
MODEL_PROJECTION_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

NBA_TEAM_ABBREVIATIONS = frozenset({
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
})


class NBADataSourceError(RuntimeError):
    pass


class JSONTransport(Protocol):
    def get_json(self, url: str, *, params: Mapping[str, Any] | None = None,
                 headers: Mapping[str, str] | None = None,
                 timeout: int | float = 8) -> Any: ...


class RequestsJSONTransport:
    def get_json(self, url: str, *, params: Mapping[str, Any] | None = None,
                 headers: Mapping[str, str] | None = None,
                 timeout: int | float = 8) -> Any:
        import requests
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, (dict, list)):
            raise NBADataSourceError(f"non-JSON object/list response from {url}")
        return body


def source_contract() -> dict[str, Any]:
    return {
        "version": MODEL_VERSION,
        "sport": SPORT,
        "page_scope": PAGE_SCOPE,
        "page_transport_primary": "KYRE_SPORTS_API",
        "kyre_api_base_url": KYRE_SPORTS_API_BASE_URL,
        "kyre_nba_slate_path": KYRE_NBA_SLATE_PATH,
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
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise NBADataSourceError(f"invalid selected date: {value!r}") from exc


def to_phoenix_time(value: Any) -> str:
    return _parse_datetime(value).astimezone(PHOENIX_TZ).isoformat(timespec="seconds")


def _phoenix_date(value: Any) -> str:
    return _parse_datetime(value).astimezone(PHOENIX_TZ).date().isoformat()


def _is_nba_pair(home: Any, away: Any) -> bool:
    h, a = str(home or "").upper(), str(away or "").upper()
    return h in NBA_TEAM_ABBREVIATIONS and a in NBA_TEAM_ABBREVIATIONS and h != a


def _official_status(game: Mapping[str, Any]) -> str:
    try:
        code = int(game.get("gameStatus") or 0)
    except (TypeError, ValueError):
        code = 0
    text = str(game.get("gameStatusText") or "").lower()
    if code == 3 or "final" in text:
        return "FINAL"
    if code == 2:
        return "LIVE"
    return "UPCOMING"


def normalize_official_schedule(payload: Mapping[str, Any], selected_date: str | date | datetime) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise NBADataSourceError("official schedule payload must be an object")
    league = payload.get("leagueSchedule")
    if not isinstance(league, Mapping) or not isinstance(league.get("gameDates"), list):
        raise NBADataSourceError("official schedule missing gameDates")
    target = _day_text(selected_date)
    rows: list[dict[str, Any]] = []
    for block in league["gameDates"]:
        if not isinstance(block, Mapping):
            continue
        for game in block.get("games") or []:
            if not isinstance(game, Mapping):
                continue
            home, away = game.get("homeTeam") or {}, game.get("awayTeam") or {}
            if not isinstance(home, Mapping) or not isinstance(away, Mapping):
                continue
            home_abbr = str(home.get("teamTricode") or "").upper()
            away_abbr = str(away.get("teamTricode") or "").upper()
            raw_tip = game.get("gameDateTimeUTC")
            if not raw_tip or not _is_nba_pair(home_abbr, away_abbr):
                continue
            if _phoenix_date(raw_tip) != target:
                continue
            home_name = " ".join(x for x in (str(home.get("teamCity") or "").strip(), str(home.get("teamName") or home_abbr).strip()) if x)
            away_name = " ".join(x for x in (str(away.get("teamCity") or "").strip(), str(away.get("teamName") or away_abbr).strip()) if x)
            rows.append({
                "game_id": str(game.get("gameId") or ""),
                "game_date_phoenix": target,
                "start_time_utc": str(raw_tip),
                "tip_phoenix": to_phoenix_time(raw_tip),
                "status": _official_status(game),
                "status_text": str(game.get("gameStatusText") or ""),
                "home_team_id": int(home.get("teamId") or 0),
                "home_team": home_name,
                "home_abbr": home_abbr,
                "home_record": f"{home.get('wins')}-{home.get('losses')}" if home.get("wins") is not None and home.get("losses") is not None else "",
                "away_team_id": int(away.get("teamId") or 0),
                "away_team": away_name,
                "away_abbr": away_abbr,
                "away_record": f"{away.get('wins')}-{away.get('losses')}" if away.get("wins") is not None and away.get("losses") is not None else "",
                "arena": str(game.get("arenaName") or "").strip(),
                "city": str(game.get("arenaCity") or "").strip(),
                "source": "NBA_OFFICIAL_CDN",
            })
    return rows


def _espn_record(side: Mapping[str, Any]) -> str:
    records = side.get("records") or []
    if not isinstance(records, list):
        return ""
    record = next((r for r in records if isinstance(r, Mapping) and r.get("type") == "total"), None)
    record = record or next((r for r in records if isinstance(r, Mapping)), {})
    return str(record.get("summary") or "")


def normalize_espn_schedule(payload: Mapping[str, Any], selected_date: str | date | datetime) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("events"), list):
        raise NBADataSourceError("ESPN schedule missing events")
    target = _day_text(selected_date)
    rows: list[dict[str, Any]] = []
    for event in payload["events"]:
        if not isinstance(event, Mapping):
            continue
        comps = event.get("competitions") or []
        if not comps or not isinstance(comps[0], Mapping):
            continue
        comp = comps[0]
        sides = {str(x.get("homeAway") or "").lower(): x for x in comp.get("competitors") or [] if isinstance(x, Mapping)}
        home_side, away_side = sides.get("home") or {}, sides.get("away") or {}
        home, away = home_side.get("team") or {}, away_side.get("team") or {}
        if not isinstance(home, Mapping) or not isinstance(away, Mapping):
            continue
        h, a = str(home.get("abbreviation") or "").upper(), str(away.get("abbreviation") or "").upper()
        raw_tip = event.get("date") or comp.get("date")
        if not raw_tip or not _is_nba_pair(h, a) or _phoenix_date(raw_tip) != target:
            continue
        status = ((event.get("status") or {}).get("type") or {})
        state = str(status.get("state") or "").lower()
        normalized_status = "FINAL" if state in {"post", "final"} else "LIVE" if state in {"in", "live"} else "UPCOMING"
        venue = comp.get("venue") or {}
        address = venue.get("address") or {} if isinstance(venue, Mapping) else {}
        rows.append({
            "game_id": str(event.get("id") or ""),
            "game_date_phoenix": target,
            "start_time_utc": str(raw_tip),
            "tip_phoenix": to_phoenix_time(raw_tip),
            "status": normalized_status,
            "status_text": str(status.get("shortDetail") or status.get("detail") or status.get("description") or ""),
            "home_team_id": int(home.get("id") or 0),
            "home_team": str(home.get("displayName") or home.get("shortDisplayName") or h),
            "home_abbr": h,
            "home_record": _espn_record(home_side),
            "away_team_id": int(away.get("id") or 0),
            "away_team": str(away.get("displayName") or away.get("shortDisplayName") or a),
            "away_abbr": a,
            "away_record": _espn_record(away_side),
            "arena": str(venue.get("fullName") or "") if isinstance(venue, Mapping) else "",
            "city": str(address.get("city") or "") if isinstance(address, Mapping) else "",
            "source": "ESPN_NBA_SCOREBOARD",
        })
    return rows


def _number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
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
        if not isinstance(event, Mapping) or event.get("sport_key") != ODDS_SPORT_KEY:
            continue
        raw_tip = event.get("commence_time")
        if not raw_tip:
            continue
        for book in event.get("bookmakers") or []:
            if not isinstance(book, Mapping):
                continue
            for market in book.get("markets") or []:
                if not isinstance(market, Mapping) or market.get("key") != ODDS_MARKET:
                    continue
                outcomes = market.get("outcomes") or []
                over = next((o for o in outcomes if isinstance(o, Mapping) and o.get("name") == "Over"), None)
                under = next((o for o in outcomes if isinstance(o, Mapping) and o.get("name") == "Under"), None)
                if not over or not under:
                    continue
                point, under_point = _number(over.get("point")), _number(under.get("point"))
                over_price, under_price = _number(over.get("price")), _number(under.get("price"))
                if point is None or point != under_point or over_price is None or under_price is None:
                    continue
                rows.append({
                    "event_id": str(event.get("id") or ""),
                    "home_team": str(event.get("home_team") or ""),
                    "away_team": str(event.get("away_team") or ""),
                    "commence_time_utc": str(raw_tip),
                    "tip_phoenix": to_phoenix_time(raw_tip),
                    "bookmaker_key": str(book.get("key") or ""),
                    "bookmaker": str(book.get("title") or ""),
                    "market_total": point,
                    "over_price": over_price,
                    "under_price": under_price,
                    "last_update": str(market.get("last_update") or book.get("last_update") or event.get("last_update") or ""),
                    "source": "THE_ODDS_API",
                })
    return rows


def _validate_hosted_slate(payload: Any, day: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise NBADataSourceError("Kyre NBA slate must be an object")
    if payload.get("data_type") != "nba_over_under_step2_slate_v1" or payload.get("source") != "Kyre Sports API":
        raise NBADataSourceError("Kyre NBA slate identity is invalid")
    if payload.get("date") != day or payload.get("timezone") != PHOENIX_TIMEZONE:
        raise NBADataSourceError("Kyre NBA slate date/timezone is invalid")
    if not isinstance(payload.get("games"), list) or not isinstance(payload.get("totals"), list):
        raise NBADataSourceError("Kyre NBA slate shape is invalid")
    return dict(payload)


class NBADataClient:
    def __init__(self, transport: JSONTransport | None = None, *, timeout: int | float = 8):
        self.transport = transport or RequestsJSONTransport()
        self.timeout = timeout

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"Accept": "application/json", "User-Agent": "kyre-sports-ai-nba-step2/1"}

    def schedule_for_date(self, selected_date: str | date | datetime) -> list[dict[str, Any]]:
        day = _day_text(selected_date)
        try:
            official = self.transport.get_json(NBA_OFFICIAL_SCHEDULE_URL, headers=self._headers(), timeout=self.timeout)
            return normalize_official_schedule(official, day)
        except Exception as primary_error:
            try:
                espn = self.transport.get_json(ESPN_SCOREBOARD_URL, params={"dates": day.replace("-", ""), "limit": 100}, headers=self._headers(), timeout=self.timeout)
                return normalize_espn_schedule(espn, day)
            except Exception as fallback_error:
                raise NBADataSourceError(f"NBA schedule unavailable: {primary_error}") from fallback_error

    def totals_odds(self, api_key: str) -> list[dict[str, Any]]:
        key = str(api_key or "").strip()
        if not key:
            raise NBADataSourceError("The Odds API key is required")
        payload = self.transport.get_json(THE_ODDS_API_URL, params={
            "apiKey": key, "regions": "us", "markets": "totals",
            "oddsFormat": "american", "dateFormat": "iso",
        }, headers={"Accept": "application/json"}, timeout=self.timeout)
        return normalize_totals_odds(payload)

    def slate_for_date(self, selected_date: str | date | datetime) -> dict[str, Any]:
        day = _day_text(selected_date)
        try:
            hosted = self.transport.get_json(KYRE_NBA_SLATE_URL, params={"date": day}, headers=self._headers(), timeout=self.timeout)
            return _validate_hosted_slate(hosted, day)
        except Exception as hosted_error:
            games = self.schedule_for_date(day)
            return {
                "data_type": "nba_over_under_step2_slate_v1",
                "source": "DIRECT_FALLBACK",
                "date": day,
                "timezone": PHOENIX_TIMEZONE,
                "games": games,
                "totals": [],
                "market_state": "DIRECT_FALLBACK_NO_SERVER_MARKET",
                "fallback_reason": type(hosted_error).__name__,
            }


__all__ = [
    "MODEL_VERSION", "SPORT", "PAGE_SCOPE", "PHOENIX_TIMEZONE",
    "KYRE_SPORTS_API_BASE_URL", "KYRE_NBA_SLATE_PATH", "KYRE_NBA_SLATE_URL",
    "NBA_OFFICIAL_SCHEDULE_URL", "ESPN_SCOREBOARD_URL", "THE_ODDS_API_URL",
    "ODDS_SPORT_KEY", "ODDS_MARKET", "NBA_TEAM_ABBREVIATIONS",
    "NBADataSourceError", "JSONTransport", "RequestsJSONTransport", "source_contract",
    "to_phoenix_time", "normalize_official_schedule", "normalize_espn_schedule",
    "normalize_totals_odds", "NBADataClient",
]
