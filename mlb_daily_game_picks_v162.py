"""MLB Daily Game Picks V1.6.2 — resilient HR lineup intake.

Preserves the calibrated HR V1.1 model and V1.6.1 resumable profile orchestration.
This patch only hardens the pre-model hitter candidate intake: when actionable
MLB games exist but the shared lineup cache returns zero usable lineups, it clears
only the stale lineup-related cache entries and retries with short backoff.
No probability math or eligibility standard is loosened.
"""
from __future__ import annotations

import time

import mlb_daily_game_picks_v161 as base
import mlb_hr_hub_v10 as hrcore
import slate_lineup_v204 as lineup

VERSION = "MLB Daily Game Picks V1.6.2 • RESILIENT HR LINEUP INTAKE"

_orig_pool = hrcore._candidate_pool
_orig_build = base._build_hr


def _clear_lineup_caches():
    """Clear only lineup-intake caches that can legitimately contain stale empties."""
    for fn_name in ("_fetch_lineups_bulk", "_fetch_game_feed", "_recent_team_games"):
        fn = getattr(lineup, fn_name, None)
        clear = getattr(fn, "clear", None)
        if callable(clear):
            try:
                clear()
            except Exception:
                pass


def _candidate_pool_resilient(games, include_live=False):
    last_meta = {}
    for attempt in range(3):
        candidates, meta = _orig_pool(games, include_live)
        candidates = list(candidates or [])
        meta = dict(meta or {})
        meta["lineup_intake_attempt"] = attempt + 1
        last_meta = meta
        if candidates:
            meta["lineup_context_unavailable"] = False
            return candidates, meta

        checked = int(meta.get("checked", 0) or 0)
        usable = int(meta.get("usable_games", 0) or 0)
        # No actionable games is a real empty slate, not an intake failure.
        if checked == 0:
            return candidates, meta

        # Actionable games but zero usable lineups is the impossible/transient state.
        if usable == 0 and attempt < 2:
            _clear_lineup_caches()
            time.sleep(1.5 * (attempt + 1))
            continue
        break

    last_meta = dict(last_meta or {})
    if int(last_meta.get("checked", 0) or 0) > 0 and int(last_meta.get("usable_games", 0) or 0) == 0:
        last_meta["lineup_context_unavailable"] = True
    return [], last_meta


hrcore._candidate_pool = _candidate_pool_resilient


def _build_hr_resilient(games, previous=None):
    result = _orig_build(games, previous)
    if not result.get("candidate_count"):
        meta = dict(result.get("meta") or {})
        if meta.get("lineup_context_unavailable"):
            result = dict(result)
            result["errors"] = [
                "Home Run lineup context is temporarily unavailable from MLB after 3 verified retries. "
                "No hitter was excluded or fabricated. Retry CONNECT HOME RUN when MLB data responds."
            ]
    return result


base._build_hr = _build_hr_resilient


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    return base.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
