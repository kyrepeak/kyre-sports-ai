"""Plate-appearance opportunity helpers for MLB Matchup Intelligence V2 Step 9.

Step 9 estimates how many trips to the plate a verified batting-order slot is likely
to receive. It uses team plate-appearance volume, batting-order position, home/away
history, recent team PA volume, hitter AB/PA conversion, and the certified Step 8
starter-to-bullpen inning path. It does not calculate hit probability, fair odds,
Monte Carlo outcomes, calibration, rankings, or any final selection signal.
"""
from __future__ import annotations

import math
from statistics import mean
from typing import Any

import pandas as pd
import requests
import streamlit as st

MLB_API = "https://statsapi.mlb.com/api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 KyreSportsAI/MatchupV2Step9",
    "Accept": "application/json,text/plain,*/*",
}

RECENT_GAMES = 10
RECENT_MIN_GAMES = 5
LOCATION_MIN_GAMES = 12
RANGE_MIN_GAMES = 10
MIN_HITTER_PA_FOR_AB_RATIO = 50
TEAM_PA_MIN_PLAUSIBLE = 25.0
TEAM_PA_MAX_PLAUSIBLE = 60.0


def _float(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _int(value: Any) -> int:
    val = _float(value)
    return int(val) if val is not None else 0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(url, params=params or {}, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.json()


def resolve_batting_team_id(games_df: pd.DataFrame | None, foundation: dict[str, Any]) -> int | None:
    """Resolve the selected hitter's team ID from the verified Step 1 game row."""
    if games_df is None or games_df.empty or "game_pk" not in games_df.columns:
        return None
    game_pk = _int(foundation.get("game_pk"))
    side = str(foundation.get("side") or "").strip().lower()
    if not game_pk or side not in {"home", "away"}:
        return None
    ids = pd.to_numeric(games_df["game_pk"], errors="coerce")
    rows = games_df[ids == game_pk]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return _int(row.get(f"{side}_team_id")) or None


@st.cache_data(ttl=900, show_spinner=False)
def fetch_team_hitting_season(team_id: int, season: int) -> dict[str, Any]:
    """Official MLB team season hitting totals used only for opportunity volume."""
    try:
        data = _json(
            f"{MLB_API}/stats",
            {
                "stats": "season",
                "group": "hitting",
                "season": int(season),
                "gameType": "R",
                "teamId": int(team_id),
            },
        )
        blocks = data.get("stats") or []
        splits = (blocks[0].get("splits") or []) if blocks else []
        stat = (splits[0].get("stat") or {}) if splits else {}
    except Exception:
        stat = {}
    if not stat:
        return {"status": "PENDING", "source": "MLB team season hitting unavailable"}
    return {
        "status": "VERIFIED",
        "source": "Official MLB team season hitting",
        "games": _int(stat.get("gamesPlayed")),
        "pa": _int(stat.get("plateAppearances")),
        "ab": _int(stat.get("atBats")),
        "runs": _int(stat.get("runs")),
        "hits": _int(stat.get("hits")),
        "walks": _int(stat.get("baseOnBalls")),
    }


def _parse_game_logs(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    blocks = (data or {}).get("stats") or []
    splits = (blocks[0].get("splits") or []) if blocks else []
    rows: list[dict[str, Any]] = []
    for split in splits:
        stat = split.get("stat") or {}
        pa = _int(stat.get("plateAppearances"))
        if pa <= 0:
            continue
        game = split.get("game") or {}
        is_home_raw = split.get("isHome")
        if is_home_raw is None:
            is_home = None
        else:
            is_home = bool(is_home_raw)
        rows.append(
            {
                "date": str(split.get("date") or "")[:10],
                "game_pk": _int(game.get("gamePk")) or None,
                "is_home": is_home,
                "pa": pa,
                "ab": _int(stat.get("atBats")),
                "runs": _int(stat.get("runs")),
                "hits": _int(stat.get("hits")),
            }
        )
    rows.sort(key=lambda row: row.get("date") or "", reverse=True)
    return rows


@st.cache_data(ttl=900, show_spinner=False)
def fetch_team_hitting_logs(team_id: int, season: int) -> dict[str, Any]:
    """Official MLB team game logs; fallback endpoint keeps the feed fail-soft."""
    data: dict[str, Any] | None = None
    try:
        data = _json(
            f"{MLB_API}/teams/{int(team_id)}/stats",
            {"stats": "gameLog", "group": "hitting", "season": int(season), "gameType": "R"},
        )
    except Exception:
        try:
            data = _json(
                f"{MLB_API}/stats",
                {
                    "stats": "gameLog",
                    "group": "hitting",
                    "season": int(season),
                    "gameType": "R",
                    "teamId": int(team_id),
                },
            )
        except Exception:
            data = None
    rows = _parse_game_logs(data)
    return {
        "status": "VERIFIED" if rows else "PENDING",
        "source": "Official MLB team hitting game logs" if rows else "MLB team game logs unavailable",
        "games": rows,
    }


def slot_pa_from_team_total(team_pa: int, slot: int) -> int | None:
    """Exact batting-slot PA count implied by an integer team PA total.

    With a nine-man batting order, every full cycle gives every slot one PA and the
    remainder is assigned in batting-order sequence beginning with slot 1.
    """
    total = _int(team_pa)
    spot = _int(slot)
    if total <= 0 or not 1 <= spot <= 9:
        return None
    cycles, remainder = divmod(total, 9)
    return cycles + (1 if remainder >= spot else 0)


def slot_pa_from_expected_team_pa(team_pa: float | None, slot: int) -> float | None:
    """Continuous interpolation of the nine-slot batting cycle for mean team PA."""
    total = _float(team_pa)
    spot = _int(slot)
    if total is None or total <= 0 or not 1 <= spot <= 9:
        return None
    cycles = math.floor(total / 9.0)
    remainder = total - cycles * 9.0
    extra = _clamp(remainder - (spot - 1), 0.0, 1.0)
    return float(cycles) + extra


def _mean(values: list[float]) -> float | None:
    clean = [float(value) for value in values if _float(value) is not None]
    return mean(clean) if clean else None


def _quantile(values: list[float], q: float) -> float | None:
    clean = sorted(float(value) for value in values if _float(value) is not None)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    pos = _clamp(float(q), 0.0, 1.0) * (len(clean) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return clean[lo]
    frac = pos - lo
    return clean[lo] * (1.0 - frac) + clean[hi] * frac


def _valid_team_pa(value: float | None) -> bool:
    return value is not None and TEAM_PA_MIN_PLAUSIBLE <= float(value) <= TEAM_PA_MAX_PLAUSIBLE


def opportunity_from_team_volume(
    foundation: dict[str, Any],
    season_payload: dict[str, Any] | None,
    log_payload: dict[str, Any] | None,
    bullpen_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the Step 9 opportunity profile without any hit-probability math."""
    season_payload = season_payload or {}
    log_payload = log_payload or {}
    bullpen_profile = bullpen_profile or {}
    slot = _int(foundation.get("slot"))
    valid_slot = bool(foundation.get("valid_slot")) and 1 <= slot <= 9
    side = str(foundation.get("side") or "").strip().lower()
    is_home = side == "home"

    season_games = _int(season_payload.get("games"))
    season_pa = _int(season_payload.get("pa"))
    season_pa_pg = season_pa / season_games if season_games > 0 and season_pa > 0 else None
    if season_pa_pg is not None and not _valid_team_pa(season_pa_pg):
        season_pa_pg = None

    logs = list(log_payload.get("games") or [])
    usable_logs = [row for row in logs if _valid_team_pa(_float(row.get("pa")))]
    location_logs = [row for row in usable_logs if row.get("is_home") is is_home]
    recent_logs = usable_logs[:RECENT_GAMES]

    location_pa_pg = _mean([row["pa"] for row in location_logs]) if len(location_logs) >= LOCATION_MIN_GAMES else None
    recent_pa_pg = _mean([row["pa"] for row in recent_logs]) if len(recent_logs) >= RECENT_MIN_GAMES else None

    volume_pieces: list[tuple[float, float, str]] = []
    if season_pa_pg is not None:
        volume_pieces.append((season_pa_pg, 0.55, "season"))
    if location_pa_pg is not None:
        volume_pieces.append((location_pa_pg, 0.25, "home" if is_home else "away"))
    if recent_pa_pg is not None:
        volume_pieces.append((recent_pa_pg, 0.20, "recent10"))
    volume_weight = sum(weight for _, weight, _ in volume_pieces)
    expected_team_pa = (
        sum(value * weight for value, weight, _ in volume_pieces) / volume_weight
        if volume_weight > 0
        else None
    )

    slot_values_all = [slot_pa_from_team_total(row["pa"], slot) for row in usable_logs] if valid_slot else []
    slot_values_all = [float(value) for value in slot_values_all if value is not None]
    slot_values_location = [slot_pa_from_team_total(row["pa"], slot) for row in location_logs] if valid_slot else []
    slot_values_location = [float(value) for value in slot_values_location if value is not None]
    slot_values_recent = [slot_pa_from_team_total(row["pa"], slot) for row in recent_logs] if valid_slot else []
    slot_values_recent = [float(value) for value in slot_values_recent if value is not None]

    slot_pieces: list[tuple[float, float, str]] = []
    season_slot = _mean(slot_values_all)
    if season_slot is None and valid_slot:
        season_slot = slot_pa_from_expected_team_pa(season_pa_pg, slot)
    if season_slot is not None:
        slot_pieces.append((season_slot, 0.55, "season slot cycle"))
    location_slot = _mean(slot_values_location) if len(slot_values_location) >= LOCATION_MIN_GAMES else None
    if location_slot is not None:
        slot_pieces.append((location_slot, 0.25, "home slot history" if is_home else "away slot history"))
    recent_slot = _mean(slot_values_recent) if len(slot_values_recent) >= RECENT_MIN_GAMES else None
    if recent_slot is not None:
        slot_pieces.append((recent_slot, 0.20, "recent10 slot history"))

    slot_weight = sum(weight for _, weight, _ in slot_pieces)
    expected_pa = (
        sum(value * weight for value, weight, _ in slot_pieces) / slot_weight
        if valid_slot and slot_weight > 0
        else None
    )

    range_values = slot_values_location if len(slot_values_location) >= LOCATION_MIN_GAMES else slot_values_all
    pa_low = _quantile(range_values, 0.10) if len(range_values) >= RANGE_MIN_GAMES else None
    pa_high = _quantile(range_values, 0.90) if len(range_values) >= RANGE_MIN_GAMES else None

    hitter_pa = _int(foundation.get("season_pa"))
    hitter_ab = _int(foundation.get("season_ab"))
    ab_per_pa = hitter_ab / hitter_pa if hitter_pa >= MIN_HITTER_PA_FOR_AB_RATIO and hitter_ab > 0 else None
    expected_ab = expected_pa * ab_per_pa if expected_pa is not None and ab_per_pa is not None else None
    ab_low = pa_low * ab_per_pa if pa_low is not None and ab_per_pa is not None else None
    ab_high = pa_high * ab_per_pa if pa_high is not None and ab_per_pa is not None else None

    bullpen_share = _float(bullpen_profile.get("bullpen_inning_share"))
    exposure_status = str((bullpen_profile.get("exposure") or {}).get("status") or "PENDING")
    if bullpen_share is None or not 0.0 <= bullpen_share <= 1.0 or exposure_status != "VERIFIED":
        bullpen_share = None
    nominal_bullpen_pa = expected_pa * bullpen_share if expected_pa is not None and bullpen_share is not None else None
    nominal_starter_pa = expected_pa - nominal_bullpen_pa if expected_pa is not None and nominal_bullpen_pa is not None else None

    if recent_pa_pg is None or season_pa_pg is None:
        offense_volume_label = "TEAM PA TREND PENDING"
    else:
        delta = recent_pa_pg - season_pa_pg
        if delta >= 1.5:
            offense_volume_label = "RECENT PA VOLUME ABOVE SEASON"
        elif delta <= -1.5:
            offense_volume_label = "RECENT PA VOLUME BELOW SEASON"
        else:
            offense_volume_label = "RECENT PA VOLUME NEAR SEASON"

    if is_home and location_pa_pg is not None:
        ninth_note = "Home ninth-inning non-batting risk is absorbed empirically by the team's home-game PA history; no extra guessed penalty is added."
    elif is_home:
        ninth_note = "Home ninth-inning non-batting risk exists, but the home split sample is too small; no guessed penalty is added."
    else:
        ninth_note = "Away-game PA history is used when available; no separate ninth-inning penalty is invented."

    if not valid_slot:
        readiness = "GATED"
    elif expected_pa is None:
        readiness = "PARTIAL"
    elif bool(foundation.get("confirmed")):
        readiness = "READY"
    elif bool(foundation.get("projected")):
        readiness = "PROVISIONAL"
    else:
        readiness = "PARTIAL"

    identity_points = 0
    identity_points += 8 if foundation.get("player_id") else 0
    identity_points += 7 if foundation.get("game_pk") else 0
    identity_points += 5 if valid_slot else 0
    season_points = 20 if season_pa_pg is not None else 0
    log_points = 25 if len(usable_logs) >= 20 else 15 if len(usable_logs) >= 10 else 5 if usable_logs else 0
    location_points = 15 if location_pa_pg is not None else 0
    recent_points = 10 if recent_pa_pg is not None else 0
    ab_points = 5 if ab_per_pa is not None else 0
    exposure_points = 5 if bullpen_share is not None else 0
    components = {
        "Identity + lineup slot": (identity_points, 20),
        "Team season PA volume": (season_points, 20),
        "Team game-log sample": (log_points, 25),
        "Home/away PA history": (location_points, 15),
        "Recent-10 PA volume": (recent_points, 10),
        "Hitter AB/PA conversion": (ab_points, 5),
        "Starter/bullpen exposure": (exposure_points, 5),
    }
    completeness = sum(value for value, _ in components.values())
    if completeness >= 90:
        data_label = "ELITE OPPORTUNITY DATA"
    elif completeness >= 75:
        data_label = "STRONG OPPORTUNITY DATA"
    elif completeness >= 60:
        data_label = "USABLE OPPORTUNITY DATA"
    elif completeness >= 40:
        data_label = "PARTIAL OPPORTUNITY DATA"
    else:
        data_label = "LOW OPPORTUNITY DATA"

    return {
        **foundation,
        "team_id_step9": foundation.get("team_id_step9"),
        "opportunity_readiness": readiness,
        "season_team_games": season_games,
        "season_team_pa": season_pa,
        "season_team_pa_per_game": season_pa_pg,
        "location_games": len(location_logs),
        "location_team_pa_per_game": location_pa_pg,
        "recent_games": len(recent_logs),
        "recent_team_pa_per_game": recent_pa_pg,
        "expected_team_pa": expected_team_pa,
        "expected_pa": expected_pa,
        "pa_low": pa_low,
        "pa_high": pa_high,
        "ab_per_pa": ab_per_pa,
        "expected_ab": expected_ab,
        "ab_low": ab_low,
        "ab_high": ab_high,
        "nominal_starter_pa": nominal_starter_pa,
        "nominal_bullpen_pa": nominal_bullpen_pa,
        "bullpen_inning_share_step9": bullpen_share,
        "offense_volume_label": offense_volume_label,
        "ninth_inning_note": ninth_note,
        "volume_basis": [label for _, _, label in volume_pieces],
        "slot_basis": [label for _, _, label in slot_pieces],
        "range_sample_games": len(range_values),
        "team_season_source": season_payload.get("source") or "UNAVAILABLE",
        "team_logs_source": log_payload.get("source") or "UNAVAILABLE",
        "opportunity_data_score": int(completeness),
        "opportunity_data_label": data_label,
        "opportunity_data_components": components,
    }


def build_opportunity_profile(
    foundation: dict[str, Any],
    team_id: int | None,
    season_payload: dict[str, Any] | None,
    log_payload: dict[str, Any] | None,
    bullpen_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    enriched = dict(foundation)
    enriched["team_id_step9"] = team_id
    return opportunity_from_team_volume(enriched, season_payload, log_payload, bullpen_profile)


__all__ = [
    "LOCATION_MIN_GAMES",
    "MIN_HITTER_PA_FOR_AB_RATIO",
    "RANGE_MIN_GAMES",
    "RECENT_GAMES",
    "RECENT_MIN_GAMES",
    "build_opportunity_profile",
    "fetch_team_hitting_logs",
    "fetch_team_hitting_season",
    "opportunity_from_team_volume",
    "resolve_batting_team_id",
    "slot_pa_from_expected_team_pa",
    "slot_pa_from_team_total",
]
