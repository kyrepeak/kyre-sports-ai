import nfl_passing_yards_hub_v36 as hub


def _identity(name: str, team: str, logo: str) -> str:
    return (
        '<article class="kpass29-card">'
        '<div class="kpass29-top">'
        '<div class="kpass29-head"></div>'
        '<div class="kpass29-ident">'
        f'<div class="kpass29-name">{name}</div>'
        f'<div class="kpass29-meta">QB • {team}</div>'
        '<div class="kpass29-badges">'
        '<span class="kpass29-badge">EXACT-ID QB1</span>'
        '<span class="kpass29-badge blue">READY</span>'
        '</div></div>'
        f'<img class="kpass29-logo" src="{logo}" alt="{team} logo">'
        '</div>'
        '</article>'
    )


def test_step2_premium_qb_identity_cards_are_two_up_and_display_only():
    away = _identity("Away Quarterback", "AWY • Away Team", "away-logo.png")
    home = _identity("Home Quarterback", "HME • Home Team", "home-logo.png")
    html = hub._compact_dashboard_html(
        {"identity": [away, home]},
        {
            "away_team": "Away Team",
            "home_team": "Home Team",
            "tip_et": "1:00 PM ET",
            "venue": "Test Stadium",
        },
    )

    assert html.count('data-qb-identity-card="true"') == 2
    assert 'data-qb-slot="1"' in html
    assert 'data-qb-slot="2"' in html
    assert html.count('class="kpass36-qbconfidence">CONFIDENCE</span>') == 2

    assert "Away Quarterback" in html
    assert "Home Quarterback" in html
    assert "away-logo.png" in html
    assert "home-logo.png" in html
    assert "AWY • Away Team" in html
    assert "HME • Home Team" in html

    css = hub._COMPACT_DASHBOARD_CSS
    assert ".kpass36-qbidentity{" in css
    assert ".kpass36-qbidentity .kpass29-logo{width:60px!important;height:60px!important" in css
    assert ".kpass36-qbidentity .kpass29-name{color:#fff!important;font-size:1.08rem!important" in css
    assert ".kpass36-qbconfidence{" in css
    assert ".kpass36-qbidentity .kpass29-logo{width:48px!important;height:48px!important" in css

    assert hub.DISPLAY_ONLY is True
    assert hub.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert hub.STAKE_SIZING_ENABLED is False
