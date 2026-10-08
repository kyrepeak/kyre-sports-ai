from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_step4_additive_page_exists_before_green() -> None:
    page = ROOT / "cfb_game_total_clean_page_v37.py"
    assert page.exists(), "Step-4 V37 prediction + market page must exist before GREEN"
