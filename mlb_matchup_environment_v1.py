"""Park, weather and defense context for MLB Matchup Intelligence V2 Step 7.

Step 7 is descriptive environment context only. It does not calculate a game-level
hit probability, fair odds, Monte Carlo outcome, calibration adjustment or ranking
change. Missing weather, roof, park or defensive data are left blank rather than
guessed.
"""
from __future__ import annotations

import math
import re
from typing import Any

import requests
import streamlit as st

MLB_API = "https://statsapi.mlb.com/api/v1"
LIVE_API = "https://statsapi.mlb.com/api/v1.1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 KyreSportsAI/MatchupV2Step7",
    "Accept": "application/json,text/plain,*/*",
}

PARK_MIN_SPLIT_AB = 120
PARK_FULL_SPLIT_AB = 900
DEFENSE_FULL_GAMES = 90
FIELDING_BASELINE = 0.985
ERRORS_PER_GAME_BASELINE = 0.55

_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)

_DIMENSION_KEYS = (
    ("leftLine", "LF line"),
    ("left", "LF"),
    ("leftCenter", "LCF"),
    ("center", "CF"),
    ("rightCenter", "RCF"),
    ("right", "RF"),
    ("rightLine", "RF line"),
)


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _int(value: Any) -> int:
    val = _finite(value)
    return int(val) if val is not None else 0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_json(url: str, params: dict[str, Any] | None = None, timeout: int = 12) -> dict[str, Any] | None:
    try:
        response = _SESSION.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


@st.cache_data(ttl=180, show_spinner=False)
def fetch_game_context(game_pk: int) -> dict[str, Any] | None:
    return _safe_json(f"{LIVE_API}/game/{int(game_pk)}/feed/live")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_venue_context(venue_id: int) -> dict[str, Any] | None:
    payload = _safe_json(f"{MLB_API}/venues/{int(venue_id)}")
    venues = (payload or {}).get("venues") or []
    return venues[0] if venues else None


def _team_stats_payload(team_id: int, season: int, group: str, stats: str = "season", sit_code: str | None = None) -> dict[str, Any] | None:
    params: dict[str, Any] = {
        "stats": stats,
        "group": group,
        "season": int(season),
    }
    if sit_code:
        params["sitCodes"] = sit_code
    return _safe_json(f"{MLB_API}/teams/{int(team_id)}/stats", params=params)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_team_split(team_id: int, season: int, sit_code: str) -> dict[str, Any] | None:
    payload = _team_stats_payload(int(team_id), int(season), "hitting", "statSplits", str(sit_code))
    for block in (payload or {}).get("stats") or []:
        for split in block.get("splits") or []:
            stat = split.get("stat") or {}
            if stat:
                return stat
    return None


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_team_fielding(team_id: int, season: int) -> dict[str, Any] | None:
    payload = _team_stats_payload(int(team_id), int(season), "fielding", "season")
    for block in (payload or {}).get("stats") or []:
        for split in block.get("splits") or []:
            stat = split.get("stat") or {}
            if stat:
                return stat
    return None


def _avg_from_stat(stat: dict[str, Any] | None) -> tuple[float | None, int, int]:
    stat = stat or {}
    ab = _int(stat.get("atBats"))
    hits = _int(stat.get("hits"))
    avg = _finite(stat.get("avg"))
    if avg is None and ab > 0:
        avg = hits / ab
    return avg, ab, hits


def park_hit_proxy(home_stat: dict[str, Any] | None, away_stat: dict[str, Any] | None) -> dict[str, Any]:
    """Shrink a home-club home/road AVG ratio toward neutral.

    This is intentionally labeled a descriptive park proxy, not an official park
    factor, because opponent mix and roster changes remain in the sample.
    """
    home_avg, home_ab, home_hits = _avg_from_stat(home_stat)
    away_avg, away_ab, away_hits = _avg_from_stat(away_stat)
    sample = min(home_ab, away_ab)
    if home_avg is None or away_avg is None or away_avg <= 0 or sample < PARK_MIN_SPLIT_AB:
        return {
            "factor": None,
            "raw_ratio": None,
            "reliability": 0.0,
            "home_avg": home_avg,
            "away_avg": away_avg,
            "home_ab": home_ab,
            "away_ab": away_ab,
            "home_hits": home_hits,
            "away_hits": away_hits,
            "label": "PENDING PARK SAMPLE",
        }
    raw = _clamp(home_avg / away_avg, 0.70, 1.30)
    reliability = _clamp((sample - PARK_MIN_SPLIT_AB) / float(PARK_FULL_SPLIT_AB - PARK_MIN_SPLIT_AB), 0.0, 1.0)
    factor = 1.0 + (raw - 1.0) * reliability
    if factor >= 1.035:
        label = "HITTER-FRIENDLY PARK PROXY"
    elif factor <= 0.965:
        label = "HIT-SUPPRESSING PARK PROXY"
    else:
        label = "NEUTRAL PARK PROXY"
    return {
        "factor": factor,
        "raw_ratio": raw,
        "reliability": reliability,
        "home_avg": home_avg,
        "away_avg": away_avg,
        "home_ab": home_ab,
        "away_ab": away_ab,
        "home_hits": home_hits,
        "away_hits": away_hits,
        "label": label,
    }


