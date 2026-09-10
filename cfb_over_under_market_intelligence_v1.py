"""CFB Over/Under Step 5C market-intelligence layer.

Pure, additive market context built above the certified Step 5A/5B safety path.
This module never modifies projection math. It groups sportsbook totals only by
strict numeric official ESPN event ID and truthfully distinguishes single-book
context from real multi-book consensus.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Any, Mapping

MODEL_VERSION = "CFB O/U MARKET INTELLIGENCE V1 • STEP 5C"
CONSENSUS_RANGE_MAX = 1.0
MIXED_RANGE_MAX = 2.5
_ALLOWED_LINE_STATUS = {"active", "open"}


class MarketIntelligenceError(ValueError):
    """Raised when market context cannot be certified safely."""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _finite_number(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MarketIntelligenceError(f"unsafe_non_numeric:{field}") from exc
    if not math.isfinite(number):
        raise MarketIntelligenceError(f"unsafe_nonfinite:{field}")
    return number


def _verify_zero_weight(payload: Mapping[str, Any]) -> None:
    semantics = payload.get("market_semantics")
    if semantics is None:
        return
    if not isinstance(semantics, Mapping):
        raise MarketIntelligenceError("unsafe_market_semantics")
    weight = _finite_number(
        semantics.get("projection_weight", 0.0),
        field="projection_weight",
    )
    if weight != 0.0:
        raise MarketIntelligenceError("unsafe_nonzero_projection_weight")
    if semantics.get("may_modify_projection") is True:
        raise MarketIntelligenceError("unsafe_market_may_modify_projection")


def _market_state(provider_count: int, total_range: float) -> str:
    if provider_count == 1:
        return "SINGLE_BOOK"
    if total_range <= CONSENSUS_RANGE_MAX:
        return "CONSENSUS"
    if total_range <= MIXED_RANGE_MAX:
        return "MIXED"
    return "DISAGREEMENT"


def build_market_intelligence(
    payload: Mapping[str, Any],
    *,
    model_projections: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a strict per-event market board without influencing projections.

    `model_projections`, when supplied, is used only to report a display edge
    against the market reference total. The supplied projection value is copied
    into the result unchanged and receives a projection weight of exactly 0.0.
    """
    if not isinstance(payload, Mapping):
        raise MarketIntelligenceError("unsafe_payload_not_mapping")
    _verify_zero_weight(payload)

    rows = payload.get("games")
    if not isinstance(rows, list):
        raise MarketIntelligenceError("unsafe_games_not_list")

    grouped: dict[str, list[dict[str, Any]]] = {}
    books_seen: dict[str, set[str]] = {}

    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise MarketIntelligenceError(f"unsafe_market_row:{index}")

        event_id = _clean(row.get("game_id"))
        if not event_id or not event_id.isdigit():
            raise MarketIntelligenceError("unsafe_non_official_event_id")

        sportsbook = _clean(row.get("sportsbook"))
        if not sportsbook:
            raise MarketIntelligenceError(f"unsafe_missing_sportsbook:{event_id}")

        status = _clean(row.get("line_status")).casefold()
        if status not in _ALLOWED_LINE_STATUS:
            raise MarketIntelligenceError(
                f"unsafe_noncurrent_line_status:{event_id}:{status or 'missing'}"
            )

        if row.get("identity_verified") is not True:
            raise MarketIntelligenceError(
                f"unsafe_unverified_event_identity:{event_id}"
            )

        total = _finite_number(row.get("total"), field=f"total:{event_id}")
        book_key = sportsbook.casefold()
        event_books = books_seen.setdefault(event_id, set())
        if book_key in event_books:
            raise MarketIntelligenceError(
                f"unsafe_duplicate_sportsbook:{event_id}:{sportsbook}"
            )
        event_books.add(book_key)

        grouped.setdefault(event_id, []).append(
            {
                "sportsbook": sportsbook,
                "total": total,
                "line_status": status,
                "line_updated_at_utc": _clean(row.get("line_updated_at_utc")),
            }
        )

    projection_map = model_projections if isinstance(model_projections, Mapping) else {}
    games: dict[str, dict[str, Any]] = {}

    for event_id, market_rows in sorted(grouped.items()):
        market_rows = sorted(
            market_rows,
            key=lambda item: item["sportsbook"].casefold(),
        )
        totals = [float(item["total"]) for item in market_rows]
        provider_count = len(market_rows)
        low = min(totals)
        high = max(totals)
        total_range = high - low
        reference_total = float(median(totals))
        consensus_available = provider_count >= 2

        projection_value = projection_map.get(event_id)
        projection: float | None = None
        model_market_edge: float | None = None
        if projection_value is not None:
            projection = _finite_number(
                projection_value,
                field=f"model_projection:{event_id}",
            )
            model_market_edge = projection - reference_total

        games[event_id] = {
            "game_id": event_id,
            "provider_count": provider_count,
            "sportsbooks": market_rows,
            "market_state": _market_state(provider_count, total_range),
            "consensus_available": consensus_available,
            "reference_total": reference_total,
            "reference_source": (
                "multibook_median" if consensus_available else "single_book"
            ),
            "minimum_total": low,
            "maximum_total": high,
            "total_range": total_range,
            "model_projection": projection,
            "model_market_edge": model_market_edge,
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        }

    return {
        "version": MODEL_VERSION,
        "game_count": len(games),
        "games": games,
        "diagnostics": {
            "official_event_id_only": True,
            "fuzzy_matching": False,
            "synthetic_official_ids": False,
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "single_book_is_consensus": False,
            "consensus_minimum_provider_count": 2,
            "consensus_range_max": CONSENSUS_RANGE_MAX,
            "mixed_range_max": MIXED_RANGE_MAX,
        },
    }


__all__ = [
    "CONSENSUS_RANGE_MAX",
    "MIXED_RANGE_MAX",
    "MODEL_VERSION",
    "MarketIntelligenceError",
    "build_market_intelligence",
]
