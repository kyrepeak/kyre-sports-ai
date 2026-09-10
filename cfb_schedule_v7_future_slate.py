"""College Football Schedule V7 — official future-slate identity recovery.

Additive wrapper over frozen Schedule V6. V7 repairs and supplements schedule
identity using only official ESPN-backed snapshots that are already published by
this repository. It never changes projection math, never synthesizes event IDs,
and never performs fuzzy matching.

Match order is intentionally strict:
1. exact official ESPN event ID;
2. exact away/home ESPN team-ID pair + date;
3. exact deterministic team aliases + date, only when unique.

The only alias normalization added here is deterministic text cleanup plus a
terminal ``St.``/``St`` -> ``State`` equivalence (for example Norfolk St. ->
Norfolk State). Collisions fail closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping

import requests
import streamlit as st

import cfb_over_under_runtime_team_data_v1 as runtime_data
import cfb_schedule_v6_runtime_snapshot as frozen

MODEL_VERSION = "CFB SCHEDULE V7 • OFFICIAL FUTURE SLATE COVERAGE"
FROZEN_SCHEDULE = "cfb_schedule_v6_runtime_snapshot"
MARKET_PROJECTION_WEIGHT = 0.0

MARKET_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "data" / "cfb_market_identity_snapshot_v1.json"
)
REMOTE_MARKET_SNAPSHOT_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    "cfb-market-identity-auto-refresh-v1/data/cfb_market_identity_snapshot_v1.json"
)
REMOTE_SNAPSHOT_TIMEOUT_SECONDS = 5.0

_UNAVAILABLE = {
    "",
    "venue unavailable",
    "broadcast unavailable",
    "status unavailable",
    "conference unavailable",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: Any) -> str:
    text = _clean(value).lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _canonical_team(value: Any) -> str:
    """Return a deterministic alias key; this is not fuzzy matching."""
    text = _clean(value).casefold().replace("&", " and ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    tokens = [token for token in text.split() if token]
    if tokens and tokens[-1] == "st":
        tokens[-1] = "state"
    return " ".join(tokens)


def _market_snapshot_valid(payload: Any, *, source: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    games = payload.get("games")
    if not isinstance(games, list) or not games:
        return None

    seen: set[str] = set()
    for row in games:
        if not isinstance(row, Mapping):
            return None
        event_id = _clean(row.get("event_id"))
        day = _clean(row.get("game_date"))[:10]
        away = _clean(row.get("away_team"))
        home = _clean(row.get("home_team"))
        away_id = _clean(row.get("away_team_id"))
        home_id = _clean(row.get("home_team_id"))
        if not all((event_id, day, away, home, away_id, home_id)):
            return None
        if not event_id.isdigit() or event_id in seen:
            return None
        seen.add(event_id)

    out = dict(payload)
    out["_future_slate_snapshot_source"] = source
    return out


@st.cache_data(ttl=90, show_spinner=False)
def _load_market_snapshot() -> dict[str, Any]:
    """Prefer the live market-horizon identity branch; fail closed locally."""
    try:
        response = requests.get(
            REMOTE_MARKET_SNAPSHOT_URL,
            timeout=REMOTE_SNAPSHOT_TIMEOUT_SECONDS,
            headers={
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "User-Agent": "KyreSportsAI-CFB-ScheduleV7/1.0",
            },
        )
        response.raise_for_status()
        remote = _market_snapshot_valid(
            response.json(),
            source="certified-market-identity-branch",
        )
        if remote is not None:
            return remote
    except Exception:
        pass

    try:
        payload = json.loads(MARKET_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"games": [], "_future_slate_snapshot_source": "unavailable"}

    local = _market_snapshot_valid(
        payload,
        source="checked-in-main-fallback",
    )
    if local is not None:
        return local
    return {"games": [], "_future_slate_snapshot_source": "unavailable"}


def _runtime_rows_for_date(day: str) -> list[dict[str, Any]]:
    payload = frozen._load_v2_snapshot()
    return [
        dict(row)
        for row in (payload.get("games") or [])
        if isinstance(row, Mapping) and _clean(row.get("game_date"))[:10] == day
    ]


def _market_rows_for_date(day: str) -> list[dict[str, Any]]:
    payload = _load_market_snapshot()
    return [
        dict(row)
        for row in (payload.get("games") or [])
        if isinstance(row, Mapping) and _clean(row.get("game_date"))[:10] == day
    ]


def _official_rows_for_date(day: str) -> list[dict[str, Any]]:
    """Combine official snapshots by ESPN event ID, preferring richer runtime rows."""
    by_id: dict[str, dict[str, Any]] = {}
    for source_name, rows in (
        ("market_identity_v1", _market_rows_for_date(day)),
        ("runtime_snapshot_v2", _runtime_rows_for_date(day)),
    ):
        for raw in rows:
            event_id = _clean(raw.get("event_id"))
            if not event_id or not event_id.isdigit():
                continue
            row = dict(raw)
            row["_official_snapshot_kind"] = source_name
            by_id[event_id] = row
    return sorted(by_id.values(), key=lambda row: _clean(row.get("event_id")))


def _row_team_ids(row: Mapping[str, Any]) -> tuple[str, str]:
    away_side = row.get("away") if isinstance(row.get("away"), Mapping) else {}
    home_side = row.get("home") if isinstance(row.get("home"), Mapping) else {}
    away_id = _clean(row.get("away_team_id") or away_side.get("team_id"))
    home_id = _clean(row.get("home_team_id") or home_side.get("team_id"))
    return away_id, home_id


def _unique_official_match(
    game: Mapping[str, Any],
    official_rows: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], str]:
    """Resolve exactly one official row or fail closed."""
    event_id = _clean(game.get("espn_event_id"))
    if event_id:
        exact = [row for row in official_rows if _clean(row.get("event_id")) == event_id]
        return (dict(exact[0]), "event_id") if len(exact) == 1 else ({}, "collision")

    day = _clean(game.get("game_date"))[:10]
    away_id = _clean(game.get("away_espn_team_id"))
    home_id = _clean(game.get("home_espn_team_id"))
    if day and away_id and home_id:
        exact_ids = []
        for row in official_rows:
            row_away_id, row_home_id = _row_team_ids(row)
            if (
                _clean(row.get("game_date"))[:10] == day
                and row_away_id == away_id
                and row_home_id == home_id
            ):
                exact_ids.append(row)
        if len(exact_ids) == 1:
            return dict(exact_ids[0]), "team_ids"
        if len(exact_ids) > 1:
            return {}, "collision"

    away = _canonical_team(game.get("away_team"))
    home = _canonical_team(game.get("home_team"))
    if not day or not away or not home:
        return {}, "none"

    aliases = [
        row
        for row in official_rows
        if (
            _clean(row.get("game_date"))[:10] == day
            and _canonical_team(row.get("away_team")) == away
            and _canonical_team(row.get("home_team")) == home
        )
    ]
    if len(aliases) == 1:
        return dict(aliases[0]), "deterministic_alias"
    if len(aliases) > 1:
        return {}, "collision"
    return {}, "none"


def _replace_if_missing(game: dict[str, Any], key: str, value: Any) -> None:
    current = _clean(game.get(key))
    if current.casefold() in _UNAVAILABLE and _clean(value):
        game[key] = value


def _merge_official_row(game: dict[str, Any], row: Mapping[str, Any]) -> None:
    """Merge identity/presentation metadata only; never projection fields."""
    event_id = _clean(row.get("event_id"))
    away_id, home_id = _row_team_ids(row)

    if row.get("_official_snapshot_kind") == "runtime_snapshot_v2":
        runtime_data._merge_game_snapshot(game, row)

    if event_id:
        game["espn_event_id"] = event_id
        game["game_id"] = event_id
        game["identity_key"] = f"espn:{event_id}"
        game["identity_fingerprint"] = f"espn:{event_id}"
    if away_id:
        game["away_espn_team_id"] = away_id
    if home_id:
        game["home_espn_team_id"] = home_id

    _replace_if_missing(game, "venue", row.get("venue"))
    _replace_if_missing(game, "broadcast", row.get("broadcast"))
    _replace_if_missing(game, "status", row.get("status"))

    game["identity_verified"] = bool(event_id and away_id and home_id)
    game["date_matches_query"] = True
    game["identity_provider"] = "ESPN"
    game["schedule_v7_future_slate_enriched"] = True
    game["enrichment_source"] = (
        "Official ESPN-backed future-slate snapshots • exact identity recovery"
    )


def _seed_from_official(row: Mapping[str, Any], day: str) -> dict[str, Any] | None:
    event_id = _clean(row.get("event_id"))
    away_team = _clean(row.get("away_team"))
    home_team = _clean(row.get("home_team"))
    away_id, home_id = _row_team_ids(row)
    if not all((event_id, away_team, home_team, away_id, home_id)):
        return None

    away_side = row.get("away") if isinstance(row.get("away"), Mapping) else {}
    home_side = row.get("home") if isinstance(row.get("home"), Mapping) else {}
    game: dict[str, Any] = {
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
        "away_espn_team_id": away_id,
        "home_espn_team_id": home_id,
        "schedule_source": "Official ESPN-backed future-slate snapshot seed",
        "enrichment_source": "Official ESPN-backed future-slate snapshot seed",
        "identity_verified": True,
        "date_matches_query": True,
        "identity_provider": "ESPN",
        "schedule_v7_future_slate_seeded": True,
    }
    if row.get("_official_snapshot_kind") == "runtime_snapshot_v2":
        runtime_data._merge_game_snapshot(game, row)
    return game


def _sort_key(game: Mapping[str, Any]) -> tuple[str, str, str]:
    kickoff = _clean(game.get("kickoff_iso"))
    return (
        kickoff or "9999-12-31T23:59:59Z",
        _clean(game.get("away_team")),
        _clean(game.get("espn_event_id")),
    )


@st.cache_data(ttl=90, show_spinner=False)
def load_with_diagnostics(
    target_date: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    day = _clean(target_date)[:10]
    games, diag = frozen.load_with_diagnostics(target_date)
    out = [dict(game) for game in games]
    official_rows = _official_rows_for_date(day) if day else []

    ids_before = sum(bool(_clean(game.get("espn_event_id"))) for game in out)
    recovered = 0
    alias_recovered = 0
    collision_count = 0
    matched_event_ids: set[str] = set()

    for game in out:
        match, method = _unique_official_match(game, official_rows)
        if method == "collision":
            collision_count += 1
            continue
        if not match:
            continue
        before_id = _clean(game.get("espn_event_id"))
        _merge_official_row(game, match)
        event_id = _clean(match.get("event_id"))
        if event_id:
            matched_event_ids.add(event_id)
        if not before_id and _clean(game.get("espn_event_id")):
            recovered += 1
        if method == "deterministic_alias":
            alias_recovered += 1

    existing_ids = {
        _clean(game.get("espn_event_id"))
        for game in out
        if _clean(game.get("espn_event_id"))
    }
    supplemented = 0
    for row in official_rows:
        event_id = _clean(row.get("event_id"))
        if not event_id or event_id in existing_ids:
            continue
        seed = _seed_from_official(row, day)
        if seed is None:
            continue
        out.append(seed)
        existing_ids.add(event_id)
        supplemented += 1

    out.sort(key=_sort_key)

    ids_after = sum(bool(_clean(game.get("espn_event_id"))) for game in out)
    venue_missing = sum(
        1 for game in out
        if _clean(game.get("venue")).casefold() in {"", "venue unavailable"}
    )
    broadcast_missing = sum(
        1 for game in out
        if _clean(game.get("broadcast")).casefold() in {"", "broadcast unavailable"}
    )

    market_payload = _load_market_snapshot()
    runtime_payload = frozen._load_v2_snapshot()
    result_diag = dict(diag)
    result_diag.update(
        {
            "version": MODEL_VERSION,
            "games": len(out),
            "identity_ready": bool(out) and all(
                bool(game.get("identity_verified") and game.get("date_matches_query"))
                for game in out
            ),
            "espn_matches": max(
                int(diag.get("espn_matches") or 0),
                sum(bool(game.get("identity_verified")) for game in out),
            ),
            "future_slate_layer": True,
            "future_slate_official_rows": len(official_rows),
            "future_slate_identity_recovered": recovered,
            "future_slate_alias_recovered": alias_recovered,
            "future_slate_supplemented_games": supplemented,
            "future_slate_collision_count": collision_count,
            "official_ids_before_v7": ids_before,
            "official_ids_after_v7": ids_after,
            "venue_missing": venue_missing,
            "broadcast_missing": broadcast_missing,
            "runtime_snapshot_v2_source": _clean(
                runtime_payload.get("_runtime_snapshot_source")
            ) or _clean(diag.get("runtime_snapshot_v2_source")) or "unknown",
            "market_identity_snapshot_source": _clean(
                market_payload.get("_future_slate_snapshot_source")
            ) or "unknown",
            "identity_match_policy": (
                "event_id -> exact team IDs/date -> deterministic exact alias/date; "
                "collisions fail closed"
            ),
            "fuzzy_matching": False,
            "synthetic_ids": False,
            "sportsbook_projection_weight": MARKET_PROJECTION_WEIGHT,
        }
    )
    return out, result_diag


@st.cache_data(ttl=90, show_spinner=False)
def games_for_date(target_date: Any) -> list[dict[str, Any]]:
    games, _ = load_with_diagnostics(target_date)
    return games


def clear_schedule_cache() -> None:
    for fn in (load_with_diagnostics, games_for_date, _load_market_snapshot):
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
    "MARKET_PROJECTION_WEIGHT",
    "MODEL_VERSION",
    "REMOTE_MARKET_SNAPSHOT_URL",
    "_canonical_team",
    "_market_snapshot_valid",
    "_unique_official_match",
    "clear_schedule_cache",
    "games_for_date",
    "load_with_diagnostics",
]
