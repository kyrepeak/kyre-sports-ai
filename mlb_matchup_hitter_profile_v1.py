"""Hitter true-talent profile helpers for MLB Matchup Intelligence V2 Step 2.

This module is intentionally player-skill only. It may estimate a neutral hitting
skill baseline from season results, Statcast expected statistics and sample-shrunk
recent form, but it does not calculate a game-level 1+ hit probability, matchup
adjustment, fair odds, ranking or Monte Carlo result.
"""
from __future__ import annotations

from io import StringIO
import math
import re
from typing import Any

import pandas as pd
import requests
import streamlit as st

SAVANT = "https://baseballsavant.mlb.com"
SAVANT_CUSTOM = f"{SAVANT}/leaderboard/custom"
SAVANT_SELECTIONS = (
    "ab",
    "pa",
    "hit",
    "strikeout",
    "k_percent",
    "batting_avg",
    "xba",
    "xbacon",
    "xbadiff",
    "exit_velocity_avg",
    "barrel_batted_rate",
    "hard_hit_percent",
    "iz_contact_percent",
    "whiff_percent",
    "swing_percent",
    "batted_ball",
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 KyreSportsAI/MatchupV2Step2",
    "Accept": "text/csv,text/plain,*/*",
}


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


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    available = {_norm(c): c for c in df.columns}
    for alias in aliases:
        key = _norm(alias)
        if key in available:
            return available[key]
    return None


def _row_value(row: pd.Series, df: pd.DataFrame, aliases: tuple[str, ...]) -> Any:
    col = _column(df, aliases)
    if col is None:
        return None
    value = row.get(col)
    return None if pd.isna(value) else value


def _player_row(df: pd.DataFrame, player_id: int) -> pd.Series | None:
    if df is None or df.empty:
        return None
    pid_col = _column(df, ("player_id", "player id", "id"))
    if pid_col is None:
        return None
    ids = pd.to_numeric(df[pid_col], errors="coerce")
    match = df[ids == int(player_id)]
    return None if match.empty else match.iloc[0]


def _read_csv(url: str, params: dict[str, Any]) -> pd.DataFrame:
    response = requests.get(url, params=params, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text))


def _custom_profile(player_id: int, season: int) -> dict[str, Any] | None:
    params = {
        "year": int(season),
        "type": "batter",
        "filter": "",
        "min": "1",
        "selections": ",".join(SAVANT_SELECTIONS),
        "chart": "false",
        "sort": "xba",
        "sortDir": "desc",
        "csv": "true",
    }
    df = _read_csv(SAVANT_CUSTOM, params)
    row = _player_row(df, player_id)
    if row is None:
        return None

    return {
        "source": "Baseball Savant custom leaderboard",
        "season": int(season),
        "pa": _int(_row_value(row, df, ("pa", "plate appearances"))),
        "ab": _int(_row_value(row, df, ("ab", "at bats"))),
        "hits": _int(_row_value(row, df, ("hit", "h", "hits"))),
        "xba": _rate(_row_value(row, df, ("xba", "x ba", "expected batting average"))),
        "xbacon": _rate(_row_value(row, df, ("xbacon", "x bacon"))),
        "k_pct": _rate(_row_value(row, df, ("k_percent", "k%", "strikeout rate"))),
        "whiff_pct": _rate(_row_value(row, df, ("whiff_percent", "whiff%", "whiff rate"))),
        "zone_contact_pct": _rate(_row_value(row, df, ("iz_contact_percent", "in zone contact %", "zone contact %"))),
        "hard_hit_pct": _rate(_row_value(row, df, ("hard_hit_percent", "hard hit %", "hard-hit %"))),
        "avg_ev": _float(_row_value(row, df, ("exit_velocity_avg", "avg ev", "average exit velocity"))),
        "barrel_pct": _rate(_row_value(row, df, ("barrel_batted_rate", "barrel %", "barrel%"))),
        "bbe": _int(_row_value(row, df, ("batted_ball", "batted balls", "bbe", "attempts"))),
    }


