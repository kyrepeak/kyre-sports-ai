"""V20.5 team-history context for the MLB Slate.

Uses official MLB schedule/standings data to add season records, last-10,
last-5 and shrinkage-free descriptive H2H last-10 context to slate cards.
These are display/context fields; sportsbook prices remain separate from model
inputs unless the dedicated model module explicitly uses them.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import requests
import streamlit as st

from engine import ET, MLB_API

HEADERS = {"User-Agent": "KyreSportsAI/1.0"}


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return None


def _is_final(game):
    state = str(((game or {}).get("status") or {}).get("detailedState") or "").lower()
    return "final" in state or "game over" in state or "completed" in state


def _score_for_team(game, team_id):
    teams = (game or {}).get("teams") or {}
    away = teams.get("away") or {}
    home = teams.get("home") or {}
    away_id = _safe_int(((away.get("team") or {}).get("id")))
    home_id = _safe_int(((home.get("team") or {}).get("id")))
    try:
        away_score = int(away.get("score"))
        home_score = int(home.get("score"))
    except Exception:
        return None
    if away_id == int(team_id):
        return away_score, home_score, home_id
    if home_id == int(team_id):
        return home_score, away_score, away_id
    return None


def _summary(results, n):
    games = list(results or [])[-int(n):]
    if not games:
        return {"games": 0, "wins": 0, "losses": 0, "record": "N/A", "run_diff": None}
    wins = sum(1 for x in games if x["rf"] > x["ra"])
    losses = len(games) - wins
    diff = sum(x["rf"] - x["ra"] for x in games) / len(games)
    return {
        "games": len(games),
        "wins": wins,
        "losses": losses,
        "record": f"{wins}-{losses}",
        "run_diff": float(diff),
    }


@st.cache_data(ttl=900, show_spinner=False)
def _recent_results(day_iso):
    target = date.fromisoformat(str(day_iso))
    end = min(target - timedelta(days=1), datetime.now(ET).date())
    start = end - timedelta(days=38)
    if end < start:
        return {}
    r = requests.get(
        f"{MLB_API}/schedule",
        params={"sportId": 1, "startDate": start.isoformat(), "endDate": end.isoformat()},
        headers=HEADERS,
        timeout=22,
    )
    r.raise_for_status()
    out = {}
    for block in r.json().get("dates", []):
        d = str(block.get("date") or "")
        for game in block.get("games", []):
            if not _is_final(game):
                continue
            for side in ("away", "home"):
                tid = _safe_int((((game.get("teams") or {}).get(side) or {}).get("team") or {}).get("id"))
                if tid is None:
                    continue
                score = _score_for_team(game, tid)
                if not score:
                    continue
                rf, ra, opp = score
                out.setdefault(tid, []).append({"date": d, "game_pk": game.get("gamePk"), "rf": rf, "ra": ra, "opp": opp})
    for tid in out:
        out[tid].sort(key=lambda x: (x.get("date", ""), int(x.get("game_pk") or 0)))
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def _standings(day_iso):
    target = date.fromisoformat(str(day_iso))
    lookup = min(target - timedelta(days=1), datetime.now(ET).date())
    year = lookup.year
    r = requests.get(
        f"{MLB_API}/standings",
        params={
            "leagueId": "103,104",
            "season": year,
            "date": lookup.isoformat(),
            "standingsTypes": "regularSeason",
            "hydrate": "team",
        },
        headers=HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    out = {}
    for record in r.json().get("records", []):
        for team_record in record.get("teamRecords", []):
            team = team_record.get("team") or {}
            tid = _safe_int(team.get("id"))
            if tid is None:
                continue
            try:
                wins = int(team_record.get("wins", 0))
                losses = int(team_record.get("losses", 0))
            except Exception:
                continue
            out[tid] = {
                "wins": wins,
                "losses": losses,
                "record": f"{wins}-{losses}",
                "pct": team_record.get("winningPercentage"),
            }
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def _h2h_one(day_iso, team_id, opponent_id):
    target = date.fromisoformat(str(day_iso))
    end = min(target - timedelta(days=1), datetime.now(ET).date())
    start = end - timedelta(days=1095)
    r = requests.get(
        f"{MLB_API}/schedule",
        params={
            "sportId": 1,
            "teamId": int(team_id),
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        },
        headers=HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    games = []
    for block in r.json().get("dates", []):
        d = str(block.get("date") or "")
        for game in block.get("games", []):
            if not _is_final(game):
                continue
            score = _score_for_team(game, int(team_id))
            if not score:
                continue
            rf, ra, opp = score
            if _safe_int(opp) != int(opponent_id):
                continue
            games.append({"date": d, "game_pk": game.get("gamePk"), "rf": rf, "ra": ra})
    games.sort(key=lambda x: (x.get("date", ""), int(x.get("game_pk") or 0)))
    return _summary(games, 10)


def build_slate_history_context(games_df):
    if games_df is None or getattr(games_df, "empty", True):
        return {}
    rows = [r.to_dict() for _, r in games_df.iterrows()]
    day = str(rows[0].get("game_date") or datetime.now(ET).date().isoformat())

    try:
        recent = _recent_results(day)
    except Exception:
        recent = {}
    try:
        standings = _standings(day)
    except Exception:
        standings = {}

    h2h = {}
    jobs = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for row in rows:
            away_id = _safe_int(row.get("away_team_id"))
            home_id = _safe_int(row.get("home_team_id"))
            pk = _safe_int(row.get("game_pk"))
            if pk is None or away_id is None or home_id is None:
                continue
            jobs.append((pk, away_id, home_id, pool.submit(_h2h_one, day, away_id, home_id)))
        for pk, away_id, home_id, fut in jobs:
            try:
                h2h[pk] = {"away": fut.result(), "away_team_id": away_id, "home_team_id": home_id}
            except Exception:
                h2h[pk] = {"away": {"games": 0, "record": "N/A", "run_diff": None}, "away_team_id": away_id, "home_team_id": home_id}

    out = {}
    for row in rows:
        pk = _safe_int(row.get("game_pk"))
        away_id = _safe_int(row.get("away_team_id"))
        home_id = _safe_int(row.get("home_team_id"))
        if pk is None:
            continue
        away_recent = recent.get(away_id, []) if away_id is not None else []
        home_recent = recent.get(home_id, []) if home_id is not None else []
        h = h2h.get(pk, {}).get("away") or {"games": 0, "record": "N/A", "run_diff": None}
        # Home record is the mirror of the away-perspective H2H record.
        home_h2h = {
            "games": h.get("games", 0),
            "wins": h.get("losses", 0),
            "losses": h.get("wins", 0),
            "record": f"{h.get('losses', 0)}-{h.get('wins', 0)}" if h.get("games") else "N/A",
            "run_diff": (-float(h.get("run_diff"))) if h.get("run_diff") is not None else None,
        }
        out[pk] = {
            "away_record": standings.get(away_id, {}).get("record", "N/A"),
            "home_record": standings.get(home_id, {}).get("record", "N/A"),
            "away_l10": _summary(away_recent, 10),
            "away_l5": _summary(away_recent, 5),
            "home_l10": _summary(home_recent, 10),
            "home_l5": _summary(home_recent, 5),
            "away_h2h": h,
            "home_h2h": home_h2h,
        }
    return out
