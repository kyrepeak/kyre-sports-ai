from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step4_additive_page_exists_before_green() -> None:
    page = ROOT / "cfb_game_total_clean_page_v37.py"
    assert page.exists(), "Step-4 V37 prediction + market page must exist before GREEN"


def test_step4_prediction_market_helper_exists_before_behavior_green() -> None:
    helper = ROOT / "cfb_game_total_page1_step4_prediction_market_v1.py"
    assert helper.exists(), "Step-4 pure prediction/market helper must exist before behavior GREEN"
