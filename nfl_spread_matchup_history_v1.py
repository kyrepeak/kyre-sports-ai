"""NFL Spread matchup history — descriptive exact-match context only.

History is presentation context. It never mutates, weights, or feeds the NFL
Spread model. nflverse completed-game rows are primary; ESPN exact-team schedule
rows are a score-only fallback. Historical ATS is emitted only when a verified
historical spread line exists on the source row.
"""
from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
import math
from typing import Any

import requests

from sports_api import nfl_data_nflverse_v1 as nflverse

DISPLAY_ONLY = True
MODEL_INFLUENCE = 0.0
PRIMARY_SOURCE = "nflverse"
FALLBACK_SOURCE = "espn"
ESPN_TEAM_SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/schedule"
REQUEST_TIMEOUT_SECONDS = 4

_TEAM_NICKNAMES = {
    "ARI":"Cardinals","ATL":"Falcons","BAL":"Ravens","BUF":"Bills","CAR":"Panthers","CHI":"Bears",
    "CIN":"Bengals","CLE":"Browns","DAL":"Cowboys","DEN":"Broncos","DET":"Lions","GB":"Packers",
    "HOU":"Texans","IND":"Colts","JAX":"Jaguars","KC":"Chiefs","LAC":"Chargers","LAR":"Rams",
    "LV":"Raiders","MIA":"Dolphins","MIN":"Vikings","NE":"Patriots","NO":"Saints","NYG":"Giants",
    "NYJ":"Jets","PHI":"Eagles","PIT":"Steelers","SEA":"Seahawks","SF":"49ers","TB":"Buccaneers",
    "TEN":"Titans","WAS":"Commanders",
}


def _num(value: Any) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else math.nan
    except (TypeError, ValueError, OverflowError):
        return math.nan


def _abbr(value: Any) -> str:
    return nflverse.canonical_team_abbr(value)


def _fmt_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Date unavailable"
    try:
        day = datetime.fromisoformat(text[:10]).date()
        return f"{day.strftime('%b')} {day.day}, {day.year}"
    except ValueError:
        return text[:10]


def _ats_winner(away: str, home: str, away_score: float, home_score: float, spread_line: Any) -> str | None:
    line = _num(spread_line)
    if not math.isfinite(line):
        return None
    adjusted_home_margin = (home_score - away_score) + line
    if abs(adjusted_home_margin) < 1e-9:
        return "PUSH"
    return home if adjusted_home_margin > 0 else away


def _meeting(*, date_value: Any, away: str, home: str, away_score: Any, home_score: Any, spread_line: Any = None) -> dict[str, Any] | None:
    a_score = _num(away_score)
    h_score = _num(home_score)
    if not (math.isfinite(a_score) and math.isfinite(h_score)):
        return None
    winner = "TIE" if abs(a_score - h_score) < 1e-9 else (away if a_score > h_score else home)
    margin = abs(a_score - h_score)
    line = _num(spread_line)
    verified_line = line if math.isfinite(line) else None
    return {
        "date": _fmt_date(date_value),
        "away_abbr": away,
        "home_abbr": home,
        "away_score": int(a_score),
        "home_score": int(h_score),
        "score": f"{away} {int(a_score)} • {home} {int(h_score)}",
        "winner_abbr": winner,
        "margin": round(float(margin), 1),
        "spread_line": verified_line,
        "ats_winner": _ats_winner(away, home, a_score, h_score, verified_line),
    }


def _from_nflverse(away: str, home: str, limit: int) -> list[dict[str, Any]]:
    frame = nflverse._load_games_csv().copy()
    if frame.empty:
        return []
    for column in ("away_team", "home_team"):
        if column not in frame.columns:
            return []
        frame[column] = frame[column].map(_abbr)
    if "away_score" not in frame.columns or "home_score" not in frame.columns:
        return []
    pair = frame[
        ((frame["away_team"] == away) & (frame["home_team"] == home))
        | ((frame["away_team"] == home) & (frame["home_team"] == away))
    ].copy()
    pair = pair[pair["away_score"].notna() & pair["home_score"].notna()]
    if "gameday" in pair.columns:
        pair = pair.sort_values("gameday", ascending=False)
    meetings: list[dict[str, Any]] = []
    for row in pair.head(max(int(limit), 1)).to_dict("records"):
        item = _meeting(
            date_value=row.get("gameday"),
            away=_abbr(row.get("away_team")),
            home=_abbr(row.get("home_team")),
            away_score=row.get("away_score"),
            home_score=row.get("home_score"),
            spread_line=row.get("spread_line"),
        )
        if item:
            meetings.append(item)
    return meetings


