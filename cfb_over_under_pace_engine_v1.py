"""CFB Over/Under Intelligence V2 — Upgrade Step 4 pace engine.

Additive model layer above permanently frozen Upgrade Step 3.

Certified pace evidence
-----------------------
1. NCAA Total Offense -> Games + offensive Plays -> plays/game.
2. NCAA Time of Possession -> AvgTOP -> possession-clock seconds/offensive play.
3. Division-aware baselines are computed from the same NCAA tables.
4. FBS and FCS teams are located independently in their actual NCAA stat pool;
   mixed-division matchups are allowed because raw plays/time are absolute
   measures, not cross-division rank comparisons.

Projection policy
-----------------
- expected combined plays is the primary pace quantity,
- pace is shrunk heavily toward the relevant division baseline when samples
  are small,
- Time of Possession is a secondary clock/tempo check, never fabricated,
- direct drive/possession counts are intentionally not invented when a
  certified source is unavailable,
- the incremental game-total adjustment is capped at +/- 2.75 points,
- frozen reliability and structural sigma are not inflated/reduced,
- the analysis total line has exactly 0% pace/projection weight.

No sportsbook feed, market-implied probability, EV, price, or Monte Carlo is
introduced here.
"""
from __future__ import annotations

from statistics import median
from typing import Any, Mapping
from urllib.parse import urljoin

import streamlit as st

import cfb_over_under_matchup_engine_v1 as step3
import cfb_over_under_model_v1 as frozen_raw
import cfb_team_data_v1 as frozen_team

MODEL_VERSION = "CFB O/U PACE ENGINE V1 • UPGRADE STEP 4 EXPECTED PLAYS"
FROZEN_STEP3_ENGINE = "cfb_over_under_matchup_engine_v1"
FROZEN_RAW_MODEL = "cfb_over_under_model_v1"

NCAA_FBS_STATS_INDEX = frozen_team.NCAA_STATS_INDEX
NCAA_FCS_STATS_INDEX = step3.NCAA_FCS_STATS_INDEX

MAX_TOTAL_PACE_ADJUSTMENT = 2.75
MIN_PACE_COVERAGE = 0.75
SAMPLE_GAMES_FULL_WEIGHT = 5.0
PACE_FULL_SIGNAL_RATIO = 0.12
HISTORICAL_PLAYS_WEIGHT = 0.65
CLOCK_IMPLIED_PLAYS_WEIGHT = 0.35
ANALYSIS_LINE_PACE_WEIGHT = 0.0

MIN_EXPECTED_COMBINED_PLAYS = 100.0
MAX_EXPECTED_COMBINED_PLAYS = 180.0


def _clean(value: Any) -> str:
    return frozen_team._clean(value)


def _float(value: Any) -> float | None:
    return frozen_team._float(value)


def _int(value: Any) -> int | None:
    return frozen_team._int(value)


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _norm_header(value: Any) -> str:
    return "".join(ch for ch in _clean(value).lower() if ch.isalnum())


def _header_index(headers: list[str], aliases: tuple[str, ...]) -> int | None:
    normalized = [_norm_header(h) for h in headers]
    wanted = {_norm_header(a) for a in aliases}
    for idx, header in enumerate(normalized):
        if header in wanted:
            return idx
    for idx, header in enumerate(normalized):
        if any(alias and alias in header for alias in wanted):
            return idx
    return None


def _row_value(item: Mapping[str, Any], aliases: tuple[str, ...]) -> str:
    headers = list(item.get("headers") or [])
    row = list(item.get("row") or [])
    idx = _header_index(headers, aliases)
    if idx is None or idx >= len(row):
        return ""
    return _clean(row[idx])


def _games_and_plays(item: Mapping[str, Any]) -> tuple[int | None, float | None]:
    games = _int(_row_value(item, ("G", "Games", "GP")))
    plays = _float(_row_value(item, ("Plays", "Off Plays", "Total Plays")))
    if games is None or games <= 0 or plays is None or plays <= 0:
        return games, None
    return games, float(plays)


