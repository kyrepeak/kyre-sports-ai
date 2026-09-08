"""CFB Over/Under Intelligence V2 — Upgrade Step 6 red-zone engine.

Additive model layer above permanently frozen Upgrade Step 5.

Certified evidence
------------------
First-party NCAA Red Zone Offense and Red Zone Defense tables expose direct
trip counts and outcomes:
- red-zone attempts,
- rushing touchdowns,
- passing touchdowns,
- field goals made,
- total red-zone scores,
- scoring percentage.

Step 6 deliberately parses every NCAA table row, including tied ranks whose
rank cell may be blank. This fixes a limitation of the older rank-oriented
parser and lets the red-zone engine use direct rates instead of ranking
proxies.

Projection policy
-----------------
- touchdown conversion rate is the primary red-zone quantity (65%),
- estimated points per red-zone trip is secondary (35%),
- offense rates are normalized to that offense's FBS/FCS baseline,
- opponent allowed rates are normalized to that defense's FBS/FCS baseline,
- mixed FBS/FCS games are allowed because absolute rates are normalized inside
  each team's own division; cross-division ranks are never compared,
- sample shrinkage is based on the smaller verified red-zone attempt count,
- both direct offense and direct defense rows are required for a side,
- per-team adjustment is capped at +/-1.50 points,
- frozen reliability and structural sigma are unchanged,
- the analysis total line has exactly 0% red-zone/projection weight.

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

MODEL_VERSION = "CFB O/U RED ZONE ENGINE V1 • UPGRADE STEP 6"
FROZEN_STEP5_ENGINE = "cfb_over_under_explosive_engine_v1"
FROZEN_RAW_MODEL = "cfb_over_under_model_v1"

NCAA_FBS_STATS_INDEX = frozen_team.NCAA_STATS_INDEX
NCAA_FCS_STATS_INDEX = step3.NCAA_FCS_STATS_INDEX

TD_RATE_WEIGHT = 0.65
POINTS_PER_TRIP_WEIGHT = 0.35
MIN_SIDE_COVERAGE = 1.00
MAX_TEAM_RED_ZONE_ADJUSTMENT = 1.50
FULL_SAMPLE_RED_ZONE_ATTEMPTS = 12.0
TD_FULL_SIGNAL_RATIO = 0.18
PPT_FULL_SIGNAL_RATIO = 0.16
ANALYSIS_LINE_RED_ZONE_WEIGHT = 0.0

_CATEGORY_LABELS = {
    "red_zone_offense": "red zone offense",
    "red_zone_defense": "red zone defense",
}


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


def _row_value(item: Mapping[str, Any], aliases: tuple[str, ...]) -> str:
    headers = list(item.get("headers") or [])
    row = list(item.get("row") or [])
    normalized = [_norm_header(h) for h in headers]
    wanted = {_norm_header(a) for a in aliases}
    for idx, header in enumerate(normalized):
        if header in wanted and idx < len(row):
            return _clean(row[idx])
    for idx, header in enumerate(normalized):
        if any(alias and alias in header for alias in wanted) and idx < len(row):
            return _clean(row[idx])
    return ""


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
            if key not in out and lower == expected:
                out[key] = urljoin(frozen_team.NCAA_ROOT, normalized_path)
    return out


def _red_zone_rows(html: str) -> dict[str, dict[str, Any]]:
    """Parse all NCAA red-zone rows, including tied rows with blank Rank."""
    headers, rows = frozen_team._table_rows(html or "")
    if not rows:
        return {}
    team_idx = frozen_team._team_cell_index(headers, rows)
    out: dict[str, dict[str, Any]] = {}
    for cells in rows:
        if team_idx >= len(cells):
            continue
        team = _clean(cells[team_idx])
        key = frozen_team._canonical_name(team)
        if not key:
            continue
        out[key] = {
            "team": team,
            "headers": list(headers),
            "row": list(cells),
        }
    return out


@st.cache_data(ttl=300, show_spinner=False)
def _load_red_zone_table(
    url: str,
    provider: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    first, first_attempts = frozen_team._fetch_text_with_fallback(url, provider)
    attempts.extend(first_attempts)
    if not first:
        return {}, {"rows": 0, "pages": 0, "attempts": attempts}

    found = _red_zone_rows(first)
    max_pages = frozen_team._max_stat_pages(first)
    for page in range(2, max_pages + 1):
        page_url = url.rstrip("/") + f"/p{page}"
        html, page_attempts = frozen_team._fetch_text_with_fallback(
            page_url,
            f"{provider} p{page}",
        )
        attempts.extend(page_attempts)
        if html:
            found.update(_red_zone_rows(html))

    return found, {
        "rows": len(found),
        "pages": max_pages,
        "attempts": attempts,
    }


def _metrics(row: Mapping[str, Any], defense: bool = False) -> dict[str, Any]:
    if not row:
        return {}

    games = _int(_row_value(row, ("G", "Games", "GP")))
    attempts_alias = ("Opp RZAtt", "Opp RZ Att") if defense else ("RZAtt", "RZ Att")
    rush_td_alias = (
        ("Opp RZ Rush TD", "Opp RZ Rush TDs")
        if defense
        else ("RZ Rush TD", "RZ Rush TDs")
    )
    pass_td_alias = (
        ("Opp RZ Pass TD", "Opp RZ Pass TDs")
        if defense
        else ("RZ Pass TD", "RZ Pass TDs")
    )
    fg_alias = (
        ("Opp RZ FG Made", "Opp RZ FGM")
        if defense
        else ("RZ FG Made", "RZ FGM")
    )
    scores_alias = (
        ("Opp RZScores", "Opp RZ Scores")
        if defense
        else ("RZScores", "RZ Scores")
    )

    rz_attempts = _float(_row_value(row, attempts_alias))
    rush_td = _float(_row_value(row, rush_td_alias)) or 0.0
    pass_td = _float(_row_value(row, pass_td_alias)) or 0.0
    fg_made = _float(_row_value(row, fg_alias)) or 0.0
    scores = _float(_row_value(row, scores_alias))
    touchdowns = float(rush_td + pass_td)

    if rz_attempts is None or rz_attempts <= 0:
        return {
            "team": _clean(row.get("team")),
            "games": games,
            "attempts": rz_attempts,
            "ready": False,
        }

    score_count = float(scores) if scores is not None else touchdowns + float(fg_made)
    td_rate = touchdowns / float(rz_attempts)
    score_rate = score_count / float(rz_attempts)
    points_per_trip = (7.0 * touchdowns + 3.0 * float(fg_made)) / float(rz_attempts)
    attempts_per_game = (
        float(rz_attempts) / float(games)
        if games is not None and games > 0
        else None
    )

    return {
        "team": _clean(row.get("team")),
        "games": games,
        "attempts": float(rz_attempts),
        "rush_touchdowns": float(rush_td),
        "pass_touchdowns": float(pass_td),
        "touchdowns": float(touchdowns),
        "field_goals_made": float(fg_made),
        "scores": float(score_count),
        "touchdown_rate": float(td_rate),
        "scoring_rate": float(score_rate),
        "points_per_trip": float(points_per_trip),
        "attempts_per_game": attempts_per_game,
        "ready": True,
    }


def _median_positive(values: list[float]) -> float | None:
    good = [float(v) for v in values if v is not None and v > 0]
    return float(median(good)) if good else None


@st.cache_data(ttl=300, show_spinner=False)
def _load_red_zone_division(
    division: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    division = _clean(division).upper()
    stats_index = NCAA_FCS_STATS_INDEX if division == "FCS" else NCAA_FBS_STATS_INDEX

    index_html, attempts = frozen_team._fetch_text_with_fallback(
        stats_index,
        f"NCAA {division} red-zone category index",
    )
    categories = _discover_categories(index_html)

    tables: dict[str, dict[str, dict[str, Any]]] = {}
    table_diag: dict[str, Any] = {}
    for key, url in categories.items():
        table, diag = _load_red_zone_table(
            url,
            f"NCAA {division} {key}",
        )
        tables[key] = table
        table_diag[key] = diag
        attempts.extend(diag.get("attempts") or [])

    offense_metrics = [
        _metrics(row, False)
        for row in (tables.get("red_zone_offense") or {}).values()
    ]
    defense_metrics = [
        _metrics(row, True)
        for row in (tables.get("red_zone_defense") or {}).values()
    ]

    baselines = {
        "offense_touchdown_rate": _median_positive(
            [m.get("touchdown_rate") for m in offense_metrics if m.get("ready")]
        ),
        "offense_points_per_trip": _median_positive(
            [m.get("points_per_trip") for m in offense_metrics if m.get("ready")]
        ),
        "defense_touchdown_rate_allowed": _median_positive(
            [m.get("touchdown_rate") for m in defense_metrics if m.get("ready")]
        ),
        "defense_points_per_trip_allowed": _median_positive(
            [m.get("points_per_trip") for m in defense_metrics if m.get("ready")]
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
    if value_f is None or baseline_f is None or value_f < 0 or baseline_f <= 0:
        return None
    return _clamp(
        ((float(value_f) / float(baseline_f)) - 1.0) / float(full_ratio),
        -1.0,
        1.0,
    )


def _sample_factor(offense: Mapping[str, Any], defense: Mapping[str, Any]) -> float:
    off_attempts = _float(offense.get("attempts")) or 0.0
    def_attempts = _float(defense.get("attempts")) or 0.0
    if off_attempts <= 0 or def_attempts <= 0:
        return 0.0
    return _clamp(
        min(off_attempts, def_attempts) / FULL_SAMPLE_RED_ZONE_ATTEMPTS,
        0.0,
        1.0,
    )


def _label(signal: float) -> str:
    if signal >= 0.35:
        return "STRONG RED-ZONE EDGE"
    if signal >= 0.12:
        return "RED-ZONE EDGE"
    if signal <= -0.35:
        return "STRONG RED-ZONE SUPPRESSION"
    if signal <= -0.12:
        return "RED-ZONE SUPPRESSION"
    return "BALANCED"


def _side(
    offense_profile: Mapping[str, Any],
    defense_profile: Mapping[str, Any],
    offense_bundle: Mapping[str, Any],
    defense_bundle: Mapping[str, Any],
    offense_division: str,
    defense_division: str,
) -> dict[str, Any]:
    off_row = step4._lookup(
        (offense_bundle.get("tables") or {}).get("red_zone_offense") or {},
        offense_profile,
    )
    def_row = step4._lookup(
        (defense_bundle.get("tables") or {}).get("red_zone_defense") or {},
        defense_profile,
    )

    offense = _metrics(off_row, False)
    defense = _metrics(def_row, True)
    offense_ready = bool(offense.get("ready"))
    defense_ready = bool(defense.get("ready"))
    coverage = 0.5 * float(offense_ready) + 0.5 * float(defense_ready)

    off_base = offense_bundle.get("baselines") or {}
    def_base = defense_bundle.get("baselines") or {}

    off_td_signal = _ratio_signal(
        offense.get("touchdown_rate"),
        off_base.get("offense_touchdown_rate"),
        TD_FULL_SIGNAL_RATIO,
    )
    def_td_signal = _ratio_signal(
        defense.get("touchdown_rate"),
        def_base.get("defense_touchdown_rate_allowed"),
        TD_FULL_SIGNAL_RATIO,
    )
    off_ppt_signal = _ratio_signal(
        offense.get("points_per_trip"),
        off_base.get("offense_points_per_trip"),
        PPT_FULL_SIGNAL_RATIO,
    )
    def_ppt_signal = _ratio_signal(
        defense.get("points_per_trip"),
        def_base.get("defense_points_per_trip_allowed"),
        PPT_FULL_SIGNAL_RATIO,
    )

    td_ready = off_td_signal is not None and def_td_signal is not None
    ppt_ready = off_ppt_signal is not None and def_ppt_signal is not None
    model_ready = (
        offense_ready
        and defense_ready
        and td_ready
        and ppt_ready
        and coverage >= MIN_SIDE_COVERAGE
    )

    td_signal = (
        _clamp((float(off_td_signal) + float(def_td_signal)) / 2.0, -1.0, 1.0)
        if td_ready
        else 0.0
    )
    ppt_signal = (
        _clamp((float(off_ppt_signal) + float(def_ppt_signal)) / 2.0, -1.0, 1.0)
        if ppt_ready
        else 0.0
    )
    signal = _clamp(
        TD_RATE_WEIGHT * td_signal + POINTS_PER_TRIP_WEIGHT * ppt_signal,
        -1.0,
        1.0,
    )
    sample_factor = _sample_factor(offense, defense)
    adjustment = (
        _clamp(
            signal * MAX_TEAM_RED_ZONE_ADJUSTMENT * sample_factor,
            -MAX_TEAM_RED_ZONE_ADJUSTMENT,
            MAX_TEAM_RED_ZONE_ADJUSTMENT,
        )
        if model_ready and sample_factor > 0
        else 0.0
    )

    reason = ""
    if not model_ready:
        if not offense_ready and not defense_ready:
            reason = "direct NCAA red-zone offense and defense rows are unavailable"
        elif not offense_ready:
            reason = "direct NCAA red-zone offense row is unavailable"
        elif not defense_ready:
            reason = "direct NCAA red-zone defense row is unavailable"
        else:
            reason = "verified red-zone rate baseline is unavailable"

    return {
        "offense_team": _clean(offense_profile.get("team")) or "Offense",
        "defense_team": _clean(defense_profile.get("team")) or "Defense",
        "offense_division": offense_division,
        "defense_division": defense_division,
        "offense": offense,
        "defense": defense,
        "coverage": float(coverage),
        "sample_factor": float(sample_factor),
        "touchdown_signal": float(td_signal),
        "points_per_trip_signal": float(ppt_signal),
        "signal": float(signal),
        "label": _label(signal),
        "points_adjustment": float(adjustment),
        "model_ready": bool(model_ready and sample_factor > 0),
        "reason": reason,
    }


def build_red_zone_engine(
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
            "analysis_line_red_zone_weight": ANALYSIS_LINE_RED_ZONE_WEIGHT,
            "sportsbook_input_used": False,
            "market_price_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "monte_carlo_used": False,
        }

    fbs, fbs_diag = _load_red_zone_division("FBS")
    fcs, fcs_diag = _load_red_zone_division("FCS")
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
        reasons = [
            text
            for text in (
                _clean(away_side.get("reason")),
                _clean(home_side.get("reason")),
            )
            if text
        ]
        reason = "; ".join(dict.fromkeys(reasons)) or (
            "one or both offenses lack complete verified NCAA red-zone evidence"
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
        "analysis_line_red_zone_weight": ANALYSIS_LINE_RED_ZONE_WEIGHT,
        "max_team_adjustment": MAX_TEAM_RED_ZONE_ADJUSTMENT,
        "rankless_tie_safe_parser_active": True,
        "cross_division_rank_comparison_used": False,
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
    """Apply bounded Step-6 red-zone adjustments to Step-5 raw output."""
    out = dict(base_raw)
    out["base_step5_model_version"] = _clean(base_raw.get("version"))
    out["version"] = MODEL_VERSION
    out["upgrade_step6_red_zone_ready"] = bool(engine.get("model_ready"))
    out["upgrade_step6_applied"] = False
    out["red_zone_engine_coverage"] = float(engine.get("coverage") or 0.0)
    out["analysis_line_red_zone_weight"] = ANALYSIS_LINE_RED_ZONE_WEIGHT

    if not base_raw.get("ready") or not engine.get("model_ready"):
        out["red_zone_engine_reason"] = _clean(
            engine.get("reason")
            or "red-zone evidence below Step-6 minimum coverage"
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
        "step6_away_red_zone_adjustment": float(away_adjustment),
        "step6_home_red_zone_adjustment": float(home_adjustment),
        "step6_total_red_zone_adjustment": float(
            projected_total - (base_away + base_home)
        ),
        "step6_red_zone_coverage": float(engine.get("coverage") or 0.0),
    })

    out.update({
        "upgrade_step6_applied": True,
        "step6_base_projected_away_points": float(base_away),
        "step6_base_projected_home_points": float(base_home),
        "step6_base_projected_total": float(base_away + base_home),
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


def clear_red_zone_engine_cache() -> None:
    for fn in (_load_red_zone_table, _load_red_zone_division):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "ANALYSIS_LINE_RED_ZONE_WEIGHT",
    "FROZEN_RAW_MODEL",
    "FROZEN_STEP5_ENGINE",
    "MAX_TEAM_RED_ZONE_ADJUSTMENT",
    "MIN_SIDE_COVERAGE",
    "MODEL_VERSION",
    "POINTS_PER_TRIP_WEIGHT",
    "TD_RATE_WEIGHT",
    "_discover_categories",
    "_load_red_zone_division",
    "_load_red_zone_table",
    "_metrics",
    "_red_zone_rows",
    "_side",
    "apply_to_raw",
    "build_red_zone_engine",
    "clear_red_zone_engine_cache",
]
