from datetime import date


def test_history_steps_back_one_extra_season_only_when_recent_seasons_are_empty():
    from runless_v2.nba_pra_cbs_v1 import load_cbs_profiles

    roster = '''<table><tbody>
      <tr><td>0</td><td><a href="/nba/players/2252663/fred-vanvleet/">F. VanVleet</a></td><td>PG</td></tr>
    </tbody></table>'''
    games = '''<table><tr><th>date</th><th>opponent</th><th>result</th><th>min Minutes</th><th>pts Points</th><th>reb Total Rebounds</th><th>ast Total Assists</th></tr>
      <tr><td>Apr 10, 2025</td><td>vs UTA</td><td>W</td><td>34</td><td>20</td><td>4</td><td>8</td></tr>
    </table>'''
    calls = []

    def fetch(kind, value, season=None):
        calls.append((kind, value, season))
        if kind == 'roster':
            return roster if value == 'HOU' else '<table></table>'
        if kind == 'gamelog':
            return games if season == 2024 else '<table></table>'
        raise AssertionError((kind, value, season))

    rows = load_cbs_profiles(
        date(2026, 10, 21),
        ['Fred VanVleet'],
        team_codes=['HOU'],
        fetch_text=fetch,
    )
    row = rows['fredvanvleet']
    assert row['current_games'] == []
    assert len(row['prior_games']) == 1
    assert ('gamelog', '2252663', 2026) in calls
    assert ('gamelog', '2252663', 2025) in calls
    assert ('gamelog', '2252663', 2024) in calls
    assert not any(call[2] == 2023 for call in calls if call[0] == 'gamelog')
