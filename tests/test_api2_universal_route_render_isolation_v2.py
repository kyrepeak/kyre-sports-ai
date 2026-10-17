from __future__ import annotations

from importlib import import_module


class _RerunRaised(RuntimeError):
    pass


class _FakeSt:
    def __init__(self):
        self.session_state = {
            "ks_universal_sport": "mlb",
            "ks_universal_market": "slate",
            "ks_universal_nav_source": "tap",
            "ks_universal_epoch": 9,
            "ks_universal_last_market_by_sport": {
                "mlb": "slate",
                "nfl": "receiving-yards",
            },
            "ks_mlb_market_touch": "Slate",
            "ks_universal_pending_intent_v2": {
                "sport_id": "nfl",
                "market_id": "receiving-yards",
                "source": "tap",
            },
        }
        self.query_params = {
            "sport": "mlb",
            "market": "slate",
            "date": "2026-10-17",
        }
        self.markdowns = []
        self.reruns = 0

    def markdown(self, body, *args, **kwargs):
        self.markdowns.append(str(body))

    def rerun(self):
        self.reruns += 1
        raise _RerunRaised()


def test_pending_handoff_is_a_hard_render_barrier(monkeypatch):
    router = import_module("streamlit_memory_lazy_router_universal_nav_v2")
    fake = _FakeSt()
    delegated = []

    monkeypatch.setattr(router, "st", fake)
    monkeypatch.setattr(
        router.prior,
        "render_app",
        lambda: delegated.append("legacy-page-rendered"),
    )

    try:
        router._render_app_impl()
    except _RerunRaised:
        pass

    assert fake.session_state["ks_universal_sport"] == "nfl"
    assert fake.session_state["ks_universal_market"] == "receiving-yards"
    assert fake.query_params["sport"] == "nfl"
    assert fake.query_params["market"] == "receiving-yards"
    assert fake.reruns == 1
    assert delegated == [], "no old/new sports page may render inside the handoff run"


def test_handoff_masks_the_old_page_before_rerun(monkeypatch):
    router = import_module("streamlit_memory_lazy_router_universal_nav_v2")
    fake = _FakeSt()
    monkeypatch.setattr(router, "st", fake)
    monkeypatch.setattr(router.prior, "render_app", lambda: None)

    try:
        router._render_app_impl()
    except _RerunRaised:
        pass

    html = "\n".join(fake.markdowns)
    assert "ks-route-transition-v2" in html
    assert "NFL" in html
    assert "Receiving Yards" in html
    assert "position:fixed" in html.replace(" ", "")
