from datetime import datetime, timezone

from nba_pra_page1_sources_v2 import is_upcoming_game, select_next_upcoming_slate

NOW = datetime(2026, 10, 20, 20, 45, tzinfo=timezone.utc)


def game(status_code=1, status_text="Scheduled", tip="2026-10-21T02:00:00Z", day="2026-10-20"):
    return {"gameStatus": status_code, "gameStatusText": status_text, "tip_utc": tip, "game_date_phoenix": day, "away_tricode": "LAL", "home_tricode": "PHX"}


def test_future_scheduled_game_is_upcoming():
    assert is_upcoming_game(game(), NOW) is True


def test_started_or_finished_game_is_hidden():
    for code, text in [(2, "Live"), (2, "Halftime"), (2, "Q3 05:21"), (3, "Final"), (3, "Completed")]:
        assert is_upcoming_game(game(code, text), NOW) is False


def test_canceled_postponed_suspended_game_is_hidden():
    for text in ("Canceled", "Postponed", "Suspended"):
        assert is_upcoming_game(game(1, text), NOW) is False


def test_stale_scheduled_game_with_past_tip_is_hidden():
    assert is_upcoming_game(game(1, "Scheduled", "2026-10-20T20:00:00Z"), NOW) is False


def test_unknown_today_fails_closed():
    assert is_upcoming_game(game(None, "TBD", None, "2026-10-20"), NOW) is False


def test_selects_first_date_with_only_upcoming_games():
    games = [
        game(3, "Final", "2026-10-20T18:00:00Z", "2026-10-20"),
        game(1, "Scheduled", "2026-10-21T02:00:00Z", "2026-10-20"),
        {**game(1, "Scheduled", "2026-10-22T01:00:00Z", "2026-10-21"), "away_tricode": "BOS", "home_tricode": "NYK"},
    ]
    day, selected = select_next_upcoming_slate(games, NOW)
    assert day == "2026-10-20"
    assert len(selected) == 1
    assert selected[0]["away_tricode"] == "LAL"
