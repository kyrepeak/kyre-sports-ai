import nfl_passing_yards_hub_v16 as target


def test_reference_style_why_projection_contract():
    html = target._why_html(
        [
            {"qb_name": "Daniel Jones", "expected_attempts": 28.9, "expected_ypa": 5.76},
            {"qb_name": "Patrick Mahomes", "expected_attempts": 29.4, "expected_ypa": 6.80},
        ],
        [
            {"qb_name": "Daniel Jones", "pressure_adjustment_yards": -5.4, "personnel_context": "WATCH", "weather_context": "NORMAL", "context_projection_yards": 161.2},
            {"qb_name": "Patrick Mahomes", "pressure_adjustment_yards": -0.5, "personnel_context": "NEUTRAL", "weather_context": "NORMAL", "context_projection_yards": 199.8},
        ],
        [
            {"qb_name": "Daniel Jones", "confidence": "MEDIUM", "location_yards": 161.2, "sigma_yards": 71.4},
            {"qb_name": "Patrick Mahomes", "confidence": "MEDIUM", "location_yards": 199.8, "sigma_yards": 78.3},
        ],
        [
            {"grade_ready": True, "lean": "LEAN UNDER", "grade": "B", "line": 218.5, "model_over_probability": 0.214, "model_under_probability": 0.786},
            {"grade_ready": True, "lean": "LEAN UNDER", "grade": "B", "line": 221.5, "model_over_probability": 0.393, "model_under_probability": 0.607},
        ],
        {
            "away": {"abbr": "NYG", "team": "New York Giants"},
            "home": {"abbr": "KC", "team": "Kansas City Chiefs"},
        },
    )

    assert html.count('data-reference-why-projection="true"') == 1
    assert "Why This Projection" in html
    assert "RESULT → REASONS" in html
    assert "Daniel Jones" in html and "Patrick Mahomes" in html
    assert "QB • New York Giants" in html
    assert "QB • Kansas City Chiefs" in html
    assert "MEDIUM CONFIDENCE" in html
    assert "https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png" in html
    assert "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png" in html
    assert html.count('class="kpy16-reason ') == 12
    for label in ("Volume", "Efficiency", "Pressure Adj", "Personnel", "Weather", "Recent SD"):
        assert html.count(f"<span>{label}</span>") == 2
    assert "Projection: <strong>161.2</strong> yds" in html
    assert "Projection: <strong>199.8</strong> yds" in html
    assert html.count('class="kpy16-grade b"') == 2

    css = target._CLEANUP_STEP4_CSS
    assert ".kpy16-reasons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))" in css
    assert ".kpy16-r-volume{" in css
    assert ".kpy16-r-eff{" in css
    assert ".kpy16-r-pressure{" in css
    assert ".kpy16-r-personnel{" in css
    assert ".kpy16-r-weather{" in css
    assert ".kpy16-r-sd{" in css
    assert "@media(max-width:430px)" in css