def parse_wind(wind: Any) -> dict[str, Any]:
    text = str(wind or "").strip()
    mph_match = re.search(r"(\d+(?:\.\d+)?)\s*mph", text, flags=re.I)
    mph = _finite(mph_match.group(1)) if mph_match else None
    lower = text.lower()
    if "out" in lower:
        direction = "OUT"
    elif "in" in lower:
        direction = "IN"
    elif any(token in lower for token in ("l to r", "r to l", "cross")):
        direction = "CROSS"
    elif any(token in lower for token in ("none", "calm", "indoor")):
        direction = "CALM"
    else:
        direction = "UNKNOWN"
    return {"text": text or "—", "mph": mph, "direction": direction}


def _roof_indoor(roof_type: Any, condition: Any, wind: Any) -> bool:
    text = " ".join(str(x or "") for x in (roof_type, condition, wind)).lower()
    return any(token in text for token in ("dome", "indoor", "roof closed", "fixed roof", "closed roof"))


def weather_context(weather: dict[str, Any] | None, roof_type: Any) -> dict[str, Any]:
    weather = weather or {}
    temp = _finite(weather.get("temp"))
    condition = str(weather.get("condition") or "—")
    wind = parse_wind(weather.get("wind"))
    indoor = _roof_indoor(roof_type, condition, wind.get("text"))

    if indoor:
        return {
            "temperature": temp,
            "condition": condition,
            "wind": wind,
            "indoor": True,
            "signal": 0.0,
            "reliability": 1.0,
            "label": "WEATHER SUPPRESSED BY ROOF/INDOOR SETTING",
        }

    pieces: list[tuple[float, float]] = []
    if temp is not None:
        pieces.append((_clamp((temp - 70.0) / 25.0, -1.0, 1.0), 0.45))
    mph = wind.get("mph")
    direction = wind.get("direction")
    if mph is not None and direction in {"OUT", "IN", "CROSS", "CALM"}:
        magnitude = _clamp(mph / 20.0, 0.0, 1.0)
        wind_signal = magnitude if direction == "OUT" else -magnitude if direction == "IN" else 0.0
        pieces.append((wind_signal, 0.55))

    total_weight = sum(weight for _, weight in pieces)
    signal = sum(value * weight for value, weight in pieces) / total_weight if total_weight > 0 else None
    reliability = _clamp(total_weight, 0.0, 1.0)
    if signal is None:
        label = "WEATHER PENDING"
    elif signal >= 0.25:
        label = "HITTER-FRIENDLY WEATHER"
    elif signal <= -0.25:
        label = "HIT-SUPPRESSING WEATHER"
    else:
        label = "NEUTRAL WEATHER"
    return {
        "temperature": temp,
        "condition": condition,
        "wind": wind,
        "indoor": False,
        "signal": signal,
        "reliability": reliability,
        "label": label,
    }


def defense_context(stat: dict[str, Any] | None) -> dict[str, Any]:
    stat = stat or {}
    errors = _int(stat.get("errors"))
    games = _int(stat.get("gamesPlayed") or stat.get("games"))
    fielding_pct = _finite(stat.get("fielding"))
    if fielding_pct is None:
        putouts = _int(stat.get("putOuts"))
        assists = _int(stat.get("assists"))
        chances = putouts + assists + errors
        fielding_pct = (putouts + assists) / chances if chances > 0 else None
    errors_per_game = errors / games if games > 0 else None
    reliability = _clamp(games / float(DEFENSE_FULL_GAMES), 0.0, 1.0) if games > 0 else 0.0

    signals: list[float] = []
    if fielding_pct is not None:
        signals.append(_clamp((FIELDING_BASELINE - fielding_pct) / 0.012, -1.0, 1.0))
    if errors_per_game is not None:
        signals.append(_clamp((errors_per_game - ERRORS_PER_GAME_BASELINE) / 0.35, -1.0, 1.0))
    signal = sum(signals) / len(signals) if signals else None

    if signal is None:
        label = "DEFENSE PENDING"
    elif signal >= 0.25:
        label = "SOFTER FIELDING EXECUTION"
    elif signal <= -0.25:
        label = "STRONG FIELDING EXECUTION"
    else:
        label = "NEUTRAL FIELDING EXECUTION"
    return {
        "fielding_pct": fielding_pct,
        "errors": errors,
        "games": games,
        "errors_per_game": errors_per_game,
        "reliability": reliability,
        "signal": signal,
        "label": label,
    }


