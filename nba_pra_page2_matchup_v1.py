'''NBA PRA Page 2 opponent-rank presentation logic.'''
from __future__ import annotations
from statistics import mean
from typing import Any, Mapping

RANK_SEMANTICS = "NBA opponent rank: 1 = toughest/stingiest, 30 = most permissive"
PRA_METHOD = "mean of verified PTS/REB/AST opponent ranks"


def grade_rank(rank: int | None) -> str:
    try:
        value = int(rank) if rank is not None else 0
    except (TypeError, ValueError):
        return "UNAVAILABLE"
    if not 1 <= value <= 30:
        return "UNAVAILABLE"
    if value <= 10:
        return "TOUGH"
    if value <= 21:
        return "MEDIUM"
    return "FAVORABLE"


def _component(value: Any) -> dict[str, Any]:
    row = dict(value) if isinstance(value, Mapping) else {}
    rank = row.get("rank")
    row["grade"] = grade_rank(rank)
    return row


def build_matchup_summary(rows: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(rows or {})
    components = {name: _component(payload.get(name)) for name in ("points", "rebounds", "assists")}
    ranks = [c.get("rank") for c in components.values()]
    valid = []
    for rank in ranks:
        try:
            number = int(rank)
        except (TypeError, ValueError):
            number = 0
        if 1 <= number <= 30:
            valid.append(number)
    pra_rank = int(round(mean(valid))) if len(valid) == 3 else None
    return {
        **components,
        "pra_rank": pra_rank,
        "matchup_grade": grade_rank(pra_rank),
        "pra_method": PRA_METHOD,
        "rank_semantics": RANK_SEMANTICS,
        "source": payload.get("source"),
        "evidence_period": payload.get("evidence_period"),
        "verification": payload.get("verification"),
        "diagnostic_state": payload.get("diagnostic_state"),
    }
