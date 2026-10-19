from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_universal_runtime_routes_nfl_moneyline_to_consumer_v19():
    source = (ROOT / "universal_runtime_v5_loader_v21.py").read_text(encoding="utf-8")
    assert 'route.sport_id == "nfl" and route.market_id == "moneyline"' in source
    assert '"nfl_moneyline_hub_v19"' in source


def test_consumer_v19_exists_and_owns_headless_legacy_execution():
    page = ROOT / "nfl_moneyline_hub_v19.py"
    assert page.exists(), "V19 consumer Moneyline owner is missing"
    source = page.read_text(encoding="utf-8")
    assert "HEADLESS_FROZEN_ENGINE" in source
    assert "_silent_frozen_engine" in source
    assert "Advanced Diagnostics" in source
    assert "PRESENTATION_ONLY = True" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_MARKET_MATH = False" in source
    assert 'API_ADAPTER = "nfl_moneyline_market_api_v1"' in source


def test_consumer_v19_forbids_step_first_console_copy():
    source = (ROOT / "nfl_moneyline_hub_v19.py").read_text(encoding="utf-8")
    forbidden = (
        "STEP 1A PASSED",
        "STEP 1B PASSED",
        "Step 2 — QB Depth + Current Availability",
        "Step 3 — Preseason Game-Plan Intelligence",
        "Step 4 — Team-Strength Win Model",
    )
    assert not any(text in source for text in forbidden)
