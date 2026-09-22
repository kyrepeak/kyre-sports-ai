"""WNBA schedule V2.5 — Eastern-date reconciliation for isolated Points work.

This module fixes a V2.4 slate-date bug without modifying the frozen PRA stack.
Official WNBA CDN timestamps are converted to America/New_York BEFORE selecting
which calendar slate they belong to. It also reconciles official CDN, ESPN daily
and ESPN season results by matchup identity instead of blindly choosing the first
non-empty source.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import wnba_schedule_v24 as v24

ET = v24.ET
WNBA_CDN = v24.WNBA_CDN
ESPN_SCOREBOARD = v24.ESPN_SCOREBOARD
SCHEDULE_COLUMNS = v24.SCHEDULE_COLUMNS


def _empty_schedule():
    return v24._empty_schedule()


def _cdn_game_date(game: dict, block_date) -> str:
    utc_value = game.get("gameDateTimeUTC")
    if utc_value:
        return v24._event_date_et(utc_value)
    est_value = game.get("gameDateTimeEst")
    if est_value:
        return v24.transport.base._safe_date(est_value) or ""
    return v24.transport.base._safe_date(block_date) or ""


def _parse_cdn(payload):
    league = (payload or {}).get("leagueSchedule") or {}
    rows, raw_games, rejected = [], 0, 0
    for block in league.get("gameDates", []) or []:
        block_date = block.get("gameDate")
        for game in block.get("games", []) or []:
            raw_games += 1
            away, home = game.get("awayTeam") or {}, game.get("homeTeam") or {}
            away_team = {
                "abbreviation": away.get("teamTricode"),
                "displayName": v24.transport.base._team_name(away),
                "name": v24.transport.base._team_name(away),
            }
            home_team = {
                "abbreviation": home.get("teamTricode"),
                "displayName": v24.transport.base._team_name(home),
                "name": v24.transport.base._team_name(home),
            }
            away_id = v24._safe_team_id(away_team, away.get("teamId"))
            home_id = v24._safe_team_id(home_team, home.get("teamId"))
            if not v24.guarded._is_wnba_team_id(away_id) or not v24.guarded._is_wnba_team_id(home_id):
                rejected += 1
                continue
            rows.append({
                "game_id": str(game.get("gameId") or game.get("gameID") or ""),
                "game_date": _cdn_game_date(game, block_date),
                "first_tip_et": v24.transport._tip_et(game),
                "status": v24.transport.base._status_bucket(game.get("gameStatus"), game.get("gameStatusText")),
                "status_text": str(game.get("gameStatusText") or ""),
                "away_team_id": away_id,
                "away_team": v24.transport.base._team_name(away),
                "away_tricode": str(away.get("teamTricode") or ""),
                "home_team_id": home_id,
                "home_team": v24.transport.base._team_name(home),
                "home_tricode": str(home.get("teamTricode") or ""),
                "venue": str(game.get("arenaName") or game.get("arenaCity") or "Venue TBD"),
                "source": "WNBA official CDN • ET-date corrected",
            })
    frame = v24.guarded._guard_schedule(pd.DataFrame(rows)) if rows else _empty_schedule()
    return frame, {"raw_games": raw_games, "valid_games": len(frame), "rejected_games": rejected}


def _selected(frame, day_str):
    return v24._selected(frame, day_str)


def _sig(row):
    try:
        return (int(row.get("away_team_id") or 0), int(row.get("home_team_id") or 0))
    except Exception:
        return (str(row.get("away_team") or ""), str(row.get("home_team") or ""))


def _reconcile(candidates):
    """Return consensus slate. Two-source agreement wins; official row wins fields."""
    if not candidates:
        return _empty_schedule(), [], "none", []

    support = {}
    rows_by_sig = {}
    source_names = []
    for priority, frame, source in candidates:
        source_names.append(source)
        seen = set()
        for _, row in frame.iterrows():
            sig = _sig(row)
            rows_by_sig.setdefault(sig, []).append((priority, source, row))
            if sig not in seen:
                support[sig] = support.get(sig, 0) + 1
                seen.add(sig)

    if len(source_names) >= 2:
        keep = {sig for sig, n in support.items() if n >= 2}
    else:
        keep = set(support)

    # Safety fallback: if providers disagree so much that consensus is empty,
    # choose the source with the most selected games, then priority.
    if not keep:
        best = sorted(candidates, key=lambda x: (-len(x[1]), x[0]))[0]
        return best[1].reset_index(drop=True), source_names, best[2], []

    chosen_rows = []
    for sig in sorted(keep):
        variants = sorted(rows_by_sig[sig], key=lambda x: x[0])
        chosen_rows.append(variants[0][2].to_dict())

    frame = pd.DataFrame(chosen_rows)
    if not frame.empty:
        frame = v24.guarded._guard_schedule(frame).reset_index(drop=True)
    rejected_sigs = [sig for sig, n in support.items() if sig not in keep]
    chosen = "reconciled WNBA/ESPN consensus"
    return frame, source_names, chosen, rejected_sigs


@st.cache_data(ttl=180, show_spinner=False)
def _verified_schedule(day_str: str):
    day_str = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    year = pd.to_datetime(day_str).year
    attempts = []
    selected_candidates = []
    season_sources_ok = 0

    payload, meta = v24._request_json("WNBA official CDN", WNBA_CDN, timeout=8, attempts=2)
    if payload is not None:
        frame, counts = _parse_cdn(payload)
        selected = _selected(frame, day_str)
        meta.update(counts)
        meta.update({"selected_games": len(selected), "parse_ok": True})
        if len(frame):
            season_sources_ok += 1
        if len(selected):
            selected_candidates.append((0, selected, "WNBA official CDN"))
    else:
        meta.update({"raw_games": 0, "valid_games": 0, "rejected_games": 0, "selected_games": 0, "parse_ok": False})
    attempts.append(meta)

    payload, meta = v24._request_json(
        "ESPN WNBA daily", ESPN_SCOREBOARD,
        params={"dates": pd.to_datetime(day_str).strftime("%Y%m%d"), "limit": 100},
        timeout=8, attempts=2,
    )
    if payload is not None:
        frame, counts = v24._parse_espn(payload, "ESPN WNBA daily fallback")
        selected = _selected(frame, day_str)
        meta.update(counts)
        meta.update({"selected_games": len(selected), "parse_ok": True})
        if len(selected):
            selected_candidates.append((1, selected, "ESPN WNBA daily"))
    else:
        meta.update({"raw_games": 0, "valid_games": 0, "rejected_games": 0, "selected_games": 0, "parse_ok": False})
    attempts.append(meta)

    payload, meta = v24._request_json(
        "ESPN WNBA season", ESPN_SCOREBOARD,
        params={"dates": str(year), "limit": 1000}, timeout=10, attempts=2,
    )
    if payload is not None:
        frame, counts = v24._parse_espn(payload, "ESPN WNBA season fallback")
        selected = _selected(frame, day_str)
        meta.update(counts)
        meta.update({"selected_games": len(selected), "parse_ok": True})
        if len(frame):
            season_sources_ok += 1
        if len(selected):
            selected_candidates.append((2, selected, "ESPN WNBA season"))
    else:
        meta.update({"raw_games": 0, "valid_games": 0, "rejected_games": 0, "selected_games": 0, "parse_ok": False})
    attempts.append(meta)

    if selected_candidates:
        schedule, confirming, chosen, rejected_sigs = _reconcile(selected_candidates)
        state = "VERIFIED" if len(confirming) >= 2 else "VERIFIED_SINGLE_SOURCE"
    elif season_sources_ok:
        schedule, confirming, chosen, rejected_sigs = _empty_schedule(), [], "season schedule verification", []
        state = "VERIFIED_OFF_DAY"
    else:
        schedule, confirming, chosen, rejected_sigs = _empty_schedule(), [], "none", []
        state = "PROVIDER_FAILURE"

    valid_team_ids = set()
    if not schedule.empty:
        valid_team_ids.update(schedule["away_team_id"].astype(int).tolist())
        valid_team_ids.update(schedule["home_team_id"].astype(int).tolist())

    diagnostics = {
        "selected_date": day_str,
        "state": state,
        "games": len(schedule),
        "teams": len(valid_team_ids),
        "chosen_source": chosen,
        "confirming_sources": confirming,
        "season_sources_ok": season_sources_ok,
        "attempts": attempts,
        "source_selected_counts": {m.get("provider"): int(m.get("selected_games") or 0) for m in attempts},
        "rejected_single_source_matchups": len(rejected_sigs),
        "timezone_rule": "America/New_York slate date",
    }
    return schedule, diagnostics


def schedule_for_date(day: str | date):
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    schedule, _ = _verified_schedule(day_str)
    return v24.guarded._guard_schedule(schedule)


def schedule_diagnostics(day: str | date):
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    _, diagnostics = _verified_schedule(day_str)
    return diagnostics


def clear_schedule_cache():
    try:
        _verified_schedule.clear()
    except Exception:
        st.cache_data.clear()


# Shared non-schedule helpers remain unchanged and are read-only.
current_season = v24.current_season
empirical_profile = v24.empirical_profile
game_for_team = v24.game_for_team
logo_url = v24.logo_url
official_roster = v24.official_roster
player_form_table = v24.player_form_table
player_game_log = v24.player_game_log
slate_player_pool = v24.slate_player_pool
team_player_pool = v24.team_player_pool
