from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from pathlib import Path


class _Box:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeSt:
    def __init__(self, *, clicked=None, session=None):
        self.session_state = dict(session or {})
        self.clicked = set(clicked or ())
        self.buttons = []
        self.popovers = []
        self.captions = []

    def popover(self, label, **kwargs):
        self.popovers.append((label, kwargs))
        return _Box()

    def button(self, label, key=None, **kwargs):
        self.buttons.append((label, key, kwargs))
        return key in self.clicked

    def caption(self, text):
        self.captions.append(text)

    def selectbox(self, *args, **kwargs):
        raise AssertionError("native selectbox must not be used")


def _selector_module():
    name = "universal_tap_only_selector_v2" if find_spec("universal_tap_only_selector_v2") else "universal_tap_only_selector_v1"
    return import_module(name)


def _router_module():
    name = "streamlit_memory_lazy_router_universal_nav_v3" if find_spec("streamlit_memory_lazy_router_universal_nav_v3") else "streamlit_memory_lazy_router_universal_nav_v2"
    return import_module(name)


def _receiving_module():
    name = "nfl_receiving_yards_hub_v21" if find_spec("nfl_receiving_yards_hub_v21") else "nfl_receiving_yards_hub_v20"
    return import_module(name)


def test_game_tap_key_follows_exact_value_when_options_reorder(monkeypatch):
    selector = _selector_module()

    first = _FakeSt(session={"game": "401872997"})
    monkeypatch.setattr(selector, "st", first)
    selector._tap_only_selectbox(
        "Game",
        ["401872997", "401873001"],
        key="game",
        format_func=lambda value: value,
    )
    target_key = next(key for label, key, _ in first.buttons if label == "401873001")

    second = _FakeSt(clicked={target_key}, session={"game": "401872997"})
    monkeypatch.setattr(selector, "st", second)
    selected = selector._tap_only_selectbox(
        "Game",
        ["401873001", "401872997"],
        key="game",
        format_func=lambda value: value,
    )

    assert selected == "401873001"
    assert second.session_state["game"] == "401873001"


def test_cross_sport_handoff_retires_old_page_local_session_state():
    router = _router_module()
    session = {
        "ks_universal_sport": "nfl",
        "ks_universal_market": "receiving-yards",
        "ks_universal_nav_source": "tap",
        "ks_universal_epoch": 5,
        "ks_universal_last_market_by_sport": {"nfl": "receiving-yards", "cfb": "game-total"},
        "nfl_receiving_yards_step2_event": "401872997",
        "nfl_receiving_yards_selected_player": "4696882",
    }
    query = {
        "sport": "nfl",
        "market": "receiving-yards",
        "game_id": "401872997",
        "player_id": "4696882",
    }
    intent = router.RouteIntent(sport_id="cfb", market_id="game-total", source="tap")

    router._prepare_pending_handoff(intent, session, query)

    assert session["ks_universal_sport"] == "cfb"
    assert session["ks_universal_market"] == "game-total"
    assert "nfl_receiving_yards_step2_event" not in session
    assert "nfl_receiving_yards_selected_player" not in session
    assert "game_id" not in query
    assert "player_id" not in query


def test_key_receiving_options_show_face_team_logo_and_exact_identity():
    hub = _receiving_module()
    team = {
        "official_team_id": "33",
        "team_abbreviation": "BAL",
        "team_name": "Baltimore Ravens",
        "players": [
            {
                "official_athlete_id": "4696882",
                "official_team_id": "33",
                "player_name": "Devontez Walker",
                "position": "WR",
                "jersey_number": "17",
                "headshot_url": "https://example.com/walker.png",
            }
        ],
    }
    renderer = getattr(hub, "_team_id_cards_html_v21", getattr(hub, "_team_id_cards_html_v20"))
    html = renderer(team)

    assert "Devontez Walker" in html
    assert "ESPN ID 4696882" in html
    assert "ESPN + NFLVERSE" in html
    assert "headshot" in html.lower()
    assert "BAL logo" in html
    assert "<img" in html.lower()


def test_player_vs_defense_history_contract_remains_in_active_lineage():
    history = import_module("nfl_receiving_yards_hub_v15")
    assert history.DISPLAY_ONLY is True
    assert history.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    source = Path("nfl_receiving_yards_hub_v15.py").read_text(encoding="utf-8")
    assert "PLAYER VS DEFENSE HISTORY" in source
    assert "latest_exact_game" in source
    assert "No fallback was invented" in source


def test_app_activates_single_owner_router_successor():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_universal_nav_v3 import record_bootstrap_import_ms, render_app" in source
