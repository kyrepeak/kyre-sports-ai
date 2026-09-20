import nfl_passing_yards_hub_v36 as hub


def test_step5_final_responsive_polish_proves_entire_five_step_visual_contract():
    html = hub._compact_dashboard_html(
        {},
        {
            "away_team": "Away Team",
            "home_team": "Home Team",
            "tip_et": "1:00 PM ET",
            "venue": "Test Stadium",
        },
    )

    # Final five-step shell marker.
    assert html.count('data-five-step-visual-complete="true"') == 1

    # Frozen Steps 1-4 remain intact.
    assert html.count('data-why-projection-header="true"') == 1
    assert html.count('data-qb-identity-card="true"') == 2
    assert html.count('data-driver-grid="true"') == 2
    assert html.count('data-projection-driver="true"') == 12
    assert html.count('data-projection-result-row="true"') == 2
    assert html.count('data-result-cell="model"') == 2
    assert html.count('data-result-cell="market"') == 2

    css = hub._COMPACT_DASHBOARD_CSS

    # Desktop/tablet/mobile/narrow-phone responsive contract.
    assert "@media(max-width:1180px)" in css
    assert "@media(max-width:900px)" in css
    assert "@media(max-width:640px)" in css
    assert "@media(max-width:420px)" in css
    assert ".kpass36-grid{grid-template-columns:1fr;gap:12px}" in css
    assert ".kpass36-resultcells{grid-template-columns:1fr}" in css
    assert ".kpass36-drivers{grid-template-columns:1fr}" in css
    assert "overflow-wrap:anywhere" in css
    assert ".kpass36-dashboard img{max-width:100%}" in css
    assert ".kpass36-dashboard,.kpass36-dashboard *{box-sizing:border-box}" in css
    assert "flex-wrap:wrap!important" in css

    # Frozen analytics and safety contract.
    assert hub.DISPLAY_ONLY is True
    assert hub.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert hub.STAKE_SIZING_ENABLED is False
