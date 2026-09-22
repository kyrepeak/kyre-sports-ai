import nfl_passing_yards_hub_v36 as hub


def test_step3_six_driver_tiles_render_per_qb_and_preserve_frozen_steps():
    html = hub._compact_dashboard_html(
        {},
        {
            "away_team": "Away Team",
            "home_team": "Home Team",
            "tip_et": "1:00 PM ET",
            "venue": "Test Stadium",
        },
    )

    # Frozen Step 1 + Step 2 remain present.
    assert html.count('data-why-projection-header="true"') == 1
    assert html.count('data-qb-identity-card="true"') == 2

    # Exactly six Step 3 drivers per quarterback.
    assert html.count('data-driver-grid="true"') == 2
    assert html.count('data-projection-driver="true"') == 12
    for key in ("volume", "efficiency", "matchup", "pressure", "personnel", "environment"):
        assert html.count(f'data-driver-key="{key}"') == 2

    # Every tile points at already-certified evidence; no new model pass.
    assert html.count('data-driver-source="profile"') == 4
    assert html.count('data-driver-source="defense"') == 2
    assert html.count('data-driver-source="pressure"') == 2
    assert html.count('data-driver-source="personnel"') == 2
    assert html.count('data-driver-source="environment"') == 2

    css = hub._COMPACT_DASHBOARD_CSS
    assert ".kpass36-drivers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))" in css
    assert ".kpass36-driver{" in css
    assert ".kpass36-driver-blue{" in css
    assert ".kpass36-driver-green{" in css
    assert ".kpass36-driver-red{" in css
    assert ".kpass36-driver-amber{" in css
    assert ".kpass36-driver-purple{" in css
    assert ".kpass36-driver-cyan{" in css
    assert ".kpass36-drivers{grid-template-columns:repeat(2,minmax(0,1fr))" in css

    assert hub.DISPLAY_ONLY is True
    assert hub.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert hub.STAKE_SIZING_ENABLED is False