@lru_cache(maxsize=128)
def _espn_schedule(team: str, season: int) -> tuple[dict[str, Any], ...]:
    response = requests.get(
        ESPN_TEAM_SCHEDULE.format(team=team.lower()),
        params={"season": int(season)},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    events = payload.get("events") if isinstance(payload, dict) else []
    return tuple(event for event in (events or []) if isinstance(event, dict))


def _load_espn_fallback(away: str, home: str, limit: int) -> list[dict[str, Any]]:
    meetings: list[dict[str, Any]] = []
    seen: set[str] = set()
    current_season = date.today().year
    for season in range(current_season, current_season - 7, -1):
        try:
            events = _espn_schedule(away, season)
        except Exception:
            continue
        for event in events:
            event_id = str(event.get("id") or "")
            if event_id and event_id in seen:
                continue
            competition = ((event.get("competitions") or [{}])[0]) if isinstance(event, dict) else {}
            status = competition.get("status") or event.get("status") or {}
            status_type = status.get("type") if isinstance(status, dict) else {}
            if isinstance(status_type, dict) and status_type.get("completed") is not True:
                continue
            competitors = competition.get("competitors") or []
            by_side: dict[str, dict[str, Any]] = {}
            for competitor in competitors:
                if not isinstance(competitor, dict):
                    continue
                side = str(competitor.get("homeAway") or "").lower()
                team = competitor.get("team") or {}
                abbr = _abbr(team.get("abbreviation"))
                if side in {"home", "away"} and abbr:
                    by_side[side] = {"abbr": abbr, "score": competitor.get("score")}
            if set(by_side) != {"home", "away"}:
                continue
            a = by_side["away"]["abbr"]
            h = by_side["home"]["abbr"]
            if {a, h} != {away, home}:
                continue
            item = _meeting(
                date_value=event.get("date"),
                away=a,
                home=h,
                away_score=by_side["away"].get("score"),
                home_score=by_side["home"].get("score"),
                spread_line=None,
            )
            if item:
                meetings.append(item)
                if event_id:
                    seen.add(event_id)
        if len(meetings) >= limit:
            break
    meetings.sort(key=lambda row: datetime.strptime(row["date"], "%b %d, %Y"), reverse=True)
    return meetings[:limit]


def _empty(*, source: str = "unavailable", error: str = "Matchup history unavailable.") -> dict[str, Any]:
    return {
        "ready": False,
        "display_only": True,
        "model_influence": 0.0,
        "source": source,
        "games": 0,
        "series_summary": "No verified meetings",
        "average_margin": None,
        "ats_games": 0,
        "ats_summary": "—",
        "meetings": [],
        "error": error,
    }


def _summarize(away: str, home: str, meetings: list[dict[str, Any]], source: str) -> dict[str, Any]:
    if not meetings:
        return _empty(source=source)
    wins = {away: 0, home: 0}
    ties = 0
    for row in meetings:
        winner = row.get("winner_abbr")
        if winner in wins:
            wins[winner] += 1
        elif winner == "TIE":
            ties += 1
    if wins[away] == wins[home]:
        series = f"Series tied {wins[away]}-{wins[home]}"
    else:
        leader = away if wins[away] > wins[home] else home
        trailer = home if leader == away else away
        series = f"{_TEAM_NICKNAMES.get(leader, leader)} lead {wins[leader]}-{wins[trailer]}"
        if ties:
            series += f"-{ties}"
    margins = [float(row["margin"]) for row in meetings if math.isfinite(_num(row.get("margin")))]
    ats_rows = [row for row in meetings if row.get("ats_winner")]
    ats_counts = {away: 0, home: 0, "PUSH": 0}
    for row in ats_rows:
        winner = row.get("ats_winner")
        if winner in ats_counts:
            ats_counts[winner] += 1
    if not ats_rows:
        ats_summary = "—"
    elif ats_counts[away] == ats_counts[home]:
        ats_summary = f"ATS split {ats_counts[away]}-{ats_counts[home]}"
    else:
        leader = away if ats_counts[away] > ats_counts[home] else home
        trailer = home if leader == away else away
        ats_summary = f"{leader} {ats_counts[leader]}-{ats_counts[trailer]} ATS"
        if ats_counts["PUSH"]:
            ats_summary += f" • {ats_counts['PUSH']} push"
    return {
        "ready": True,
        "display_only": True,
        "model_influence": 0.0,
        "source": source,
        "games": len(meetings),
        "series_summary": series,
        "average_margin": round(sum(margins) / len(margins), 1) if margins else None,
        "ats_games": len(ats_rows),
        "ats_summary": ats_summary,
        "meetings": meetings,
        "error": "",
    }


def load_matchup_history(game: dict[str, Any], *, limit: int = 5) -> dict[str, Any]:
    """Return last verified team-vs-team meetings without touching model inputs."""
    away = _abbr(game.get("away_abbr"))
    home = _abbr(game.get("home_abbr"))
    if not away or not home or away == home:
        return _empty(error="Exact matchup identity unavailable.")
    bounded_limit = min(max(int(limit), 1), 10)
    try:
        meetings = _from_nflverse(away, home, bounded_limit)
    except Exception:
        meetings = []
    if meetings:
        return _summarize(away, home, meetings, PRIMARY_SOURCE)
    try:
        meetings = _load_espn_fallback(away, home, bounded_limit)
    except Exception:
        meetings = []
    return _summarize(away, home, meetings, FALLBACK_SOURCE) if meetings else _empty()


__all__ = ["DISPLAY_ONLY", "MODEL_INFLUENCE", "load_matchup_history"]
