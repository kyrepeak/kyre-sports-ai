import nfl_passing_yards_hub_v36 as hub


def test_step1_shared_why_projection_header_matches_premium_shell_contract():
    html = hub._compact_dashboard_html({}, {
        "away_team": "Away",
        "home_team": "Home",
        "tip_et": "1:00 PM ET",
        "venue": "Test Stadium",
    })

    assert html.count('data-why-projection-header="true"') == 1
    assert 'class="kpass36-whybrain"' in html
    assert '🧠' in html
    assert 'class="kpass36-whyheadline">Why This Projection</div>' in html
    assert (
        'Fast read of the exact certified drivers already calculated below '
        '— no extra model pass.'
    ) in html
    assert 'class="kpass36-whypill">RESULT → REASONS</div>' in html

    css = hub._COMPACT_DASHBOARD_CSS
    assert ".kpass36-whyintro{" in css
    assert "border:1px solid rgba(59,130,246,.72)" in css
    assert "border-radius:26px" in css
    assert "0 0 34px rgba(37,99,235,.18)" in css
    assert ".kpass36-whybrain{" in css
    assert ".kpass36-whypill{" in css
    assert "@media(max-width:640px){.kpass36-whyintro" in css

    assert hub.DISPLAY_ONLY is True
    assert hub.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
