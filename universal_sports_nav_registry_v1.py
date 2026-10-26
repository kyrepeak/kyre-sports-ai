"""Universal Sports Navigation V1 live-route registry.

Data-only contract. This module owns canonical sport/market identities and their
legacy compatibility metadata. It imports no sports providers or renderers.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketRoute:
    id: str
    label: str
    legacy_market: str
    legacy_market_key: str
    page_params: tuple[str, ...] = ()
    live: bool = True
    legacy_flags: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class SportRoute:
    id: str
    label: str
    icon: str
    legacy_sport: str
    default_market_id: str
    markets: tuple[MarketRoute, ...]


DEFAULT_SPORT_ID = "mlb"


def _market(
    id: str,
    label: str,
    legacy_market: str,
    legacy_key: str,
    *,
    page_params: tuple[str, ...] = ("date",),
    flags: tuple[tuple[str, object], ...] = (),
) -> MarketRoute:
    return MarketRoute(
        id=id,
        label=label,
        legacy_market=legacy_market,
        legacy_market_key=legacy_key,
        page_params=page_params,
        live=True,
        legacy_flags=flags,
    )


_NFL_KEY = "ks_nfl_market_touch"
_CFB_KEY = "ks_cfb_market_touch"
_NBA_KEY = "ks_nba_market_touch"
_MLB_KEY = "ks_mlb_market_touch"
_WNBA_KEY = "ks_wnba_market_touch"
_MLB_NORMAL = (("ks_mlb_live_odds_route", False),)

SPORTS: tuple[SportRoute, ...] = (
    SportRoute(
        id="nfl", label="NFL", icon="🏈", legacy_sport="NFL", default_market_id="daily-picks",
        markets=(
            _market("slate", "Slate", "Slate", _NFL_KEY),
            _market("moneyline", "Moneyline", "Moneyline", _NFL_KEY),
            _market("spread", "Spread", "Spread", _NFL_KEY),
            _market("game-total", "Game Total", "Game Total", _NFL_KEY, page_params=("date", "game_id")),
            _market("passing-yards", "Passing Yards", "Passing Yards", _NFL_KEY, page_params=("date", "game_id", "player_id")),
            _market("rushing-yards", "Rushing Yards", "Rushing Yards", _NFL_KEY, page_params=("date", "game_id", "player_id")),
            _market("receiving-yards", "Receiving Yards", "Receiving Yards", _NFL_KEY, page_params=("date", "game_id", "player_id")),
            _market("receptions", "Receptions", "Receptions", _NFL_KEY, page_params=("date", "game_id", "player_id")),
            _market("passing-tds", "Passing TDs", "Passing TDs", _NFL_KEY, page_params=("date", "game_id", "player_id")),
            _market("anytime-td", "Anytime TD", "Anytime TD", _NFL_KEY, page_params=("date", "game_id", "player_id")),
            _market("daily-picks", "Daily Picks", "Daily Picks", _NFL_KEY),
        ),
    ),
    SportRoute(
        id="cfb", label="CFB", icon="🏟️", legacy_sport="College Football", default_market_id="moneyline",
        markets=(
            _market("moneyline", "Moneyline", "Moneyline", _CFB_KEY),
            _market("over-under", "Over/Under", "Over/Under", _CFB_KEY),
            _market("game-total", "Game Total", "Game Total", _CFB_KEY, page_params=("date", "game_id")),
            _market("top-picks", "Top Picks", "Top Picks", _CFB_KEY),
            _market("player-props", "Player Props", "Player Props", _CFB_KEY, page_params=("date", "game_id", "player_id", "prop")),
        ),
    ),
    SportRoute(
        id="nba", label="NBA", icon="🏀", legacy_sport="NBA", default_market_id="spread",
        markets=(
            _market("spread", "Spread", "Spread", _NBA_KEY, page_params=("date", "game_id")),
            _market("pra", "PRA", "PRA", _NBA_KEY, page_params=("date", "game_id", "player_id")),
        ),
    ),
    SportRoute(
        id="mlb", label="MLB", icon="⚾", legacy_sport="MLB", default_market_id="slate",
        markets=(
            _market("slate", "Slate", "Slate", _MLB_KEY, flags=_MLB_NORMAL),
            _market("one-plus-hit", "1+ Hit", "1+ Hit", _MLB_KEY, page_params=("date", "player_id"), flags=_MLB_NORMAL),
            _market("home-run", "Home Run", "Home Run", _MLB_KEY, page_params=("date", "player_id"), flags=_MLB_NORMAL),
            _market("hits-runs-rbis", "Hits + Runs + RBIs", "Hits + Runs + RBIs", _MLB_KEY, page_params=("date", "player_id"), flags=_MLB_NORMAL),
            _market("pitcher-strikeouts", "Pitcher Strikeouts", "Pitcher Strikeouts", _MLB_KEY, page_params=("date", "player_id"), flags=_MLB_NORMAL),
            _market("matchup-explorer", "Matchup Explorer", "Matchup Explorer", _MLB_KEY, page_params=("date", "game_id"), flags=_MLB_NORMAL),
            _market("daily-game-picks", "Daily Game Picks", "Daily Game Picks", _MLB_KEY, flags=_MLB_NORMAL),
            _market("moneyline", "Moneyline", "Moneyline", _MLB_KEY, page_params=("date", "game_id"), flags=_MLB_NORMAL),
            _market("run-line", "Run Line", "Run Line", _MLB_KEY, page_params=("date", "game_id"), flags=_MLB_NORMAL),
            _market("game-total", "Game Total", "Game Total", _MLB_KEY, page_params=("date", "game_id"), flags=_MLB_NORMAL),
            _market("live-game", "Live Game", "Live Game", _MLB_KEY, page_params=("date", "game_id"), flags=_MLB_NORMAL),
            _market("live-odds", "Live Odds", "MLB Live Odds", _MLB_KEY, page_params=("date", "game_id"), flags=(("ks_mlb_live_odds_route", True),)),
        ),
    ),
    SportRoute(
        id="wnba", label="WNBA", icon="🏀", legacy_sport="WNBA", default_market_id="pra",
        markets=(
            _market("points", "Points", "Points", _WNBA_KEY, page_params=("date", "game_id", "player_id")),
            _market("rebounds", "Rebounds", "Rebounds", _WNBA_KEY, page_params=("date", "game_id", "player_id")),
            _market("assists", "Assists", "Assists", _WNBA_KEY, page_params=("date", "game_id", "player_id")),
            _market("rebounds-assists", "Rebounds + Assists", "Rebounds + Assists", _WNBA_KEY, page_params=("date", "game_id", "player_id")),
            _market("pra", "PRA", "PRA", _WNBA_KEY, page_params=("date", "game_id", "player_id")),
            _market("spread", "Spread", "Spread", _WNBA_KEY, page_params=("date", "game_id")),
            _market("moneyline", "Moneyline", "Moneyline", _WNBA_KEY, page_params=("date", "game_id")),
            _market("game-total", "Game Total", "Game Total", _WNBA_KEY, page_params=("date", "game_id")),
            _market("daily-picks", "Daily Picks", "Daily Picks", _WNBA_KEY),
        ),
    ),
)

_SPORT_BY_ID = {sport.id: sport for sport in SPORTS}


def get_sport(sport_id: str) -> SportRoute | None:
    return _SPORT_BY_ID.get(str(sport_id or "").strip().lower())


def get_market(sport_id: str, market_id: str) -> MarketRoute | None:
    sport = get_sport(sport_id)
    if sport is None:
        return None
    wanted = str(market_id or "").strip().lower()
    return next((market for market in sport.markets if market.id == wanted and market.live), None)


def visible_sports() -> tuple[SportRoute, ...]:
    return tuple(sport for sport in SPORTS if any(m.live for m in sport.markets))


def validate_registry() -> tuple[str, ...]:
    errors: list[str] = []
    sport_ids = [sport.id for sport in SPORTS]
    if len(sport_ids) != len(set(sport_ids)):
        errors.append("duplicate sport ids")
    if DEFAULT_SPORT_ID not in _SPORT_BY_ID:
        errors.append("default sport missing")
    for sport in SPORTS:
        ids = [market.id for market in sport.markets]
        if len(ids) != len(set(ids)):
            errors.append(f"{sport.id}: duplicate market ids")
        live = [market for market in sport.markets if market.live]
        if not live:
            errors.append(f"{sport.id}: no live markets")
        default = get_market(sport.id, sport.default_market_id)
        if default is None:
            errors.append(f"{sport.id}: default market is not live")
        legacy = [(market.legacy_market, market.legacy_market_key) for market in live]
        if len(legacy) != len(set(legacy)):
            errors.append(f"{sport.id}: duplicate legacy identities")
        if any(not market.legacy_market or not market.legacy_market_key for market in live):
            errors.append(f"{sport.id}: incomplete compatibility target")
    return tuple(errors)


__all__ = [
    "DEFAULT_SPORT_ID", "MarketRoute", "SPORTS", "SportRoute", "get_market",
    "get_sport", "validate_registry", "visible_sports",
]
