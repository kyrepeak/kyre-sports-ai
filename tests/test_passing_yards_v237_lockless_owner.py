import threading

import streamlit_memory_lazy_router_v237 as router


def test_passing_owner_install_is_idempotent(monkeypatch):
    monkeypatch.setattr(router.passing_router, "PASSING_HUB", "old-passing-owner")
    monkeypatch.setitem(router.identity_router.PROP_HUBS, router.PASSING_MARKET, "old-v187-owner")

    router._install_passing_owners()
    router._install_passing_owners()

    assert router.passing_router.PASSING_HUB == router.PASSING_HUB
    assert router.identity_router.PROP_HUBS[router.PASSING_MARKET] == router.PASSING_HUB


def test_non_passing_route_delegates_without_owner_install(monkeypatch):
    monkeypatch.setattr(router, "_passing_requested", lambda: False)
    monkeypatch.setattr(router.passing_router, "PASSING_HUB", "old-passing-owner")
    monkeypatch.setitem(router.identity_router.PROP_HUBS, router.PASSING_MARKET, "old-v187-owner")

    calls = {"count": 0}

    def fake_render():
        calls["count"] += 1
        return "DELEGATED"

    monkeypatch.setattr(router.prior, "render_app", fake_render)

    assert router.render_app() == "DELEGATED"
    assert calls["count"] == 1
    assert router.passing_router.PASSING_HUB == "old-passing-owner"
    assert router.identity_router.PROP_HUBS[router.PASSING_MARKET] == "old-v187-owner"


def test_two_passing_sessions_can_enter_render_concurrently(monkeypatch):
    """Regression proof for hosted Streamlit cross-session lock starvation.

    The former V237 held one process-wide RLock around the entire render. This
    test blocks the first synthetic render and proves a second session can
    still enter prior.render_app before the first one is released.
    """
    monkeypatch.setattr(router, "_passing_requested", lambda: True)
    monkeypatch.setattr(router, "_cleanup_hub_importable", lambda: True)

    first_entered = threading.Event()
    second_entered = threading.Event()
    release = threading.Event()
    counter_lock = threading.Lock()
    entered = {"count": 0}
    errors = []

    def fake_render():
        with counter_lock:
            entered["count"] += 1
            number = entered["count"]
            if number == 1:
                first_entered.set()
            elif number == 2:
                second_entered.set()
        if not release.wait(timeout=4):
            raise RuntimeError("synthetic render release timeout")
        return "GREEN"

    monkeypatch.setattr(router.prior, "render_app", fake_render)

    def worker():
        try:
            assert router.render_app() == "GREEN"
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=worker, daemon=True)
    t2 = threading.Thread(target=worker, daemon=True)

    t1.start()
    assert first_entered.wait(timeout=1.5)

    t2.start()
    assert second_entered.wait(timeout=1.5), (
        "second Passing Yards session was serialized behind the first render"
    )

    assert router.passing_router.PASSING_HUB == router.PASSING_HUB
    assert router.identity_router.PROP_HUBS[router.PASSING_MARKET] == router.PASSING_HUB

    release.set()
    t1.join(timeout=3)
    t2.join(timeout=3)

    assert not t1.is_alive()
    assert not t2.is_alive()
    assert errors == []


def test_v237_has_no_render_wide_process_lock():
    source = __import__("inspect").getsource(router)
    assert "_PROCESS_PASSING_ROUTE_RLOCK" not in source
    assert "with _PROCESS_PASSING_ROUTE_RLOCK" not in source
