"""CFB Game Total Page 1 V2 Step 4 exact-event side-market context.

Presentation-only enrichment for spread and moneyline. It reuses the existing
ESPN exact-event market context reader, requires exact official event identity,
and never changes projection/model inputs. Generic nested odds are never trusted.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Mapping

MODEL_VERSION = "CFB GAME TOTAL PAGE1 V2 STEP4 • EXACT EVENT SIDE MARKET"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_SIDE_KEYS = (
    "verified_away_spread",
    "verified_home_spread",
    "verified_away_moneyline",
    "verified_home_moneyline",
    "verified_side_market_provider",
    "verified_side_market_event_id",
    "verified_side_market_projection_weight",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _game_id(display_game: Mapping[str, Any]) -> str:
    for key in ("event_id", "game_id", "id"):
        value = _clean(display_game.get(key))
        if value:
            return value
    return ""


def _game_date(display_game: Mapping[str, Any]) -> str:
    for key in ("game_date", "date", "start_date"):
        value = _clean(display_game.get(key))
        if value:
            return value[:10]
    return ""


def _default_loader(target_date: str):
    from cfb_top_picks_market_context_v1 import load_market_context

    return load_market_context(target_date)


def _clear_verified_side_fields(out: dict[str, Any]) -> None:
    for key in _SIDE_KEYS:
        out.pop(key, None)


def enrich_verified_side_market(
    display_game: Mapping[str, Any],
    *,
    loader: Callable[[str], tuple[Mapping[str, Mapping[str, Any]], Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Attach only exact-event spread/moneyline context or fail closed."""
    out = dict(display_game or {})
    _clear_verified_side_fields(out)
    out["verified_side_market_status"] = "UNAVAILABLE"

    event_id = _game_id(out)
    game_date = _game_date(out)
    if not event_id or not game_date:
        out["verified_side_market_reason"] = "official event identity unavailable"
        return out

    chosen_loader = loader or _default_loader
    try:
        markets, diagnostics = chosen_loader(game_date)
    except Exception as exc:
        out["verified_side_market_reason"] = f"side market load failed: {type(exc).__name__}"[:180]
        return out

    if not isinstance(markets, Mapping):
        out["verified_side_market_reason"] = "side market payload invalid"
        return out
    row = markets.get(event_id)
    if not isinstance(row, Mapping) or _clean(row.get("event_id")) != event_id:
        out["verified_side_market_reason"] = "no exact-event side market"
        return out
    if row.get("market_available") is not True:
        out["verified_side_market_reason"] = "exact-event side market unavailable"
        return out
    if _finite(row.get("projection_weight")) != 0.0:
        out["verified_side_market_reason"] = "side market projection firewall rejected"
        return out
    if row.get("may_modify_projection") not in (None, False):
        out["verified_side_market_reason"] = "side market projection firewall rejected"
        return out

    away_spread = _finite(row.get("away_spread"))
    home_spread = _finite(row.get("home_spread"))
    away_ml = _finite(row.get("away_moneyline"))
    home_ml = _finite(row.get("home_moneyline"))

    if away_spread is not None and abs(away_spread) <= 100:
        out["verified_away_spread"] = away_spread
    if home_spread is not None and abs(home_spread) <= 100:
        out["verified_home_spread"] = home_spread
    if away_ml is not None and abs(away_ml) >= 100:
        out["verified_away_moneyline"] = away_ml
    if home_ml is not None and abs(home_ml) >= 100:
        out["verified_home_moneyline"] = home_ml

    provider = _clean(row.get("provider")) or "ESPN market context"
    out["verified_side_market_provider"] = provider
    out["verified_side_market_event_id"] = event_id
    out["verified_side_market_projection_weight"] = 0.0
    out["verified_side_market_status"] = "GREEN"
    out["verified_side_market_reason"] = "exact official event_id match"
    if isinstance(diagnostics, Mapping):
        out["verified_side_market_diagnostics"] = {
            "status": diagnostics.get("status"),
            "date": diagnostics.get("date"),
            "projection_weight": diagnostics.get("projection_weight", 0.0),
        }
    return out


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "enrich_verified_side_market",
]