def field_dimensions(field_info: dict[str, Any] | None) -> dict[str, Any]:
    field_info = field_info or {}
    rows = []
    for key, label in _DIMENSION_KEYS:
        value = field_info.get(key)
        if value not in (None, "", "Unknown"):
            rows.append({"key": key, "label": label, "value": value})
    return {
        "rows": rows,
        "summary": " • ".join(f"{row['label']} {row['value']}" for row in rows) if rows else "—",
        "count": len(rows),
    }


def environment_label(score: int | None) -> str:
    if score is None:
        return "PENDING ENVIRONMENT"
    if score >= 58:
        return "HITTER-FRIENDLY ENVIRONMENT"
    if score <= 42:
        return "HIT-SUPPRESSING ENVIRONMENT"
    return "NEUTRAL ENVIRONMENT"


def _data_quality(game_ok: bool, venue_ok: bool, weather: dict[str, Any], park: dict[str, Any], defense: dict[str, Any], dimensions: dict[str, Any]) -> tuple[int, dict[str, tuple[int, int]]]:
    game_points = 12 if game_ok else 0
    venue_points = 8 if venue_ok else 0

    weather_points = 0
    weather_points += 8 if weather.get("temperature") is not None or weather.get("indoor") else 0
    weather_points += 7 if (weather.get("wind") or {}).get("direction") != "UNKNOWN" or weather.get("indoor") else 0
    weather_points += 5 if str(weather.get("condition") or "—") != "—" else 0

    park_points = int(round(25 * float(park.get("reliability") or 0.0))) if park.get("factor") is not None else 0

    defense_points = 0
    defense_points += 15 if defense.get("fielding_pct") is not None else 0
    defense_points += 10 if defense.get("errors_per_game") is not None else 0
    defense_points = int(round(defense_points * float(defense.get("reliability") or 0.0)))

    dimension_points = min(10, int(dimensions.get("count") or 0) * 2)
    components = {
        "Game + venue feed": (game_points + venue_points, 20),
        "Official weather/roof": (weather_points, 20),
        "Park home/road sample": (park_points, 25),
        "Opponent fielding": (defense_points, 25),
        "Field dimensions": (dimension_points, 10),
    }
    return sum(v[0] for v in components.values()), components


def quality_label(score: int) -> str:
    if score >= 90:
        return "ELITE ENVIRONMENT DATA"
    if score >= 75:
        return "STRONG ENVIRONMENT DATA"
    if score >= 60:
        return "USABLE ENVIRONMENT DATA"
    if score >= 40:
        return "PARTIAL ENVIRONMENT DATA"
    return "LOW ENVIRONMENT DATA"


