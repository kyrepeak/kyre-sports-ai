from datetime import datetime, timezone

from nba_pra_page1_sources_v2 import is_upcoming_game, select_next_upcoming_slate

NOW = datetime(2026, 10, 20, 21, 20, tzinfo=timezone.utc)


def game(status, tip, away='PHI', home='NYK'):
    return {
        'status': status,
        'tip_utc': tip,
        'game_date_phoenix': '2026-10-20',
        'away_tricode': away,
        'home_tricode': home,
    }


def test_canonical_upcoming_status_is_eligible_when_tip_is_future():
    assert is_upcoming_game(game('UPCOMING', '2026-10-20T23:00:00Z'), NOW) is True


def test_live_and_final_stay_ineligible():
    assert is_upcoming_game(game('LIVE', '2026-10-20T20:00:00Z'), NOW) is False
    assert is_upcoming_game(game('FINAL', '2026-10-20T18:00:00Z'), NOW) is False


def test_next_slate_keeps_future_upcoming_and_drops_live_game():
    slate, games = select_next_upcoming_slate(
        [
            game('LIVE', '2026-10-20T20:00:00Z', 'BOS', 'DET'),
            game('UPCOMING', '2026-10-20T23:00:00Z', 'PHI', 'NYK'),
            game('UPCOMING', '2026-10-21T01:30:00Z', 'OKC', 'SAS'),
        ],
        NOW,
    )
    assert slate == '2026-10-20'
    assert [(g['away_tricode'], g['home_tricode']) for g in games] == [('PHI', 'NYK'), ('OKC', 'SAS')]
