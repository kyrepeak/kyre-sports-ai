"""Isolated NBA PRA navigation overlay; leaves the shared registry file untouched."""
from __future__ import annotations
import universal_sports_nav_registry_v1 as registry

MODEL_VERSION = "API2 NBA PRA NAV OVERLAY V1"


def activate() -> None:
    nba = registry.get_sport("nba")
    if nba is None or registry.get_market("nba", "pra") is not None:
        return
    pra = registry.MarketRoute(
        id="pra", label="PRA", legacy_market="PRA",
        legacy_market_key="ks_nba_market_touch",
        page_params=("date", "game_id", "player_id"), live=True,
    )
    updated = registry.SportRoute(
        id=nba.id, label=nba.label, icon=nba.icon,
        legacy_sport=nba.legacy_sport, default_market_id=nba.default_market_id,
        markets=nba.markets + (pra,),
    )
    registry.SPORTS = tuple(updated if sport.id == "nba" else sport for sport in registry.SPORTS)
    registry._SPORT_BY_ID["nba"] = updated
