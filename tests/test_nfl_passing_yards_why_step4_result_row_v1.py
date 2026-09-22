import nfl_passing_yards_hub_v36 as hub


def test_step4_projection_result_row_is_premium_and_display_only():
    projection_a = '<section class="kpy-proj">A MODEL RESULT</section>'
    projection_b = '<section class="kpy-proj">B MODEL RESULT</section>'
    market_a = '<section class="kpy10-card">A MARKET RESULT</section>'
    market_b = '<section class="kpy10-card">B MARKET RESULT</section>'

    html = hub._compact_dashboard_html(
        {
            "projection": [projection_a, projection_b],
            "market": [market_a, market_b],
        },
        {
            "away_team": "Away Team",
            "home_team": "Home Team",
            "tip_et": "1:00 PM ET",
            "venue": "Test Stadium",
        },
    )

    # Frozen prior visual steps remain present.
    assert html.count('data-why-projection-header="true"') == 1
    assert html.count('data-qb-identity-card="true"') == 2
    assert html.count('data-driver-grid="true"') == 2
    assert html.count('data-projection-driver="true"') == 12

    # Step 4: one premium result row per QB, each preserving model + market payload.
    assert html.count('data-projection-result-row="true"') == 2
    assert html.count('data-result-cell="model"') == 2
    assert html.count('data-result-cell="market"') == 2
    assert html.count('MODEL RESULT</span>') == 2
    assert html.count('MARKET CHECK</span>') == 2
    assert "A MODEL RESULT" in html and "B MODEL RESULT" in html
    assert "A MARKET RESULT" in html and "B MARKET RESULT" in html

    css = hub._COMPACT_DASHBOARD_CSS
    assert ".kpass36-resultrow{" in css
    assert ".kpass36-resultcells{position:relative;z-index:1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert ".kpass36-resultcell{" in css
    assert ".kpass36-resulttag{" in css
    assert ".kpass36-resultcells{grid-template-columns:1fr}" in css

    assert hub.DISPLAY_ONLY is True
    assert hub.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert hub.STAKE_SIZING_ENABLED is False
