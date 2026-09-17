"""CFB Game Total runtime display adapter V2 — exact market identity overlay.

V2 is additive over frozen V1. Deterministic team/environment/history evidence
continues to come from V1. Sportsbook market fields may be copied onto the
DISPLAY game only when selected date + away team + home team all match.
Nothing in this module feeds sportsbook data into projection/model math.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

import cfb_game_total_runtime_display_v1 as prior

MODEL_VERSION = "CFB GAME TOTAL RUNTIME DISPLAY V2 • EXACT MARKET IDENTITY"
FROZEN_RUNTIME_DISPLAY = "cfb_game_total_runtime_display_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_MARKET_TOTAL_KEYS = (
    "total",
    "market_total",
    "total_line",
    "over_under",
    "ou",
)
_MARKET_METADATA_KEYS = (
    "sportsbook",
    "bookmaker",
    "provider",
    "odds_source",
    "market_source",
    "market_updated_at",
    "odds_updated_at",
)
_MARKET_CONTAINER_KEYS = ("odds", "market")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _day_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _clean(value)
    if not text:
        return ""
    # ISO timestamps and ordinary YYYY-MM-DD strings both reduce safely here.
    return text[:10]


def _team_key(value: Any) -> str:
    try:
        return prior.frozen_runtime._key(value)
    except Exception:
        return "".join(ch for ch in _clean(value).lower() if ch.isalnum())


def _event_day(game: Mapping[str, Any], selected_day: Any = None) -> str:
    if selected_day not in (None, ""):
        return _day_text(selected_day)
    for key in ("game_date", "date", "commence_time", "start_time", "game_time"):
        day = _day_text(game.get(key))
        if day:
            return day
    return ""


def _same_event(
    base_game: Mapping[str, Any],
    market_game: Mapping[str, Any],
    selected_day: Any,
) -> bool:
    selected = _day_text(selected_day)
    base_day = _event_day(base_game, selected_day)
    market_day = _event_day(market_game)
    if not selected or base_day != selected or market_day != selected:
        return False

    base_away = _team_key(base_game.get("away_team"))
    base_home = _team_key(base_game.get("home_team"))
    market_away = _team_key(market_game.get("away_team"))
    market_home = _team_key(market_game.get("home_team"))
    return bool(
        base_away
        and base_home
        and market_away
        and market_home
        and base_away == market_away
        and base_home == market_home
    )


def _coerce_total(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 < number < 200.0 else None


def _extract_total(game: Mapping[str, Any]) -> tuple[str, float] | None:
    for key in _MARKET_TOTAL_KEYS:
        value = _coerce_total(game.get(key))
        if value is not None:
            return key, value
    for container_key in _MARKET_CONTAINER_KEYS:
        nested = game.get(container_key)
        if not isinstance(nested, Mapping):
            continue
        for key in _MARKET_TOTAL_KEYS:
            value = _coerce_total(nested.get(key))
            if value is not None:
                return key, value
    return None


def overlay_verified_market_fields(
    base_game: Mapping[str, Any],
    market_game: Mapping[str, Any] | None,
    selected_day: Any,
) -> dict[str, Any]:
    """Copy market-only fields after a strict date/away/home identity match.

    If identity is incomplete/mismatched or no valid total exists, fail closed
    and return an unchanged copy of ``base_game``.
    """
    out = dict(base_game)
    if not isinstance(market_game, Mapping):
        return out
    if not _same_event(base_game, market_game, selected_day):
        return out

    total_hit = _extract_total(market_game)
    if total_hit is None:
        return out

    total_key, total_value = total_hit
    # Canonical display key guarantees V159's frozen market reader sees the line.
    out["market_total"] = total_value
    if total_key in market_game:
        out[total_key] = total_value

    for key in _MARKET_METADATA_KEYS:
        value = market_game.get(key)
        if value not in (None, "", [], {}):
            out[key] = dict(value) if isinstance(value, Mapping) else value

    for key in _MARKET_CONTAINER_KEYS:
        value = market_game.get(key)
        if isinstance(value, Mapping):
            out[key] = dict(value)
    return out


def _verified_market_candidate(game: Mapping[str, Any]) -> dict[str, Any]:
    """Return an already-attached market candidate, if the schedule row has one.

    Step 5 owns external provider/freshness hookup. V2 deliberately does not
    invent or fetch odds. This hook lets a verified upstream schedule market be
    overlaid now while preserving a single exact-identity gate for live data.
    """
    return dict(game) if _extract_total(game) is not None else {}


def reconcile_display_bundle(
    game: Mapping[str, Any],
    selected_day: Any,
    frozen_away: Mapping[str, Any],
    frozen_home: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Run V1 evidence reconciliation, then apply display-only market overlay."""
    display_game, away, home, diag = prior.reconcile_display_bundle(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )
    display_game = dict(display_game or game)
    away = dict(away or frozen_away)
    home = dict(home or frozen_home)
    diag = dict(diag or {})

    market_game = _verified_market_candidate(game)
    merged = overlay_verified_market_fields(display_game, market_game, selected_day)
    market_total = _extract_total(merged)

    diag["game_total_runtime_display_version"] = MODEL_VERSION
    diag["market_identity_gate"] = "date+away+home"
    diag["market_overlay_applied"] = bool(market_total and market_game)
    diag["sportsbook_projection_influence"] = SPORTSBOOK_PROJECTION_INFLUENCE
    return merged, away, home, diag


__all__ = [
    "MODEL_VERSION",
    "FROZEN_RUNTIME_DISPLAY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_PROJECTION",
    "overlay_verified_market_fields",
    "reconcile_display_bundle",
]
