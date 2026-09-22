"""CFB Over/Under deep current-data reconciliation V1.

Additive correctness layer above the permanently frozen 12-step O/U stack and
the separately frozen post-12 provider-recovery layer.

Why this exists
---------------
The frozen NCAA full-season schedule query can lag or fail while current event
and team sources already know the real record. That produced contradictions such
as Miami showing a one-game sample but a 0-0 record.

This reconciler does not invent new model formulas. It repairs stale evidence:
- exact current overall and conference records from the verified ESPN event,
- completed current-season W/L, scoring, splits and recent form from exact ESPN
  team schedules before the target kickoff,
- opponent-record/SOS coverage using the already-certified Step-11 fallback,
- current head coach from ESPN Core,
- AP / AFCA Coaches / CFP ranks from the exact current event week,
- venue, broadcast, status and site metadata from the verified event summary.

Provider hierarchy
------------------
1. Frozen NCAA profile remains the base and keeps official NCAA category stats.
2. Exact ESPN event/team identity from the frozen post-12 recovery layer.
3. ESPN event summary for current record / venue / broadcast / event week.
4. ESPN team schedule for completed current-season game facts.
5. ESPN Core for head coach and current-week polls.

No sportsbook, price, market probability, EV, Monte Carlo, or new selection
threshold is introduced here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import fmean
import re
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_data_recovery_v1 as recovery
import cfb_over_under_environment_engine_v1 as environment_engine
import cfb_over_under_form_strength_engine_v1 as form_engine
import cfb_over_under_history_engine_v1 as history_engine
import cfb_over_under_rankings_v1 as frozen_rankings
import cfb_schedule_v3 as schedule
import cfb_team_data_v2 as frozen_team_data

MODEL_VERSION = "CFB O/U DEEP DATA RECONCILIATION V1 • CURRENT DATA HOTFIX"
FROZEN_PARENT_RECOVERY = "cfb_over_under_data_recovery_v1"
FROZEN_TEAM_DATA = "cfb_team_data_v2"

SPORTSBOOK_INPUT_USED = False
MARKET_PROBABILITY_USED = False
EDGE_OR_EV_USED = False
MONTE_CARLO_USED = False
NEW_MODEL_FORMULA_ADDED = False

_CORE_ROOT = (
    "https://sports.core.api.espn.com/v2/sports/football/leagues/"
    "college-football"
)
_FROZEN_RANKING_CONTEXT = frozen_rankings.build_ranking_context


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except Exception:
        return None


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _cutoff(game: Mapping[str, Any]) -> datetime:
    parsed = _parse_dt(game.get("kickoff_iso") or game.get("date"))
    if parsed is not None:
        return parsed
    day = _clean(game.get("game_date"))
    try:
        return datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.max.replace(tzinfo=timezone.utc)


def _season(game: Mapping[str, Any]) -> int:
    day = _clean(game.get("game_date"))
    try:
        return int(day[:4])
    except Exception:
        return datetime.now(timezone.utc).year


def _competition(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    header = payload.get("header") or {}
    if not isinstance(header, Mapping):
        return {}
    comps = header.get("competitions") or []
    if comps and isinstance(comps[0], Mapping):
        return comps[0]
    return {}


def _summary_sides(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    comp = _competition(payload)
    out: dict[str, Mapping[str, Any]] = {}
    for competitor in comp.get("competitors") or []:
        if not isinstance(competitor, Mapping):
            continue
        side = _clean(competitor.get("homeAway")).lower()
        if side in {"away", "home"}:
            out[side] = competitor
    return out


def _record_summary(competitor: Mapping[str, Any], wanted: set[str]) -> str:
    records = competitor.get("record") or competitor.get("records") or []
    if isinstance(records, Mapping):
        records = [records]
    for item in records if isinstance(records, list) else []:
        if not isinstance(item, Mapping):
            continue
        typ = _clean(item.get("type") or item.get("name")).lower()
        if typ not in wanted:
            continue
        text = _clean(
            item.get("summary")
            or item.get("displayValue")
            or item.get("record")
        )
        if text:
            return text
    return ""


def _parse_record(text: Any) -> dict[str, int]:
    match = re.fullmatch(r"(\d+)-(\d+)(?:-(\d+))?", _clean(text))
    if not match:
        return {}
    wins = int(match.group(1))
    losses = int(match.group(2))
    ties = int(match.group(3) or 0)
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "games": wins + losses + ties,
    }


def _record_from_rows(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    wins = losses = ties = 0
    for row in rows:
        pf = float(row.get("points_for") or 0.0)
        pa = float(row.get("points_against") or 0.0)
        if pf > pa:
            wins += 1
        elif pf < pa:
            losses += 1
        else:
            ties += 1
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "games": wins + losses + ties,
    }


def _record_text(record: Mapping[str, Any]) -> str:
    wins = int(record.get("wins") or 0)
    losses = int(record.get("losses") or 0)
    ties = int(record.get("ties") or 0)
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _split_record(rows: list[Mapping[str, Any]], location: str) -> dict[str, int]:
    return _record_from_rows([
        row for row in rows if _clean(row.get("location")).lower() == location
    ])


def _mean(rows: list[float]) -> float | None:
    return float(fmean(rows)) if rows else None


@st.cache_data(ttl=900, show_spinner=False)
def _core_json(
    url: str,
    provider: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    secure = _clean(url).replace("http://", "https://", 1)
    return schedule.frozen.frozen._fetch_json_with_fallback(
        secure,
        {},
        provider,
    )


@st.cache_data(ttl=1800, show_spinner=False)
def _head_coach(team_id: str, season: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    team_id = _clean(team_id)
    if not team_id.isdigit():
        return {}, []
    collection_url = (
        f"{_CORE_ROOT}/seasons/{int(season)}/teams/{team_id}/coaches"
        "?lang=en&region=us"
    )
    collection, attempts = _core_json(
        collection_url,
        f"ESPN Core CFB team {team_id} head coach",
    )
    items = collection.get("items") or []
    if not items:
        return {}, attempts
    first = items[0] if isinstance(items[0], Mapping) else {}
    ref = _clean(first.get("$ref"))
    if not ref:
        return {}, attempts
    detail, detail_attempts = _core_json(
        ref,
        f"ESPN Core CFB team {team_id} coach detail",
    )
    attempts.extend(detail_attempts)
    if not detail:
        return {}, attempts
    first_name = _clean(detail.get("firstName"))
    last_name = _clean(detail.get("lastName"))
    display = " ".join(x for x in (first_name, last_name) if x)
    return {
        "ready": bool(display),
        "id": _clean(detail.get("id")),
        "name": display,
        "first_name": first_name,
        "last_name": last_name,
        "source": "ESPN Core current-season head coach",
    }, attempts


@st.cache_data(ttl=900, show_spinner=False)
def _team_polls(
    team_id: str,
    season: int,
    week: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    team_id = _clean(team_id)
    if not team_id.isdigit() or int(week) <= 0:
        return {}, []
    url = (
        f"{_CORE_ROOT}/seasons/{int(season)}/types/2/weeks/{int(week)}/"
        f"teams/{team_id}/ranks?lang=en&region=us"
    )
    collection, attempts = _core_json(
        url,
        f"ESPN Core CFB team {team_id} Week {int(week)} polls",
    )
    out: dict[str, Any] = {}
    for item in collection.get("items") or []:
        if not isinstance(item, Mapping):
            continue
        ref = _clean(item.get("$ref"))
        if not ref:
            continue
        detail, detail_attempts = _core_json(
            ref,
            f"ESPN Core CFB team {team_id} poll detail",
        )
        attempts.extend(detail_attempts)
        if not detail:
            continue
        typ = _clean(detail.get("type")).lower()
        name = _clean(detail.get("shortName") or detail.get("name"))
        rank_obj = detail.get("rank") or {}
        if not isinstance(rank_obj, Mapping):
            rank_obj = {}
        current = _int(rank_obj.get("current"))
        row = {
            "rank": current,
            "previous": _int(rank_obj.get("previous")),
            "state": "ranked" if current is not None else "unranked",
            "name": name,
            "date": _clean(detail.get("date") or detail.get("lastUpdated")),
            "week": int(week),
            "source": "ESPN Core exact-week poll",
        }
        if typ == "ap" or "ap poll" in name.lower():
            out["ap"] = row
        elif typ == "usa" or "coach" in name.lower():
            out["coaches"] = row
        elif typ == "cfp" or "playoff" in name.lower():
            out["cfp"] = row
    return out, attempts


def _current_rows(
    team_id: str,
    season: int,
    cutoff: datetime,
    excluded_event_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    payload, attempts = history_engine._fetch_team_schedule(team_id, int(season))
    rows = form_engine._current_season_rows(
        payload,
        team_id,
        int(season),
        cutoff,
        excluded_event_id,
    )
    hydrated, hydration = form_engine._hydrate_opponent_records(
        rows,
        int(season),
        cutoff,
        excluded_event_id,
    )
    attempts.extend(hydration.get("attempts") or [])

    # Restore all current-season completed games, not just the Step-11 form
    # window, so season W/L and splits stay exact later in the year.
    all_rows: dict[str, dict[str, Any]] = {}
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        row = form_engine._event_row_with_opponent_record(event, team_id)
        if not row:
            continue
        event_id = _clean(row.get("event_id"))
        if excluded_event_id and event_id == _clean(excluded_event_id):
            continue
        dt = row.get("date_dt")
        if not isinstance(dt, datetime) or dt >= cutoff or dt.year != int(season):
            continue
        comp = event.get("competitions") or []
        competition = comp[0] if comp and isinstance(comp[0], Mapping) else {}
        row = dict(row)
        if competition.get("neutralSite") is True:
            row["location"] = "neutral"
        else:
            row["location"] = _clean(row.get("home_away")).lower()
        all_rows[event_id or _clean(row.get("date"))] = row

    ordered = sorted(
        all_rows.values(),
        key=lambda row: row.get("date_dt")
        or datetime.min.replace(tzinfo=timezone.utc),
    )

    # Copy hydrated opponent-record values back onto matching all-season rows.
    hydrated_by_id = {
        _clean(row.get("event_id")): row
        for row in hydrated
        if _clean(row.get("event_id"))
    }
    for row in ordered:
        hydrated_row = hydrated_by_id.get(_clean(row.get("event_id")))
        if hydrated_row:
            row["opponent_record_pct"] = hydrated_row.get("opponent_record_pct")
            row["opponent_record_source"] = hydrated_row.get(
                "opponent_record_source"
            )

    return ordered, hydration, attempts


def _team_snapshot_from_summary(
    summary: Mapping[str, Any],
    side: str,
) -> dict[str, Any]:
    competitor = (_summary_sides(summary).get(side) or {})
    team = competitor.get("team") or {}
    if not isinstance(team, Mapping):
        team = {}
    overall = _record_summary(competitor, {"total", "overall"})
    conference = _record_summary(
        competitor,
        {"vsconf", "conference", "conference record"},
    )
    return {
        "team_id": _clean(team.get("id") or competitor.get("id")),
        "overall_record": overall,
        "conference_record": conference,
        "curated_rank": _int(
            (competitor.get("curatedRank") or {}).get("current")
            if isinstance(competitor.get("curatedRank"), Mapping)
            else None
        ),
    }


def _broadcast(comp: Mapping[str, Any]) -> str:
    for row in comp.get("broadcasts") or []:
        if not isinstance(row, Mapping):
            continue
        media = row.get("media") or {}
        if not isinstance(media, Mapping):
            media = {}
        name = _clean(
            media.get("shortName")
            or media.get("name")
            or row.get("name")
        )
        if name:
            return name
    return ""


def _enrich_game(
    game: Mapping[str, Any],
    summary: Mapping[str, Any],
    environment: Mapping[str, Any],
) -> dict[str, Any]:
    out = dict(game)
    comp = _competition(summary)
    game_info = summary.get("gameInfo") or {}
    if not isinstance(game_info, Mapping):
        game_info = {}
    venue = game_info.get("venue") or {}
    if not isinstance(venue, Mapping):
        venue = {}
    address = venue.get("address") or {}
    if not isinstance(address, Mapping):
        address = {}

    status = comp.get("status") or {}
    if not isinstance(status, Mapping):
        status = {}
    status_type = status.get("type") or {}
    if not isinstance(status_type, Mapping):
        status_type = {}

    away = _team_snapshot_from_summary(summary, "away")
    home = _team_snapshot_from_summary(summary, "home")

    event_id = _clean(
        environment.get("event_id")
        or (summary.get("header") or {}).get("id")
        or comp.get("id")
    )
    if event_id:
        out["espn_event_id"] = event_id
    name = _clean(venue.get("fullName") or venue.get("name"))
    if name:
        out["venue"] = name
    broadcast = _broadcast(comp)
    if broadcast:
        out["broadcast"] = broadcast
    description = _clean(
        status_type.get("description")
        or status_type.get("name")
        or out.get("status")
    )
    if description:
        out["status"] = description
    detail = _clean(status_type.get("detail") or status_type.get("shortDetail"))
    if detail:
        out["status_detail"] = detail
    if comp:
        out["neutral_site"] = comp.get("neutralSite") is True
    if address:
        out["venue_city"] = _clean(address.get("city"))
        out["venue_state"] = _clean(address.get("state"))
    out["venue_surface_grass"] = venue.get("grass") is True if venue else None
    try:
        out["espn_week"] = int((summary.get("header") or {}).get("week") or 0)
    except Exception:
        out["espn_week"] = 0

    out["away_record_summary"] = (
        away.get("overall_record") or out.get("away_record_summary") or ""
    )
    out["home_record_summary"] = (
        home.get("overall_record") or out.get("home_record_summary") or ""
    )
    out["away_conference_record_summary"] = (
        away.get("conference_record")
        or out.get("away_conference_record_summary")
        or ""
    )
    out["home_conference_record_summary"] = (
        home.get("conference_record")
        or out.get("home_conference_record_summary")
        or ""
    )
    out["deep_data_reconciled"] = True
    out["deep_data_source"] = (
        "NCAA base + verified ESPN event summary / team schedules / Core"
    )
    return out


def _reconcile_profile(
    side: str,
    game: Mapping[str, Any],
    profile: Mapping[str, Any],
    summary: Mapping[str, Any],
    environment: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    out = dict(profile)
    season = _season(game)
    cutoff = _cutoff(game)
    event_id = _clean(environment.get("event_id"))
    team_id = _clean(
        environment.get(f"{side}_espn_team_id")
        or _team_snapshot_from_summary(summary, side).get("team_id")
    )

    rows: list[dict[str, Any]] = []
    hydration: dict[str, Any] = {}
    attempts: list[dict[str, Any]] = []
    if team_id.isdigit():
        rows, hydration, schedule_attempts = _current_rows(
            team_id,
            season,
            cutoff,
            event_id,
        )
        attempts.extend(schedule_attempts)

    summary_side = _team_snapshot_from_summary(summary, side)
    summary_record = _parse_record(summary_side.get("overall_record"))
    row_record = _record_from_rows(rows)
    record = (
        summary_record
        if int(summary_record.get("games") or 0)
        >= int(row_record.get("games") or 0)
        else row_record
    )
    if not record and row_record:
        record = row_record

    if record:
        out["record"] = dict(record)
        out["record_text"] = _record_text(record)

    if rows:
        pfs = [float(row.get("points_for") or 0.0) for row in rows]
        pas = [float(row.get("points_against") or 0.0) for row in rows]
        diffs = [pf - pa for pf, pa in zip(pfs, pas)]
        recent = rows[-5:]

        out["ppg"] = float(fmean(pfs))
        out["points_allowed_pg"] = float(fmean(pas))
        out["point_diff_pg"] = float(fmean(diffs))
        out["home_record"] = _split_record(rows, "home")
        out["away_record"] = _split_record(rows, "away")
        out["neutral_record"] = _split_record(rows, "neutral")
        out["recent_record"] = _record_from_rows(recent)
        out["recent_form"] = "".join(
            "W" if float(r.get("points_for") or 0) > float(r.get("points_against") or 0)
            else "L" if float(r.get("points_for") or 0) < float(r.get("points_against") or 0)
            else "T"
            for r in recent
        ) or "—"
        out["recent_ppg"] = _mean([
            float(r.get("points_for") or 0.0) for r in recent
        ])
        out["recent_points_allowed_pg"] = _mean([
            float(r.get("points_against") or 0.0) for r in recent
        ])
        out["recent_point_diff_pg"] = _mean([
            float(r.get("points_for") or 0.0)
            - float(r.get("points_against") or 0.0)
            for r in recent
        ])
        opp_pcts = [
            float(r["opponent_record_pct"])
            for r in rows
            if r.get("opponent_record_pct") is not None
        ]
        out["sos_opponent_win_pct"] = _mean(opp_pcts)
        out["sos_coverage"] = len(opp_pcts) / len(rows) if rows else 0.0
        out["completed_games"] = [
            {
                "event_id": _clean(r.get("event_id")),
                "date": _clean(r.get("date"))[:10],
                "opponent": _clean(r.get("opponent_name")),
                "opponent_id": _clean(r.get("opponent_id")),
                "location": _clean(r.get("location")),
                "result": (
                    "W" if float(r.get("points_for") or 0) > float(r.get("points_against") or 0)
                    else "L" if float(r.get("points_for") or 0) < float(r.get("points_against") or 0)
                    else "T"
                ),
                "score": (
                    f"{int(float(r.get('points_for') or 0))}-"
                    f"{int(float(r.get('points_against') or 0))}"
                ),
            }
            for r in rows
        ]

    conference_record_text = _clean(summary_side.get("conference_record"))
    out["conference_record_text"] = conference_record_text or "—"
    out["conference_record"] = _parse_record(conference_record_text)

    division = _clean(out.get("division_context")).upper()
    if not division or division not in {"FBS", "FCS"}:
        source = _clean(out.get("data_source")).lower()
        stat_labels = " ".join(
            _clean(item.get("label")).lower()
            for item in (out.get("official_stats") or {}).values()
            if isinstance(item, Mapping)
        )
        division = "FCS" if ("fcs" in source or "fcs" in stat_labels) else "FBS"
    elif division == "FBS":
        # The stats-only crossover fallback can inherit a stale FBS default.
        # Official NCAA rows labeled FCS are stronger evidence of division.
        stat_labels = " ".join(
            _clean(item.get("label")).lower()
            for item in (out.get("official_stats") or {}).values()
            if isinstance(item, Mapping)
        )
        if "fcs" in stat_labels:
            division = "FCS"
    out["division_context"] = division

    coach, coach_attempts = _head_coach(team_id, season)
    attempts.extend(coach_attempts)
    if coach.get("ready"):
        out["head_coach"] = _clean(coach.get("name"))
        out["head_coach_id"] = _clean(coach.get("id"))
        out["head_coach_source"] = _clean(coach.get("source"))

    week = int(game.get("espn_week") or 0)
    polls, poll_attempts = _team_polls(team_id, season, week)
    attempts.extend(poll_attempts)
    out["polls"] = dict(polls)
    out["ap_poll_rank"] = (polls.get("ap") or {}).get("rank")
    out["coaches_poll_rank"] = (polls.get("coaches") or {}).get("rank")
    out["cfp_rank"] = (polls.get("cfp") or {}).get("rank")

    if division == "FBS":
        ap_rank = out.get("ap_poll_rank")
        if ap_rank is None:
            ap_rank = summary_side.get("curated_rank")
        out["ap_rank"] = _int(ap_rank)
        out["rank_source"] = (
            "ESPN Core AP Poll exact current week"
            if out.get("ap_rank") is not None
            else "AP Poll current week — unranked"
        )
    else:
        out["ap_rank"] = None
        out["rank_source"] = "FCS • FBS AP Poll not applicable"

    out["espn_team_id"] = team_id
    out["deep_data_reconciled"] = True
    out["current_schedule_games_verified"] = len(rows)
    out["data_source"] = (
        _clean(out.get("data_source"))
        + " + ESPN exact-event/current-season reconciliation"
    ).strip(" +")
    try:
        out["data_quality"] = frozen_team_data.frozen._quality(out)
    except Exception:
        pass

    return out, {
        "side": side,
        "team_id": team_id,
        "schedule_games": len(rows),
        "summary_record": _clean(summary_side.get("overall_record")),
        "conference_record": conference_record_text,
        "coach_ready": bool(coach.get("ready")),
        "polls": sorted(polls),
        "opponent_record_fallback_resolved": int(
            hydration.get("fallback_resolved") or 0
        ),
        "attempts": attempts,
    }


def reconcile_matchup(
    game: Mapping[str, Any],
    as_of_day: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return enriched game + reconciled away/home profiles for one matchup."""
    profiles, base_diag = frozen_team_data.load_matchup_team_data(
        game,
        as_of_day,
    )
    away_base = dict(profiles.get("away") or {})
    home_base = dict(profiles.get("home") or {})

    environment = recovery.build_environment_engine(
        game,
        away_base,
        home_base,
    )
    event_id = _clean(environment.get("event_id"))
    summary: dict[str, Any] = {}
    summary_attempts: list[dict[str, Any]] = []
    if event_id:
        try:
            summary, summary_attempts = environment_engine._fetch_summary(
                event_id
            )
        except Exception:
            summary, summary_attempts = {}, []

    enriched_game = _enrich_game(game, summary, environment)
    away, away_diag = _reconcile_profile(
        "away",
        enriched_game,
        away_base,
        summary,
        environment,
    )
    home, home_diag = _reconcile_profile(
        "home",
        enriched_game,
        home_base,
        summary,
        environment,
    )

    diag = dict(base_diag)
    diag.update({
        "version": MODEL_VERSION,
        "deep_data_reconciled": True,
        "event_id": event_id,
        "event_summary_ready": bool(summary),
        "away_reconciliation": away_diag,
        "home_reconciliation": home_diag,
        "attempts": list(base_diag.get("attempts") or [])
        + list(summary_attempts or [])
        + list(away_diag.get("attempts") or [])
        + list(home_diag.get("attempts") or []),
        "sportsbook_input_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "new_model_formula_added": False,
    })
    return {
        "game": enriched_game,
        "away": away,
        "home": home,
        "environment": dict(environment),
        "summary_ready": bool(summary),
    }, diag


