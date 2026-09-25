from pathlib import Path
from types import SimpleNamespace

import streamlit_memory_lazy_router_v239 as router


def test_app_activates_v239_entrypoint():
    app = Path("app.py").read_text(encoding="utf-8")
    assert (
        "from streamlit_memory_lazy_router_v239 import "
        "record_bootstrap_import_ms, render_app"
    ) in app
    assert (
        "from streamlit_memory_lazy_router_v238 import "
        "record_bootstrap_import_ms, render_app"
    ) not in app


def test_v239_source_never_uses_v187_global_mutation_path():
    source = Path("streamlit_memory_lazy_router_v239.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_v187" not in source
    assert 'root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nfl_",)' not in source
    assert "root._render_nfl =" not in source
    assert "route_guard._prime_passing_route_token_for_session()" in source


def test_live_session_state_detects_passing_yards(monkeypatch):
    monkeypatch.setattr(
        router.st,
        "session_state",
        {
            router.SPORT_KEY: "NFL",
            router.NFL_MARKET_KEY: router.PASSING_MARKET,
        },
        raising=False,
    )
    assert router._passing_requested() is True


def test_query_route_detects_passing_yards(monkeypatch):
    monkeypatch.setattr(router.st, "session_state", {}, raising=False)
    monkeypatch.setattr(
        router.st,
        "query_params",
        {
            router.SPORT_JUMP_QUERY_KEY: "NFL",
            router.MARKET_JUMP_QUERY_KEY: router.PASSING_MARKET,
        },
        raising=False,
    )
    assert router._passing_requested() is True


def test_prepare_route_primes_v225_guard_after_same_run_handoff(monkeypatch):
    calls = []

    monkeypatch.setattr(
        router.handoff,
        "_consume_any_nfl_category_without_rerun",
        lambda: calls.append("handoff") or True,
    )
    monkeypatch.setattr(
        router.route_guard,
        "_prime_passing_route_token_for_session",
        lambda: calls.append("prime") or router.route_guard.PASSING_ROUTE_TOKEN,
    )

    assert router._prepare_passing_route() == router.route_guard.PASSING_ROUTE_TOKEN
    assert calls == ["handoff", "prime"]


def test_passing_shell_keeps_global_router_state_unchanged(monkeypatch):
    state = {
        router.SPORT_KEY: "NFL",
        router.NFL_MARKET_KEY: router.PASSING_MARKET,
        router.root._ROUTE_TOKEN_KEY: router.root._route_token(
            "NFL", router.PASSING_MARKET
        ),
    }
    monkeypatch.setattr(router.st, "session_state", state, raising=False)
    monkeypatch.setattr(router.st, "set_page_config", lambda **kwargs: None)
    monkeypatch.setattr(router.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(router.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(router.root, "_apply_shell_css", lambda: None)

    def selectbox(label, options, key):
        return state[key]

    monkeypatch.setattr(router.st, "selectbox", selectbox)

    original_prefixes = router.root._ROUTE_MODULE_PREFIXES
    original_render_nfl = router.root._render_nfl
    rendered = []

    fake_hub = SimpleNamespace(
        render_nfl_hub=lambda market: rendered.append(market)
    )

    router._render_passing_shell_no_purge(
        importer=lambda name: fake_hub if name == router.PASSING_HUB else None
    )

    assert rendered == [router.PASSING_MARKET]
    assert router.root._ROUTE_MODULE_PREFIXES is original_prefixes
    assert router.root._render_nfl is original_render_nfl
    assert state[router.root._ROUTE_TOKEN_KEY] == router.root._route_token(
        "NFL", router.PASSING_MARKET
    )


def test_passing_route_order_is_prime_marker_then_render(monkeypatch):
    calls = []
    monkeypatch.setattr(router, "_passing_requested", lambda: True)
    monkeypatch.setattr(
        router,
        "_prepare_passing_route",
        lambda: calls.append("prime") or "NFL:Passing Yards",
    )
    monkeypatch.setattr(
        router,
        "_render_v239_marker",
        lambda: calls.append("marker"),
    )
    monkeypatch.setattr(
        router,
        "_render_passing_shell_no_purge",
        lambda: calls.append("render") or "V239_GREEN",
    )

    assert router.render_app() == "V239_GREEN"
    assert calls == ["prime", "marker", "render"]


def test_non_passing_route_delegates_to_frozen_v238(monkeypatch):
    monkeypatch.setattr(router, "_passing_requested", lambda: False)
    monkeypatch.setattr(router.prior, "render_app", lambda: "V238_DELEGATED")
    assert router.render_app() == "V238_DELEGATED"
