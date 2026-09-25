import pytest

import streamlit_memory_lazy_router_v237 as router


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
        "_cold_passing_yards_query_requested",
        lambda: False,
    )
    monkeypatch.setattr(
        router.passing_router,
        "_active_route",
        lambda: ("", ""),
    )
    assert router._passing_requested() is True


def test_passing_yards_temporarily_redirects_v187_to_v85(monkeypatch):
    original_identity = router.identity_router.PROP_HUBS.get(router.PASSING_MARKET)
    original_passing = router.passing_router.PASSING_HUB
    observed = {}

    monkeypatch.setattr(router, "_passing_requested", lambda: True)
    monkeypatch.setattr(router, "_cleanup_hub_importable", lambda: True)

    def fake_prior_render():
        observed["identity"] = router.identity_router.PROP_HUBS.get(
            router.PASSING_MARKET
        )
        observed["passing"] = router.passing_router.PASSING_HUB
        return "GREEN"

    monkeypatch.setattr(router.prior, "render_app", fake_prior_render)

    assert router.render_app() == "GREEN"
    assert observed == {
        "identity": router.PASSING_HUB,
        "passing": router.PASSING_HUB,
    }
    assert router.identity_router.PROP_HUBS.get(router.PASSING_MARKET) == original_identity
    assert router.passing_router.PASSING_HUB == original_passing


def test_passing_yards_restores_redirect_after_exception(monkeypatch):
    original_identity = router.identity_router.PROP_HUBS.get(router.PASSING_MARKET)
    original_passing = router.passing_router.PASSING_HUB

    monkeypatch.setattr(router, "_passing_requested", lambda: True)
    monkeypatch.setattr(router, "_cleanup_hub_importable", lambda: True)

    def explode():
        assert router.identity_router.PROP_HUBS.get(router.PASSING_MARKET) == router.PASSING_HUB
        assert router.passing_router.PASSING_HUB == router.PASSING_HUB
        raise RuntimeError("synthetic render failure")

    monkeypatch.setattr(router.prior, "render_app", explode)

    with pytest.raises(RuntimeError, match="synthetic render failure"):
        router.render_app()

    assert router.identity_router.PROP_HUBS.get(router.PASSING_MARKET) == original_identity
    assert router.passing_router.PASSING_HUB == original_passing


def test_non_passing_route_delegates_without_mutation(monkeypatch):
    original_identity = router.identity_router.PROP_HUBS.get(router.PASSING_MARKET)
    original_passing = router.passing_router.PASSING_HUB
    calls = {"count": 0}

    monkeypatch.setattr(router, "_passing_requested", lambda: False)

    def fake_prior_render():
        calls["count"] += 1
        return "DELEGATED"

    monkeypatch.setattr(router.prior, "render_app", fake_prior_render)

    assert router.render_app() == "DELEGATED"
    assert calls["count"] == 1
    assert router.identity_router.PROP_HUBS.get(router.PASSING_MARKET) == original_identity
    assert router.passing_router.PASSING_HUB == original_passing
