"""WNBA Live Games Step 5 context engine.

Read-only live context layered on top of the frozen Steps 1-4 contracts.
Provides:
- verified current-season H2H final/Q3/Q4/second-half history;
- current ESPN-reported injury/availability designations with source coverage;
- explicit live starter flags and players who have entered the current game;
- last verified starters from each team's most recent completed game.

Nothing in this module creates or changes a moneyline/spread/total projection,
probability, Monte Carlo result, edge, EV, qualification, ranking or pick.
"""
from __future__ import annotations

from datetime import datetime
import math
import re
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_availability_v33 as availability
import wnba_data_v232 as data232
import wnba_live_flow_v1 as flow
import wnba_live_second_half_v14 as hist14

ET = ZoneInfo("America/New_York")
MODEL_VERSION = "WNBA LIVE CONTEXT V1 • STEP 5 H2H + ROSTER + AVAILABILITY"


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _safe_float(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _team_id(team: dict) -> int:
    try:
        return int(data232._team_id(team or {}) or 0)
    except Exception:
        return 0


def _period(lines: dict, p: int) -> int:
    try:
        return int(lines.get(p) or 0)
    except Exception:
        return 0


def _team_view(row: dict, team_id: int) -> dict | None:
    away_id = _safe_int(row.get("away_team_id"))
    home_id = _safe_int(row.get("home_team_id"))
    if int(team_id) not in {away_id, home_id}:
        return None
    is_away = int(team_id) == away_id
    own_score = _safe_int(row.get("away_score") if is_away else row.get("home_score"))
    opp_score = _safe_int(row.get("home_score") if is_away else row.get("away_score"))
    own_lines = row.get("away_lines") if is_away else row.get("home_lines")
    opp_lines = row.get("home_lines") if is_away else row.get("away_lines")
    own_lines, opp_lines = own_lines or {}, opp_lines or {}
    q3 = _period(own_lines, 3) - _period(opp_lines, 3)
    q4 = _period(own_lines, 4) - _period(opp_lines, 4)
    h2 = q3 + q4
    opp_id = home_id if is_away else away_id
    opp_name = str(row.get("home_team") if is_away else row.get("away_team") or "Opponent")
    return {
        "team_id": int(team_id),
        "opponent_id": opp_id,
        "opponent": opp_name,
        "venue": "AWAY" if is_away else "HOME",
        "score_for": own_score,
        "score_against": opp_score,
        "margin": own_score - opp_score,
        "q3_margin": q3,
        "q4_margin": q4,
        "h2_margin": h2,
        "total": own_score + opp_score,
        "win": own_score > opp_score,
        "date": row.get("game_date_et") or row.get("date_utc"),
        "event_id": str(row.get("event_id") or ""),
    }


def _h2h_summary(rows: list[dict], away_id: int, home_id: int) -> dict:
    pair = {int(away_id), int(home_id)}
    h2h = [
        r for r in rows
        if {int(r.get("away_team_id") or 0), int(r.get("home_team_id") or 0)} == pair
    ]
    h2h = sorted(h2h, key=lambda r: str(r.get("date_utc") or ""), reverse=True)
    away_views = [x for x in (_team_view(r, away_id) for r in h2h) if x]
    home_views = [x for x in (_team_view(r, home_id) for r in h2h) if x]

    def avg(items, key):
        vals = [_safe_float(x.get(key)) for x in items]
        vals = [x for x in vals if x is not None]
        return sum(vals) / len(vals) if vals else None

    n = len(h2h)
    reliability = "HIGH" if n >= 5 else ("MEDIUM" if n >= 3 else ("LOW" if n >= 1 else "NONE"))
    return {
        "games": n,
        "reliability": reliability,
        "away_wins": sum(1 for x in away_views if x["win"]),
        "away_losses": sum(1 for x in away_views if not x["win"]),
        "home_wins": sum(1 for x in home_views if x["win"]),
        "home_losses": sum(1 for x in home_views if not x["win"]),
        "away_avg_margin": avg(away_views, "margin"),
        "away_avg_h2_margin": avg(away_views, "h2_margin"),
        "away_avg_q3_margin": avg(away_views, "q3_margin"),
        "away_avg_q4_margin": avg(away_views, "q4_margin"),
        "avg_total": avg(away_views, "total"),
        "last5": away_views[:5],
    }


def _stat_labels(block: dict) -> list[str]:
    labels = block.get("labels") or block.get("names") or block.get("abbreviations") or []
    return [str(x or "") for x in labels]


def _minutes_from_entry(entry: dict, labels: list[str]):
    stats = entry.get("stats") or entry.get("statistics") or []
    if isinstance(stats, dict):
        stats = stats.get("stats") or stats.get("values") or []
    if not isinstance(stats, list):
        return None
    idx = None
    for i, label in enumerate(labels):
        if _norm(label) in {"min", "minutes"}:
            idx = i
            break
    if idx is None or idx >= len(stats):
        return None
    text = str(stats[idx] or "").strip()
    try:
        if ":" in text:
            mm, ss = text.split(":", 1)
            return float(mm) + float(ss) / 60.0
        return float(text)
    except Exception:
        return None


def _live_rotation(payload: dict, target_ids: tuple[int, ...]) -> dict[int, list[dict]]:
    out = {int(t): [] for t in target_ids}
    blocks = (((payload or {}).get("boxscore") or {}).get("players") or [])
    for block in blocks:
        if not isinstance(block, dict):
            continue
        tid = _team_id(block.get("team") or {})
        if tid not in out:
            continue
        for stat_block in block.get("statistics") or []:
            if not isinstance(stat_block, dict):
                continue
            labels = _stat_labels(stat_block)
            for entry in stat_block.get("athletes") or []:
                if not isinstance(entry, dict):
                    continue
                athlete = entry.get("athlete") if isinstance(entry.get("athlete"), dict) else {}
                name = athlete.get("displayName") or athlete.get("fullName") or entry.get("displayName")
                if not name:
                    continue
                dnp = bool(entry.get("didNotPlay"))
                mins = _minutes_from_entry(entry, labels)
                stats = entry.get("stats") or entry.get("statistics") or []
                entered = (mins is not None and mins > 0) or (not dnp and isinstance(stats, list) and any(str(x or "").strip() not in {"", "0", "0.0", "--"} for x in stats))
                if not entered:
                    continue
                out[tid].append({
                    "player_id": str(athlete.get("id") or entry.get("id") or ""),
                    "name": str(name),
                    "starter": bool(entry.get("starter") is True or athlete.get("starter") is True),
                    "minutes": mins,
                })
    for tid in list(out):
        dedup = {}
        for row in out[tid]:
            dedup[_norm(row["name"])] = row
        out[tid] = sorted(dedup.values(), key=lambda x: (not x.get("starter"), -(x.get("minutes") or 0), x["name"]))
    return out


def _starters_from_payload(payload: dict, team_ids: tuple[int, ...]) -> dict[int, list[str]]:
    out = {int(t): [] for t in team_ids}
    try:
        rows = availability._walk_starters(payload)
    except Exception:
        rows = []
    for row in rows:
        tid = _safe_int(row.get("TEAM_ID"))
        name = str(row.get("PLAYER_NAME") or "").strip()
        if tid in out and name and name not in out[tid]:
            out[tid].append(name)
    return out


def _latest_prior_starters(history_rows: list[dict], team_id: int) -> dict:
    candidates = [r for r in history_rows if int(team_id) in {int(r.get("away_team_id") or 0), int(r.get("home_team_id") or 0)}]
    candidates = sorted(candidates, key=lambda r: str(r.get("date_utc") or ""), reverse=True)
    for row in candidates[:5]:
        event_id = str(row.get("event_id") or "")
        if not event_id:
            continue
        payload, meta = flow.espn_summary(event_id)
        if not payload:
            continue
        starters = _starters_from_payload(payload, (int(team_id),)).get(int(team_id), [])
        if starters:
            return {
                "event_id": event_id,
                "date": row.get("game_date_et") or row.get("date_utc"),
                "opponent": (_team_view(row, int(team_id)) or {}).get("opponent") or "Opponent",
                "starters": starters,
                "source_ok": True,
            }
    return {"event_id": "", "date": "", "opponent": "", "starters": [], "source_ok": False}


def _availability_context(game: dict) -> dict:
    away_id = _safe_int(game.get("away_team_id"))
    home_id = _safe_int(game.get("home_team_id"))
    event_id = str(game.get("espn_event_id") or "")
    day = pd.to_datetime(game.get("captured_at") or datetime.now(ET).isoformat(), utc=True).tz_convert(ET).strftime("%Y-%m-%d")
    try:
        raw = availability.availability_for_game_key(event_id, away_id, home_id, day)
    except Exception as exc:
        return {
            "injuries": [], "starters": [], "summary_connected": False,
            "team_feeds_connected": 0, "team_status_coverage": {away_id: False, home_id: False},
            "source": "ESPN WNBA availability", "error": str(exc)[:220],
        }
    raw = dict(raw or {})
    raw.setdefault("error", "")
    return raw


def context_for_game(game: dict) -> dict:
    captured = pd.to_datetime(game.get("captured_at") or datetime.now(ET).isoformat(), utc=True)
    year = captured.tz_convert(ET).year
    cutoff_day = captured.tz_convert(ET).strftime("%Y-%m-%d")
    away_id = _safe_int(game.get("away_team_id"))
    home_id = _safe_int(game.get("home_team_id"))
    event_id = str(game.get("espn_event_id") or "")

    try:
        history_rows, history_meta = hist14._history(year, (away_id, home_id), cutoff_day, event_id)
    except Exception as exc:
        history_rows, history_meta = [], {"error": str(exc)[:220]}

    h2h = _h2h_summary(history_rows, away_id, home_id)
    avail = _availability_context(game)

    payload, summary_meta = flow.espn_summary(event_id) if event_id else ({}, {"available": False, "error": "missing event id"})
    rotations = _live_rotation(payload, (away_id, home_id)) if payload else {away_id: [], home_id: []}
    current_starters = _starters_from_payload(payload, (away_id, home_id)) if payload else {away_id: [], home_id: []}

    # Availability parser may find an explicit starter flag in a part of the
    # summary not represented by boxscore.players. Merge without inference.
    for row in avail.get("starters") or []:
        tid = _safe_int(row.get("TEAM_ID"))
        name = str(row.get("PLAYER_NAME") or "").strip()
        if tid in current_starters and name and name not in current_starters[tid]:
            current_starters[tid].append(name)

    last_starters = {
        away_id: _latest_prior_starters(history_rows, away_id),
        home_id: _latest_prior_starters(history_rows, home_id),
    }

    return {
        "h2h": h2h,
        "history_meta": history_meta,
        "availability": avail,
        "current_summary_meta": summary_meta,
        "rotation": rotations,
        "current_starters": current_starters,
        "last_starters": last_starters,
        "fetched_at": datetime.now(ET).isoformat(),
    }


def clear_cache():
    try:
        availability.clear_availability_cache()
    except Exception:
        pass
    try:
        flow.clear_cache()
    except Exception:
        pass
    try:
        hist14.clear_cache()
    except Exception:
        pass


__all__ = ["MODEL_VERSION", "context_for_game", "clear_cache"]
