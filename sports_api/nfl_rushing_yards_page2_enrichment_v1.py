"""Verified field-first enrichment for NFL Rushing Yards Page 2.

Kyre Sports API remains the only application-facing gateway. This module fills
Page-2 fields that were previously hard-coded as pending: official injury and
trench context, current game spread/total, bounded historical rushing-prop line
context, exact-kickoff NWS weather, and nflverse schedule date repair.

No ESPN, ESPN BET, or SGO. No sportsbook value influences Kyre projections.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from html.parser import HTMLParser
import math
import os
import re
from typing import Any, Mapping

import requests

from sports_api.nfl_data_nws_v1 import fetch_environment

VERSION = "NFL_RUSHING_PAGE2_ENRICHMENT_V1"
NFL_INJURY_URL = "https://www.nfl.com/injuries/"
ODDS_BASE = "https://api.the-odds-api.com/v4"
BOOK_PRIORITY = ("FanDuel", "DraftKings", "BetMGM", "Caesars", "bet365", "Fanatics Sportsbook")
TEAM_NAMES = {
    "ARI":"Arizona Cardinals","ATL":"Atlanta Falcons","BAL":"Baltimore Ravens","BUF":"Buffalo Bills","CAR":"Carolina Panthers","CHI":"Chicago Bears","CIN":"Cincinnati Bengals","CLE":"Cleveland Browns","DAL":"Dallas Cowboys","DEN":"Denver Broncos","DET":"Detroit Lions","GB":"Green Bay Packers","HOU":"Houston Texans","IND":"Indianapolis Colts","JAX":"Jacksonville Jaguars","KC":"Kansas City Chiefs","LV":"Las Vegas Raiders","LAC":"Los Angeles Chargers","LAR":"Los Angeles Rams","MIA":"Miami Dolphins","MIN":"Minnesota Vikings","NE":"New England Patriots","NO":"New Orleans Saints","NYG":"New York Giants","NYJ":"New York Jets","PHI":"Philadelphia Eagles","PIT":"Pittsburgh Steelers","SF":"San Francisco 49ers","SEA":"Seattle Seahawks","TB":"Tampa Bay Buccaneers","TEN":"Tennessee Titans","WAS":"Washington Commanders",
}
NAME_TO_TEAM = {name.casefold(): abbr for abbr, name in TEAM_NAMES.items()}
OL_POSITIONS = frozenset({"C", "G", "T", "OT", "OG", "OL", "C/G", "G/T"})
FRONT_POSITIONS = frozenset({"DE", "DT", "NT", "DL", "LB", "ILB", "OLB", "EDGE"})


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split()).strip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).casefold()).strip()


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _book_name(key: Any, title: Any = None) -> str:
    mapping = {"fanduel":"FanDuel","draftkings":"DraftKings","betmgm":"BetMGM","caesars":"Caesars","williamhill_us":"Caesars","bet365":"bet365","bet365_nj":"bet365","fanatics":"Fanatics Sportsbook","fanaticssportsbook":"Fanatics Sportsbook"}
    return mapping.get(_text(key).casefold()) or _text(title) or _text(key)


def _api_key() -> str:
    for name in ("THE_ODDS_API_KEY", "KYRE_THE_ODDS_API_KEY", "ODDS_API_KEY"):
        value = _text(os.environ.get(name))
        if value:
            return value
    return ""


class _InjuryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current_team = ""
        self.in_table = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.headers: list[str] = []
        self.report: dict[str, dict[str, Any]] = {}

    def _observe_team(self, text: str) -> None:
        token = _text(text)
        folded = token.casefold()
        for name, abbr in NAME_TO_TEAM.items():
            if folded == name or name in folded:
                self.current_team = abbr
                self.report.setdefault(abbr, {"verified": True, "rows": []})
                return
        if self.current_team and "no injuries reported" in folded:
            self.report.setdefault(self.current_team, {"verified": True, "rows": []})["verified"] = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.in_table = True
            self.headers = []
        elif tag == "tr" and self.in_table:
            self.row = []
        elif tag in {"th", "td"} and self.in_table:
            self.in_cell = True
            self.cell_parts = []
        elif tag == "img":
            for key, value in attrs:
                if key == "alt" and value:
                    self._observe_team(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self.in_table and self.in_cell:
            self.row.append(_text(" ".join(self.cell_parts)))
            self.in_cell = False
        elif tag == "tr" and self.in_table and self.row:
            if any(_norm(cell) == "player" for cell in self.row):
                self.headers = list(self.row)
            elif self.current_team and len(self.row) >= 2:
                headers = self.headers or ["Player", "Position", "Injuries", "Practice Status", "Game Status"]
                data = {headers[i] if i < len(headers) else f"field_{i}": value for i, value in enumerate(self.row)}
                player = _text(data.get("Player"))
                position = _text(data.get("Position")).upper()
                if player and position:
                    self.report.setdefault(self.current_team, {"verified": True, "rows": []})["rows"].append({
                        "player_name": player,
                        "position": position,
                        "injury": _text(data.get("Injuries") or data.get("Injury")),
                        "practice_status": _text(data.get("Practice Status")),
                        "game_status": _text(data.get("Game Status")).upper(),
                    })
        elif tag == "table":
            self.in_table = False

    def handle_data(self, data: str) -> None:
        text = _text(data)
        if text:
            self._observe_team(text)
            if self.in_cell:
                self.cell_parts.append(text)


def parse_official_nfl_injury_html(html: str) -> dict[str, dict[str, Any]]:
    parser = _InjuryParser()
    parser.feed(str(html or ""))
    return parser.report


@lru_cache(maxsize=1)
def collect_official_nfl_injury_report() -> dict[str, dict[str, Any]]:
    response = requests.get(NFL_INJURY_URL, timeout=10, headers={"User-Agent": "KyreSportsAPI/1.0", "Accept": "text/html"})
    response.raise_for_status()
    return parse_official_nfl_injury_html(response.text)


def _flagged(rows: list[dict[str, Any]], positions: frozenset[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        position = _text(row.get("position")).upper()
        if position not in positions:
            continue
        status = _text(row.get("game_status")).upper()
        practice = _text(row.get("practice_status"))
        injury = _text(row.get("injury"))
        if status or injury or "DID NOT" in practice.upper() or "LIMITED" in practice.upper():
            out.append({"player_name": _text(row.get("player_name")), "position": position, "injury": injury, "game_status": status or "NO GAME STATUS", "practice_status": practice})
    return out


def build_injury_personnel_context(report: Mapping[str, Any], *, player_name: str, team: str, opponent: str) -> dict[str, Any]:
    team = _text(team).upper()
    opponent = _text(opponent).upper()
    team_report = report.get(team) if isinstance(report.get(team), Mapping) else {}
    opp_report = report.get(opponent) if isinstance(report.get(opponent), Mapping) else {}
    team_verified = team_report.get("verified") is True
    opp_verified = opp_report.get("verified") is True
    team_rows = [dict(row) for row in (team_report.get("rows") or []) if isinstance(row, Mapping)]
    opp_rows = [dict(row) for row in (opp_report.get("rows") or []) if isinstance(row, Mapping)]
    player = next((row for row in team_rows if _norm(row.get("player_name")) == _norm(player_name)), None)
    if team_verified:
        if player:
            status = _text(player.get("game_status")).upper() or "NO GAME STATUS"
            availability = {"verification":"VERIFIED","status":"VERIFIED","display":f"{status} · {_text(player.get('injury')) or 'No injury detail'}","game_status":status,"injury":_text(player.get("injury")),"practice_status":_text(player.get("practice_status")),"source":"NFL.com Official Injury Report"}
        else:
            availability = {"verification":"VERIFIED","status":"VERIFIED","display":"No official injury designation listed","game_status":"NO OFFICIAL INJURY DESIGNATION","injury":"","practice_status":"","source":"NFL.com Official Injury Report"}
    else:
        availability = {"verification":"UNAVAILABLE","status":"DATA_UNAVAILABLE","display":"Official NFL injury report unavailable","game_status":"DATA_UNAVAILABLE","injury":"","practice_status":"","source":"NFL.com Official Injury Report"}
    ol = _flagged(team_rows, OL_POSITIONS) if team_verified else []
    front = _flagged(opp_rows, FRONT_POSITIONS) if opp_verified else []
    return {
        "availability": availability,
        "offensive_line": {"verification":"VERIFIED" if team_verified else "UNAVAILABLE","flagged":ol,"display": ("No current OL injury designations" if team_verified and not ol else f"{len(ol)} OL designation{'s' if len(ol) != 1 else ''}" if team_verified else "Official OL report unavailable")},
        "defensive_front": {"verification":"VERIFIED" if opp_verified else "UNAVAILABLE","flagged":front,"display": ("No current front-seven injury designations" if opp_verified and not front else f"{len(front)} front-seven designation{'s' if len(front) != 1 else ''}" if opp_verified else "Official defensive-front report unavailable")},
    }


def parse_game_markets(payload: Mapping[str, Any], *, away_name: str, home_name: str) -> dict[str, Any]:
    priority = {name: index for index, name in enumerate(BOOK_PRIORITY)}
    candidates: list[dict[str, Any]] = []
    for book in payload.get("bookmakers") or []:
        if not isinstance(book, Mapping):
            continue
        sportsbook = _book_name(book.get("key"), book.get("title"))
        if sportsbook not in priority:
            continue
        row: dict[str, Any] = {"sportsbook": sportsbook, "timestamp": _text(book.get("last_update"))}
        for market in book.get("markets") or []:
            if not isinstance(market, Mapping):
                continue
            key = _text(market.get("key"))
            outcomes = [o for o in (market.get("outcomes") or []) if isinstance(o, Mapping)]
            if key == "spreads":
                for outcome in outcomes:
                    if _norm(outcome.get("name")) == _norm(away_name): row["away_spread"] = _num(outcome.get("point"))
                    if _norm(outcome.get("name")) == _norm(home_name): row["home_spread"] = _num(outcome.get("point"))
            elif key == "totals":
                points = [_num(outcome.get("point")) for outcome in outcomes if _num(outcome.get("point")) is not None]
                if points: row["total"] = points[0]
        if row.get("away_spread") is not None and row.get("home_spread") is not None and row.get("total") is not None:
            candidates.append(row)
    candidates.sort(key=lambda row: priority.get(_text(row.get("sportsbook")), 999))
    return dict(candidates[0]) if candidates else {}


def build_line_history(current: Mapping[str, Any], snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    current_line = _num(current.get("current_line"))
    sportsbook = _text(current.get("sportsbook"))
    valid = [dict(row) for row in snapshots if _num(row.get("line")) is not None and (not sportsbook or _text(row.get("sportsbook")) == sportsbook)]
    valid.sort(key=lambda row: _text(row.get("timestamp")))
    if current_line is None or not valid:
        return {"opening_line":None,"opening_line_status":"Historical snapshot unavailable","movement":None,"movement_status":"Historical movement unavailable"}
    opening = float(_num(valid[0].get("line")))
    movement = round(current_line - opening, 1)
    arrow = "UP" if movement > 0 else "DOWN" if movement < 0 else "UNCHANGED"
    return {"opening_line":opening,"opening_line_status":f"{opening:.1f} · earliest verified snapshot","movement":movement,"movement_status":f"{arrow} {movement:+.1f} FROM EARLIEST VERIFIED SNAPSHOT","opening_timestamp":valid[0].get("timestamp")}


def repair_history_dates(rows: list[dict[str, Any]], schedule: Mapping[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        if not _text(row.get("game_date")):
            day = _text(schedule.get(_text(row.get("source_game_id"))))
            if day: row["game_date"] = day[:10]
        out.append(row)
    return out


def normalize_weather(result: Mapping[str, Any]) -> dict[str, Any]:
    if result.get("ready") is not True:
        return {"verification":"UNAVAILABLE","status":"DATA_UNAVAILABLE","display":"Weather data unavailable","source":_text(result.get("provider"))}
    data = result.get("data") if isinstance(result.get("data"), Mapping) else {}
    if data.get("indoor") is True:
        return {"verification":"VERIFIED","status":"VERIFIED","display":"INDOORS — WEATHER IMPACT NONE","indoor":True,"source":_text(result.get("provider"))}
    temp, precip, gust = _num(data.get("temperature")), _num(data.get("precipitation")), _num(data.get("gust"))
    display = f"{temp:.0f}°F · {precip:.0f}% precip · {gust:.0f} mph gust" if None not in {temp, precip, gust} else "Verified outdoor weather"
    return {"verification":"VERIFIED","status":"VERIFIED","display":display,"indoor":False,"temperature_f":temp,"precipitation_pct":precip,"gust_mph":gust,"pressure":_text(data.get("weather_pressure")),"source":_text(result.get("provider"))}


def _request_json(url: str, *, params: Mapping[str, Any], timeout: int = 8) -> tuple[Any | None, str | None]:
    try:
        response = requests.get(url, params=dict(params), timeout=timeout, headers={"Accept":"application/json","User-Agent":"KyreSportsAPI-NFL-Rushing-Page2/1.0"})
        response.raise_for_status()
        return response.json(), None
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return None, f"{type(exc).__name__}" + (f":HTTP{status}" if status else "")


def _exact_event(events: Any, *, away_name: str, home_name: str) -> dict[str, Any] | None:
    if not isinstance(events, list): return None
    rows = [row for row in events if isinstance(row, Mapping) and _norm(row.get("away_team")) == _norm(away_name) and _norm(row.get("home_team")) == _norm(home_name)]
    return dict(rows[0]) if len(rows) == 1 else None


def _player_line(payload: Mapping[str, Any], *, player_name: str, sportsbook: str) -> float | None:
    for book in payload.get("bookmakers") or []:
        if not isinstance(book, Mapping) or _book_name(book.get("key"), book.get("title")) != sportsbook: continue
        for market in book.get("markets") or []:
            if not isinstance(market, Mapping) or _text(market.get("key")) != "player_rush_yds": continue
            for outcome in market.get("outcomes") or []:
                if isinstance(outcome, Mapping) and _norm(outcome.get("description")) == _norm(player_name):
                    point = _num(outcome.get("point"))
                    if point is not None: return point
    return None


def collect_market_context(*, away_name: str, home_name: str, kickoff_iso: str, player_name: str, current_prop: Mapping[str, Any]) -> dict[str, Any]:
    key = _api_key()
    if not key:
        return {"game_market":{},"prop_history":build_line_history(current_prop, []),"diagnostic":"THE_ODDS_API_NOT_CONFIGURED"}
    events, error = _request_json(f"{ODDS_BASE}/sports/americanfootball_nfl/events", params={"apiKey":key,"dateFormat":"iso"})
    event = _exact_event(events, away_name=away_name, home_name=home_name) if not error else None
    if not event or not _text(event.get("id")):
        return {"game_market":{},"prop_history":build_line_history(current_prop, []),"diagnostic":error or "EVENT_NOT_MAPPED"}
    event_id = _text(event.get("id"))
    current, current_error = _request_json(f"{ODDS_BASE}/sports/americanfootball_nfl/events/{event_id}/odds", params={"apiKey":key,"regions":"us","markets":"spreads,totals","oddsFormat":"american","dateFormat":"iso"})
    game_market = parse_game_markets(current, away_name=away_name, home_name=home_name) if isinstance(current, Mapping) and not current_error else {}
    snapshots: list[dict[str, Any]] = []
    sportsbook = _text(current_prop.get("sportsbook"))
    try:
        kickoff = datetime.fromisoformat(_text(kickoff_iso).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        kickoff = None
    if kickoff and sportsbook and _num(current_prop.get("current_line")) is not None:
        now = datetime.now(timezone.utc)
        for hours in (72, 48, 24):
            stamp = kickoff - timedelta(hours=hours)
            if stamp > now: continue
            hist, hist_error = _request_json(f"{ODDS_BASE}/historical/sports/americanfootball_nfl/events/{event_id}/odds", params={"apiKey":key,"regions":"us","markets":"player_rush_yds","oddsFormat":"american","dateFormat":"iso","date":stamp.isoformat().replace("+00:00","Z")})
            if hist_error: break
            payload = hist.get("data") if isinstance(hist, Mapping) and isinstance(hist.get("data"), Mapping) else hist
            if isinstance(payload, Mapping):
                line = _player_line(payload, player_name=player_name, sportsbook=sportsbook)
                if line is not None:
                    snapshots.append({"timestamp":_text(hist.get("timestamp") if isinstance(hist, Mapping) else stamp.isoformat()),"line":line,"sportsbook":sportsbook})
    return {"game_market":game_market,"prop_history":build_line_history(current_prop, snapshots),"provider_event_id":event_id,"diagnostic":""}


def collect_weather(*, home_abbr: str, kickoff_iso: str) -> dict[str, Any]:
    return normalize_weather(fetch_environment({"venue_name":"","home_abbr":_text(home_abbr).upper(),"kickoff_utc":kickoff_iso}))


__all__ = ["VERSION","build_injury_personnel_context","build_line_history","collect_market_context","collect_official_nfl_injury_report","collect_weather","normalize_weather","parse_game_markets","parse_official_nfl_injury_html","repair_history_dates"]
