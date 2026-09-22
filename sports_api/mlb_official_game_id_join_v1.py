"""Exact official-MLB-game-ID join for model rows and live sportsbook markets.

Step 5.1 is intentionally identity-only. It does not compare team names, dates,
start times, pitchers, or any other heuristic field. A model row may join a
sportsbook row only when its MLB Stats API ``game_pk`` is exactly the same
canonical positive integer as the market row's ``official_game_id``.

This module is additive and read-only. It does not alter projections, market
collection, persistence, or wagering behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


MODEL_GAME_ID_FIELD = "game_pk"
MARKET_GAME_ID_FIELD = "official_game_id"
MATCH_METHOD = "official_mlb_game_id_exact"
DATA_TYPE = "mlb_model_market_official_id_join_v1"
SCHEMA_VERSION = 1


class MLBOfficialGameIDJoinError(ValueError):
    """Raised when exact identity matching would be ambiguous."""


@dataclass(frozen=True)
class InvalidIdentity:
    source: str
    index: int
    field: str
    value: Any
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "index": self.index,
            "field": self.field,
            "value": self.value,
            "reason": self.reason,
        }


def canonical_official_game_id(value: Any) -> int:
    """Return a positive integer MLB game ID or raise.

    ``bool`` and floats are deliberately rejected even though Python can coerce
    them to integers. Decimal-string forms such as ``"824911.0"`` are also
    rejected. This keeps the identity contract narrow and auditable.
    """
    if isinstance(value, bool):
        raise MLBOfficialGameIDJoinError("boolean is not a valid MLB game ID")
    if isinstance(value, int):
        game_id = value
    elif isinstance(value, str):
        text = value.strip()
        if not text or not text.isdigit():
            raise MLBOfficialGameIDJoinError("MLB game ID must be digits only")
        game_id = int(text)
    else:
        raise MLBOfficialGameIDJoinError("MLB game ID must be an int or digit string")
    if game_id <= 0:
        raise MLBOfficialGameIDJoinError("MLB game ID must be positive")
    return game_id


def _get(row: Any, field: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(field)
    getter = getattr(row, "get", None)
    if callable(getter):
        return getter(field)
    return None


def _snapshot(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    to_dict = getattr(row, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, Mapping):
            return dict(value)
    return {"value": row}


def _index_rows(
    rows: Iterable[Any],
    *,
    source: str,
    field: str,
) -> tuple[dict[int, dict[str, Any]], list[InvalidIdentity], int]:
    index: dict[int, dict[str, Any]] = {}
    invalid: list[InvalidIdentity] = []
    count = 0
    for position, row in enumerate(rows):
        count += 1
        raw = _get(row, field)
        try:
            game_id = canonical_official_game_id(raw)
        except MLBOfficialGameIDJoinError as exc:
            invalid.append(
                InvalidIdentity(
                    source=source,
                    index=position,
                    field=field,
                    value=raw,
                    reason=str(exc),
                )
            )
            continue
        if game_id in index:
            raise MLBOfficialGameIDJoinError(
                f"duplicate {source} MLB game ID {game_id}; exact join is ambiguous"
            )
        index[game_id] = _snapshot(row)
    return index, invalid, count


def join_model_games_to_markets(
    model_games: Iterable[Any],
    market_games: Iterable[Any],
) -> dict[str, Any]:
    """Join model and market rows by exact official MLB game ID only.

    Model identity is read only from ``game_pk``. Market identity is read only
    from ``official_game_id``. Missing/invalid identities are never matched.
    Duplicate valid IDs raise because there is no safe one-to-one resolution.
    """
    model_index, invalid_model, model_count = _index_rows(
        model_games,
        source="model",
        field=MODEL_GAME_ID_FIELD,
    )
    market_index, invalid_market, market_count = _index_rows(
        market_games,
        source="market",
        field=MARKET_GAME_ID_FIELD,
    )

    matched_ids = sorted(set(model_index).intersection(market_index))
    matched = [
        {
            "official_game_id": game_id,
            "model": model_index[game_id],
            "market": market_index[game_id],
            "match_method": MATCH_METHOD,
        }
        for game_id in matched_ids
    ]

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "match_method": MATCH_METHOD,
        "fallback_matching_used": False,
        "model_game_id_field": MODEL_GAME_ID_FIELD,
        "market_game_id_field": MARKET_GAME_ID_FIELD,
        "model_game_count": model_count,
        "market_game_count": market_count,
        "valid_model_game_count": len(model_index),
        "valid_market_game_count": len(market_index),
        "matched_count": len(matched),
        "matched_games": matched,
        "unmatched_model_game_ids": sorted(set(model_index) - set(market_index)),
        "unmatched_market_game_ids": sorted(set(market_index) - set(model_index)),
        "invalid_model_identities": [row.as_dict() for row in invalid_model],
        "invalid_market_identities": [row.as_dict() for row in invalid_market],
    }


__all__ = [
    "DATA_TYPE",
    "MARKET_GAME_ID_FIELD",
    "MATCH_METHOD",
    "MODEL_GAME_ID_FIELD",
    "MLBOfficialGameIDJoinError",
    "SCHEMA_VERSION",
    "canonical_official_game_id",
    "join_model_games_to_markets",
]
