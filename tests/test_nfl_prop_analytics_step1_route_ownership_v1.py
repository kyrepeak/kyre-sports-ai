from pathlib import Path


def test_step1_route_owner_contract():
    router = Path("streamlit_memory_lazy_router_v240.py").read_text()
    hub = Path("nfl_prop_analytics_hub_v1.py").read_text()

    for token in (
        'FROZEN_ROUTER = "streamlit_memory_lazy_router_v239"',
        'PROP_ANALYTICS_MARKET = "Prop Analytics"',
        'PROP_ANALYTICS_HUB = "nfl_prop_analytics_hub_v1"',
        'MAY_MODIFY_PASSING_YARDS = False',
        'return prior.render_app()',
        'root.NFL_MARKETS = _prop_market_options()',
        'root._render_nfl = _render_nfl_v240',
    ):
        assert token in router, token

    for token in (
        'MARKET = "Prop Analytics"',
        'data-nfl-prop-analytics-route="v1"',
        'data-prop-analytics-owner="nfl_prop_analytics_hub_v1"',
        'data-prop-analytics-step="1"',
        'MAY_MODIFY_PASSING_YARDS = False',
        'MAY_MODIFY_EXISTING_NFL_MARKETS = False',
    ):
        assert token in hub, token


def test_step1_is_route_only_no_schedule_or_props_yet():
    router = Path("streamlit_memory_lazy_router_v240.py").read_text()
    hub = Path("nfl_prop_analytics_hub_v1.py").read_text()

    assert 'ROUTE_OWNERSHIP_ONLY = True' in router
    assert 'ROUTE_ONLY = True' in hub

    forbidden = (
        "requests.get(",
        "httpx.",
        "pandas.read_",
        "sportsbook",
        "projection",
        "player_prop",
    )
    lower = hub.lower()
    for token in forbidden:
        assert token.lower() not in lower, token


def test_app_boots_v240_and_keeps_v239_as_frozen_delegate():
    app = Path("app.py").read_text()
    router = Path("streamlit_memory_lazy_router_v240.py").read_text()

    assert (
        "from streamlit_memory_lazy_router_v240 "
        "import record_bootstrap_import_ms, render_app"
    ) in app
    assert "import streamlit_memory_lazy_router_v239 as prior" in router
