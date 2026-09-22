"""MLB Daily Game Picks V1.9.4 — transient Pitcher K retry cleanup.

Preserves Moneyline V1.9.2 and Pitcher K V1.8.2 production math. This bridge only
cleans stale transient network/timeout diagnostics before a resumable Pitcher K
retry so successful retries do not leave misleading old connection errors visible.
The resumable cache still preserves already completed starter profiles.
"""
from __future__ import annotations

import mlb_daily_game_picks_v193 as base
import mlb_daily_game_picks_v182 as pitcher_k

_orig_build = pitcher_k._build


def _is_transient_error(text):
    t = str(text or "").lower()
    return any(x in t for x in (
        "connecttimeout", "connectiontimeout", "connection timed out",
        "readtimeout", "max retries exceeded", "safety limit",
        "temporary failure", "connectionerror",
    ))


def _retry_clean_build(games, previous=None):
    cleaned = previous
    if previous and not previous.get("complete"):
        cleaned = dict(previous)
        cleaned["errors"] = [
            str(e) for e in (previous.get("errors") or [])
            if not _is_transient_error(e)
        ]
    return _orig_build(games, cleaned)


pitcher_k._build = _retry_clean_build

VERSION = "MLB Daily Game Picks V1.9.4 • TRANSIENT PITCHER K RETRY CLEANUP"
render_daily_game_picks = base.render_daily_game_picks
