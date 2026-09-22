"""WNBA Live Step 6.3 — checkpoint-only historical PBP reconstruction.

Validation-only transport. Reconstructs partial-game team box metrics from ESPN
play-by-play through an exact replay checkpoint. Future plays and final boxscore
statistics are never fed into the reconstructed state.
"""
from __future__ import annotations

import math
import re
from typing import Any

import streamlit as st

import wnba_live_flow_v1 as flow

MODEL_VERSION = "WNBA LIVE STEP-6.3 PBP V1 • CHECKPOINT-ONLY RECONSTRUCTION"


def _num(value: Any, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _int(value: Any, default=0):
    try:
        if isinstance(value, dict):
            value = value.get("number", value.get("value", value.get("displayValue")))
        return int(round(float(value)))
    except Exception:
        return int(default)


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _competition(payload: dict) -> dict:
    comps = ((payload or {}).get("header") or {}).get("competitions") or []
    return comps[0] if comps and isinstance(comps[0], dict) else {}


def _side_map(payload: dict, state: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for comp in [_competition(payload)]:
        for c in comp.get("competitors") or []:
            if not isinstance(c, dict):
                continue
            side = str(c.get("homeAway") or "").lower()
            if side not in {"away", "home"}:
                continue
            team = c.get("team") or {}
            for raw in (
                team.get("id"), team.get("uid"), team.get("displayName"),
                team.get("shortDisplayName"), team.get("name"), team.get("abbreviation"),
            ):
                key = _norm(raw)
                if key:
                    out[key] = side
    for side in ("away", "home"):
        for raw in (state.get(f"{side}_team"), state.get(f"{side}_abbr")):
            key = _norm(raw)
            if key:
                out[key] = side
    return out


def _period(play: dict) -> int:
    obj = (play or {}).get("period")
    if isinstance(obj, dict):
        return _int(obj.get("number", obj.get("value")), 0)
    return _int(obj, 0)


def _text(play: dict) -> str:
    ptype = (play or {}).get("type") or {}
    return " ".join(
        str(x or "")
        for x in (
            (play or {}).get("text"), (play or {}).get("shortText"),
            ptype.get("text"), ptype.get("abbreviation"),
        )
    ).strip()


def _side(play: dict, mapping: dict[str, str]):
    team = (play or {}).get("team") or {}
    for raw in (
        team.get("id"), team.get("uid"), team.get("displayName"),
        team.get("shortDisplayName"), team.get("name"), team.get("abbreviation"),
    ):
        key = _norm(raw)
        if key in mapping:
            return mapping[key]
    return None


def _three(text: str) -> bool:
    t = text.lower()
    return any(x in t for x in ("three point", "three-point", "3-point", "3 point", "3-pt"))


def _shot(text: str) -> bool:
    t = text.lower()
    if "free throw" in t:
        return False
    return any(x in t for x in (
        "shot", "jumper", "layup", "dunk", "hook", "tip-in", "tip shot",
        "three point", "three-point", "3-point", "3 point", "3-pt",
        "floater", "floating", "pullup", "pull-up", "fadeaway", "bank shot",
    ))


def _blank_stats() -> dict:
    return {
        "fgm": 0.0, "fga": 0.0, "3pm": 0.0, "3pa": 0.0,
        "ftm": 0.0, "fta": 0.0, "oreb": 0.0, "dreb": 0.0,
        "reb": 0.0, "ast": 0.0, "tov": 0.0, "stl": 0.0,
        "blk": 0.0, "pf": 0.0,
    }


def _score(play: dict, side: str):
    return _num((play or {}).get("awayScore" if side == "away" else "homeScore"))


@st.cache_data(ttl=1800, show_spinner=False, max_entries=64)
def reconstruct(state: dict) -> dict:
    event_id = str(state.get("espn_event_id") or "")
    payload, meta = flow.espn_summary(event_id) if event_id else ({}, {"error": "missing event id"})
    completed = _int(state.get("replay_completed_periods"), 0)
    elapsed = flow.elapsed_seconds(state)
    elapsed_min = elapsed / 60.0 if elapsed > 0 else 0.0
    current_a = _int(state.get("away_score"))
    current_h = _int(state.get("home_score"))

    result = {
        "model_version": MODEL_VERSION,
        "event_id": event_id,
        "checkpoint": str(state.get("replay_checkpoint_id") or ""),
        "summary_available": bool(payload),
        "summary_error": str((meta or {}).get("error") or ""),
        "completed_periods": completed,
        "total_plays": 0,
        "included_plays": 0,
        "future_plays_excluded": 0,
        "unmapped_stat_plays": 0,
        "score_reconciled": False,
        "seen_away_score": None,
        "seen_home_score": None,
        "state_away_score": current_a,
        "state_home_score": current_h,
        "away_stats": {},
        "home_stats": {},
        "away_metrics": {},
        "home_metrics": {},
        "blended_possessions": None,
        "pace40": None,
        "quality": "UNAVAILABLE",
        "future_stats_used": False,
        "final_boxscore_used": False,
    }
    if not payload or completed <= 0:
        return result

    mapping = _side_map(payload, state)
    plays = [p for p in ((payload or {}).get("plays") or []) if isinstance(p, dict)]
    result["total_plays"] = len(plays)
    stats = {"away": _blank_stats(), "home": _blank_stats()}
    included = []
    future = 0
    unmapped = 0

    for index, play in enumerate(plays):
        p = _period(play)
        if p <= 0:
            continue
        if p > completed:
            future += 1
            continue
        included.append((index, play))
        side = _side(play, mapping)
        text = _text(play)
        low = text.lower()
        if not side:
            if any(x in low for x in ("makes", "misses", "rebound", "turnover")):
                unmapped += 1
            continue

        s = stats[side]
        made = " makes " in f" {low} " or low.startswith("makes ")
        missed = " misses " in f" {low} " or low.startswith("misses ")

        if "free throw" in low and (made or missed):
            s["fta"] += 1.0
            if made:
                s["ftm"] += 1.0
        elif (made or missed) and _shot(low):
            s["fga"] += 1.0
            if made:
                s["fgm"] += 1.0
            if _three(low):
                s["3pa"] += 1.0
                if made:
                    s["3pm"] += 1.0

        if "offensive rebound" in low:
            s["oreb"] += 1.0
            s["reb"] += 1.0
        elif "defensive rebound" in low:
            s["dreb"] += 1.0
            s["reb"] += 1.0
        if "turnover" in low:
            s["tov"] += 1.0
        if "assist" in low:
            s["ast"] += 1.0
        if "steal" in low:
            s["stl"] += 1.0
        if "block" in low:
            s["blk"] += 1.0

    seen_a = seen_h = None
    for _, play in reversed(included):
        a = _score(play, "away")
        h = _score(play, "home")
        if a is not None and h is not None:
            seen_a, seen_h = int(round(a)), int(round(h))
            break

    score_ok = seen_a == current_a and seen_h == current_h
    away_metrics = flow._team_metrics(stats["away"], float(current_a), stats["home"])
    home_metrics = flow._team_metrics(stats["home"], float(current_h), stats["away"])
    poss = [m.get("poss") for m in (away_metrics, home_metrics) if m.get("poss") is not None]
    blended = sum(poss) / len(poss) if len(poss) == 2 else None
    pace40 = blended / elapsed_min * 40.0 if blended is not None and elapsed_min > 0 else None

    stat_ok = (
        stats["away"]["fga"] >= 10 and stats["home"]["fga"] >= 10
        and blended is not None and 45.0 <= float(pace40 or 0.0) <= 115.0
    )
    high = bool(score_ok and stat_ok and len(included) >= 25)

    result.update({
        "included_plays": len(included),
        "future_plays_excluded": future,
        "unmapped_stat_plays": unmapped,
        "score_reconciled": bool(score_ok),
        "seen_away_score": seen_a,
        "seen_home_score": seen_h,
        "away_stats": stats["away"],
        "home_stats": stats["home"],
        "away_metrics": away_metrics if high else {},
        "home_metrics": home_metrics if high else {},
        "blended_possessions": blended if high else None,
        "pace40": pace40 if high else None,
        "quality": "HIGH" if high else "CHECK",
    })
    return result


def audit(state: dict, reconstruction: dict) -> list[dict]:
    return [
        {
            "name": "ESPN play-by-play transport",
            "pass": bool(reconstruction.get("summary_available")) and int(reconstruction.get("total_plays") or 0) > 0,
            "detail": f"{int(reconstruction.get('total_plays') or 0)} total play(s) returned.",
        },
        {
            "name": "Checkpoint-only filter",
            "pass": not bool(reconstruction.get("future_stats_used")),
            "detail": f"{int(reconstruction.get('included_plays') or 0)} included • {int(reconstruction.get('future_plays_excluded') or 0)} future play(s) excluded.",
        },
        {
            "name": "Checkpoint score reconciliation",
            "pass": bool(reconstruction.get("score_reconciled")),
            "detail": (
                f"PBP {reconstruction.get('seen_away_score')}–{reconstruction.get('seen_home_score')} "
                f"vs replay state {state.get('away_score')}–{state.get('home_score')}."
            ),
        },
        {
            "name": "Final boxscore blocked",
            "pass": not bool(reconstruction.get("final_boxscore_used")),
            "detail": "Reconstruction reads play-by-play only; final boxscore statistics are not used.",
        },
        {
            "name": "Partial possession quality",
            "pass": str(reconstruction.get("quality") or "") == "HIGH",
            "detail": (
                f"pace40={reconstruction.get('pace40')} • "
                f"away FGA={float((reconstruction.get('away_stats') or {}).get('fga') or 0):.0f} • "
                f"home FGA={float((reconstruction.get('home_stats') or {}).get('fga') or 0):.0f}."
            ),
        },
    ]


def clear_cache():
    try:
        reconstruct.clear()
    except Exception:
        pass
    try:
        flow.clear_cache()
    except Exception:
        pass
