from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

from devsystem.api2_universal_shell_route_top_public_cert_v1 import _visible_nfl_control

ROOT = Path(__file__).resolve().parents[1]
V4_PATH = ROOT / "streamlit_memory_lazy_router_universal_nav_v4.py"

SPORTS = {
    "nfl": ("NFL", "slate", "Slate", "🎯 NFL Market", "ks_nfl_market_touch"),
    "cfb": ("College Football", "moneyline", "Moneyline", "🎯 CFB Market", "ks_cfb_market_touch"),
    "nba": ("NBA", "spread", "Spread", "🎯 NBA Market", "ks_nba_market_touch"),
    "mlb": ("MLB", "slate", "Slate", "🎯 MLB Market", "ks_mlb_market_touch"),
    "wnba": ("WNBA", "pra", "PRA", "🎯 WNBA Market", "ks_wnba_market_touch"),
}
LEGACY_TO_ID = {legacy: sport_id for sport_id, (legacy, *_rest) in SPORTS.items()}


class _RerunSignal(BaseException):
    pass


def _state(sport_id: str):
    _legacy, market_id, _market, _label, _key = SPORTS[sport_id]
    return types.SimpleNamespace(
        sport_id=sport_id,
        market_id=market_id,
        source="canonical",
        epoch=0,
        last_market_by_sport={},
    )


