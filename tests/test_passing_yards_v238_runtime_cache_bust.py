from pathlib import Path

import streamlit_memory_lazy_router_v238 as router


def test_app_activates_v238_entrypoint():
    app = Path("app.py").read_text()
    assert (
        "from streamlit_memory_lazy_router_v238 import "
        "record_bootstrap_import_ms, render_app"
    ) in app
    assert (
        "from streamlit_memory_lazy_router_v237 import "
        "record_bootstrap_import_ms, render_app"
    ) not in app


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
    monkeypatch.setattr(
        router.passing_router,
        "_active_route",
        lambda: ("", ""),
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
    monkeypatch.setattr(
        router.passing_router,
        "_active_route",
        lambda: ("", ""),
    )
    assert router._passing_requested() is True


def test_passing_route_uses_direct_v187_shell(monkeypatch):
    monkeypatch.setattr(router, "_passing_requested", lambda: True)
    monkeypatch.setattr(router, "_cleanup_hub_importable", lambda: True)

    calls = {"marker": 0, "direct": 0, "prior": 0}

    monkeypatch.setattr(
        router,
        "_render_v238_marker",
        lambda: calls.__setitem__("marker", calls["marker"] + 1),
    )

    def direct():
        calls["direct"] += 1
        assert (
            router.identity_router.PROP_HUBS[router.PASSING_MARKET]
            == router.PASSING_HUB
        )
        assert router.passing_router.PASSING_HUB == router.PASSING_HUB
        return "V238_DIRECT_GREEN"

    def stale_prior():
        calls["prior"] += 1
        raise AssertionError("Passing Yards must not delegate to cached V237")

    monkeypatch.setattr(router.identity_router, "_render_direct_prop", direct)
    monkeypatch.setattr(router.prior, "render_app", stale_prior)

    assert router.render_app() == "V238_DIRECT_GREEN"
    assert calls == {"marker": 1, "direct": 1, "prior": 0}


def test_non_passing_route_delegates_to_v237(monkeypatch):
    monkeypatch.setattr(router, "_passing_requested", lambda: False)
    calls = {"prior": 0, "direct": 0}

    def prior_render():
        calls["prior"] += 1
        return "V237_DELEGATED"

    def direct():
        calls["direct"] += 1
        raise AssertionError("non-Passing route must not enter V187 direct shell")

    monkeypatch.setattr(router.prior, "render_app", prior_render)
    monkeypatch.setattr(router.identity_router, "_render_direct_prop", direct)

    assert router.render_app() == "V237_DELEGATED"
    assert calls == {"prior": 1, "direct": 0}
