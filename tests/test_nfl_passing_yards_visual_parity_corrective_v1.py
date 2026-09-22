import nfl_passing_yards_hub_v16 as compact_target
import nfl_passing_yards_hub_v36 as hub


def test_v36_passthrough_preserves_compact_why_projection_owner(monkeypatch):
    original_css = hub.composition._PLAYER_CARD_CSS
    original_banner = hub.composition._visual_build_banner_v34
    original_combined = hub.composition._combined_player_cards_html
    identity_module = hub.composition.identity_visual_ui.step7_ui.identity
    original_identity_resolver = identity_module.resolve_matchup_identity

    sentinel = object()

    def fake_prior():
        return sentinel

    monkeypatch.setattr(hub.prior, "render_nfl_passing_yards_hub", fake_prior)

    result = hub.render_nfl_passing_yards_hub()

    assert result is sentinel
    assert hub.composition._PLAYER_CARD_CSS is original_css
    assert hub.composition._visual_build_banner_v34 is original_banner
    assert hub.composition._combined_player_cards_html is original_combined
    assert identity_module.resolve_matchup_identity is original_identity_resolver


def test_exact_compact_reference_panel_contract_remains_available():
    html = compact_target._why_html(
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
    )

    assert "🧠 Why This Projection" in html
    assert "RESULT → REASONS" in html
    assert "Daniel Jones" in html
    assert "Patrick Mahomes" in html
    for label in ("Volume", "Efficiency", "Pressure Adj", "Personnel", "Weather", "Recent SD"):
        assert html.count(f"<span>{label}</span>") == 2
    assert "Projection: 161.2 yds" in html
    assert "Projection: 199.8 yds" in html
    assert "LEAN UNDER • line 218.5 • O 21.4% / U 78.6%" in html
    assert "LEAN UNDER • line 221.5 • O 39.3% / U 60.7%" in html
    assert html.count('class="kpy16-grade b"') == 2
