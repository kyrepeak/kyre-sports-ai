"""CFB Over/Under Intelligence V2 — Upgrade Step 11 current-form + schedule-strength engine.

Additive model layer above permanently frozen Upgrade Step 10.

Certified scope
---------------
Step 11 uses only completed CURRENT-SEASON games strictly before the target
kickoff. It reads exact ESPN team IDs inherited from Step 10 and extracts:
- recent points scored / allowed,
- opponent records from the same ESPN schedule payload,
- opponent-record coverage,
- current-season sample size.

The layer converts recent scoring form into a conservative matchup signal, then
shrinks it by sample size and opponent-record coverage. Opponent quality is used
only as a schedule-strength normalization proxy. The incremental adjustment is
bounded per team and for the game total.

Integrity rules
---------------
- Previous-season games may be displayed by Step 10, but NEVER enter Step 11.
- Target/future events are excluded.
- Opponent records must be parseable; missing records reduce coverage.
- At least two current-season completed games per side are required.
- At least 60% opponent-record coverage per side is required.
- Reliability, structural sigma, feature coverage, and frozen qualification
  thresholds remain unchanged.
- The analysis line has exactly 0% influence on the Step-11 adjustment.
- No sportsbook feed, price, market probability, EV, or Monte Carlo is added.
- This structural rule is not claimed as empirical backtest calibration.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from statistics import fmean
from typing import Any, Mapping

import cfb_over_under_history_engine_v1 as history_engine
import cfb_over_under_model_v1 as frozen_raw

MODEL_VERSION = "CFB O/U FORM + SCHEDULE STRENGTH ENGINE V1 • UPGRADE STEP 11"
FROZEN_STEP10_ENGINE = "cfb_over_under_history_engine_v1"

MIN_CURRENT_SEASON_GAMES = 2
FULL_SAMPLE_GAMES = 5
MIN_OPPONENT_RECORD_COVERAGE = 0.60
FORM_GAME_WINDOW = 5
MAX_OPPONENT_RECORD_WORKERS = 6
OPPONENT_RECORD_FALLBACK_ACTIVE = True
RECENT_FORM_PROJECTION_BLEND = 0.18
SOS_CORRECTION_POINTS = 4.0
MAX_TEAM_FORM_ADJUSTMENT = 1.25
MAX_TOTAL_FORM_ADJUSTMENT = 2.0

ANALYSIS_LINE_FORM_WEIGHT = 0.0
DIRECT_SELECTION_FORM_WEIGHT = 0.0
EMPIRICAL_CALIBRATION_CLAIMED = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except Exception:
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _season_year(game: Mapping[str, Any]) -> int:
    day = _clean(game.get("game_date"))
    try:
        return int(day[:4])
    except Exception:
        return datetime.now(timezone.utc).year


def _cutoff(game: Mapping[str, Any]) -> datetime:
    kickoff = _parse_dt(game.get("kickoff_iso") or game.get("date"))
    if kickoff is not None:
        return kickoff
    day = _clean(game.get("game_date"))
    try:
        return datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.max.replace(tzinfo=timezone.utc)


def _competition(event: Mapping[str, Any]) -> Mapping[str, Any]:
    comps = event.get("competitions") or []
    if comps and isinstance(comps[0], Mapping):
        return comps[0]
    return {}


def _record_pct(summary: Any) -> float | None:
    text = _clean(summary)
    if not text:
        return None
    import re
    match = re.fullmatch(r"(\d+)-(\d+)(?:-(\d+))?", text)
    if not match:
        return None
    wins = int(match.group(1))
    losses = int(match.group(2))
    ties = int(match.group(3) or 0)
    games = wins + losses + ties
    if games <= 0:
        return None
    return (wins + 0.5 * ties) / games


def _competitor_record_pct(competitor: Mapping[str, Any]) -> float | None:
    records = competitor.get("records") or []
    if isinstance(records, Mapping):
        records = [records]
    if not isinstance(records, list):
        return None

    ordered: list[Mapping[str, Any]] = []
    for item in records:
        if isinstance(item, Mapping) and _clean(item.get("type")).lower() in {
            "total", "overall",
        }:
            ordered.append(item)
    ordered.extend(
        item for item in records
        if isinstance(item, Mapping) and item not in ordered
    )
    for item in ordered:
        pct = _record_pct(
            item.get("summary")
            or item.get("displayValue")
            or item.get("record")
        )
        if pct is not None:
            return float(pct)
    return None


def _event_row_with_opponent_record(
    event: Mapping[str, Any],
    team_id: str,
) -> dict[str, Any] | None:
    base = history_engine._event_row(event, team_id)
    if not base:
        return None

    comp = _competition(event)
    opponent: Mapping[str, Any] | None = None
    for competitor in comp.get("competitors") or []:
        if not isinstance(competitor, Mapping):
            continue
        team = competitor.get("team") or {}
        if not isinstance(team, Mapping):
            team = {}
        if _clean(team.get("id")) != _clean(team_id):
            opponent = competitor
            break

    out = dict(base)
    out["opponent_record_pct"] = (
        _competitor_record_pct(opponent) if opponent is not None else None
    )
    return out


def _current_season_rows(
    payload: Mapping[str, Any],
    team_id: str,
    season: int,
    cutoff: datetime,
    excluded_event_id: str = "",
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        row = _event_row_with_opponent_record(event, team_id)
        if not row:
            continue
        event_id = _clean(row.get("event_id"))
        if excluded_event_id and event_id == _clean(excluded_event_id):
            continue
        dt = row.get("date_dt")
        if not isinstance(dt, datetime) or dt >= cutoff:
            continue
        if dt.year != int(season):
            continue
        rows[event_id or _clean(row.get("date"))] = row
    ordered = sorted(
        rows.values(),
        key=lambda row: row.get("date_dt") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return ordered[:FORM_GAME_WINDOW]


def _opponent_schedule_record_pct(
    team_id: str,
    season: int,
    cutoff: datetime,
    excluded_event_id: str = "",
) -> tuple[float | None, int, list[dict[str, Any]]]:
    """Compute an opponent's pre-target current-season record from its own schedule."""
    payload, attempts = history_engine._fetch_team_schedule(_clean(team_id), int(season))
    wins = losses = ties = 0
    seen: set[str] = set()
    for event in payload.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        row = history_engine._event_row(event, _clean(team_id))
        if not row:
            continue
        event_id = _clean(row.get("event_id"))
        if excluded_event_id and event_id == _clean(excluded_event_id):
            continue
        dt = row.get("date_dt")
        if not isinstance(dt, datetime) or dt >= cutoff or dt.year != int(season):
            continue
        key = event_id or _clean(row.get("date"))
        if key in seen:
            continue
        seen.add(key)
        pf = float(row.get("points_for") or 0.0)
        pa = float(row.get("points_against") or 0.0)
        if pf > pa:
            wins += 1
        elif pf < pa:
            losses += 1
        else:
            ties += 1
    games = wins + losses + ties
    pct = ((wins + 0.5 * ties) / games) if games else None
    return (float(pct) if pct is not None else None, games, list(attempts or []))


