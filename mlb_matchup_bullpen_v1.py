"""Bullpen-path helpers for MLB Matchup Intelligence V2 Step 8.

Step 8 describes the opposing relief corps: active reliever depth, season run/contact
suppression, expected-stat context, handedness mix, recent workload/availability and
nominal post-starter exposure. It is descriptive only. It does not calculate game-level
hit probability, fair odds, Monte Carlo outcomes, calibration or rankings.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from io import StringIO
import math
from typing import Any

import pandas as pd
import requests
import streamlit as st

MLB_API = "https://statsapi.mlb.com/api/v1"
SAVANT_EXPECTED = "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
HEADERS = {
    "User-Agent": "Mozilla/5.0 KyreSportsAI/MatchupV2Step8",
    "Accept": "application/json,text/csv,text/plain,*/*",
}

RELIEVER_MAX_STARTS = 3
RELIEVER_MAX_START_SHARE = 0.35
WORKLOAD_DAYS = 3
LIMITED_YESTERDAY_PITCHES = 30
LIMITED_TWO_DAY_PITCHES = 45
WATCH_YESTERDAY_PITCHES = 20
WATCH_TWO_DAY_PITCHES = 35


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


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def _column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    if df is None or df.empty:
        return None
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


def _json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


def _date(value: Any) -> date | None:
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except Exception:
        return None


def resolve_opponent_team_id(games_df: pd.DataFrame | None, foundation: dict[str, Any]) -> int | None:
    """Resolve the opponent team from the verified Step 1 game and selected side."""
    if games_df is None or games_df.empty:
        return None
    game_pk = _int(foundation.get("game_pk"))
    side = str(foundation.get("side") or "").strip().lower()
    if not game_pk or side not in {"home", "away"} or "game_pk" not in games_df.columns:
        return None
    ids = pd.to_numeric(games_df["game_pk"], errors="coerce")
    rows = games_df[ids == game_pk]
    if rows.empty:
        return None
    row = rows.iloc[0]
    key = "home_team_id" if side == "away" else "away_team_id"
    return _int(row.get(key)) or None


@st.cache_data(ttl=900, show_spinner=False)
def fetch_active_pitchers(team_id: int, season: int, game_date: str) -> dict[str, Any]:
    """Active opponent pitchers as of game date when MLB supports the dated roster."""
    params = {"rosterType": "active", "season": int(season), "hydrate": "person"}
    if str(game_date or ""):
        params["date"] = str(game_date)[:10]
    data: dict[str, Any] | None = None
    dated = bool(params.get("date"))
    try:
        data = _json(f"{MLB_API}/teams/{int(team_id)}/roster", params)
    except Exception:
        if dated:
            try:
                params.pop("date", None)
                data = _json(f"{MLB_API}/teams/{int(team_id)}/roster", params)
            except Exception:
                data = None
    if not data:
        return {"status": "PENDING", "pitchers": [], "source": "MLB active roster unavailable"}

    pitchers: list[dict[str, Any]] = []
    for entry in data.get("roster") or []:
        position = entry.get("position") or {}
        if str(position.get("abbreviation") or "").upper() != "P":
            continue
        person = entry.get("person") or {}
        pid = _int(person.get("id"))
        if not pid:
            continue
        hand = str((person.get("pitchHand") or {}).get("code") or "").upper()[:1]
        pitchers.append(
            {
                "id": pid,
                "name": str(person.get("fullName") or f"Pitcher {pid}"),
                "hand": hand if hand in {"L", "R"} else "—",
                "status": str((entry.get("status") or {}).get("description") or "Active"),
            }
        )
    return {
        "status": "VERIFIED" if pitchers else "PENDING",
        "pitchers": pitchers,
        "source": "Official MLB active roster",
    }


@st.cache_data(ttl=900, show_spinner=False)
def fetch_team_pitcher_stats(team_id: int, season: int) -> dict[str, Any]:
    """One-call MLB season pitching lines for the opponent's pitchers."""
    try:
        data = _json(
            f"{MLB_API}/stats",
            {
                "stats": "season",
                "group": "pitching",
                "season": int(season),
                "gameType": "R",
                "teamId": int(team_id),
                "playerPool": "ALL",
                "limit": 100,
                "hydrate": "person",
            },
        )
        blocks = data.get("stats") or []
        splits = (blocks[0].get("splits") or []) if blocks else []
    except Exception:
        return {"status": "PENDING", "rows": [], "source": "MLB season pitching unavailable"}

    rows: list[dict[str, Any]] = []
    for split in splits:
        player = split.get("player") or split.get("person") or {}
        pid = _int(player.get("id"))
        stat = split.get("stat") or {}
        if not pid or not isinstance(stat, dict):
            continue
        rows.append({"player_id": pid, "player_name": str(player.get("fullName") or f"Pitcher {pid}"), "stat": stat})
    return {
        "status": "VERIFIED" if rows else "PENDING",
        "rows": rows,
        "source": "Official MLB individual season pitching stats",
    }


