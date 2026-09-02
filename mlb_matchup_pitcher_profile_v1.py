"""Starting-pitcher quality helpers for MLB Matchup Intelligence V2 Step 3.

Step 3 is starter context only. It describes the opposing starter's run prevention,
contact suppression, strikeout/walk skill, workload, recent form and historical
third-time-through-order tendency. It does not calculate a hitter/game hit
probability, fair odds, ranking, calibration or Monte Carlo result.
"""
from __future__ import annotations

from io import StringIO
import math
from typing import Any

import pandas as pd
import requests
import streamlit as st

MLB_API = "https://statsapi.mlb.com/api/v1"
SAVANT_EXPECTED = "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
HEADERS = {
    "User-Agent": "Mozilla/5.0 KyreSportsAI/MatchupV2Step3",
    "Accept": "application/json,text/csv,text/plain,*/*",
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


def _ip(value: Any) -> float:
    """Convert baseball innings notation (e.g. 6.2) into true innings."""
    try:
        text = str(value or "0").strip()
        if "." not in text:
            return float(text)
        whole, frac = text.split(".", 1)
        outs = int((frac or "0")[:1])
        return float(int(whole)) + max(0, min(2, outs)) / 3.0
    except Exception:
        return 0.0


def _rate(value: Any) -> float | None:
    val = _float(value)
    if val is None:
        return None
    if abs(val) > 1.0:
        val /= 100.0
    return max(0.0, min(1.0, val))


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


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
    id_col = _column(df, ("player_id", "player id", "id"))
    if id_col is None:
        return None
    ids = pd.to_numeric(df[id_col], errors="coerce")
    rows = df[ids == int(player_id)]
    return None if rows.empty else rows.iloc[0]


def _json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_pitcher_season(pitcher_id: int, season: int) -> dict[str, Any]:
    """Official MLB season pitching line for the selected opposing starter."""
    try:
        data = _json(
            f"{MLB_API}/people/{int(pitcher_id)}/stats",
            {"stats": "season", "group": "pitching", "season": int(season), "gameType": "R"},
        )
        blocks = data.get("stats") or []
        splits = (blocks[0].get("splits") or []) if blocks else []
        stat = (splits[0].get("stat") or {}) if splits else {}
        return stat if isinstance(stat, dict) else {}
    except Exception:
        return {}


@st.cache_data(ttl=900, show_spinner=False)
def fetch_pitcher_logs(pitcher_id: int, season: int) -> list[dict[str, Any]]:
    """Official MLB regular-season starter game logs, newest first."""
    try:
        data = _json(
            f"{MLB_API}/people/{int(pitcher_id)}/stats",
            {"stats": "gameLog", "group": "pitching", "season": int(season), "gameType": "R"},
        )
        blocks = data.get("stats") or []
        splits = (blocks[0].get("splits") or []) if blocks else []
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for split in splits:
        stat = split.get("stat") or {}
        starts = _int(stat.get("gamesStarted"))
        innings = _ip(stat.get("inningsPitched"))
        if starts <= 0 and innings <= 0:
            continue
        game = split.get("game") or {}
        rows.append(
            {
                "date": str(split.get("date") or ""),
                "game_pk": _int(game.get("gamePk")) or None,
                "ip": innings,
                "hits": _int(stat.get("hits")),
                "earned_runs": _int(stat.get("earnedRuns")),
                "home_runs": _int(stat.get("homeRuns")),
                "walks": _int(stat.get("baseOnBalls")),
                "hit_batters": _int(stat.get("hitBatsmen")),
                "strikeouts": _int(stat.get("strikeOuts")),
                "batters_faced": _int(stat.get("battersFaced")),
                "pitches": _int(stat.get("numberOfPitches") or stat.get("pitchesThrown")),
                "games_started": starts,
            }
        )
    rows.sort(key=lambda item: item.get("date") or "", reverse=True)
    starts_only = [row for row in rows if row.get("games_started", 0) > 0]
    return starts_only if starts_only else rows


def recent_form(logs: list[dict[str, Any]] | None, n: int) -> dict[str, Any]:
    rows = list(logs or [])[: max(1, int(n))]
    if not rows:
        return {"status": "PENDING", "starts": 0}

    ip = sum(float(row.get("ip") or 0.0) for row in rows)
    hits = sum(_int(row.get("hits")) for row in rows)
    er = sum(_int(row.get("earned_runs")) for row in rows)
    walks = sum(_int(row.get("walks")) for row in rows)
    strikeouts = sum(_int(row.get("strikeouts")) for row in rows)
    bf = sum(_int(row.get("batters_faced")) for row in rows)
    pitches = [_int(row.get("pitches")) for row in rows if _int(row.get("pitches")) > 0]
    starts = len(rows)

    return {
        "status": "VERIFIED",
        "starts": starts,
        "ip": ip,
        "era": 9.0 * er / ip if ip > 0 else None,
        "whip": (hits + walks) / ip if ip > 0 else None,
        "h9": 9.0 * hits / ip if ip > 0 else None,
        "k_pct": strikeouts / bf if bf > 0 else None,
        "bb_pct": walks / bf if bf > 0 else None,
        "ip_per_start": ip / starts if starts else None,
        "pitches_per_start": sum(pitches) / len(pitches) if pitches else None,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_savant_expected(pitcher_id: int, season: int) -> dict[str, Any] | None:
    """Baseball Savant expected-statistics row (xERA/xBA allowed) for a pitcher."""
    try:
        response = requests.get(
            SAVANT_EXPECTED,
            params={
                "type": "pitcher",
                "year": int(season),
                "position": "",
                "team": "",
                "filterType": "pa",
                "min": "1",
                "csv": "true",
            },
            headers=HEADERS,
            timeout=25,
        )
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        row = _player_row(df, int(pitcher_id))
        if row is None:
            return None
        return {
            "source": "Baseball Savant expected statistics",
            "pa": _int(_row_value(row, df, ("pa", "plate appearances"))),
            "bip": _int(_row_value(row, df, ("bip", "batted balls"))),
            "ba_allowed": _rate(_row_value(row, df, ("ba", "avg", "batting average"))),
            "xba_allowed": _rate(_row_value(row, df, ("est_ba", "xba", "xavg", "expected batting average"))),
            "era": _float(_row_value(row, df, ("era",))),
            "xera": _float(_row_value(row, df, ("xera", "est_era", "expected era", "expected earned run average"))),
            "xwoba_allowed": _rate(_row_value(row, df, ("est_woba", "xwoba", "expected woba"))),
        }
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_league_fip_constant(season: int) -> float | None:
    """Derive the season FIP constant so aggregate league FIP equals aggregate ERA."""
    try:
        data = _json(
            f"{MLB_API}/stats",
            {
                "stats": "season",
                "group": "pitching",
                "season": int(season),
                "gameType": "R",
                "playerPool": "ALL",
                "limit": 5000,
            },
        )
        blocks = data.get("stats") or []
        splits = (blocks[0].get("splits") or []) if blocks else []
    except Exception:
        return None

    innings = 0.0
    earned_runs = home_runs = walks = hbp = strikeouts = 0
    for split in splits:
        stat = split.get("stat") or {}
        innings += _ip(stat.get("inningsPitched"))
        earned_runs += _int(stat.get("earnedRuns"))
        home_runs += _int(stat.get("homeRuns"))
        walks += _int(stat.get("baseOnBalls"))
        hbp += _int(stat.get("hitBatsmen"))
        strikeouts += _int(stat.get("strikeOuts"))

    if innings <= 0:
        return None
    league_era = 9.0 * earned_runs / innings
    component = (13.0 * home_runs + 3.0 * (walks + hbp) - 2.0 * strikeouts) / innings
    constant = league_era - component
    return constant if 1.0 <= constant <= 5.0 else None


def calculate_fip(stat: dict[str, Any], constant: float | None) -> float | None:
    if constant is None:
        return None
    innings = _ip(stat.get("inningsPitched"))
    if innings <= 0:
        return None
    home_runs = _int(stat.get("homeRuns"))
    walks = _int(stat.get("baseOnBalls"))
    hbp = _int(stat.get("hitBatsmen"))
    strikeouts = _int(stat.get("strikeOuts"))
    return (13.0 * home_runs + 3.0 * (walks + hbp) - 2.0 * strikeouts) / innings + float(constant)


_AB_EVENTS = {
    "single",
    "double",
    "triple",
    "home_run",
    "field_out",
    "force_out",
    "grounded_into_double_play",
    "field_error",
    "fielders_choice",
    "fielders_choice_out",
    "strikeout",
    "strikeout_double_play",
    "double_play",
    "triple_play",
}
_HIT_EVENTS = {"single", "double", "triple", "home_run"}
_K_EVENTS = {"strikeout", "strikeout_double_play"}


def tto_profile_from_frame(frame: pd.DataFrame | None) -> dict[str, Any]:
    """Infer first/second/third+ PA vs each batter within each game from Statcast rows."""
    if frame is None or frame.empty:
        return {"status": "PENDING", "segments": {}}
    required = {"game_pk", "batter", "events", "at_bat_number"}
    if not required.issubset(set(frame.columns)):
        return {"status": "PENDING", "segments": {}}

    terminal = frame.copy()
    terminal = terminal[terminal["events"].notna()]
    terminal = terminal[terminal["events"].astype(str).str.strip() != ""]
    if terminal.empty:
        return {"status": "PENDING", "segments": {}}

    terminal = terminal.sort_values(["game_pk", "at_bat_number"]).copy()
    terminal["tto"] = terminal.groupby(["game_pk", "batter"]).cumcount() + 1
    terminal["event_norm"] = terminal["events"].astype(str).str.lower().str.strip()
    terminal["is_ab"] = terminal["event_norm"].isin(_AB_EVENTS)
    terminal["is_hit"] = terminal["event_norm"].isin(_HIT_EVENTS)
    terminal["is_k"] = terminal["event_norm"].isin(_K_EVENTS)

    segments: dict[str, dict[str, Any]] = {}
    for label, mask in (
        ("1st", terminal["tto"] == 1),
        ("2nd", terminal["tto"] == 2),
        ("3rd+", terminal["tto"] >= 3),
    ):
        rows = terminal[mask]
        ab = int(rows["is_ab"].sum())
        hits = int(rows["is_hit"].sum())
        bf = int(len(rows))
        strikeouts = int(rows["is_k"].sum())
        segments[label] = {
            "bf": bf,
            "ab": ab,
            "hits": hits,
            "avg": hits / ab if ab > 0 else None,
            "k_pct": strikeouts / bf if bf > 0 else None,
        }

    first = segments["1st"]
    third = segments["3rd+"]
    penalty = None
    if first.get("avg") is not None and third.get("avg") is not None and first.get("ab", 0) >= 10 and third.get("ab", 0) >= 10:
        penalty = float(third["avg"]) - float(first["avg"])
    if penalty is None:
        label = "LOW SAMPLE"
    elif penalty >= 0.035:
        label = "MATERIAL 3RD-TIME FADE"
    elif penalty >= 0.015:
        label = "MODERATE 3RD-TIME FADE"
    elif penalty <= -0.015:
        label = "HOLDS / IMPROVES LATE"
    else:
        label = "STABLE THROUGH ORDER"

    return {
        "status": "VERIFIED",
        "segments": segments,
        "third_time_avg_delta": penalty,
        "third_time_label": label,
        "terminal_pa": int(len(terminal)),
    }


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_tto_profile(pitcher_id: int, season: int) -> dict[str, Any]:
    """Use the repository's existing read-only Statcast cache to derive TTO history."""
    try:
        import mlb_matchup_rankings_v17 as feeds

        payload = feeds._statcast_rows(int(pitcher_id), int(season), "pitcher")
        if payload.get("status") != "VERIFIED":
            return {"status": "PENDING", "segments": {}, "error": payload.get("error")}
        return tto_profile_from_frame(payload.get("frame"))
    except Exception as exc:
        return {"status": "PENDING", "segments": {}, "error": type(exc).__name__}


def _metric_score(value: float | None, center: float, scale: float, lower_is_better: bool = True) -> float | None:
    if value is None:
        return None
    direction = (center - value) if lower_is_better else (value - center)
    return max(0.0, min(100.0, 50.0 + direction * scale))


def starter_strength_score(metrics: dict[str, Any]) -> dict[str, Any]:
    """Descriptive starter-quality index; never interpreted as a hit probability."""
    pieces: list[tuple[float, float]] = []

    def add(value: float | None, weight: float, center: float, scale: float, lower: bool = True) -> None:
        score = _metric_score(value, center, scale, lower)
        if score is not None:
            pieces.append((score, weight))

    add(_float(metrics.get("xera")), 0.24, 4.20, 12.0, True)
    add(_float(metrics.get("fip")), 0.20, 4.20, 12.0, True)
    add(_float(metrics.get("era")), 0.12, 4.20, 10.0, True)
    add(_float(metrics.get("whip")), 0.10, 1.30, 50.0, True)
    add(_float(metrics.get("xba_allowed")), 0.14, 0.245, 250.0, True)
    k_minus_bb = None
    if metrics.get("k_pct") is not None and metrics.get("bb_pct") is not None:
        k_minus_bb = float(metrics["k_pct"]) - float(metrics["bb_pct"])
    add(k_minus_bb, 0.20, 0.150, 150.0, False)

    total_weight = sum(weight for _, weight in pieces)
    if total_weight <= 0:
        return {"score": None, "label": "PENDING", "coverage": 0.0}
    score = sum(value * weight for value, weight in pieces) / total_weight
    coverage = total_weight / 1.0
    if score >= 72:
        label = "ELITE / VERY TOUGH STARTER"
    elif score >= 60:
        label = "STRONG STARTER"
    elif score >= 45:
        label = "AVERAGE STARTER"
    elif score >= 33:
        label = "BELOW-AVERAGE STARTER"
    else:
        label = "VULNERABLE STARTER"
    return {"score": int(round(score)), "label": label, "coverage": min(1.0, coverage)}


def _quality(metrics: dict[str, Any]) -> tuple[int, dict[str, tuple[int, int]]]:
    season = 0
    season += 5 if metrics.get("era") is not None else 0
    season += 5 if metrics.get("whip") is not None else 0
    season += 5 if metrics.get("h9") is not None else 0
    season += 5 if metrics.get("k_pct") is not None else 0
    season += 5 if metrics.get("bb_pct") is not None else 0
    season += 10 if metrics.get("fip") is not None else 0

    expected = 0
    expected += 10 if metrics.get("xera") is not None else 0
    expected += 10 if metrics.get("xba_allowed") is not None else 0

    recent = 0
    recent += 10 if metrics.get("recent5_status") == "VERIFIED" else 0
    recent += 10 if metrics.get("recent10_status") == "VERIFIED" else 0

    workload = 0
    workload += 5 if metrics.get("ip_per_start") is not None else 0
    workload += 5 if metrics.get("pitches_per_start") is not None else 0
    workload += 5 if metrics.get("recent_pitches_per_start") is not None else 0

    tto = 10 if metrics.get("tto_status") == "VERIFIED" else 0
    components = {
        "Season skill": (season, 35),
        "Expected stats": (expected, 20),
        "Recent form": (recent, 20),
        "Workload": (workload, 15),
        "Times through order": (tto, 10),
    }
    return sum(value[0] for value in components.values()), components


def quality_label(score: int) -> str:
    if score >= 90:
        return "ELITE STARTER DATA"
    if score >= 75:
        return "STRONG STARTER DATA"
    if score >= 60:
        return "USABLE STARTER DATA"
    if score >= 40:
        return "PARTIAL STARTER DATA"
    return "LOW STARTER DATA"


def build_pitcher_profile(
    foundation: dict[str, Any],
    season_stat: dict[str, Any] | None,
    logs: list[dict[str, Any]] | None,
    savant: dict[str, Any] | None,
    fip_constant: float | None,
    tto: dict[str, Any] | None,
) -> dict[str, Any]:
    stat = season_stat or {}
    logs = list(logs or [])
    savant = savant or {}
    tto = tto or {"status": "PENDING", "segments": {}}

    innings = _ip(stat.get("inningsPitched"))
    games_started = _int(stat.get("gamesStarted"))
    hits = _int(stat.get("hits"))
    walks = _int(stat.get("baseOnBalls"))
    strikeouts = _int(stat.get("strikeOuts"))
    batters_faced = _int(stat.get("battersFaced"))

    era = _float(stat.get("era"))
    whip = _float(stat.get("whip"))
    if whip is None and innings > 0:
        whip = (hits + walks) / innings
    h9 = 9.0 * hits / innings if innings > 0 else None
    k_pct = strikeouts / batters_faced if batters_faced > 0 else None
    bb_pct = walks / batters_faced if batters_faced > 0 else None
    fip = calculate_fip(stat, fip_constant)

    recent5 = recent_form(logs, 5)
    recent10 = recent_form(logs, 10)
    pitches = [_int(row.get("pitches")) for row in logs if _int(row.get("pitches")) > 0]
    ip_per_start = innings / games_started if innings > 0 and games_started > 0 else None
    pitches_per_start = sum(pitches) / len(pitches) if pitches else None
    recent_pitches_per_start = recent5.get("pitches_per_start")

    xera = _float(savant.get("xera"))
    xba_allowed = _rate(savant.get("xba_allowed"))
    era_xera_gap = (era - xera) if era is not None and xera is not None else None

    segments = tto.get("segments") or {}
    third = segments.get("3rd+") or {}
    first = segments.get("1st") or {}

    metrics = {
        "era": era,
        "xera": xera,
        "fip": fip,
        "whip": whip,
        "h9": h9,
        "k_pct": k_pct,
        "bb_pct": bb_pct,
        "xba_allowed": xba_allowed,
        "ip_per_start": ip_per_start,
        "pitches_per_start": pitches_per_start,
        "recent_pitches_per_start": recent_pitches_per_start,
        "recent5_status": recent5.get("status"),
        "recent10_status": recent10.get("status"),
        "tto_status": tto.get("status"),
    }
    completeness, components = _quality(metrics)
    strength = starter_strength_score(metrics)

    return {
        **foundation,
        **metrics,
        "starter_games_started": games_started,
        "starter_innings": innings,
        "starter_batters_faced": batters_faced,
        "starter_hits_allowed": hits,
        "starter_walks": walks,
        "starter_strikeouts": strikeouts,
        "era_xera_gap": era_xera_gap,
        "fip_constant": fip_constant,
        "fip_constant_source": "current-season MLB aggregate" if fip_constant is not None else "UNAVAILABLE",
        "recent5": recent5,
        "recent10": recent10,
        "tto": tto,
        "tto_first_avg": first.get("avg"),
        "tto_third_avg": third.get("avg"),
        "third_time_avg_delta": tto.get("third_time_avg_delta"),
        "third_time_label": tto.get("third_time_label") or "PENDING",
        "savant_source": savant.get("source") or "UNAVAILABLE",
        "savant_pa": _int(savant.get("pa")),
        "savant_bip": _int(savant.get("bip")),
        "starter_strength_score": strength.get("score"),
        "starter_strength_label": strength.get("label"),
        "starter_strength_coverage": strength.get("coverage"),
        "starter_profile_score": int(completeness),
        "starter_profile_label": quality_label(int(completeness)),
        "starter_profile_components": components,
    }


__all__ = [
    "build_pitcher_profile",
    "calculate_fip",
    "fetch_league_fip_constant",
    "fetch_pitcher_logs",
    "fetch_pitcher_season",
    "fetch_savant_expected",
    "fetch_tto_profile",
    "quality_label",
    "recent_form",
    "starter_strength_score",
    "tto_profile_from_frame",
]
