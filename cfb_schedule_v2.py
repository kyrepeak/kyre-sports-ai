"""College Football Schedule V2 — mixed-division FBS slate hotfix.

Additive correctness layer over permanently frozen cfb_schedule_v1.

Root cause fixed
----------------
The frozen Step-2 NCAA query is scoped to division 11 (FBS). That can omit
FBS-vs-FCS games from the date-scoped slate because the contest may live under
the FCS side's NCAA schedule feed instead.

V2 preserves the frozen FBS schedule as primary, then:
1. fetches ESPN's FBS-scoped scoreboard (groups=80) for the requested date,
2. fetches NCAA division 12 (FCS) schedule data,
3. keeps only NCAA FCS contests that match an ESPN FBS-scoped event,
4. merges those cross-division contests into the FBS slate,
5. keeps NCAA contest identity whenever the NCAA FCS source is available.

No model/probability/price logic is added here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Mapping

import streamlit as st

import cfb_schedule_v1 as frozen

MODEL_VERSION = "CFB SCHEDULE V2 • MIXED-DIVISION FBS SLATE HOTFIX"
FROZEN_SCHEDULE = "cfb_schedule_v1"

NCAA_FCS_DIVISION = 12
ESPN_FBS_GROUP = 80


def _ncaa_params_for_division(season_year: int, division: int) -> dict[str, str]:
    variables = {
        "sportCode": frozen.NCAA_SPORT_CODE,
        "division": int(division),
        "seasonYear": int(season_year),
    }
    extensions = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": frozen.NCAA_SCHEDULE_HASH,
        }
    }
    return {
        "extensions": json.dumps(extensions, separators=(",", ":")),
        "queryName": frozen.NCAA_SCHEDULE_QUERY_NAME,
        "variables": json.dumps(variables, separators=(",", ":")),
    }


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_ncaa_division_payload(
    season_year: int,
    division: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return frozen._fetch_json_with_fallback(
        frozen.NCAA_SCHEDULE_URL,
        _ncaa_params_for_division(season_year, division),
        f"NCAA official schedule division {int(division)}",
    )


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_espn_fbs_payload(
    requested_day: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return frozen._fetch_json_with_fallback(
        frozen.ESPN_SCOREBOARD_URL,
        {
            "dates": str(requested_day).replace("-", ""),
            "limit": 500,
            "groups": ESPN_FBS_GROUP,
        },
        "ESPN FBS scoreboard supplement",
    )


def _matches_espn_fbs_event(
    game: Mapping[str, Any],
    espn_rows: list[dict[str, Any]],
) -> bool:
    home_keys = frozen._game_name_keys(game, "home")
    away_keys = frozen._game_name_keys(game, "away")
    for row in espn_rows:
        if frozen._names_overlap(home_keys, row.get("home_names") or set()) and frozen._names_overlap(
            away_keys, row.get("away_names") or set()
        ):
            return True
    return False


def _cross_division_games(
    fcs_payload: Mapping[str, Any],
    espn_payload: Mapping[str, Any],
    requested_day: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    fcs_games, fcs_diag = frozen._parse_ncaa_schedule(fcs_payload, requested_day)
    espn_rows = frozen._espn_index(espn_payload, requested_day)

    kept = []
    rejected = 0
    for game in fcs_games:
        if not _matches_espn_fbs_event(game, espn_rows):
            rejected += 1
            continue
        row = dict(game)
        row["schedule_source"] = "NCAA official FCS schedule GraphQL • FBS crossover"
        row["mixed_division_supplement"] = True
        kept.append(row)

    return kept, {
        "fcs_date_games": len(fcs_games),
        "fcs_crossovers_kept": len(kept),
        "fcs_non_fbs_events_rejected": rejected,
        "fcs_raw_contests": int(fcs_diag.get("raw_contests") or 0),
    }


def _merge_primary_and_crossovers(
    primary: list[dict[str, Any]],
    crossovers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    combined = [dict(g) for g in primary] + [dict(g) for g in crossovers]
    deduped, diag = frozen._dedupe_official(combined)
    return deduped, {
        "mixed_division_candidates": len(crossovers),
        "mixed_division_added": max(0, len(deduped) - len(primary)),
        **diag,
    }


@st.cache_data(ttl=120, show_spinner=False)
def load_with_diagnostics(target_date: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested_day = frozen._day(target_date)
    season_year = frozen._season_year(requested_day)

    primary, primary_diag = frozen.load_with_diagnostics(requested_day)
    attempts = list(primary_diag.get("attempts") or [])

    espn_payload, espn_attempts = _fetch_espn_fbs_payload(requested_day)
    attempts.extend(espn_attempts)

    fcs_payload, fcs_attempts = _fetch_ncaa_division_payload(
        season_year,
        NCAA_FCS_DIVISION,
    )
    attempts.extend(fcs_attempts)

    crossovers: list[dict[str, Any]] = []
    crossover_diag = {
        "fcs_date_games": 0,
        "fcs_crossovers_kept": 0,
        "fcs_non_fbs_events_rejected": 0,
        "fcs_raw_contests": 0,
    }
    if fcs_payload and espn_payload:
        crossovers, crossover_diag = _cross_division_games(
            fcs_payload,
            espn_payload,
            requested_day,
        )

    games, merge_diag = _merge_primary_and_crossovers(primary, crossovers)

    # Enrich every merged game from the already-fetched ESPN FBS payload.
    espn_matches = 0
    if games and espn_payload:
        espn_matches = frozen._enrich_with_espn(
            games,
            espn_payload,
            requested_day,
        )

    ready = bool(games) and all(
        bool(g.get("identity_verified") and g.get("date_matches_query"))
        for g in games
    )
    venue_missing = sum(1 for g in games if g.get("venue") == "Venue unavailable")

    diag = {
        **dict(primary_diag),
        "version": MODEL_VERSION,
        "requested_date": requested_day,
        "season_year": season_year,
        "source": "NCAA FBS + verified NCAA FCS crossover supplement" if games else "none",
        "games": len(games),
        "identity_ready": ready,
        "espn_matches": espn_matches,
        "venue_missing": venue_missing,
        "attempts": attempts,
        "primary_fbs_games": len(primary),
        **crossover_diag,
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
        _fetch_ncaa_division_payload,
        _fetch_espn_fbs_payload,
    ):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "ESPN_FBS_GROUP",
    "FROZEN_SCHEDULE",
    "MODEL_VERSION",
    "NCAA_FCS_DIVISION",
    "_cross_division_games",
    "_fetch_espn_fbs_payload",
    "_fetch_ncaa_division_payload",
    "_matches_espn_fbs_event",
    "_merge_primary_and_crossovers",
    "_ncaa_params_for_division",
    "clear_schedule_cache",
    "games_for_date",
    "load_with_diagnostics",
]
