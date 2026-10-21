from datetime import date


def test_unique_first_initial_plus_exact_surname_resolves_to_canonical_player():
    from runless_v2.nba_pra_cbs_v1 import load_cbs_profiles

    roster = '''<table><tbody>
      <tr><td>34</td><td><a href="/nba/players/2135542/giannis-antetokounmpo/">G. Antetokounmpo</a><a href="/nba/players/2135542/giannis-antetokounmpo/">Giannis Antetokounmpo</a></td><td>PF</td></tr>
    </tbody></table>'''
    games = '''<table><tr><th>date</th><th>opponent</th><th>result</th><th>min Minutes</th><th>pts Points</th><th>reb Total Rebounds</th><th>ast Total Assists</th></tr>
      <tr><td>Apr 12, 2026</td><td>vs BOS</td><td>W</td><td>36</td><td>32</td><td>12</td><td>8</td></tr>
    </table>'''

    def fetch(kind, value, season=None):
        if kind == 'roster':
            return roster if value == 'MIL' else '<table></table>'
        if kind == 'gamelog':
            return games
        raise AssertionError((kind, value, season))

    rows = load_cbs_profiles(
        date(2026, 10, 21),
        ['G Antetokounmpo'],
        team_codes=['MIL'],
        fetch_text=fetch,
    )
    row = rows['gantetokounmpo']
    assert row['player_name'] == 'Giannis Antetokounmpo'
    assert row['provider_ids']['cbs_sports'] == '2135542'
    assert row['team'] == 'MIL'


def test_ambiguous_initial_surname_never_guesses():
    from runless_v2.nba_pra_cbs_v1 import resolve_requested_player

    roster = {
        'jaylenwilliams': {'player_name': 'Jaylen Williams'},
        'jalenwilliams': {'player_name': 'Jalen Williams'},
    }
    assert resolve_requested_player('J Williams', roster) is None
