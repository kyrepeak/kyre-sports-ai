def test_full_market_name_resolves_unique_abbreviated_roster_label():
    from runless_v2.nba_pra_cbs_v1 import resolve_requested_player

    roster = {
        'agreen': {
            'player_name': 'A. Green',
            'team': 'MIL',
            'provider_ids': {'cbs_sports': '3041713'},
        }
    }
    match = resolve_requested_player('AJ Green', roster)
    assert match is not None
    assert match[1]['provider_ids']['cbs_sports'] == '3041713'


def test_full_name_initial_match_still_requires_unique_surname():
    from runless_v2.nba_pra_cbs_v1 import resolve_requested_player

    roster = {
        'jalenwilliams': {'player_name': 'J. Williams'},
        'jaylenwilliams': {'player_name': 'J. Williams'},
    }
    assert resolve_requested_player('Jalen Williams', roster) is None