def _clock_seconds(value: Any) -> float | None:
    text = _clean(value)
    if not text:
        return None

    if ":" in text:
        parts = text.split(":")
        try:
            if len(parts) == 2:
                minutes = float(parts[0])
                seconds = float(parts[1])
                if minutes < 0 or seconds < 0 or seconds >= 60:
                    return None
                return minutes * 60.0 + seconds
            if len(parts) == 3:
                hours = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])
                if min(hours, minutes, seconds) < 0 or minutes >= 60 or seconds >= 60:
                    return None
                return hours * 3600.0 + minutes * 60.0 + seconds
        except Exception:
            return None

    number = _float(text)
    if number is None or number <= 0:
        return None

    # NCAA AvgTOP is minute-based when rendered without seconds.
    if number <= 60.0:
        return float(number) * 60.0
    return float(number)


def _avg_top_seconds(item: Mapping[str, Any], games: int | None) -> float | None:
    avg = _row_value(
        item,
        ("AvgTOP", "Avg TOP", "Average TOP", "Average Time of Possession"),
    )
    parsed = _clock_seconds(avg)
    if parsed is not None:
        return parsed

    total = _row_value(item, ("TOP", "Time of Possession"))
    total_seconds = _clock_seconds(total)
    if total_seconds is None or games is None or games <= 0:
        return None

    # If NCAA renders season TOP as raw total minutes, _clock_seconds already
    # converted that number to seconds; divide by games here.
    return float(total_seconds) / float(games)


def _discover_time_of_possession(html: str) -> str:
    parser = step3._CategoryOptionParser()
    parser.feed(html or "")
    for label, path in parser.options:
        lower = _clean(label).lower()
        if "time of possession" in lower:
            return urljoin(frozen_team.NCAA_ROOT, path)
    return ""


