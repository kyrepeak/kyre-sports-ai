"""NFL Prop Analytics V1 — Step 2 Schedule Truth Layer.

Page 1 only. This module discovers the upcoming Sunday NFL slate from
independent public schedule sources, reconciles the fields, and renders a
fail-closed schedule board. It intentionally does not own player props,
sportsbook odds, projections, or any Passing Yards behavior.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dt_time, timedelta, timezone
import html as html_lib
from io import StringIO
from html.parser import HTMLParser
import re
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 2 SCHEDULE TRUTH"
STEP = 2
PAGE = 1
SCHEDULE_ONLY = True
PLAYER_PROP_LOGIC = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PASSING_YARDS = False
MAY_MODIFY_EXISTING_NFL_MARKETS = False

NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_WEB_SCOREBOARD_URL = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_TEAM_SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/schedule"
ESPN_WEB_TEAM_SCHEDULE_URL = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/schedule"
NFL_SCHEDULE_URL = "https://www.nfl.com/schedules/{season}/by-week/reg-{week}"
NFL_SCHEDULE_RELEASE_URL = "https://www.nfl.com/nfl-schedule-release/"
CBS_SCHEDULE_URL = "https://www.cbssports.com/nfl/schedule/{season}/regular/{week}/"
FOOTBALLDB_SCHEDULE_URL = "https://www.footballdb.com/scores/schedule{season}.html"
PFR_SCHEDULE_URL = "https://www.pro-football-reference.com/years/{season}/games.htm"
PFN_SCHEDULE_URL = "https://www.profootballnetwork.com/nfl-hq/schedule?date={target}"

AZ = ZoneInfo("America/Phoenix")
ET = ZoneInfo("America/New_York")

TEAM_ALIASES = {
    "ARI": "ARI", "ARIZONA": "ARI", "CARDINALS": "ARI",
    "ATL": "ATL", "ATLANTA": "ATL", "FALCONS": "ATL",
    "BAL": "BAL", "BALTIMORE": "BAL", "RAVENS": "BAL",
    "BUF": "BUF", "BUFFALO": "BUF", "BILLS": "BUF",
    "CAR": "CAR", "CAROLINA": "CAR", "PANTHERS": "CAR",
    "CHI": "CHI", "CHICAGO": "CHI", "BEARS": "CHI",
    "CIN": "CIN", "CINCINNATI": "CIN", "BENGALS": "CIN",
    "CLE": "CLE", "CLEVELAND": "CLE", "BROWNS": "CLE",
    "DAL": "DAL", "DALLAS": "DAL", "COWBOYS": "DAL",
    "DEN": "DEN", "DENVER": "DEN", "BRONCOS": "DEN",
    "DET": "DET", "DETROIT": "DET", "LIONS": "DET",
    "GB": "GB", "GNB": "GB", "GREEN BAY": "GB", "PACKERS": "GB",
    "HOU": "HOU", "HOUSTON": "HOU", "TEXANS": "HOU",
    "IND": "IND", "INDIANAPOLIS": "IND", "COLTS": "IND",
    "JAX": "JAX", "JAC": "JAX", "JACKSONVILLE": "JAX", "JAGUARS": "JAX",
    "KC": "KC", "KAN": "KC", "KANSAS CITY": "KC", "CHIEFS": "KC",
    "LAC": "LAC", "LA CHARGERS": "LAC", "CHARGERS": "LAC",
    "LAR": "LAR", "LA": "LAR", "LA RAMS": "LAR", "RAMS": "LAR",
    "LV": "LV", "OAK": "LV", "LAS VEGAS": "LV", "RAIDERS": "LV",
    "MIA": "MIA", "MIAMI": "MIA", "DOLPHINS": "MIA",
    "MIN": "MIN", "MINNESOTA": "MIN", "VIKINGS": "MIN",
    "NE": "NE", "NWE": "NE", "NEW ENGLAND": "NE", "PATRIOTS": "NE",
    "NO": "NO", "NOR": "NO", "NEW ORLEANS": "NO", "SAINTS": "NO",
    "NYG": "NYG", "GIANTS": "NYG",
    "NYJ": "NYJ", "JETS": "NYJ",
    "PHI": "PHI", "PHILADELPHIA": "PHI", "EAGLES": "PHI",
    "PIT": "PIT", "PITTSBURGH": "PIT", "STEELERS": "PIT",
    "SEA": "SEA", "SEATTLE": "SEA", "SEAHAWKS": "SEA",
    "SF": "SF", "SFO": "SF", "SAN FRANCISCO": "SF", "49ERS": "SF",
    "TB": "TB", "TAM": "TB", "TAMPA BAY": "TB", "BUCCANEERS": "TB",
    "TEN": "TEN", "TENNESSEE": "TEN", "TITANS": "TEN",
    "WAS": "WAS", "WSH": "WAS", "WASHINGTON": "WAS", "COMMANDERS": "WAS",
}

TEAM_NAMES = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills",
    "CAR": "Panthers", "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs",
    "LAC": "Chargers", "LAR": "Rams", "LV": "Raiders", "MIA": "Dolphins",
    "MIN": "Vikings", "NE": "Patriots", "NO": "Saints", "NYG": "Giants",
    "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers", "SEA": "Seahawks",
    "SF": "49ers", "TB": "Buccaneers", "TEN": "Titans", "WAS": "Commanders",
}

CBS_TEAM_ALIASES = {
    "ARIZONA": "ARI", "ATLANTA": "ATL", "BALTIMORE": "BAL", "BUFFALO": "BUF",
    "CAROLINA": "CAR", "CHICAGO": "CHI", "CINCINNATI": "CIN", "CLEVELAND": "CLE",
    "DALLAS": "DAL", "DENVER": "DEN", "DETROIT": "DET", "GREEN BAY": "GB",
    "HOUSTON": "HOU", "INDIANAPOLIS": "IND", "JACKSONVILLE": "JAX", "KANSAS CITY": "KC",
    "L.A. CHARGERS": "LAC", "LA CHARGERS": "LAC", "L.A. RAMS": "LAR", "LA RAMS": "LAR",
    "LAS VEGAS": "LV", "MIAMI": "MIA", "MINNESOTA": "MIN", "NEW ENGLAND": "NE",
    "NEW ORLEANS": "NO", "N.Y. GIANTS": "NYG", "NY GIANTS": "NYG",
    "N.Y. JETS": "NYJ", "NY JETS": "NYJ", "PHILADELPHIA": "PHI",
    "PITTSBURGH": "PIT", "SAN FRANCISCO": "SF", "SEATTLE": "SEA",
    "TAMPA BAY": "TB", "TENNESSEE": "TEN", "WASHINGTON": "WAS",
}


ESPN_LOGO_CODES = {
    "WAS": "wsh",
}


def team_logo_url(team: Any) -> str:
    """Return the stable ESPN CDN logo URL for a canonical NFL abbreviation."""
    canonical = _canon_team(team)
    code = ESPN_LOGO_CODES.get(canonical, canonical.lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{code}.png"


SOURCE_PRIORITY = ("NFL", "CBS", "PFR", "PFN", "FOOTBALLDB", "NFLVERSE", "ESPN")
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "application/json,text/plain,*/*",
}

ESPN_TEAM_IDS = {
    "ATL": "1", "BUF": "2", "CHI": "3", "CIN": "4", "CLE": "5",
    "DAL": "6", "DEN": "7", "DET": "8", "GB": "9", "TEN": "10",
    "IND": "11", "KC": "12", "LV": "13", "LAR": "14", "MIA": "15",
    "MIN": "16", "NE": "17", "NO": "18", "NYG": "19", "NYJ": "20",
    "PHI": "21", "ARI": "22", "PIT": "23", "LAC": "24", "SF": "25",
    "SEA": "26", "TB": "27", "WAS": "28", "CAR": "29", "JAX": "30",
    "BAL": "33", "HOU": "34",
}


def _canon_team(value: Any) -> str:
    token = str(value or "").strip().upper()
    return TEAM_ALIASES.get(token, token)


def _target_sunday(today: date | None = None) -> date:
    base = today or datetime.now(AZ).date()
    return base + timedelta(days=(6 - base.weekday()) % 7)


def _kickoff_et(target: date, clock: str) -> datetime | None:
    raw = str(clock or "").strip()
    if not raw or raw.lower() in {"nan", "none"}:
        return None
    for fmt in ("%H:%M", "%I:%M %p"):
        try:
            parsed = datetime.strptime(raw, fmt).time()
            return datetime.combine(target, parsed, ET).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _safe_iso(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _game(
    *,
    away: Any,
    home: Any,
    kickoff_utc: datetime | None,
    source: str,
    season: int,
    week: int | None = None,
    network: str = "",
    status: str = "",
    venue: str = "",
    game_id: str = "",
) -> dict[str, Any] | None:
    away_abbr = _canon_team(away)
    home_abbr = _canon_team(home)
    if away_abbr not in TEAM_NAMES or home_abbr not in TEAM_NAMES or away_abbr == home_abbr:
        return None
    return {
        "away": away_abbr,
        "home": home_abbr,
        "kickoff_utc": kickoff_utc,
        "source": source,
        "season": int(season),
        "week": int(week) if week not in (None, "", "nan") else None,
        "network": str(network or "").strip(),
        "status": str(status or "").strip(),
        "venue": str(venue or "").strip(),
        "game_id": str(game_id or "").strip(),
    }


def _from_nflverse(target: date) -> list[dict[str, Any]]:
    response = requests.get(
        NFLVERSE_GAMES_URL,
        headers=REQUEST_HEADERS,
        timeout=6,
    )
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text), low_memory=False)
    if "gameday" not in frame.columns:
        raise RuntimeError("NFLVERSE_GAMEDAY_MISSING")
    rows = frame[frame["gameday"].astype(str) == target.isoformat()]
    games: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        kickoff = _kickoff_et(target, row.get("gametime", ""))
        item = _game(
            away=row.get("away_team"),
            home=row.get("home_team"),
            kickoff_utc=kickoff,
            source="NFLVERSE",
            season=int(row.get("season", target.year)),
            week=row.get("week"),
            network=row.get("network", ""),
            status="scheduled",
            venue=row.get("stadium", ""),
            game_id=row.get("game_id", ""),
        )
        if item:
            games.append(item)
    return games


class _CBSScheduleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current_date: date | None = None
        self.rows: list[tuple[date | None, list[str]]] = []
        self.text_nodes: list[str] = []
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None
        self._ignored_depth = 0

    @staticmethod
    def _clean(parts: list[str]) -> str:
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    @staticmethod
    def _heading_date(text: str) -> date | None:
        match = re.search(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
            r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        month, day_text, year_text = match.groups()
        try:
            return datetime.strptime(
                f"{month} {int(day_text)} {int(year_text)}", "%B %d %Y"
            ).date()
        except ValueError:
            return None

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if lowered in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading_tag = lowered
            self._heading_parts = []
        elif lowered == "tr":
            self._row = []
        elif lowered in {"td", "th"} and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        cleaned = re.sub(r"\s+", " ", data).strip()
        if cleaned:
            self.text_nodes.append(cleaned)
        if self._heading_tag is not None:
            self._heading_parts.append(data)
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            if self._ignored_depth:
                self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if lowered == self._heading_tag:
            heading = self._clean(self._heading_parts)
            parsed = self._heading_date(heading)
            if parsed is not None:
                self.current_date = parsed
            self._heading_tag = None
            self._heading_parts = []
        elif lowered in {"td", "th"} and self._cell_parts is not None:
            if self._row is not None:
                self._row.append(self._clean(self._cell_parts))
            self._cell_parts = None
        elif lowered == "tr" and self._row is not None:
            self.rows.append((self.current_date, self._row))
            self._row = None
            self._cell_parts = None


def _canon_cbs_team(value: Any) -> str:
    token = re.sub(r"\s+", " ", str(value or "")).strip().upper()
    if token in CBS_TEAM_ALIASES:
        return CBS_TEAM_ALIASES[token]
    canonical = _canon_team(token)
    if canonical in TEAM_NAMES:
        return canonical
    for label, team in sorted(
        CBS_TEAM_ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if token.startswith(label + " "):
            nickname = TEAM_NAMES[team].upper()
            if nickname in token[len(label):]:
                return team
    return canonical


_CBS_TEAM_TOKEN_RE = re.compile(
    "|".join(
        rf"(?<![A-Z0-9]){re.escape(label)}(?![A-Z0-9])"
        for label in sorted(CBS_TEAM_ALIASES, key=len, reverse=True)
    ),
    re.IGNORECASE,
)
_CBS_TIME_TOKEN_RE = re.compile(
    r"\b(\d{1,2}:\d{2})\s*(am|pm)\b",
    re.IGNORECASE,
)


def _cbs_day_text_nodes(
    parser: _CBSScheduleHTMLParser,
    target: date,
) -> list[str]:
    selected: list[str] = []
    active = False
    for node in parser.text_nodes:
        parsed = parser._heading_date(node)
        if parsed is not None:
            if active and parsed != target:
                break
            active = parsed == target
            continue
        if active:
            selected.append(node)
    return selected


def _parse_cbs_schedule_text_nodes(
    nodes: list[str],
    *,
    target: date,
    week: int,
) -> list[dict[str, Any]]:
    events: list[tuple[int, str, str]] = []
    offset = 0
    joined_parts: list[str] = []
    for node in nodes:
        joined_parts.append(node)
    text = " ".join(joined_parts)
    upper = text.upper()

    for match in _CBS_TEAM_TOKEN_RE.finditer(upper):
        events.append((match.start(), "team", match.group(0)))
    for match in _CBS_TIME_TOKEN_RE.finditer(text):
        events.append((match.start(), "time", match.group(0)))
    events.sort(key=lambda item: item[0])

    pending_teams: list[str] = []
    games: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for _, kind, value in events:
        if kind == "team":
            team = _canon_cbs_team(value)
            if team in TEAM_NAMES:
                if not pending_teams or pending_teams[-1] != team:
                    pending_teams.append(team)
                    pending_teams = pending_teams[-2:]
            continue

        time_match = _CBS_TIME_TOKEN_RE.search(value)
        if not time_match or len(pending_teams) != 2:
            continue
        away, home = pending_teams
        pending_teams = []
        if away == home or (away, home) in seen:
            continue
        clock = f"{time_match.group(1)} {time_match.group(2).upper()}"
        item = _game(
            away=away,
            home=home,
            kickoff_utc=_kickoff_et(target, clock),
            source="CBS",
            season=target.year,
            week=week,
            network="",
            status="scheduled",
        )
        if item:
            games.append(item)
            seen.add((away, home))
    return games


def _parse_cbs_schedule_html(
    body: str,
    *,
    target: date,
    week: int,
) -> list[dict[str, Any]]:
    parser = _CBSScheduleHTMLParser()
    parser.feed(body)

    games: list[dict[str, Any]] = []
    for row_date, cells in parser.rows:
        if row_date != target or len(cells) < 3:
            continue
        away = _canon_cbs_team(cells[0])
        home = _canon_cbs_team(cells[1])
        if away not in TEAM_NAMES or home not in TEAM_NAMES:
            continue

        time_cell = next(
            (
                cell
                for cell in cells[2:]
                if re.search(r"\b\d{1,2}:\d{2}\s*(?:am|pm)\b", cell, re.IGNORECASE)
            ),
            "",
        )
        time_match = re.search(
            r"\b(\d{1,2}:\d{2})\s*(am|pm)\b",
            time_cell,
            re.IGNORECASE,
        )
        if not time_match:
            continue
        clock = f"{time_match.group(1)} {time_match.group(2).upper()}"
        network = time_cell[time_match.end():].strip(" -|")
        venue = cells[4].strip() if len(cells) >= 5 else ""
        item = _game(
            away=away,
            home=home,
            kickoff_utc=_kickoff_et(target, clock),
            source="CBS",
            season=target.year,
            week=week,
            network=network,
            status="scheduled",
            venue=venue,
        )
        if item:
            games.append(item)
    if games:
        return games

    # CBS's production schedule markup is component/div based rather than a
    # semantic table in some responses. Fall back to ordered visible text for
    # the exact target-day section while preserving the same independent
    # away/home/kickoff evidence contract.
    from_nodes = _parse_cbs_schedule_text_nodes(
        _cbs_day_text_nodes(parser, target),
        target=target,
        week=week,
    )
    if from_nodes:
        return from_nodes
    return _parse_cbs_schedule_stripped_text(
        body,
        target=target,
        week=week,
    )


def _parse_cbs_schedule_stripped_text(
    body: str,
    *,
    target: date,
    week: int,
) -> list[dict[str, Any]]:
    """Parse the exact target-day CBS section from stripped visible HTML text."""
    clean = html_lib.unescape(re.sub(r"<[^>]+>", " ", body))
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return []

    month = target.strftime("%B")
    weekday = target.strftime("%A")
    anchors = (
        f"{weekday}, {month} {target.day}, {target.year}",
        f"{weekday}, {month} {target.day}",
    )
    lower = clean.lower()
    start = -1
    anchor_used = ""
    for anchor in anchors:
        pos = lower.find(anchor.lower())
        if pos >= 0:
            start = pos + len(anchor)
            anchor_used = anchor
            break
    if start < 0:
        return []

    # Stop at the next dated weekday heading when present.
    section = clean[start:]
    next_positions: list[int] = []
    for name in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"):
        if name.lower() == weekday.lower():
            continue
        m = re.search(
            rf"\b{name},\s+[A-Za-z]+\s+\d{{1,2}}(?:,\s+\d{{4}})?\b",
            section,
            re.IGNORECASE,
        )
        if m:
            next_positions.append(m.start())
    if next_positions:
        section = section[: min(next_positions)]

    return _parse_cbs_schedule_text_nodes(
        [section],
        target=target,
        week=week,
    )


def _from_cbs(target: date, week: int | None) -> list[dict[str, Any]]:
    if not week:
        return []
    response = requests.get(
        CBS_SCHEDULE_URL.format(season=target.year, week=week),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0 Safari/537.36"
            )
        },
        timeout=6,
    )
    response.raise_for_status()
    return _parse_cbs_schedule_html(response.text, target=target, week=int(week))


def _espn_events_to_games(payload: dict[str, Any], target: date) -> list[dict[str, Any]]:
    games: list[dict[str, Any]] = []
    for event in payload.get("events", []) or []:
        competition = (event.get("competitions") or [{}])[0]
        sides = {}
        for competitor in competition.get("competitors", []) or []:
            sides[competitor.get("homeAway")] = (
                competitor.get("team", {}).get("abbreviation")
            )
        broadcasts = []
        for broadcast in competition.get("broadcasts", []) or []:
            broadcasts.extend(broadcast.get("names") or [])
        week = (
            event.get("week", {}).get("number")
            or competition.get("week", {}).get("number")
            or payload.get("week", {}).get("number")
        )
        season = event.get("season", {}).get("year") or target.year
        status = (
            event.get("status", {}).get("type", {}).get("description")
            or event.get("status", {}).get("type", {}).get("name")
            or competition.get("status", {}).get("type", {}).get("description")
            or "scheduled"
        )
        venue = competition.get("venue", {}).get("fullName", "")
        kickoff = _safe_iso(event.get("date") or competition.get("date"))
        if kickoff is not None and kickoff.astimezone(ET).date() != target:
            continue
        item = _game(
            away=sides.get("away"),
            home=sides.get("home"),
            kickoff_utc=kickoff,
            source="ESPN",
            season=int(season),
            week=week,
            network=" / ".join(dict.fromkeys(broadcasts)),
            status=status,
            venue=venue,
            game_id=event.get("id", ""),
        )
        if item:
            games.append(item)
    return games


def _espn_json(url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(
        url,
        params=params or {},
        headers=REQUEST_HEADERS,
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _from_espn_team_schedules(
    target: date,
    candidate_games: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # Query one team schedule per candidate matchup. The candidate list chooses
    # which independent ESPN pages to inspect; ESPN remains a single source.
    team_ids: list[str] = []
    for game in candidate_games:
        team_id = ESPN_TEAM_IDS.get(str(game.get("away") or "").upper())
        if team_id and team_id not in team_ids:
            team_ids.append(team_id)

    # If the slate-discovery source is unavailable in public Streamlit, ESPN
    # must still be able to discover the target date independently. Query all
    # team schedules and dedupe the resulting events. This is slower only on
    # the failover path and remains cached by the Step 2 truth layer.
    if not team_ids:
        team_ids = list(dict.fromkeys(ESPN_TEAM_IDS.values()))

    def load_one(team_id: str) -> list[dict[str, Any]]:
        params = {"season": target.year, "seasontype": 2}
        last_error: Exception | None = None
        for template in (ESPN_TEAM_SCHEDULE_URL, ESPN_WEB_TEAM_SCHEDULE_URL):
            try:
                payload = _espn_json(template.format(team_id=team_id), params=params)
                games = _espn_events_to_games(payload, target)
                if games:
                    return games
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            return []
        return []

    collected: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, len(team_ids))) as pool:
        futures = [pool.submit(load_one, team_id) for team_id in team_ids]
        for future in futures:
            collected.extend(future.result())

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for game in collected:
        deduped[(game["away"], game["home"])] = game
    return list(deduped.values())


_FOOTBALLDB_GAME_RE = re.compile(
    r"\b(\d{2}/\d{2})(?:\s+\([A-Za-z]{3}\))?\s+"
    r"([A-Za-z]{2,3})\s+@\s+([A-Za-z]{2,3})\s+"
    r"(\d{1,2}:\d{2}\s+[AP]M)\b",
    re.IGNORECASE,
)


def _parse_footballdb_schedule(
    body: str,
    *,
    target: date,
) -> list[dict[str, Any]]:
    clean = html_lib.unescape(re.sub(r"<[^>]+>", " ", body))
    clean = re.sub(r"\s+", " ", clean)
    target_token = target.strftime("%m/%d")
    games: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in _FOOTBALLDB_GAME_RE.finditer(clean):
        day_token, away, home, clock = match.groups()
        if day_token != target_token:
            continue
        item = _game(
            away=away,
            home=home,
            kickoff_utc=_kickoff_et(target, clock.upper()),
            source="FOOTBALLDB",
            season=target.year,
            status="scheduled",
        )
        if item and (item["away"], item["home"]) not in seen:
            seen.add((item["away"], item["home"]))
            games.append(item)
    return games


def _from_footballdb(target: date) -> list[dict[str, Any]]:
    response = requests.get(
        FOOTBALLDB_SCHEDULE_URL.format(season=target.year),
        headers={
            "User-Agent": REQUEST_HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,*/*",
        },
        timeout=8,
    )
    response.raise_for_status()
    return _parse_footballdb_schedule(response.text, target=target)


_PFR_GAME_RE = re.compile(
    rf"\b(\d{{4}}-\d{{2}}-\d{{2}})\s+"
    r"(\d{1,2}:\d{2}(?:AM|PM))\s+"
    rf"({_NFL_RELEASE_TEAM_PATTERN})\s+@\s+"
    rf"({_NFL_RELEASE_TEAM_PATTERN})\b",
    re.IGNORECASE,
)


def _parse_pfr_schedule(
    body: str,
    *,
    target: date,
) -> list[dict[str, Any]]:
    clean = html_lib.unescape(re.sub(r"<[^>]+>", " ", body))
    clean = re.sub(r"\s+", " ", clean)
    name_map = {name.upper(): team for name, team in NFL_RELEASE_TEAM_NAMES.items()}
    games: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in _PFR_GAME_RE.finditer(clean):
        day_token, clock, away_name, home_name = match.groups()
        if day_token != target.isoformat():
            continue
        away = name_map.get(away_name.upper())
        home = name_map.get(home_name.upper())
        item = _game(
            away=away,
            home=home,
            kickoff_utc=_kickoff_et(target, clock.upper()),
            source="PFR",
            season=target.year,
            status="scheduled",
        )
        if item and (item["away"], item["home"]) not in seen:
            seen.add((item["away"], item["home"]))
            games.append(item)
    return games


def _from_pfr(target: date) -> list[dict[str, Any]]:
    response = requests.get(
        PFR_SCHEDULE_URL.format(season=target.year),
        headers={
            "User-Agent": REQUEST_HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,*/*",
        },
        timeout=8,
    )
    response.raise_for_status()
    return _parse_pfr_schedule(response.text, target=target)


def _parse_pfn_schedule(
    body: str,
    *,
    target: date,
) -> list[dict[str, Any]]:
    clean = html_lib.unescape(re.sub(r"<[^>]+>", " ", body))
    clean = re.sub(r"\s+", " ", clean)

    heading = target.strftime("%A, %B %-d, %Y")
    start = clean.lower().find(heading.lower())
    if start < 0:
        # Some renders omit the year from day headings.
        heading = target.strftime("%A, %B %-d")
        start = clean.lower().find(heading.lower())
    if start < 0:
        return []

    section = clean[start + len(heading):]
    next_heading = re.search(
        r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
        r"[A-Za-z]+\s+\d{1,2}(?:,\s+\d{4})?\b",
        section,
        re.IGNORECASE,
    )
    if next_heading:
        section = section[:next_heading.start()]

    team_re = re.compile(_NFL_RELEASE_TEAM_PATTERN, re.IGNORECASE)
    time_re = re.compile(r"\b(\d{1,2}:\d{2}\s+[AP]M)\s+ET\b", re.IGNORECASE)
    events: list[tuple[int, str, str]] = []
    for match in team_re.finditer(section):
        events.append((match.start(), "team", match.group(0)))
    for match in time_re.finditer(section):
        events.append((match.start(), "time", match.group(1)))
    events.sort(key=lambda item: item[0])

    name_map = {name.upper(): team for name, team in NFL_RELEASE_TEAM_NAMES.items()}
    pending_time: str | None = None
    pending_teams: list[str] = []
    games: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for _, kind, value in events:
        if kind == "time":
            pending_time = value.upper()
            pending_teams = []
            continue

        team = name_map.get(value.upper())
        if not team or pending_time is None:
            continue
        if not pending_teams or pending_teams[-1] != team:
            pending_teams.append(team)
        # PFN cards can repeat team names in image/link text. Deduplicate until
        # two distinct teams are observed after one kickoff timestamp.
        unique: list[str] = []
        for candidate in pending_teams:
            if candidate not in unique:
                unique.append(candidate)
        if len(unique) < 2:
            continue

        away, home = unique[0], unique[1]
        if away != home and (away, home) not in seen:
            item = _game(
                away=away,
                home=home,
                kickoff_utc=_kickoff_et(target, pending_time),
                source="PFN",
                season=target.year,
                status="scheduled",
            )
            if item:
                seen.add((away, home))
                games.append(item)
        pending_time = None
        pending_teams = []

    return games


def _from_pfn(target: date) -> list[dict[str, Any]]:
    response = requests.get(
        PFN_SCHEDULE_URL.format(target=target.isoformat()),
        headers={
            "User-Agent": REQUEST_HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,*/*",
        },
        timeout=8,
    )
    response.raise_for_status()
    return _parse_pfn_schedule(response.text, target=target)


def _from_espn(
    target: date,
    candidate_games: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    params = {"dates": target.strftime("%Y%m%d"), "limit": 100}
    for url in (ESPN_SCOREBOARD_URL, ESPN_WEB_SCOREBOARD_URL):
        try:
            games = _espn_events_to_games(_espn_json(url, params=params), target)
            if games:
                return games
        except Exception:
            pass

    # GitHub-runner history proves ESPN team schedule endpoints can remain
    # reachable even when the scoreboard endpoint is blocked with HTTP 403.
    return _from_espn_team_schedules(target, list(candidate_games or []))


_OFFICIAL_GAME_RE = re.compile(
    r"\b([A-Za-z0-9]+)\s+at\s+([A-Za-z0-9]+),\s+Sunday,\s+"
    r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th),\s+"
    r"(\d{1,2}:\d{2}\s+[AP]M)(?:,\s+([A-Z][A-Z0-9+/.]*))?",
    re.IGNORECASE,
)


NFL_RELEASE_TEAM_NAMES = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}
_NFL_RELEASE_TEAM_PATTERN = "|".join(
    re.escape(name)
    for name in sorted(NFL_RELEASE_TEAM_NAMES, key=len, reverse=True)
)
_NFL_RELEASE_GAME_RE = re.compile(
    rf"\b(?:THU|FRI|SAT|SUN|MON)\s+(\d{{2}}/\d{{2}})\s+"
    rf"({_NFL_RELEASE_TEAM_PATTERN})\s+"
    r"(\d{1,2}:\d{2})\s+(AM|PM)\s+(?:ET|EST|EDT)\s+@\s+"
    rf"({_NFL_RELEASE_TEAM_PATTERN})\b",
    re.IGNORECASE,
)


def _parse_nfl_schedule_release(
    body: str,
    *,
    target: date,
    season: int,
    week: int | None,
) -> list[dict[str, Any]]:
    clean = html_lib.unescape(re.sub(r"<[^>]+>", " ", body))
    clean = re.sub(r"\s+", " ", clean)
    target_token = target.strftime("%m/%d")
    name_map = {name.upper(): team for name, team in NFL_RELEASE_TEAM_NAMES.items()}
    games: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in _NFL_RELEASE_GAME_RE.finditer(clean):
        day_token, away_name, clock, meridiem, home_name = match.groups()
        if day_token != target_token:
            continue
        away = name_map.get(away_name.upper())
        home = name_map.get(home_name.upper())
        item = _game(
            away=away,
            home=home,
            kickoff_utc=_kickoff_et(target, f"{clock} {meridiem.upper()}"),
            source="NFL",
            season=season,
            week=week,
            status="scheduled",
        )
        if item and (item["away"], item["home"]) not in seen:
            seen.add((item["away"], item["home"]))
            games.append(item)
    return games


def _from_nfl_schedule_release(
    target: date,
    *,
    season: int,
    week: int | None,
) -> list[dict[str, Any]]:
    response = requests.get(
        NFL_SCHEDULE_RELEASE_URL,
        headers={
            "User-Agent": REQUEST_HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,*/*",
        },
        timeout=8,
    )
    response.raise_for_status()
    return _parse_nfl_schedule_release(
        response.text,
        target=target,
        season=season,
        week=week,
    )


def _from_nfl_official(target: date, season: int, week: int | None) -> list[dict[str, Any]]:
    if not week:
        return []
    url = NFL_SCHEDULE_URL.format(season=season, week=week)
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=6)
    response.raise_for_status()
    clean = html_lib.unescape(re.sub(r"<[^>]+>", " ", response.text))
    clean = re.sub(r"\s+", " ", clean)

    games: list[dict[str, Any]] = []
    for match in _OFFICIAL_GAME_RE.finditer(clean):
        away, home, month, day_text, clock, network = match.groups()
        try:
            game_date = datetime.strptime(
                f"{month} {int(day_text)} {season}", "%B %d %Y"
            ).date()
        except ValueError:
            continue
        if game_date != target:
            continue
        kickoff = _kickoff_et(target, clock)
        item = _game(
            away=away,
            home=home,
            kickoff_utc=kickoff,
            source="NFL",
            season=season,
            week=week,
            network=network or "",
            status="scheduled",
        )
        if item:
            games.append(item)
    if games:
        return games
    return _from_nfl_schedule_release(
        target,
        season=season,
        week=week,
    )


def _week_hint(*collections: list[dict[str, Any]]) -> int | None:
    for games in collections:
        for game in games:
            if game.get("week"):
                return int(game["week"])
    return None


def _field_from_sources(
    bundle: dict[str, dict[str, Any]],
    field: str,
    order: tuple[str, ...],
    default: Any = "",
) -> Any:
    for source in order:
        value = bundle.get(source, {}).get(field)
        if value not in (None, ""):
            return value
    return default


def _reconcile_schedule(
    source_games: dict[str, list[dict[str, Any]]],
    target: date,
) -> list[dict[str, Any]]:
    bundles: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for source, games in source_games.items():
        for game in games:
            kickoff = game.get("kickoff_utc")
            if kickoff is not None:
                event_date = kickoff.astimezone(ET).date()
                if event_date != target:
                    continue
            key = (game["away"], game["home"])
            bundles.setdefault(key, {})[source] = game

    reconciled: list[dict[str, Any]] = []
    for (away, home), bundle in bundles.items():
        sources = tuple(source for source in SOURCE_PRIORITY if source in bundle)
        kickoff = _field_from_sources(
            bundle, "kickoff_utc", ("NFL", "CBS", "ESPN", "NFLVERSE"), None
        )
        week = _field_from_sources(bundle, "week", ("NFL", "CBS", "NFLVERSE", "ESPN"), None)
        network = _field_from_sources(bundle, "network", ("NFL", "CBS", "ESPN", "NFLVERSE"), "")
        status = _field_from_sources(bundle, "status", ("ESPN", "NFL", "CBS", "NFLVERSE"), "scheduled")
        venue = _field_from_sources(bundle, "venue", ("CBS", "NFLVERSE", "ESPN", "NFL"), "")
        game_id = _field_from_sources(bundle, "game_id", ("NFLVERSE", "ESPN", "NFL", "CBS"), "")

        kickoff_votes = [
            game.get("kickoff_utc")
            for game in bundle.values()
            if game.get("kickoff_utc") is not None
        ]
        kickoff_consensus = len(kickoff_votes) >= 2
        if kickoff_consensus:
            anchor = kickoff_votes[0]
            kickoff_consensus = all(
                abs((vote - anchor).total_seconds()) <= 600
                for vote in kickoff_votes[1:]
            )

        reconciled.append(
            {
                "away": away,
                "home": home,
                "away_name": TEAM_NAMES[away],
                "home_name": TEAM_NAMES[home],
                "kickoff_utc": kickoff,
                "week": week,
                "network": network,
                "status": status,
                "venue": venue,
                "game_id": game_id,
                "sources": sources,
                "source_count": len(sources),
                "verified": (
                    len(sources) >= 2
                    and len(kickoff_votes) >= 2
                    and kickoff_consensus
                ),
                "kickoff_consensus": kickoff_consensus,
            }
        )

    def sort_key(game: dict[str, Any]) -> tuple[int, str, str]:
        kickoff = game.get("kickoff_utc")
        stamp = int(kickoff.timestamp()) if kickoff else 2**62
        return stamp, game["away"], game["home"]

    return sorted(reconciled, key=sort_key)


def _load_schedule_truth_uncached(target: date) -> dict[str, Any]:
    errors: dict[str, str] = {}

    def safe(label: str, loader):
        try:
            return loader()
        except Exception as exc:
            errors[label] = f"{type(exc).__name__}:{exc}"
            return []

    # NFLVERSE is a fast slate-discovery source. Once its candidate matchups
    # are known, independent providers verify those fields. No provider is
    # mandatory and no single source can produce VERIFIED status.
    nflverse_games = safe("NFLVERSE", lambda: _from_nflverse(target))
    week = _week_hint(nflverse_games)
    season = target.year

    with ThreadPoolExecutor(max_workers=6) as pool:
        espn_future = pool.submit(
            safe,
            "ESPN",
            lambda: _from_espn(target, candidate_games=nflverse_games),
        )
        cbs_future = pool.submit(
            safe,
            "CBS",
            lambda: _from_cbs(target, week=week),
        )
        pfr_future = pool.submit(
            safe,
            "PFR",
            lambda: _from_pfr(target),
        )
        pfn_future = pool.submit(
            safe,
            "PFN",
            lambda: _from_pfn(target),
        )
        footballdb_future = pool.submit(
            safe,
            "FOOTBALLDB",
            lambda: _from_footballdb(target),
        )
        nfl_future = pool.submit(
            safe,
            "NFL",
            lambda: _from_nfl_official(target, season=season, week=week),
        )
        espn_games = espn_future.result()
        cbs_games = cbs_future.result()
        pfr_games = pfr_future.result()
        pfn_games = pfn_future.result()
        footballdb_games = footballdb_future.result()
        official_games = nfl_future.result()

    source_games = {
        "NFL": official_games,
        "CBS": cbs_games,
        "PFR": pfr_games,
        "PFN": pfn_games,
        "FOOTBALLDB": footballdb_games,
        "NFLVERSE": nflverse_games,
        "ESPN": espn_games,
    }
    games = _reconcile_schedule(source_games, target)
    available = tuple(
        source for source in SOURCE_PRIORITY if source_games.get(source)
    )
    verified_count = sum(1 for game in games if game["verified"])

    return {
        "target_date": target.isoformat(),
        "season": season,
        "week": week,
        "games": games,
        "game_count": len(games),
        "verified_count": verified_count,
        "sources_available": available,
        "source_errors": errors,
        "fail_closed": not bool(games),
    }


@st.cache_data(ttl=600, show_spinner=False)
def _cached_schedule_truth(target_iso: str) -> dict[str, Any]:
    return _load_schedule_truth_uncached(date.fromisoformat(target_iso))


def load_schedule_truth(target_date: date | None = None) -> dict[str, Any]:
    target = target_date or _target_sunday()
    return _cached_schedule_truth(target.isoformat())


def _kickoff_label(kickoff: datetime | None) -> str:
    if kickoff is None:
        return "Time TBD"
    local = kickoff.astimezone(ET)
    return local.strftime("%-I:%M %p ET")


def render_schedule_truth_layer() -> None:
    truth = load_schedule_truth()
    games = truth["games"]
    target = date.fromisoformat(truth["target_date"])
    date_label = target.strftime("%A • %B %-d, %Y")
    source_label = " + ".join(truth["sources_available"]) or "No source"
    verified_count = int(truth["verified_count"])

    if truth["fail_closed"]:
        st.markdown(
            f"""
