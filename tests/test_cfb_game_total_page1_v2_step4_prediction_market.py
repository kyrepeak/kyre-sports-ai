from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "cfb_game_total_page1_step4_prediction_market_v1.py"


def _load_helper():
    spec = importlib.util.spec_from_file_location("step4_prediction_market", HELPER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _renderer():
    helper = _load_helper()
    renderer = getattr(helper, "build_prediction_market_html", None)
    assert callable(renderer), "Step-4 helper must expose build_prediction_market_html"
    return renderer


def test_step4_additive_page_exists_before_green() -> None:
    page = ROOT / "cfb_game_total_clean_page_v37.py"
    assert page.exists(), "Step-4 V37 prediction + market page must exist before GREEN"


def test_step4_prediction_market_helper_exists_before_behavior_green() -> None:
    assert HELPER_PATH.exists(), "Step-4 pure prediction/market helper must exist before behavior GREEN"


def test_step4_verified_market_comparison_renders_model_and_real_lines() -> None:
    html = _renderer()(
        {"projected_combined_total": 57.1},
        {
            "ready": True,
            "projected_combined_total": 57.1,
            "forecast_strength": 0.82,
            "grade": "A",
        },
        {
            "away_team": "Syracuse",
            "home_team": "Pittsburgh",
            "market_total": 52.5,
            "away_spread": 3.5,
            "home_spread": -3.5,
            "away_moneyline": 145,
            "home_moneyline": -165,
        },
        {},
        10,
    )
    for expected in (
        "PREDICTION + MARKET COMPARISON",
        "57.1",
        "52.5",
        "Syracuse +3.5",
        "Pittsburgh -3.5",
        "Syracuse +145",
        "Pittsburgh -165",
        "Over +4.6",
        "+4.6 pts vs market",
        "82%",
        "Grade A",
        "5M CERTIFIED",
        "10/12 verified",
        "0.0% sportsbook projection influence",
    ):
        assert expected in html


def test_step4_missing_market_lines_fail_closed_without_inventing_numbers() -> None:
    html = _renderer()(
        {"projected_combined_total": 44.0},
        {"ready": True, "projected_combined_total": 44.0, "forecast_strength": 0.61, "grade": "B"},
        {"away_team": "Away", "home_team": "Home"},
        {},
        8,
    )
    assert '<span>Market Total</span><strong>Line not posted</strong>' in html
    assert '<span>Spread</span><strong>Line not posted</strong>' in html
    assert '<span>Moneyline</span><strong>Line not posted</strong>' in html
    assert "Market line unavailable" in html
    assert "No verified total • model remains independent" in html


def test_step4_nested_verified_odds_are_supported() -> None:
    html = _renderer()(
        {"projected_combined_total": 47.0},
        {"ready": True, "projected_combined_total": 47.0, "forecast_strength": 72, "grade": "B+"},
        {
            "away_team": "Arizona",
            "home_team": "Utah",
            "odds": {
                "total": 48.5,
                "away_spread": 2.5,
                "home_spread": -2.5,
                "away_ml": 120,
                "home_ml": -140,
            },
        },
        {},
        12,
    )
    assert "48.5" in html
    assert "Arizona +2.5" in html and "Utah -2.5" in html
    assert "Arizona +120" in html and "Utah -140" in html
    assert "Under -1.5" in html
    assert "72%" in html


def test_step4_v37_owns_only_analysis_seam_over_frozen_v36() -> None:
    page = (ROOT / "cfb_game_total_clean_page_v37.py").read_text()
    assert "import cfb_game_total_clean_page_v36 as prior" in page
    assert "import cfb_game_total_clean_page_v9 as analysis_owner" in page
    assert "analysis_owner._game_total_hero_html = prediction.build_prediction_market_html" in page
    assert "return prior.render_game_total_hub" in page or "prior.render_game_total_hub" in page
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v36"' in page
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page
    assert "MAY_MODIFY_PROJECTION = False" in page


def test_step4_activation_uses_unfrozen_component_seam_and_preserves_step3_shell() -> None:
    activation_path = ROOT / "cfb_game_total_page1_v2_step4_activation.py"
    assert activation_path.exists(), "Step-4 activation wrapper must exist"
    activation = activation_path.read_text()
    shell = (ROOT / "kyre_universal_shell_runtime_v1.py").read_text()
    components = (ROOT / "kyre_universal_components_v1.py").read_text()
    assert 'BASE_PAGE = "cfb_game_total_clean_page_v36"' in activation
    assert 'STEP4_PAGE = "cfb_game_total_clean_page_v37"' in activation
    assert "cfb_router.GAME_TOTAL_PAGE = STEP4_PAGE" in activation
    assert "MAY_MODIFY_OTHER_SPORTS = False" in activation
    assert "MAY_MODIFY_PROJECTION = False" in activation
    assert "from cfb_game_total_page1_v2_step3_activation import activate_step3_page" in shell
    assert "activate_step3_page()" in shell
    assert "cfb_game_total_page1_v2_step4_activation" not in shell
    assert "activate_step4_page" not in shell
    assert "from cfb_game_total_page1_v2_step4_activation import activate_step4_page" in components
    assert "activate_step4_page()" in components
