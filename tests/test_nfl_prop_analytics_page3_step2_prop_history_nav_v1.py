from pathlib import Path

import nfl_prop_analytics_prop_page_v1 as page3

SRC = Path("nfl_prop_analytics_prop_page_v1.py").read_text()


def test_page3_step2_contract_tokens():
    for token in (
        'PAGE3_NAV_STEP = 2',
        'PAGE3_NAV_VERSION = "v1"',
        'HISTORY_QUERY_KEY = "ks_pa_history"',
        'DEFAULT_HISTORY_KEY = "L10"',
        'data-prop-page3-step2-navigation="',
        'data-prop-page3-step2-nav-state="ready"',
        'st.segmented_control(',
        '"History window"',
        '"Prop category"',
    ):
        assert token in SRC, token


def test_history_navigation_contract():
    assert [key for key, _ in page3.HISTORY_WINDOWS] == [
        "H2H", "L5", "L10", "L20", "2026", "2025"
    ]
    assert page3._resolve_history_key("") == "L10"
    assert page3._resolve_history_key("L5") == "L5"
    assert page3._resolve_history_key("bogus") == "L10"


def test_qb_compact_prop_navigation_matches_reference_amenities():
    options = page3.market_options("QB")
    labels = {
        key: page3._market_nav_label(key, label)
        for key, label in options
    }
    assert [labels[key] for key, _ in options] == [
        "PASS YDS",
        "PASS TD",
        "INT",
        "COMP",
        "ATT",
        "RUSH",
    ]


def test_non_qb_navigation_remains_position_aware():
    rb = dict(page3.market_options("RB"))
    wr = dict(page3.market_options("WR"))
    assert page3._market_nav_label("rushing_yards", rb["rushing_yards"]) == "RUSH"
    assert page3._market_nav_label("receptions", wr["receptions"]) == "REC"
    assert page3._market_nav_label("receiving_yards", wr["receiving_yards"]) == "REC YDS"


def test_step1_hero_and_frozen_safety_contract_remain_present():
    for token in (
        'PAGE3_POLISH_STEP = 1',
        'PAGE3_HERO_VERSION = "v1"',
        'data-prop-page3-step1-hero="',
        'data-prop-page3-player-headshot="',
        'data-prop-page3-team-logo="player"',
        'data-prop-page3-team-logo="opponent"',
        'SHELL_NAVIGATION_ONLY = True',
        'PLAYER_PROP_LOGIC = False',
        'SPORTSBOOK_ODDS_LOGIC = False',
        'PROJECTION_LOGIC = False',
        'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
        'MAY_MODIFY_PASSING_YARDS = False',
        'data-prop-step8-sportsbook-lines="0"',
        'data-prop-step8-odds="0"',
        'data-prop-step8-projections="0"',
        'data-prop-step8-recommendations="0"',
    ):
        assert token in SRC, token


def test_context_resolves_history_without_changing_player_gate(monkeypatch):
    matchup = {"state": "ready", "selection_key": "KC-MIA"}
    roster = {"state": "live"}
    step6 = {"state": "live", "event_id": "401872952"}
    player = {
        "espn_id": "3139477",
        "name": "Patrick Mahomes",
        "team": "KC",
        "position": "QB",
        "availability_state": "PENDING",
        "depth_verified": True,
        "verified": True,
        "source_count": 2,
        "depth_rank": 1,
        "depth_role": "QB1 • STARTER",
    }

    monkeypatch.setattr(page3, "resolve_matchup_handoff", lambda: matchup)
    monkeypatch.setattr(page3, "load_verified_roster_truth", lambda h: roster)
    monkeypatch.setattr(page3, "load_availability_depth_truth", lambda h, r: step6)
    monkeypatch.setattr(page3, "eligible_players", lambda truth: [player])
    monkeypatch.setattr(
        page3,
        "build_player_handoff",
        lambda h, s, p: {
            "version": "v1",
            "state": "ready",
            "selection_key": "KC-MIA",
            "event_id": "401872952",
            "player_id": "3139477",
            "player_name": "Patrick Mahomes",
            "team": "KC",
            "position": "QB",
            "depth_rank": 1,
            "depth_role": "QB1 • STARTER",
            "availability_state": "PENDING",
            "roster_verified": True,
            "roster_source_count": 2,
            "depth_verified": True,
            "selection_eligible": True,
            "prop_analysis_gate_open": False,
            "prop_page_ready": True,
        },
    )
    monkeypatch.setattr(
        page3,
        "_query_value",
        lambda key: {
            page3.PLAYER_QUERY_KEY: "3139477",
            page3.MARKET_QUERY_KEY: "passing_yards",
            page3.HISTORY_QUERY_KEY: "L5",
        }.get(key, ""),
    )

    context = page3.resolve_prop_page_context()
    assert context["state"] == "ready"
    assert context["history_key"] == "L5"
    assert context["market_key"] == "passing_yards"
    assert context["player_handoff"]["prop_analysis_gate_open"] is False