def build_ranking_context(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    """Keep NCAA category ranks but repair polls/records from reconciled profiles."""
    context = _FROZEN_RANKING_CONTEXT(game, away, home)
    out = dict(context)
    for side_name, profile in (("away", away), ("home", home)):
        side = dict(out.get(side_name) or {})
        division = _clean(profile.get("division_context")).upper() or "FBS"
        side.update({
            "team": _clean(profile.get("team")) or side.get("team") or "Team",
            "conference": _clean(profile.get("conference"))
            or side.get("conference")
            or "Conference unavailable",
            "division": division,
            "record": _clean(profile.get("record_text")) or side.get("record") or "—",
            "home_record": _record_text(profile.get("home_record") or {}),
            "away_record": _record_text(profile.get("away_record") or {}),
            "recent_form": _clean(profile.get("recent_form")) or "—",
        })
        polls = profile.get("polls") or {}
        if division == "FBS":
            ap = polls.get("ap") or {}
            coaches = polls.get("coaches") or {}
            cfp = polls.get("cfp") or {}
            side["ap"] = {
                "rank": profile.get("ap_rank"),
                "state": "ranked" if profile.get("ap_rank") is not None else "unranked",
            }
            side["coaches"] = {
                "rank": coaches.get("rank"),
                "state": (
                    "ranked" if coaches.get("rank") is not None
                    else "unranked" if "coaches" in polls
                    else "unavailable"
                ),
            }
            if "cfp" in polls:
                side["cfp"] = {
                    "rank": cfp.get("rank"),
                    "state": "ranked" if cfp.get("rank") is not None else "unranked",
                }
        else:
            side["ap"] = {"rank": None, "state": "not_applicable"}
            side["coaches"] = {"rank": None, "state": "not_applicable"}
            side["cfp"] = {"rank": None, "state": "not_applicable"}
        out[side_name] = side
    out["deep_data_reconciled"] = True
    out["poll_source"] = "ESPN Core exact current event week"
    out["record_source"] = "ESPN exact event + completed team schedules"
    return out


def clear_reconciliation_cache() -> None:
    for fn in (_core_json, _head_coach, _team_polls):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "EDGE_OR_EV_USED",
    "FROZEN_PARENT_RECOVERY",
    "FROZEN_TEAM_DATA",
    "MARKET_PROBABILITY_USED",
    "MODEL_VERSION",
    "MONTE_CARLO_USED",
    "NEW_MODEL_FORMULA_ADDED",
    "SPORTSBOOK_INPUT_USED",
    "_head_coach",
    "_team_polls",
    "build_ranking_context",
    "clear_reconciliation_cache",
    "reconcile_matchup",
]
