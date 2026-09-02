"""Recent-form and stability helpers for MLB Matchup Intelligence V2 Step 10.

Step 10 measures recent hitting form over L5/L10/L20 completed games, then shrinks
short-window results toward the hitter's season baseline. It also tracks strikeout,
contact-quality and expected-contact trends and reports a descriptive stability read.
This layer does not calculate game-level hit probability, fair odds, Monte Carlo
outcomes, calibration or rankings.
"""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any

import pandas as pd
import requests
import streamlit as st

import mlb_matchup_batted_ball_v1 as batted_ball
import mlb_matchup_pitch_mix_v1 as pitch_mix

MLB_API = "https://statsapi.mlb.com/api/v1"
HEADERS = {"User-Agent": "Mozilla/5.0 KyreSportsAI/MatchupV2Step10", "Accept": "application/json"}
WINDOWS = (5, 10, 20)
WINDOW_PRIORS = {5: 45.0, 10: 75.0, 20: 120.0}
WINDOW_BLEND_WEIGHTS = {5: 0.20, 10: 0.35, 20: 0.45}
MIN_LOG_GAMES = 5
FULL_LOG_GAMES = 20
STABILITY_FULL_AB = 80
CONTACT_MIN_BBE = 3


def _float(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _int(value: Any) -> int:
    val = _float(value)
    return int(val) if val is not None else 0


def _rate(value: Any) -> float | None:
    val = _float(value)
    if val is None:
        return None
    if abs(val) > 1.0:
        val /= 100.0
    return max(0.0, min(1.0, val))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, params=params, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_hitter_game_logs(player_id: int, season: int) -> dict[str, Any]:
    """Official MLB regular-season hitter game logs, newest first."""
    try:
        data = _json(
            f"{MLB_API}/people/{int(player_id)}/stats",
            {"stats": "gameLog", "group": "hitting", "season": int(season), "gameType": "R"},
        )
        blocks = data.get("stats") or []
        splits = (blocks[0].get("splits") or []) if blocks else []
    except Exception as exc:
        return {"status": "PENDING", "logs": [], "source": "Official MLB hitter game log unavailable", "error": str(exc)}

    rows: list[dict[str, Any]] = []
    for split in splits:
        stat = split.get("stat") or {}
        game = split.get("game") or {}
        pa = _int(stat.get("plateAppearances"))
        ab = _int(stat.get("atBats"))
        if pa <= 0 and ab <= 0:
            continue
        rows.append(
            {
                "date": str(split.get("date") or "")[:10],
                "game_pk": _int(game.get("gamePk")) or None,
                "pa": pa,
                "ab": ab,
                "hits": _int(stat.get("hits")),
                "strikeouts": _int(stat.get("strikeOuts")),
                "walks": _int(stat.get("baseOnBalls")),
                "home_runs": _int(stat.get("homeRuns")),
            }
        )
    rows.sort(key=lambda row: (row.get("date") or "", row.get("game_pk") or 0), reverse=True)
    return {
        "status": "VERIFIED" if rows else "PENDING",
        "logs": rows,
        "source": "Official MLB hitter game log",
        "error": "" if rows else "no completed hitting logs",
    }


def fetch_recent_statcast(player_id: int, season: int) -> dict[str, Any]:
    """Reuse the certified shared Statcast batter cache instead of another request chain."""
    return batted_ball.fetch_batted_ball_input(int(player_id), int(season))


def pregame_logs(logs: list[dict[str, Any]] | None, game_date: Any) -> list[dict[str, Any]]:
    """Keep completed games strictly before the selected game's date."""
    cutoff = str(game_date or "")[:10]
    rows = list(logs or [])
    if not cutoff:
        return rows
    return [row for row in rows if str(row.get("date") or "")[:10] < cutoff]


def window_reliability(at_bats: int, window: int) -> float:
    ab = max(0, int(at_bats or 0))
    prior = float(WINDOW_PRIORS.get(int(window), 90.0))
    return ab / (ab + prior) if ab > 0 else 0.0


def window_summary(
    logs: list[dict[str, Any]] | None,
    window: int,
    season_avg: float | None,
) -> dict[str, Any]:
    rows = list(logs or [])[: max(1, int(window))]
    games = len(rows)
    pa = sum(_int(row.get("pa")) for row in rows)
    ab = sum(_int(row.get("ab")) for row in rows)
    hits = sum(_int(row.get("hits")) for row in rows)
    strikeouts = sum(_int(row.get("strikeouts")) for row in rows)
    walks = sum(_int(row.get("walks")) for row in rows)
    home_runs = sum(_int(row.get("home_runs")) for row in rows)
    hit_games = sum(1 for row in rows if _int(row.get("hits")) > 0)
    avg = hits / ab if ab > 0 else None
    k_pct = strikeouts / pa if pa > 0 else None
    bb_pct = walks / pa if pa > 0 else None
    hit_game_rate = hit_games / games if games > 0 else None
    hits_per_game = hits / games if games > 0 else None
    reliability = window_reliability(ab, int(window))
    shrunk_avg = None
    if season_avg is not None and avg is not None:
        shrunk_avg = float(season_avg) + reliability * (float(avg) - float(season_avg))
    return {
        "window": int(window),
        "games": games,
        "game_pks": [int(row["game_pk"]) for row in rows if row.get("game_pk")],
        "pa": pa,
        "ab": ab,
        "hits": hits,
        "home_runs": home_runs,
        "strikeouts": strikeouts,
        "walks": walks,
        "hit_games": hit_games,
        "avg": avg,
        "k_pct": k_pct,
        "bb_pct": bb_pct,
        "hit_game_rate": hit_game_rate,
        "hits_per_game": hits_per_game,
        "reliability": reliability,
        "shrunk_avg": shrunk_avg,
        "avg_delta_vs_season": (shrunk_avg - season_avg) if shrunk_avg is not None and season_avg is not None else None,
    }


def _filter_statcast_by_games(frame: pd.DataFrame | None, game_pks: list[int]) -> pd.DataFrame:
    if frame is None or frame.empty or not game_pks or "game_pk" not in frame.columns:
        return pd.DataFrame()
    ids = pd.to_numeric(frame["game_pk"], errors="coerce")
    return frame[ids.isin([int(x) for x in game_pks])].copy()


def contact_summary(frame: pd.DataFrame | None) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {
            "pitches": 0,
            "swings": 0,
            "whiffs": 0,
            "contact_pct": None,
            "whiff_pct": None,
            "bbe": 0,
            "avg_ev": None,
            "hard_hit_pct": None,
            "xba_contact": None,
            "contact_reliability": 0.0,
        }

    descriptions = (
        frame["description"].fillna("").astype(str).str.lower()
        if "description" in frame.columns
        else pd.Series([""] * len(frame), index=frame.index, dtype=str)
    )
    whiffs = int(descriptions.isin(pitch_mix.WHIFF_DESCRIPTIONS).sum())
    contacts = int(descriptions.isin(pitch_mix.SWING_CONTACT_DESCRIPTIONS).sum())
    swings = whiffs + contacts
    contact_pct = contacts / swings if swings > 0 else None
    whiff_pct = whiffs / swings if swings > 0 else None

    ev = pd.to_numeric(frame["launch_speed"], errors="coerce").dropna() if "launch_speed" in frame.columns else pd.Series(dtype=float)
    xba = (
        pd.to_numeric(frame["estimated_ba_using_speedangle"], errors="coerce").dropna()
        if "estimated_ba_using_speedangle" in frame.columns
        else pd.Series(dtype=float)
    )
    bbe = len(ev)
    swing_rel = swings / (swings + 45.0) if swings > 0 else 0.0
    bbe_rel = bbe / (bbe + 30.0) if bbe > 0 else 0.0
    available = [x for x in (swing_rel, bbe_rel) if x > 0]
    reliability = sum(available) / len(available) if available else 0.0
    return {
        "pitches": int(len(frame)),
        "swings": swings,
        "whiffs": whiffs,
        "contact_pct": contact_pct,
        "whiff_pct": whiff_pct,
        "bbe": bbe,
        "avg_ev": float(ev.mean()) if len(ev) >= CONTACT_MIN_BBE else None,
        "hard_hit_pct": float((ev >= batted_ball.HARD_HIT_MPH).mean()) if len(ev) >= CONTACT_MIN_BBE else None,
        "xba_contact": float(xba.mean()) if len(xba) >= CONTACT_MIN_BBE else None,
        "contact_reliability": _clamp(reliability, 0.0, 1.0),
    }


def attach_contact_windows(
    windows: dict[int, dict[str, Any]],
    statcast_frame: pd.DataFrame | None,
) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for window, summary in windows.items():
        frame = _filter_statcast_by_games(statcast_frame, list(summary.get("game_pks") or []))
        out[int(window)] = {**summary, "contact": contact_summary(frame)}
    return out


def _signal(value: float | None, scale: float) -> float | None:
    if value is None or scale <= 0:
        return None
    return _clamp(float(value) / float(scale), -1.0, 1.0)


def _window_form_signal(
    summary: dict[str, Any],
    season_avg: float | None,
    season_k_pct: float | None,
    season_hits_per_game: float | None,
    season_contact: dict[str, Any],
) -> tuple[float | None, float]:
    pieces: list[tuple[float, float]] = []
    reliability = float(summary.get("reliability") or 0.0)
    if season_avg is not None and summary.get("shrunk_avg") is not None:
        s = _signal(float(summary["shrunk_avg"]) - float(season_avg), 0.050)
        if s is not None:
            pieces.append((s, 0.45 * reliability))
    if season_hits_per_game is not None and summary.get("hits_per_game") is not None:
        raw = float(summary["hits_per_game"]) - float(season_hits_per_game)
        s = _signal(raw * reliability, 0.45)
        if s is not None:
            pieces.append((s, 0.15))
    if season_k_pct is not None and summary.get("k_pct") is not None:
        s = _signal((float(season_k_pct) - float(summary["k_pct"])) * reliability, 0.080)
        if s is not None:
            pieces.append((s, 0.15))

    recent_contact = summary.get("contact") or {}
    contact_rel = float(recent_contact.get("contact_reliability") or 0.0)
    recent_xba = _float(recent_contact.get("xba_contact"))
    base_xba = _float(season_contact.get("xba_contact"))
    if recent_xba is not None and base_xba is not None:
        s = _signal((recent_xba - base_xba) * contact_rel, 0.080)
        if s is not None:
            pieces.append((s, 0.15))
    recent_hard = _float(recent_contact.get("hard_hit_pct"))
    base_hard = _float(season_contact.get("hard_hit_pct"))
    if recent_hard is not None and base_hard is not None:
        s = _signal((recent_hard - base_hard) * contact_rel, 0.150)
        if s is not None:
            pieces.append((s, 0.10))

    total = sum(weight for _, weight in pieces)
    if total <= 0:
        return None, 0.0
    return sum(signal * weight for signal, weight in pieces) / total, min(1.0, total)


def recent_form_index(
    windows: dict[int, dict[str, Any]],
    season_avg: float | None,
    season_k_pct: float | None,
    season_hits_per_game: float | None,
    season_contact: dict[str, Any],
) -> dict[str, Any]:
    weighted = 0.0
    total = 0.0
    window_signals: dict[str, Any] = {}
    for window in WINDOWS:
        summary = windows.get(window) or {}
        signal, coverage = _window_form_signal(summary, season_avg, season_k_pct, season_hits_per_game, season_contact)
        window_signals[f"L{window}"] = {"signal": signal, "coverage": coverage}
        if signal is None:
            continue
        weight = WINDOW_BLEND_WEIGHTS[window] * max(0.10, float(summary.get("reliability") or 0.0))
        weighted += float(signal) * weight
        total += weight
    if total <= 0:
        return {"score": None, "label": "PENDING", "coverage": 0.0, "signal": None, "window_signals": window_signals}
    signal = weighted / total
    score = int(round(_clamp(50.0 + 16.0 * signal, 35.0, 65.0)))
    if score >= 60:
        label = "STRONG POSITIVE RECENT FORM"
    elif score >= 54:
        label = "POSITIVE RECENT FORM"
    elif score >= 46:
        label = "NEUTRAL RECENT FORM"
    elif score >= 40:
        label = "COOLING RECENT FORM"
    else:
        label = "COLD RECENT FORM"
    return {
        "score": score,
        "label": label,
        "coverage": _clamp(total / sum(WINDOW_BLEND_WEIGHTS.values()), 0.0, 1.0),
        "signal": signal,
        "window_signals": window_signals,
    }


def stability_index(windows: dict[int, dict[str, Any]]) -> dict[str, Any]:
    avgs = [_float((windows.get(w) or {}).get("shrunk_avg")) for w in WINDOWS]
    ks = [_float((windows.get(w) or {}).get("k_pct")) for w in WINDOWS]
    hard = [_float(((windows.get(w) or {}).get("contact") or {}).get("hard_hit_pct")) for w in WINDOWS]
    xbas = [_float(((windows.get(w) or {}).get("contact") or {}).get("xba_contact")) for w in WINDOWS]
    avgs = [x for x in avgs if x is not None]
    ks = [x for x in ks if x is not None]
    hard = [x for x in hard if x is not None]
    xbas = [x for x in xbas if x is not None]
    if len(avgs) < 2:
        return {"score": None, "label": "LOW SAMPLE", "reliability": 0.0, "avg_spread": None, "k_spread": None}

    avg_spread = max(avgs) - min(avgs)
    k_spread = (max(ks) - min(ks)) if len(ks) >= 2 else 0.0
    hard_spread = (max(hard) - min(hard)) if len(hard) >= 2 else 0.0
    xba_spread = (max(xbas) - min(xbas)) if len(xbas) >= 2 else 0.0
    penalty = (
        _clamp(avg_spread / 0.060, 0.0, 1.5) * 45.0
        + _clamp(k_spread / 0.120, 0.0, 1.5) * 25.0
        + _clamp(hard_spread / 0.200, 0.0, 1.5) * 15.0
        + _clamp(xba_spread / 0.120, 0.0, 1.5) * 15.0
    )
    raw = _clamp(100.0 - penalty, 0.0, 100.0)
    l20_ab = _int((windows.get(20) or {}).get("ab"))
    reliability = _clamp(l20_ab / float(STABILITY_FULL_AB), 0.0, 1.0)
    score = int(round(50.0 + (raw - 50.0) * reliability))
    if l20_ab < 25:
        label = "LOW SAMPLE"
    elif score >= 80:
        label = "VERY STABLE"
    elif score >= 65:
        label = "STABLE"
    elif score >= 50:
        label = "MIXED / MODERATE"
    else:
        label = "VOLATILE"
    return {
        "score": score,
        "label": label,
        "reliability": reliability,
        "raw_score": raw,
        "avg_spread": avg_spread,
        "k_spread": k_spread,
        "hard_hit_spread": hard_spread,
        "xba_contact_spread": xba_spread,
    }


def trend_direction(windows: dict[int, dict[str, Any]]) -> dict[str, Any]:
    l5 = windows.get(5) or {}
    l20 = windows.get(20) or {}
    short = _float(l5.get("shrunk_avg"))
    long = _float(l20.get("shrunk_avg"))
    if short is not None and long is not None:
        delta = short - long
        if delta >= 0.015:
            return {"label": "RISING", "delta": delta}
        if delta <= -0.015:
            return {"label": "COOLING", "delta": delta}
        return {"label": "FLAT", "delta": delta}
    return {"label": "PENDING", "delta": None}


def _data_quality(
    logs_status: str,
    log_games: int,
    windows: dict[int, dict[str, Any]],
    statcast_status: str,
    season_ready: bool,
    asof_ready: bool,
) -> tuple[int, dict[str, tuple[int, int]]]:
    logs = 25 if logs_status == "VERIFIED" and log_games >= FULL_LOG_GAMES else 18 if log_games >= 10 else 10 if log_games >= MIN_LOG_GAMES else 0
    window_points = 0
    for window in WINDOWS:
        games = _int((windows.get(window) or {}).get("games"))
        target = window
        window_points += 10 if games >= target else 5 if games >= max(3, target // 2) else 0
    statcast = 15 if statcast_status == "VERIFIED" else 0
    contact = 0
    for window in WINDOWS:
        bbe = _int(((windows.get(window) or {}).get("contact") or {}).get("bbe"))
        if bbe >= CONTACT_MIN_BBE:
            contact += 5
    season = 10 if season_ready else 0
    asof = 5 if asof_ready else 0
    components = {
        "Official hitter logs": (logs, 25),
        "L5/L10/L20 windows": (window_points, 30),
        "Shared Statcast feed": (statcast, 15),
        "Recent contact samples": (contact, 15),
        "Season baseline": (season, 10),
        "Pregame as-of filter": (asof, 5),
    }
    return sum(v[0] for v in components.values()), components


def data_label(score: int) -> str:
    if score >= 90:
        return "ELITE RECENT-FORM DATA"
    if score >= 75:
        return "STRONG RECENT-FORM DATA"
    if score >= 60:
        return "USABLE RECENT-FORM DATA"
    if score >= 40:
        return "PARTIAL RECENT-FORM DATA"
    return "LOW RECENT-FORM DATA"


def readiness_label(log_games: int, season_avg: float | None, statcast_status: str) -> str:
    if season_avg is None or log_games < MIN_LOG_GAMES:
        return "GATED"
    if log_games >= 20 and statcast_status == "VERIFIED":
        return "READY"
    if log_games >= 10:
        return "USABLE"
    return "PARTIAL"


def build_recent_stability_profile(
    foundation: dict[str, Any],
    logs_payload: dict[str, Any] | None,
    statcast_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    logs_payload = logs_payload or {}
    statcast_payload = statcast_payload or {}
    season_stat = foundation.get("season_stat") or {}
    season_avg = _rate(season_stat.get("avg"))
    season_pa = _int(season_stat.get("plateAppearances"))
    season_hits = _int(season_stat.get("hits"))
    season_games = _int(season_stat.get("gamesPlayed"))
    season_k = _int(season_stat.get("strikeOuts"))
    season_k_pct = season_k / season_pa if season_pa > 0 else None
    season_hits_per_game = season_hits / season_games if season_games > 0 else None

    game_date = str(foundation.get("game_date") or "")[:10]
    logs = pregame_logs(list(logs_payload.get("logs") or []), game_date)
    base_windows = {window: window_summary(logs, window, season_avg) for window in WINDOWS}

    statcast_verified = statcast_payload.get("status") == "VERIFIED"
    frame = statcast_payload.get("frame") if statcast_verified else None
    completed_game_pks = [int(row["game_pk"]) for row in logs if row.get("game_pk")]
    pregame_frame = _filter_statcast_by_games(frame, completed_game_pks) if completed_game_pks else pd.DataFrame()
    windows = attach_contact_windows(base_windows, pregame_frame)
    season_contact = contact_summary(pregame_frame)

    form = recent_form_index(windows, season_avg, season_k_pct, season_hits_per_game, season_contact)
    stability = stability_index(windows)
    trend = trend_direction(windows)
    asof_ready = bool(game_date and logs_payload.get("status") == "VERIFIED")
    data_score, components = _data_quality(
        str(logs_payload.get("status") or "PENDING"),
        len(logs),
        windows,
        str(statcast_payload.get("status") or "PENDING"),
        season_avg is not None and season_pa > 0,
        asof_ready,
    )

    return {
        **foundation,
        "recent_readiness": readiness_label(len(logs), season_avg, str(statcast_payload.get("status") or "PENDING")),
        "recent_logs_status": logs_payload.get("status") or "PENDING",
        "recent_logs_source": logs_payload.get("source") or "UNAVAILABLE",
        "recent_log_games": len(logs),
        "recent_asof_date": game_date,
        "recent_statcast_status": statcast_payload.get("status") or "PENDING",
        "recent_statcast_source": "Shared certified Baseball Savant / Statcast batter feed" if statcast_verified else "UNAVAILABLE",
        "season_avg_step10": season_avg,
        "season_k_pct_step10": season_k_pct,
        "season_hits_per_game_step10": season_hits_per_game,
        "season_contact_step10": season_contact,
        "windows": windows,
        "l5": windows.get(5) or {},
        "l10": windows.get(10) or {},
        "l20": windows.get(20) or {},
        "recent_form_score": form.get("score"),
        "recent_form_label": form.get("label"),
        "recent_form_signal": form.get("signal"),
        "recent_form_coverage": form.get("coverage"),
        "recent_window_signals": form.get("window_signals"),
        "stability_score": stability.get("score"),
        "stability_label": stability.get("label"),
        "stability_reliability": stability.get("reliability"),
        "avg_window_spread": stability.get("avg_spread"),
        "k_window_spread": stability.get("k_spread"),
        "hard_hit_window_spread": stability.get("hard_hit_spread"),
        "xba_contact_window_spread": stability.get("xba_contact_spread"),
        "trend_label": trend.get("label"),
        "trend_delta": trend.get("delta"),
        "recent_data_score": int(data_score),
        "recent_data_label": data_label(int(data_score)),
        "recent_data_components": components,
        "recent_sample_note": "L5/L10/L20 batting averages are shrunk toward the pregame season baseline using window-specific AB priors; shorter windows receive less authority.",
    }


__all__ = [
    "CONTACT_MIN_BBE",
    "FULL_LOG_GAMES",
    "MIN_LOG_GAMES",
    "STABILITY_FULL_AB",
    "WINDOWS",
    "WINDOW_BLEND_WEIGHTS",
    "WINDOW_PRIORS",
    "attach_contact_windows",
    "build_recent_stability_profile",
    "contact_summary",
    "data_label",
    "fetch_hitter_game_logs",
    "fetch_recent_statcast",
    "pregame_logs",
    "readiness_label",
    "recent_form_index",
    "stability_index",
    "trend_direction",
    "window_reliability",
    "window_summary",
]
