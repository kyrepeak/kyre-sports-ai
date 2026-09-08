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
import re
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


def _side_keys_with_parenthetical_alias(
    game: Mapping[str, Any],
    side: str,
) -> set[str]:
    keys = set(frozen._game_name_keys(game, side))
    raw = str(game.get(f"{side}_team") or "")
    base = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
    if base and base != raw:
        alias = frozen._name_key(base)
        if alias:
            keys.add(alias)
    return keys


def _matches_espn_fbs_event(
    game: Mapping[str, Any],
    espn_rows: list[dict[str, Any]],
) -> bool:
    # Parenthetical NCAA qualifiers such as "Miami (FL)" are explicit aliases,
    # not fuzzy matching. This keeps Miami (FL) -> ESPN "Miami" valid without
    # introducing broad nickname guessing.
    home_keys = _side_keys_with_parenthetical_alias(game, "home")
    away_keys = _side_keys_with_parenthetical_alias(game, "away")
    for row in espn_rows:
        if (home_keys & (row.get("home_names") or set())) and (
            away_keys & (row.get("away_names") or set())
        ):
            return True
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




def _espn_record_summary(competitor: Mapping[str, Any]) -> str:
    for record in competitor.get("records") or []:
        if not isinstance(record, dict):
            continue
        if str(record.get("name") or "").lower() in {"overall", "total"}:
            summary = str(record.get("summary") or "").strip()
            if summary:
                return summary
    for record in competitor.get("records") or []:
        if isinstance(record, dict):
            summary = str(record.get("summary") or "").strip()
            if summary:
                return summary
    return ""


def _espn_rank(competitor: Mapping[str, Any]) -> int | None:
    try:
        value = int((competitor.get("curatedRank") or {}).get("current"))
    except Exception:
        return None
    return value if 0 < value < 99 else None


def _espn_schedule_games(
    payload: Mapping[str, Any],
    requested_day: str,
) -> list[dict[str, Any]]:
    """Convert ESPN's FBS-scoped scoreboard into stable fallback identities."""
    games: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        competitions = event.get("competitions") or []
        if not competitions or not isinstance(competitions[0], dict):
            continue
        comp = competitions[0]

        sides: dict[str, dict[str, Any]] = {}
        for competitor in comp.get("competitors") or []:
            if isinstance(competitor, dict):
                side = str(competitor.get("homeAway") or "").lower()
                if side in {"home", "away"}:
                    sides[side] = competitor
        away = sides.get("away") or {}
        home = sides.get("home") or {}
        if not away or not home:
            continue

        raw_date = str(event.get("date") or comp.get("date") or "").strip()
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            kickoff = dt.astimezone(frozen._ET)
        except Exception:
            continue
        game_day = kickoff.date().isoformat()
        if game_day != requested_day:
            continue

        away_team = away.get("team") or {}
        home_team = home.get("team") or {}
        away_name = str(
            away_team.get("location")
            or away_team.get("shortDisplayName")
            or away_team.get("displayName")
            or "Away"
        ).strip()
        home_name = str(
            home_team.get("location")
            or home_team.get("shortDisplayName")
            or home_team.get("displayName")
            or "Home"
        ).strip()
        away_slug = str(away_team.get("slug") or frozen._slug(away_name)).strip()
        home_slug = str(home_team.get("slug") or frozen._slug(home_name)).strip()
        event_id = str(event.get("id") or "").strip()
        if not event_id or not away_slug or not home_slug:
            continue

        status_type = (event.get("status") or {}).get("type") or {}
        status = str(
            status_type.get("description")
            or status_type.get("detail")
            or status_type.get("shortDetail")
            or "Status unavailable"
        ).strip()

        broadcast_names: list[str] = []
        for broadcast in comp.get("broadcasts") or []:
            if isinstance(broadcast, dict):
                for name in broadcast.get("names") or []:
                    if str(name).strip():
                        broadcast_names.append(str(name).strip())
        broadcast = ", ".join(dict.fromkeys(broadcast_names)) or "Broadcast unavailable"

        venue = str((comp.get("venue") or {}).get("fullName") or "Venue unavailable").strip()
        kickoff_text = kickoff.strftime("%I:%M %p").lstrip("0") + " ET"

        games.append({
            "game_id": event_id,
            "identity_key": f"espn:{event_id}",
            "identity_fingerprint": f"espn:{event_id}",
            "game_date": game_day,
            "kickoff_et": kickoff_text,
            "kickoff_iso": kickoff.isoformat(),
            "away_team": away_name,
            "away_team_slug": away_slug,
            "away_conference": "Conference unavailable",
            "away_rank": _espn_rank(away),
            "away_record_summary": _espn_record_summary(away),
            "home_team": home_name,
            "home_team_slug": home_slug,
            "home_conference": "Conference unavailable",
            "home_rank": _espn_rank(home),
            "home_record_summary": _espn_record_summary(home),
            "venue": venue,
            "status": status,
            "broadcast": broadcast,
            "neutral_site": bool(comp.get("neutralSite")),
            "ncaa_url": "",
            "espn_event_id": event_id,
            "schedule_source": "ESPN FBS scoreboard verified fallback",
            "enrichment_source": "ESPN College Football scoreboard",
            "identity_verified": True,
            "date_matches_query": True,
            "mixed_division_supplement": True,
            "identity_provider": "ESPN",
        })

    games.sort(key=lambda g: (str(g.get("kickoff_iso")), str(g.get("game_id"))))
    return games


def _game_matches_existing(
    candidate: Mapping[str, Any],
    existing: list[dict[str, Any]],
) -> bool:
    candidate_home = _side_keys_with_parenthetical_alias(candidate, "home")
    candidate_away = _side_keys_with_parenthetical_alias(candidate, "away")
    for game in existing:
        home = _side_keys_with_parenthetical_alias(game, "home")
        away = _side_keys_with_parenthetical_alias(game, "away")
        home_match = bool(candidate_home & home) or frozen._names_overlap(candidate_home, home)
        away_match = bool(candidate_away & away) or frozen._names_overlap(candidate_away, away)
        if home_match and away_match:
            return True
    return False


def _supplement_with_espn_fallback(
    games: list[dict[str, Any]],
    espn_payload: Mapping[str, Any],
    requested_day: str,
) -> tuple[list[dict[str, Any]], int]:
    out = [dict(g) for g in games]
    added = 0
    for candidate in _espn_schedule_games(espn_payload, requested_day):
        if _game_matches_existing(candidate, out):
            continue
        out.append(candidate)
        added += 1
    out.sort(key=lambda g: (str(g.get("kickoff_iso")), str(g.get("game_id"))))
    return out, added


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

    # If NCAA's current persisted schedule query is stale/empty, or if it
    # misses an FBS-scoped event, use ESPN groups=80 as an explicit verified
    # fallback identity. This is a schedule completeness fallback only.
    espn_fallback_added = 0
    if espn_payload:
        games, espn_fallback_added = _supplement_with_espn_fallback(
            games,
            espn_payload,
            requested_day,
        )

    # Enrich NCAA-identity games from the already-fetched ESPN payload.
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
        "espn_fallback_added": espn_fallback_added,
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
    "_espn_schedule_games",
    "_supplement_with_espn_fallback",
    "_fetch_espn_fbs_payload",
    "_fetch_ncaa_division_payload",
    "_matches_espn_fbs_event",
    "_side_keys_with_parenthetical_alias",
    "_merge_primary_and_crossovers",
    "_ncaa_params_for_division",
    "clear_schedule_cache",
    "games_for_date",
    "load_with_diagnostics",
]
