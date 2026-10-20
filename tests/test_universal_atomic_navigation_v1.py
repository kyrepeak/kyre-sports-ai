from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "universal_atomic_navigation_v1.py"
TERMINAL = ROOT / "streamlit_memory_lazy_router_universal_runtime_v5_atomic_navigation_v1.py"
APP = ROOT / "app.py"


def _required_source(path: Path) -> str:
    assert path.exists(), f"required Atomic Navigation V1 file missing: {path.name}"
    return path.read_text(encoding="utf-8")


def test_route_identity_detects_only_canonical_route_changes():
    _required_source(HELPER)
    helper = importlib.import_module("universal_atomic_navigation_v1")

    before = SimpleNamespace(sport_id="cfb", market_id="moneyline", params={"date": "2026-10-20"})
    same = SimpleNamespace(sport_id="cfb", market_id="moneyline", params={"date": "2026-10-20"})
    market = SimpleNamespace(sport_id="cfb", market_id="game-total", params={"date": "2026-10-20"})
    sport = SimpleNamespace(sport_id="nba", market_id="spread", params={"date": "2026-10-20"})
    params = SimpleNamespace(sport_id="cfb", market_id="moneyline", params={"date": "2026-10-21"})

    assert helper.is_route_transition(before, same) is False
    assert helper.is_route_transition(before, market) is True
    assert helper.is_route_transition(before, sport) is True
    assert helper.is_route_transition(before, params) is True


def test_transition_markup_is_opaque_and_route_specific():
    _required_source(HELPER)
    helper = importlib.import_module("universal_atomic_navigation_v1")
    route = SimpleNamespace(sport_id="nba", market_id="spread", params={})
    markup = helper.transition_markup(route)

    assert "KYRE SPORTS AI" in markup
    assert "NBA" in markup.upper()
    assert "SPREAD" in markup.upper()
    assert "position:fixed" in markup.replace(" ", "").lower()
    assert "background:" in markup.lower()
    assert "pointer-events:all" in markup.replace(" ", "").lower()


def test_terminal_clears_destination_and_shields_before_loading():
    source = _required_source(TERMINAL)
    shield_at = source.index("transition_slot.markdown")
    clear_at = source.index("destination_slot.empty()")
    load_at = source.index("core.load_destination")

    assert shield_at < load_at
    assert clear_at < load_at


def test_terminal_renders_one_destination_and_removes_shield_after_commit():
    source = _required_source(TERMINAL)
    container_at = source.index("with destination_slot.container()")
    render_at = source.index("adapter.renderer")
    shield_clear_at = source.index("transition_slot.empty()", render_at)

    assert container_at < render_at < shield_clear_at
    assert "core.can_commit(scope, current)" in source
    assert "core.commit_if_current" in source


def test_terminal_has_zero_background_destination_prefetch():
    source = _required_source(TERMINAL)
    assert "_run_bounded_prefetch(" not in source
    assert "choose_prefetch(" not in source
    assert "run_prefetch(" not in source


def test_terminal_preserves_current_runtime_chain_and_fallback():
    source = _required_source(TERMINAL)
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3" in source
    assert "core._render_fallback()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source


def test_app_activates_atomic_navigation_terminal():
    source = _required_source(APP)
    assert "streamlit_memory_lazy_router_universal_runtime_v5_atomic_navigation_v1" in source
    assert "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3 import" not in source