def _load_v4(
    monkeypatch,
    *,
    initial_sport: str = "mlb",
    returned_intent=None,
    downstream_selector_clobber: bool = False,
):
    events: list[object] = []
    initial = _state(initial_sport)

    st = types.ModuleType("streamlit")
    st.session_state = {
        "ks_universal_sport": initial.sport_id,
        "ks_universal_market": initial.market_id,
    }
    st.query_params = {"sport": initial.sport_id, "market": initial.market_id}

    def rerun():
        events.append("rerun")
        raise _RerunSignal()

    st.rerun = rerun

    stable_ui = types.ModuleType("universal_sports_nav_ui_v1")

    def returned_renderer(_state):
        events.append("pill-return")
        return returned_intent

    stable_ui.render_universal_nav = returned_renderer

    legacy_root = types.ModuleType("streamlit_memory_lazy_router_v1")
    legacy_root.st = st

    def native_selectbox(_label, options, *args, **kwargs):
        values = list(options)
        return values[0] if values else None

    st.selectbox = native_selectbox

    def root_render_app():
        sport = st.selectbox(
            "🏟️ Sport",
            ["MLB", "WNBA", "NFL", "College Football", "NBA"],
            key="ks_sport_touch",
        )
        sport_id = LEGACY_TO_ID[str(sport)]
        _legacy, _market_id, legacy_market, market_label, market_key = SPORTS[sport_id]
        market = st.selectbox(market_label, [legacy_market], key=market_key)
        events.append(("root-owner", sport, market))
        return sport

    legacy_root.render_app = root_render_app

    canonical_v1 = types.ModuleType("streamlit_memory_lazy_router_universal_nav_v1")

    class RouteIntent:
        def __init__(self, sport_id=None, market_id=None, source="tap"):
            self.sport_id = sport_id
            self.market_id = market_id
            self.source = source

    def resolve_initial_state(session, query):
        sport_id = str(query.get("sport") or session.get("ks_universal_sport") or "mlb").lower()
        if sport_id not in SPORTS:
            sport_id = "mlb"
        state = _state(sport_id)
        market_id = str(query.get("market") or session.get("ks_universal_market") or state.market_id)
        if market_id != state.market_id:
            market_id = state.market_id
        state.market_id = market_id
        return state

    def persist_state(state, session):
        session["ks_universal_sport"] = state.sport_id
        session["ks_universal_market"] = state.market_id

    def apply_legacy_route_state(state, session):
        legacy, _market_id, legacy_market, _label, market_key = SPORTS[state.sport_id]
        session["ks_sport_touch"] = legacy
        session[market_key] = legacy_market
        if state.sport_id != "mlb":
            session.pop("ks_mlb_live_odds_route", None)

    def make_legacy_selectbox_bridge(delegate, state):
        legacy, _market_id, legacy_market, market_label, _market_key = SPORTS[state.sport_id]

        def bridge(label, options, *args, **kwargs):
            if label == "🏟️ Sport":
                return legacy
            if label == market_label:
                return legacy_market
            values = list(options or ())
            return values[0] if values else delegate(label, options, *args, **kwargs)

        return bridge

    def apply_intent(state, intent):
        target = str(getattr(intent, "sport_id", None) or state.sport_id).lower()
        return _state(target)

    canonical_v1.RouteIntent = RouteIntent
    canonical_v1._resolve_initial_state = resolve_initial_state
    canonical_v1._persist_state = persist_state
    canonical_v1.apply_legacy_route_state = apply_legacy_route_state
    canonical_v1.make_legacy_selectbox_bridge = make_legacy_selectbox_bridge
    canonical_v1._apply_intent = apply_intent
    canonical_v1.query_patch_for_state = lambda state, query: {
        "sport": state.sport_id,
        "market": state.market_id,
    }
    canonical_v1.apply_query_patch = lambda query, patch: query.update(patch)

    v2 = types.ModuleType("streamlit_memory_lazy_router_universal_nav_v2")
    v2.nav_ui = types.SimpleNamespace(render_universal_nav=lambda _state: None)
    v2.prior = canonical_v1
    v2.legacy_root = legacy_root

    def clear_query(query):
        assert query is st.query_params
        events.append("clear-query")

    def clear_session(session, outgoing_sport_id):
        assert session is st.session_state
        events.append(("clear-session", outgoing_sport_id))

    v2._clear_cross_route_query_context = clear_query
    v2._clear_cross_route_session_context = clear_session

    v3 = types.ModuleType("streamlit_memory_lazy_router_universal_nav_v3")
    v3.record_bootstrap_import_ms = lambda value: events.append(("bootstrap", value))

    def v3_render_app():
        events.append("v3-delegate")
        state = _state(initial_sport)
        intent = v2.nav_ui.render_universal_nav(state)
        owner = str(getattr(intent, "sport_id", None) or state.sport_id).lower()
        if downstream_selector_clobber:
            target = _state(owner)
            st.session_state["ks_universal_sport"] = target.sport_id
            st.session_state["ks_universal_market"] = target.market_id
            st.query_params["sport"] = target.sport_id
            st.query_params["market"] = target.market_id

            outgoing_legacy = SPORTS[initial_sport][0]

            def stale_downstream_selectbox(label, options, *args, **kwargs):
                if label == "🏟️ Sport":
                    return outgoing_legacy
                values = list(options)
                return values[0] if values else None

            legacy_root.st.selectbox = stale_downstream_selectbox
            return legacy_root.render_app()
        events.append(("legacy-owner", owner))
        return owner

    v3.render_app = v3_render_app

    for name, module in {
        "streamlit": st,
        "streamlit_memory_lazy_router_universal_nav_v1": canonical_v1,
        "streamlit_memory_lazy_router_universal_nav_v2": v2,
        "streamlit_memory_lazy_router_universal_nav_v3": v3,
        "streamlit_memory_lazy_router_v1": legacy_root,
        "universal_sports_nav_ui_v1": stable_ui,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location("_api2_router_v4_test", V4_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, v2, legacy_root, st, events


def test_entrypoint_boots_v4_and_forces_r4_runtime_refresh():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_universal_nav_v4" in app
    assert "API2_UNIVERSAL_SHELL_ROUTE_TOP_V1_RUNTIME_REFRESH_2026_10_17_R4" in app
    assert 'sys.modules["streamlit_memory_lazy_router_universal_nav_v2"] = _router_v4' in app


def test_entrypoint_executes_preserved_body_fresh_on_every_streamlit_rerun():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from app_legacy_entrypoint_v1 import *" not in app
    assert '_legacy_entrypoint_path = Path(__file__).with_name("app_legacy_entrypoint_v1.py")' in app
    assert "exec(_legacy_entrypoint_code, globals(), globals())" in app


def test_entrypoint_scopes_legacy_module_aliases_to_each_exec():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '_original_nav_v2_module = sys.modules.get("streamlit_memory_lazy_router_universal_nav_v2")' in app
    assert '_original_shell_v1_module = sys.modules.get("kyre_universal_shell_runtime_v1")' in app
    assert 'try:\n    exec(_legacy_entrypoint_code, globals(), globals())' in app
    assert 'finally:\n    if _original_nav_v2_module is None:' in app
    assert 'sys.modules["streamlit_memory_lazy_router_universal_nav_v2"] = _original_nav_v2_module' in app
    assert 'sys.modules["kyre_universal_shell_runtime_v1"] = _original_shell_v1_module' in app


def test_entrypoint_self_heals_previously_poisoned_hot_reload_modules_before_exec():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "import importlib" in app
    assert "def _ensure_base_module(" in app
    assert '_real_nav_v2 = _ensure_base_module("streamlit_memory_lazy_router_universal_nav_v2", "nav_ui")' in app
    assert '_real_shell_v1 = _ensure_base_module("kyre_universal_shell_runtime_v1", "activate_step3_page")' in app
    assert "_router_v4.v2 = _real_nav_v2" in app
    assert "_shell_v2.prior = _real_shell_v1" in app
    assert "_router_v4.prior.prior = _real_nav_v2" in app


def test_v4_returns_tap_intent_so_legacy_owner_switches_to_nfl_in_same_run(monkeypatch):
    intent = types.SimpleNamespace(sport_id="nfl", market_id=None, source="tap")
    module, v2, _root, _st, events = _load_v4(monkeypatch, returned_intent=intent)
    original = v2.nav_ui.render_universal_nav

    result = module.render_app()

    assert result == "nfl"
    assert events == [
        "v3-delegate",
        "pill-return",
        "clear-query",
        ("clear-session", "mlb"),
        ("legacy-owner", "nfl"),
    ]
    assert v2.nav_ui.render_universal_nav is original


@pytest.mark.parametrize(
    ("outgoing", "incoming"),
    [
        ("mlb", "nfl"),
        ("nfl", "mlb"),
        ("nfl", "cfb"),
        ("cfb", "nfl"),
        ("nba", "nfl"),
        ("nfl", "wnba"),
    ],
)
def test_v4_final_root_enforces_only_canonical_body_owner_after_downstream_clobber(
    monkeypatch,
    outgoing,
    incoming,
):
    intent = types.SimpleNamespace(sport_id=incoming, market_id=None, source="tap")
    module, v2, legacy_root, st, events = _load_v4(
        monkeypatch,
        initial_sport=outgoing,
        returned_intent=intent,
        downstream_selector_clobber=True,
    )
    original_renderer = v2.nav_ui.render_universal_nav
    original_root_render = legacy_root.render_app

    result = module.render_app()

    incoming_legacy, incoming_market_id, incoming_market, _label, _key = SPORTS[incoming]
    outgoing_legacy = SPORTS[outgoing][0]
    assert result == incoming_legacy
    assert ("root-owner", incoming_legacy, incoming_market) in events
    assert st.query_params["sport"] == incoming
    assert st.query_params["market"] == incoming_market_id
    assert st.session_state["ks_universal_sport"] == incoming
    assert st.session_state["ks_sport_touch"] == incoming_legacy
    assert result != outgoing_legacy
    assert legacy_root.render_app is original_root_render
    assert v2.nav_ui.render_universal_nav is original_renderer


def test_v4_no_tap_preserves_v3_delegate_without_extra_rerun(monkeypatch):
    module, v2, _root, _st, events = _load_v4(monkeypatch, returned_intent=None)
    original = v2.nav_ui.render_universal_nav

    result = module.render_app()

    assert result == "mlb"
    assert events == ["v3-delegate", "pill-return", ("legacy-owner", "mlb")]
    assert v2.nav_ui.render_universal_nav is original


class _FakeItem:
    def __init__(self, label: str):
        self.label = label

    def is_visible(self):
        return True


class _FakeLocator:
    def __init__(self, labels):
        self.labels = list(labels)

    def filter(self, *, has_text):
        return _FakeLocator([label for label in self.labels if has_text.search(label)])

    def count(self):
        return len(self.labels)

    def nth(self, index):
        return _FakeItem(self.labels[index])


class _FakeFrame:
    def locator(self, selector):
        assert selector == "button"
        return _FakeLocator(["🏈 NFL", "🏟️ CFB", "🏀 NBA", "⚾ MLB", "🏀 WNBA"])

    def get_by_text(self, text, exact=False):
        assert text == "NFL"
        assert exact is True
        return _FakeLocator([])


def test_public_certificate_targets_actual_emoji_labeled_nfl_button():
    control = _visible_nfl_control(_FakeFrame())
    assert control is not None
    assert control.label == "🏈 NFL"
