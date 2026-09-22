"""CFB Over/Under Intelligence V2 — Upgrade Step 5 explosive-play engine.

Additive model layer above permanently frozen Upgrade Step 4.

Certified evidence
------------------
NCAA team tables do not currently expose stable true 20+ yard pass-play or
10+ yard run-play rates in the certified selector. Step 5 therefore does NOT
invent those rates. Instead it builds a transparent explosive-efficiency proxy
from first-party NCAA per-attempt/per-completion measures:

Passing:
- offense yards per pass attempt,
- offense yards per completion,
- opponent yards allowed per pass attempt,
- opponent yards allowed per completion.

Rushing:
- offense yards per rush,
- opponent yards allowed per rush.

Each quantity is normalized to the correct FBS/FCS division baseline. Mixed
FBS/FCS games are allowed because the engine compares absolute efficiency
rates and normalizes each team to its own division; it never compares FBS and
FCS ranking numbers as if they shared one pool.

Projection policy
-----------------
- pass explosiveness proxy weight: 60%
- rush explosiveness proxy weight: 40%
- missing dimensions reduce coverage and contribute no invented signal,
- each side requires >=60% coverage,
- early-season samples are shrunk aggressively,
- per-team adjustment is capped at +/-1.75 points,
- frozen reliability and structural sigma are unchanged,
- the analysis total line has exactly 0% explosive/projection weight.

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
import cfb_over_under_pace_engine_v1 as step4
import cfb_team_data_v1 as frozen_team

MODEL_VERSION = "CFB O/U EXPLOSIVE ENGINE V1 • UPGRADE STEP 5"
FROZEN_STEP4_ENGINE = "cfb_over_under_pace_engine_v1"
FROZEN_RAW_MODEL = "cfb_over_under_model_v1"

NCAA_FBS_STATS_INDEX = frozen_team.NCAA_STATS_INDEX
NCAA_FCS_STATS_INDEX = step3.NCAA_FCS_STATS_INDEX

PASS_WEIGHT = 0.60
RUSH_WEIGHT = 0.40
MIN_SIDE_COVERAGE = 0.60
MAX_TEAM_EXPLOSIVE_ADJUSTMENT = 1.75
SAMPLE_GAMES_FULL_WEIGHT = 5.0
PASS_FULL_SIGNAL_RATIO = 0.14
RUSH_FULL_SIGNAL_RATIO = 0.16
ANALYSIS_LINE_EXPLOSIVE_WEIGHT = 0.0

_CATEGORY_LABELS = {
    "pass_offense": "team passing efficiency",
    "pass_defense": "team passing efficiency defense",
    "pass_yards_per_completion": "passing yards per completion",
    "rush_offense": "rushing offense",
    "rush_defense": "rushing defense",
}


def _clean(value: Any) -> str:
    return frozen_team._clean(value)


def _float(value: Any) -> float | None:
    return frozen_team._float(value)


def _int(value: Any) -> int | None:
    return frozen_team._int(value)


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _row_value(item: Mapping[str, Any], aliases: tuple[str, ...]) -> str:
    return step4._row_value(item, aliases)


def _safe_rate(numerator: Any, denominator: Any) -> float | None:
    num = _float(numerator)
    den = _float(denominator)
    if num is None or den is None or den <= 0:
        return None
    value = float(num) / float(den)
    if value <= 0:
        return None
    return value


def _games(item: Mapping[str, Any]) -> int | None:
    games = _int(_row_value(item, ("G", "Games", "GP")))
    return games if games is not None and games > 0 else None


def _pass_offense_metrics(
    row: Mapping[str, Any],
    ypc_row: Mapping[str, Any],
) -> dict[str, Any]:
    attempts = _float(_row_value(row, ("Pass Att", "Att", "Attempts")))
    completions = _float(_row_value(row, ("Pass Com", "Com", "Comp", "Completions")))
    yards = _float(_row_value(row, ("Pass Yds", "Yds", "Passing Yards")))

    ypa = _safe_rate(yards, attempts)
    ypc = _float(_row_value(ypc_row, ("Avg", "Yds/Comp", "Yds/Cmp")))
    if ypc is None:
        ypc = _safe_rate(yards, completions)

    return {
        "games": _games(row) or _games(ypc_row),
        "attempts": attempts,
        "completions": completions,
        "yards": yards,
        "yards_per_attempt": ypa,
        "yards_per_completion": ypc,
    }


def _pass_defense_metrics(row: Mapping[str, Any]) -> dict[str, Any]:
    attempts = _float(_row_value(row, ("Opp Pass", "Opp Att", "Pass Att")))
    completions = _float(_row_value(row, ("Opp Cpl", "Opp Com", "Opp Comp")))
    yards = _float(
        _row_value(
            row,
            (
                "Opp Pass Yds",
                "Opp Pass <br/>Yds",
                "Opp Passing Yards",
            ),
        )
    )

    return {
        "games": _games(row),
        "attempts": attempts,
        "completions": completions,
        "yards": yards,
        "yards_per_attempt_allowed": _safe_rate(yards, attempts),
        "yards_per_completion_allowed": _safe_rate(yards, completions),
    }


def _rush_metrics(row: Mapping[str, Any], defense: bool = False) -> dict[str, Any]:
    attempts_aliases = ("Opp Rush", "Rush Att", "Rush") if defense else ("Rush", "Rush Att")
    yards_aliases = ("Opp Rush Yds", "Rush Yds") if defense else ("Rush Yds",)
    attempts = _float(_row_value(row, attempts_aliases))
    yards = _float(_row_value(row, yards_aliases))
    per_rush = _float(_row_value(row, ("Yds/Rush", "Yards/Rush", "Avg")))
    if per_rush is None:
        per_rush = _safe_rate(yards, attempts)

    key = "yards_per_rush_allowed" if defense else "yards_per_rush"
    return {
        "games": _games(row),
        "attempts": attempts,
        "yards": yards,
        key: per_rush,
    }


def _discover_categories(html: str) -> dict[str, str]:
    parser = step3._CategoryOptionParser()
    parser.feed(html or "")
    out: dict[str, str] = {}
    for label, path in parser.options:
        normalized_path = _clean(path)
        if "/team/" not in normalized_path:
            continue
        lower = _clean(label).lower()
        for key, expected in _CATEGORY_LABELS.items():
            if key in out:
                continue
            if lower == expected:
                out[key] = urljoin(frozen_team.NCAA_ROOT, normalized_path)
    return out


def _median_metric(
    table: Mapping[str, Mapping[str, Any]],
    extractor,
    key: str,
) -> float | None:
    values: list[float] = []
    for row in table.values():
        metrics = extractor(row)
        value = _float(metrics.get(key))
        if value is not None and value > 0:
            values.append(float(value))
    return float(median(values)) if values else None


@st.cache_data(ttl=300, show_spinner=False)
def _load_explosive_division(
    division: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    division = _clean(division).upper()
    stats_index = NCAA_FCS_STATS_INDEX if division == "FCS" else NCAA_FBS_STATS_INDEX

    index_html, attempts = frozen_team._fetch_text_with_fallback(
        stats_index,
        f"NCAA {division} explosive category index",
    )
    categories = _discover_categories(index_html)

    tables: dict[str, dict[str, dict[str, Any]]] = {}
    table_diag: dict[str, Any] = {}
    for key, url in categories.items():
        table, diag = step3._load_category_table(
            url,
            f"NCAA {division} explosive {key}",
        )
        tables[key] = table
        table_diag[key] = diag
        attempts.extend(diag.get("attempts") or [])

    pass_off = tables.get("pass_offense") or {}
    pass_def = tables.get("pass_defense") or {}
    pass_ypc = tables.get("pass_yards_per_completion") or {}
    rush_off = tables.get("rush_offense") or {}
    rush_def = tables.get("rush_defense") or {}

    pass_ypa: list[float] = []
    pass_ypc_values: list[float] = []
    pass_ypa_allowed: list[float] = []
    pass_ypc_allowed: list[float] = []
    rush_ypr: list[float] = []
    rush_ypr_allowed: list[float] = []

    for key, row in pass_off.items():
        metrics = _pass_offense_metrics(row, pass_ypc.get(key) or {})
        if _float(metrics.get("yards_per_attempt")) is not None:
            pass_ypa.append(float(metrics["yards_per_attempt"]))
        if _float(metrics.get("yards_per_completion")) is not None:
            pass_ypc_values.append(float(metrics["yards_per_completion"]))

    for row in pass_def.values():
        metrics = _pass_defense_metrics(row)
        if _float(metrics.get("yards_per_attempt_allowed")) is not None:
            pass_ypa_allowed.append(float(metrics["yards_per_attempt_allowed"]))
        if _float(metrics.get("yards_per_completion_allowed")) is not None:
            pass_ypc_allowed.append(float(metrics["yards_per_completion_allowed"]))

    for row in rush_off.values():
        metrics = _rush_metrics(row, False)
        if _float(metrics.get("yards_per_rush")) is not None:
            rush_ypr.append(float(metrics["yards_per_rush"]))

    for row in rush_def.values():
        metrics = _rush_metrics(row, True)
        if _float(metrics.get("yards_per_rush_allowed")) is not None:
            rush_ypr_allowed.append(float(metrics["yards_per_rush_allowed"]))

    baselines = {
        "pass_ypa": float(median(pass_ypa)) if pass_ypa else None,
        "pass_ypc": float(median(pass_ypc_values)) if pass_ypc_values else None,
        "pass_ypa_allowed": (
            float(median(pass_ypa_allowed)) if pass_ypa_allowed else None
        ),
        "pass_ypc_allowed": (
            float(median(pass_ypc_allowed)) if pass_ypc_allowed else None
        ),
        "rush_ypr": float(median(rush_ypr)) if rush_ypr else None,
        "rush_ypr_allowed": (
            float(median(rush_ypr_allowed)) if rush_ypr_allowed else None
        ),
    }

    return {
        "division": division,
        "tables": tables,
        "baselines": baselines,
    }, {
        "division": division,
        "categories": categories,
        "table_rows": {key: len(value) for key, value in tables.items()},
        "table_diagnostics": table_diag,
        "baselines": baselines,
        "attempts": attempts,
    }


def _ratio_signal(value: Any, baseline: Any, full_ratio: float) -> float | None:
    value_f = _float(value)
    baseline_f = _float(baseline)
    if value_f is None or baseline_f is None or value_f <= 0 or baseline_f <= 0:
        return None
    return _clamp(
        ((float(value_f) / float(baseline_f)) - 1.0) / float(full_ratio),
        -1.0,
        1.0,
    )


def _pass_dimension(
    offense: Mapping[str, Any],
    defense: Mapping[str, Any],
    offense_baseline: Mapping[str, Any],
    defense_baseline: Mapping[str, Any],
) -> dict[str, Any]:
    off_ypa = _float(offense.get("yards_per_attempt"))
    off_ypc = _float(offense.get("yards_per_completion"))
    def_ypa = _float(defense.get("yards_per_attempt_allowed"))
    def_ypc = _float(defense.get("yards_per_completion_allowed"))

    ypa_off_signal = _ratio_signal(
        off_ypa,
        offense_baseline.get("pass_ypa"),
        PASS_FULL_SIGNAL_RATIO,
    )
    ypa_def_signal = _ratio_signal(
        def_ypa,
        defense_baseline.get("pass_ypa_allowed"),
        PASS_FULL_SIGNAL_RATIO,
    )
    ypc_off_signal = _ratio_signal(
        off_ypc,
        offense_baseline.get("pass_ypc"),
        PASS_FULL_SIGNAL_RATIO,
    )
    ypc_def_signal = _ratio_signal(
        def_ypc,
        defense_baseline.get("pass_ypc_allowed"),
        PASS_FULL_SIGNAL_RATIO,
    )

    ready = all(
        value is not None
        for value in (
            ypa_off_signal,
            ypa_def_signal,
            ypc_off_signal,
            ypc_def_signal,
        )
    )
    signal = 0.0
    if ready:
        ypa_matchup = (float(ypa_off_signal) + float(ypa_def_signal)) / 2.0
        ypc_matchup = (float(ypc_off_signal) + float(ypc_def_signal)) / 2.0
        signal = _clamp(0.60 * ypa_matchup + 0.40 * ypc_matchup, -1.0, 1.0)

    return {
        "ready": bool(ready),
        "weight": PASS_WEIGHT,
        "signal": float(signal),
        "offense_yards_per_attempt": off_ypa,
        "defense_yards_per_attempt_allowed": def_ypa,
        "offense_yards_per_completion": off_ypc,
        "defense_yards_per_completion_allowed": def_ypc,
    }


def _rush_dimension(
    offense: Mapping[str, Any],
    defense: Mapping[str, Any],
    offense_baseline: Mapping[str, Any],
    defense_baseline: Mapping[str, Any],
) -> dict[str, Any]:
    off_ypr = _float(offense.get("yards_per_rush"))
    def_ypr = _float(defense.get("yards_per_rush_allowed"))

    off_signal = _ratio_signal(
        off_ypr,
        offense_baseline.get("rush_ypr"),
        RUSH_FULL_SIGNAL_RATIO,
    )
    def_signal = _ratio_signal(
        def_ypr,
        defense_baseline.get("rush_ypr_allowed"),
        RUSH_FULL_SIGNAL_RATIO,
    )
    ready = off_signal is not None and def_signal is not None
    signal = (
        _clamp((float(off_signal) + float(def_signal)) / 2.0, -1.0, 1.0)
        if ready
        else 0.0
    )

    return {
        "ready": bool(ready),
        "weight": RUSH_WEIGHT,
        "signal": float(signal),
        "offense_yards_per_rush": off_ypr,
        "defense_yards_per_rush_allowed": def_ypr,
    }


def _sample_factor(
    pass_offense: Mapping[str, Any],
    pass_defense: Mapping[str, Any],
    rush_offense: Mapping[str, Any],
    rush_defense: Mapping[str, Any],
) -> float:
    games = [
        _int(row.get("games"))
        for row in (pass_offense, pass_defense, rush_offense, rush_defense)
        if row
    ]
    known = [g for g in games if g is not None and g > 0]
    if not known:
        return 0.0
    return _clamp(min(known) / SAMPLE_GAMES_FULL_WEIGHT, 0.0, 1.0)


def _label(signal: float) -> str:
    if signal >= 0.32:
        return "STRONG EXPLOSIVE EDGE"
    if signal >= 0.10:
        return "EXPLOSIVE EDGE"
    if signal <= -0.32:
        return "STRONG EXPLOSIVE SUPPRESSION"
    if signal <= -0.10:
        return "EXPLOSIVE SUPPRESSION"
    return "BALANCED"


def _side(
    offense_profile: Mapping[str, Any],
    defense_profile: Mapping[str, Any],
    offense_bundle: Mapping[str, Any],
    defense_bundle: Mapping[str, Any],
    offense_division: str,
    defense_division: str,
) -> dict[str, Any]:
    off_tables = offense_bundle.get("tables") or {}
    def_tables = defense_bundle.get("tables") or {}

    pass_off_row = step4._lookup(off_tables.get("pass_offense") or {}, offense_profile)
    pass_ypc_row = step4._lookup(
        off_tables.get("pass_yards_per_completion") or {},
        offense_profile,
    )
    pass_def_row = step4._lookup(def_tables.get("pass_defense") or {}, defense_profile)
    rush_off_row = step4._lookup(off_tables.get("rush_offense") or {}, offense_profile)
    rush_def_row = step4._lookup(def_tables.get("rush_defense") or {}, defense_profile)

    pass_off = _pass_offense_metrics(pass_off_row, pass_ypc_row)
    pass_def = _pass_defense_metrics(pass_def_row)
    rush_off = _rush_metrics(rush_off_row, False)
    rush_def = _rush_metrics(rush_def_row, True)

    pass_dim = _pass_dimension(
        pass_off,
        pass_def,
        offense_bundle.get("baselines") or {},
        defense_bundle.get("baselines") or {},
    )
    rush_dim = _rush_dimension(
        rush_off,
        rush_def,
        offense_bundle.get("baselines") or {},
        defense_bundle.get("baselines") or {},
    )

    coverage = sum(
        float(dim.get("weight") or 0.0)
        for dim in (pass_dim, rush_dim)
        if dim.get("ready")
    )
    weighted = sum(
        float(dim.get("weight") or 0.0) * float(dim.get("signal") or 0.0)
        for dim in (pass_dim, rush_dim)
        if dim.get("ready")
    )
    normalized_signal = (
        _clamp(weighted / coverage, -1.0, 1.0)
        if coverage > 0
        else 0.0
    )
    sample_factor = _sample_factor(pass_off, pass_def, rush_off, rush_def)
    model_ready = coverage >= MIN_SIDE_COVERAGE and sample_factor > 0

    adjustment = (
        _clamp(
            normalized_signal
            * MAX_TEAM_EXPLOSIVE_ADJUSTMENT
            * float(coverage)
            * float(sample_factor),
            -MAX_TEAM_EXPLOSIVE_ADJUSTMENT,
            MAX_TEAM_EXPLOSIVE_ADJUSTMENT,
        )
        if model_ready
        else 0.0
    )

    return {
        "offense_team": _clean(offense_profile.get("team")) or "Offense",
        "defense_team": _clean(defense_profile.get("team")) or "Defense",
        "offense_division": offense_division,
        "defense_division": defense_division,
        "pass": pass_dim,
        "rush": rush_dim,
        "coverage": float(coverage),
        "sample_factor": float(sample_factor),
        "signal": float(normalized_signal),
        "label": _label(normalized_signal),
        "points_adjustment": float(adjustment),
        "model_ready": bool(model_ready),
    }


def build_explosive_engine(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
) -> dict[str, Any]:
    fbs_pace, fbs_pace_diag = step4._load_pace_division("FBS")
    fcs_pace, fcs_pace_diag = step4._load_pace_division("FCS")

    away_div, _ = step4._resolve_division(away, fbs_pace, fcs_pace)
    home_div, _ = step4._resolve_division(home, fbs_pace, fcs_pace)

    if not away_div or not home_div:
        return {
            "version": MODEL_VERSION,
            "ready": True,
            "model_ready": False,
            "reason": "NCAA FBS/FCS identity is unavailable for one or both teams",
            "away_offense": {},
            "home_offense": {},
            "coverage": 0.0,
            "analysis_line_explosive_weight": ANALYSIS_LINE_EXPLOSIVE_WEIGHT,
            "true_explosive_pass_rate_available": False,
            "true_explosive_run_rate_available": False,
            "sportsbook_input_used": False,
            "market_price_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "monte_carlo_used": False,
        }

    fbs, fbs_diag = _load_explosive_division("FBS")
    fcs, fcs_diag = _load_explosive_division("FCS")
    bundles = {"FBS": fbs, "FCS": fcs}

    away_side = _side(
        away,
        home,
        bundles[away_div],
        bundles[home_div],
        away_div,
        home_div,
    )
    home_side = _side(
        home,
        away,
        bundles[home_div],
        bundles[away_div],
        home_div,
        away_div,
    )

    coverage = (
        float(away_side.get("coverage") or 0.0)
        + float(home_side.get("coverage") or 0.0)
    ) / 2.0
    model_ready = bool(
        away_side.get("model_ready")
        and home_side.get("model_ready")
    )

    reason = ""
    if not model_ready:
        reason = (
            "one or both offenses lack the minimum verified NCAA explosive-efficiency "
            "proxy coverage"
        )

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "model_ready": model_ready,
        "reason": reason,
        "away_division": away_div,
        "home_division": home_div,
        "mixed_division": away_div != home_div,
        "away_offense": away_side,
        "home_offense": home_side,
        "coverage": float(coverage),
        "analysis_line_explosive_weight": ANALYSIS_LINE_EXPLOSIVE_WEIGHT,
        "max_team_adjustment": MAX_TEAM_EXPLOSIVE_ADJUSTMENT,
        "true_explosive_pass_rate_available": False,
        "true_explosive_run_rate_available": False,
        "true_explosive_rate_reason": (
            "certified NCAA team tables do not expose stable 20+ pass / 10+ rush "
            "play-rate fields; Step 5 uses transparent per-attempt/per-completion "
            "explosive-efficiency proxies instead"
        ),
        "diagnostics": {
            "FBS": fbs_diag,
            "FCS": fcs_diag,
            "pace_identity_FBS": fbs_pace_diag,
            "pace_identity_FCS": fcs_pace_diag,
        },
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
    engine: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply bounded Step-5 explosive proxy adjustments to Step-4 raw output."""
    out = dict(base_raw)
    out["base_step4_model_version"] = _clean(base_raw.get("version"))
    out["version"] = MODEL_VERSION
    out["upgrade_step5_explosive_ready"] = bool(engine.get("model_ready"))
    out["upgrade_step5_applied"] = False
    out["explosive_engine_coverage"] = float(engine.get("coverage") or 0.0)
    out["analysis_line_explosive_weight"] = ANALYSIS_LINE_EXPLOSIVE_WEIGHT

    if not base_raw.get("ready") or not engine.get("model_ready"):
        out["explosive_engine_reason"] = _clean(
            engine.get("reason")
            or "explosive proxy evidence below Step-5 minimum coverage"
        )
        return out

    away_adjustment = float(
        (engine.get("away_offense") or {}).get("points_adjustment") or 0.0
    )
    home_adjustment = float(
        (engine.get("home_offense") or {}).get("points_adjustment") or 0.0
    )

    base_away = float(base_raw.get("projected_away_points") or 0.0)
    base_home = float(base_raw.get("projected_home_points") or 0.0)

    projected_away = frozen_raw._clamp(
        base_away + away_adjustment,
        frozen_raw.MIN_TEAM_POINTS,
        frozen_raw.MAX_TEAM_POINTS,
    )
    projected_home = frozen_raw._clamp(
        base_home + home_adjustment,
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
        "step5_away_explosive_adjustment": float(away_adjustment),
        "step5_home_explosive_adjustment": float(home_adjustment),
        "step5_total_explosive_adjustment": float(
            projected_total - (base_away + base_home)
        ),
        "step5_explosive_coverage": float(engine.get("coverage") or 0.0),
    })

    out.update({
        "upgrade_step5_applied": True,
        "step5_base_projected_away_points": float(base_away),
        "step5_base_projected_home_points": float(base_home),
        "step5_base_projected_total": float(base_away + base_home),
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


def clear_explosive_engine_cache() -> None:
    try:
        _load_explosive_division.clear()
    except Exception:
        pass


__all__ = [
    "ANALYSIS_LINE_EXPLOSIVE_WEIGHT",
    "FROZEN_RAW_MODEL",
    "FROZEN_STEP4_ENGINE",
    "MAX_TEAM_EXPLOSIVE_ADJUSTMENT",
    "MIN_SIDE_COVERAGE",
    "MODEL_VERSION",
    "PASS_WEIGHT",
    "RUSH_WEIGHT",
    "_discover_categories",
    "_load_explosive_division",
    "_pass_defense_metrics",
    "_pass_offense_metrics",
    "_ratio_signal",
    "_rush_metrics",
    "_side",
    "apply_to_raw",
    "build_explosive_engine",
    "clear_explosive_engine_cache",
]
