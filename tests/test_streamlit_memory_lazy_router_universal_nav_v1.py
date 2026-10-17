from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace

from universal_sports_nav_controller_v1 import RouteIntent

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "streamlit_memory_lazy_router_universal_nav_v1.py"
APP = ROOT / "app.py"


def _overlay():
    assert find_spec("streamlit_memory_lazy_router_universal_nav_v1") is not None, (
        "streamlit_memory_lazy_router_universal_nav_v1 must exist"
    )
    return import_module("streamlit_memory_lazy_router_universal_nav_v1")


def test_activation_contract_is_additive_and_owns_universal_state_before_parent():
    overlay = _overlay()
    source = OVERLAY.read_text(encoding="utf-8")
    assert overlay.UNIVERSAL_NAV_ENABLED is True
    assert overlay.FROZEN_PARENT == "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1"
    assert "normalize_legacy_query" in source
    assert "render_universal_nav" in source
    assert "query_patch_for_state" in source
    assert "apply_legacy_route_state" in source
    assert "make_legacy_selectbox_bridge" in source
    assert source.index("render_universal_nav") < source.index("prior.render_app()")


def test_render_delegates_after_canonicalizing_and_restores_selectbox(monkeypatch):
    overlay = _overlay()
    calls = []

    def original_selectbox(label, options, *args, **kwargs):
        calls.append(label)
        return options[0]

    dummy_st = SimpleNamespace(
        session_state={},
        query_params={"sport": "nfl", "market": "spread"},
        selectbox=original_selectbox,
    )
    monkeypatch.setattr(overlay, "st", dummy_st)
    monkeypatch.setattr(overlay.nav_ui, "render_universal_nav", lambda state: None)
    monkeypatch.setattr(overlay.prior, "render_app", lambda: (
        dummy_st.session_state.get("ks_sport_touch"),
        dummy_st.session_state.get("ks_nfl_market_touch"),
        dummy_st.selectbox("📅 Date", ["2026-10-18"]),
    ))

    result = overlay.render_app()
    assert result == ("NFL", "Spread", "2026-10-18")
    assert dummy_st.selectbox is original_selectbox
    assert calls == ["📅 Date"]


def test_fresh_tap_overrides_stale_route_and_memory_round_trips(monkeypatch):
    overlay = _overlay()
    dummy_st = SimpleNamespace(
        session_state={
            "ks_universal_last_market_by_sport": {"nfl": "moneyline", "cfb": "game-total"},
            "ks_universal_epoch": 4,
        },
        query_params={"sport": "cfb", "market": "game-total", "ks_sport": "NBA"},
        selectbox=lambda label, options, *args, **kwargs: options[0],
    )
    monkeypatch.setattr(overlay, "st", dummy_st)
    monkeypatch.setattr(
        overlay.nav_ui,
        "render_universal_nav",
        lambda state: RouteIntent(sport_id="nfl", source="tap"),
    )
    monkeypatch.setattr(overlay.prior, "render_app", lambda: "delegated")

    assert overlay.render_app() == "delegated"
    assert dummy_st.query_params["sport"] == "nfl"
    assert dummy_st.query_params["market"] == "moneyline"
    assert "ks_sport" not in dummy_st.query_params
    assert dummy_st.session_state["ks_sport_touch"] == "NFL"
    assert dummy_st.session_state["ks_nfl_market_touch"] == "Moneyline"
    assert dummy_st.session_state["ks_universal_last_market_by_sport"]["cfb"] == "game-total"


def test_bridge_and_parent_hygiene_are_restored_after_parent_exception(monkeypatch):
    overlay = _overlay()
    original_selectbox = lambda label, options, *args, **kwargs: options[0]
    dummy_st = SimpleNamespace(
        session_state={},
        query_params={"sport": "mlb", "market": "slate"},
        selectbox=original_selectbox,
    )
    monkeypatch.setattr(overlay, "st", dummy_st)
    monkeypatch.setattr(overlay.nav_ui, "render_universal_nav", lambda state: None)
    original_hygiene = overlay.prior.apply_route_hygiene
    original_bridge_factory = overlay.prior._make_selectbox_bridge

    def boom():
        raise RuntimeError("parent boom")

    monkeypatch.setattr(overlay.prior, "render_app", boom)
    try:
        overlay.render_app()
    except RuntimeError as exc:
        assert str(exc) == "parent boom"
    else:
        raise AssertionError("parent exception must propagate")

    assert dummy_st.selectbox is original_selectbox
    assert overlay.prior.apply_route_hygiene is original_hygiene
    assert overlay.prior._make_selectbox_bridge is original_bridge_factory


def test_production_entrypoint_boots_universal_nav_overlay():
    source = APP.read_text(encoding="utf-8")
    expected = (
        "from streamlit_memory_lazy_router_universal_nav_v1 import "
        "record_bootstrap_import_ms, render_app"
    )
    assert expected in source
