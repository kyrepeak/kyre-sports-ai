from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVATION = ROOT / "cfb_game_total_page1_v2_step4_activation.py"
V38 = ROOT / "cfb_game_total_clean_page_v38.py"


def test_step4_runtime_repair_targets_v38_after_frozen_v37_baseline() -> None:
    activation = ACTIVATION.read_text()
    assert 'STEP4_PAGE = "cfb_game_total_clean_page_v37"' in activation
    assert 'STEP4_REPAIR_PAGE = "cfb_game_total_clean_page_v38"' in activation
    assert "cfb_router.GAME_TOTAL_PAGE = STEP4_PAGE" in activation
    assert "cfb_router.GAME_TOTAL_PAGE = STEP4_REPAIR_PAGE" in activation
    assert activation.index("cfb_router.GAME_TOTAL_PAGE = STEP4_PAGE") < activation.index(
        "cfb_router.GAME_TOTAL_PAGE = STEP4_REPAIR_PAGE"
    )
    assert "return STEP4_REPAIR_PAGE" in activation


def test_step4_v38_owns_both_analysis_seams_during_render() -> None:
    page = V38.read_text()
    assert "import cfb_game_total_clean_page_v9 as base_analysis_owner" in page
    assert "import cfb_game_total_clean_page_v26 as v26_analysis_owner" in page
    assert "base_analysis_owner._game_total_hero_html = _step4_prediction_market_html_v38" in page
    assert "v26_analysis_owner._game_total_analysis_html_v26 = _step4_prediction_market_html_v38" in page
    assert "base_analysis_owner._game_total_hero_html = original_base" in page
    assert "v26_analysis_owner._game_total_analysis_html_v26 = original_v26" in page
    assert "prior.render_game_total_hub" in page


def test_step4_v38_uses_identity_verified_fanduel_total_adapter_and_existing_side_market() -> None:
    page = V38.read_text()
    assert "import cfb_over_under_market_adapter_v1 as market_adapter" in page
    assert 'market_adapter.load_odds_for_date(game_date, "FanDuel")' in page
    assert "market_adapter.attach_market_lines([probe], payload)" in page
    assert 'row.get("market_identity_verified") is not True' in page
    assert 'float(row.get("market_projection_weight"))' in page
    assert "if projection_weight != 0.0" in page
    assert "side_market.enrich_verified_side_market(total_enriched)" in page
    assert "prediction.build_prediction_market_html" in page
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page
    assert "MAY_MODIFY_PROJECTION = False" in page


def test_step4_v38_preserves_fail_closed_market_behavior() -> None:
    page = V38.read_text()
    assert "if not event_id or not game_date:" in page
    assert "except Exception:" in page
    assert 'if row.get("market_line_available") is not True:' in page
    assert "return out" in page
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v37"' in page
