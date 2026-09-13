from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _load_history_module():
    spec = importlib.util.spec_from_file_location(
        "nfl_receiving_yards_history_v1_isolated",
        ROOT / "nfl_receiving_yards_history_v1.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_v5_isolated():
    fake_streamlit = types.ModuleType("streamlit")
    fake_streamlit.markdown = lambda *args, **kwargs: None
    fake_streamlit.cache_data = lambda *args, **kwargs: (lambda func: func)

    fake_prior = types.ModuleType("nfl_receiving_yards_hub_v4")
    fake_prior._player_card_v4 = lambda player, team, opponent: "<article>V4</article>"
    fake_prior._advance_step4_copy = lambda body: body
    fake_prior.render_nfl_receiving_yards_hub = lambda: None

    fake_history = types.ModuleType("nfl_receiving_yards_history_v1")
    fake_history.HISTORY_SEASONS = 3
    fake_history.HISTORY_GAME_LIMIT = 5
    fake_history.get_player_vs_team_history = lambda *args: {"ready": True, "games": []}

    names = ("streamlit", "nfl_receiving_yards_hub_v4", "nfl_receiving_yards_history_v1")
    previous = {name: sys.modules.get(name) for name in names}
    sys.modules["streamlit"] = fake_streamlit
    sys.modules["nfl_receiving_yards_hub_v4"] = fake_prior
    sys.modules["nfl_receiving_yards_history_v1"] = fake_history
    try:
        spec = importlib.util.spec_from_file_location(
            "nfl_receiving_yards_hub_v5_isolated",
            ROOT / "nfl_receiving_yards_hub_v5.py",
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, prior in previous.items():
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior


def test_history_fails_closed_without_exact_identity():
    module = _load_history_module()
    result = module.get_player_vs_team_history("Player Name", "1", "2", 2025)
    assert result["ready"] is False
    assert result["games"] == []
    assert result["sportsbook_influence"] == 0.0


def test_receiving_row_matches_exact_athlete_id_and_explicit_targets_only():
    module = _load_history_module()
    summary = {
        "header": {"competitions": [{"competitors": [{"team": {"id": "1"}}, {"team": {"id": "2"}}]}]},
        "boxscore": {
            "players": [{
                "team": {"id": "1"},
                "statistics": [{
                    "name": "receiving",
                    "labels": ["REC", "YDS", "TD", "TGTS"],
                    "athletes": [
                        {"athlete": {"id": "10", "displayName": "Same Name"}, "stats": ["4", "67", "1", "6"]},
                        {"athlete": {"id": "11", "displayName": "Same Name"}, "stats": ["9", "120", "0", "12"]},
                    ],
                }],
            }],
        },
    }
    row = module._receiving_row(summary, "1", "10")
    assert row == {
        "receptions": 4,
        "receiving_yards": 67,
        "receiving_touchdowns": 1,
        "targets_data_available": True,
        "targets": 6,
    }
    assert module._receiving_row(summary, "1", "999") is None


def test_matchup_event_discovery_requires_exact_team_pair(monkeypatch):
    module = _load_history_module()
    module._matchup_events.cache_clear()
    payload = {
        "events": [
            {
                "id": "100",
                "date": "2025-10-01T00:00Z",
                "season": {"year": 2025},
                "seasonType": {"type": 2},
                "competitions": [{
                    "competitors": [{"team": {"id": "1"}}, {"team": {"id": "2"}}],
                    "status": {"type": {"state": "post", "completed": True}},
                }],
            },
            {
                "id": "101",
                "date": "2025-09-01T00:00Z",
                "season": {"year": 2025},
                "seasonType": {"type": 2},
                "competitions": [{
                    "competitors": [{"team": {"id": "1"}}, {"team": {"id": "3"}}],
                    "status": {"type": {"state": "post", "completed": True}},
                }],
            },
        ]
    }
    monkeypatch.setattr(module, "_get_json", lambda *args, **kwargs: payload)
    rows = module._matchup_events("1", "2", 2025)
    assert rows == (("2025-10-01T00:00Z", "100", 2025),)


def test_v5_is_additive_over_frozen_v4_and_keeps_market_off():
    source = _source("nfl_receiving_yards_hub_v5.py")
    assert "import nfl_receiving_yards_hub_v4 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v4"' in source
    assert "PAGE_BUILD_STEP = 5" in source
    assert "PAGE_BUILD_TOTAL = 10" in source
    assert "50%!important" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "Projection, live markets, probability, EV, Monte Carlo" in source
    assert "wager actions remain OFF" in source


def test_step5_defense_requires_exact_opponent_id():
    module = _load_v5_isolated()
    team = {"opponent_pass_defense": {"official_team_id": "2", "receiving_yards_allowed_per_game": 210.0}}
    assert module._defense_context(team, "2") is team["opponent_pass_defense"]
    assert module._defense_context(team, "3") is None


def test_step5_h2h_html_filters_every_history_row_by_exact_ids(monkeypatch):
    module = _load_v5_isolated()
    monkeypatch.setattr(
        module,
        "_load_history",
        lambda *args: {
            "ready": True,
            "games": [
                {
                    "official_event_id": "100",
                    "official_athlete_id": "10",
                    "official_team_id": "1",
                    "opponent_official_team_id": "2",
                    "date": "2025-10-01T00:00Z",
                    "receptions": 5,
                    "receiving_yards": 88,
                    "receiving_touchdowns": 1,
                    "targets_data_available": True,
                    "targets": 7,
                },
                {
                    "official_event_id": "101",
                    "official_athlete_id": "10",
                    "official_team_id": "1",
                    "opponent_official_team_id": "999",
                    "date": "BAD ROW",
                    "receptions": 99,
                    "receiving_yards": 999,
                },
            ],
        },
    )
    html = module._step5_context_html(
        {"official_athlete_id": "10", "official_team_id": "1", "baseline_season": 2025},
        {
            "official_team_id": "1",
            "opponent_official_team_id": "2",
            "opponent_pass_defense": {
                "official_team_id": "2",
                "receptions_allowed_per_game": 20.0,
                "receiving_yards_allowed_per_game": 220.0,
                "yards_per_reception_allowed": 11.0,
                "receiving_touchdowns_allowed_per_game": 1.2,
                "targets_data_available": False,
                "targets_allowed_per_game": None,
            },
        },
        {"official_team_id": "2", "team_abbreviation": "OPP"},
    )
    assert "88 YDS" in html
    assert "7 TGT" in html
    assert "BAD ROW" not in html
    assert "999 YDS" not in html


def test_router_v116_advances_only_receiving_to_v5():
    source = _source("streamlit_memory_lazy_router_v116.py")
    assert "import streamlit_memory_lazy_router_v115 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v115"' in source
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v5"' in source
    assert 'RECEIVING_YARDS_MARKET = "Receiving Yards"' in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_boots_v116_and_preserves_v115_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v116 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V115_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V115_NFL_RECEIVING_YARDS_STEP4_VOLUME_EFFICIENCY_2026-09-13"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V116_NFL_RECEIVING_YARDS_STEP5_DEFENSE_H2H_2026-09-13"' in source


def test_frozen_v4_passing_and_rushing_owners_are_not_rewritten():
    v4 = _source("nfl_receiving_yards_hub_v4.py")
    rushing_v15 = _source("nfl_rushing_yards_hub_v15.py")
    router_v115 = _source("streamlit_memory_lazy_router_v115.py")
    assert 'FROZEN_PRIOR = "nfl_receiving_yards_hub_v3"' in v4
    assert "PAGE_BUILD_STEP = 4" in v4
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v14"' in rushing_v15
    assert 'ACTIVE_RECEIVING_YARDS_HUB = "nfl_receiving_yards_hub_v4"' in router_v115
