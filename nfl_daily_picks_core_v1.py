from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
from typing import Any, Iterable

PLAYER_MARKETS = frozenset({"passing-yards", "rushing-yards", "receiving-yards"})
LINE_REQUIRED_MARKETS = frozenset({"spread", "game-total", "passing-yards", "rushing-yards", "receiving-yards"})
BLOCKED_SOURCE_STATES = frozenset({"GATED", "NO PLAY", "UNAVAILABLE", "STALE", "ERROR"})


@dataclass(frozen=True)
class DailyPickCandidate:
    market_id: str
    market_label: str
    game_id: str
    game_date: date
    kickoff_at: datetime
    team_id: str
    opponent_team_id: str
    athlete_id: str | None
    subject_label: str
    matchup_label: str
    side: str
    market_line: float | None
    model_projection: float | None
    model_probability: float
    edge_value: float
    source_ready: bool
    source_fresh_at: datetime
    source_age_seconds: float
    data_quality: float
    uncertainty: float
    source_version: str
    reason_components: tuple[str, ...]
    source_grade: str = "QUALIFIED"
    source_state: str = "READY"
    freshness_limit_seconds: float = 300.0
    metadata: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class MarketLoadResult:
    market_id: str
    status: str
    candidates: tuple[DailyPickCandidate, ...]
    source_version: str
    fresh_at: datetime | None
    diagnostic: str = ""


def _finite(value: float | int | None) -> bool:
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def candidate_is_eligible(candidate: DailyPickCandidate, *, now_utc: datetime) -> tuple[bool, str]:
    if not candidate.game_id or not candidate.team_id or not candidate.opponent_team_id:
        return False, "MISSING_GAME_IDENTITY"
    if candidate.market_id in PLAYER_MARKETS and not candidate.athlete_id:
        return False, "MISSING_ATHLETE_ID"
    if candidate.kickoff_at <= now_utc:
        return False, "KICKED_OFF"
    if not candidate.source_ready:
        return False, "SOURCE_NOT_READY"

    source_state = str(candidate.source_state or "").strip().upper()
    if source_state in BLOCKED_SOURCE_STATES:
        return False, f"SOURCE_{source_state.replace(' ', '_')}"

    if not _finite(candidate.model_probability) or not 0.0 <= float(candidate.model_probability) <= 1.0:
        return False, "INVALID_PROBABILITY"
    if not _finite(candidate.edge_value):
        return False, "INVALID_EDGE"
    if candidate.market_id in LINE_REQUIRED_MARKETS and not _finite(candidate.market_line):
        return False, "MISSING_MARKET_LINE"
    if candidate.model_projection is not None and not _finite(candidate.model_projection):
        return False, "INVALID_PROJECTION"
    if not _finite(candidate.source_age_seconds) or float(candidate.source_age_seconds) < 0:
        return False, "INVALID_FRESHNESS"
    if not _finite(candidate.freshness_limit_seconds) or float(candidate.freshness_limit_seconds) <= 0:
        return False, "INVALID_FRESHNESS_LIMIT"
    try:
        elapsed_age = max(0.0, float((now_utc - candidate.source_fresh_at).total_seconds()))
    except (AttributeError, TypeError, ValueError):
        return False, "INVALID_FRESHNESS"
    effective_age = max(float(candidate.source_age_seconds), elapsed_age)
    if effective_age > float(candidate.freshness_limit_seconds):
        return False, "STALE"
    if not _finite(candidate.data_quality) or not 0.0 <= float(candidate.data_quality) <= 1.0:
        return False, "INVALID_DATA_QUALITY"
    if not _finite(candidate.uncertainty) or float(candidate.uncertainty) < 0:
        return False, "INVALID_UNCERTAINTY"
    if not str(candidate.side or "").strip():
        return False, "MISSING_SIDE"
    return True, "ELIGIBLE"


def market_status_from_results(results: Iterable[MarketLoadResult]) -> dict[str, str]:
    return {result.market_id: result.status for result in results}
