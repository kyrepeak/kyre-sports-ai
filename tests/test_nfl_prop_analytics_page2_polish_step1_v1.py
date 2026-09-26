from nfl_prop_analytics_matchup_shell_v1 import _display_date, _premium_matchup_header


def _handoff():
    return {
        "state": "ready",
        "selection_key": "CAR-CLE",
        "away": "CAR",
        "home": "CLE",
        "away_name": "Panthers",
        "home_name": "Browns",
        "target_date": "2026-09-27",
        "kickoff_utc": "2026-09-27T17:00:00+00:00",
        "week": 4,
        "network": "FOX",
        "venue": "Huntington Bank Field",
        "source_count": 2,
        "verified": True,
    }


def test_page2_premium_header_contract():
    html = _premium_matchup_header(_handoff())
    assert 'data-prop-page2-premium-header="v1"' in html
    assert 'data-prop-page2-header-away="CAR"' in html
    assert 'data-prop-page2-header-home="CLE"' in html
    assert 'data-prop-page2-header-kickoff="1:00 PM ET"' in html
    assert 'data-prop-page2-header-date="2026-09-27"' in html
    assert html.count("data-prop-page2-header-logo=") == 2
    assert 'data-prop-page2-header-logo="CAR"' in html
    assert 'data-prop-page2-header-logo="CLE"' in html
    assert "a.espncdn.com/i/teamlogos/nfl/500/car.png" in html
    assert "a.espncdn.com/i/teamlogos/nfl/500/cle.png" in html
    assert "Panthers" in html
    assert "Browns" in html
    assert "FOX" in html
    assert "Huntington Bank Field" in html
    assert "VERIFIED MATCHUP" in html


def test_page2_header_date_is_compact():
    assert _display_date("2026-09-27") == "SUN • SEP 27"
    assert _display_date("") == "DATE TBD"
