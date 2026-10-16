from nfl_spread_professional_intelligence_v1 import render_matchup_card


def _game():
    return {
        "game_id": "401772912",
        "state": "pre",
        "season_type": "REGULAR SEASON",
        "tip_et": "9:30 AM ET",
        "venue": "Wembley Stadium",
        "broadcast": "NFL Net",
        "away_team": "Houston Texans",
        "away_abbr": "HOU",
        "away_record": "1-4",
        "home_team": "Jacksonville Jaguars",
        "home_abbr": "JAX",
        "home_record": "4-1",
    }


def _market():
    return {"ready": True}


def _book():
    return {
        "sportsbook": "FanDuel",
        "away_spread": 2.5,
        "away_price": -110,
        "home_spread": -2.5,
        "home_price": -110,
    }


def _analytics():
    return {
        "ready": True,
        "projected_away_margin": -3.66174,
        "away_win_probability": 0.374,
        "home_win_probability": 0.626,
        "away_cover_probability": 0.464,
        "home_cover_probability": 0.536,
        "simulated_away_margin_median": -4.0,
        "parameter_se": 0.87,
        "residual_sd": 12.97,
        "predictive_sd": 12.999,
        "margin_quantiles": {"p05": -25.0, "p25": -12.0, "p50": -4.0, "p75": 5.0, "p95": 17.0},
        "push_probability": 0.0,
        "simulations": 5_000_000,
        "certified_run": True,
        "converged": True,
        "model_quality": "HIGH",
        "away_cover_mc_se": 0.00022,
    }


def test_professional_card_promotes_decision_hierarchy_and_rounds_precision():
    html = render_matchup_card(_game(), _market(), _analytics(), book=_book())
    assert "MODEL VERDICT" in html
    assert "Jaguars -2.5" in html
    assert "MODEL EDGE" in html
    assert "+1.2 pts" in html
    assert "53.6%" in html
    assert "62.6%" in html
    assert "3.66174" not in html
    assert "-3.7" in html


def test_professional_card_adds_information_sections_without_fabricating_inputs():
    html = render_matchup_card(_game(), _market(), _analytics(), book=_book())
    for label in (
        "MARKET VS MODEL",
        "PROJECTION RANGE",
        "WHY THE MODEL LEANS",
        "RISK / COUNTERWEIGHTS",
        "MODEL VERIFICATION",
    ):
        assert label in html
    assert "Strength gap" in html
    assert "Scoring interaction gap" in html
    assert "Recent L6 margin gap" in html
    assert "Site context" in html
    assert "0.0%" in html
    assert "5,000,000" in html


def test_market_unavailable_fails_closed_without_fake_edge():
    html = render_matchup_card(_game(), {"ready": False}, _analytics(), book={})
    assert "MARKET UNAVAILABLE" in html
    assert "MODEL EDGE" in html
    assert "—" in html
    assert "FanDuel -0.0" not in html


def test_unready_analytics_gates_verdict_cleanly():
    analytics = {"ready": False, "error": "Independent analytics unavailable"}
    html = render_matchup_card(_game(), _market(), analytics, book=_book())
    assert "MODEL VERDICT" in html
    assert "GATED" in html
    assert "Independent analytics unavailable" in html


def test_v7_is_additive_over_v6_and_restores_frozen_v4_matchup_renderer():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "nfl_spread_hub_v7.py").read_text(encoding="utf-8")
    assert "import nfl_spread_hub_v6 as prior" in source
    assert "import nfl_spread_hub_v4 as frozen_v4" in source
    assert "certified_guard._install_html_guard(frozen_v4)" in source
    assert "original_matchup_card = frozen_v4._matchup_card" in source
    assert "frozen_v4._matchup_card = _professional_matchup_card" in source
    assert "frozen_v4._matchup_card = original_matchup_card" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_existing_mobile_overlay_preserves_tap_only_nav_and_activates_v7():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1.py").read_text(encoding="utf-8")
    assert "import nfl_spread_hub_v7 as spread_v7" in source
    assert 'ACTIVE_SPREAD_PAGE = "nfl_spread_hub_v7"' in source
    assert "prior.spread_v5 = spread_v7" in source
    assert "st.popover" in source
    assert "st.button" in source
    assert "st.text_input" not in source
