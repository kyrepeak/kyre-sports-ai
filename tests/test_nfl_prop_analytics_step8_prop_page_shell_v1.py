from pathlib import Path

import nfl_prop_analytics_prop_page_v1 as step8


def _player(position="QB", availability="PENDING", player_id="101"):
    return {
        "version": "v1",
        "state": "ready",
        "selection_key": "CAR-CLE",
        "event_id": "401872949",
        "player_id": player_id,
        "player_name": "Test Player",
        "team": "CAR",
        "position": position,
        "depth_rank": 1,
        "depth_role": f"{position}1 • STARTER",
        "availability_state": availability,
        "roster_verified": True,
        "roster_source_count": 2,
        "depth_verified": True,
        "selection_eligible": True,
        "prop_analysis_gate_open": availability == "AVAILABLE",
        "prop_page_ready": True,
    }


def test_step8_contract_is_page3_shell_navigation_only():
    source = Path("nfl_prop_analytics_prop_page_v1.py").read_text()
    for token in (
        'MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 8 PROP PAGE SHELL + MARKET NAVIGATION"',
        "STEP = 8",
        "PAGE = 3",
        "SHELL_NAVIGATION_ONLY = True",
        "PLAYER_PROP_LOGIC = False",
        "SPORTSBOOK_ODDS_LOGIC = False",
        "PROJECTION_LOGIC = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
        'PAGE_QUERY_VALUE = "props"',
        'MARKET_QUERY_KEY = "ks_pa_prop"',
        'data-nfl-prop-analytics-step8-prop-page="v1"',
        'data-prop-step8-shell-content="navigation-only"',
        'data-prop-step8-sportsbook-lines="0"',
        'data-prop-step8-odds="0"',
        'data-prop-step8-projections="0"',
        'data-prop-step8-recommendations="0"',
    ):
        assert token in source, token


def test_position_aware_market_contract():
    assert [k for k, _ in step8.market_options("QB")] == [
        "passing_yards",
        "passing_touchdowns",
        "interceptions",
        "completions",
        "attempts",
        "rushing_yards",
    ]
    assert [k for k, _ in step8.market_options("RB")] == [
        "rushing_yards",
        "carries",
        "receptions",
        "receiving_yards",
        "anytime_touchdown",
    ]
    assert [k for k, _ in step8.market_options("WR")] == [
        "receptions",
        "receiving_yards",
        "longest_reception",
        "anytime_touchdown",
    ]
    assert step8.market_options("TE") == step8.market_options("WR")


def test_invalid_market_falls_back_to_position_default():
    assert step8._resolve_market_key("QB", "not_real") == "passing_yards"
    assert step8._resolve_market_key("WR", "") == "receptions"


def test_prop_page_context_preserves_frozen_pending_gate(monkeypatch):
    matchup = {"state": "ready", "selection_key": "CAR-CLE"}
    roster = {"state": "live"}
    step6 = {"state": "live", "event_id": "401872949"}
    player = {
        "espn_id": "101",
        "name": "Test Player",
        "team": "CAR",
        "position": "QB",
        "availability_state": "PENDING",
        "depth_verified": True,
        "verified": True,
        "source_count": 2,
        "depth_rank": 1,
        "depth_role": "QB1 • STARTER",
    }

    monkeypatch.setattr(step8, "resolve_matchup_handoff", lambda: matchup)
    monkeypatch.setattr(step8, "load_verified_roster_truth", lambda handoff: roster)
    monkeypatch.setattr(step8, "load_availability_depth_truth", lambda h, r: step6)
    monkeypatch.setattr(step8, "eligible_players", lambda truth: [player])
    monkeypatch.setattr(
        step8,
        "build_player_handoff",
        lambda h, s, p: _player("QB", "PENDING", "101"),
    )
    monkeypatch.setattr(
        step8,
        "_query_value",
        lambda key: {
            step8.PLAYER_QUERY_KEY: "101",
            step8.MARKET_QUERY_KEY: "passing_touchdowns",
        }.get(key, ""),
    )

    context = step8.resolve_prop_page_context()
    assert context["state"] == "ready"
    assert context["market_key"] == "passing_touchdowns"
    assert context["player_handoff"]["prop_analysis_gate_open"] is False
    assert context["player_handoff"]["availability_state"] == "PENDING"


def test_exact_requested_player_is_required(monkeypatch):
    monkeypatch.setattr(step8, "resolve_matchup_handoff", lambda: {"state": "ready"})
    monkeypatch.setattr(step8, "load_verified_roster_truth", lambda h: {"state": "live"})
    monkeypatch.setattr(step8, "load_availability_depth_truth", lambda h, r: {"state": "live"})
    monkeypatch.setattr(
        step8,
        "eligible_players",
        lambda truth: [{
            "espn_id": "101",
            "name": "One",
            "team": "CAR",
            "position": "QB",
            "availability_state": "PENDING",
            "depth_verified": True,
            "verified": True,
            "source_count": 2,
        }],
    )
    monkeypatch.setattr(
        step8,
        "_query_value",
        lambda key: "999" if key == step8.PLAYER_QUERY_KEY else "",
    )
    context = step8.resolve_prop_page_context()
    assert context["state"] == "fail-closed"
    assert "exact Step 7 player id" in context["reason"]


def test_hub_routes_page3_before_page2_and_adds_open_control():
    hub = Path("nfl_prop_analytics_hub_v1.py").read_text()
    assert "if is_prop_page():" in hub
    assert "render_prop_page_shell()" in hub
    assert "player_handoff = render_player_selection_handoff(handoff, availability_truth)" in hub
    assert "render_prop_page_open_control(player_handoff)" in hub
    assert hub.index("if is_prop_page():") < hub.index("if is_matchup_page():")


def test_step8_has_no_sportsbook_or_projection_logic_enabled():
    assert step8.PLAYER_PROP_LOGIC is False
    assert step8.SPORTSBOOK_ODDS_LOGIC is False
    assert step8.PROJECTION_LOGIC is False
    assert step8.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step8.MAY_MODIFY_PASSING_YARDS is False
    assert step8.MAY_MODIFY_EXISTING_NFL_MARKETS is False
