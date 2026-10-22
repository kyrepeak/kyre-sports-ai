from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_professional_v1 as page
from sports_api.api import nfl_passing_yards_page_v1 as api


ROOT = Path(__file__).resolve().parents[1]


def _player(*, projection=268.0, line=250.5, over=0.68, under=0.32, recent=None, defense_rank=24):
    recent = recent or [280.0, 272.0, 265.0, 240.0, 300.0]
    return {
        "player_id": "kyre:nfl:player:00-0039851",
        "qb_name": "D.Maye",
        "team_abbr": "NE",
        "team_name": "New England Patriots",
        "opponent_abbr": "CHI",
        "identity_visuals": {
            "canonical_player_id": "kyre:nfl:player:00-0039851",
            "identity_verified": True,
            "headshot_url": "https://images.example.test/maye.png",
            "team_logo_url": "https://static.www.nfl.com/t_q-best/league/api/clubs/logos/NE.png",
            "opponent_logo_url": "https://static.www.nfl.com/t_q-best/league/api/clubs/logos/CHI.png",
        },
        "profile": {
            "games": len(recent),
            "passing_yards_per_game": sum(recent) / len(recent),
            "attempts_per_game": 34.0,
            "yards_per_attempt": 7.8,
            "recent_games": [
                {"game_id": f"g{i}", "passing_yards": y, "attempts": 34}
                for i, y in enumerate(recent, 1)
            ],
        },
        "context_projection": {
            "context_projection_yards": projection,
            "pressure_adjustment_yards": -1.5,
            "confidence": "MEDIUM",
        },
        "distribution": {
            "confidence": "MEDIUM",
            "sigma_yards": 48.0,
            "thresholds": [],
        },
        "market": {
            "ready": True,
            "provider": "FanDuel",
            "sportsbook": "FanDuel",
            "line": line,
            "over_odds": -110,
            "under_odds": -110,
            "source_timestamp": "2026-10-22T14:00:00Z",
            "books": [
                {"sportsbook": "FanDuel", "line": line, "over_odds": -110, "under_odds": -110, "source_timestamp": "2026-10-22T14:00:00Z"},
                {"sportsbook": "DraftKings", "line": line + 1.0, "over_odds": -105, "under_odds": -115, "source_timestamp": "2026-10-22T14:01:00Z"},
            ],
            "line_movement": {"ready": True, "sportsbook": "FanDuel", "open_line": line - 2.0, "current_line": line, "delta": 2.0},
        },
        "market_evaluation": {
            "ready": True,
            "lean": "OVER" if over > under else "UNDER",
            "grade": "A" if max(over, under) >= 0.65 else "B",
            "model_over_probability": over,
            "model_under_probability": under,
        },
        "pass_defense": {
            "rank": defense_rank,
            "grade": "FAVORABLE" if defense_rank >= 20 else "TOUGH",
            "pass_yards_allowed_per_game": 249.0 if defense_rank >= 20 else 190.0,
            "recent3_pass_yards_allowed": 260.0 if defense_rank >= 20 else 180.0,
            "sack_rate_generated": 5.0 if defense_rank >= 20 else 10.0,
        },
        "qb_vs_team_history": {"available": True, "games": 1, "avg_passing_yards": 275.0},
        "availability": {
            "verified": True,
            "qb_status": "ACTIVE",
            "offensive_line": "STABLE",
            "receivers": "HEALTHY",
            "opponent_secondary": "DEPLETED" if defense_rank >= 20 else "HEALTHY",
            "source": "Official team/NFL report",
        },
        "game_environment": {
            "verified": True,
            "venue": "Soldier Field",
            "surface": "Outdoor",
            "temperature_f": 58,
            "wind_mph": 6,
            "weather": "Clear",
            "game_script": "Competitive",
            "source": "verified weather feed",
        },
    }


def test_market_snapshot_preserves_books_and_tracks_same_book_movement_without_averaging():
    rows = [
        {"player_name":"D.Maye","sportsbook":"FanDuel","market":"Passing Yards","line":245.5,"over_odds":-110,"under_odds":-110,"source_timestamp":"2026-10-22T12:00:00Z"},
        {"player_name":"D.Maye","sportsbook":"DraftKings","market":"Passing Yards","line":246.5,"over_odds":-105,"under_odds":-115,"source_timestamp":"2026-10-22T12:01:00Z"},
        {"player_name":"D.Maye","sportsbook":"FanDuel","market":"Passing Yards","line":247.5,"over_odds":-108,"under_odds":-112,"source_timestamp":"2026-10-22T14:00:00Z"},
    ]
    snap = api.build_market_snapshot(rows, qb_name="D.Maye", projection_yards=260.0)
    assert snap["ready"] is True
    assert snap["sportsbook"] == "FanDuel"
    assert snap["line"] == 247.5
    assert {row["sportsbook"] for row in snap["books"]} == {"FanDuel", "DraftKings"}
    assert "consensus_line" not in snap
    assert snap["line_movement"] == {"ready": True, "sportsbook": "FanDuel", "open_line": 245.5, "current_line": 247.5, "delta": 2.0}


