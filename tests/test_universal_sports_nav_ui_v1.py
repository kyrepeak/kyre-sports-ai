from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

from universal_sports_nav_controller_v1 import RouteState

ROOT = Path(__file__).resolve().parents[1]


def _ui():
    assert find_spec("universal_sports_nav_ui_v1") is not None, (
        "universal_sports_nav_ui_v1 must exist"
    )
    return import_module("universal_sports_nav_ui_v1")


def test_ui_contract_uses_one_scoped_sticky_pills_shell():
    ui = _ui()
    source = (ROOT / "universal_sports_nav_ui_v1.py").read_text(encoding="utf-8")
    assert ui.NAV_CONTAINER_KEY == "ks_universal_nav_shell"
    assert ui.SPORT_CONTROL_KEY == "ks_universal_sport_pills"
    assert ui.MARKET_CONTROL_KEY == "ks_universal_market_pills"
    assert "st.container(key=NAV_CONTAINER_KEY)" in source
    assert source.count("st.pills(") == 2
    assert "st.selectbox(" not in source
    assert ".st-key-ks_universal_nav_shell" in source
    assert "position: sticky" in source
    assert "overflow-x: auto" in source
    assert "z-index:" in source
    assert "KYRE SPORTS" in source


def test_renderer_scopes_widget_keys_to_route_epoch(monkeypatch):
    ui = _ui()
    state = RouteState("nfl", "spread", "canonical_url", 7, {"nfl": "spread"})
    seen_keys = []
    selections = iter(["nfl", "spread"])
    def pills(*args, **kwargs):
        seen_keys.append(kwargs.get("key"))
        return next(selections)
    monkeypatch.setattr(ui.st, "pills", pills)
    class DummyContainer:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr(ui.st, "container", lambda **k: DummyContainer())
    monkeypatch.setattr(ui.st, "markdown", lambda *a, **k: None)
    assert ui.render_universal_nav(state) is None
    assert seen_keys == [
        "ks_universal_sport_pills__7",
        "ks_universal_market_pills__7",
    ]


def test_renderer_returns_sport_tap_only_when_selection_changes(monkeypatch):
    ui = _ui()
    state = RouteState("nfl", "spread", "canonical_url", 1, {"nfl": "spread"})
    selections = iter(["nba", "spread"])
    monkeypatch.setattr(ui.st, "pills", lambda *a, **k: next(selections))
    class DummyContainer:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr(ui.st, "container", lambda **k: DummyContainer())
    monkeypatch.setattr(ui.st, "markdown", lambda *a, **k: None)
    intent = ui.render_universal_nav(state)
    assert intent.source == "tap"
    assert intent.sport_id == "nba"
    assert intent.market_id is None


def test_renderer_returns_market_tap_and_no_intent_for_unchanged(monkeypatch):
    ui = _ui()
    state = RouteState("nfl", "spread", "canonical_url", 1, {"nfl": "spread"})
    class DummyContainer:
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr(ui.st, "container", lambda **k: DummyContainer())
    monkeypatch.setattr(ui.st, "markdown", lambda *a, **k: None)

    selections = iter(["nfl", "moneyline"])
    monkeypatch.setattr(ui.st, "pills", lambda *a, **k: next(selections))
    intent = ui.render_universal_nav(state)
    assert (intent.sport_id, intent.market_id, intent.source) == ("nfl", "moneyline", "tap")

    selections = iter(["nfl", "spread"])
    monkeypatch.setattr(ui.st, "pills", lambda *a, **k: next(selections))
    assert ui.render_universal_nav(state) is None