<section data-nfl-prop-analytics-step2-schedule="v1"
         data-prop-schedule-state="fail-closed"
         data-prop-schedule-date="{html_lib.escape(truth['target_date'])}"
         data-prop-schedule-count="0"
         data-prop-schedule-verified-count="0">
  <div class="ks-pa2-empty">
    <strong>Schedule truth is temporarily unavailable.</strong>
    <span>No unverified or fabricated games are being displayed.</span>
  </div>
</section>
""",
            unsafe_allow_html=True,
        )
        return

    cards = []
    for game in games:
        badge = "VERIFIED" if game["verified"] else "SOURCE CONFIRMED"
        sources = " • ".join(game["sources"])
        network = game["network"] or "Network TBD"
        cards.append(
            f"""
<article class="ks-pa2-game" data-prop-game="{game['away']}-{game['home']}"
         data-prop-game-source-count="{game['source_count']}"
         data-prop-game-verified="{'true' if game['verified'] else 'false'}">
  <div class="ks-pa2-cardtop">
    <span>{html_lib.escape(_kickoff_label(game['kickoff_utc']))}</span>
    <span>{html_lib.escape(network)}</span>
  </div>
  <div class="ks-pa2-matchup">
    <div class="ks-pa2-team">
      <img class="ks-pa2-logo"
           data-prop-team-logo="{html_lib.escape(game['away'])}"
           data-prop-logo-side="away"
           src="{html_lib.escape(team_logo_url(game['away']))}"
           alt="{html_lib.escape(game['away_name'])} logo"
           loading="lazy" width="42" height="42" />
      <div class="ks-pa2-teamcopy">
        <b>{html_lib.escape(game['away'])}</b>
        <span>{html_lib.escape(game['away_name'])}</span>
      </div>
    </div>
    <div class="ks-pa2-at">@</div>
    <div class="ks-pa2-team ks-pa2-home">
      <img class="ks-pa2-logo"
           data-prop-team-logo="{html_lib.escape(game['home'])}"
           data-prop-logo-side="home"
           src="{html_lib.escape(team_logo_url(game['home']))}"
           alt="{html_lib.escape(game['home_name'])} logo"
           loading="lazy" width="42" height="42" />
      <div class="ks-pa2-teamcopy">
        <b>{html_lib.escape(game['home'])}</b>
        <span>{html_lib.escape(game['home_name'])}</span>
      </div>
    </div>
  </div>
  <div class="ks-pa2-proof">
    <span class="ks-pa2-badge">{badge}</span>
    <span>{html_lib.escape(sources)}</span>
  </div>
