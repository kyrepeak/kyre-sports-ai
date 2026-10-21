from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _route(sport: str, market: str, **params):
    return SimpleNamespace(sport_id=sport, market_id=market, params=params)


def test_destination_page_name_uses_deep_page_identity():
    nav = importlib.import_module("universal_atomic_navigation_v2")
    assert nav.destination_page_name(_route("cfb", "player-props")) == "CFB Player Props"
    assert nav.destination_page_name(_route("cfb", "player-props", game_id="401")) == "CFB Player Props • Game"
    assert nav.destination_page_name(
        _route("cfb", "player-props", game_id="401", player_id="99", prop="rushing_yards")
    ) == "CFB Player Prop Intelligence Lab"
    assert nav.destination_page_name(
        _route("nfl", "receiving-yards", player_id="88")
    ) == "NFL Receiving Yards • Player"


def test_controller_is_preinstalled_opaque_delayed_and_singleton():
    nav = importlib.import_module("universal_atomic_navigation_v2")
    markup = nav.transition_controller_markup()
    compact = markup.replace(" ", "").lower()
    assert 'data-kyre-universal-loading="v2"' in markup
    assert "delay_ms=140" in compact
    assert "data-test-script-state" in markup
    assert "pointerdown" in markup
    assert "popstate" in markup
    assert "MutationObserver" in markup
    assert "__KYRE_UNIVERSAL_LOADING_V2__" in markup
    assert "2147483647" in markup
    assert "background:#060b13" in compact
    assert "Loading" in markup


def test_controller_skips_fast_reruns_and_does_not_poll():
    nav = importlib.import_module("universal_atomic_navigation_v2")
    markup = nav.transition_controller_markup()
    assert "clearTimeout" in markup
    assert "NOTRUNNING" in markup
    assert "setInterval" not in markup
    assert "pointerdown" in markup


def test_controller_normalizes_real_streamlit_script_state_values():
    nav = importlib.import_module("universal_atomic_navigation_v2")
    markup = nav.transition_controller_markup()
    assert "NOTRUNNING" in markup
    assert "RERUNREQUESTED" in markup
    assert "replace(/[^A-Z]/g" in markup


def test_server_fallback_is_named_opaque_and_pointer_blocking():
    nav = importlib.import_module("universal_atomic_navigation_v2")
    markup = nav.transition_markup(_route("nba", "spread", game_id="7"))
    compact = markup.replace(" ", "").lower()
    assert "NBA Spread • Game" in markup
    assert "Loading" in markup
    assert "position:fixed" in compact
    assert "pointer-events:all" in compact
    assert "background:#060b13" in compact