def test_strong_why_over_uses_only_verified_evidence_and_exact_market_line():
    thesis = api.build_bet_thesis(_player())
    assert thesis["ready"] is True
    assert thesis["side"] == "OVER"
    assert thesis["line"] == 250.5
    assert thesis["strength"] == "STRONG"
    assert thesis["recent_hit_rate"]["hits"] == 4
    assert thesis["recent_hit_rate"]["sample"] == 5
    text = thesis["narrative"]
    assert "4 of his last 5" in text
    assert "Over 250.5" in text
    assert "secondary" in text.lower()
    assert "pressure" in text.lower()
    assert "receiver" in text.lower()
    assert thesis["positive_factor_count"] >= 5


def test_strong_why_under_can_make_the_opposite_case_without_forcing_over():
    player = _player(projection=224.0, line=250.5, over=0.28, under=0.72, recent=[210.0, 230.0, 245.0, 260.0, 220.0], defense_rank=5)
    player["context_projection"]["pressure_adjustment_yards"] = -14.0
    player["availability"]["receivers"] = "LIMITED"
    thesis = api.build_bet_thesis(player)
    assert thesis["side"] == "UNDER"
    assert thesis["recent_hit_rate"]["hits"] == 4
    assert "Under 250.5" in thesis["narrative"]
    assert "4 of his last 5" in thesis["narrative"]
    assert "pressure" in thesis["narrative"].lower()


def test_thesis_fails_soft_when_exact_two_way_market_is_missing():
    player = _player()
    player["market"] = None
    player["market_evaluation"] = {"ready": False, "lean": "MARKET PENDING", "grade": "CHECK"}
    thesis = api.build_bet_thesis(player)
    assert thesis["ready"] is False
    assert thesis["side"] == "NO STRONG SIDE"
    assert "verified two-way Passing Yards market" in thesis["narrative"]
    assert "injury" not in thesis["narrative"].lower()


def test_page1_decision_support_exposes_fast_read_recent_form_environment_and_risks():
    support = api.build_page1_decision_support(_player(), game_date="2026-10-22")
    assert support["quick_verdict"]["side"] == "OVER"
    assert support["recent_form"]["yards"] == [280.0, 272.0, 265.0, 240.0, 300.0]
    assert support["environment"]["verified"] is True
    assert support["environment"]["wind_mph"] == 6
    assert isinstance(support["risk_flags"], list)
    assert support["book_comparison"][0]["sportsbook"] == "FanDuel"


def test_renderer_has_the_full_page1_decision_layer_and_real_page2_handoff():
    player = _player()
    player["page1_decision_support"] = api.build_page1_decision_support(player, game_date="2026-10-22")
    html = page._decision_support(player, slot=1, game_date="2026-10-22")
    for label in ("QUICK VERDICT", "LINE MOVEMENT", "RECENT FORM", "GAME ENVIRONMENT", "AVAILABILITY", "BOOK COMPARISON", "RISK FLAGS", "WHY OVER 250.5"):
        assert label in html
    assert "ks_qb_slot=1" in html
    assert "ks_py_date=2026-10-22" in html
    assert "FULL QB ANALYSIS" in html


def test_nfl_multi_source_rule_is_encoded_in_page1_api_without_banned_providers():
    source = Path(api.__file__).read_text(encoding="utf-8").lower()
    assert "api.the-odds-api.com" in source
    assert "market_provider_priority" in source
    assert "fanduel" in source
    assert "draftkings" in source
    assert "espn" not in source
    assert "sgo" not in source
    assert "missing_to_zero" in source


def test_game_environment_uses_verified_nflverse_venue_surface_and_rest_without_inventing_weather():
    env = api.build_game_environment({
        "stadium":"Soldier Field", "roof":"outdoors", "surface":"grass",
        "temp":None, "wind":None, "away_rest":4, "home_rest":4,
    }, side="away")
    assert env["verified"] is True
    assert env["venue"] == "Soldier Field"
    assert env["surface"] == "grass"
    assert env["roof"] == "outdoors"
    assert env["rest_days"] == 4
    assert env["temperature_f"] is None
    assert env["wind_mph"] is None
    assert env["weather"] == "CHECK"
    assert env["source"] == "NFLverse schedule"


def test_repeated_identity_is_compacted_inside_each_analytics_unit_instead_of_separate_grid_cells():
    player = _player()
    for html in (
        page._market_board(player), page._profile_card(player), page._matchup_card(player),
        page._drivers(player), page._ladder(player),
    ):
        assert html.startswith('<div class="kpy-playerunit">')
        assert 'class="kpy-ident"' in html
