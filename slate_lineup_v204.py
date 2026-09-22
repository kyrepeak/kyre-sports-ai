"""Slate V20.4 lineup + pitcher enrichment.

Uses official MLB game feeds for confirmed batting orders. When a future game's
lineup has not been posted yet, it falls back to each team's most recent
completed official batting order and labels it PROJECTED. Pitcher season ERA,
WHIP, K/9 and handedness are fetched from the MLB Stats API.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import requests
import streamlit as st

from engine import ET, LIVE_API, MLB_API, ipfloat, season, sf


HEADERS = {"User-Agent": "KyreSportsAI/1.0"}


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return None


def _stat_avg(b):
    value = (b or {}).get("avg")
    if value not in (None, ""):
        return str(value)
    hits = sf((b or {}).get("hits"), 0) or 0
    ab = sf((b or {}).get("atBats"), 0) or 0
    return f"{hits / ab:.3f}" if ab else ".000"


def _parse_lineups(payload):
    teams = (((payload or {}).get("liveData") or {}).get("boxscore") or {}).get("teams") or {}
    out = {"away": [], "home": []}
    for side in ("away", "home"):
        block = teams.get(side) or {}
        players = block.get("players") or {}
        order = []
        for raw in block.get("battingOrder") or []:
            pid = _safe_int(raw)
            if pid is not None:
                order.append(pid)
        arr = []
        for spot, pid in enumerate(order, 1):
            p = players.get(f"ID{pid}") or {}
            person = p.get("person") or {}
            batting = ((p.get("seasonStats") or {}).get("batting") or {})
            arr.append({
                "player_id": pid,
                "player_name": person.get("fullName") or f"Player {pid}",
                "spot": spot,
                "avg": _stat_avg(batting),
                "ops": batting.get("ops") or "—",
                "hits": batting.get("hits", 0),
                "at_bats": batting.get("atBats", 0),
            })
        out[side] = arr
    return out


@st.cache_data(ttl=150, show_spinner=False)
def _fetch_game_feed(game_pk):
    r = requests.get(f"{LIVE_API}/game/{int(game_pk)}/feed/live", headers=HEADERS, timeout=16)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_lineups_bulk(game_pks):
    pks = tuple(sorted({int(x) for x in game_pks if x is not None}))
    if not pks:
        return {}

    def work(pk):
        try:
            return pk, _parse_lineups(_fetch_game_feed(pk))
        except Exception:
            return pk, {"away": [], "home": []}

    out = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(work, pk) for pk in pks]
        for fut in as_completed(futures):
            pk, lineups = fut.result()
            out[int(pk)] = lineups
    return out


@st.cache_data(ttl=900, show_spinner=False)
def _recent_team_games(day_iso, team_ids):
    """Map each team to its most recent completed game before the selected day."""
    target = date.fromisoformat(str(day_iso))
    start = target - timedelta(days=16)
    end = target - timedelta(days=1)
    if end < start:
        return {}

    r = requests.get(
        f"{MLB_API}/schedule",
        params={
            "sportId": 1,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        },
        headers=HEADERS,
        timeout=18,
    )
    r.raise_for_status()

    wanted = {int(x) for x in team_ids if x is not None}
    latest = {}
    for block in r.json().get("dates", []):
        d = str(block.get("date") or "")
        for g in block.get("games", []):
            status = str((g.get("status") or {}).get("detailedState") or "").lower()
            if "final" not in status and "game over" not in status:
                continue
            pk = _safe_int(g.get("gamePk"))
            teams = g.get("teams") or {}
            for side in ("away", "home"):
                tid = _safe_int(((teams.get(side) or {}).get("team") or {}).get("id"))
                if tid not in wanted or pk is None:
                    continue
                prev = latest.get(tid)
                if prev is None or d >= prev.get("date", ""):
                    latest[tid] = {"game_pk": pk, "side": side, "date": d}
    return latest


@st.cache_data(ttl=900, show_spinner=False)
def _pitcher_stats_bulk(pitcher_ids):
    ids = tuple(sorted({int(x) for x in pitcher_ids if x is not None}))
    if not ids:
        return {}

    def work(pid):
        try:
            person_r = requests.get(f"{MLB_API}/people/{pid}", headers=HEADERS, timeout=14)
            person_r.raise_for_status()
            person = (person_r.json().get("people") or [{}])[0]

            stats_r = requests.get(
                f"{MLB_API}/people/{pid}/stats",
                params={"stats": "season", "group": "pitching", "season": season()},
                headers=HEADERS,
                timeout=14,
            )
            stats_r.raise_for_status()
            groups = stats_r.json().get("stats") or []
            s = groups[0]["splits"][0].get("stat", {}) if groups and groups[0].get("splits") else {}
            innings = s.get("inningsPitched", "0.0")
            ip = ipfloat(innings)
            k = sf(s.get("strikeOuts"), 0) or 0
            return pid, {
                "id": pid,
                "name": person.get("fullName") or "Unknown",
                "hand": (person.get("pitchHand") or {}).get("code") or "?",
                "era": s.get("era") or "—",
                "whip": s.get("whip") or "—",
                "k9": (k * 9 / ip) if ip else None,
                "innings": innings,
                "wins": s.get("wins", 0),
                "losses": s.get("losses", 0),
            }
        except Exception:
            return pid, None

    out = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(work, pid) for pid in ids]
        for fut in as_completed(futures):
            pid, stats = fut.result()
            if stats:
                out[int(pid)] = stats
    return out


def build_slate_player_context(games_df):
    if games_df is None or getattr(games_df, "empty", True):
        return {}

    rows = [r.to_dict() for _, r in games_df.iterrows()]
    day = str(rows[0].get("game_date") or datetime.now(ET).date().isoformat())

    game_pks = []
    team_ids = []
    pitcher_ids = []
    for row in rows:
        pk = _safe_int(row.get("game_pk"))
        if pk is not None:
            game_pks.append(pk)
        for key in ("away_team_id", "home_team_id"):
            tid = _safe_int(row.get(key))
            if tid is not None:
                team_ids.append(tid)
        for key in ("away_pitcher_id", "home_pitcher_id"):
            pid = _safe_int(row.get(key))
            if pid is not None:
                pitcher_ids.append(pid)

    try:
        recent = _recent_team_games(day, tuple(sorted(set(team_ids))))
    except Exception:
        recent = {}

    prior_pks = [v.get("game_pk") for v in recent.values() if v.get("game_pk") is not None]
    all_pks = tuple(sorted(set(game_pks + prior_pks)))
    lineups = _fetch_lineups_bulk(all_pks)
    pitchers = _pitcher_stats_bulk(tuple(sorted(set(pitcher_ids))))

    context = {}
    for row in rows:
        pk = _safe_int(row.get("game_pk"))
        if pk is None:
            continue
        current = lineups.get(pk) or {"away": [], "home": []}
        item = {}

        for side in ("away", "home"):
            team_id = _safe_int(row.get(f"{side}_team_id"))
            cur = current.get(side) or []
            if cur:
                item[f"{side}_lineup"] = cur
                item[f"{side}_lineup_label"] = "✅ CONFIRMED LINEUP" if len(cur) >= 9 else "🟡 PARTIAL LINEUP"
                item[f"{side}_lineup_confirmed"] = len(cur) >= 9
            else:
                prev = recent.get(team_id) if team_id is not None else None
                projected = []
                if prev:
                    projected = (lineups.get(int(prev["game_pk"])) or {}).get(prev.get("side")) or []
                item[f"{side}_lineup"] = projected
                item[f"{side}_lineup_label"] = "🕒 PROJECTED • LAST OFFICIAL LINEUP" if projected else "🕒 LINEUP NOT POSTED"
                item[f"{side}_lineup_confirmed"] = False

            pid = _safe_int(row.get(f"{side}_pitcher_id"))
            item[f"{side}_pitcher_stats"] = pitchers.get(pid) if pid is not None else None

        context[pk] = item

    return context
