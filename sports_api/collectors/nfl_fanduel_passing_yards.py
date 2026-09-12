"""Read-only FanDuel NFL Passing Yards collector for Kyre Sports API.

This module is deliberately market/context-only. It resolves one official ESPN
NFL event, locates the same FanDuel event by exact team identity + kickoff, then
normalizes only open pregame two-way Passing Yards props. Player identity is
resolved without player-name matching: FanDuel selection -> FDX player -> exact
team/jersey/QB roster row -> official ESPN athlete ID.

Guardrails:
- official ESPN event and athlete IDs only;
- no fuzzy team/player matching;
- no synthetic game/player IDs;
- no fabricated line or price;
- no wagering actions;
- sportsbook projection influence = 0.0%.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import re
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FANDUEL_BASE_URL = "https://api.sportsbook.fanduel.com"
FANDUEL_FDX_BASE_URL = "https://fdx-api.sportsbook.fanduel.com/api"
FANDUEL_PUBLIC_WEB_KEY = "FhMFpcPWXMeyZxOx"
FANDUEL_REGION = "NJ"
FANDUEL_NFL_PAGE_ID = "nfl"
ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

DEFAULT_TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 20_000_000
MAX_KICKOFF_DELTA_SECONDS = 3 * 60 * 60

FANDUEL_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-NFL/1.0; read-only)",
    "Origin": "https://sportsbook.fanduel.com",
    "Referer": "https://sportsbook.fanduel.com/",
    "x-sportsbook-region": FANDUEL_REGION,
}
ESPN_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-NFL/1.0; read-only)",
}

# Deterministic provider display-name -> official ESPN team identity. These are
# exact aliases, not fuzzy matching. Unknown names fail closed.
TEAM_BY_FANDUEL_NAME: dict[str, tuple[str, str]] = {
    "Arizona Cardinals": ("ARI", "22"),
    "Atlanta Falcons": ("ATL", "1"),
    "Baltimore Ravens": ("BAL", "33"),
    "Buffalo Bills": ("BUF", "2"),
    "Carolina Panthers": ("CAR", "29"),
    "Chicago Bears": ("CHI", "3"),
    "Cincinnati Bengals": ("CIN", "4"),
    "Cleveland Browns": ("CLE", "5"),
    "Dallas Cowboys": ("DAL", "6"),
    "Denver Broncos": ("DEN", "7"),
    "Detroit Lions": ("DET", "8"),
    "Green Bay Packers": ("GB", "9"),
    "Houston Texans": ("HOU", "34"),
    "Indianapolis Colts": ("IND", "11"),
    "Jacksonville Jaguars": ("JAX", "30"),
    "Kansas City Chiefs": ("KC", "12"),
    "Las Vegas Raiders": ("LV", "13"),
    "Los Angeles Chargers": ("LAC", "24"),
    "Los Angeles Rams": ("LAR", "14"),
    "Miami Dolphins": ("MIA", "15"),
    "Minnesota Vikings": ("MIN", "16"),
    "New England Patriots": ("NE", "17"),
    "New Orleans Saints": ("NO", "18"),
    "New York Giants": ("NYG", "19"),
    "New York Jets": ("NYJ", "20"),
    "Philadelphia Eagles": ("PHI", "21"),
    "Pittsburgh Steelers": ("PIT", "23"),
    "San Francisco 49ers": ("SF", "25"),
    "Seattle Seahawks": ("SEA", "26"),
    "Tampa Bay Buccaneers": ("TB", "27"),
    "Tennessee Titans": ("TEN", "10"),
    "Washington Commanders": ("WSH", "28"),
}

# FanDuel FDX abbreviations observed across sports can differ from ESPN's app
# abbreviations for Jacksonville/Washington. Only explicit aliases are allowed.
TEAM_ID_BY_PROVIDER_ABBR: dict[str, str] = {
    "ARI": "22", "ATL": "1", "BAL": "33", "BUF": "2", "CAR": "29",
    "CHI": "3", "CIN": "4", "CLE": "5", "DAL": "6", "DEN": "7",
    "DET": "8", "GB": "9", "HOU": "34", "IND": "11", "JAC": "30",
    "JAX": "30", "KC": "12", "LV": "13", "LAC": "24", "LAR": "14",
    "MIA": "15", "MIN": "16", "NE": "17", "NO": "18", "NYG": "19",
    "NYJ": "20", "PHI": "21", "PIT": "23", "SF": "25", "SEA": "26",
    "TB": "27", "TEN": "10", "WAS": "28", "WSH": "28",
}

KNOWN_PROP_TABS = (
    "passing-props",
    "player-passing-props",
    "player-props",
    "passing",
    "popular",
)


class NFLPassingYardsCollectorError(RuntimeError):
    """Raised when the live NFL Passing Yards market cannot be proven safely."""


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        out: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("_attachment_key", str(key))
                out.append(row)
        return out
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _get_json(
    url: str,
    params: Mapping[str, Any] | None = None,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    query = urlencode({str(k): str(v) for k, v in (params or {}).items()})
    target = f"{url}?{query}" if query else url
    request = Request(target, headers=dict(headers or {}), method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 0) or 0)
            if status != 200:
                raise NFLPassingYardsCollectorError(f"GET returned HTTP {status}")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except NFLPassingYardsCollectorError:
        raise
    except Exception as exc:
        raise NFLPassingYardsCollectorError(
            f"read-only upstream GET failed: {type(exc).__name__}"
        ) from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise NFLPassingYardsCollectorError("upstream response exceeded safe size limit")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NFLPassingYardsCollectorError("upstream response was not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise NFLPassingYardsCollectorError("upstream response was not a JSON object")
    return payload


def _aware_utc(value: Any, field: str) -> datetime:
    text = _text(value).replace("Z", "+00:00")
    if not text:
        raise NFLPassingYardsCollectorError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise NFLPassingYardsCollectorError(f"{field} is not valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NFLPassingYardsCollectorError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def fetch_espn_event_summary(event_id: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    event_id = _text(event_id)
    if not event_id.isdigit():
        raise NFLPassingYardsCollectorError("official ESPN event_id must be numeric")
    return _get_json(
        f"{ESPN_SITE_BASE}/summary",
        {"event": event_id},
        headers=ESPN_HEADERS,
        timeout=timeout,
    )


def parse_official_event(summary: Mapping[str, Any]) -> dict[str, Any]:
    header = summary.get("header") if isinstance(summary, Mapping) else {}
    competitions = (header or {}).get("competitions") or []
    competition = competitions[0] if competitions and isinstance(competitions[0], Mapping) else {}
    event_id = _text((header or {}).get("id") or competition.get("id"))
    if not event_id.isdigit():
        raise NFLPassingYardsCollectorError("ESPN summary is missing an official numeric event ID")

    status = (competition.get("status") or {}).get("type") or {}
    state = _text(status.get("state")).lower()
    completed = bool(status.get("completed"))
    if completed or state in {"in", "post"}:
        raise NFLPassingYardsCollectorError("official NFL event is not pregame")

    competitors = competition.get("competitors") or []
    sides: dict[str, dict[str, str]] = {}
    for row in competitors:
        if not isinstance(row, Mapping):
            continue
        side = _text(row.get("homeAway")).lower()
        team = row.get("team") or {}
        team_id = _text(team.get("id"))
        if side in {"home", "away"} and team_id.isdigit():
            sides[side] = {
                "team_id": team_id,
                "abbr": _text(team.get("abbreviation")).upper(),
                "name": _text(team.get("displayName") or team.get("name")),
            }
    if set(sides) != {"home", "away"}:
        raise NFLPassingYardsCollectorError("ESPN summary is missing exact home/away team identities")

    kickoff = _aware_utc(competition.get("date") or (header or {}).get("date"), "ESPN kickoff")
    return {
        "event_id": event_id,
        "kickoff_utc": kickoff,
        "home": sides["home"],
        "away": sides["away"],
    }


def fetch_fanduel_nfl_landing(*, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    return _get_json(
        f"{FANDUEL_BASE_URL}/sbapi/content-managed-page",
        {
            "_ak": FANDUEL_PUBLIC_WEB_KEY,
            "page": "CUSTOM",
            "customPageId": FANDUEL_NFL_PAGE_ID,
            "timezone": "America/New_York",
        },
        headers=FANDUEL_HEADERS,
        timeout=timeout,
    )


def _fanduel_event_identity(event: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _text(event.get("eventId") or event.get("id") or event.get("_attachment_key"))
    name = _text(event.get("name") or event.get("eventName") or event.get("displayName"))
    parts = [part.strip() for part in name.split(" @ ")]
    if len(parts) != 2:
        raise NFLPassingYardsCollectorError("FanDuel event is not an exact two-team '@' matchup")
    away = TEAM_BY_FANDUEL_NAME.get(parts[0])
    home = TEAM_BY_FANDUEL_NAME.get(parts[1])
    if not event_id or away is None or home is None:
        raise NFLPassingYardsCollectorError("FanDuel event contains an unsupported exact team identity")
    kickoff = _aware_utc(event.get("openDate"), "FanDuel event openDate")
    return {
        "provider_event_id": event_id,
        "kickoff_utc": kickoff,
        "away_team_id": away[1],
        "home_team_id": home[1],
        "away_abbr": away[0],
        "home_abbr": home[0],
        "provider_event_name": name,
    }


def reconcile_fanduel_event(
    landing: Mapping[str, Any],
    official_event: Mapping[str, Any],
) -> dict[str, Any]:
    attachments = landing.get("attachments") if isinstance(landing, Mapping) else {}
    if not isinstance(attachments, Mapping):
        raise NFLPassingYardsCollectorError("FanDuel NFL landing page has no attachments object")
    matches: list[dict[str, Any]] = []
    for event in _rows(attachments.get("events")):
        try:
            candidate = _fanduel_event_identity(event)
        except NFLPassingYardsCollectorError:
            continue
        if candidate["away_team_id"] != _text((official_event.get("away") or {}).get("team_id")):
            continue
        if candidate["home_team_id"] != _text((official_event.get("home") or {}).get("team_id")):
            continue
        delta = abs((candidate["kickoff_utc"] - official_event["kickoff_utc"]).total_seconds())
        if delta <= MAX_KICKOFF_DELTA_SECONDS:
            candidate["kickoff_delta_seconds"] = int(delta)
            matches.append(candidate)
    if len(matches) != 1:
        raise NFLPassingYardsCollectorError(
            f"exact FanDuel/ESPN event reconciliation expected 1 match, found {len(matches)}"
        )
    return matches[0]


def fetch_fanduel_event_page(
    provider_event_id: str,
    tab: str | None = None,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "_ak": FANDUEL_PUBLIC_WEB_KEY,
        "eventId": _text(provider_event_id),
    }
    if tab:
        params["tab"] = tab
    return _get_json(
        f"{FANDUEL_BASE_URL}/sbapi/event-page",
        params,
        headers=FANDUEL_HEADERS,
        timeout=timeout,
    )


def fetch_fanduel_event_players(
    provider_event_id: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return _get_json(
        f"{FANDUEL_FDX_BASE_URL}/v1/live/event/{_text(provider_event_id)}/players",
        headers=FANDUEL_HEADERS,
        timeout=timeout,
    )


def fetch_espn_team_roster(team_id: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    team_id = _text(team_id)
    if not team_id.isdigit():
        raise NFLPassingYardsCollectorError("official ESPN team ID must be numeric")
    return _get_json(
        f"{ESPN_SITE_BASE}/teams/{team_id}/roster",
        headers=ESPN_HEADERS,
        timeout=timeout,
    )


def parse_espn_qb_roster(payload: Mapping[str, Any], team_id: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for group in (payload or {}).get("athletes") or []:
        if not isinstance(group, Mapping):
            continue
        for item in group.get("items") or []:
            if not isinstance(item, Mapping):
                continue
            pos = item.get("position") or {}
            position = _text(pos.get("abbreviation") or pos.get("name")).upper()
            if position != "QB" and "QUARTERBACK" not in position:
                continue
            athlete_id = _text(item.get("id"))
            jersey = _text(item.get("jersey") or item.get("jerseyNumber"))
            if athlete_id.isdigit() and jersey:
                out.append({
                    "team_id": _text(team_id),
                    "athlete_id": athlete_id,
                    "jersey": jersey,
                    "position": "QB",
                    "display_name": _text(item.get("displayName") or item.get("fullName")),
                })
    return out


def _provider_player_maps(payload: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    raw = payload.get("playerMap") if isinstance(payload, Mapping) else None
    if not isinstance(raw, Mapping):
        raise NFLPassingYardsCollectorError("FanDuel FDX playerMap is missing")
    players: dict[str, dict[str, Any]] = {}
    by_selection: dict[str, list[str]] = {}
    for provider_key, value in raw.items():
        if not isinstance(value, Mapping):
            continue
        key = _text(provider_key)
        if not key:
            continue
        row = dict(value)
        players[key] = row
        for selection in row.get("selectionIds") or []:
            selection_id = _text(selection)
            if selection_id:
                by_selection.setdefault(selection_id, []).append(key)
    return players, by_selection


def _provider_team_id(player: Mapping[str, Any]) -> str:
    return TEAM_ID_BY_PROVIDER_ABBR.get(_text(player.get("team")).upper(), "")


def reconcile_provider_qb(
    player: Mapping[str, Any],
    rosters_by_team: Mapping[str, list[dict[str, str]]],
) -> dict[str, str]:
    team_id = _provider_team_id(player)
    jersey = _text(player.get("number") or player.get("jersey") or player.get("jerseyNumber"))
    position = _text(player.get("position")).upper()
    if not team_id or not jersey or position != "QB":
        raise NFLPassingYardsCollectorError("FanDuel player lacks exact team/jersey/QB identity")
    matches = [
        row for row in rosters_by_team.get(team_id, [])
        if _text(row.get("jersey")) == jersey and _text(row.get("position")).upper() == "QB"
    ]
    unique = {row["athlete_id"]: row for row in matches if _text(row.get("athlete_id")).isdigit()}
    if len(unique) != 1:
        raise NFLPassingYardsCollectorError(
            f"FanDuel QB identity did not resolve to exactly one ESPN athlete ({len(unique)})"
        )
    return next(iter(unique.values()))


def _market_text(market: Mapping[str, Any]) -> str:
    return " ".join(
        _text(market.get(field))
        for field in ("marketType", "marketTypeCode", "type", "marketName", "name", "displayName")
        if _text(market.get(field))
    )


def is_passing_yards_market(market: Mapping[str, Any]) -> bool:
    text = _market_text(market).lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", text)
    if "alternate" in normalized or "alternative" in normalized:
        return False
    return "passing" in normalized and "yard" in normalized


def _market_is_open_pregame(market: Mapping[str, Any]) -> bool:
    status = _text(market.get("marketStatus") or market.get("status")).upper()
    return status == "OPEN" and market.get("inPlay") is not True


def _active_player_runners(market: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        runner for runner in _rows(market.get("runners"))
        if _text(runner.get("runnerStatus")).upper() in {"", "ACTIVE"}
    ]


def _runner_role(runner: Mapping[str, Any]) -> str:
    result = runner.get("result") or {}
    return _text(result.get("type")).upper() if isinstance(result, Mapping) else ""


def _line(runner: Mapping[str, Any]) -> float:
    try:
        value = float(runner.get("handicap"))
    except (TypeError, ValueError) as exc:
        raise NFLPassingYardsCollectorError("Passing Yards runner has invalid line") from exc
    if not math.isfinite(value) or value <= 0 or value > 700:
        raise NFLPassingYardsCollectorError("Passing Yards line is outside safe NFL range")
    return value


def _american_odds(runner: Mapping[str, Any]) -> int:
    win = runner.get("winRunnerOdds") or {}
    display = win.get("americanDisplayOdds") or {} if isinstance(win, Mapping) else {}
    raw = display.get("americanOddsInt") if isinstance(display, Mapping) else None
    if raw is None and isinstance(display, Mapping):
        raw = display.get("americanOdds")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise NFLPassingYardsCollectorError("Passing Yards runner has invalid American odds") from exc
    if not math.isfinite(value) or value == 0 or not value.is_integer() or abs(value) < 100:
        raise NFLPassingYardsCollectorError("Passing Yards American odds are invalid")
    return int(value)


def _selection_id(runner: Mapping[str, Any]) -> str:
    return _text(runner.get("selectionId"))


def _provider_player_for_market(
    over: Mapping[str, Any],
    under: Mapping[str, Any],
    players: Mapping[str, dict[str, Any]],
    by_selection: Mapping[str, list[str]],
) -> tuple[str, dict[str, Any]]:
    keys: list[str] = []
    for runner in (over, under):
        selection = _selection_id(runner)
        mapped = by_selection.get(selection) or []
        if len(mapped) != 1:
            raise NFLPassingYardsCollectorError("runner selection does not map to one FanDuel player")
        keys.append(mapped[0])
    if keys[0] != keys[1]:
        raise NFLPassingYardsCollectorError("Over and Under map to different FanDuel players")
    player = players.get(keys[0])
    if not isinstance(player, Mapping):
        raise NFLPassingYardsCollectorError("FanDuel player identity is missing")
    return keys[0], dict(player)


def normalize_passing_yards_market(
    market: Mapping[str, Any],
    *,
    official_event_id: str,
    provider_event_id: str,
    players: Mapping[str, dict[str, Any]],
    by_selection: Mapping[str, list[str]],
    rosters_by_team: Mapping[str, list[dict[str, str]]],
    captured_at_utc: datetime,
) -> dict[str, Any] | None:
    if not is_passing_yards_market(market) or not _market_is_open_pregame(market):
        return None
    active = _active_player_runners(market)
    overs = [row for row in active if _runner_role(row) == "OVER"]
    unders = [row for row in active if _runner_role(row) == "UNDER"]
    if len(overs) != 1 or len(unders) != 1:
        raise NFLPassingYardsCollectorError("Passing Yards market must have exactly one active OVER and UNDER")
    over, under = overs[0], unders[0]
    over_line, under_line = _line(over), _line(under)
    if over_line != under_line:
        raise NFLPassingYardsCollectorError("Passing Yards OVER/UNDER lines do not match")
    provider_player_key, provider_player = _provider_player_for_market(over, under, players, by_selection)
    official_player = reconcile_provider_qb(provider_player, rosters_by_team)
    return {
        "official_event_id": _text(official_event_id),
        "official_athlete_id": official_player["athlete_id"],
        "official_team_id": official_player["team_id"],
        "player_name": official_player.get("display_name") or "Verified QB",
        "position": "QB",
        "market_type": "passing_yards",
        "line": over_line,
        "over_odds": _american_odds(over),
        "under_odds": _american_odds(under),
        "sportsbook": "FanDuel",
        "line_status": "active",
        "provider_event_id": _text(provider_event_id),
        "provider_market_id": _text(market.get("marketId") or market.get("id") or market.get("_attachment_key")),
        "provider_player_key": provider_player_key,
        "captured_at_utc": _utc_iso(captured_at_utc),
    }


def _passing_markets(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
    if not isinstance(attachments, Mapping):
        return []
    return [row for row in _rows(attachments.get("markets")) if is_passing_yards_market(row)]


def discover_passing_tab_candidates(payload: Mapping[str, Any]) -> list[str]:
    """Find provider-declared passing tab slugs without depending on player names."""
    found: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = _text(value)
        if not text or len(text) > 80 or not re.fullmatch(r"[A-Za-z0-9_-]+", text):
            return
        low = text.lower()
        if "pass" not in low or ("prop" not in low and "yard" not in low):
            return
        if low not in seen:
            seen.add(low)
            found.append(text)

    def walk(value: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(value, Mapping):
            for key, child in value.items():
                if _text(key).lower() in {"tab", "tabid", "slug", "key", "id"}:
                    add(child)
                walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:200]:
                walk(child, depth + 1)

    walk(payload)
    for tab in KNOWN_PROP_TABS:
        if tab.lower() not in seen:
            found.append(tab)
            seen.add(tab.lower())
    return found[:8]


def collect_fanduel_nfl_passing_yards(
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now.astimezone(timezone.utc)

    summary = fetch_espn_event_summary(official_event_id, timeout=timeout)
    official = parse_official_event(summary)
    landing = fetch_fanduel_nfl_landing(timeout=timeout)
    provider_event = reconcile_fanduel_event(landing, official)

    base_page = fetch_fanduel_event_page(provider_event["provider_event_id"], timeout=timeout)
    selected_payload = base_page
    selected_tab = "default"
    markets = _passing_markets(base_page)
    attempted_tabs: list[str] = ["default"]
    if not markets:
        for tab in discover_passing_tab_candidates(base_page):
            attempted_tabs.append(tab)
            try:
                candidate = fetch_fanduel_event_page(provider_event["provider_event_id"], tab, timeout=timeout)
            except NFLPassingYardsCollectorError:
                continue
            candidate_markets = _passing_markets(candidate)
            if candidate_markets:
                selected_payload = candidate
                selected_tab = tab
                markets = candidate_markets
                break

    if not markets:
        return {
            "schema_version": "nfl_passing_yards_market_v1",
            "ready": True,
            "market_available": False,
            "official_event_id": official["event_id"],
            "sportsbook": "FanDuel",
            "captured_at_utc": _utc_iso(now),
            "props": [],
            "reason": "FanDuel returned no open canonical Passing Yards market for this exact event",
            "provider_diagnostics": {
                "provider_event_id": provider_event["provider_event_id"],
                "selected_tab": selected_tab,
                "attempted_tabs": attempted_tabs,
            },
            "identity": {
                "official_authority": "ESPN",
                "event_identity": "exact ESPN event ID + exact team IDs + bounded kickoff equality",
                "player_identity": "FanDuel selection -> FDX player -> exact team/jersey/QB ESPN roster row",
                "player_name_matching": False,
                "fuzzy_matching": False,
                "synthetic_event_ids": False,
                "synthetic_player_ids": False,
            },
            "market_semantics": {
                "projection_weight": 0.0,
                "market_context_only": True,
                "may_modify_projection": False,
                "stake_sizing_enabled": False,
            },
        }

    fdx_players = fetch_fanduel_event_players(provider_event["provider_event_id"], timeout=timeout)
    players, by_selection = _provider_player_maps(fdx_players)

    rosters_by_team: dict[str, list[dict[str, str]]] = {}
    for side in ("away", "home"):
        team_id = official[side]["team_id"]
        roster_payload = fetch_espn_team_roster(team_id, timeout=timeout)
        rosters_by_team[team_id] = parse_espn_qb_roster(roster_payload, team_id)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for market in markets:
        market_id = _text(market.get("marketId") or market.get("id") or market.get("_attachment_key"))
        try:
            row = normalize_passing_yards_market(
                market,
                official_event_id=official["event_id"],
                provider_event_id=provider_event["provider_event_id"],
                players=players,
                by_selection=by_selection,
                rosters_by_team=rosters_by_team,
                captured_at_utc=now,
            )
            if row:
                accepted.append(row)
        except Exception as exc:
            rejected.append({"provider_market_id": market_id, "reason": f"{type(exc).__name__}: {exc}"[:300]})

    # Multiple canonical lines for one official player are ambiguous and are
    # withheld rather than choosing an arbitrary provider row.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in accepted:
        grouped.setdefault(row["official_athlete_id"], []).append(row)
    final_props: list[dict[str, Any]] = []
    for athlete_id, rows in grouped.items():
        signatures = {(row["line"], row["over_odds"], row["under_odds"]) for row in rows}
        if len(signatures) != 1:
            rejected.append({
                "provider_market_id": ",".join(_text(row.get("provider_market_id")) for row in rows),
                "reason": f"ambiguous multiple canonical Passing Yards prices for ESPN athlete {athlete_id}",
            })
            continue
        final_props.append(rows[0])

    final_props.sort(key=lambda row: (row["official_team_id"], row["official_athlete_id"]))
    return {
        "schema_version": "nfl_passing_yards_market_v1",
        "ready": True,
        "market_available": bool(final_props),
        "official_event_id": official["event_id"],
        "sportsbook": "FanDuel",
        "captured_at_utc": _utc_iso(now),
        "props": final_props,
        "reason": "" if final_props else "Passing Yards markets were present but exact player/price certification failed closed",
        "provider_diagnostics": {
            "provider_event_id": provider_event["provider_event_id"],
            "provider_event_name": provider_event["provider_event_name"],
            "kickoff_delta_seconds": provider_event["kickoff_delta_seconds"],
            "selected_tab": selected_tab,
            "attempted_tabs": attempted_tabs,
            "passing_market_count": len(markets),
            "accepted_prop_count": len(final_props),
            "rejected_market_count": len(rejected),
            "rejected_markets": rejected,
            "http_methods": ["GET"],
            "sportsbook_credentials_required": False,
            "wager_actions": False,
        },
        "identity": {
            "official_authority": "ESPN",
            "event_identity": "exact ESPN event ID + exact team IDs + bounded kickoff equality",
            "player_identity": "FanDuel selection -> FDX player -> exact team/jersey/QB ESPN roster row",
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "stake_sizing_enabled": False,
        },
    }


__all__ = [
    "NFLPassingYardsCollectorError",
    "TEAM_BY_FANDUEL_NAME",
    "TEAM_ID_BY_PROVIDER_ABBR",
    "collect_fanduel_nfl_passing_yards",
    "discover_passing_tab_candidates",
    "fetch_espn_event_summary",
    "fetch_espn_team_roster",
    "fetch_fanduel_event_page",
    "fetch_fanduel_event_players",
    "fetch_fanduel_nfl_landing",
    "is_passing_yards_market",
    "normalize_passing_yards_market",
    "parse_espn_qb_roster",
    "parse_official_event",
    "reconcile_fanduel_event",
    "reconcile_provider_qb",
]
