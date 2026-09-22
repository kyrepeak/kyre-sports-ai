"""WNBA PRA V3.5.3 — Step-6 empirical variance repair.

PRA-only hotfix. The current player-pool layer can rebuild season/L10/L5 production
from ESPN game summaries when WNBA Stats is unavailable, but the older Step-6
variance path still calls the legacy WNBA-Stats ``player_game_log`` by player id.
That mismatch can surface valid players as ``FALLBACK • 0 GP`` even though the
same verified ESPN game summaries already contain their prior game history.

This module changes only the empirical-history handoff used by Step 6:
- keep the existing player-id profile when it is healthy;
- otherwise reuse the already-tested V3.1.1 ESPN profile builder;
- only completed games strictly before the selected slate date are eligible;
- require >=5 verified games before labeling a variance estimate EMPIRICAL;
- preserve the exact V2.9 PRA-SD math, role scaling and quality formula;
- leave projection means, injuries/minutes/usage, matchup adjustments,
  SportsGameOdds/no-vig/EV, 5M/10M Monte Carlo and finalization rules unchanged.

The V3.1.1 Monte Carlo engine already uses this ESPN fallback for covariance, so
this repair also makes the Preliminary PRA board and production Monte Carlo use a
consistent historical sample instead of displaying a misleading 0-game fallback.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import wnba_pra_market_v29 as step6
import wnba_pra_monte_carlo_v311 as monte

MODEL_VERSION = "PRA V3.5.3 • EMPIRICAL VARIANCE REPAIR"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _profile(proj_row):
    """Resolve the same verified empirical profile used by production MC."""
    try:
        profile = monte._profile_for_projection(proj_row) or {}
    except Exception:
        profile = {}
    return profile if isinstance(profile, dict) else {}


def _pra_sd_v353(proj_row):
    """V2.9 PRA-SD formula with the V3.1.1 verified ESPN history fallback."""
    profile = _profile(proj_row)

    proj_pts = max(0.0, _num(proj_row.get("PROJ_PTS"), 0.0))
    proj_reb = max(0.0, _num(proj_row.get("PROJ_REB"), 0.0))
    proj_ast = max(0.0, _num(proj_row.get("PROJ_AST"), 0.0))
    proj_pra = max(0.0, proj_pts + proj_reb + proj_ast)

    games = int(profile.get("games") or 0)
    if games >= 5:
        sp = max(1.0, _num(profile.get("sd_pts"), 1.0))
        sr = max(0.7, _num(profile.get("sd_reb"), 0.7))
        sa = max(0.7, _num(profile.get("sd_ast"), 0.7))
        cpr = float(np.clip(_num(profile.get("corr_pr"), 0.0), -0.75, 0.75))
        cpa = float(np.clip(_num(profile.get("corr_pa"), 0.0), -0.75, 0.75))
        cra = float(np.clip(_num(profile.get("corr_ra"), 0.0), -0.75, 0.75))

        var = (
            sp * sp + sr * sr + sa * sa
            + 2.0 * cpr * sp * sr
            + 2.0 * cpa * sp * sa
            + 2.0 * cra * sr * sa
        )
        hist_pra = max(1.0, _num(profile.get("pra"), proj_pra or 1.0))
        role_scale = float(np.clip((max(proj_pra, 1.0) / hist_pra) ** 0.25, 0.82, 1.20))
        sd = max(2.2, math.sqrt(max(var, 1.0)) * role_scale)
        quality = min(1.0, 0.55 + min(games, 30) / 30.0 * 0.35)

        source = str(profile.get("source") or "verified empirical game log")
        label = "EMPIRICAL ESPN" if "ESPN" in source.upper() else "EMPIRICAL"
        return sd, games, quality, label

    # Preserve the exact existing Step-6 fallback for true small/no-sample cases.
    sp = max(2.4, math.sqrt(max(proj_pts, 1.0)) * 1.20)
    sr = max(1.5, math.sqrt(max(proj_reb, 1.0)) * 1.10)
    sa = max(1.3, math.sqrt(max(proj_ast, 1.0)) * 1.12)
    sd = max(2.8, math.sqrt(sp * sp + sr * sr + sa * sa))
    return sd, games, 0.48, "FALLBACK"


def install():
    """Install once into the Step-6 module; no other model function is replaced."""
    if getattr(step6, "_v353_empirical_variance_installed", False):
        return
    step6._pra_sd = _pra_sd_v353
    step6._v353_empirical_variance_installed = True


def clear_cache():
    """Clear only empirical-history caches when a manual PRA recheck requests it."""
    try:
        monte._espn_profile.clear()
    except Exception:
        pass
    try:
        step6._empirical_for_player.clear()
    except Exception:
        pass


__all__ = ["MODEL_VERSION", "install", "clear_cache"]
