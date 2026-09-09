"""College Football Schedule V4 — robust ESPN enrichment for NCAA scoreboard rows.

Additive layer above frozen Schedule V3.

V3's authoritative NCAA scoreboard can use names such as "Miami (FL)" while
ESPN uses "Miami". The older generic matcher can miss that event, leaving the
visible page with 0 venue/status matches even though the ESPN scoreboard is
available and the logo resolver can identify the same matchup.

V4 preserves the NCAA scoreboard as schedule identity and performs a second,
strict enrichment pass using the already-certified parenthetical-alias matching
from Schedule V2. It adds only verified ESPN metadata:
- ESPN event/team IDs,
- current overall records carried by the event,
- AP curated rank carried by the event,
- venue,
- broadcast,
- status,
- site/neutral flag,
- event week when present.

No model/probability/price logic is added.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import streamlit as st

import cfb_schedule_v2 as frozen
import cfb_schedule_v3 as base
import cfb_schedule_v1 as schedule_v1

MODEL_VERSION = "CFB SCHEDULE V4 • ROBUST ESPN ENRICHMENT"
FROZEN_SCHEDULE = "cfb_schedule_v3"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _record_summary(competitor: Mapping[str, Any]) -> str:
    records = competitor.get("records") or competitor.get("record") or []
    if isinstance(records, Mapping):
        records = [records]
    for item in records if isinstance(records, list) else []:
        if not isinstance(item, Mapping):
            continue
        name = _clean(item.get("name") or item.get("type")).lower()
        if name not in {"overall", "total"}:
            continue
        text = _clean(
            item.get("summary")
            or item.get("displayValue")
            or item.get("record")
        )
        if text:
            return text
    for item in records if isinstance(records, list) else []:
        if isinstance(item, Mapping):
            text = _clean(
                item.get("summary")
                or item.get("displayValue")
                or item.get("record")
            )
            if text:
                return text
    return ""


def _rank(competitor: Mapping[str, Any]) -> int | None:
    try:
        value = int((competitor.get("curatedRank") or {}).get("current"))
    except Exception:
        return None
    return value if 0 < value < 99 else None


def _broadcast(comp: Mapping[str, Any]) -> str:
    names: list[str] = []
    for row in comp.get("broadcasts") or []:
        if not isinstance(row, Mapping):
            continue
        for name in row.get("names") or []:
            text = _clean(name)
            if text:
                names.append(text)
        media = row.get("media") or {}
        if isinstance(media, Mapping):
            text = _clean(media.get("shortName") or media.get("name"))
            if text:
                names.append(text)
    return ", ".join(dict.fromkeys(names))


def _event_week(event: Mapping[str, Any]) -> int:
    week = event.get("week")
    if isinstance(week, Mapping):
        try:
            return int(week.get("number") or 0)
        except Exception:
            return 0
    try:
        return int(week or 0)
    except Exception:
        return 0


def _event_rows(
    payload: Mapping[str, Any],
    requested_day: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        comps = event.get("competitions") or []
        if not comps or not isinstance(comps[0], Mapping):
            continue
        comp = comps[0]

        raw_date = _clean(event.get("date") or comp.get("date"))
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            game_day = dt.astimezone(schedule_v1._ET).date().isoformat()
        except Exception:
            game_day = requested_day
        if game_day != requested_day:
            continue

        sides: dict[str, Mapping[str, Any]] = {}
        for competitor in comp.get("competitors") or []:
            if not isinstance(competitor, Mapping):
                continue
            side = _clean(competitor.get("homeAway")).lower()
            if side in {"away", "home"}:
                sides[side] = competitor
        away = sides.get("away") or {}
        home = sides.get("home") or {}
        if not away or not home:
            continue

        status_type = (event.get("status") or {}).get("type") or {}
        if not isinstance(status_type, Mapping):
            status_type = {}
        venue = comp.get("venue") or {}
        if not isinstance(venue, Mapping):
            venue = {}

        rows.append({
            "event_id": _clean(event.get("id") or comp.get("id")),
            "away_names": schedule_v1._espn_team_names(away),
            "home_names": schedule_v1._espn_team_names(home),
            "away": away,
            "home": home,
            "away_team_id": _clean((away.get("team") or {}).get("id")),
            "home_team_id": _clean((home.get("team") or {}).get("id")),
            "away_record": _record_summary(away),
            "home_record": _record_summary(home),
            "away_rank": _rank(away),
            "home_rank": _rank(home),
            "venue": _clean(venue.get("fullName") or venue.get("name")),
            "broadcast": _broadcast(comp),
            "status": _clean(
                status_type.get("description")
                or status_type.get("detail")
                or status_type.get("shortDetail")
            ),
            "neutral_site": comp.get("neutralSite") is True,
            "week": _event_week(event),
        })
    return rows


def _match(
    game: Mapping[str, Any],
    row: Mapping[str, Any],
) -> bool:
    home = frozen._side_keys_with_parenthetical_alias(game, "home")
    away = frozen._side_keys_with_parenthetical_alias(game, "away")
    row_home = row.get("home_names") or set()
    row_away = row.get("away_names") or set()
    home_ok = bool(home & row_home) or schedule_v1._names_overlap(home, row_home)
    away_ok = bool(away & row_away) or schedule_v1._names_overlap(away, row_away)
    return bool(home_ok and away_ok)


def _enrich_games(
    games: list[dict[str, Any]],
    payload: Mapping[str, Any],
    requested_day: str,
) -> int:
    rows = _event_rows(payload, requested_day)
    used: set[str] = set()
    matched = 0

    for game in games:
        candidate = None
        for row in rows:
            event_id = _clean(row.get("event_id"))
            if event_id and event_id in used:
                continue
            if _match(game, row):
                candidate = row
                break
        if candidate is None:
            continue

        event_id = _clean(candidate.get("event_id"))
        if event_id:
            used.add(event_id)
        matched += 1

        if event_id:
            game["espn_event_id"] = event_id
        if _clean(candidate.get("away_team_id")):
            game["away_espn_team_id"] = _clean(candidate.get("away_team_id"))
        if _clean(candidate.get("home_team_id")):
            game["home_espn_team_id"] = _clean(candidate.get("home_team_id"))
        if _clean(candidate.get("away_record")):
            game["away_record_summary"] = _clean(candidate.get("away_record"))
        if _clean(candidate.get("home_record")):
            game["home_record_summary"] = _clean(candidate.get("home_record"))
        if candidate.get("away_rank") is not None:
            game["away_rank"] = candidate.get("away_rank")
        if candidate.get("home_rank") is not None:
            game["home_rank"] = candidate.get("home_rank")
        if _clean(candidate.get("venue")):
            game["venue"] = _clean(candidate.get("venue"))
        if _clean(candidate.get("broadcast")):
            game["broadcast"] = _clean(candidate.get("broadcast"))
        if _clean(candidate.get("status")):
            game["status"] = _clean(candidate.get("status"))
        game["neutral_site"] = bool(candidate.get("neutral_site"))
        if int(candidate.get("week") or 0) > 0:
            game["espn_week"] = int(candidate.get("week") or 0)

        game["enrichment_source"] = (
            "ESPN College Football scoreboard • Schedule V4 alias-safe match"
        )
        game["schedule_v4_espn_enriched"] = True

    return matched


@st.cache_data(ttl=90, show_spinner=False)
def load_with_diagnostics(
    target_date: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    requested_day = frozen.frozen._day(target_date)
    games, diag = base.load_with_diagnostics(requested_day)
    out = [dict(game) for game in games]
    attempts = list(diag.get("attempts") or [])

    payload: dict[str, Any] = {}
    try:
        payload, espn_attempts = frozen._fetch_espn_fbs_payload(requested_day)
        attempts.extend(espn_attempts or [])
    except Exception:
        payload = {}

    matched = _enrich_games(out, payload, requested_day) if payload else 0
    venue_missing = sum(
        1 for game in out
        if not _clean(game.get("venue"))
        or _clean(game.get("venue")) == "Venue unavailable"
    )
    broadcast_missing = sum(
        1 for game in out
        if not _clean(game.get("broadcast"))
        or _clean(game.get("broadcast")) == "Broadcast unavailable"
    )

    result_diag = dict(diag)
    result_diag.update({
        "version": MODEL_VERSION,
        "attempts": attempts,
        "espn_matches": matched,
        "venue_missing": venue_missing,
        "broadcast_missing": broadcast_missing,
        "schedule_v4_alias_safe_enrichment": True,
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
        base.clear_schedule_cache()
    except Exception:
        pass


__all__ = [
    "FROZEN_SCHEDULE",
    "MODEL_VERSION",
    "_enrich_games",
    "_event_rows",
    "_match",
    "clear_schedule_cache",
    "games_for_date",
    "load_with_diagnostics",
]
