"""CFB Game Total Page 1 V2 Step 4 — exact-event side-market repair.

The frozen Step-4 market card already owns verified official-event -> FanDuel
provider-event identity. The prior completeness layer reused that identity but
read FanDuel's sport landing surface, which is sufficient for the game total but
not a reliable source for side markets. This additive no-thaw repair keeps the
same verified provider_game_id and reads FanDuel's exact event page before
selecting canonical open pregame Spread and Moneyline markets.

No team-name or fuzzy matching is introduced. Sportsbook values remain context
only and carry 0.0% projection influence. Any transport, identity, market, or
runner ambiguity fails closed to the frozen Step-4 fallback.
"""
from __future__ import annotations

import math
from threading import RLock
from typing import Any, Callable, Mapping

import streamlit as st

import cfb_game_total_page1_v2_step4_side_market_completeness_v1 as frozen_side

MODEL_VERSION = "CFB GAME TOTAL PAGE1 V2 STEP4 • EXACT EVENT SIDE MARKET REPAIR V1"
SPORTSBOOK = "FanDuel"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 1
IDENTITY_METHOD = "Kyre verified official event -> exact FanDuel provider_game_id -> event page"
_INSTALL_ATTR = "_cfb_step4_event_page_side_market_repair_installed"
_LOCK = RLock()
_FROZEN_FALLBACK = frozen_side.enrich_verified_side_market
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
    "verified_side_market_status",
    "verified_side_market_reason",
)


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        out: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("_attachment_key", str(key))
                out.append(row)
        return out
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _market_name(market: Mapping[str, Any]) -> str:
    return _clean(market.get("marketName") or market.get("name") or market.get("displayName"))


def _market_type(market: Mapping[str, Any]) -> str:
    return _clean(market.get("marketType") or market.get("type")).upper()


def _market_id(market: Mapping[str, Any]) -> str:
    return _clean(market.get("marketId") or market.get("_attachment_key"))


def _market_event_id(market: Mapping[str, Any]) -> str:
    return _clean(market.get("eventId") or market.get("eventID") or market.get("event_id"))


def _open_pregame(market: Mapping[str, Any]) -> bool:
    status = _clean(market.get("marketStatus") or market.get("status")).upper()
    return status == "OPEN" and market.get("inPlay") is not True and market.get("isLive") is not True


def _market_kind(market: Mapping[str, Any]) -> str:
    name = _market_name(market).casefold()
    kind = _market_type(market)
    if name == "moneyline" or kind == "MONEY_LINE":
        return "moneyline"
    if name in {"spread", "point spread"} or kind in {"SPREAD", "POINT_SPREAD"}:
        return "spread"
    return ""


def _priority(market: Mapping[str, Any]) -> int:
    try:
        return int(market.get("sortPriority") or 10_000)
    except (TypeError, ValueError):
        return 10_000


