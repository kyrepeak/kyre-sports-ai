from datetime import date


def test_market_alias_receives_same_kyre_id_as_resolved_full_player_name():
    from runless_v2.nba_pra_enrichment_v1 import collect_nba_pra_enrichment, kyre_player_id

    def official(_day):
        raise TimeoutError('degraded')

    def cbs(_day, names):
        assert names == ['G Antetokounmpo']
        return {
            'gantetokounmpo': {
                'player_name': 'Giannis Antetokounmpo',
                'team': 'MIA',
                'position': 'PF',
                'provider_ids': {'cbs_sports': '2135542'},
                'headshot': 'https://example.test/headshot.png',
                'current_games': [],
                'prior_games': [{'game_date': '2026-04-01', 'minutes': 36, 'points': 30, 'rebounds': 12, 'assists': 8}],
                'stats_source': 'CBS Sports',
                'data_state': 'VERIFIED',
            }
        }

    payload = collect_nba_pra_enrichment(
        date(2026, 10, 21),
        ['G Antetokounmpo'],
        official_loader=official,
        cbs_loader=cbs,
        bref_loader=lambda *_args: {},
        env={},
    )
    row = payload['profiles']['gantetokounmpo']
    assert row['kyre_player_id'] == kyre_player_id('Giannis Antetokounmpo')
    assert row['kyre_player_id'] != kyre_player_id('G Antetokounmpo')