def _daily_pitching_rows(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    blocks = (data or {}).get("stats") or []
    splits = (blocks[0].get("splits") or []) if blocks else []
    out: list[dict[str, Any]] = []
    for split in splits:
        player = split.get("player") or split.get("person") or {}
        pid = _int(player.get("id"))
        stat = split.get("stat") or {}
        if not pid or not stat:
            continue
        out.append(
            {
                "player_id": pid,
                "pitches": _int(stat.get("numberOfPitches") or stat.get("pitchesThrown")),
                "ip": _ip(stat.get("inningsPitched")),
                "games": _int(stat.get("gamesPlayed")),
            }
        )
    return out


@st.cache_data(ttl=900, show_spinner=False)
def fetch_recent_workload(team_id: int, season: int, game_date: str, days: int = WORKLOAD_DAYS) -> dict[str, Any]:
    """Opponent pitcher workloads for each of the three calendar days before first pitch."""
    target = _date(game_date)
    if target is None:
        return {"status": "PENDING", "days": [], "source": "game date unavailable"}
    day_payloads: list[dict[str, Any]] = []
    verified = 0
    for offset in range(1, max(1, int(days)) + 1):
        day = target - timedelta(days=offset)
        day_text = day.isoformat()
        try:
            data = _json(
                f"{MLB_API}/stats",
                {
                    "stats": "byDateRange",
                    "group": "pitching",
                    "teamId": int(team_id),
                    "season": int(season),
                    "gameType": "R",
                    "startDate": day_text,
                    "endDate": day_text,
                    "playerPool": "ALL",
                    "limit": 100,
                    "hydrate": "person",
                },
            )
            rows = _daily_pitching_rows(data)
            day_payloads.append({"date": day_text, "offset": offset, "status": "VERIFIED", "rows": rows})
            verified += 1
        except Exception:
            day_payloads.append({"date": day_text, "offset": offset, "status": "PENDING", "rows": []})
    return {
        "status": "VERIFIED" if verified == max(1, int(days)) else "PARTIAL" if verified else "PENDING",
        "days": day_payloads,
        "source": "Official MLB prior-day pitching workloads",
    }


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_savant_expected_table(season: int) -> dict[str, Any]:
    """One expected-statistics leaderboard request for all bullpen pitchers."""
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
        frame = pd.read_csv(StringIO(response.text))
        return {"status": "VERIFIED" if not frame.empty else "PENDING", "frame": frame, "source": "Baseball Savant expected statistics"}
    except Exception:
        return {"status": "PENDING", "frame": None, "source": "Baseball Savant expected statistics unavailable"}


def is_reliever(stat: dict[str, Any], starter_id: int | None = None, player_id: int | None = None) -> bool:
    if starter_id and player_id and int(starter_id) == int(player_id):
        return False
    games = _int(stat.get("gamesPlayed"))
    starts = _int(stat.get("gamesStarted"))
    innings = _ip(stat.get("inningsPitched"))
    if games <= 0 or innings <= 0:
        return False
    return starts <= RELIEVER_MAX_STARTS or starts / max(games, 1) <= RELIEVER_MAX_START_SHARE


def fatigue_status(day1_pitches: int, day2_pitches: int, workload_verified: bool = True) -> dict[str, Any]:
    """Transparent availability flag from the two most recent calendar days."""
    p1 = max(0, int(day1_pitches or 0))
    p2 = max(0, int(day2_pitches or 0))
    p2_total = p1 + p2
    if not workload_verified:
        return {"status": "UNKNOWN", "availability": None, "reason": "recent workload feed incomplete"}
    if p1 >= LIMITED_YESTERDAY_PITCHES or p2_total >= LIMITED_TWO_DAY_PITCHES:
        return {"status": "LIMITED", "availability": 0.35, "reason": f"{p1} pitches yesterday / {p2_total} over two days"}
    if p1 >= WATCH_YESTERDAY_PITCHES or p2_total >= WATCH_TWO_DAY_PITCHES or (p1 > 0 and p2 > 0):
        return {"status": "WATCH", "availability": 0.65, "reason": f"{p1} pitches yesterday / {p2_total} over two days"}
    return {"status": "READY", "availability": 1.0, "reason": f"{p1} pitches yesterday / {p2_total} over two days"}


def _workload_maps(recent: dict[str, Any] | None) -> tuple[dict[int, dict[int, int]], bool]:
    maps: dict[int, dict[int, int]] = {}
    days = (recent or {}).get("days") or []
    verified = len(days) >= 2 and all(str(day.get("status")) == "VERIFIED" for day in days[:2])
    for day in days:
        offset = _int(day.get("offset"))
        if not offset:
            continue
        maps[offset] = {int(row["player_id"]): _int(row.get("pitches")) for row in day.get("rows") or [] if _int(row.get("player_id"))}
    return maps, verified


def _savant_map(payload: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    if not payload or payload.get("status") != "VERIFIED":
        return {}
    frame = payload.get("frame")
    if frame is None or frame.empty:
        return {}
    id_col = _column(frame, ("player_id", "player id", "id"))
    if id_col is None:
        return {}
    out: dict[int, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        pid = _int(row.get(id_col))
        if not pid:
            continue
        out[pid] = {
            "pa": _int(_row_value(row, frame, ("pa", "plate appearances"))),
            "xera": _float(_row_value(row, frame, ("xera", "est_era", "expected era"))),
            "xba_allowed": _rate(_row_value(row, frame, ("est_ba", "xba", "xavg", "expected batting average"))),
        }
    return out


def _weighted(rows: list[dict[str, Any]], key: str, weight_key: str) -> float | None:
    num = den = 0.0
    for row in rows:
        value = _float(row.get(key))
        weight = _float(row.get(weight_key))
        if value is None or weight is None or weight <= 0:
            continue
        num += value * weight
        den += weight
    return num / den if den > 0 else None


def _metric_score(value: float | None, center: float, scale: float, lower_is_tougher: bool) -> float | None:
    if value is None:
        return None
    direction = (center - value) if lower_is_tougher else (value - center)
    return _clamp(50.0 + direction * scale, 10.0, 90.0)


def bullpen_quality_score(metrics: dict[str, Any]) -> dict[str, Any]:
    """Descriptive bullpen difficulty index; higher means a tougher relief corps."""
    pieces: list[tuple[float, float]] = []

    def add(value: float | None, weight: float, center: float, scale: float, lower: bool) -> None:
        score = _metric_score(value, center, scale, lower)
        if score is not None:
            pieces.append((score, weight))

    add(_float(metrics.get("xera")), 0.25, 4.20, 12.0, True)
    add(_float(metrics.get("era")), 0.15, 4.20, 10.0, True)
    add(_float(metrics.get("whip")), 0.15, 1.30, 50.0, True)
    add(_float(metrics.get("xba_allowed")), 0.15, 0.245, 250.0, True)
    add(_float(metrics.get("h9")), 0.10, 8.70, 8.0, True)
    k_minus_bb = None
    if metrics.get("k_pct") is not None and metrics.get("bb_pct") is not None:
        k_minus_bb = float(metrics["k_pct"]) - float(metrics["bb_pct"])
    add(k_minus_bb, 0.20, 0.150, 150.0, False)

    total_weight = sum(weight for _, weight in pieces)
    if total_weight <= 0:
        return {"score": None, "coverage": 0.0, "label": "PENDING"}
    score = sum(value * weight for value, weight in pieces) / total_weight
    if score >= 70:
        label = "ELITE / VERY TOUGH BULLPEN"
    elif score >= 60:
        label = "STRONG BULLPEN"
    elif score >= 45:
        label = "AVERAGE BULLPEN"
    elif score >= 35:
        label = "BELOW-AVERAGE BULLPEN"
    else:
        label = "VULNERABLE BULLPEN"
    return {"score": int(round(score)), "coverage": min(1.0, total_weight), "label": label}


def starter_to_bullpen_exposure(starter_profile: dict[str, Any] | None) -> dict[str, Any]:
    """Nominal nine-inning bullpen share from Step 3 workload; not a PA projection."""
    profile = starter_profile or {}
    season_ip = _float(profile.get("ip_per_start"))
    recent5 = profile.get("recent5") or {}
    recent_ip = _float(recent5.get("ip_per_start")) if recent5.get("status") == "VERIFIED" else None
    if season_ip is None and recent_ip is None:
        return {"status": "PENDING", "starter_ip": None, "bullpen_ip": None, "bullpen_inning_share": None, "basis": "starter workload unavailable"}
    if season_ip is not None and recent_ip is not None:
        expected_starter_ip = 0.65 * season_ip + 0.35 * recent_ip
        basis = "65% season IP/start + 35% recent-5 IP/start"
    else:
        expected_starter_ip = season_ip if season_ip is not None else recent_ip
        basis = "season IP/start" if season_ip is not None else "recent-5 IP/start"
    expected_starter_ip = _clamp(float(expected_starter_ip), 3.5, 7.0)
    bullpen_ip = max(0.0, 9.0 - expected_starter_ip)
    return {
        "status": "VERIFIED",
        "starter_ip": expected_starter_ip,
        "bullpen_ip": bullpen_ip,
        "bullpen_inning_share": bullpen_ip / 9.0,
        "basis": basis,
    }


def _data_quality(metrics: dict[str, Any]) -> tuple[int, dict[str, tuple[int, int]]]:
    roster = 15 if metrics.get("active_status") == "VERIFIED" else 0
    season = 25 if metrics.get("reliever_count", 0) >= 4 and metrics.get("era") is not None and metrics.get("whip") is not None else 12 if metrics.get("reliever_count", 0) > 0 else 0
    expected = 0
    expected += 8 if metrics.get("xera") is not None else 0
    expected += 7 if metrics.get("xba_allowed") is not None else 0
    hand = 10 if metrics.get("hand_coverage", 0.0) >= 0.80 else 5 if metrics.get("hand_coverage", 0.0) > 0 else 0
    workload = 25 if metrics.get("workload_status") == "VERIFIED" else 12 if metrics.get("workload_status") == "PARTIAL" else 0
    exposure = 10 if metrics.get("exposure_status") == "VERIFIED" else 0
    components = {
        "Active relief roster": (roster, 15),
        "Season bullpen stats": (season, 25),
        "Expected stats": (expected, 15),
        "Handedness mix": (hand, 10),
        "Recent workload": (workload, 25),
        "Starter-to-bullpen exposure": (exposure, 10),
    }
    return sum(v[0] for v in components.values()), components


def quality_label(score: int) -> str:
    if score >= 90:
        return "ELITE BULLPEN DATA"
    if score >= 75:
        return "STRONG BULLPEN DATA"
    if score >= 60:
        return "USABLE BULLPEN DATA"
    if score >= 40:
        return "PARTIAL BULLPEN DATA"
    return "LOW BULLPEN DATA"


def build_bullpen_profile(
    foundation: dict[str, Any],
    opponent_team_id: int | None,
    active_payload: dict[str, Any] | None,
    season_payload: dict[str, Any] | None,
    recent_payload: dict[str, Any] | None,
    savant_payload: dict[str, Any] | None,
    starter_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    active_payload = active_payload or {"status": "PENDING", "pitchers": []}
    season_payload = season_payload or {"status": "PENDING", "rows": []}
    recent_payload = recent_payload or {"status": "PENDING", "days": []}
    savant_payload = savant_payload or {"status": "PENDING", "frame": None}

    active = {int(row["id"]): row for row in active_payload.get("pitchers") or [] if _int(row.get("id"))}
    season_rows = {int(row["player_id"]): row for row in season_payload.get("rows") or [] if _int(row.get("player_id"))}
    workload_maps, workload_verified = _workload_maps(recent_payload)
    savant = _savant_map(savant_payload)
    starter_id = _int(foundation.get("starter_id")) or None

    relievers: list[dict[str, Any]] = []
    for pid, roster_row in active.items():
        season_row = season_rows.get(pid)
        if not season_row:
            continue
        stat = season_row.get("stat") or {}
        if not is_reliever(stat, starter_id, pid):
            continue
        innings = _ip(stat.get("inningsPitched"))
        hits = _int(stat.get("hits"))
        walks = _int(stat.get("baseOnBalls"))
        earned_runs = _int(stat.get("earnedRuns"))
        strikeouts = _int(stat.get("strikeOuts"))
        batters_faced = _int(stat.get("battersFaced"))
        day1 = (workload_maps.get(1) or {}).get(pid, 0)
        day2 = (workload_maps.get(2) or {}).get(pid, 0)
        day3 = (workload_maps.get(3) or {}).get(pid, 0)
        fatigue = fatigue_status(day1, day2, workload_verified)
        expected = savant.get(pid) or {}
        relievers.append(
            {
                "player_id": pid,
                "name": roster_row.get("name") or season_row.get("player_name") or f"Pitcher {pid}",
                "hand": roster_row.get("hand") or "—",
                "games": _int(stat.get("gamesPlayed")),
                "starts": _int(stat.get("gamesStarted")),
                "ip": innings,
                "hits": hits,
                "walks": walks,
                "earned_runs": earned_runs,
                "strikeouts": strikeouts,
                "batters_faced": batters_faced,
                "era": 9.0 * earned_runs / innings if innings > 0 else None,
                "whip": (hits + walks) / innings if innings > 0 else None,
                "k_pct": strikeouts / batters_faced if batters_faced > 0 else None,
                "bb_pct": walks / batters_faced if batters_faced > 0 else None,
                "day1_pitches": day1,
                "day2_pitches": day2,
                "day3_pitches": day3,
                "two_day_pitches": day1 + day2,
                "fatigue_status": fatigue.get("status"),
                "availability": fatigue.get("availability"),
                "fatigue_reason": fatigue.get("reason"),
                "savant_pa": _int(expected.get("pa")),
                "xera": _float(expected.get("xera")),
                "xba_allowed": _rate(expected.get("xba_allowed")),
            }
        )

    relievers.sort(key=lambda row: float(row.get("ip") or 0.0), reverse=True)
    ip = sum(float(row.get("ip") or 0.0) for row in relievers)
    hits = sum(_int(row.get("hits")) for row in relievers)
    walks = sum(_int(row.get("walks")) for row in relievers)
    er = sum(_int(row.get("earned_runs")) for row in relievers)
    strikeouts = sum(_int(row.get("strikeouts")) for row in relievers)
    bf = sum(_int(row.get("batters_faced")) for row in relievers)

    era = 9.0 * er / ip if ip > 0 else None
    whip = (hits + walks) / ip if ip > 0 else None
    h9 = 9.0 * hits / ip if ip > 0 else None
    k_pct = strikeouts / bf if bf > 0 else None
    bb_pct = walks / bf if bf > 0 else None

    xera = _weighted(relievers, "xera", "savant_pa")
    xba_allowed = _weighted(relievers, "xba_allowed", "savant_pa")
    expected_pa = sum(_int(row.get("savant_pa")) for row in relievers if row.get("xera") is not None or row.get("xba_allowed") is not None)

    handed_ip = sum(float(row.get("ip") or 0.0) for row in relievers if row.get("hand") in {"L", "R"})
    left_ip = sum(float(row.get("ip") or 0.0) for row in relievers if row.get("hand") == "L")
    right_ip = sum(float(row.get("ip") or 0.0) for row in relievers if row.get("hand") == "R")
    hand_coverage = handed_ip / ip if ip > 0 else 0.0
    left_share = left_ip / handed_ip if handed_ip > 0 else None
    right_share = right_ip / handed_ip if handed_ip > 0 else None

    known_availability = [row for row in relievers if row.get("availability") is not None]
    availability_index = None
    if known_availability:
        denom = sum(float(row.get("ip") or 0.0) for row in known_availability)
        availability_index = (
            sum(float(row.get("ip") or 0.0) * float(row.get("availability") or 0.0) for row in known_availability) / denom
            if denom > 0 else None
        )
    ready = sum(1 for row in relievers if row.get("fatigue_status") == "READY")
    watch = sum(1 for row in relievers if row.get("fatigue_status") == "WATCH")
    limited = sum(1 for row in relievers if row.get("fatigue_status") == "LIMITED")
    unknown = sum(1 for row in relievers if row.get("fatigue_status") == "UNKNOWN")

    metrics = {
        "era": era,
        "xera": xera,
        "whip": whip,
        "h9": h9,
        "k_pct": k_pct,
        "bb_pct": bb_pct,
        "xba_allowed": xba_allowed,
    }
    quality = bullpen_quality_score(metrics)
    exposure = starter_to_bullpen_exposure(starter_profile)

    path_score = quality.get("score")
    if path_score is not None and availability_index is not None:
        availability_modifier = _clamp((availability_index - 0.80) * 25.0, -8.0, 5.0)
        path_score = int(round(_clamp(float(path_score) + availability_modifier, 15.0, 85.0)))
    if path_score is None:
        path_label = "PENDING"
    elif path_score >= 70:
        path_label = "VERY TOUGH RELIEF PATH"
    elif path_score >= 60:
        path_label = "TOUGH RELIEF PATH"
    elif path_score >= 45:
        path_label = "NEUTRAL RELIEF PATH"
    elif path_score >= 35:
        path_label = "FAVORABLE RELIEF PATH"
    else:
        path_label = "VERY FAVORABLE RELIEF PATH"

    quality_inputs = {
        **metrics,
        "active_status": active_payload.get("status"),
        "reliever_count": len(relievers),
        "hand_coverage": hand_coverage,
        "workload_status": recent_payload.get("status"),
        "exposure_status": exposure.get("status"),
    }
    data_score, components = _data_quality(quality_inputs)

    return {
        **foundation,
        "opponent_team_id_step8": opponent_team_id,
        "active_roster_status": active_payload.get("status") or "PENDING",
        "season_pitching_status": season_payload.get("status") or "PENDING",
        "workload_status": recent_payload.get("status") or "PENDING",
        "savant_status": savant_payload.get("status") or "PENDING",
        "reliever_count": len(relievers),
        "bullpen_innings": ip,
        "bullpen_hits_allowed": hits,
        "bullpen_walks": walks,
        "bullpen_strikeouts": strikeouts,
        "era": era,
        "xera": xera,
        "whip": whip,
        "h9": h9,
        "k_pct": k_pct,
        "bb_pct": bb_pct,
        "xba_allowed": xba_allowed,
        "expected_stats_pa": expected_pa,
        "left_share": left_share,
        "right_share": right_share,
        "hand_coverage": hand_coverage,
        "availability_index": availability_index,
        "ready_count": ready,
        "watch_count": watch,
        "limited_count": limited,
        "unknown_count": unknown,
        "relievers": relievers,
        "bullpen_quality_score": quality.get("score"),
        "bullpen_quality_label": quality.get("label"),
        "bullpen_quality_coverage": quality.get("coverage"),
        "bullpen_path_score": path_score,
        "bullpen_path_label": path_label,
        "exposure": exposure,
        "expected_starter_ip": exposure.get("starter_ip"),
        "expected_bullpen_ip": exposure.get("bullpen_ip"),
        "bullpen_inning_share": exposure.get("bullpen_inning_share"),
        "exposure_basis": exposure.get("basis"),
        "bullpen_data_score": int(data_score),
        "bullpen_data_label": quality_label(int(data_score)),
        "bullpen_data_components": components,
        "active_source": active_payload.get("source") or "UNAVAILABLE",
        "season_source": season_payload.get("source") or "UNAVAILABLE",
        "workload_source": recent_payload.get("source") or "UNAVAILABLE",
        "savant_source": savant_payload.get("source") or "UNAVAILABLE",
    }


__all__ = [
    "LIMITED_TWO_DAY_PITCHES",
    "LIMITED_YESTERDAY_PITCHES",
    "RELIEVER_MAX_STARTS",
    "RELIEVER_MAX_START_SHARE",
    "WATCH_TWO_DAY_PITCHES",
    "WATCH_YESTERDAY_PITCHES",
    "WORKLOAD_DAYS",
    "build_bullpen_profile",
    "bullpen_quality_score",
    "fatigue_status",
    "fetch_active_pitchers",
    "fetch_recent_workload",
    "fetch_savant_expected_table",
    "fetch_team_pitcher_stats",
    "is_reliever",
    "quality_label",
    "resolve_opponent_team_id",
    "starter_to_bullpen_exposure",
]
