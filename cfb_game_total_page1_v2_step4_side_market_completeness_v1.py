"""CFB Game Total Page 1 V2 Step 4 — exact FanDuel side-market completeness.

The frozen Step-4 page already receives an identity-verified FanDuel total from
Kyre Sports API. That row includes FanDuel's provider_game_id after the official
ESPN event ID has been verified server-side. This additive layer reuses that
exact provider event ID to read the corresponding OPEN pregame FanDuel Spread
and Moneyline markets. No fuzzy/team-name matching is used.

If the direct FanDuel side markets cannot be proven, the prior exact-event side
market enricher remains the fail-closed fallback. Sportsbook data is comparison
context only and carries 0.0% projection weight.
"""
from __future__ import annotations

import math
from threading import RLock
from typing import Any, Callable, Mapping

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v160 as render_owner
import streamlit_memory_lazy_router_v181 as route_owner
from cfb_game_total_page1_step4_side_market_v1 import (
    enrich_verified_side_market as _legacy_side_market_enricher,
)

MODEL_VERSION = "CFB GAME TOTAL PAGE1 V2 STEP4 • FANDUEL SIDE MARKET COMPLETENESS V1"
TARGET_PAGE = "cfb_game_total_clean_page_v38"
SPORTSBOOK = "FanDuel"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 1
IDENTITY_METHOD = "Kyre verified official event -> exact FanDuel provider_game_id"

_INSTALL_ATTR = "_cfb_step4_side_market_completeness_installed"
_LOCK = RLock()
_VERIFIED_KEYS = (
    "verified_away_spread",
    "verified_home_spread",
    "verified_away_spread_price",
    "verified_home_spread_price",
    "verified_away_moneyline",
    "verified_home_moneyline",
    "verified_side_market_provider",
    "verified_side_market_event_id",
    "verified_side_market_provider_event_id",
    "verified_side_market_projection_weight",
    "verified_side_market_identity_method",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(item) for item in value.values() if isinstance(item, Mapping)]
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _event_id(market: Mapping[str, Any]) -> str:
    return _clean(
        market.get("eventId")
        or market.get("eventID")
        or market.get("event_id")
    )


def _market_name(market: Mapping[str, Any]) -> str:
    return _clean(
        market.get("marketName")
        or market.get("name")
        or market.get("displayName")
    )


def _market_type(market: Mapping[str, Any]) -> str:
    return _clean(market.get("marketType") or market.get("type")).upper()


def _open_pregame(market: Mapping[str, Any]) -> bool:
    return (
        _clean(market.get("marketStatus") or market.get("status")).upper() == "OPEN"
        and market.get("inPlay") is not True
        and market.get("isLive") is not True
    )


def _runner_side(runner: Mapping[str, Any]) -> str:
    side = _clean(runner.get("side")).upper()
    if side in {"AWAY", "HOME"}:
        return side
    result = runner.get("result") if isinstance(runner.get("result"), Mapping) else {}
    side = _clean(result.get("type")).upper()
    return side if side in {"AWAY", "HOME"} else ""


def _runner_active(runner: Mapping[str, Any]) -> bool:
    return _clean(runner.get("runnerStatus") or runner.get("status")).upper() in {"", "ACTIVE"}


def _american(runner: Mapping[str, Any]) -> int | None:
    candidates: list[Any] = [runner.get("americanOdds"), runner.get("american_odds")]
    win = runner.get("winRunnerOdds") if isinstance(runner.get("winRunnerOdds"), Mapping) else {}
    display = win.get("americanDisplayOdds") if isinstance(win.get("americanDisplayOdds"), Mapping) else {}
    candidates.extend(
        [
            display.get("americanOddsInt"),
            display.get("americanOdds"),
            win.get("americanOddsInt"),
            win.get("americanOdds"),
        ]
    )
    for candidate in candidates:
        number = _finite(candidate)
        if number is None or number == 0 or abs(number) < 100 or abs(number) > 100000:
            continue
        return int(round(number))
    return None


def _two_sides(market: Mapping[str, Any]) -> dict[str, Mapping[str, Any]] | None:
    sides: dict[str, Mapping[str, Any]] = {}
    for runner in _rows(market.get("runners") or market.get("selections")):
        if not _runner_active(runner):
            continue
        side = _runner_side(runner)
        if side not in {"AWAY", "HOME"} or side in sides:
            continue
        sides[side] = runner
    return sides if set(sides) == {"AWAY", "HOME"} else None


def _market_kind(market: Mapping[str, Any]) -> str:
    name = _market_name(market).casefold()
    kind = _market_type(market)
    if name == "moneyline" or kind == "MONEY_LINE":
        return "moneyline"
    if name in {"spread", "point spread"} or kind in {"SPREAD", "POINT_SPREAD"}:
        return "spread"
    return ""


