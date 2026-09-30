"""CFB Top Picks Research V2 Step 7 — verified benefits + risks.

Read-only synthesis over frozen Steps 1-6. No projection, probability, ranking,
selection, sportsbook weighting, or API 2 behavior may change here.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

MODEL_VERSION = "CFB TOP PICKS RESEARCH V2 STEP 7 • VERIFIED BENEFITS RISKS"
BENEFITS_RISKS_PROJECTION_WEIGHT = 0.0
SPORTSBOOK_PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
API2_USED = False

_ALLOWED = {"VERIFIED", "VERIFIED_MODEL_CONTEXT", "VERIFIED_EVIDENCE_GAP"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _f(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except Exception:
        return None


def _metric(profile: Mapping[str, Any], key: str) -> dict[str, Any]:
    metrics = profile.get("metrics") or {}
    raw = metrics.get(key) or {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _metric_value(profile: Mapping[str, Any], key: str) -> float | None:
    return _f(_metric(profile, key).get("value"))


def _item(
    kind: str,
    text: str,
    *,
    sources: list[str],
    observed_at: str,
    evidence_key: str,
    status: str = "VERIFIED",
    football_evidence: bool = True,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "status": status if status in _ALLOWED else "VERIFIED_EVIDENCE_GAP",
        "text": _clean(text),
        "sources": [str(s) for s in sources if _clean(s)],
        "observed_at": _clean(observed_at),
        "evidence_key": evidence_key,
        "football_evidence": bool(football_evidence),
    }


def _sources(*metrics: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for metric in metrics:
        source = _clean(metric.get("source"))
        if source and source not in out:
            out.append(source)
    return out


def _observed(*metrics: Mapping[str, Any], fallback: str = "") -> str:
    for metric in metrics:
        value = _clean(metric.get("observed_at"))
        if value:
            return value
    return fallback


def _line(row: Mapping[str, Any]) -> float | None:
    match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*$", _clean(row.get("pick")))
    return _f(match.group(1)) if match else None


def _probability(row: Mapping[str, Any]) -> float | None:
    value = _f(row.get("probability_value"))
    if value is not None:
        return value if value <= 1.0 else value / 100.0
    raw = _f(row.get("probability"))
    if raw is None:
        return None
    return raw if raw <= 1.0 else raw / 100.0


def _selected_side(row: Mapping[str, Any]) -> tuple[str, str]:
    pick = _clean(row.get("pick"))
    away = _clean(row.get("away"))
    home = _clean(row.get("home"))
    if away and pick.casefold().startswith(away.casefold()):
        return "away", away
    if home and pick.casefold().startswith(home.casefold()):
        return "home", home
    return "", ""


def _model_context(row: Mapping[str, Any], observed_at: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    p = _probability(row)
    if p is None:
        return None, None
    source = _clean(row.get("source")) or "Frozen CFB Top Picks model"
    pick = _clean(row.get("pick")) or "this pick"
    benefit = _item(
        "benefit",
        f"Frozen model support: {pick} carries a {p * 100:.0f}% probability in the already-ranked board.",
        sources=[source],
        observed_at=observed_at,
        evidence_key="frozen_model_probability",
        status="VERIFIED_MODEL_CONTEXT",
        football_evidence=False,
    )
    risk = _item(
        "risk",
        f"Residual model risk: the same frozen probability leaves {(1.0 - p) * 100:.0f}% modeled outcome mass against {pick}.",
        sources=[source],
        observed_at=observed_at,
        evidence_key="frozen_model_residual",
        status="VERIFIED_MODEL_CONTEXT",
        football_evidence=False,
    )
    return benefit, risk


def _add_threshold_fact(
    benefits: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    *,
    value: float | None,
    line: float | None,
    over_selected: bool,
    label: str,
    source_metrics: tuple[Mapping[str, Any], ...],
    observed_at: str,
    evidence_key: str,
) -> None:
    if value is None or line is None or value == line:
        return
    supports_over = value > line
    supports_pick = supports_over if over_selected else not supports_over
    relation = "above" if value > line else "below"
    target = benefits if supports_pick else risks
    kind = "benefit" if supports_pick else "risk"
    target.append(_item(
        kind,
        f"{label}: {value:.1f} is {relation} the selected {line:.1f} total threshold.",
        sources=_sources(*source_metrics),
        observed_at=_observed(*source_metrics, fallback=observed_at),
        evidence_key=evidence_key,
    ))


def _over_under(row: Mapping[str, Any], detail: Mapping[str, Any], benefits, risks, observed_at: str) -> None:
    line = _line(row)
    pick = _clean(row.get("pick")).upper()
    over_selected = pick.startswith("OVER")
    if line is None or not (over_selected or pick.startswith("UNDER")):
        return

    offense = detail.get("offense_research") or {}
    defense = detail.get("defense_pace_research") or {}
    away_o, home_o = offense.get("away") or {}, offense.get("home") or {}
    away_d, home_d = defense.get("away") or {}, defense.get("home") or {}

    a_ppg, h_ppg = _metric_value(away_o, "points_per_game"), _metric_value(home_o, "points_per_game")
    if a_ppg is not None and h_ppg is not None:
        _add_threshold_fact(
            benefits, risks, value=a_ppg + h_ppg, line=line, over_selected=over_selected,
            label="Combined season scoring", source_metrics=(
                _metric(away_o, "points_per_game"), _metric(home_o, "points_per_game")
            ), observed_at=observed_at, evidence_key="combined_season_scoring",
        )

    a_recent, h_recent = _metric_value(away_o, "recent_scoring_avg"), _metric_value(home_o, "recent_scoring_avg")
    if a_recent is not None and h_recent is not None:
        _add_threshold_fact(
            benefits, risks, value=a_recent + h_recent, line=line, over_selected=over_selected,
            label="Recent team scoring", source_metrics=(
                _metric(away_o, "recent_scoring_avg"), _metric(home_o, "recent_scoring_avg")
            ), observed_at=observed_at, evidence_key="recent_scoring_total",
        )

    a_allow, h_allow = _metric_value(away_d, "recent_points_allowed_avg"), _metric_value(home_d, "recent_points_allowed_avg")
    if a_allow is not None and h_allow is not None:
        _add_threshold_fact(
            benefits, risks, value=a_allow + h_allow, line=line, over_selected=over_selected,
            label="Recent defensive allowance", source_metrics=(
                _metric(away_d, "recent_points_allowed_avg"), _metric(home_d, "recent_points_allowed_avg")
            ), observed_at=observed_at, evidence_key="recent_defensive_allowance_total",
        )

    if bool(detail.get("history_ready")):
        history_avg = _f(detail.get("avg_combined_total"))
        if history_avg is not None and history_avg > 0:
            history_source = _clean(detail.get("history_source"))
            verified = [str(s) for s in (detail.get("sources_verified") or []) if _clean(s)]
            _add_threshold_fact(
                benefits, risks, value=history_avg, line=line, over_selected=over_selected,
                label="Verified matchup-history average", source_metrics=(),
                observed_at=_clean(detail.get("history_observed_at")) or observed_at,
                evidence_key="verified_history_total",
            )
            target = benefits if ((history_avg > line) == over_selected) else risks
            if target:
                target[-1]["sources"] = ([history_source] if history_source else verified)


def _recent_margin_fact(row: Mapping[str, Any], detail: Mapping[str, Any], observed_at: str):
    side, team = _selected_side(row)
    if not side:
        return None
    offense = detail.get("offense_research") or {}
    profile = offense.get(side) or {}
    margins: list[float] = []
    for game in list(profile.get("recent_games") or []):
        if not isinstance(game, Mapping):
            continue
        pf, pa = _f(game.get("points_for")), _f(game.get("points_against"))
        if pf is not None and pa is not None:
            margins.append(pf - pa)
    if not margins:
        return None
    provider = _clean(((profile.get("source_router") or {}).get("recent_scoring") or {}).get("provider"))
    return {
        "team": team,
        "margin": sum(margins) / len(margins),
        "games": len(margins),
        "sources": [provider or "Verified completed-game scoring"],
        "observed_at": _clean(profile.get("observed_at")) or observed_at,
    }


def _series_fact(row: Mapping[str, Any], detail: Mapping[str, Any], observed_at: str):
    if not bool(detail.get("history_ready")):
        return None
    side, team = _selected_side(row)
    if not side:
        return None
    wins = int(_f(detail.get(f"{side}_wins")) or 0)
    losses = int(_f(detail.get("home_wins" if side == "away" else "away_wins")) or 0)
    meetings = int(_f(detail.get("meetings")) or 0)
    if meetings <= 0 or wins == losses:
        return None
    source = _clean(detail.get("history_source"))
    verified = [str(s) for s in (detail.get("sources_verified") or []) if _clean(s)]
    return {
        "team": team, "wins": wins, "losses": losses, "meetings": meetings,
        "sources": ([source] if source else verified),
        "observed_at": _clean(detail.get("history_observed_at")) or observed_at,
    }


def _spread(row: Mapping[str, Any], detail: Mapping[str, Any], benefits, risks, observed_at: str) -> None:
    line = _line(row)
    recent = _recent_margin_fact(row, detail, observed_at)
    if line is not None and recent is not None:
        threshold = -line
        supports = recent["margin"] > threshold
        target = benefits if supports else risks
        kind = "benefit" if supports else "risk"
        target.append(_item(
            kind,
            f"Recent scoring-margin context: {recent['team']} averages {recent['margin']:+.1f} points across its last {recent['games']} verified games; this is {'above' if supports else 'below'} the {threshold:+.1f} average-margin level implied by {line:+.1f}.",
            sources=recent["sources"], observed_at=recent["observed_at"],
            evidence_key="recent_margin_vs_spread",
        ))

    series = _series_fact(row, detail, observed_at)
    if series is not None:
        supports = series["wins"] > series["losses"]
        target = benefits if supports else risks
        kind = "benefit" if supports else "risk"
        target.append(_item(
            kind,
            f"Straight-up series context: {series['team']} is {series['wins']}-{series['losses']} across {series['meetings']} verified meetings. This is directional history, not a claimed historical cover record.",
            sources=series["sources"], observed_at=series["observed_at"],
            evidence_key="series_directional_context",
        ))


def _moneyline(row: Mapping[str, Any], detail: Mapping[str, Any], benefits, risks, observed_at: str) -> None:
    recent = _recent_margin_fact(row, detail, observed_at)
    if recent is not None and recent["margin"] != 0:
        supports = recent["margin"] > 0
        target = benefits if supports else risks
        kind = "benefit" if supports else "risk"
        target.append(_item(
            kind,
            f"Recent form: {recent['team']} has a {recent['margin']:+.1f} average scoring margin across its last {recent['games']} verified completed games.",
            sources=recent["sources"], observed_at=recent["observed_at"],
            evidence_key="recent_scoring_margin",
        ))

    series = _series_fact(row, detail, observed_at)
    if series is not None:
        supports = series["wins"] > series["losses"]
        target = benefits if supports else risks
        kind = "benefit" if supports else "risk"
        target.append(_item(
            kind,
            f"Verified series direction: {series['team']} is {series['wins']}-{series['losses']} across {series['meetings']} meetings.",
            sources=series["sources"], observed_at=series["observed_at"],
            evidence_key="series_win_direction",
        ))


def build_benefits_risks(row: Mapping[str, Any], detail: Mapping[str, Any]) -> dict[str, Any]:
    reasoning = detail.get("market_reasoning") or {}
    observed_at = _clean(reasoning.get("observed_at")) or _clean(detail.get("history_observed_at"))
    market = _clean(row.get("market")).upper()
    benefits: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []

    if detail.get("ready") is not True:
        return {
            "version": MODEL_VERSION, "market": market, "status": "IDENTITY_UNAVAILABLE",
            "benefits": [], "risks": [],
            "football_benefit_count": 0, "football_risk_count": 0,
            "projection_weight": 0.0, "sportsbook_projection_weight": 0.0,
            "may_modify_probability": False, "may_modify_ranking": False,
            "may_modify_selection": False, "api2_used": False,
        }

    if market == "OVER/UNDER":
        _over_under(row, detail, benefits, risks, observed_at)
    elif market == "SPREAD":
        _spread(row, detail, benefits, risks, observed_at)
    elif market == "MONEYLINE":
        _moneyline(row, detail, benefits, risks, observed_at)

    model_benefit, model_risk = _model_context(row, observed_at)
    if model_benefit is not None:
        benefits.append(model_benefit)
    if model_risk is not None:
        risks.append(model_risk)

    football_benefits = sum(1 for x in benefits if x.get("football_evidence"))
    football_risks = sum(1 for x in risks if x.get("football_evidence"))
    status = "READY" if benefits and risks and football_benefits and football_risks else "PARTIAL"

    return {
        "version": MODEL_VERSION,
        "market": market,
        "status": status,
        "benefits": benefits,
        "risks": risks,
        "football_benefit_count": football_benefits,
        "football_risk_count": football_risks,
        "projection_weight": BENEFITS_RISKS_PROJECTION_WEIGHT,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
        "may_modify_probability": MAY_MODIFY_PROBABILITY,
        "may_modify_ranking": MAY_MODIFY_RANKING,
        "may_modify_selection": MAY_MODIFY_SELECTION,
        "api2_used": API2_USED,
        "observed_at": observed_at,
    }


__all__ = [
    "API2_USED", "BENEFITS_RISKS_PROJECTION_WEIGHT", "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION", "MAY_MODIFY_RANKING", "MAY_MODIFY_SELECTION",
    "MODEL_VERSION", "SPORTSBOOK_PROJECTION_WEIGHT", "build_benefits_risks",
]
