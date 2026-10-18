"""Exact FanDuel PRA eligibility over API-owned WNBA market rows.

FanDuel owns customer-board eligibility and the threshold shown by the V2 PRA
product. Other books remain comparison context only. This module does not
calculate projections, probabilities, edges, ranks, or selections.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
import unicodedata
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class FanDuelPRAOffer:
    game_id: str
    player_key: str
    player_name: str
    line: float
    over_odds: int | None
    under_odds: int | None
    captured_at: str | None
    source_event_id: str | None
    evidence_state: str


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _odds(value: Any) -> int | None:
    number = _float(value)
    if number is None or not number.is_integer():
        return None
    integer = int(number)
    return integer if abs(integer) >= 100 else None


def _captured(row: dict[str, Any]) -> str | None:
    values = [
        row.get("captured_at"), row.get("market_captured_at_utc"),
        row.get("updated_at"), row.get("over_updated"), row.get("under_updated"),
    ]
    parsed: list[tuple[datetime, str]] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        try:
            stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            parsed.append((stamp.astimezone(timezone.utc), stamp.astimezone(timezone.utc).isoformat()))
        except ValueError:
            continue
    return max(parsed, key=lambda item: item[0])[1] if parsed else None


def _is_pra(row: dict[str, Any]) -> bool:
    value = _norm(row.get("market") or row.get("stat") or row.get("stat_id"))
    if not value:
        # Frozen grade_pra_markets() rows are already PRA-only and historically
        # do not carry a market/stat column.
        return True
    return value in {"pra", "points rebounds assists"}


def current_fanduel_pra_offers(
    market_rows: pd.DataFrame,
) -> dict[tuple[str, str], FanDuelPRAOffer]:
    """Return one current exact FanDuel PRA threshold per game/player identity."""
    if not isinstance(market_rows, pd.DataFrame) or market_rows.empty:
        return {}

    grouped: dict[tuple[str, str], list[tuple[datetime | None, FanDuelPRAOffer]]] = {}
    for row in market_rows.to_dict("records"):
        if _norm(row.get("book") or row.get("sportsbook")) != "fanduel":
            continue
        if str(row.get("freshness") or "").strip().upper() == "STALE":
            continue
        if not _is_pra(row):
            continue
        game_id = str(row.get("game_id") or "").strip()
        player_name = str(row.get("player") or row.get("player_name") or "").strip()
        player_key = _norm(row.get("player_key") or player_name)
        line = _float(row.get("line"))
        if not game_id or not player_key or not player_name or line is None or line < 0:
            continue
        captured = _captured(row)
        stamp = None
        if captured:
            try:
                stamp = datetime.fromisoformat(captured.replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                stamp = None
        offer = FanDuelPRAOffer(
            game_id=game_id,
            player_key=player_key,
            player_name=player_name,
            line=float(line),
            over_odds=_odds(row.get("over_odds")),
            under_odds=_odds(row.get("under_odds")),
            captured_at=captured,
            source_event_id=str(row.get("source_event_id") or "").strip() or None,
            evidence_state="FANDUEL_CURRENT",
        )
        grouped.setdefault((game_id, player_key), []).append((stamp, offer))

    result: dict[tuple[str, str], FanDuelPRAOffer] = {}
    for key, candidates in grouped.items():
        candidates.sort(key=lambda item: item[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        newest_stamp = candidates[0][0]
        newest = [offer for stamp, offer in candidates if stamp == newest_stamp]
        lines = {offer.line for offer in newest}
        # Same-timestamp line conflict is not resolvable without guessing.
        if len(lines) != 1:
            continue
        # Prefer the row with the most complete same-line price pair.
        newest.sort(
            key=lambda offer: (
                int(offer.over_odds is not None) + int(offer.under_odds is not None),
                offer.source_event_id or "",
            ),
            reverse=True,
        )
        result[key] = newest[0]
    return result


__all__ = ["FanDuelPRAOffer", "current_fanduel_pra_offers"]
