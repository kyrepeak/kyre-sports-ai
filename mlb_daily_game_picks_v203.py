"""MLB Daily Game Picks V2.0.3 — production-candidate identity firewall.

Preserves V2.0.2 and all production model / Pick Strength math. Moves matchup
identity enforcement to the lowest shared Step-5 candidate function so both the
Top-3 selector and scoring audit receive only candidates independently verified
for that exact MLB matchup.
"""
from __future__ import annotations

import re
import unicodedata

import mlb_daily_game_picks_v202 as previous
import mlb_daily_game_picks_v200 as core
import mlb_matchup_hub_v10 as matchup

VERSION = "MLB Daily Game Picks V2.0.3 • PRODUCTION-CANDIDATE IDENTITY FIREWALL"

_orig_production_candidates = core._production_candidates

_TEAM_IDS = {
    "arizona diamondbacks": 109,
    "atlanta braves": 144,
    "baltimore orioles": 110,
    "boston red sox": 111,
    "chicago cubs": 112,
    "chicago white sox": 145,
    "cincinnati reds": 113,
    "cleveland guardians": 114,
    "colorado rockies": 115,
    "detroit tigers": 116,
    "houston astros": 117,
    "kansas city royals": 118,
    "los angeles angels": 108,
    "los angeles dodgers": 119,
    "miami marlins": 146,
    "milwaukee brewers": 158,
    "minnesota twins": 142,
    "new york mets": 121,
    "new york yankees": 147,
    "athletics": 133,
    "oakland athletics": 133,
    "philadelphia phillies": 143,
    "pittsburgh pirates": 134,
    "san diego padres": 135,
    "san francisco giants": 137,
    "seattle mariners": 136,
    "st louis cardinals": 138,
    "saint louis cardinals": 138,
    "tampa bay rays": 139,
    "texas rangers": 140,
    "toronto blue jays": 141,
    "washington nationals": 120,
}


def _norm(v):
    s = str(v or "").strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    parts = [p for p in s.split() if p]
    while parts and parts[-1] in {"jr", "sr", "ii", "iii", "iv", "v"}:
        parts.pop()
    return " ".join(parts)


def _day(row):
    return str(row.get("game_date") or "")[:10]


def _team_pair(row):
    return (
        _norm(row.get("away_team") or row.get("away_name")),
        _norm(row.get("home_team") or row.get("home_name")),
    )


def _verified_hitter_names(row):
    """Build identity pool independently from displayed matchup team names.

    Prefer the official game boxscore lineup when published. If lineups are still
    pending, use active rosters fetched by canonical MLB team id derived from the
    displayed team names rather than trusting connector game/team metadata.
    """
    names = set()
    game_pk = row.get("game_pk") or row.get("gamePk")
    try:
        game_pk = int(float(game_pk))
    except Exception:
        game_pk = None

    official = []
    if game_pk is not None:
        for side in ("away", "home"):
            try:
                official.extend(matchup._official_hitters(game_pk, side) or [])
            except Exception:
                pass
    if official:
        for p in official:
            n = _norm(p.get("name"))
            if n:
                names.add(n)
        return names

    day = _day(row)
    for team_name in _team_pair(row):
        tid = _TEAM_IDS.get(team_name)
        if not tid:
            continue
        try:
            roster = matchup._active_roster(tid, day) or []
        except Exception:
            roster = []
        for p in roster:
            if str(p.get("position") or "").upper() == "P":
                continue
            n = _norm(p.get("name"))
            if n:
                names.add(n)
    return names


def _starter_names(row):
    vals = (
        row.get("away_pitcher") or row.get("away_probable_pitcher") or row.get("away_starter"),
        row.get("home_pitcher") or row.get("home_probable_pitcher") or row.get("home_starter"),
    )
    return {_norm(v) for v in vals if _norm(v) not in {"", "tbd", "probable starter tbd"}}


def _moneyline_names(row):
    return {x for x in _team_pair(row) if x}


def _identity_filter(row, rows):
    hitter_names = None
    starters = None
    teams = None
    out = []
    for c in rows or []:
        market = str(c.get("market") or "")
        name = _norm(c.get("name"))
        if market in {"1+ Hit", "Home Run", "H+R+RBI"}:
            if hitter_names is None:
                hitter_names = _verified_hitter_names(row)
            if not hitter_names or name not in hitter_names:
                continue
        elif market == "Pitcher Strikeouts":
            if starters is None:
                starters = _starter_names(row)
            if not starters or name not in starters:
                continue
        elif market == "Moneyline":
            if teams is None:
                teams = _moneyline_names(row)
            if not teams or name not in teams:
                continue
        out.append(c)
    return out


def _production_candidates(row, market):
    rows = _orig_production_candidates(row, market) or []
    return _identity_filter(row, rows)


# Lowest shared Step-5 candidate source: Top-3 ranking and audit both pass here.
core._production_candidates = _production_candidates


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Reinstall defensively because V2.0's renderer also patches lower bridge layers.
    core._production_candidates = _production_candidates
    return previous.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
