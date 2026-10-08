from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "cfb_game_total_page1_step4_prediction_market_v1.py"
SIDE_MARKET_PATH = ROOT / "cfb_game_total_page1_step4_side_market_v1.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_helper():
    return _load_module(HELPER_PATH, "step4_prediction_market")


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
            "verified_away_spread": 3.5,
            "verified_home_spread": -3.5,
            "verified_away_moneyline": 145,
            "verified_home_moneyline": -165,
            "verified_side_market_provider": "ESPN BET",
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
        "Side market ESPN BET • exact event ID",
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


def test_step4_generic_nested_odds_are_not_trusted_for_side_lines() -> None:
    html = _renderer()(
        {"projected_combined_total": 47.0},
        {"ready": True, "projected_combined_total": 47.0, "forecast_strength": 72, "grade": "B+"},
        {
            "away_team": "Arizona",
            "home_team": "Utah",
            "market_total": 48.5,
            "odds": {
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
    assert '<span>Spread</span><strong>Line not posted</strong>' in html
    assert '<span>Moneyline</span><strong>Line not posted</strong>' in html
    assert "Arizona +2.5" not in html and "Utah -2.5" not in html
    assert "Arizona +120" not in html and "Utah -140" not in html
    assert "Under -1.5" in html


def test_step4_side_market_enrichment_requires_exact_event_identity() -> None:
    assert SIDE_MARKET_PATH.exists(), "Step-4 exact-event side-market helper must exist"
    side_market = _load_module(SIDE_MARKET_PATH, "step4_side_market")

    def loader(target_date: str):
        assert target_date == "2026-10-10"
        return (
            {
                "401999001": {
                    "event_id": "401999001",
                    "provider": "ESPN BET",
                    "market_available": True,
                    "away_spread": 2.5,
                    "home_spread": -2.5,
                    "away_moneyline": 120,
                    "home_moneyline": -140,
                    "projection_weight": 0.0,
                    "may_modify_projection": False,
                },
                "401999999": {
                    "event_id": "401999999",
                    "provider": "Wrong Game",
                    "market_available": True,
                    "away_spread": 99,
                    "home_spread": -99,
                    "away_moneyline": 999,
                    "home_moneyline": -999,
                    "projection_weight": 0.0,
                    "may_modify_projection": False,
                },
            },
            {"status": "GREEN", "projection_weight": 0.0},
        )

    enriched = side_market.enrich_verified_side_market(
        {
            "event_id": "401999001",
            "game_date": "2026-10-10",
            "away_team": "Arizona",
            "home_team": "Utah",
            "odds": {"away_spread": 88, "away_ml": 888},
        },
        loader=loader,
    )
    assert enriched["verified_away_spread"] == 2.5
    assert enriched["verified_home_spread"] == -2.5
    assert enriched["verified_away_moneyline"] == 120
    assert enriched["verified_home_moneyline"] == -140
    assert enriched["verified_side_market_provider"] == "ESPN BET"
    assert enriched["verified_side_market_event_id"] == "401999001"
    assert enriched["verified_side_market_projection_weight"] == 0.0


def test_step4_side_market_enrichment_fails_closed_on_identity_miss() -> None:
    assert SIDE_MARKET_PATH.exists(), "Step-4 exact-event side-market helper must exist"
    side_market = _load_module(SIDE_MARKET_PATH, "step4_side_market_miss")

    def loader(_target_date: str):
        return (
            {
                "OTHER": {
                    "event_id": "OTHER",
                    "provider": "Wrong Game",
                    "market_available": True,
                    "away_spread": 9.5,
                    "home_spread": -9.5,
                    "away_moneyline": 300,
                    "home_moneyline": -350,
                    "projection_weight": 0.0,
                    "may_modify_projection": False,
                }
            },
            {"status": "GREEN", "projection_weight": 0.0},
        )

    enriched = side_market.enrich_verified_side_market(
        {
            "event_id": "401999001",
            "game_date": "2026-10-10",
            "verified_away_spread": 77,
            "verified_away_moneyline": 777,
        },
        loader=loader,
    )
    assert "verified_away_spread" not in enriched
    assert "verified_away_moneyline" not in enriched
    assert enriched["verified_side_market_status"] == "UNAVAILABLE"


def test_step4_v37_patches_last_analysis_owner_and_enriches_side_market() -> None:
    page = (ROOT / "cfb_game_total_clean_page_v37.py").read_text()
    assert "import cfb_game_total_clean_page_v36 as prior" in page
    assert "import cfb_game_total_clean_page_v26 as analysis_owner" in page
    assert "import cfb_game_total_page1_step4_side_market_v1 as side_market" in page
    assert "analysis_owner._game_total_analysis_html_v26 = _step4_prediction_market_html" in page
    assert "side_market.enrich_verified_side_market(display_game)" in page
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