def parse_exact_fanduel_side_markets(
    payload: Mapping[str, Any],
    provider_game_id: str,
) -> dict[str, Any] | None:
    """Return one exact provider-event spread/moneyline pair or fail closed."""
    provider_id = _clean(provider_game_id)
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
    if not provider_id or not isinstance(attachments, Mapping):
        return None

    candidates = [
        market
        for market in _rows(attachments.get("markets"))
        if _event_id(market) == provider_id and _open_pregame(market)
    ]
    moneylines = [market for market in candidates if _market_kind(market) == "moneyline"]
    spreads = [market for market in candidates if _market_kind(market) == "spread"]
    if len(moneylines) != 1 or len(spreads) != 1:
        return None

    money_sides = _two_sides(moneylines[0])
    spread_sides = _two_sides(spreads[0])
    if money_sides is None or spread_sides is None:
        return None

    away_ml = _american(money_sides["AWAY"])
    home_ml = _american(money_sides["HOME"])
    away_spread = _finite(spread_sides["AWAY"].get("handicap"))
    home_spread = _finite(spread_sides["HOME"].get("handicap"))
    away_spread_price = _american(spread_sides["AWAY"])
    home_spread_price = _american(spread_sides["HOME"])
    if None in {away_ml, home_ml, away_spread, home_spread}:
        return None
    assert away_spread is not None and home_spread is not None
    if abs(away_spread) > 100 or abs(home_spread) > 100:
        return None
    if abs(away_spread + home_spread) > 1e-6:
        return None

    return {
        "away_spread": away_spread,
        "home_spread": home_spread,
        "away_spread_price": away_spread_price,
        "home_spread_price": home_spread_price,
        "away_moneyline": away_ml,
        "home_moneyline": home_ml,
        "provider_game_id": provider_id,
    }


@st.cache_data(ttl=45, show_spinner=False)
def _load_fanduel_page() -> dict[str, Any]:
    from sports_api.collectors.cfb_fanduel_direct import fetch_fanduel_ncaaf_page

    payload = fetch_fanduel_ncaaf_page(timeout=12.0)
    if not isinstance(payload, dict):
        raise RuntimeError("FanDuel NCAAF page returned a non-object payload")
    return payload


def _official_event_id(game: Mapping[str, Any]) -> str:
    for key in ("market_official_game_id", "espn_event_id", "event_id", "game_id", "id"):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _direct_identity_ready(game: Mapping[str, Any]) -> bool:
    if game.get("market_identity_verified") is not True:
        return False
    if _clean(game.get("market_sportsbook")).casefold() != SPORTSBOOK.casefold():
        return False
    if not _clean(game.get("market_provider_game_id")):
        return False
    try:
        if float(game.get("market_projection_weight")) != 0.0:
            return False
    except (TypeError, ValueError):
        return False
    if game.get("market_may_modify_projection") not in (None, False):
        return False
    return bool(_official_event_id(game))


def _clear_verified(out: dict[str, Any]) -> None:
    for key in _VERIFIED_KEYS:
        out.pop(key, None)


def enrich_verified_side_market(
    display_game: Mapping[str, Any],
    *,
    payload_loader: Callable[[], Mapping[str, Any]] | None = None,
    legacy_enricher: Callable[[Mapping[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prefer exact FanDuel provider-event side markets, then legacy exact-event fallback."""
    source = dict(display_game or {})
    fallback = legacy_enricher or _legacy_side_market_enricher

    if _direct_identity_ready(source):
        provider_id = _clean(source.get("market_provider_game_id"))
        try:
            payload = (payload_loader or _load_fanduel_page)()
            parsed = parse_exact_fanduel_side_markets(payload, provider_id)
        except Exception:
            parsed = None
        if parsed is not None:
            out = dict(source)
            _clear_verified(out)
            out.update(
                {
                    "verified_away_spread": parsed["away_spread"],
                    "verified_home_spread": parsed["home_spread"],
                    "verified_away_spread_price": parsed.get("away_spread_price"),
                    "verified_home_spread_price": parsed.get("home_spread_price"),
                    "verified_away_moneyline": parsed["away_moneyline"],
                    "verified_home_moneyline": parsed["home_moneyline"],
                    "verified_side_market_provider": SPORTSBOOK,
                    "verified_side_market_event_id": _official_event_id(source),
                    "verified_side_market_provider_event_id": provider_id,
                    "verified_side_market_projection_weight": 0.0,
                    "verified_side_market_identity_method": IDENTITY_METHOD,
                    "verified_side_market_status": "GREEN",
                    "verified_side_market_reason": "exact verified FanDuel provider event",
                }
            )
            return out

    return fallback(source)


def install_side_market_completeness() -> bool:
    """Install an idempotent post-purge V38 side-market ownership wrapper."""
    with _LOCK:
        current = render_owner._render_exact_game_total_surface
        if getattr(current, _INSTALL_ATTR, False):
            return True
        original = current

        def repaired_render_exact_game_total_surface(*args: Any, **kwargs: Any):
            if not route_owner._game_total_route_active():
                return original(*args, **kwargs)

            original_import = root._import

            def import_with_side_market_completeness(name: str):
                page = original_import(name)
                if str(name) == TARGET_PAGE:
                    side_market = getattr(page, "side_market", None)
                    if side_market is None or not hasattr(side_market, "enrich_verified_side_market"):
                        raise RuntimeError("Step-4 side-market module unavailable on V38")
                    side_market.enrich_verified_side_market = enrich_verified_side_market
                return page

            root._import = import_with_side_market_completeness
            try:
                return original(*args, **kwargs)
            finally:
                root._import = original_import

        setattr(repaired_render_exact_game_total_surface, _INSTALL_ATTR, True)
        setattr(
            repaired_render_exact_game_total_surface,
            "_cfb_step4_side_market_completeness_original",
            original,
        )
        render_owner._render_exact_game_total_surface = repaired_render_exact_game_total_surface
        return True


__all__ = [
    "IDENTITY_METHOD",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "enrich_verified_side_market",
    "install_side_market_completeness",
    "parse_exact_fanduel_side_markets",
]
