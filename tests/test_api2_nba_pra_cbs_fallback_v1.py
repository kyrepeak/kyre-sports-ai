from __future__ import annotations

from datetime import date


def _roster_html():
    return '''<table><thead><tr><th>NO</th><th>Player</th><th>POS</th></tr></thead><tbody>
    <tr><td>15</td><td>
      <a href="/nba/players/2152529/devin-booker/">D. Booker</a>
      <a href="/nba/players/2152529/devin-booker/">Devin Booker</a>
    </td><td>SG</td></tr>
    </tbody></table>'''


def _gamelog_html(rows):
    body = ''.join(
        f'<tr><td>{day}</td><td>vs OKC</td><td>W 120-110</td><td>{mins}</td><td>{pts}</td><td>{reb}</td><td>{ast}</td></tr>'
        for day, mins, pts, reb, ast in rows
    )
    return '''<table><thead><tr>
      <th>date</th><th>opponent</th><th>result</th><th>min Minutes</th>
      <th>pts Points</th><th>reb Total Rebounds</th><th>ast Total Assists</th>
    </tr></thead><tbody>''' + body + '</tbody></table>'


def test_cbs_roster_resolves_provider_alias_without_controlling_canonical_id():
    from runless_v2.nba_pra_cbs_v1 import parse_cbs_roster

    rows = parse_cbs_roster(_roster_html(), team='PHX')
    player = rows['devinbooker']
    assert player['player_name'] == 'Devin Booker'
    assert player['team'] == 'PHX'
    assert player['position'] == 'SG'
    assert player['provider_ids']['cbs_sports'] == '2152529'
    assert player['headshot'] == 'https://sportshub.cbsistatic.com/i/sports/player/headshot/2152529.png?width=160'
    assert 'kyre_player_id' not in player


def test_cbs_gamelog_parser_excludes_non_game_rows_and_normalizes_dates():
    from runless_v2.nba_pra_cbs_v1 import parse_cbs_gamelog

    html = _gamelog_html([
        ('Apr 27, 2026', '41', 24, 0, 6),
        ('Apr 25, 2026', '39', 16, 4, 7),
    ]) + _gamelog_html([
        ('Totals', '999', 999, 999, 999),
    ])
    rows = parse_cbs_gamelog(html)
    assert rows == [
        {'game_date': '2026-04-27', 'minutes': 41.0, 'points': 24.0, 'rebounds': 0.0, 'assists': 6.0},
        {'game_date': '2026-04-25', 'minutes': 39.0, 'points': 16.0, 'rebounds': 4.0, 'assists': 7.0},
    ]


def test_cbs_loader_fetches_rosters_once_and_history_only_for_requested_players():
    from runless_v2.nba_pra_cbs_v1 import load_cbs_profiles

    calls = []
    def fetch(kind, value, season=None):
        calls.append((kind, value, season))
        if kind == 'roster':
            return _roster_html() if value == 'PHX' else '<table></table>'
        if kind == 'gamelog' and value == '2152529' and season == 2026:
            return _gamelog_html([])
        if kind == 'gamelog' and value == '2152529' and season == 2025:
            return _gamelog_html([
                ('Apr 27, 2026', '41', 24, 0, 6),
                ('Apr 25, 2026', '39', 16, 4, 7),
                ('Apr 22, 2026', '40', 22, 7, 4),
            ])
        raise AssertionError((kind, value, season))

    payload = load_cbs_profiles(
        date(2026, 10, 21),
        ['Devin Booker'],
        team_codes=['PHX'],
        fetch_text=fetch,
    )
    row = payload['devinbooker']
    assert row['provider_ids']['cbs_sports'] == '2152529'
    assert row['current_games'] == []
    assert len(row['prior_games']) == 3
    assert row['stats_source'] == 'CBS Sports'
    assert calls.count(('roster', 'PHX', None)) == 1
    assert ('gamelog', '2152529', 2026) in calls
    assert ('gamelog', '2152529', 2025) in calls
