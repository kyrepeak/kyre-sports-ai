"""College Football Schedule V6 — additive FBS + FCS runtime snapshot V2.

Wraps permanently frozen Schedule V5 without editing it. V5 remains the baseline
schedule/enrichment path. V6 adds a second checked-in verified snapshot source
that includes both ESPN FBS and FCS identities so every current NCAAF market row
can receive an official ESPN event ID before the Step 4 market adapter runs.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping

import requests
import streamlit as st

import cfb_over_under_runtime_team_data_v1 as runtime_data
import cfb_schedule_v5_runtime_snapshot as frozen

MODEL_VERSION = "CFB SCHEDULE V6 • FBS + FCS RUNTIME SNAPSHOT V2"
FROZEN_SCHEDULE = "cfb_schedule_v5_runtime_snapshot"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "cfb_runtime_snapshot_v2.json"
REMOTE_SNAPSHOT_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    "cfb-runtime-snapshot-auto-refresh-v2/data/cfb_runtime_snapshot_v2.json"
)
REMOTE_SNAPSHOT_TIMEOUT_SECONDS = 5.0


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _validated_v2_snapshot(
    payload: Any,
    *,
    source: str,
) -> dict[str, Any] | None:
    """Accept only complete, unambiguous official-identity Snapshot V2 payloads."""
    if not isinstance(payload, dict):
        return None
    if int(payload.get("version") or 0) != 2:
        return None

    games = payload.get("games")
    if not isinstance(games, list) or not games:
        return None

    seen_event_ids: set[str] = set()
    for row in games:
        if not isinstance(row, Mapping):
            return None
        event_id = _clean(row.get("event_id"))
        game_date = _clean(row.get("game_date"))[:10]
        away_team = _clean(row.get("away_team"))
        home_team = _clean(row.get("home_team"))
        away_side = row.get("away") if isinstance(row.get("away"), Mapping) else {}
        home_side = row.get("home") if isinstance(row.get("home"), Mapping) else {}
        away_team_id = _clean(away_side.get("team_id"))
        home_team_id = _clean(home_side.get("team_id"))

        if not all(
            (
                event_id,
                game_date,
                away_team,
                home_team,
                away_team_id,
                home_team_id,
            )
        ):
            return None
        if event_id in seen_event_ids:
            return None
        seen_event_ids.add(event_id)

    out = dict(payload)
    out["_runtime_snapshot_source"] = source
    return out


@st.cache_data(ttl=90, show_spinner=False)
def _load_v2_snapshot() -> dict[str, Any]:
    """Prefer the certified runtime-data branch; fail closed to main's snapshot."""
    try:
        response = requests.get(
            REMOTE_SNAPSHOT_URL,
            timeout=REMOTE_SNAPSHOT_TIMEOUT_SECONDS,
            headers={
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "User-Agent": "KyreSportsAI-CFB-ScheduleV6/1.0",
            },
        )
        response.raise_for_status()
        remote = _validated_v2_snapshot(
            response.json(),
            source="certified-runtime-branch",
        )
        if remote is not None:
            return remote
    except Exception:
        pass

    try:
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "version": 2,
            "games": [],
            "_runtime_snapshot_source": "unavailable",
        }

    local = _validated_v2_snapshot(
        payload,
        source="checked-in-main-fallback",
    )
    if local is not None:
        return local
    return {
        "version": 2,
        "games": [],
        "_runtime_snapshot_source": "unavailable",
    }