def _canonical_market(candidates: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    if not candidates:
        return None
    if kind == "spread":
        candidates.sort(
            key=lambda row: (
                0 if _market_name(row).casefold() == "spread" else 1,
                _priority(row),
                _market_id(row),
            )
        )
    else:
        candidates.sort(key=lambda row: (_priority(row), _market_id(row)))
    return candidates[0]


def _runner_role(runner: Mapping[str, Any]) -> str:
    side = _clean(runner.get("side")).upper()
    if side in {"AWAY", "HOME"}:
        return side
    result = runner.get("result") if isinstance(runner.get("result"), Mapping) else {}
    side = _clean(result.get("type")).upper()
    return side if side in {"AWAY", "HOME"} else ""


def _runner_active(runner: Mapping[str, Any]) -> bool:
    return _clean(runner.get("runnerStatus") or runner.get("status")).upper() in {"", "ACTIVE"}


def _two_sides(market: Mapping[str, Any]) -> dict[str, Mapping[str, Any]] | None:
    sides: dict[str, Mapping[str, Any]] = {}
    for runner in _rows(market.get("runners") or market.get("selections")):
        if not _runner_active(runner):
            continue
        role = _runner_role(runner)
        if role not in {"AWAY", "HOME"}:
            continue
        if role in sides:
            return None
        sides[role] = runner
    return sides if set(sides) == {"AWAY", "HOME"} else None


def _american(runner: Mapping[str, Any]) -> int | None:
    candidates: list[Any] = [runner.get("americanOdds"), runner.get("american_odds")]
    win = runner.get("winRunnerOdds") if isinstance(runner.get("winRunnerOdds"), Mapping) else {}
    display = win.get("americanDisplayOdds") if isinstance(win.get("americanDisplayOdds"), Mapping) else {}
    candidates.extend(
        (
            display.get("americanOddsInt"),
            display.get("americanOdds"),
            win.get("americanOddsInt"),
            win.get("americanOdds"),
        )
    )
    for raw in candidates:
        number = _finite(raw)
        if number is None or number == 0 or abs(number) < 100 or abs(number) > 100_000:
            continue
        return int(round(number))
    return None


def parse_event_page_side_markets(
    payload: Mapping[str, Any],
    provider_game_id: str,
) -> dict[str, Any] | None:
    """Parse canonical exact-event FanDuel Spread and Moneyline or fail closed."""
    provider_id = _clean(provider_game_id)
    attachments = payload.get("attachments") if isinstance(payload, Mapping) else None
    if not provider_id or not isinstance(attachments, Mapping):
        return None

    moneylines: list[dict[str, Any]] = []
    spreads: list[dict[str, Any]] = []
    for market in _rows(attachments.get("markets")):
        if not _open_pregame(market):
            continue
        market_event_id = _market_event_id(market)
        # The exact event-page request itself scopes identity. A missing market-
        # level eventId is therefore valid; a present conflicting ID is not.
        if market_event_id and market_event_id != provider_id:
            continue
        kind = _market_kind(market)
        if kind == "moneyline":
            moneylines.append(market)
        elif kind == "spread":
            spreads.append(market)

    moneyline = _canonical_market(moneylines, "moneyline")
    spread = _canonical_market(spreads, "spread")
    if moneyline is None or spread is None:
        return None

    money_sides = _two_sides(moneyline)
    spread_sides = _two_sides(spread)
    if money_sides is None or spread_sides is None:
        return None

    away_ml = _american(money_sides["AWAY"])
    home_ml = _american(money_sides["HOME"])
    away_spread = _finite(spread_sides["AWAY"].get("handicap"))
    home_spread = _finite(spread_sides["HOME"].get("handicap"))
    if None in {away_ml, home_ml, away_spread, home_spread}:
        return None
    assert away_spread is not None and home_spread is not None
    if abs(away_spread) > 100 or abs(home_spread) > 100:
        return None
    if not math.isclose(away_spread + home_spread, 0.0, abs_tol=1e-9):
        return None

    return {
        "away_spread": away_spread,
        "home_spread": home_spread,
        "away_spread_price": _american(spread_sides["AWAY"]),
        "home_spread_price": _american(spread_sides["HOME"]),
        "away_moneyline": away_ml,
        "home_moneyline": home_ml,
        "provider_game_id": provider_id,
    }


@st.cache_data(ttl=45, show_spinner=False)
def _load_exact_event_page(provider_game_id: str) -> dict[str, Any]:
    # This transport is generic despite its historical NFL module location and
    # requests FanDuel's exact /sbapi/event-page using only the provider event ID.
    from sports_api.collectors.nfl_fanduel_passing_yards import fetch_fanduel_event_page

    payload = fetch_fanduel_event_page(_clean(provider_game_id), timeout=12.0)
    if not isinstance(payload, dict):
        raise RuntimeError("FanDuel event page returned a non-object payload")
    return payload


def _official_event_id(game: Mapping[str, Any]) -> str:
    for key in ("market_official_game_id", "espn_event_id", "event_id", "game_id", "id"):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _identity_ready(game: Mapping[str, Any]) -> bool:
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
    event_page_loader: Callable[[str], Mapping[str, Any]] | None = None,
    fallback_enricher: Callable[[Mapping[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prefer exact-event FanDuel side markets, then frozen fail-closed fallback."""
    source = dict(display_game or {})
    fallback = fallback_enricher or _FROZEN_FALLBACK

    if _identity_ready(source):
        provider_id = _clean(source.get("market_provider_game_id"))
        try:
            payload = (event_page_loader or _load_exact_event_page)(provider_id)
            parsed = parse_event_page_side_markets(payload, provider_id)
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
                    "verified_side_market_reason": "exact FanDuel event page verified",
                }
            )
            return out

    return fallback(source)


def install_event_page_side_market_repair() -> bool:
    """Patch only the frozen CFB Step-4 side-market enrichment callable."""
    with _LOCK:
        current = frozen_side.enrich_verified_side_market
        if current is enrich_verified_side_market or getattr(current, _INSTALL_ATTR, False):
            return True
        setattr(enrich_verified_side_market, _INSTALL_ATTR, True)
        frozen_side.enrich_verified_side_market = enrich_verified_side_market
        return True


__all__ = [
    "IDENTITY_METHOD",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "enrich_verified_side_market",
    "install_event_page_side_market_repair",
    "parse_event_page_side_markets",
]
