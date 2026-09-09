"""College Football Schedule V6 — additive FBS + FCS runtime snapshot V2.

Wraps permanently frozen Schedule V5 without editing it. V5 remains the baseline
schedule/enrichment path. V6 adds a second checked-in verified snapshot source
that includes both ESPN FBS and FCS identities so every current NCAAF market row
can receive an official ESPN event ID before the Step 4 market adapter runs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_runtime_team_data_v1 as runtime_data
import cfb_schedule_v5_runtime_snapshot as frozen

MODEL_VERSION = "CFB SCHEDULE V6 • FBS + FCS RUNTIME SNAPSHOT V2"
FROZEN_SCHEDULE = "cfb_schedule_v5_runtime_snapshot"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "cfb_runtime_snapshot_v2.json"


def _clean(value: Any) -> str:
    return str(value or "").strip()


@st.cache_data(ttl=90, show_spinner=False)
def _load_v2_snapshot() -> dict[str, Any]:
    try:
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 2, "games": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("games"), list):
        return {"version": 2, "games": []}
    return payload


def _find_v2_snapshot(game: Mapping[str, Any]) -> dict[str, Any]:
    payload = _load_v2_snapshot()
    event_id = _clean(game.get("espn_event_id"))
    day = _clean(game.get("game_date"))
    away = runtime_data._key(game.get("away_team"))
    home = runtime_data._key(game.get("home_team"))

    for row in payload.get("games") or []:
        if not isinstance(row, Mapping):
            continue
        if event_id and _clean(row.get("event_id")) == event_id:
            return dict(row)
        if (
            day
            and _clean(row.get("game_date")) == day
            and runtime_data._key(row.get("away_team")) == away
            and runtime_data._key(row.get("home_team")) == home
        ):
            return dict(row)
    return {}


@st.cache_data(ttl=90, show_spinner=False)
def load_with_diagnostics(
    target_date: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    games, diag = frozen.load_with_diagnostics(target_date)
    out = [dict(game) for game in games]

    v2_matches = 0
    official_ids_before = sum(bool(_clean(game.get("espn_event_id"))) for game in out)

    for game in out:
        snap = _find_v2_snapshot(game)
        if not snap:
            continue
        runtime_data._merge_game_snapshot(game, snap)
        game["schedule_v6_runtime_snapshot_v2_enriched"] = True
        game["enrichment_source"] = (
            "Verified runtime snapshot V2 • ESPN FBS + FCS identity"
        )
        v2_matches += 1

    official_ids_after = sum(bool(_clean(game.get("espn_event_id"))) for game in out)
    venue_missing = sum(
        1 for game in out
        if _clean(game.get("venue")) in {"", "Venue unavailable"}
    )
    broadcast_missing = sum(
        1 for game in out
        if _clean(game.get("broadcast")) in {"", "Broadcast unavailable"}
    )

    result_diag = dict(diag)
    result_diag.update(
        {
            "version": MODEL_VERSION,
            "runtime_snapshot_v2_matches": int(v2_matches),
            "official_ids_before_v2": int(official_ids_before),
            "official_ids_after_v2": int(official_ids_after),
            "venue_missing": int(venue_missing),
            "broadcast_missing": int(broadcast_missing),
            "runtime_snapshot_v2_active": True,
            "fuzzy_matching": False,
            "synthetic_ids": False,
        }
    )
    return out, result_diag


@st.cache_data(ttl=90, show_spinner=False)
def games_for_date(target_date: Any) -> list[dict[str, Any]]:
    games, _ = load_with_diagnostics(target_date)
    return games


def clear_schedule_cache() -> None:
    for fn in (load_with_diagnostics, games_for_date, _load_v2_snapshot):
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
    "SNAPSHOT_PATH",
    "_find_v2_snapshot",
    "clear_schedule_cache",
    "games_for_date",
    "load_with_diagnostics",
]
