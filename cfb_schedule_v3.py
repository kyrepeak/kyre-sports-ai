"""College Football Schedule V3 — official NCAA scoreboard completeness hotfix.

Additive correctness layer over permanently frozen cfb_schedule_v2.

Root cause
----------
The older frozen NCAA schedule persisted query can return an empty contest list
for future dates even while NCAA's public FBS scoreboard shows those games.
V3 adds NCAA's current date-scoped scoreboard GraphQL persisted query as the
authoritative completeness layer.

Provider order
--------------
1. NCAA current FBS scoreboard GraphQL (contestDate scoped) — authoritative.
2. Frozen Schedule V2 — preserves prior FBS/FCS crossover and ESPN fallback
   behavior as a secondary supplement.
3. ESPN enrichment remains metadata-only.

No model/probability/price logic is added.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

import streamlit as st

import cfb_schedule_v2 as frozen

MODEL_VERSION = "CFB SCHEDULE V3 • NCAA SCOREBOARD COMPLETENESS HOTFIX"
FROZEN_SCHEDULE = "cfb_schedule_v2"

NCAA_SCOREBOARD_HASH = "7287cda610a9326931931080cb3a604828febe6fe3c9016a7e4a36db99efdb7c"
NCAA_SCOREBOARD_DIVISION = 11


def _scoreboard_params(requested_day: str) -> dict[str, str]:
    day = frozen.frozen._day(requested_day)
    variables = {
        "sportCode": frozen.frozen.NCAA_SPORT_CODE,
        "division": NCAA_SCOREBOARD_DIVISION,
        "seasonYear": frozen.frozen._season_year(day),
        "contestDate": day,
    }
    extensions = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": NCAA_SCOREBOARD_HASH,
        }
    }
    return {
        "extensions": json.dumps(extensions, separators=(",", ":")),
        "variables": json.dumps(variables, separators=(",", ":")),
    }


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_ncaa_scoreboard_payload(
    requested_day: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return frozen.frozen._fetch_json_with_fallback(
        frozen.frozen.NCAA_SCHEDULE_URL,
        _scoreboard_params(requested_day),
        "NCAA current FBS scoreboard GraphQL",
    )


def _official_scoreboard_games(
    payload: Mapping[str, Any],
    requested_day: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    games, diag = frozen.frozen._parse_ncaa_schedule(payload, requested_day)
    out = []
    for game in games:
        row = dict(game)
        row["schedule_source"] = "NCAA current FBS scoreboard GraphQL"
        row["identity_provider"] = "NCAA"
        row["scoreboard_completeness_hotfix"] = True
        out.append(row)
    return out, diag


def _merge_authoritative_scoreboard(
    official: list[dict[str, Any]],
    fallback: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Use the complete NCAA scoreboard when available; otherwise fail over.

    The current NCAA FBS scoreboard already includes FBS-vs-FCS crossover
    contests. Mixing name-based ESPN fallback rows into a non-empty official
    slate can duplicate abbreviations such as "Western Ky." / "Western
    Kentucky", so V3 treats the official date-scoped scoreboard as atomic.
    """
    if official:
        out = [dict(g) for g in official]
        out.sort(key=lambda g: (str(g.get("kickoff_iso")), str(g.get("game_id"))))
        return out, {
            "official_scoreboard_games": len(official),
            "fallback_games_seen": len(fallback),
            "fallback_games_added": 0,
            "fallback_duplicates_suppressed": len(fallback),
            "fallback_mode": 0,
        }

    out = [dict(g) for g in fallback]
    out.sort(key=lambda g: (str(g.get("kickoff_iso")), str(g.get("game_id"))))
    return out, {
        "official_scoreboard_games": 0,
        "fallback_games_seen": len(fallback),
        "fallback_games_added": len(fallback),
        "fallback_duplicates_suppressed": 0,
        "fallback_mode": 1,
    }


@st.cache_data(ttl=120, show_spinner=False)
def load_with_diagnostics(target_date: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested_day = frozen.frozen._day(target_date)

    fallback_games, fallback_diag = frozen.load_with_diagnostics(requested_day)
    attempts = list(fallback_diag.get("attempts") or [])

    payload, scoreboard_attempts = _fetch_ncaa_scoreboard_payload(requested_day)
    attempts.extend(scoreboard_attempts)

    official_games: list[dict[str, Any]] = []
    scoreboard_diag: dict[str, Any] = {
        "raw_contests": 0,
        "date_games": 0,
        "off_date_contests": 0,
        "malformed_contests": 0,
    }
    if payload:
        official_games, scoreboard_diag = _official_scoreboard_games(
            payload,
            requested_day,
        )

    games, merge_diag = _merge_authoritative_scoreboard(
        official_games,
        fallback_games,
    )

    espn_matches = 0
    espn_payload = {}
    if games:
        try:
            espn_payload, espn_attempts = frozen._fetch_espn_fbs_payload(
                requested_day
            )
            attempts.extend(espn_attempts)
        except Exception:
            espn_payload = {}
    if games and espn_payload:
        espn_matches = frozen.frozen._enrich_with_espn(
            games,
            espn_payload,
            requested_day,
        )

    ready = bool(games) and all(
        bool(g.get("identity_verified") and g.get("date_matches_query"))
        for g in games
    )
    venue_missing = sum(
        1 for g in games if g.get("venue") == "Venue unavailable"
    )

    diag = {
        **dict(fallback_diag),
        "version": MODEL_VERSION,
        "requested_date": requested_day,
        "source": (
            "NCAA current FBS scoreboard GraphQL + frozen V2 supplement"
            if games
            else "none"
        ),
        "games": len(games),
        "identity_ready": ready,
        "venue_missing": venue_missing,
        "espn_matches": espn_matches,
        "attempts": attempts,
        "scoreboard_raw_contests": int(
            scoreboard_diag.get("raw_contests") or 0
        ),
        "scoreboard_date_games": int(
            scoreboard_diag.get("date_games") or len(official_games)
        ),
        "scoreboard_off_date_contests": int(
            scoreboard_diag.get("off_date_contests") or 0
        ),
        "scoreboard_malformed_contests": int(
            scoreboard_diag.get("malformed_contests") or 0
        ),
        **merge_diag,
    }
    return games, diag


@st.cache_data(ttl=120, show_spinner=False)
def games_for_date(target_date: Any) -> list[dict[str, Any]]:
    games, _ = load_with_diagnostics(target_date)
    return games


def clear_schedule_cache() -> None:
    for fn in (
        games_for_date,
        load_with_diagnostics,
        _fetch_ncaa_scoreboard_payload,
    ):
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
    "NCAA_SCOREBOARD_DIVISION",
    "NCAA_SCOREBOARD_HASH",
    "_fetch_ncaa_scoreboard_payload",
    "_merge_authoritative_scoreboard",
    "_official_scoreboard_games",
    "_scoreboard_params",
    "clear_schedule_cache",
    "games_for_date",
    "load_with_diagnostics",
]
