from __future__ import annotations

import importlib

import pandas as pd


def _page():
    return importlib.import_module("nfl_rushing_yards_hub_v17")


def test_relevant_rushers_keep_real_workload_or_live_market_only() -> None:
    page = _page()
    projections = [
        {"official_athlete_id": "1", "expected_carries": 14.2},
        {"official_athlete_id": "2", "expected_carries": 0.3},
        {"official_athlete_id": "3", "expected_carries": 0.0},
        {"official_athlete_id": "4", "expected_carries": None},
    ]
    players = {
        "1": {"official_athlete_id": "1", "carries_per_game": 12.0},
        "2": {"official_athlete_id": "2", "carries_per_game": 0.2},
        "3": {"official_athlete_id": "3", "carries_per_game": 0.0},
        "4": {"official_athlete_id": "4", "carries_per_game": 2.1},
    }
    markets = {
        "1": {"ready": True},
        "2": {"ready": True},
        "3": {"ready": False},
        "4": {"ready": False},
    }

    kept = page.select_relevant_rushers(projections, players, markets)
    assert [row["official_athlete_id"] for row in kept] == ["1", "4", "2"]


def test_relevant_rushers_exclude_zero_usage_roster_clutter() -> None:
    page = _page()
    projections = [
        {"official_athlete_id": "10", "expected_carries": 0.0},
        {"official_athlete_id": "11", "expected_carries": 0.4},
    ]
    players = {
        "10": {"official_athlete_id": "10", "carries_per_game": 0.0},
        "11": {"official_athlete_id": "11", "carries_per_game": 0.3},
    }
    markets = {"10": {"ready": False}, "11": {"ready": False}}

    assert page.select_relevant_rushers(projections, players, markets) == []


def test_run_front_is_one_compact_strip_not_four_streamlit_metrics() -> None:
    page = _page()
    html = page.run_front_strip_html(
        {
            "data_available": True,
            "rush_yards_allowed_per_game": 95.4,
            "yards_per_carry_allowed": 4.12,
            "rush_attempts_allowed_per_game": 22.3,
            "rushing_touchdowns_allowed_per_game": 0.8,
        }
    )
    assert "95.4" in html
    assert "4.12" in html
    assert "22.3" in html
    assert "0.8" in html
    assert "krush17-front-grid" in html


def test_game_navigation_builds_verified_event_labels_for_top_selector() -> None:
    page = _page()
    games = pd.DataFrame(
        [
            {"game_id": "401", "away_abbr": "HOU", "home_abbr": "JAX", "tip_et": "12:30 PM MST"},
            {"game_id": "bad-id", "away_abbr": "A", "home_abbr": "B", "tip_et": "TBD"},
        ]
    )
    options, labels = page.verified_game_options(games)
    assert options == ["401"]
    assert labels == {"401": "HOU @ JAX • 12:30 PM MST"}


def test_cleanup_router_temporarily_owns_only_rushing_page(monkeypatch) -> None:
    router = importlib.import_module("streamlit_memory_lazy_router_api2_nfl_rushing_cleanup_v1")
    previous = router.route_owner.PROP_HUBS["Rushing Yards"]
    observed = {}

    def fake_render():
        observed["during"] = router.route_owner.PROP_HUBS["Rushing Yards"]
        return "rendered"

    monkeypatch.setattr(router.prior, "render_app", fake_render)
    result = router.render_app()

    assert result == "rendered"
    assert observed["during"] == "nfl_rushing_yards_hub_v17"
    assert router.route_owner.PROP_HUBS["Rushing Yards"] == previous
