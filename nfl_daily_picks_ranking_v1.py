from __future__ import annotations

from typing import Sequence

from nfl_daily_picks_core_v1 import DailyPickCandidate, candidate_is_eligible

TEAM_MARKETS = frozenset({"moneyline", "spread", "game-total"})


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _edge_strength(candidate: DailyPickCandidate) -> float:
    edge = abs(float(candidate.edge_value))
    scales = {
        "moneyline": 0.10,
        "spread": 7.0,
        "game-total": 7.0,
        "passing-yards": 10.0,
        "rushing-yards": 15.0,
        "receiving-yards": 15.0,
    }
    scale = scales.get(candidate.market_id, 10.0)
    return _clamp(edge / scale)


def _freshness(candidate: DailyPickCandidate) -> float:
    limit = max(1e-9, float(candidate.freshness_limit_seconds))
    return _clamp(1.0 - float(candidate.source_age_seconds) / limit)


def normalized_pick_score(candidate: DailyPickCandidate) -> float:
    probability_strength = _clamp((float(candidate.model_probability) - 0.50) / 0.20)
    quality = _clamp(candidate.data_quality)
    freshness = _freshness(candidate)
    uncertainty = _clamp(candidate.uncertainty)
    edge = _edge_strength(candidate)
    score = (
        0.50 * probability_strength
        + 0.20 * edge
        + 0.18 * quality
        + 0.12 * freshness
        - 0.10 * uncertainty
    )
    return round(score, 12)


def _identity(candidate: DailyPickCandidate) -> str:
    return str(candidate.athlete_id or candidate.team_id or "").strip()


def correlation_key(candidate: DailyPickCandidate) -> tuple[str, ...]:
    return (
        str(candidate.game_id),
        str(candidate.market_id),
        _identity(candidate),
        str(candidate.side).upper(),
    )


def picks_conflict(left: DailyPickCandidate, right: DailyPickCandidate) -> bool:
    if left.game_id != right.game_id or left.market_id != right.market_id:
        return False
    if left.side.upper() == right.side.upper() and _identity(left) == _identity(right):
        return False
    if left.market_id in TEAM_MARKETS:
        return True
    if left.athlete_id and right.athlete_id and left.athlete_id == right.athlete_id:
        return left.side.upper() != right.side.upper()
    return False


def picks_redundant(left: DailyPickCandidate, right: DailyPickCandidate) -> bool:
    if left.game_id != right.game_id:
        return False
    if (
        left.market_id == right.market_id
        and _identity(left) == _identity(right)
        and left.side.upper() == right.side.upper()
    ):
        return True
    if {left.market_id, right.market_id} == {"moneyline", "spread"}:
        return bool(left.team_id and left.team_id == right.team_id)
    return False


def _stable_identity(candidate: DailyPickCandidate) -> tuple[str, ...]:
    return (
        str(candidate.game_id),
        str(candidate.market_id),
        _identity(candidate),
        str(candidate.team_id),
        str(candidate.side).upper(),
    )


def _sort_key(candidate: DailyPickCandidate) -> tuple:
    return (
        -normalized_pick_score(candidate),
        -float(candidate.data_quality),
        float(candidate.source_age_seconds),
        float(candidate.uncertainty),
        -_edge_strength(candidate),
        _stable_identity(candidate),
    )


def rank_daily_picks(
    candidates: Sequence[DailyPickCandidate],
    *,
    now_utc,
    limit: int = 10,
) -> tuple[DailyPickCandidate, ...]:
    if limit <= 0:
        return ()
    eligible = []
    for candidate in tuple(candidates):
        ok, _ = candidate_is_eligible(candidate, now_utc=now_utc)
        if ok:
            eligible.append(candidate)
    ordered = sorted(eligible, key=_sort_key)
    selected: list[DailyPickCandidate] = []
    for candidate in ordered:
        if any(picks_conflict(candidate, chosen) or picks_redundant(candidate, chosen) for chosen in selected):
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return tuple(selected)


__all__ = [
    "correlation_key",
    "normalized_pick_score",
    "picks_conflict",
    "picks_redundant",
    "rank_daily_picks",
]
