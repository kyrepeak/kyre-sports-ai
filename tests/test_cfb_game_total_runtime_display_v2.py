from datetime import date

import cfb_game_total_runtime_display_v2 as subject


GAME_DAY = date(2026, 9, 19)
BASE_GAME = {
    "away_team": "Syracuse",
    "home_team": "Pittsburgh",
    "date": "2026-09-19",
    "weather": {"temperature_f": 72},
    "away_stats": {"points_per_game": 31.0},
    "home_stats": {"points_per_game": 28.0},
}


def test_v2_keeps_sportsbook_display_only():
    assert subject.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert subject.MAY_MODIFY_PROJECTION is False


def test_exact_event_identity_allows_market_overlay_only():
    market_game = {
        "away_team": "Syracuse",
        "home_team": "Pittsburgh",
        "date": "2026-09-19",
        "market_total": 52.5,
        "sportsbook": "FanDuel",
        "market_updated_at": "2026-09-19T15:30:00Z",
        "weather": {"temperature_f": 99},
        "away_stats": {"points_per_game": 999.0},
    }
    merged = subject.overlay_verified_market_fields(BASE_GAME, market_game, GAME_DAY)
    assert merged["market_total"] == 52.5
    assert merged["sportsbook"] == "FanDuel"
    assert merged["market_updated_at"] == "2026-09-19T15:30:00Z"
    assert merged["weather"] == BASE_GAME["weather"]
    assert merged["away_stats"] == BASE_GAME["away_stats"]


def test_wrong_home_team_fails_closed():
    market_game = {
        "away_team": "Syracuse",
        "home_team": "Boston College",
        "date": "2026-09-19",
        "market_total": 52.5,
    }
    assert subject.overlay_verified_market_fields(BASE_GAME, market_game, GAME_DAY) == BASE_GAME


def test_wrong_away_team_fails_closed():
    market_game = {
        "away_team": "Virginia Tech",
        "home_team": "Pittsburgh",
        "date": "2026-09-19",
        "market_total": 52.5,
    }
    assert subject.overlay_verified_market_fields(BASE_GAME, market_game, GAME_DAY) == BASE_GAME


def test_wrong_date_fails_closed():
    market_game = {
        "away_team": "Syracuse",
        "home_team": "Pittsburgh",
        "date": "2026-09-20",
        "market_total": 52.5,
    }
    assert subject.overlay_verified_market_fields(BASE_GAME, market_game, GAME_DAY) == BASE_GAME


def test_missing_market_total_does_not_claim_a_line():
    market_game = {
        "away_team": "Syracuse",
        "home_team": "Pittsburgh",
        "date": "2026-09-19",
        "sportsbook": "FanDuel",
    }
    merged = subject.overlay_verified_market_fields(BASE_GAME, market_game, GAME_DAY)
    assert "market_total" not in merged
    assert "sportsbook" not in merged