def build_environment_profile(foundation: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    feed = payload.get("game_feed") or {}
    game_data = feed.get("gameData") or {}
    venue = game_data.get("venue") or {}
    venue_detail = payload.get("venue_detail") or {}
    field_info = venue.get("fieldInfo") or venue_detail.get("fieldInfo") or {}
    weather_raw = game_data.get("weather") or {}
    roof_type = field_info.get("roofType") or "—"
    turf_type = field_info.get("turfType") or "—"

    park = park_hit_proxy(payload.get("home_split"), payload.get("away_split"))
    weather = weather_context(weather_raw, roof_type)
    defense = defense_context(payload.get("opponent_fielding"))
    dimensions = field_dimensions(field_info)

    park_signal = None
    if park.get("factor") is not None:
        park_signal = _clamp((float(park["factor"]) - 1.0) / 0.08, -1.0, 1.0)
    combined = 0.0
    coverage = 0.0
    if park_signal is not None:
        rel = float(park.get("reliability") or 0.0)
        combined += park_signal * 0.40 * rel
        coverage += 0.40 * rel
    if weather.get("signal") is not None:
        rel = float(weather.get("reliability") or 0.0)
        combined += float(weather["signal"]) * 0.30 * rel
        coverage += 0.30 * rel
    if defense.get("signal") is not None:
        rel = float(defense.get("reliability") or 0.0)
        combined += float(defense["signal"]) * 0.30 * rel
        coverage += 0.30 * rel

    score = int(round(_clamp(50.0 + 20.0 * combined, 30.0, 70.0))) if coverage > 0 else None
    data_score, components = _data_quality(bool(feed), bool(venue or venue_detail), weather, park, defense, dimensions)

    return {
        **foundation,
        "environment_score": score,
        "environment_label": environment_label(score),
        "environment_coverage": _clamp(coverage, 0.0, 1.0),
        "venue_id": _int(venue.get("id") or venue_detail.get("id")),
        "venue_name_step7": venue.get("name") or venue_detail.get("name") or foundation.get("venue") or "—",
        "roof_type": roof_type,
        "turf_type": turf_type,
        "temperature": weather.get("temperature"),
        "condition": weather.get("condition"),
        "wind_text": (weather.get("wind") or {}).get("text") or "—",
        "wind_mph": (weather.get("wind") or {}).get("mph"),
        "wind_direction": (weather.get("wind") or {}).get("direction") or "UNKNOWN",
        "weather_indoor": bool(weather.get("indoor")),
        "weather_signal": weather.get("signal"),
        "weather_reliability": weather.get("reliability"),
        "weather_label": weather.get("label"),
        "park_factor_proxy": park.get("factor"),
        "park_raw_ratio": park.get("raw_ratio"),
        "park_reliability": park.get("reliability"),
        "park_home_avg": park.get("home_avg"),
        "park_away_avg": park.get("away_avg"),
        "park_home_ab": park.get("home_ab"),
        "park_away_ab": park.get("away_ab"),
        "park_label": park.get("label"),
        "defense_fielding_pct": defense.get("fielding_pct"),
        "defense_errors": defense.get("errors"),
        "defense_games": defense.get("games"),
        "defense_errors_per_game": defense.get("errors_per_game"),
        "defense_reliability": defense.get("reliability"),
        "defense_label": defense.get("label"),
        "dimensions": dimensions.get("rows"),
        "dimension_summary": dimensions.get("summary"),
        "dimension_count": dimensions.get("count"),
        "environment_data_score": int(data_score),
        "environment_data_label": quality_label(int(data_score)),
        "environment_data_components": components,
        "home_team_id_step7": payload.get("home_team_id"),
        "opponent_team_id_step7": payload.get("opponent_team_id"),
        "park_source": "Current-season home-club home/road AVG split; descriptive proxy, not an official park factor",
        "weather_source": "Official MLB game feed weather/venue data",
        "defense_source": "Official MLB team season fielding stats",
    }


@st.cache_data(ttl=180, show_spinner=False)
def fetch_environment_inputs(game_pk: int, season: int, hitter_side: str) -> dict[str, Any]:
    feed = fetch_game_context(int(game_pk)) or {}
    game_data = feed.get("gameData") or {}
    teams = game_data.get("teams") or {}
    venue = game_data.get("venue") or {}
    home_team_id = _int((teams.get("home") or {}).get("id"))
    away_team_id = _int((teams.get("away") or {}).get("id"))
    side = str(hitter_side or "").strip().lower()
    opponent_team_id = home_team_id if side == "away" else away_team_id if side == "home" else 0
    venue_id = _int(venue.get("id"))

    venue_detail = fetch_venue_context(venue_id) if venue_id else None
    home_split = fetch_team_split(home_team_id, int(season), "home") if home_team_id else None
    away_split = fetch_team_split(home_team_id, int(season), "away") if home_team_id else None
    opponent_fielding = fetch_team_fielding(opponent_team_id, int(season)) if opponent_team_id else None

    return {
        "game_feed": feed,
        "venue_detail": venue_detail,
        "home_split": home_split,
        "away_split": away_split,
        "opponent_fielding": opponent_fielding,
        "home_team_id": home_team_id or None,
        "opponent_team_id": opponent_team_id or None,
    }


__all__ = [
    "DEFENSE_FULL_GAMES",
    "ERRORS_PER_GAME_BASELINE",
    "FIELDING_BASELINE",
    "PARK_FULL_SPLIT_AB",
    "PARK_MIN_SPLIT_AB",
    "build_environment_profile",
    "defense_context",
    "environment_label",
    "fetch_environment_inputs",
    "field_dimensions",
    "park_hit_proxy",
    "parse_wind",
    "quality_label",
    "weather_context",
]
