from __future__ import annotations

import universal_runtime_v5_loader_nfl_daily_picks_command_v3 as loader
import universal_sports_nav_registry_v1 as registry
from universal_runtime_v5_state import RuntimeRoute


def test_cfb_player_props_is_additive_canonical_route():
    market = registry.get_market("cfb", "player-props")
    assert market is not None
    assert market.label == "Player Props"
    assert market.legacy_market == "Player Props"
    assert market.page_params == ("date", "game_id")
    cfb = registry.get_sport("cfb")
    assert cfb is not None
    assert tuple(item.id for item in cfb.markets if item.live) == (
        "moneyline", "over-under", "game-total", "top-picks", "player-props"
    )
    assert cfb.default_market_id == "moneyline"


def test_cfb_player_props_gets_lazy_runtime_v3_adapter_without_importing_page():
    route = RuntimeRoute("cfb", "player-props", {"date": "2026-10-24"}, 7, "tap")
    adapter = loader.resolve_destination(route)
    assert adapter.route_key == ("cfb", "player-props")
    assert adapter.source_version == "CFB_PLAYER_PROPS_RUNTIME_V3"
    assert adapter.ttl_ms == 30_000


def test_other_routes_delegate_unchanged(monkeypatch):
    sentinel = object()
    seen = []

    def fake_resolve(route):
        seen.append(route)
        return sentinel

    monkeypatch.setattr(loader.upstream, "resolve_destination", fake_resolve)
    route = RuntimeRoute("cfb", "moneyline", {}, 1, "tap")
    assert loader.resolve_destination(route) is sentinel
    assert seen == [route]
