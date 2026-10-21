from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest


def _search_html(slug: str, name: str) -> str:
    return f'<a href="/players/{slug[0]}/{slug}.html">{name}</a>'


def _profile_html(name: str, nba_id: str, team: str, position: str) -> str:
    return f'''<html><h1>{name}</h1>
    <p><strong>Position:</strong> {position}</p>
    <p><strong>Team</strong>: <a href="/teams/{team}/2027.html">Team</a></p>
    <div id="div_stats-nba-com"><a href="http://stats.nba.com/player/{nba_id}/">Player Front</a></div>
    </html>'''


def _gamelog_html(rows: list[tuple[str, str, int, int, int]]) -> str:
    body = []
    for day, minutes, pts, reb, ast in rows:
        body.append(
            '<tr>'
            f'<th data-stat="date_game"><a>{day}</a></th>'
            f'<td data-stat="mp">{minutes}</td>'
            f'<td data-stat="pts">{pts}</td>'
            f'<td data-stat="trb">{reb}</td>'
            f'<td data-stat="ast">{ast}</td>'
            '</tr>'
        )
    return '<table><tbody>' + ''.join(body) + '</tbody></table>'


def test_canonical_player_id_is_provider_independent_and_stable():
    from runless_v2.nba_pra_enrichment_v1 import kyre_player_id

    assert kyre_player_id('Devin Booker') == kyre_player_id('  devin   booker ')
    assert kyre_player_id('Devin Booker').startswith('KYRE-NBA-')


def test_provider_failure_falls_through_without_espn_or_sgo_and_builds_history():
    from runless_v2.nba_pra_enrichment_v1 import collect_nba_pra_enrichment

    pages = {
        'search:Devin Booker': _search_html('bookede01', 'Devin Booker'),
        'profile:bookede01': _profile_html('Devin Booker', '1626164', 'PHX', 'Guard'),
        'gamelog:bookede01:2027': _gamelog_html([
            ('2026-10-16', '26:00', 16, 3, 6),
            ('2026-10-07', '23:00', 11, 0, 1),
        ]),
        'gamelog:bookede01:2026': _gamelog_html([
            ('2026-04-27', '41:00', 24, 0, 6),
            ('2026-04-25', '39:00', 16, 4, 7),
            ('2026-04-22', '38:00', 31, 3, 8),
        ]),
    }

    def official_loader(_day):
        raise TimeoutError('stats.nba.com timed out')

    def fetch_text(kind, value, season=None):
        key = f'{kind}:{value}' if season is None else f'{kind}:{value}:{season}'
        return pages[key]

    payload = collect_nba_pra_enrichment(
        date(2026, 10, 21),
        ['Devin Booker'],
        official_loader=official_loader,
        fetch_text=fetch_text,
        env={},
    )

    profile = payload['profiles']['devinbooker']
    assert profile['kyre_player_id'].startswith('KYRE-NBA-')
    assert profile['provider_ids']['nba'] == '1626164'
    assert profile['provider_ids']['basketball_reference'] == 'bookede01'
    assert profile['team'] == 'PHX'
    assert profile['headshot'].endswith('/1626164.png')
    assert len(profile['current_games']) == 2
    assert len(profile['prior_games']) == 3
    assert payload['provider_health']['nba_official']['status'] == 'DEGRADED'
    assert payload['provider_health']['sportradar']['status'] == 'UNAVAILABLE'
    assert payload['provider_health']['sportsdataio']['status'] == 'UNAVAILABLE'
    assert payload['provider_health']['basketball_reference']['status'] == 'HEALTHY'
    assert payload['data_state'] == 'VERIFIED'
    serialized = repr(payload).casefold()
    assert 'espn' not in serialized
    assert 'sportsgameodds' not in serialized
    assert 'sgo' not in serialized


def test_history_from_enrichment_produces_projection_probability_and_edge():
    from nba_pra_page1_model_v1 import grade_market, project_pra
    from runless_v2.nba_pra_enrichment_v1 import normalize_history_rows

    current = normalize_history_rows([
        {'game_date': '2026-10-16', 'minutes': 36, 'points': 30, 'rebounds': 5, 'assists': 7},
        {'game_date': '2026-10-14', 'minutes': 35, 'points': 28, 'rebounds': 6, 'assists': 8},
        {'game_date': '2026-10-10', 'minutes': 34, 'points': 32, 'rebounds': 4, 'assists': 6},
    ])
    prior = normalize_history_rows([
        {'game_date': '2026-04-20', 'minutes': 36, 'points': 27, 'rebounds': 5, 'assists': 7},
        {'game_date': '2026-04-18', 'minutes': 35, 'points': 29, 'rebounds': 4, 'assists': 6},
        {'game_date': '2026-04-15', 'minutes': 37, 'points': 31, 'rebounds': 6, 'assists': 8},
    ])
    model = project_pra(current, prior)
    grade = grade_market(model['projection'], 35.5, model['sigma'])
    assert model['projection'] is not None
    assert grade['edge'] is not None
    assert grade['over_probability'] is not None
    assert grade['lean'] in {'OVER', 'UNDER'}


def test_active_frontend_enrichment_transport_is_kyre_api_only():
    source = Path('nba_pra_enrichment_api_v1.py').read_text(encoding='utf-8').casefold()
    assert 'kyre-runless-proof.vercel.app' in source
    assert 'espn.com' not in source
    assert 'stats.nba.com' not in source
    assert 'basketball-reference.com' not in source
    assert 'sportsgameodds' not in source
    assert 'sgo' not in source


def test_api_only_overlay_disables_legacy_profile_rescue():
    source = Path('nba_pra_page1_api_only_v1.py').read_text(encoding='utf-8').casefold()
    assert 'backup_profile_loader' in source
    assert 'load_kyre_sports_api_nba_enrichment' in source
    assert 'espn' not in source
