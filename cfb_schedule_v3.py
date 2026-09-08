"""College Football Schedule V3 — full FBS slate completeness fallback.

Additive correctness layer over permanently frozen cfb_schedule_v2.

Why V3 exists
-------------
V2 successfully repaired mixed-division crossover omissions, but the live app
still exposed dates (for example a full Saturday slate) where the ESPN
`groups=80` scoreboard path itself returned no usable events.

V3 keeps every V2 result, then adds a second ESPN path:
1. fetch the ESPN FBS team directory (`groups=80`),
2. fetch the unscoped College Football scoreboard for the requested date,
3. admit only events containing at least one verified FBS team-directory member,
4. merge/dedupe those verified FBS-scoped events into the V2 slate.

This makes the fallback slate-wide instead of matchup-specific while still
excluding pure-FCS events. No model, probability, price, or pick logic lives
here.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import cfb_schedule_v2 as prior

MODEL_VERSION = "CFB SCHEDULE V3 • FULL FBS SLATE FALLBACK"
FROZEN_SCHEDULE = "cfb_schedule_v2"

ESPN_TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/"
    "football/college-football/teams"
)
ESPN_SCOREBOARD_URL = prior.frozen.ESPN_SCOREBOARD_URL
ESPN_FBS_GROUP = prior.ESPN_FBS_GROUP


def _team_key(value: Any) -> str:
    return prior.frozen._name_key(value)


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_espn_fbs_team_directory() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return prior.frozen._fetch_json_with_fallback(
        ESPN_TEAMS_URL,
        {
            "limit": 500,
            "groups": ESPN_FBS_GROUP,
        },
        "ESPN FBS team directory",
    )


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_espn_unscoped_scoreboard(
    requested_day: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return prior.frozen._fetch_json_with_fallback(
        ESPN_SCOREBOARD_URL,
        {
            "dates": str(requested_day).replace("-", ""),
            "limit": 1000,
        },
        "ESPN all-CFB scoreboard fallback",
    )


def _directory_team_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Yield team objects across ESPN's common directory response shapes."""
    rows: list[Mapping[str, Any]] = []

    for item in payload.get("teams") or []:
        if not isinstance(item, Mapping):
            continue
        team = item.get("team") if isinstance(item.get("team"), Mapping) else item
        if isinstance(team, Mapping):
            rows.append(team)

    for sport in payload.get("sports") or []:
        if not isinstance(sport, Mapping):
            continue
        for league in sport.get("leagues") or []:
            if not isinstance(league, Mapping):
                continue
            for item in league.get("teams") or []:
                if not isinstance(item, Mapping):
                    continue
                team = item.get("team") if isinstance(item.get("team"), Mapping) else item
                if isinstance(team, Mapping):
                    rows.append(team)

    return rows


def _fbs_team_index(payload: Mapping[str, Any]) -> dict[str, set[str]]:
    ids: set[str] = set()
    slugs: set[str] = set()
    names: set[str] = set()

    for team in _directory_team_rows(payload):
        team_id = str(team.get("id") or "").strip()
        if team_id:
            ids.add(team_id)

        slug = str(team.get("slug") or "").strip().lower()
        if slug:
            slugs.add(slug)

        for raw in (
            team.get("location"),
            team.get("displayName"),
            team.get("shortDisplayName"),
            team.get("name"),
            team.get("abbreviation"),
        ):
            key = _team_key(raw)
            if key:
                names.add(key)

    return {"ids": ids, "slugs": slugs, "names": names}


def _competitor_is_fbs(
    competitor: Mapping[str, Any],
    index: Mapping[str, set[str]],
) -> bool:
    team = competitor.get("team") or {}
    if not isinstance(team, Mapping):
        return False

    team_id = str(team.get("id") or "").strip()
    if team_id and team_id in (index.get("ids") or set()):
        return True

    slug = str(team.get("slug") or "").strip().lower()
    if slug and slug in (index.get("slugs") or set()):
        return True

    names = index.get("names") or set()
    for raw in (
        team.get("location"),
        team.get("displayName"),
        team.get("shortDisplayName"),
        team.get("name"),
        team.get("abbreviation"),
    ):
        key = _team_key(raw)
        if key and key in names:
            return True

    return False


