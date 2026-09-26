from pathlib import Path

import nfl_prop_analytics_prop_page_v1 as page3

SRC = Path("nfl_prop_analytics_prop_page_v1.py").read_text()


def test_page3_step1_contract_tokens():
    for token in (
        'PAGE3_POLISH_STEP = 1',
        'PAGE3_HERO_VERSION = "v1"',
        'data-prop-page3-step1-hero="',
        'data-prop-page3-player-headshot="',
        'data-prop-page3-team-logo="player"',
        'data-prop-page3-team-logo="opponent"',
        'Matchup ›',
        '✕',
    ):
        assert token in SRC, token


def test_page3_step1_uses_exact_headshot_or_exact_id_fallback():
    assert (
        page3._player_headshot_url(
            {"headshot_url": "https://example.com/player.png"},
            "3139477",
        )
        == "https://example.com/player.png"
    )
    assert (
        page3._player_headshot_url({}, "3139477")
        == "https://a.espncdn.com/i/headshots/nfl/players/full/3139477.png"
    )


def test_page3_step1_preserves_step8_safety_contract():
    for token in (
        'SHELL_NAVIGATION_ONLY = True',
        'PLAYER_PROP_LOGIC = False',
        'SPORTSBOOK_ODDS_LOGIC = False',
        'PROJECTION_LOGIC = False',
        'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
        'MAY_MODIFY_PASSING_YARDS = False',
        'MAY_MODIFY_EXISTING_NFL_MARKETS = False',
        'data-prop-step8-sportsbook-lines="0"',
        'data-prop-step8-odds="0"',
        'data-prop-step8-projections="0"',
        'data-prop-step8-recommendations="0"',
    ):
        assert token in SRC, token


def test_page3_context_exposes_selected_player_only_for_presentation(monkeypatch):
    matchup = {
        "state": "ready",
        "selection_key": "KC-MIA",
        "away": "KC",
        "home": "MIA",
        "away_name": "Chiefs",
        "home_name": "Dolphins",
    }
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
        "headshot_url": "https://example.com/mahomes.png",
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
        }.get(key, ""),
    )

    context = page3.resolve_prop_page_context()
    assert context["state"] == "ready"
    assert context["selected_player"]["espn_id"] == "3139477"
    assert context["player_handoff"]["prop_analysis_gate_open"] is False
    assert context["player_handoff"]["availability_state"] == "PENDING"
