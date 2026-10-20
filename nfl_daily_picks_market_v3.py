from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Iterable, Mapping

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_market_observations(
    observations: Iterable[Mapping[str, Any]],
    *,
    now_utc: datetime,
    max_age_seconds: float = 900.0,
) -> list[dict[str, Any]]:
    now = _utc(now_utc) or datetime.now(timezone.utc)
    output: list[dict[str, Any]] = []
    for raw in observations:
        row = dict(raw or {})
        if row.get("verified") is not True:
            continue
        updated_at = _utc(row.get("updated_at"))
        if updated_at is None:
            continue
        age = max(0.0, (now - updated_at).total_seconds())
        if age > float(max_age_seconds):
            continue
        book = str(row.get("book") or "").strip()
        game_id = str(row.get("game_id") or "").strip()
        market_id = str(row.get("market_id") or "").strip()
        side = str(row.get("side") or "").strip().upper()
        if not (book and game_id and market_id and side):
            continue
        output.append(
            {
                **row,
                "book": book,
                "game_id": game_id,
                "market_id": market_id,
                "side": side,
                "updated_at": updated_at,
                "age_seconds": age,
                "price": _finite(row.get("price")),
                "line": _finite(row.get("line")),
                "opening_line": _finite(row.get("opening_line")),
                "opening_updated_at": _utc(row.get("opening_updated_at")),
                "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
            }
        )
    return output


def _value_key(row: Mapping[str, Any], market_id: str, side: str) -> tuple[float, float, str]:
    price = _finite(row.get("price"))
    line = _finite(row.get("line"))
    price_value = price if price is not None else -10_000.0
    if market_id == "moneyline":
        line_value = 0.0
    elif market_id == "game-total":
        if line is None:
            line_value = -10_000.0
        elif side == "OVER":
            line_value = -line
        else:
            line_value = line
    else:
        line_value = line if line is not None else -10_000.0
    return line_value, price_value, str(row.get("book") or "")


def best_verified_book(
    observations: Iterable[Mapping[str, Any]],
    *,
    game_id: str,
    market_id: str,
    side: str,
) -> dict[str, Any]:
    target_side = str(side).upper()
    rows = [
        dict(row)
        for row in observations
        if str(row.get("game_id")) == str(game_id)
        and str(row.get("market_id")) == str(market_id)
        and str(row.get("side") or "").upper() == target_side
    ]
    if not rows:
        return {
            "ready": False,
            "status": "No verified current book",
            "book": None,
            "price": None,
            "line": None,
            "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        }
    best = max(rows, key=lambda row: _value_key(row, str(market_id), target_side))
    return {
        "ready": True,
        "status": "VERIFIED",
        "book": best.get("book"),
        "price": best.get("price"),
        "line": best.get("line"),
        "updated_at": best.get("updated_at"),
        "age_seconds": best.get("age_seconds"),
        "provider": best.get("provider"),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


def line_movement(observation: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(observation or {})
    if row.get("verified") is not True:
        return {"ready": False, "reason": "UNVERIFIED_OBSERVATION"}
    opening = _finite(row.get("opening_line"))
    current = _finite(row.get("line"))
    opening_at = _utc(row.get("opening_updated_at"))
    current_at = _utc(row.get("updated_at"))
    if opening is None or current is None or opening_at is None or current_at is None:
        return {"ready": False, "reason": "OPENING_EVIDENCE_UNAVAILABLE"}
    return {
        "ready": True,
        "opening_line": opening,
        "current_line": current,
        "delta": round(current - opening, 6),
    }


__all__ = [
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "best_verified_book",
    "line_movement",
    "normalize_market_observations",
]