def _event_has_fbs_member(
    event: Mapping[str, Any],
    index: Mapping[str, set[str]],
) -> bool:
    competitions = event.get("competitions") or []
    if not competitions or not isinstance(competitions[0], Mapping):
        return False
    for competitor in competitions[0].get("competitors") or []:
        if isinstance(competitor, Mapping) and _competitor_is_fbs(competitor, index):
            return True
    return False


def _filter_unscoped_to_fbs(
    scoreboard_payload: Mapping[str, Any],
    fbs_index: Mapping[str, set[str]],
) -> tuple[dict[str, Any], dict[str, int]]:
    events = [
        event
        for event in scoreboard_payload.get("events") or []
        if isinstance(event, Mapping)
    ]
    kept = [event for event in events if _event_has_fbs_member(event, fbs_index)]
    return (
        {"events": kept},
        {
            "unscoped_events": len(events),
            "fbs_scoped_events": len(kept),
            "non_fbs_events_rejected": max(0, len(events) - len(kept)),
        },
    )


def _merge_verified_fbs_events(
    base_games: list[dict[str, Any]],
    filtered_scoreboard: Mapping[str, Any],
    requested_day: str,
) -> tuple[list[dict[str, Any]], int]:
    candidates = prior._espn_schedule_games(filtered_scoreboard, requested_day)
    out = [dict(game) for game in base_games]
    added = 0

    for candidate in candidates:
        if prior._game_matches_existing(candidate, out):
            continue
        row = dict(candidate)
        row["schedule_source"] = "ESPN FBS team-directory verified fallback"
        row["identity_provider"] = "ESPN"
        row["full_fbs_slate_fallback"] = True
        row["mixed_division_supplement"] = bool(
            row.get("mixed_division_supplement")
        )
        out.append(row)
        added += 1

    out.sort(
        key=lambda g: (
            str(g.get("kickoff_iso") or ""),
            str(g.get("game_id") or ""),
        )
    )
    return out, added


@st.cache_data(ttl=120, show_spinner=False)
def load_with_diagnostics(target_date: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested_day = prior.frozen._day(target_date)

    base_games, base_diag = prior.load_with_diagnostics(requested_day)
    attempts = list(base_diag.get("attempts") or [])

    directory_payload, directory_attempts = _fetch_espn_fbs_team_directory()
    attempts.extend(directory_attempts)
    fbs_index = _fbs_team_index(directory_payload or {})

    scoreboard_payload, scoreboard_attempts = _fetch_espn_unscoped_scoreboard(
        requested_day
    )
    attempts.extend(scoreboard_attempts)

    filter_diag = {
        "unscoped_events": 0,
        "fbs_scoped_events": 0,
        "non_fbs_events_rejected": 0,
    }
    added = 0
    games = [dict(g) for g in base_games]

    if scoreboard_payload and any(fbs_index.values()):
        filtered_payload, filter_diag = _filter_unscoped_to_fbs(
            scoreboard_payload,
            fbs_index,
        )
        games, added = _merge_verified_fbs_events(
            games,
            filtered_payload,
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
        **dict(base_diag),
        "version": MODEL_VERSION,
        "requested_date": requested_day,
        "source": (
            "CFB Schedule V2 + ESPN FBS team-directory verified full-slate fallback"
            if games
            else "none"
        ),
        "games": len(games),
        "identity_ready": ready,
        "venue_missing": venue_missing,
        "attempts": attempts,
        "v2_games": len(base_games),
        "fbs_directory_ids": len(fbs_index.get("ids") or set()),
        "fbs_directory_slugs": len(fbs_index.get("slugs") or set()),
        "fbs_directory_names": len(fbs_index.get("names") or set()),
        "full_fbs_fallback_added": added,
        **filter_diag,
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
        _fetch_espn_fbs_team_directory,
        _fetch_espn_unscoped_scoreboard,
    ):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "ESPN_FBS_GROUP",
    "ESPN_SCOREBOARD_URL",
    "ESPN_TEAMS_URL",
    "FROZEN_SCHEDULE",
    "MODEL_VERSION",
    "_competitor_is_fbs",
    "_directory_team_rows",
    "_event_has_fbs_member",
    "_fbs_team_index",
    "_fetch_espn_fbs_team_directory",
    "_fetch_espn_unscoped_scoreboard",
    "_filter_unscoped_to_fbs",
    "_merge_verified_fbs_events",
    "clear_schedule_cache",
    "games_for_date",
    "load_with_diagnostics",
]