def _fallback_profile(player_id: int, season: int) -> dict[str, Any] | None:
    """Fallback keeps xBA/contact quality available if the custom table changes."""
    expected = _read_csv(
        f"{SAVANT}/leaderboard/expected_statistics",
        {
            "type": "batter",
            "year": int(season),
            "position": "",
            "team": "",
            "filterType": "pa",
            "min": "1",
            "csv": "true",
        },
    )
    contact = _read_csv(
        f"{SAVANT}/leaderboard/statcast",
        {
            "type": "batter",
            "year": int(season),
            "position": "",
            "team": "",
            "min": "1",
            "csv": "true",
        },
    )
    erow = _player_row(expected, player_id)
    crow = _player_row(contact, player_id)
    if erow is None and crow is None:
        return None

    return {
        "source": "Baseball Savant expected/statcast fallback",
        "season": int(season),
        "pa": _int(_row_value(erow, expected, ("pa", "plate appearances"))) if erow is not None else 0,
        "ab": _int(_row_value(erow, expected, ("ab", "at bats"))) if erow is not None else 0,
        "hits": _int(_row_value(erow, expected, ("hit", "h", "hits"))) if erow is not None else 0,
        "xba": _rate(_row_value(erow, expected, ("est_ba", "xba", "x ba"))) if erow is not None else None,
        "xbacon": None,
        "k_pct": None,
        "whiff_pct": None,
        "zone_contact_pct": None,
        "hard_hit_pct": _rate(_row_value(crow, contact, ("hard_hit_percent", "ev95percent", "hard hit %"))) if crow is not None else None,
        "avg_ev": _float(_row_value(crow, contact, ("exit_velocity_avg", "avg_hit_speed", "avg ev"))) if crow is not None else None,
        "barrel_pct": _rate(_row_value(crow, contact, ("barrel_batted_rate", "brl_percent", "barrel %"))) if crow is not None else None,
        "bbe": _int(_row_value(crow, contact, ("batted_ball", "attempts", "bbe"))) if crow is not None else 0,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_savant_profile(player_id: int, season: int) -> dict[str, Any] | None:
    """Fetch the Step 2 Statcast profile without inventing unavailable fields."""
    try:
        custom = _custom_profile(int(player_id), int(season))
        if custom:
            return custom
    except Exception:
        pass
    try:
        return _fallback_profile(int(player_id), int(season))
    except Exception:
        return None


def weighted_recent_avg(logs: list[dict[str, Any]] | None, limit: int = 20, decay: float = 0.90) -> dict[str, Any]:
    """AB-weighted recent average with exponential recency decay; newest row first."""
    rows = list(logs or [])[: max(1, int(limit))]
    weighted_hits = 0.0
    weighted_ab = 0.0
    raw_hits = 0
    raw_ab = 0
    used = 0
    for index, row in enumerate(rows):
        ab = max(0, _int(row.get("AB")))
        hits = max(0, _int(row.get("H")))
        if ab <= 0:
            continue
        weight = float(decay) ** index
        weighted_hits += weight * hits
        weighted_ab += weight * ab
        raw_hits += hits
        raw_ab += ab
        used += 1
    avg = weighted_hits / weighted_ab if weighted_ab > 0 else None
    return {
        "avg": avg,
        "games": used,
        "ab": raw_ab,
        "hits": raw_hits,
        "weighted_ab": weighted_ab,
    }


def _babip(hits: int, home_runs: int, at_bats: int, strikeouts: int, sac_flies: int) -> float | None:
    denominator = int(at_bats) - int(strikeouts) - int(home_runs) + int(sac_flies)
    numerator = int(hits) - int(home_runs)
    if denominator <= 0 or numerator < 0:
        return None
    return max(0.0, min(1.0, numerator / denominator))


def _babip_sustainability(babip: float | None, avg: float | None, xba: float | None, ab: int) -> dict[str, Any]:
    if babip is None:
        return {"label": "PENDING", "gap": None, "note": "BABIP inputs incomplete"}
    if xba is None or avg is None:
        return {"label": "WATCH", "gap": None, "note": "xBA unavailable; no regression claim made"}
    gap = avg - xba
    if ab < 100:
        label = "LOW SAMPLE"
        note = "Too few AB for a strong sustainability read"
    elif gap >= 0.025 and babip >= 0.320:
        label = "REGRESSION RISK"
        note = "AVG is materially above xBA with an elevated BABIP"
    elif gap <= -0.025 and babip <= 0.280:
        label = "REBOUND SIGNAL"
        note = "AVG is materially below xBA with a suppressed BABIP"
    elif abs(gap) <= 0.015:
        label = "ALIGNED"
        note = "AVG and xBA are closely aligned"
    else:
        label = "MIXED"
        note = "BABIP and xBA gap do not give a clean regression signal"
    return {"label": label, "gap": gap, "note": note}


def _blend_skill(season_avg: float | None, xba: float | None, recent_avg: float | None, savant_pa: int, recent_ab: int) -> dict[str, Any]:
    raw = []
    if season_avg is not None:
        raw.append(("season", season_avg, 0.62))
    if xba is not None:
        reliability = max(0.0, savant_pa) / (max(0.0, savant_pa) + 120.0) if savant_pa > 0 else 0.35
        raw.append(("xba", xba, 0.28 * reliability))
    if recent_avg is not None:
        reliability = max(0.0, recent_ab) / (max(0.0, recent_ab) + 80.0) if recent_ab > 0 else 0.0
        raw.append(("recent", recent_avg, 0.10 * reliability))
    total = sum(weight for _, _, weight in raw)
    if total <= 0:
        return {"neutral_hit_skill": None, "weights": {"season": 0.0, "xba": 0.0, "recent": 0.0}}
    weights = {"season": 0.0, "xba": 0.0, "recent": 0.0}
    value = 0.0
    for name, metric, raw_weight in raw:
        weight = raw_weight / total
        weights[name] = weight
        value += metric * weight
    return {"neutral_hit_skill": max(0.0, min(0.500, value)), "weights": weights}


def _quality(metrics: dict[str, Any]) -> tuple[int, dict[str, tuple[int, int]]]:
    season = 0
    season += 10 if metrics.get("season_avg") is not None else 0
    season += 10 if metrics.get("hit_per_pa") is not None else 0
    season += 10 if metrics.get("k_pct") is not None else 0

    expected = 0
    expected += 12 if metrics.get("xba") is not None else 0
    expected += 8 if metrics.get("expected_hits") is not None else 0

    discipline = 0
    discipline += 8 if metrics.get("whiff_pct") is not None else 0
    discipline += 7 if metrics.get("contact_pct") is not None else 0
    discipline += 10 if metrics.get("zone_contact_pct") is not None else 0

    quality = 10 if metrics.get("hard_hit_pct") is not None else 0

    recent = 0
    recent += 7 if metrics.get("recent_avg") is not None else 0
    recent += 3 if (metrics.get("recent_ab") or 0) > 0 else 0

    sample = 5 if (metrics.get("savant_pa") or 0) > 0 else 0
    components = {
        "Season hit skill": (season, 30),
        "Expected stats": (expected, 20),
        "Plate discipline": (discipline, 25),
        "Contact quality": (quality, 10),
        "Recent form": (recent, 10),
        "Statcast sample": (sample, 5),
    }
    return sum(v[0] for v in components.values()), components


def quality_label(score: int) -> str:
    if score >= 90:
        return "ELITE PROFILE DATA"
    if score >= 75:
        return "STRONG PROFILE DATA"
    if score >= 60:
        return "USABLE PROFILE DATA"
    if score >= 40:
        return "PARTIAL PROFILE DATA"
    return "LOW PROFILE DATA"


def build_hitter_profile(
    foundation: dict[str, Any],
    logs: list[dict[str, Any]] | None,
    savant: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a neutral hitter-skill profile from already-selected player inputs."""
    stat = foundation.get("season_stat") or {}
    pa = _int(stat.get("plateAppearances"))
    ab = _int(stat.get("atBats"))
    hits = _int(stat.get("hits"))
    home_runs = _int(stat.get("homeRuns"))
    strikeouts = _int(stat.get("strikeOuts"))
    sac_flies = _int(stat.get("sacFlies"))

    season_avg = _rate(stat.get("avg"))
    if season_avg is None and ab > 0:
        season_avg = hits / ab
    hit_per_pa = hits / pa if pa > 0 else None
    k_pct = strikeouts / pa if pa > 0 else None

    savant = savant or {}
    xba = _rate(savant.get("xba"))
    whiff_pct = _rate(savant.get("whiff_pct"))
    zone_contact_pct = _rate(savant.get("zone_contact_pct"))
    hard_hit_pct = _rate(savant.get("hard_hit_pct"))
    contact_pct = (1.0 - whiff_pct) if whiff_pct is not None else None
    expected_hits = xba * ab if xba is not None and ab > 0 else None
    savant_pa = _int(savant.get("pa")) or pa

    recent = weighted_recent_avg(logs)
    recent_avg = recent.get("avg")
    recent_ab = _int(recent.get("ab"))

    actual_babip = _babip(hits, home_runs, ab, strikeouts, sac_flies)
    sustainability = _babip_sustainability(actual_babip, season_avg, xba, ab)
    blend = _blend_skill(season_avg, xba, recent_avg, savant_pa, recent_ab)

    metrics = {
        "season_avg": season_avg,
        "hit_per_pa": hit_per_pa,
        "k_pct": k_pct,
        "xba": xba,
        "expected_hits": expected_hits,
        "whiff_pct": whiff_pct,
        "contact_pct": contact_pct,
        "zone_contact_pct": zone_contact_pct,
        "hard_hit_pct": hard_hit_pct,
        "recent_avg": recent_avg,
        "recent_ab": recent_ab,
        "savant_pa": savant_pa,
    }
    score, components = _quality(metrics)

    return {
        **foundation,
        **metrics,
        "season_hr": home_runs,
        "season_k": strikeouts,
        "season_sf": sac_flies,
        "babip": actual_babip,
        "babip_label": sustainability["label"],
        "babip_gap": sustainability["gap"],
        "babip_note": sustainability["note"],
        "neutral_hit_skill": blend["neutral_hit_skill"],
        "skill_weights": blend["weights"],
        "recent_games": recent.get("games", 0),
        "recent_hits": recent.get("hits", 0),
        "profile_score": int(score),
        "profile_quality_label": quality_label(int(score)),
        "profile_components": components,
        "savant_source": savant.get("source") or "UNAVAILABLE",
        "avg_ev": _float(savant.get("avg_ev")),
        "barrel_pct": _rate(savant.get("barrel_pct")),
        "savant_bbe": _int(savant.get("bbe")),
    }


__all__ = [
    "SAVANT_SELECTIONS",
    "build_hitter_profile",
    "fetch_savant_profile",
    "quality_label",
    "weighted_recent_avg",
]
