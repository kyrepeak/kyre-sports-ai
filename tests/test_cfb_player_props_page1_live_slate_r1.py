from datetime import datetime, timezone

import cfb_player_props_page1_slate_v1 as slate
import cfb_schedule_v4


def _game():
    return {
        'game_id': '6603850',
        'identity_key': 'ncaa:6603850',
        'identity_verified': True,
        'kickoff_iso': '2026-10-20T19:00:00-04:00',
        'status': 'Scheduled',
        'away_team': 'Middle Tenn.',
        'away_team_slug': 'middle-tenn',
        'away_conference': 'Conference USA',
        'away_rank': None,
        'away_espn_team_id': '2393',
        'home_team': 'FIU',
        'home_team_slug': 'fiu',
        'home_conference': 'Conference USA',
        'home_rank': None,
        'home_espn_team_id': '2229',
        'venue': 'Pitbull Stadium',
        'broadcast': 'ESPN2',
    }


def test_page1_uses_current_schedule_v4_owner():
    assert slate.schedule is cfb_schedule_v4


def test_next_slate_keeps_games_from_the_same_successful_schedule_read(monkeypatch):
    calls = []

    def one_good_read_then_empty(day):
        calls.append(day)
        return [_game()] if len(calls) == 1 else []

    monkeypatch.setattr(slate.schedule, 'games_for_date', one_good_read_then_empty)
    result = slate.load_next_player_prop_slate(
        now_provider=lambda: datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
    )

    assert result['state'] == 'live'
    assert result['slate_date'].isoformat() == '2026-10-20'
    assert [g['official_game_id'] for g in result['games']] == ['6603850']
    assert len(calls) == 1


def test_next_slate_skips_provider_failure_and_uses_next_verified_day(monkeypatch):
    calls = []

    def loader(day):
        calls.append(day)
        if len(calls) == 1:
            raise RuntimeError('temporary provider failure')
        game = _game()
        game['kickoff_iso'] = '2026-10-21T20:00:00-04:00'
        game['game_id'] = '6603883'
        game['identity_key'] = 'ncaa:6603883'
        return [game]

    monkeypatch.setattr(slate.schedule, 'games_for_date', loader)
    result = slate.load_next_player_prop_slate(
        now_provider=lambda: datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
    )

    assert result['state'] == 'live'
    assert result['slate_date'].isoformat() == '2026-10-21'
    assert result['games'][0]['official_game_id'] == '6603883'
    assert len(calls) == 2
