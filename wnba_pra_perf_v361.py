"""WNBA PRA V3.6.1 — same-render Step-6 performance cache.

Performance-only patch. No projection formula, sportsbook grading formula,
qualification gate, matchup multiplier, Monte Carlo count, or final-card rule is
changed.

The PRA page historically recalculated the same Step-5 game projection several
times during one Streamlit rerun (integrity preflight, Step 5 UI, Step 6, Step 7,
and downstream checks). It also recalculated the same player's empirical PRA
variance once per sportsbook pair.

V3.6.1 keeps those calculations identical but memoizes them for the duration of a
single page render:
- one Step-5 role/minutes projection per game per render;
- one empirical PRA-SD result per player + exact P/R/A projection signature;
- caches are cleared at the beginning of every PRA render, so injury/lineup/role
  changes are never carried across reruns;
- SportsGameOdds refresh/caching is untouched, so market freshness is unchanged.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_role_v28 as role28
import wnba_role_v282 as role282
import wnba_pra_market_v29 as step6
import wnba_pra_variance_v353 as variance

MODEL_VERSION = "PRA V3.6.1 • SAME-RENDER STEP-6 PERFORMANCE CACHE"

_ROLE_MEMO = {}
_SD_MEMO = {}


def _game_key(game):
    day = st.session_state.get("wnba_pra_v2_date")
    gid = str(game.get("game_id") or "").strip()
    if gid:
        return (str(day or ""), gid)
    return (
        str(day or ""),
        str(game.get("game_date") or ""),
        int(float(game.get("away_team_id") or 0)),
        int(float(game.get("home_team_id") or 0)),
    )


def _clone_role_result(result):
    """Return caller-safe copies while keeping the cached canonical result clean."""
    if not isinstance(result, dict):
        return result
    out = dict(result)
    teams = out.get("teams")
    if isinstance(teams, dict):
        out["teams"] = {
            team_id: frame.copy(deep=True) if isinstance(frame, pd.DataFrame) else frame
            for team_id, frame in teams.items()
        }
    return out


def _projection_signature(proj):
    def num(name):
        try:
            value = float(proj.get(name))
            return round(value, 10) if pd.notna(value) else None
        except Exception:
            return None

    return (
        str(proj.get("game_id") or ""),
        str(proj.get("player_key") or ""),
        str(proj.get("PLAYER_ID") or ""),
        num("PROJ_PTS"),
        num("PROJ_REB"),
        num("PROJ_AST"),
    )


def install():
    """Install idempotent memo wrappers around existing production functions."""
    variance.install()

    if not hasattr(role282, "_v361_original_role_projection_for_game"):
        role282._v361_original_role_projection_for_game = role282.role_projection_for_game

    original_role = role282._v361_original_role_projection_for_game

    def role_projection_for_game_cached(game, stats=None):
        key = _game_key(game)
        if key not in _ROLE_MEMO:
            result = original_role(game, stats)
            _ROLE_MEMO[key] = _clone_role_result(result)
        return _clone_role_result(_ROLE_MEMO[key])

    role282.role_projection_for_game = role_projection_for_game_cached
    role28.role_projection_for_game = role_projection_for_game_cached

    if not hasattr(step6, "_v361_original_pra_sd"):
        step6._v361_original_pra_sd = step6._pra_sd

    original_sd = step6._v361_original_pra_sd

    def pra_sd_cached(proj):
        key = _projection_signature(proj)
        if key not in _SD_MEMO:
            _SD_MEMO[key] = original_sd(proj)
        return _SD_MEMO[key]

    step6._pra_sd = pra_sd_cached
    step6._v361_step6_performance_cache_installed = True


def begin_render():
    """Start a fresh same-render cache epoch and install the wrappers."""
    _ROLE_MEMO.clear()
    _SD_MEMO.clear()
    install()


def cache_stats():
    return {
        "game_projections": int(len(_ROLE_MEMO)),
        "variance_profiles": int(len(_SD_MEMO)),
    }


__all__ = ["MODEL_VERSION", "install", "begin_render", "cache_stats"]
