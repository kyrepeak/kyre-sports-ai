"""CFB Player Props V1 — normalized verified sportsbook observations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Mapping, Sequence

from cfb_player_props_identity_v1 import CanonicalPlayerIdentity, resolve_player_identity

SUPPORTED_MARKETS = frozenset({
    "passing_yards", "rushing_yards", "receiving_yards",
    "receiving_receptions", "passing_touchdowns", "touchdowns",
})


@dataclass(frozen=True)
class PropObservation:
    official_game_id: str
    canonical_player_id: str
    player_name: str
    official_team_id: str
    market_key: str
    sportsbook: str
    side: str
    line: float
    price: int | None
    observed_at_utc: str
    provider: str
    provider_event_id: str
    provider_player_id: str
    provider_market_id: str
    identity_verified: bool = True


def _text(value: Any) -> str:
    return str(value or "").strip()


def canonical_market_key(stat_id: str) -> str | None:
    key = _text(stat_id).lower().replace("-", "_").replace(" ", "_")
    return key if key in SUPPORTED_MARKETS else None


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _timestamp(value: Any) -> tuple[str, float] | None:
    text = _text(value)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    utc = dt.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z"), utc.timestamp()


def normalize_prop_observation(
    raw: Mapping[str, Any], identity_index: Mapping[str, CanonicalPlayerIdentity]
) -> PropObservation | None:
    game_id = _text(raw.get("official_game_id"))
    market = canonical_market_key(_text(raw.get("stat_id") or raw.get("market_key")))
    player = resolve_player_identity(raw, identity_index)
    book = _text(raw.get("sportsbook") or raw.get("book"))
    side = _text(raw.get("side")).lower()
    line = _finite(raw.get("line"))
    stamp = _timestamp(raw.get("observed_at_utc") or raw.get("updated_at"))
    if not game_id or market is None or player is None or not book or side not in {"over", "under"}:
        return None
    if line is None or line < 0 or stamp is None:
        return None
    price = raw.get("price", raw.get("odds"))
    if price in (None, ""):
        american = None
    else:
        try:
            american = int(round(float(price)))
        except (TypeError, ValueError):
            return None
        if not -10000 <= american <= 10000:
            return None
    observed_at, _ = stamp
    return PropObservation(
        game_id, player.official_player_id, player.canonical_name, player.official_team_id,
        market, book, side, line, american, observed_at,
        _text(raw.get("provider")), _text(raw.get("provider_event_id") or raw.get("event_id")),
        _text(raw.get("provider_player_id") or raw.get("player_id")),
        _text(raw.get("provider_market_id") or raw.get("odd_id")), True,
    )


def merge_prop_observations(*sources: Sequence[PropObservation | None]) -> list[PropObservation]:
    chosen: dict[tuple[str, str, str, str, str], PropObservation] = {}
    for source in sources:
        for row in source:
            if row is None or row.identity_verified is not True:
                continue
            key = (row.official_game_id, row.canonical_player_id, row.market_key, row.sportsbook, row.side)
            prior = chosen.get(key)
            if prior is None or _timestamp(row.observed_at_utc)[1] > _timestamp(prior.observed_at_utc)[1]:
                chosen[key] = row
    return sorted(chosen.values(), key=lambda r: (r.official_game_id, r.canonical_player_id, r.market_key, r.sportsbook, r.side))


__all__ = ["PropObservation", "SUPPORTED_MARKETS", "canonical_market_key", "merge_prop_observations", "normalize_prop_observation"]
