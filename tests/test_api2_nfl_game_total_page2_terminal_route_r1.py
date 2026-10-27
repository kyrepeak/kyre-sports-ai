from pathlib import Path


TERMINAL = Path("streamlit_memory_lazy_router_universal_runtime_v5_nfl_moneyline_page1_live_route_restore_r1.py")


def test_terminal_owner_routes_nfl_game_total_directly_through_fresh_canonical_loader() -> None:
    source = TERMINAL.read_text(encoding="utf-8")
    branch = 'if route.sport_id == "nfl" and route.market_id == "game-total":'
    direct = 'return canonical_loader.resolve_destination(route)'
    delegated = 'return prior.resolve_destination(route)'

    assert branch in source
    assert direct in source
    assert source.index(branch) < source.index(delegated)
    assert source.index(direct) < source.index(delegated)


def test_terminal_owner_preserves_nfl_moneyline_override() -> None:
    source = TERMINAL.read_text(encoding="utf-8")
    assert 'if route.sport_id == "nfl" and route.market_id == "moneyline":' in source
    assert 'nfl_moneyline_hub_v20' in source