@st.cache_data(ttl=300, show_spinner=False)
def _load_pace_division(
    division: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    division = _clean(division).upper()
    stats_index = NCAA_FCS_STATS_INDEX if division == "FCS" else NCAA_FBS_STATS_INDEX

    tables, step3_diag = step3._load_division_tables(stats_index, division)
    total_offense = dict(tables.get("total_offense") or {})

    attempts: list[dict[str, Any]] = []
    index_html, index_attempts = frozen_team._fetch_text_with_fallback(
        stats_index,
        f"NCAA {division} pace category index",
    )
    attempts.extend(index_attempts)

    top_url = _discover_time_of_possession(index_html)
    time_of_possession: dict[str, dict[str, Any]] = {}
    top_diag: dict[str, Any] = {}
    if top_url:
        time_of_possession, top_diag = step3._load_category_table(
            top_url,
            f"NCAA {division} Time of Possession",
        )
        attempts.extend(top_diag.get("attempts") or [])

    play_rates: list[float] = []
    seconds_per_play_rates: list[float] = []
    for key, item in total_offense.items():
        games, plays = _games_and_plays(item)
        if games is None or plays is None:
            continue
        plays_pg = plays / float(games)
        if 35.0 <= plays_pg <= 100.0:
            play_rates.append(float(plays_pg))

        top_item = time_of_possession.get(key) or {}
        avg_top = _avg_top_seconds(top_item, games)
        if avg_top is not None and plays_pg > 0:
            spp = avg_top / plays_pg
            if 15.0 <= spp <= 40.0:
                seconds_per_play_rates.append(float(spp))

    baseline_plays = float(median(play_rates)) if play_rates else None
    baseline_spp = (
        float(median(seconds_per_play_rates))
        if seconds_per_play_rates
        else None
    )

    return {
        "division": division,
        "total_offense": total_offense,
        "time_of_possession": dict(time_of_possession),
        "baseline_plays_per_game": baseline_plays,
        "baseline_seconds_per_play": baseline_spp,
        "field_size": len(total_offense),
    }, {
        "division": division,
        "step3_table_diag": step3_diag,
        "top_url": top_url,
        "top_diag": top_diag,
        "attempts": attempts,
        "total_offense_rows": len(total_offense),
        "time_of_possession_rows": len(time_of_possession),
        "baseline_plays_per_game": baseline_plays,
        "baseline_seconds_per_play": baseline_spp,
    }


def _lookup(
    table: Mapping[str, Mapping[str, Any]],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    return step3._lookup_team(table, profile)


def _profile_division_hint(profile: Mapping[str, Any]) -> str:
    explicit = _clean(profile.get("division_context")).upper()
    if explicit in {"FBS", "FCS"}:
        return explicit
    source = _clean(profile.get("data_source")).lower()
    if "fcs" in source:
        return "FCS"
    return "FBS"


def _resolve_division(
    profile: Mapping[str, Any],
    fbs: Mapping[str, Any],
    fcs: Mapping[str, Any],
) -> tuple[str, Mapping[str, Any]]:
    fbs_row = _lookup(fbs.get("total_offense") or {}, profile)
    fcs_row = _lookup(fcs.get("total_offense") or {}, profile)

    if fbs_row and not fcs_row:
        return "FBS", fbs
    if fcs_row and not fbs_row:
        return "FCS", fcs
    if fbs_row and fcs_row:
        hint = _profile_division_hint(profile)
        return (hint, fcs if hint == "FCS" else fbs)
    return "", {}


def _team_pace(
    profile: Mapping[str, Any],
    bundle: Mapping[str, Any],
    division: str,
) -> dict[str, Any]:
    total_row = _lookup(bundle.get("total_offense") or {}, profile)
    top_row = _lookup(bundle.get("time_of_possession") or {}, profile)

    games, plays = _games_and_plays(total_row)
    plays_pg = (
        float(plays) / float(games)
        if games is not None and games > 0 and plays is not None
        else None
    )

    avg_top = _avg_top_seconds(top_row, games)
    seconds_per_play = (
        float(avg_top) / float(plays_pg)
        if avg_top is not None and plays_pg is not None and plays_pg > 0
        else None
    )
    if seconds_per_play is not None and not (15.0 <= seconds_per_play <= 40.0):
        seconds_per_play = None

    baseline_plays = _float(bundle.get("baseline_plays_per_game"))
    pace_index = (
        float(plays_pg) / float(baseline_plays)
        if plays_pg is not None and baseline_plays and baseline_plays > 0
        else None
    )

    return {
        "team": _clean(profile.get("team")),
        "team_slug": _clean(profile.get("team_slug")),
        "division": division,
        "games": games,
        "total_offensive_plays": plays,
        "plays_per_game": plays_pg,
        "avg_time_of_possession_seconds": avg_top,
        "seconds_per_offensive_play": seconds_per_play,
        "division_baseline_plays_per_game": baseline_plays,
        "division_baseline_seconds_per_play": _float(
            bundle.get("baseline_seconds_per_play")
        ),
        "pace_index": pace_index,
        "plays_source": "NCAA Total Offense" if plays_pg is not None else "",
        "clock_source": "NCAA Time of Possession" if seconds_per_play is not None else "",
    }


def _sample_factor(away: Mapping[str, Any], home: Mapping[str, Any]) -> float:
    away_games = _int(away.get("games")) or 0
    home_games = _int(home.get("games")) or 0
    minimum = min(away_games, home_games)
    return _clamp(
        float(minimum) / SAMPLE_GAMES_FULL_WEIGHT,
        0.0,
        1.0,
    )


def _pace_label(ratio: float | None) -> str:
    if ratio is None:
        return "UNAVAILABLE"
    if ratio >= 1.055:
        return "FAST"
    if ratio <= 0.945:
        return "SLOW"
    return "NEUTRAL"


def build_pace_engine(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    fbs, fbs_diag = _load_pace_division("FBS")
    fcs, fcs_diag = _load_pace_division("FCS")

    away_div, away_bundle = _resolve_division(away, fbs, fcs)
    home_div, home_bundle = _resolve_division(home, fbs, fcs)

    if not away_div or not home_div:
        return {
            "version": MODEL_VERSION,
            "ready": True,
            "model_ready": False,
            "reason": "NCAA Total Offense pace row is unavailable for one or both teams",
            "away": {},
            "home": {},
            "coverage": 0.0,
            "analysis_line_pace_weight": ANALYSIS_LINE_PACE_WEIGHT,
            "direct_possessions_available": False,
            "direct_possessions_reason": "direct possession/drive counts are not certified in Step 4",
            "diagnostics": {"FBS": fbs_diag, "FCS": fcs_diag},
            "sportsbook_input_used": False,
            "market_price_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "monte_carlo_used": False,
        }

    away_pace = _team_pace(away, away_bundle, away_div)
    home_pace = _team_pace(home, home_bundle, home_div)

    away_ppg = _float(away_pace.get("plays_per_game"))
    home_ppg = _float(home_pace.get("plays_per_game"))
    away_base = _float(away_pace.get("division_baseline_plays_per_game"))
    home_base = _float(home_pace.get("division_baseline_plays_per_game"))

    plays_ready = all(
        value is not None and value > 0
        for value in (away_ppg, home_ppg, away_base, home_base)
    )
    clock_ready = all(
        (_float(row.get("seconds_per_offensive_play")) or 0.0) > 0
        for row in (away_pace, home_pace)
    )

    coverage = 0.75 if plays_ready else 0.0
    if clock_ready:
        coverage += 0.25

    if not plays_ready or coverage < MIN_PACE_COVERAGE:
        return {
            "version": MODEL_VERSION,
            "ready": True,
            "model_ready": False,
            "reason": "verified offensive-play pace evidence is below the Step-4 minimum",
            "away": away_pace,
            "home": home_pace,
            "coverage": float(coverage),
            "analysis_line_pace_weight": ANALYSIS_LINE_PACE_WEIGHT,
            "direct_possessions_available": False,
            "direct_possessions_reason": "direct possession/drive counts are not certified in Step 4",
            "diagnostics": {"FBS": fbs_diag, "FCS": fcs_diag},
            "sportsbook_input_used": False,
            "market_price_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "monte_carlo_used": False,
        }

    historical_combined = float(away_ppg + home_ppg)
    baseline_combined = float(away_base + home_base)

    clock_implied = None
    if clock_ready:
        away_spp = float(away_pace["seconds_per_offensive_play"])
        home_spp = float(home_pace["seconds_per_offensive_play"])
        if away_spp + home_spp > 0:
            # If each offense receives approximately the same number of snaps,
            # the two teams' possession-time seconds/play must share 3600 game
            # seconds. This is used only as a secondary pace check.
            clock_implied = 7200.0 / (away_spp + home_spp)

    if clock_implied is not None:
        raw_expected = (
            HISTORICAL_PLAYS_WEIGHT * historical_combined
            + CLOCK_IMPLIED_PLAYS_WEIGHT * float(clock_implied)
        )
    else:
        raw_expected = historical_combined

    sample_factor = _sample_factor(away_pace, home_pace)
    expected_combined = (
        baseline_combined
        + sample_factor * (float(raw_expected) - baseline_combined)
    )
    expected_combined = _clamp(
        expected_combined,
        MIN_EXPECTED_COMBINED_PLAYS,
        MAX_EXPECTED_COMBINED_PLAYS,
    )

    pace_ratio = (
        expected_combined / baseline_combined
        if baseline_combined > 0
        else 1.0
    )
    pace_signal = _clamp(
        (pace_ratio - 1.0) / PACE_FULL_SIGNAL_RATIO,
        -1.0,
        1.0,
    )
    total_adjustment = _clamp(
        pace_signal * MAX_TOTAL_PACE_ADJUSTMENT * float(coverage),
        -MAX_TOTAL_PACE_ADJUSTMENT,
        MAX_TOTAL_PACE_ADJUSTMENT,
    )

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "model_ready": True,
        "away": away_pace,
        "home": home_pace,
        "away_division": away_div,
        "home_division": home_div,
        "mixed_division": away_div != home_div,
        "coverage": float(coverage),
        "sample_factor": float(sample_factor),
        "historical_combined_plays_per_game": historical_combined,
        "clock_implied_combined_plays": clock_implied,
        "division_baseline_combined_plays": baseline_combined,
        "expected_combined_plays": float(expected_combined),
        "pace_ratio": float(pace_ratio),
        "pace_signal": float(pace_signal),
        "pace_label": _pace_label(pace_ratio),
        "total_points_adjustment": float(total_adjustment),
        "analysis_line_pace_weight": ANALYSIS_LINE_PACE_WEIGHT,
        "direct_possessions_available": False,
        "expected_combined_possessions": None,
        "direct_possessions_reason": (
            "direct possession/drive counts are not certified; Step 4 uses NCAA "
            "offensive plays and Time of Possession without inventing a drive count"
        ),
        "diagnostics": {"FBS": fbs_diag, "FCS": fcs_diag},
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }


def _lean(p_over: float, p_under: float, p_push: float) -> str:
    if p_push >= max(p_over, p_under):
        return "PASS"
    if p_over > p_under:
        return "OVER"
    if p_under > p_over:
        return "UNDER"
    return "PASS"


def apply_to_raw(
    base_raw: Mapping[str, Any],
    pace: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply bounded Step-4 pace adjustment to a Step-3 raw output."""
    out = dict(base_raw)
    out["base_step3_model_version"] = _clean(base_raw.get("version"))
    out["version"] = MODEL_VERSION
    out["upgrade_step4_pace_ready"] = bool(pace.get("model_ready"))
    out["upgrade_step4_applied"] = False
    out["pace_engine_coverage"] = float(pace.get("coverage") or 0.0)
    out["expected_combined_plays"] = pace.get("expected_combined_plays")
    out["expected_combined_possessions"] = pace.get("expected_combined_possessions")
    out["analysis_line_pace_weight"] = ANALYSIS_LINE_PACE_WEIGHT

    if not base_raw.get("ready") or not pace.get("model_ready"):
        out["pace_engine_reason"] = _clean(
            pace.get("reason")
            or "pace evidence below Step-4 minimum coverage"
        )
        return out

    total_adjustment = float(pace.get("total_points_adjustment") or 0.0)
    base_away = float(base_raw.get("projected_away_points") or 0.0)
    base_home = float(base_raw.get("projected_home_points") or 0.0)
    base_total = max(1e-9, base_away + base_home)

    away_share = base_away / base_total
    home_share = base_home / base_total

    projected_away = frozen_raw._clamp(
        base_away + total_adjustment * away_share,
        frozen_raw.MIN_TEAM_POINTS,
        frozen_raw.MAX_TEAM_POINTS,
    )
    projected_home = frozen_raw._clamp(
        base_home + total_adjustment * home_share,
        frozen_raw.MIN_TEAM_POINTS,
        frozen_raw.MAX_TEAM_POINTS,
    )
    projected_total = projected_away + projected_home

    sigma = float(
        base_raw.get("structural_total_sigma")
        or frozen_raw.BASE_TOTAL_SIGMA
    )
    line = float(base_raw.get("analysis_line") or 0.0)
    p_over, p_under, p_push = frozen_raw._line_probabilities(
        projected_total,
        sigma,
        line,
    )
    interval_low = max(0.0, projected_total - 1.645 * sigma)
    interval_high = projected_total + 1.645 * sigma

    components = dict(base_raw.get("components") or {})
    components.update({
        "step4_total_pace_adjustment": float(
            projected_total - (base_away + base_home)
        ),
        "step4_expected_combined_plays": float(
            pace.get("expected_combined_plays") or 0.0
        ),
        "step4_division_baseline_combined_plays": float(
            pace.get("division_baseline_combined_plays") or 0.0
        ),
        "step4_pace_ratio": float(pace.get("pace_ratio") or 1.0),
        "step4_sample_factor": float(pace.get("sample_factor") or 0.0),
    })

    out.update({
        "upgrade_step4_applied": True,
        "step4_base_projected_away_points": float(base_away),
        "step4_base_projected_home_points": float(base_home),
        "step4_base_projected_total": float(base_away + base_home),
        "projected_away_points": float(projected_away),
        "projected_home_points": float(projected_home),
        "projected_total": float(projected_total),
        "over_probability": float(p_over),
        "under_probability": float(p_under),
        "push_probability": float(p_push),
        "model_lean": _lean(p_over, p_under, p_push),
        "total_uncertainty_90": {
            "low": float(interval_low),
            "high": float(interval_high),
        },
        "components": components,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    })
    return out


def clear_pace_engine_cache() -> None:
    try:
        _load_pace_division.clear()
    except Exception:
        pass


__all__ = [
    "ANALYSIS_LINE_PACE_WEIGHT",
    "CLOCK_IMPLIED_PLAYS_WEIGHT",
    "FROZEN_RAW_MODEL",
    "FROZEN_STEP3_ENGINE",
    "HISTORICAL_PLAYS_WEIGHT",
    "MAX_TOTAL_PACE_ADJUSTMENT",
    "MIN_PACE_COVERAGE",
    "MODEL_VERSION",
    "PACE_FULL_SIGNAL_RATIO",
    "SAMPLE_GAMES_FULL_WEIGHT",
    "_avg_top_seconds",
    "_clock_seconds",
    "_discover_time_of_possession",
    "_games_and_plays",
    "_header_index",
    "_load_pace_division",
    "_pace_label",
    "_team_pace",
    "apply_to_raw",
    "build_pace_engine",
    "clear_pace_engine_cache",
]