</article>
"""
        )

    st.markdown(
        f"""
<section class="ks-pa2-board"
         data-nfl-prop-analytics-step2-schedule="v1"
         data-prop-schedule-state="live"
         data-prop-schedule-date="{html_lib.escape(truth['target_date'])}"
         data-prop-schedule-count="{len(games)}"
         data-prop-schedule-verified-count="{verified_count}"
         data-prop-schedule-sources="{html_lib.escape(','.join(truth['sources_available']))}">
  <div class="ks-pa2-head">
    <div>
      <div class="ks-pa2-eyebrow">STEP 2 • SCHEDULE TRUTH</div>
      <h2>Sunday NFL Games</h2>
      <p>{html_lib.escape(date_label)}</p>
    </div>
    <div class="ks-pa2-truth">
      <strong>{verified_count}/{len(games)} verified</strong>
      <span>{html_lib.escape(source_label)}</span>
    </div>
  </div>
  <div class="ks-pa2-grid">
    {''.join(cards)}
  </div>
</section>
<style data-nfl-prop-analytics-step2-css="v1">
.ks-pa2-board{{width:100%;min-width:0;margin:10px 0 24px}}
.ks-pa2-head{{display:flex;justify-content:space-between;align-items:flex-end;gap:14px;margin:0 0 14px}}
.ks-pa2-eyebrow{{font-size:.7rem;font-weight:900;letter-spacing:.14em;color:#7dd3fc}}
.ks-pa2-head h2{{margin:.28rem 0 .18rem;color:#f8fafc;font-size:clamp(1.35rem,4vw,2rem);letter-spacing:-.035em}}
.ks-pa2-head p{{margin:0;color:#8fa4bd;font-size:.84rem}}
.ks-pa2-truth{{display:flex;flex-direction:column;align-items:flex-end;gap:3px;padding:9px 11px;border:1px solid rgba(125,211,252,.18);border-radius:12px;background:rgba(14,165,233,.055)}}
.ks-pa2-truth strong{{color:#e0f2fe;font-size:.78rem}}
.ks-pa2-truth span{{color:#7890ab;font-size:.65rem}}
.ks-pa2-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.ks-pa2-game{{min-width:0;border:1px solid rgba(125,211,252,.16);border-radius:15px;background:linear-gradient(145deg,rgba(7,14,24,.98),rgba(10,22,38,.94));padding:13px;overflow:hidden}}
.ks-pa2-cardtop,.ks-pa2-proof{{display:flex;justify-content:space-between;gap:8px;align-items:center;color:#7890ab;font-size:.66rem;font-weight:800}}
.ks-pa2-matchup{{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:8px;margin:14px 0}}
.ks-pa2-team{{display:flex;align-items:center;gap:9px;min-width:0}}
.ks-pa2-logo{{width:42px;height:42px;object-fit:contain;flex:0 0 42px;filter:drop-shadow(0 2px 7px rgba(0,0,0,.28))}}
.ks-pa2-teamcopy{{display:flex;flex-direction:column;min-width:0}}
.ks-pa2-team b{{color:#f8fafc;font-size:1.05rem;line-height:1}}
.ks-pa2-team span{{margin-top:4px;color:#a8bad0;font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ks-pa2-home{{text-align:right;justify-content:flex-start;flex-direction:row-reverse}}
.ks-pa2-home .ks-pa2-teamcopy{{align-items:flex-end}}
.ks-pa2-at{{color:#38bdf8;font-size:.72rem;font-weight:900}}
.ks-pa2-proof{{padding-top:10px;border-top:1px solid rgba(148,163,184,.10)}}
.ks-pa2-badge{{color:#bae6fd!important;font-size:.61rem;letter-spacing:.07em}}
.ks-pa2-empty{{padding:16px;border:1px solid rgba(248,113,113,.3);border-radius:14px;background:rgba(127,29,29,.12);display:flex;flex-direction:column;gap:4px}}
.ks-pa2-empty strong{{color:#fecaca}}.ks-pa2-empty span{{color:#cbd5e1;font-size:.8rem}}
@media(max-width:680px){{
  .ks-pa2-head{{align-items:stretch;flex-direction:column}}
  .ks-pa2-truth{{align-items:flex-start}}
  .ks-pa2-grid{{grid-template-columns:1fr}}
}}
</style>
""",
        unsafe_allow_html=True,
    )


__all__ = [
    "MODEL_VERSION",
    "STEP",
    "PAGE",
    "SCHEDULE_ONLY",
    "PLAYER_PROP_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_PASSING_YARDS",
    "MAY_MODIFY_EXISTING_NFL_MARKETS",
    "team_logo_url",
    "load_schedule_truth",
    "render_schedule_truth_layer",
]
