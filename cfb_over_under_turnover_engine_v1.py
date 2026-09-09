"""CFB Over/Under Intelligence V2 — Upgrade Step 8 turnover-possession volatility engine.

Additive model layer above permanently frozen Upgrade Step 7.

Certified evidence
------------------
First-party NCAA Turnover Margin tables expose complete direct counts for both
sides of possession volatility:
- fumbles recovered,
- opponent interceptions,
- total turnovers gained,
- fumbles lost,
- interceptions thrown,
- total turnovers lost,
- turnover margin.

Unlike NCAA's separate "Turnovers Gained" table, the Turnover Margin table
retains teams with zero takeaways, so Step 8 uses that complete table and parses
every row including blank/tied Rank cells.

Projection policy
-----------------
Turnovers have an ambiguous directional effect on a game total without verified
field-position / return information: they kill one offense's drive but can also
create a short field for the opponent. Step 8 therefore does NOT fabricate a
mean points adjustment.

Instead, verified giveaway-vs-takeaway pressure is used to adjust structural
TOTAL UNCERTAINTY only:
- offense giveaways/game and opponent takeaways/game are blended 50/50,
- each side is normalized to its own FBS/FCS baseline,
- mixed FBS/FCS games are allowed without cross-division rank comparison,
- early samples are shrunk by verified completed games,
- total sigma adjustment is capped at +/-1.25 points,
- projected team points and projected total remain exactly Step 7,
- analysis-line turnover/projection weight remains exactly 0%.

No sportsbook feed, market-implied probability, EV, price, field-position
fabrication, or Monte Carlo is introduced here.
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

MODEL_VERSION = "CFB O/U TURNOVER VOLATILITY ENGINE V1 • UPGRADE STEP 8"
FROZEN_STEP7_ENGINE = "cfb_over_under_third_down_engine_v1"
FROZEN_RAW_MODEL = "cfb_over_under_model_v1"

NCAA_FBS_STATS_INDEX = frozen_team.NCAA_STATS_INDEX
NCAA_FCS_STATS_INDEX = step3.NCAA_FCS_STATS_INDEX

OFFENSE_GIVEAWAY_WEIGHT = 0.50
DEFENSE_TAKEAWAY_WEIGHT = 0.50
MIN_SIDE_COVERAGE = 1.00
FULL_SAMPLE_GAMES = 6.0
FULL_SIGNAL_TURNOVERS_PER_GAME = 1.00
MAX_TOTAL_SIGMA_ADJUSTMENT = 1.25
ANALYSIS_LINE_TURNOVER_WEIGHT = 0.0
PROJECTED_TOTAL_TURNOVER_WEIGHT = 0.0

_CATEGORY_LABEL = "turnover margin"


def _clean(value: Any) -> str:
    return frozen_team._clean(value)


def _float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return frozen_team._float(value)


def _int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    number = _float(value)
    if number is None:
        return None
    return int(number)


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


def _discover_category(html: str) -> str:
    parser = step3._CategoryOptionParser()
    parser.feed(html or "")
    for label, path in parser.options:
        normalized_path = _clean(path)
        if "/team/" not in normalized_path:
            continue
        if _clean(label).lower() == _CATEGORY_LABEL:
            return urljoin(frozen_team.NCAA_ROOT, normalized_path)
    return ""


def _turnover_rows(html: str) -> dict[str, dict[str, Any]]:
    """Parse all NCAA turnover-margin rows, including tied blank Rank rows."""
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
def _load_turnover_table(
    url: str,
    provider: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    first, first_attempts = frozen_team._fetch_text_with_fallback(url, provider)
    attempts.extend(first_attempts)
    if not first:
        return {}, {"rows": 0, "pages": 0, "attempts": attempts}

    found = _turnover_rows(first)
    max_pages = frozen_team._max_stat_pages(first)
    for page in range(2, max_pages + 1):
        page_url = url.rstrip("/") + f"/p{page}"
        html, page_attempts = frozen_team._fetch_text_with_fallback(
            page_url,
            f"{provider} p{page}",
        )
        attempts.extend(page_attempts)
        if html:
            found.update(_turnover_rows(html))

    return found, {
        "rows": len(found),
        "pages": max_pages,
        "attempts": attempts,
    }


def _metrics(row: Mapping[str, Any]) -> dict[str, Any]:
    if not row:
        return {}

    games = _int(_row_value(row, ("G", "Games", "GP")))
    gained = _float(_row_value(row, ("Turn Gain", "Turnovers Gained")))
    lost = _float(_row_value(row, ("Turn Lost", "Turnovers Lost")))
    fum_rec = _float(_row_value(row, ("Fum Rec", "Fumbles Recovered")))
    opp_int = _float(_row_value(row, ("Opp Int", "Opponent Interceptions")))
    fum_lost = _float(_row_value(row, ("Fum Lost", "Fumbles Lost")))
    interceptions = _float(_row_value(row, ("Int", "Interceptions")))
    margin = _float(_row_value(row, ("Margin", "Turnover Margin")))

    if games is None or games <= 0 or gained is None or gained < 0 or lost is None or lost < 0:
        return {
            "team": _clean(row.get("team")),
            "games": games,
            "turnovers_gained": gained,
            "turnovers_lost": lost,
            "ready": False,
        }

    return {
        "team": _clean(row.get("team")),
        "games": int(games),
        "fumbles_recovered": float(fum_rec or 0.0),
        "opponent_interceptions": float(opp_int or 0.0),
        "turnovers_gained": float(gained),
        "fumbles_lost": float(fum_lost or 0.0),
        "interceptions_thrown": float(interceptions or 0.0),
        "turnovers_lost": float(lost),
        "turnover_margin": float(margin if margin is not None else gained - lost),
        "takeaways_per_game": float(gained) / float(games),
        "giveaways_per_game": float(lost) / float(games),
        "margin_per_game": float((margin if margin is not None else gained - lost)) / float(games),
        "ready": True,
    }


def _median_known(values: list[float]) -> float | None:
    good = [float(v) for v in values if v is not None and v >= 0]
    return float(median(good)) if good else None


@st.cache_data(ttl=300, show_spinner=False)
def _load_turnover_division(
    division: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    division = _clean(division).upper()
    stats_index = NCAA_FCS_STATS_INDEX if division == "FCS" else NCAA_FBS_STATS_INDEX

    index_html, attempts = frozen_team._fetch_text_with_fallback(
        stats_index,
        f"NCAA {division} turnover category index",
    )
    url = _discover_category(index_html)
    table: dict[str, dict[str, Any]] = {}
    table_diag: dict[str, Any] = {}
    if url:
        table, table_diag = _load_turnover_table(
            url,
            f"NCAA {division} turnover margin",
        )
        attempts.extend(table_diag.get("attempts") or [])

    metrics = [_metrics(row) for row in table.values()]
    baselines = {
        "giveaways_per_game": _median_known(
            [m.get("giveaways_per_game") for m in metrics if m.get("ready")]
        ),
        "takeaways_per_game": _median_known(
            [m.get("takeaways_per_game") for m in metrics if m.get("ready")]
        ),
    }

    return {
        "division": division,
        "table": table,
        "baselines": baselines,
    }, {
        "division": division,
        "category_url": url,
        "table_rows": len(table),
        "table_diagnostics": table_diag,
        "baselines": baselines,
        "attempts": attempts,
    }


def _signal(value: Any, baseline: Any) -> float | None:
    value_f = _float(value)
    baseline_f = _float(baseline)
    if value_f is None or baseline_f is None or value_f < 0 or baseline_f < 0:
        return None
    return _clamp(
        (float(value_f) - float(baseline_f)) / FULL_SIGNAL_TURNOVERS_PER_GAME,
        -1.0,
        1.0,
    )


def _sample_factor(offense: Mapping[str, Any], defense: Mapping[str, Any]) -> float:
    off_games = _float(offense.get("games")) or 0.0
    def_games = _float(defense.get("games")) or 0.0
    if off_games <= 0 or def_games <= 0:
        return 0.0
    return _clamp(min(off_games, def_games) / FULL_SAMPLE_GAMES, 0.0, 1.0)


def _label(signal: float) -> str:
    if signal >= 0.35:
        return "HIGH TURNOVER VOLATILITY"
    if signal >= 0.12:
        return "ELEVATED TURNOVER VOLATILITY"
    if signal <= -0.35:
        return "LOW TURNOVER VOLATILITY"
    if signal <= -0.12:
        return "REDUCED TURNOVER VOLATILITY"
    return "NEUTRAL TURNOVER VOLATILITY"


def _side(
    offense_profile: Mapping[str, Any],
    defense_profile: Mapping[str, Any],
    offense_bundle: Mapping[str, Any],
    defense_bundle: Mapping[str, Any],
    offense_division: str,
    defense_division: str,
) -> dict[str, Any]:
    off_row = step4._lookup(offense_bundle.get("table") or {}, offense_profile)
    def_row = step4._lookup(defense_bundle.get("table") or {}, defense_profile)

    offense = _metrics(off_row)
    defense = _metrics(def_row)
    offense_ready = bool(offense.get("ready"))
    defense_ready = bool(defense.get("ready"))
    coverage = 0.5 * float(offense_ready) + 0.5 * float(defense_ready)

    off_base = offense_bundle.get("baselines") or {}
    def_base = defense_bundle.get("baselines") or {}

    off_signal = _signal(
        offense.get("giveaways_per_game"),
        off_base.get("giveaways_per_game"),
    )
    def_signal = _signal(
        defense.get("takeaways_per_game"),
        def_base.get("takeaways_per_game"),
    )
    signals_ready = off_signal is not None and def_signal is not None
    model_ready = (
        offense_ready
        and defense_ready
        and signals_ready
        and coverage >= MIN_SIDE_COVERAGE
    )

    blended_signal = (
        _clamp(
            OFFENSE_GIVEAWAY_WEIGHT * float(off_signal)
            + DEFENSE_TAKEAWAY_WEIGHT * float(def_signal),
            -1.0,
            1.0,
        )
        if signals_ready
        else 0.0
    )
    sample_factor = _sample_factor(offense, defense)
    shrunk_signal = float(blended_signal) * float(sample_factor)

    expected_giveaways = None
    if offense_ready and defense_ready:
        expected_giveaways = (
            float(offense.get("giveaways_per_game") or 0.0)
            + float(defense.get("takeaways_per_game") or 0.0)
        ) / 2.0

    baseline_expected = None
    if off_base.get("giveaways_per_game") is not None and def_base.get("takeaways_per_game") is not None:
        baseline_expected = (
            float(off_base.get("giveaways_per_game"))
            + float(def_base.get("takeaways_per_game"))
        ) / 2.0

    reason = ""
    if not model_ready:
        if not offense_ready and not defense_ready:
            reason = "direct NCAA turnover rows are unavailable for offense and defense"
        elif not offense_ready:
            reason = "direct NCAA turnover row is unavailable for the offense"
        elif not defense_ready:
            reason = "direct NCAA turnover row is unavailable for the opponent defense"
        else:
            reason = "verified turnover baseline is unavailable"

    return {
        "offense_team": _clean(offense_profile.get("team")) or "Offense",
        "defense_team": _clean(defense_profile.get("team")) or "Defense",
        "offense_division": offense_division,
        "defense_division": defense_division,
        "offense": offense,
        "defense": defense,
        "coverage": float(coverage),
        "sample_factor": float(sample_factor),
        "offense_giveaway_signal": float(off_signal) if off_signal is not None else 0.0,
        "defense_takeaway_signal": float(def_signal) if def_signal is not None else 0.0,
        "signal": float(blended_signal),
        "shrunk_signal": float(shrunk_signal),
        "expected_giveaways_per_game": expected_giveaways,
        "baseline_expected_giveaways_per_game": baseline_expected,
        "label": _label(shrunk_signal),
        "model_ready": bool(model_ready and sample_factor > 0),
        "reason": reason,
    }


def build_turnover_engine(
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
            "analysis_line_turnover_weight": ANALYSIS_LINE_TURNOVER_WEIGHT,
            "projected_total_turnover_weight": PROJECTED_TOTAL_TURNOVER_WEIGHT,
            "field_position_data_available": False,
            "field_position_points_adjustment_used": False,
            "sportsbook_input_used": False,
            "market_price_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "monte_carlo_used": False,
        }

    fbs, fbs_diag = _load_turnover_division("FBS")
    fcs, fcs_diag = _load_turnover_division("FCS")
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

    total_signal = (
        (
            float(away_side.get("shrunk_signal") or 0.0)
            + float(home_side.get("shrunk_signal") or 0.0)
        ) / 2.0
        if model_ready
        else 0.0
    )
    sigma_adjustment = (
        _clamp(
            total_signal * MAX_TOTAL_SIGMA_ADJUSTMENT,
            -MAX_TOTAL_SIGMA_ADJUSTMENT,
            MAX_TOTAL_SIGMA_ADJUSTMENT,
        )
        if model_ready
        else 0.0
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
            "one or both offenses lack complete verified NCAA turnover evidence"
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
        "total_volatility_signal": float(total_signal),
        "sigma_adjustment": float(sigma_adjustment),
        "max_total_sigma_adjustment": MAX_TOTAL_SIGMA_ADJUSTMENT,
        "analysis_line_turnover_weight": ANALYSIS_LINE_TURNOVER_WEIGHT,
        "projected_total_turnover_weight": PROJECTED_TOTAL_TURNOVER_WEIGHT,
        "rankless_tie_safe_parser_active": True,
        "cross_division_rank_comparison_used": False,
        "field_position_data_available": False,
        "field_position_points_adjustment_used": False,
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
    """Apply Step-8 turnover volatility to uncertainty, never to projected points."""
    out = dict(base_raw)
    out["base_step7_model_version"] = _clean(base_raw.get("version"))
    out["version"] = MODEL_VERSION
    out["upgrade_step8_turnover_ready"] = bool(engine.get("model_ready"))
    out["upgrade_step8_applied"] = False
    out["turnover_engine_coverage"] = float(engine.get("coverage") or 0.0)
    out["analysis_line_turnover_weight"] = ANALYSIS_LINE_TURNOVER_WEIGHT
    out["projected_total_turnover_weight"] = PROJECTED_TOTAL_TURNOVER_WEIGHT

    if not base_raw.get("ready") or not engine.get("model_ready"):
        out["turnover_engine_reason"] = _clean(
            engine.get("reason")
            or "turnover evidence below Step-8 minimum coverage"
        )
        return out

    base_away = float(base_raw.get("projected_away_points") or 0.0)
    base_home = float(base_raw.get("projected_home_points") or 0.0)
    base_total = float(base_raw.get("projected_total") or (base_away + base_home))
    base_sigma = float(
        base_raw.get("structural_total_sigma")
        or frozen_raw.BASE_TOTAL_SIGMA
    )
    sigma_adjustment = float(engine.get("sigma_adjustment") or 0.0)
    adjusted_sigma = max(1.0, base_sigma + sigma_adjustment)

    line = float(base_raw.get("analysis_line") or 0.0)
    p_over, p_under, p_push = frozen_raw._line_probabilities(
        base_total,
        adjusted_sigma,
        line,
    )
    interval_low = max(0.0, base_total - 1.645 * adjusted_sigma)
    interval_high = base_total + 1.645 * adjusted_sigma

    components = dict(base_raw.get("components") or {})
    components.update({
        "step8_turnover_sigma_adjustment": float(sigma_adjustment),
        "step8_turnover_volatility_signal": float(
            engine.get("total_volatility_signal") or 0.0
        ),
        "step8_turnover_coverage": float(engine.get("coverage") or 0.0),
        "step8_projected_total_adjustment": 0.0,
    })

    out.update({
        "upgrade_step8_applied": True,
        "step8_base_projected_away_points": float(base_away),
        "step8_base_projected_home_points": float(base_home),
        "step8_base_projected_total": float(base_total),
        "step8_base_structural_total_sigma": float(base_sigma),
        "projected_away_points": float(base_away),
        "projected_home_points": float(base_home),
        "projected_total": float(base_total),
        "structural_total_sigma": float(adjusted_sigma),
        "over_probability": float(p_over),
        "under_probability": float(p_under),
        "push_probability": float(p_push),
        "model_lean": _lean(p_over, p_under, p_push),
        "total_uncertainty_90": {
            "low": float(interval_low),
            "high": float(interval_high),
        },
        "components": components,
        "field_position_data_available": False,
        "field_position_points_adjustment_used": False,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    })
    return out


def clear_turnover_engine_cache() -> None:
    for fn in (_load_turnover_table, _load_turnover_division):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "ANALYSIS_LINE_TURNOVER_WEIGHT",
    "DEFENSE_TAKEAWAY_WEIGHT",
    "FROZEN_RAW_MODEL",
    "FROZEN_STEP7_ENGINE",
    "FULL_SAMPLE_GAMES",
    "MAX_TOTAL_SIGMA_ADJUSTMENT",
    "MIN_SIDE_COVERAGE",
    "MODEL_VERSION",
    "OFFENSE_GIVEAWAY_WEIGHT",
    "PROJECTED_TOTAL_TURNOVER_WEIGHT",
    "_discover_category",
    "_load_turnover_division",
    "_load_turnover_table",
    "_metrics",
    "_sample_factor",
    "_side",
    "_signal",
    "_turnover_rows",
    "apply_to_raw",
    "build_turnover_engine",
    "clear_turnover_engine_cache",
]
