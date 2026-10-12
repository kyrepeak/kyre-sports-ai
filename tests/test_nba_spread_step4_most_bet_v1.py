from nba_spread_most_bet_v1 import select_most_bet_game_from_html, MostBetUnavailable

SCHEDULE = [
    {"away_tricode":"LAC","home_tricode":"TOR","game_date_phoenix":"2026-10-11","tip_phoenix":"4:00 PM","status":"UPCOMING"},
    {"away_tricode":"ATL","home_tricode":"IND","game_date_phoenix":"2026-10-11","tip_phoenix":"4:30 PM","status":"UPCOMING"},
]

HTML = '''
<table><thead><tr><th>Scheduled</th><th>Open</th><th>Best Odds</th><th>% of Bets</th><th>% of Money</th><th>Diff</th><th>Bets</th></tr></thead>
<tbody>
<tr><td>Clippers LAC 545 Raptors TOR 546</td><td>+4.5 -4.5</td><td>+4.5-104 -4.5+100</td><td>53% 47%</td><td>54% 46%</td><td>+1%</td><td>434</td></tr>
<tr><td>Hawks ATL 547 Pacers IND 548</td><td>+2.5 -2.5</td><td>+1.5+100 -1.5-104</td><td>41% 59%</td><td>46% 54%</td><td>+5%</td><td>590</td></tr>
</tbody></table>
'''

def test_selects_highest_tracked_bet_count_and_binds_schedule():
    row = select_most_bet_game_from_html(HTML, SCHEDULE)
    assert row["away_tricode"] == "ATL"
    assert row["home_tricode"] == "IND"
    assert row["tracked_bets"] == 590
    assert row["bet_pct"] == [41, 59]
    assert row["money_pct"] == [46, 54]
    assert row["tip_phoenix"] == "4:30 PM"
    assert row["source"] == "Action Network"


def test_fails_closed_when_highest_row_cannot_bind_to_verified_schedule():
    html = HTML.replace("Hawks ATL 547 Pacers IND 548", "Lakers LAL 777 Suns PHX 778")
    try:
        select_most_bet_game_from_html(html, SCHEDULE)
    except MostBetUnavailable as exc:
        assert "UNBOUND_HIGHEST_VOLUME_ROW" in str(exc)
    else:
        raise AssertionError("must fail closed")


def test_ignores_non_table_noise_and_requires_split_fields():
    broken = HTML.replace("46% 54%", "N/A")
    try:
        select_most_bet_game_from_html(broken, SCHEDULE)
    except MostBetUnavailable:
        pass
    else:
        raise AssertionError("must fail closed")


from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / 'nba_spread_page_v1.py').read_text()
MODULE = (ROOT / 'nba_spread_most_bet_v1.py').read_text()

def test_page_adds_only_step4_featured_card_and_preserves_step3_markers():
    lower = PAGE.lower()
    assert 'data-testid="nba-spread-step2-active"' in PAGE
    assert 'data-testid="nba-spread-step3-schedule-active"' in PAGE
    assert 'data-testid="nba-spread-step4-most-bet-active"' in PAGE
    assert 'data-testid="nba-spread-step4-most-bet-card"' in PAGE
    assert 'Phoenix, Arizona' in PAGE
    assert 'Live / Final' in PAGE
    assert 'public bet' not in lower
    assert 'cover probability' not in lower
    assert 'fair spread' not in lower
    assert 'sportsbook_projection_influence = 0.0' in lower

def test_step4_does_not_activate_later_layers():
    assert 'MAY_ACTIVATE_SHARP_MONEY = False' in MODULE
    assert 'MAY_ACTIVATE_INJURIES = False' in MODULE
    assert 'MAY_ACTIVATE_RANKINGS = False' in MODULE
    assert 'MAY_MODIFY_PROBABILITY = False' in MODULE
