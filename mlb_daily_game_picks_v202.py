"""MLB Daily Game Picks V2.0.2 — strict player-identity firewall.

Preserves V2.0.1 game/team isolation and all production model math. Adds a final,
independent identity check built from the exact matchup's official lineup or active
roster (for hitter markets), probable starters (for Pitcher K), and scheduled teams
(for Moneyline). A candidate that cannot be independently verified as belonging to
that exact game is rejected rather than promoted into Step 5.
"""
from __future__ import annotations

import re
import unicodedata

import mlb_daily_game_picks_v201 as previous
import mlb_daily_game_picks_v200 as core
import mlb_matchup_hub_v10 as matchup

VERSION = "MLB Daily Game Picks V2.0.2 • STRICT PLAYER IDENTITY FIREWALL"

_orig_all_candidates = core._all_candidates


def _norm_name(v):
    s = str(v or "").strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    parts = [p for p in s.split() if p]
    while parts and parts[-1] in {"jr", "sr", "ii", "iii", "iv", "v"}:
        parts.pop()
    return " ".join(parts)


def _hitter_identity_pool(row):
    names = set()
    ids = set()
    try:
        players = matchup._hitters_for_game(row) or []
    except Exception:
        players = []
    for p in players:
        name = _norm_name(p.get("name"))
        if name:
            names.add(name)
        try:
            ids.add(int(p.get("id")))
        except Exception:
            pass
    return names, ids


def _starter_names(row):
    vals = (
        row.get("away_pitcher") or row.get("away_probable_pitcher") or row.get("away_starter"),
        row.get("home_pitcher") or row.get("home_probable_pitcher") or row.get("home_starter"),
    )
    return {_norm_name(v) for v in vals if _norm_name(v) and _norm_name(v) not in {"tbd", "probable starter tbd"}}


def _team_names(row):
    vals = (
        row.get("away_team") or row.get("away_name"),
        row.get("home_team") or row.get("home_name"),
    )
    return {_norm_name(v) for v in vals if _norm_name(v)}


def _identity_ok(row, c, hitter_names, hitter_ids, starter_names, team_names):
    market = str(c.get("market") or "")
    name = _norm_name(c.get("name"))

    if market in {"1+ Hit", "Home Run", "H+R+RBI"}:
        # Prefer player ID when a connector carries it; otherwise verify normalized name.
        pid = c.get("player_id") or c.get("id")
        try:
            if int(pid) in hitter_ids:
                return True
        except Exception:
            pass
        return bool(name) and name in hitter_names

    if market == "Pitcher Strikeouts":
        return bool(name) and name in starter_names

    if market == "Moneyline":
        return bool(name) and name in team_names

    # Run Line / Total are still unconnected in the current production bridge.
    return True


def _all_candidates(row):
    rows = _orig_all_candidates(row) or []
    hitter_names, hitter_ids = _hitter_identity_pool(row)
    starter_names = _starter_names(row)
    team_names = _team_names(row)
    return [
        c for c in rows
        if _identity_ok(row, c, hitter_names, hitter_ids, starter_names, team_names)
    ]


# Patch the V2.0 module global used by its existing Top-3 selector and audit renderer.
core._all_candidates = _all_candidates

render_daily_game_picks = previous.render_daily_game_picks
