"""WNBA PRA V3.3 — availability integrity layer.

Repairs the pregame availability handoff without changing the existing PRA
projection formulas.  The older Step-4 path already used ESPN event/team injury
feeds and current rosters, but duplicate provider rows were first-row-wins.  A
less severe/stale row could therefore mask a later OUT row.  V3.3 resolves every
status candidate conservatively, gives the strongest current designation
precedence, uses roster status as an independent fallback, tracks provider
coverage per team, and exposes a fail-closed verification flag downstream.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd
import streamlit as st

import wnba_availability_v27 as base
import wnba_players_v25 as players
import wnba_schedule_v24 as schedule_v24

ESPN_SUMMARY = players.ESPN_SUMMARY
ESPN_TEAM_INJURIES = base.ESPN_TEAM_INJURIES

OUT_STATUSES = {"OUT", "INACTIVE", "DOUBTFUL"}
UNCERTAIN_STATUSES = {"QUESTIONABLE", "DAY-TO-DAY", "PROBABLE"}
KNOWN_STATUSES = OUT_STATUSES | UNCERTAIN_STATUSES | {"AVAILABLE", "ACTIVE", "NO DESIGNATION"}

_STATUS_RANK = {
    "NO DESIGNATION": 0,
    "ACTIVE": 1,
    "AVAILABLE": 1,
    "PROBABLE": 2,
    "DAY-TO-DAY": 3,
    "QUESTIONABLE": 4,
    "DOUBTFUL": 5,
    "INACTIVE": 6,
    "OUT": 7,
}
_SOURCE_RANK = {
    "ESPN WNBA team injury feed": 4,
    "ESPN WNBA event summary": 3,
    "ESPN WNBA current roster status": 2,
    "ESPN WNBA roster": 1,
}


def _day_str(day=None) -> str:
    return base._day_str(day)


def _norm_name(value) -> str:
    try:
        return base._norm_name(value)
    except Exception:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
        return re.sub(r"[^a-z0-9]", "", text)


def _status_text(value) -> str:
    if isinstance(value, dict):
        for key in ("name", "description", "type", "status", "designation", "state"):
            if value.get(key):
                return str(value.get(key)).strip()
        return ""
    return str(value or "").strip()


def _normalize(value) -> str:
    raw = _status_text(value)
    if not raw:
        return "NO DESIGNATION"
    normalized = base._normalize_designation(raw)
    return normalized if normalized in KNOWN_STATUSES else "NO DESIGNATION"


def _best_status(candidates):
    """Return strongest designation; severity wins, then provider priority."""
    clean = []
    for c in candidates or []:
        if not isinstance(c, dict):
            continue
        designation = _normalize(c.get("DESIGNATION"))
        if designation == "NO DESIGNATION" and not c.get("explicit_no_designation"):
            continue
        obj = dict(c)
        obj["DESIGNATION"] = designation
        clean.append(obj)
    if not clean:
        return {
            "DESIGNATION": "NO DESIGNATION", "DETAIL": "", "SOURCE": "",
            "STATUS_RANK": 0,
        }
    clean.sort(
        key=lambda c: (
            _STATUS_RANK.get(str(c.get("DESIGNATION") or "NO DESIGNATION"), 0),
            _SOURCE_RANK.get(str(c.get("SOURCE") or ""), 0),
        ),
        reverse=True,
    )
    best = clean[0]
    return {
        "DESIGNATION": str(best.get("DESIGNATION") or "NO DESIGNATION"),
        "DETAIL": str(best.get("DETAIL") or ""),
        "SOURCE": str(best.get("SOURCE") or ""),
        "STATUS_RANK": int(_STATUS_RANK.get(str(best.get("DESIGNATION") or "NO DESIGNATION"), 0)),
    }


def _item_designation(item: dict) -> str:
    """Handle the common ESPN status shapes without treating body-part type as status."""
    candidates = []
    for key in ("status", "designation", "injuryStatus", "availability"):
        if key in item:
            candidates.append(item.get(key))
    athlete = item.get("athlete") if isinstance(item.get("athlete"), dict) else {}
    for key in ("status", "designation", "injuryStatus", "availability"):
        if key in athlete:
            candidates.append(athlete.get(key))
    # ESPN sometimes places OUT / Questionable in type; only accept it if it
    # actually normalizes to a known availability designation.
    if "type" in item:
        candidates.append(item.get("type"))
    normalized = [_normalize(x) for x in candidates]
    normalized = [x for x in normalized if x != "NO DESIGNATION"]
    if not normalized:
        return "NO DESIGNATION"
    return max(normalized, key=lambda x: _STATUS_RANK.get(x, 0))


def _team_id_from_obj(team) -> int:
    return base._team_id_from_obj(team)


def _athlete_from_item(item: dict) -> dict:
    return base._athlete_from_item(item)


def _parse_container(container, default_team_id=0, source="ESPN WNBA event summary") -> list[dict]:
    rows = []
    if not container:
        return rows
    blocks = container if isinstance(container, list) else [container]
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_tid = _team_id_from_obj(block.get("team")) or int(default_team_id or 0)
        items = block.get("injuries") or block.get("items")
        if not isinstance(items, list):
            items = [block] if block.get("athlete") or block.get("displayName") else []
        for item in items:
            if not isinstance(item, dict):
                continue
            athlete = _athlete_from_item(item)
            name = athlete.get("displayName") or athlete.get("fullName") or item.get("displayName") or item.get("fullName")
            if not name:
                continue
            designation = _item_designation(item)
            if designation == "NO DESIGNATION":
                # An injury item with no recognizable availability status is not
                # proof that the player is active; do not invent a designation.
                continue
            rows.append({
                "TEAM_ID": block_tid,
                "PLAYER_ID": athlete.get("id") or item.get("id"),
                "PLAYER_NAME": str(name),
                "DESIGNATION": designation,
                "DETAIL": base._injury_detail(item),
                "SOURCE": source,
            })
    return rows


@st.cache_data(ttl=90, show_spinner=False)
def _event_summary_fresh(game_id: str):
    payload, meta = schedule_v24._request_json(
        "ESPN WNBA PRA V3.3 availability summary",
        ESPN_SUMMARY,
        params={"event": str(game_id)},
        timeout=8,
        attempts=3,
    )
    return payload, meta


@st.cache_data(ttl=90, show_spinner=False)
def _team_injury_feed_fresh(team_id: int):
    slug = players.TEAM_SLUGS.get(int(team_id))
    if not slug:
        return None, {"ok": False, "reason": "no team slug"}
    payload, meta = schedule_v24._request_json(
        "ESPN WNBA PRA V3.3 team injuries",
        ESPN_TEAM_INJURIES.format(team=slug),
        timeout=8,
        attempts=3,
    )
    return payload, meta


def _merge_injury_rows(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    buckets = {}
    for r in rows:
        tid = int(r.get("TEAM_ID") or 0)
        name = _norm_name(r.get("PLAYER_NAME"))
        if not tid or not name:
            continue
        buckets.setdefault((tid, name), []).append(r)
    merged = []
    for (tid, _name), candidates in buckets.items():
        best = _best_status(candidates)
        # Preserve the best candidate's identity fields.
        winner = max(
            candidates,
            key=lambda c: (
                _STATUS_RANK.get(_normalize(c.get("DESIGNATION")), 0),
                _SOURCE_RANK.get(str(c.get("SOURCE") or ""), 0),
            ),
        )
        merged.append({
            "TEAM_ID": tid,
            "PLAYER_ID": winner.get("PLAYER_ID"),
            "PLAYER_NAME": winner.get("PLAYER_NAME"),
            **best,
        })
    return pd.DataFrame(merged)


def _walk_starters(obj, team_hint=0, out=None):
    return base._walk_starters(obj, team_hint, out)


@st.cache_data(ttl=90, show_spinner=False)
def availability_for_game_key(game_id: str, away_id: int, home_id: int, day_str: str):
    injury_rows, starter_rows = [], []
    summary_payload, summary_meta = _event_summary_fresh(str(game_id))
    summary_connected = isinstance(summary_payload, dict)
    if summary_connected:
        injury_rows.extend(_parse_container(summary_payload.get("injuries"), 0, "ESPN WNBA event summary"))
        starter_rows.extend(_walk_starters(summary_payload))

    team_feed_ok = {}
    for tid in (int(away_id), int(home_id)):
        try:
            payload, meta = _team_injury_feed_fresh(tid)
        except Exception:
            payload, meta = None, {}
        ok = isinstance(payload, dict)
        team_feed_ok[tid] = bool(ok)
        if ok:
            injury_rows.extend(_parse_container(payload.get("injuries") or payload, tid, "ESPN WNBA team injury feed"))

    injuries = _merge_injury_rows(injury_rows)
    starters = base._merge_rows(starter_rows)
    coverage = {
        int(away_id): bool(summary_connected or team_feed_ok.get(int(away_id))),
        int(home_id): bool(summary_connected or team_feed_ok.get(int(home_id))),
    }
    return {
        "injuries": injuries.to_dict("records") if not injuries.empty else [],
        "starters": starters.to_dict("records") if not starters.empty else [],
        "summary_connected": bool(summary_connected),
        "team_feeds_connected": int(sum(bool(x) for x in team_feed_ok.values())),
        "team_feed_ok": team_feed_ok,
        "team_status_coverage": coverage,
        "source": "ESPN WNBA event summary + team injury feeds + current roster status",
    }


def _roster_status_candidate(row: pd.Series):
    raw = str(row.get("ROSTER_STATUS") or "").strip()
    designation = _normalize(raw)
    if designation == "NO DESIGNATION":
        return None
    return {
        "DESIGNATION": designation,
        "DETAIL": "Current roster status",
        "SOURCE": "ESPN WNBA current roster status",
    }


def availability_for_game(row, stats: pd.DataFrame | None = None) -> dict:
    away_id = int(row.get("away_team_id") or 0)
    home_id = int(row.get("home_team_id") or 0)
    game_id = str(row.get("game_id") or "")
    day_str = _day_str(row.get("game_date") or None)
    raw = availability_for_game_key(game_id, away_id, home_id, day_str)
    injuries = pd.DataFrame(raw.get("injuries") or [])
    starters = pd.DataFrame(raw.get("starters") or [])

    if stats is None:
        stats = player_form_table()
    pool = slate_player_pool(pd.DataFrame([row]), stats) if stats is not None else pd.DataFrame()

    starter_names = set()
    if not starters.empty:
        starter_names = set((int(r.TEAM_ID), _norm_name(r.PLAYER_NAME)) for _, r in starters.iterrows())
    injury_map = {}
    if not injuries.empty:
        for _, r in injuries.iterrows():
            injury_map[(int(r.get("TEAM_ID") or 0), _norm_name(r.get("PLAYER_NAME")))] = r

    coverage = {int(k): bool(v) for k, v in (raw.get("team_status_coverage") or {}).items()}
    rows = []
    for _, p in pool.iterrows():
        tid = int(p.get("TEAM_ID") or 0)
        key = (tid, _norm_name(p.get("PLAYER_NAME")))
        candidates = []
        inj = injury_map.get(key)
        if inj is not None:
            candidates.append({
                "DESIGNATION": inj.get("DESIGNATION"),
                "DETAIL": inj.get("DETAIL"),
                "SOURCE": inj.get("SOURCE"),
            })
        roster_candidate = _roster_status_candidate(p)
        if roster_candidate:
            candidates.append(roster_candidate)
        best = _best_status(candidates)

        provider_ok = bool(coverage.get(tid, False))
        explicit_status = best.get("DESIGNATION") != "NO DESIGNATION"
        verified = bool(provider_ok or explicit_status)
        designation = str(best.get("DESIGNATION") or "NO DESIGNATION")
        if not verified and designation == "NO DESIGNATION":
            designation = "STATUS UNVERIFIED"

        rows.append({
            "TEAM_ID": tid,
            "PLAYER_ID": p.get("PLAYER_ID"),
            "PLAYER_NAME": p.get("PLAYER_NAME"),
            "DESIGNATION": designation,
            "DETAIL": str(best.get("DETAIL") or ""),
            "STATUS_SOURCE": str(best.get("SOURCE") or ("live provider coverage" if provider_ok else "provider unavailable")),
            "AVAILABILITY_VERIFIED": verified,
            "PROVIDER_COVERED": provider_ok,
            "STARTER_CONFIRMED": key in starter_names,
            "STARTER_SOURCE": "ESPN WNBA explicit starter flag" if key in starter_names else "",
        })

    frame = pd.DataFrame(rows)
    starter_counts = {}
    for tid in (away_id, home_id):
        starter_counts[tid] = int(frame[(frame["TEAM_ID"].eq(tid)) & (frame["STARTER_CONFIRMED"].eq(True))].shape[0]) if not frame.empty else 0
    return {
        "players": frame,
        "injuries": injuries,
        "starters": starters,
        "summary_connected": raw.get("summary_connected", False),
        "team_feeds_connected": raw.get("team_feeds_connected", 0),
        "team_status_coverage": coverage,
        "starter_counts": starter_counts,
        "source": raw.get("source"),
    }


@st.cache_data(ttl=90, show_spinner=False)
def _availability_diag_for_day(day_str: str):
    day_str = _day_str(day_str)
    schedule = schedule_for_date(day_str)
    stats, pool_diag = base._verified_pool_for_day(day_str)
    if schedule is None or schedule.empty:
        return {
            "state": "NO_GAMES", "selected_date": day_str, "games": 0,
            "teams": 0, "players": 0, "hard_out": 0, "uncertain": 0,
            "unverified": 0, "covered_teams": 0, "pool_diag": pool_diag,
        }

    frames = []
    covered_team_ids = set()
    summary_feeds = team_feeds = starter_count = 0
    for _, game in schedule.iterrows():
        status = str(game.get("status") or game.get("status_text") or "").upper()
        if "FINAL" in status:
            continue
        av = availability_for_game(game, stats)
        p = av.get("players")
        if isinstance(p, pd.DataFrame) and not p.empty:
            frames.append(p)
            starter_count += int(p.get("STARTER_CONFIRMED", pd.Series(dtype=bool)).fillna(False).sum())
        summary_feeds += int(bool(av.get("summary_connected")))
        team_feeds += int(av.get("team_feeds_connected") or 0)
        for tid, ok in (av.get("team_status_coverage") or {}).items():
            if ok:
                covered_team_ids.add(int(tid))

    allp = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    designations = allp.get("DESIGNATION", pd.Series(dtype=object)).astype(str).str.upper() if not allp.empty else pd.Series(dtype=object)
    hard_out = int(designations.isin(OUT_STATUSES).sum()) if not allp.empty else 0
    uncertain = int(designations.isin(UNCERTAIN_STATUSES).sum()) if not allp.empty else 0
    unverified = int((~allp.get("AVAILABILITY_VERIFIED", pd.Series(False, index=allp.index)).fillna(False).astype(bool)).sum()) if not allp.empty else 0
    active_teams = set()
    for _, g in schedule.iterrows():
        status = str(g.get("status") or g.get("status_text") or "").upper()
        if "FINAL" not in status:
            active_teams.add(int(g.get("away_team_id") or 0)); active_teams.add(int(g.get("home_team_id") or 0))
    active_teams.discard(0)
    coverage_ok = bool(active_teams.issubset(covered_team_ids)) if active_teams else True
    state = "VERIFIED" if coverage_ok and unverified == 0 else "CHECK"
    return {
        "state": state,
        "selected_date": day_str,
        "games": int(len(schedule)),
        "teams": int(len(active_teams)),
        "players": int(len(allp)),
        "hard_out": hard_out,
        "uncertain": uncertain,
        "unverified": unverified,
        "covered_teams": int(len(active_teams & covered_team_ids)),
        "summary_feeds": int(summary_feeds),
        "team_injury_feeds": int(team_feeds),
        "confirmed_starters": int(starter_count),
        "pool_diag": pool_diag,
        "source": "ESPN WNBA event/team injury feeds with severity precedence + roster-status fallback",
    }


def availability_diagnostics(day) -> dict:
    return _availability_diag_for_day(_day_str(day))


def clear_availability_cache():
    for fn in (_event_summary_fresh, _team_injury_feed_fresh, availability_for_game_key, _availability_diag_for_day):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        base.clear_availability_cache()
    except Exception:
        pass


# Re-export the verified Step 1-3/current-roster interfaces.
player_form_table = base.player_form_table
slate_player_pool = base.slate_player_pool
team_player_pool = base.team_player_pool
player_pool_diagnostics = base.player_pool_diagnostics
schedule_for_date = base.schedule_for_date
schedule_diagnostics = base.schedule_diagnostics
clear_schedule_cache = base.clear_schedule_cache
current_season = base.current_season
data_health = base.data_health
empirical_profile = base.empirical_profile
game_for_team = base.game_for_team
logo_url = base.logo_url
official_roster = base.official_roster
player_game_log = base.player_game_log
context_diagnostics = base.context_diagnostics
game_context = base.game_context
clear_context_cache = base.clear_context_cache

__all__ = [
    "OUT_STATUSES", "UNCERTAIN_STATUSES", "player_form_table", "slate_player_pool",
    "team_player_pool", "availability_for_game", "availability_for_game_key",
    "availability_diagnostics", "clear_availability_cache", "schedule_for_date",
    "schedule_diagnostics", "current_season", "logo_url",
]
