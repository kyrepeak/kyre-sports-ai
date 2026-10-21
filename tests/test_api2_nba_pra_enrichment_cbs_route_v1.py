from datetime import date


def test_router_stops_at_cbs_after_official_and_unconfigured_licensed_sources():
    from runless_v2.nba_pra_enrichment_v1 import collect_nba_pra_enrichment

    calls = {'cbs': 0, 'bref': 0}

    def official(_day):
        raise TimeoutError('official degraded')

    def cbs(_day, names):
        calls['cbs'] += 1
        assert names == ['Devin Booker']
        return {
            'devinbooker': {
                'player_name': 'Devin Booker',
                'team': 'PHX',
                'position': 'SG',
                'provider_ids': {'cbs_sports': '2152529'},
                'headshot': 'https://sportshub.cbsistatic.com/i/sports/player/headshot/2152529.png?width=160',
                'current_games': [],
                'prior_games': [
                    {'game_date': '2026-04-27', 'minutes': 41, 'points': 24, 'rebounds': 0, 'assists': 6},
                    {'game_date': '2026-04-25', 'minutes': 39, 'points': 16, 'rebounds': 4, 'assists': 7},
                    {'game_date': '2026-04-22', 'minutes': 40, 'points': 22, 'rebounds': 7, 'assists': 4},
                ],
                'stats_source': 'CBS Sports',
                'data_state': 'VERIFIED',
            }
        }

    def bref(*_args, **_kwargs):
        calls['bref'] += 1
        raise AssertionError('BRef must not be called after CBS succeeds')

    payload = collect_nba_pra_enrichment(
        date(2026, 10, 21),
        ['Devin Booker'],
        official_loader=official,
        cbs_loader=cbs,
        bref_loader=bref,
        env={},
    )

    row = payload['profiles']['devinbooker']
    assert row['kyre_player_id'].startswith('KYRE-NBA-')
    assert row['provider_ids']['cbs_sports'] == '2152529'
    assert len(row['prior_games']) == 3
    assert payload['provider_health']['nba_official']['status'] == 'DEGRADED'
    assert payload['provider_health']['sportradar']['status'] == 'UNAVAILABLE'
    assert payload['provider_health']['sportsdataio']['status'] == 'UNAVAILABLE'
    assert payload['provider_health']['cbs_sports']['status'] == 'HEALTHY'
    assert payload['provider_health']['basketball_reference']['attempted'] is False
    assert calls == {'cbs': 1, 'bref': 0}
