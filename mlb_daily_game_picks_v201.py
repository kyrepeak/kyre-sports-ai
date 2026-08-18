"""MLB Daily Game Picks V2.0.1 — strict matchup isolation hotfix.

Preserves V2.0 Step 5 scoring/ranking and every production connector. Adds an
independent matchup-team gate on top of game_pk matching so a malformed/shared
upstream hitter game id can never leak a player from another MLB matchup into a
game's Top 3. No probability, reliability, data-quality, or Pick Strength math is
changed.
"""
from __future__ import annotations

import re
import mlb_daily_game_picks_v200 as base

VERSION = "MLB Daily Game Picks V2.0.1 • STRICT MATCHUP ISOLATION"

_orig_direct_candidates = base._direct_candidates
_orig_all_candidates = base._all_candidates

# Canonical MLB team aliases. Values intentionally accept both full names and the
# abbreviations commonly emitted by the production modules.
_TEAM_ALIASES = {
    "ari":"ARI", "arizona diamondbacks":"ARI", "diamondbacks":"ARI",
    "atl":"ATL", "atlanta braves":"ATL", "braves":"ATL",
    "bal":"BAL", "baltimore orioles":"BAL", "orioles":"BAL",
    "bos":"BOS", "boston red sox":"BOS", "red sox":"BOS",
    "chc":"CHC", "chicago cubs":"CHC", "cubs":"CHC",
    "chw":"CWS", "cws":"CWS", "chicago white sox":"CWS", "white sox":"CWS",
    "cin":"CIN", "cincinnati reds":"CIN", "reds":"CIN",
    "cle":"CLE", "cleveland guardians":"CLE", "guardians":"CLE",
    "col":"COL", "colorado rockies":"COL", "rockies":"COL",
    "det":"DET", "detroit tigers":"DET", "tigers":"DET",
    "hou":"HOU", "houston astros":"HOU", "astros":"HOU",
    "kc":"KC", "kcr":"KC", "kansas city royals":"KC", "royals":"KC",
    "laa":"LAA", "los angeles angels":"LAA", "angels":"LAA",
    "lad":"LAD", "los angeles dodgers":"LAD", "dodgers":"LAD",
    "mia":"MIA", "miami marlins":"MIA", "marlins":"MIA",
    "mil":"MIL", "milwaukee brewers":"MIL", "brewers":"MIL",
    "min":"MIN", "minnesota twins":"MIN", "twins":"MIN",
    "nym":"NYM", "new york mets":"NYM", "mets":"NYM",
    "nyy":"NYY", "new york yankees":"NYY", "yankees":"NYY",
    "ath":"ATH", "oak":"ATH", "athletics":"ATH", "oakland athletics":"ATH",
    "phi":"PHI", "philadelphia phillies":"PHI", "phillies":"PHI",
    "pit":"PIT", "pittsburgh pirates":"PIT", "pirates":"PIT",
    "sd":"SD", "sdp":"SD", "san diego padres":"SD", "padres":"SD",
    "sea":"SEA", "seattle mariners":"SEA", "mariners":"SEA",
    "sf":"SF", "sfg":"SF", "san francisco giants":"SF", "giants":"SF",
    "stl":"STL", "st louis cardinals":"STL", "saint louis cardinals":"STL", "cardinals":"STL",
    "tb":"TB", "tbr":"TB", "tampa bay rays":"TB", "rays":"TB",
    "tex":"TEX", "texas rangers":"TEX", "rangers":"TEX",
    "tor":"TOR", "toronto blue jays":"TOR", "blue jays":"TOR",
    "wsh":"WSH", "was":"WSH", "washington nationals":"WSH", "nationals":"WSH",
}


def _norm_text(v):
    s = str(v or "").strip().lower()
    s = s.replace("&", "and").replace("’", "'")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _canon_team(v):
    s = _norm_text(v)
    if not s:
        return ""
    return _TEAM_ALIASES.get(s, s.upper())


def _game_teams(row):
    away = row.get("away_team") or row.get("away_name") or ""
    home = row.get("home_team") or row.get("home_name") or ""
    return {_canon_team(away), _canon_team(home)} - {""}


def _belongs_to_game(row, candidate):
    """Fail closed for player markets when team identity is absent or mismatched."""
    allowed = _game_teams(row)
    if not allowed:
        return False
    market = str(candidate.get("market") or "")
    if market == "Moneyline":
        team = candidate.get("team") or candidate.get("name")
        return _canon_team(team) in allowed
    if market in base._PLAYER_MARKETS:
        team = candidate.get("team")
        # A player candidate without a verifiable team must not be promoted.
        return bool(team) and _canon_team(team) in allowed
    return True


def _direct_candidates(row, market):
    rows = _orig_direct_candidates(row, market) or []
    return [c for c in rows if _belongs_to_game(row, c)]


def _all_candidates(row):
    # Final guard at the aggregate layer as well, including any future direct
    # candidate path that might bypass _direct_candidates.
    rows = _orig_all_candidates(row) or []
    return [c for c in rows if _belongs_to_game(row, c)]


# Patch the V2.0 module globals used by its existing renderer and Top-3 selector.
base._direct_candidates = _direct_candidates
base._all_candidates = _all_candidates

render_daily_game_picks = base.render_daily_game_picks