def _hydrate_opponent_records(
    rows: list[Mapping[str, Any]],
    season: int,
    cutoff: datetime,
    excluded_event_id: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fill missing inline opponent records from exact opponent schedule IDs."""
    hydrated = [dict(row) for row in rows]
    missing_ids = sorted({
        _clean(row.get("opponent_id"))
        for row in hydrated
        if row.get("opponent_record_pct") is None
        and _clean(row.get("opponent_id")).isdigit()
    })
    resolved: dict[str, tuple[float | None, int]] = {}
    attempts: list[dict[str, Any]] = []

    if missing_ids and OPPONENT_RECORD_FALLBACK_ACTIVE:
        with ThreadPoolExecutor(
            max_workers=max(1, min(MAX_OPPONENT_RECORD_WORKERS, len(missing_ids)))
        ) as pool:
            futures = {
                pool.submit(
                    _opponent_schedule_record_pct,
                    team_id,
                    int(season),
                    cutoff,
                    excluded_event_id,
                ): team_id
                for team_id in missing_ids
            }
            for future in as_completed(futures):
                team_id = futures[future]
                try:
                    pct, games, these_attempts = future.result()
                except Exception:
                    pct, games, these_attempts = None, 0, []
                resolved[team_id] = (pct, games)
                attempts.extend(these_attempts)

    fallback_resolved = 0
    inline_records = 0
    for row in hydrated:
        if row.get("opponent_record_pct") is not None:
            row["opponent_record_source"] = "ESPN inline competitor record"
            inline_records += 1
            continue
        opp_id = _clean(row.get("opponent_id"))
        pct, games = resolved.get(opp_id, (None, 0))
        row["opponent_record_pct"] = pct
        row["opponent_record_games"] = int(games)
        if pct is not None:
            row["opponent_record_source"] = (
                "ESPN opponent schedule completed games before target"
            )
            fallback_resolved += 1
        else:
            row["opponent_record_source"] = "unavailable"

    return hydrated, {
        "inline_records": inline_records,
        "fallback_requested": len(missing_ids),
        "fallback_resolved": fallback_resolved,
        "attempts": attempts,
    }


def _side_form(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n <= 0:
        return {
            "ready": False,
            "games": 0,
            "avg_points_for": None,
            "avg_points_against": None,
            "opponent_record_coverage": 0.0,
            "avg_opponent_win_pct": None,
            "sample_factor": 0.0,
            "quality_factor": 0.0,
            "sample": [],
        }

    pfs = [float(row["points_for"]) for row in rows]
    pas = [float(row["points_against"]) for row in rows]
    opp_pcts = [
        float(row["opponent_record_pct"])
        for row in rows
        if row.get("opponent_record_pct") is not None
    ]
    record_coverage = len(opp_pcts) / n
    sample_factor = min(1.0, n / FULL_SAMPLE_GAMES)
    coverage_factor = _clamp(
        record_coverage / MIN_OPPONENT_RECORD_COVERAGE,
        0.0,
        1.0,
    )
    quality_factor = sample_factor * coverage_factor
    avg_opp = float(fmean(opp_pcts)) if opp_pcts else None
    sos_signal = (
        _clamp((avg_opp - 0.5) * 2.0, -1.0, 1.0)
        if avg_opp is not None
        else 0.0
    )
    adjusted_pf = float(fmean(pfs)) + SOS_CORRECTION_POINTS * sos_signal
    adjusted_pa = float(fmean(pas)) - SOS_CORRECTION_POINTS * sos_signal

    ready = bool(
        n >= MIN_CURRENT_SEASON_GAMES
        and record_coverage >= MIN_OPPONENT_RECORD_COVERAGE
    )
    return {
        "ready": ready,
        "games": n,
        "avg_points_for": float(fmean(pfs)),
        "avg_points_against": float(fmean(pas)),
        "opponent_record_coverage": float(record_coverage),
        "avg_opponent_win_pct": avg_opp,
        "sos_signal": float(sos_signal),
        "sos_adjusted_points_for": float(adjusted_pf),
        "sos_adjusted_points_against": float(adjusted_pa),
        "sample_factor": float(sample_factor),
        "quality_factor": float(quality_factor),
        "sample": [dict(row) for row in rows],
    }


def _side_adjustment(
    base_points: float,
    offense: Mapping[str, Any],
    opponent_defense: Mapping[str, Any],
) -> dict[str, float]:
    offense_pf = _float(offense.get("sos_adjusted_points_for"))
    defense_pa = _float(opponent_defense.get("sos_adjusted_points_against"))
    if offense_pf is None or defense_pa is None:
        return {
            "recent_matchup_expectation": float(base_points),
            "raw_gap": 0.0,
            "quality_factor": 0.0,
            "adjustment": 0.0,
        }

    expectation = (offense_pf + defense_pa) / 2.0
    raw_gap = expectation - float(base_points)
    quality = min(
        float(offense.get("quality_factor") or 0.0),
        float(opponent_defense.get("quality_factor") or 0.0),
    )
    adjustment = _clamp(
        raw_gap * RECENT_FORM_PROJECTION_BLEND * quality,
        -MAX_TEAM_FORM_ADJUSTMENT,
        MAX_TEAM_FORM_ADJUSTMENT,
    )
    return {
        "recent_matchup_expectation": float(expectation),
        "raw_gap": float(raw_gap),
        "quality_factor": float(quality),
        "adjustment": float(adjustment),
    }


def build_form_strength_engine(
    game: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    step10_history: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    history = dict(step10_history or {})
    if not history:
        history = history_engine.build_history_engine(game, away, home)

    away_id = _clean(history.get("away_espn_team_id"))
    home_id = _clean(history.get("home_espn_team_id"))
    event_id = _clean(history.get("event_id"))
    if not away_id.isdigit() or not home_id.isdigit():
        return {
            "version": MODEL_VERSION,
            "ready": True,
            "model_ready": False,
            "reason": "verified ESPN team IDs are unavailable from Step 10",
            "away_form": {},
            "home_form": {},
            "coverage": 0.0,
            "analysis_line_form_weight": ANALYSIS_LINE_FORM_WEIGHT,
            "direct_selection_form_weight": DIRECT_SELECTION_FORM_WEIGHT,
            "sportsbook_input_used": False,
            "market_probability_used": False,
            "edge_or_ev_used": False,
            "monte_carlo_used": False,
        }

    season = _season_year(game)
    cutoff = _cutoff(game)
    away_payload, away_attempts = history_engine._fetch_team_schedule(away_id, season)
    home_payload, home_attempts = history_engine._fetch_team_schedule(home_id, season)

    away_rows = _current_season_rows(
        away_payload, away_id, season, cutoff, excluded_event_id=event_id
    )
    home_rows = _current_season_rows(
        home_payload, home_id, season, cutoff, excluded_event_id=event_id
    )
    away_rows, away_record_diag = _hydrate_opponent_records(
        away_rows, season, cutoff, excluded_event_id=event_id
    )
    home_rows, home_record_diag = _hydrate_opponent_records(
        home_rows, season, cutoff, excluded_event_id=event_id
    )
    away_form = _side_form(away_rows)
    home_form = _side_form(home_rows)

    model_ready = bool(away_form.get("ready") and home_form.get("ready"))
    reason = ""
    if not model_ready:
        problems = []
        if int(away_form.get("games") or 0) < MIN_CURRENT_SEASON_GAMES:
            problems.append("away current-season sample below 2 games")
        if int(home_form.get("games") or 0) < MIN_CURRENT_SEASON_GAMES:
            problems.append("home current-season sample below 2 games")
        if float(away_form.get("opponent_record_coverage") or 0.0) < MIN_OPPONENT_RECORD_COVERAGE:
            problems.append("away opponent-record coverage below 60%")
        if float(home_form.get("opponent_record_coverage") or 0.0) < MIN_OPPONENT_RECORD_COVERAGE:
            problems.append("home opponent-record coverage below 60%")
        reason = "; ".join(problems) or "current-form evidence below Step-11 minimum coverage"

    coverage = (
        float(away_form.get("quality_factor") or 0.0)
        + float(home_form.get("quality_factor") or 0.0)
    ) / 2.0

    return {
        "version": MODEL_VERSION,
        "ready": True,
        "model_ready": model_ready,
        "reason": reason,
        "event_id": event_id,
        "season": season,
        "away_espn_team_id": away_id,
        "home_espn_team_id": home_id,
        "away_form": away_form,
        "home_form": home_form,
        "coverage": float(coverage),
        "current_season_only": True,
        "previous_season_projection_weight": 0.0,
        "future_event_leakage_allowed": False,
        "target_event_excluded": True,
        "analysis_line_form_weight": ANALYSIS_LINE_FORM_WEIGHT,
        "direct_selection_form_weight": DIRECT_SELECTION_FORM_WEIGHT,
        "empirical_calibration_claimed": EMPIRICAL_CALIBRATION_CLAIMED,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
        "diagnostics": {
            "away_attempts": list(away_attempts or []),
            "home_attempts": list(home_attempts or []),
            "away_opponent_record_resolution": away_record_diag,
            "home_opponent_record_resolution": home_record_diag,
        },
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
    """Apply bounded Step-11 form normalization above frozen Step 10."""
    out = dict(base_raw)
    out["base_step10_model_version"] = _clean(base_raw.get("version"))
    out["version"] = MODEL_VERSION
    out["upgrade_step11_form_ready"] = bool(engine.get("model_ready"))
    out["upgrade_step11_applied"] = False
    out["form_strength_coverage"] = float(engine.get("coverage") or 0.0)
    out["analysis_line_form_weight"] = ANALYSIS_LINE_FORM_WEIGHT
    out["direct_selection_form_weight"] = DIRECT_SELECTION_FORM_WEIGHT
    out["previous_season_projection_weight"] = 0.0

    if not base_raw.get("ready") or not engine.get("model_ready"):
        out["form_strength_reason"] = _clean(
            engine.get("reason")
            or "current-form evidence below Step-11 minimum coverage"
        )
        return out

    base_away = float(base_raw.get("projected_away_points") or 0.0)
    base_home = float(base_raw.get("projected_home_points") or 0.0)
    away_form = engine.get("away_form") or {}
    home_form = engine.get("home_form") or {}

    away_adj = _side_adjustment(base_away, away_form, home_form)
    home_adj = _side_adjustment(base_home, home_form, away_form)
    a = float(away_adj["adjustment"])
    h = float(home_adj["adjustment"])
    total_delta = a + h
    if abs(total_delta) > MAX_TOTAL_FORM_ADJUSTMENT and abs(total_delta) > 0:
        scale = MAX_TOTAL_FORM_ADJUSTMENT / abs(total_delta)
        a *= scale
        h *= scale
        total_delta = a + h

    projected_away = base_away + a
    projected_home = base_home + h
    projected_total = projected_away + projected_home
    sigma = float(
        base_raw.get("structural_total_sigma")
        or frozen_raw.BASE_TOTAL_SIGMA
    )
    line = float(base_raw.get("analysis_line") or 0.0)
    p_over, p_under, p_push = frozen_raw._line_probabilities(
        projected_total, sigma, line
    )
    interval_low = max(0.0, projected_total - 1.645 * sigma)
    interval_high = projected_total + 1.645 * sigma

    components = dict(base_raw.get("components") or {})
    components.update({
        "step11_away_form_adjustment": float(a),
        "step11_home_form_adjustment": float(h),
        "step11_total_form_adjustment": float(total_delta),
        "step11_away_recent_matchup_expectation": float(
            away_adj["recent_matchup_expectation"]
        ),
        "step11_home_recent_matchup_expectation": float(
            home_adj["recent_matchup_expectation"]
        ),
        "step11_away_quality_factor": float(away_adj["quality_factor"]),
        "step11_home_quality_factor": float(home_adj["quality_factor"]),
        "step11_form_strength_coverage": float(engine.get("coverage") or 0.0),
        "step11_structural_sigma_adjustment": 0.0,
        "step11_reliability_adjustment": 0.0,
    })

    out.update({
        "upgrade_step11_applied": True,
        "step11_base_projected_away_points": float(base_away),
        "step11_base_projected_home_points": float(base_home),
        "step11_base_projected_total": float(
            base_raw.get("projected_total") or (base_away + base_home)
        ),
        "projected_away_points": float(projected_away),
        "projected_home_points": float(projected_home),
        "projected_total": float(projected_total),
        "structural_total_sigma": float(sigma),
        "over_probability": float(p_over),
        "under_probability": float(p_under),
        "push_probability": float(p_push),
        "model_lean": _lean(p_over, p_under, p_push),
        "total_uncertainty_90": {
            "low": float(interval_low),
            "high": float(interval_high),
        },
        "components": components,
        "current_season_only": True,
        "future_event_leakage_allowed": False,
        "target_event_excluded": True,
        "empirical_calibration_claimed": False,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    })
    return out


__all__ = [
    "ANALYSIS_LINE_FORM_WEIGHT",
    "DIRECT_SELECTION_FORM_WEIGHT",
    "EMPIRICAL_CALIBRATION_CLAIMED",
    "FROZEN_STEP10_ENGINE",
    "FORM_GAME_WINDOW",
    "FULL_SAMPLE_GAMES",
    "MAX_TEAM_FORM_ADJUSTMENT",
    "MAX_TOTAL_FORM_ADJUSTMENT",
    "MIN_CURRENT_SEASON_GAMES",
    "MIN_OPPONENT_RECORD_COVERAGE",
    "MODEL_VERSION",
    "OPPONENT_RECORD_FALLBACK_ACTIVE",
    "RECENT_FORM_PROJECTION_BLEND",
    "SOS_CORRECTION_POINTS",
    "_competitor_record_pct",
    "_current_season_rows",
    "_event_row_with_opponent_record",
    "_hydrate_opponent_records",
    "_opponent_schedule_record_pct",
    "_record_pct",
    "_side_adjustment",
    "_side_form",
    "apply_to_raw",
    "build_form_strength_engine",
]
