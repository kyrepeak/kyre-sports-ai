"""College Football Schedule V5 — runtime snapshot fallback.

Additive wrapper over permanently frozen Schedule V4.

If the deployed Streamlit runtime cannot reach the live ESPN enrichment path,
V5 fills the same verified event metadata from the checked-in runtime snapshot.
This makes schedule diagnostics and visible venue/broadcast/record/rank fields
consistent with the central team-data adapter.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import cfb_over_under_runtime_team_data_v1 as runtime_data
import cfb_schedule_v4 as frozen

MODEL_VERSION = "CFB SCHEDULE V5 • RUNTIME SNAPSHOT FALLBACK"
FROZEN_SCHEDULE = "cfb_schedule_v4"


def _clean(value: Any) -> str:
    return str(value or "").strip()


@st.cache_data(ttl=90, show_spinner=False)
def load_with_diagnostics(
    target_date: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    games, diag = frozen.load_with_diagnostics(target_date)
    out = [dict(game) for game in games]

    snapshot_matches = 0
    for game in out:
        snap = runtime_data._find_snapshot(game)
        if not snap:
            continue
        runtime_data._merge_game_snapshot(game, snap)
        game["schedule_v5_runtime_snapshot_enriched"] = True
        game["enrichment_source"] = (
            "Verified runtime snapshot • ESPN/official-source bootstrap"
        )
        snapshot_matches += 1

    venue_missing = sum(
        1 for game in out
        if _clean(game.get("venue")) in {"", "Venue unavailable"}
    )
    broadcast_missing = sum(
        1 for game in out
        if _clean(game.get("broadcast")) in {"", "Broadcast unavailable"}
    )

    result_diag = dict(diag)
    result_diag.update({
        "version": MODEL_VERSION,
        "runtime_snapshot_matches": int(snapshot_matches),
        "espn_matches": max(
            int(diag.get("espn_matches") or 0),
            int(snapshot_matches),
        ),
        "venue_missing": int(venue_missing),
        "broadcast_missing": int(broadcast_missing),
        "runtime_snapshot_fallback_active": True,
    })
    return out, result_diag


@st.cache_data(ttl=90, show_spinner=False)
def games_for_date(target_date: Any) -> list[dict[str, Any]]:
    games, _ = load_with_diagnostics(target_date)
    return games


def clear_schedule_cache() -> None:
    for fn in (load_with_diagnostics, games_for_date):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        frozen.clear_schedule_cache()
    except Exception:
        pass


__all__ = [
    "FROZEN_SCHEDULE",
    "MODEL_VERSION",
    "clear_schedule_cache",
    "games_for_date",
    "load_with_diagnostics",
]