def _slug(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _snapshot_seed_games(target_date: Any) -> list[dict[str, Any]]:
    """Seed verified ESPN identities only when the frozen schedule is empty."""
    day = _clean(target_date)[:10]
    if not day:
        return []

    payload = _load_v2_snapshot()
    seeds: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()

    for row in payload.get("games") or []:
        if not isinstance(row, Mapping):
            continue
        if _clean(row.get("game_date")) != day:
            continue

        event_id = _clean(row.get("event_id"))
        away_team = _clean(row.get("away_team"))
        home_team = _clean(row.get("home_team"))
        away_side = row.get("away") if isinstance(row.get("away"), Mapping) else {}
        home_side = row.get("home") if isinstance(row.get("home"), Mapping) else {}
        away_team_id = _clean(away_side.get("team_id"))
        home_team_id = _clean(home_side.get("team_id"))

        # Snapshot V2 is allowed to seed only complete, official ESPN identity.
        # Any duplicate/ambiguous official event ID fails closed.
        if not all(
            (
                event_id,
                away_team,
                home_team,
                away_team_id,
                home_team_id,
            )
        ):
            continue
        if event_id in seen_event_ids:
            return []
        seen_event_ids.add(event_id)

        seeds.append(
            {
                "game_id": event_id,
                "identity_key": f"espn:{event_id}",
                "identity_fingerprint": f"espn:{event_id}",
                "game_date": day,
                "kickoff_et": "TBD",
                "kickoff_iso": "",
                "away_team": away_team,
                "away_team_slug": _slug(away_team),
                "away_conference": "Conference unavailable",
                "away_rank": away_side.get("ap_rank"),
                "away_record_summary": _clean(away_side.get("record_text")),
                "home_team": home_team,
                "home_team_slug": _slug(home_team),
                "home_conference": "Conference unavailable",
                "home_rank": home_side.get("ap_rank"),
                "home_record_summary": _clean(home_side.get("record_text")),
                "venue": _clean(row.get("venue")) or "Venue unavailable",
                "status": _clean(row.get("status")) or "Status unavailable",
                "broadcast": _clean(row.get("broadcast")) or "Broadcast unavailable",
                "neutral_site": row.get("neutral_site") is True,
                "ncaa_url": "",
                "espn_event_id": event_id,
                "away_espn_team_id": away_team_id,
                "home_espn_team_id": home_team_id,
                "schedule_source": (
                    "Verified runtime snapshot V2 • ESPN official event identity seed"
                ),
                "enrichment_source": (
                    "Verified runtime snapshot V2 • ESPN FBS + FCS identity"
                ),
                "identity_verified": True,
                "date_matches_query": True,
                "identity_provider": "ESPN",
                "schedule_v6_runtime_snapshot_v2_seeded": True,
            }
        )

    seeds.sort(key=lambda game: _clean(game.get("espn_event_id")))
    return seeds


def _find_v2_snapshot(game: Mapping[str, Any]) -> dict[str, Any]:
    payload = _load_v2_snapshot()
    rows = [
        row for row in (payload.get("games") or [])
        if isinstance(row, Mapping)
    ]

    event_id = _clean(game.get("espn_event_id"))
    if event_id:
        exact = [
            row for row in rows
            if _clean(row.get("event_id")) == event_id
        ]
        return dict(exact[0]) if len(exact) == 1 else {}

    # If V5 already recovered team IDs but not the event ID, use the exact
    # away/home ESPN team-ID pair before falling back to deterministic names.
    away_team_id = _clean(game.get("away_espn_team_id"))
    home_team_id = _clean(game.get("home_espn_team_id"))
    day = _clean(game.get("game_date"))
    if away_team_id and home_team_id and day:
        exact_team_ids: list[Mapping[str, Any]] = []
        for row in rows:
            if _clean(row.get("game_date")) != day:
                continue
            away_side = row.get("away") if isinstance(row.get("away"), Mapping) else {}
            home_side = row.get("home") if isinstance(row.get("home"), Mapping) else {}
            if (
                _clean(away_side.get("team_id")) == away_team_id
                and _clean(home_side.get("team_id")) == home_team_id
            ):
                exact_team_ids.append(row)
        if len(exact_team_ids) == 1:
            return dict(exact_team_ids[0])
        if len(exact_team_ids) > 1:
            return {}

    if not day:
        return {}

    away = runtime_data._key(game.get("away_team"))
    home = runtime_data._key(game.get("home_team"))
    candidates = [
        row for row in rows
        if (
            _clean(row.get("game_date")) == day
            and runtime_data._key(row.get("away_team")) == away
            and runtime_data._key(row.get("home_team")) == home
        )
    ]
    # Fail closed on an alias collision rather than attaching the wrong event ID.
    return dict(candidates[0]) if len(candidates) == 1 else {}


@st.cache_data(ttl=90, show_spinner=False)
def load_with_diagnostics(
    target_date: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    games, diag = frozen.load_with_diagnostics(target_date)
    out = [dict(game) for game in games]

    snapshot_payload = _load_v2_snapshot()
    snapshot_source = _clean(
        snapshot_payload.get("_runtime_snapshot_source")
    ) or "unknown"

    v2_matches = 0
    official_ids_before = sum(
        bool(_clean(game.get("espn_event_id"))) for game in out
    )
    v2_seeded_games = 0

    # Small additive fallback only: Snapshot V2 may seed the requested date
    # when frozen Schedule V5 returned nothing. A non-empty V5 slate is never
    # supplemented or replaced here.
    if not out:
        out = _snapshot_seed_games(target_date)
        v2_seeded_games = len(out)

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
            "games": len(out),
            "identity_ready": bool(out) and all(
                bool(
                    game.get("identity_verified")
                    and game.get("date_matches_query")
                )
                for game in out
            ),
            "espn_matches": max(
                int(diag.get("espn_matches") or 0),
                int(v2_matches),
            ),
            "runtime_snapshot_v2_matches": int(v2_matches),
            "runtime_snapshot_v2_seeded_games": int(v2_seeded_games),
            "runtime_snapshot_v2_seed_fallback_active": bool(v2_seeded_games),
            "official_ids_before_v2": int(official_ids_before),
            "official_ids_after_v2": int(official_ids_after),
            "venue_missing": int(venue_missing),
            "broadcast_missing": int(broadcast_missing),
            "runtime_snapshot_v2_active": True,
            "runtime_snapshot_v2_source": snapshot_source,
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
    "REMOTE_SNAPSHOT_URL",
    "SNAPSHOT_PATH",
    "_validated_v2_snapshot",
    "_find_v2_snapshot",
    "_snapshot_seed_games",
    "clear_schedule_cache",
    "games_for_date",
    "load_with_diagnostics",
]
