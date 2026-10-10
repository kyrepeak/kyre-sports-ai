from __future__ import annotations

from pathlib import Path

import pytest

from devsystem.cfb_game_total_backend_preservation_step2_v1 import (
    BACKEND_FREEZE_TOKEN,
    PROTECTED_BACKEND_BLOBS,
    BackendPreservationFailure,
    validate_backend_preservation,
)

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_BACKEND_BLOBS = {
    "cfb_freeze_manifest_v12.json": "3ff2a727967e80dddbe03f747d9f32090cc39539",
    "cfb_game_total_model_v1.py": "88e98c2b78c689e48f81f049cb1a64c0e958e964",
    "cfb_game_total_final_v1.py": "78fbeaeb77e3101cc83c579b15f9cd6d485df952",
    "cfb_game_total_slate_v1.py": "777beb82b1dc3dd7df76f8f4d8d37f87eeb9b872",
    "cfb_game_total_model_input_v1.py": "0d270126b6265ec22c29ea0a73faaf57235f4b8e",
    "cfb_game_total_slate_v2.py": "1acc2859bc1666b968e8ea54fb7fadc905781d81",
    "cfb_game_total_step3_form_v1.py": "ea7bad697064625588ec31971fe642446d2f8b34",
}


def test_step2_pins_exact_certified_backend_blobs() -> None:
    assert PROTECTED_BACKEND_BLOBS == EXPECTED_BACKEND_BLOBS
    result = validate_backend_preservation(ROOT)
    assert result["status"] == "GREEN"
    assert result["freeze_token"] == BACKEND_FREEZE_TOKEN
    assert result["protected_artifact_count"] == len(EXPECTED_BACKEND_BLOBS)
    assert result["sportsbook_projection_influence"] == 0.0
    assert result["sportsbook_input_used"] is False
    assert result["market_price_used"] is False
    assert result["market_probability_used"] is False
    assert result["monte_carlo_used"] is False


def test_step2_rejects_backend_blob_drift(tmp_path: Path) -> None:
    for relative_path in EXPECTED_BACKEND_BLOBS:
        source = ROOT / relative_path
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    model = tmp_path / "cfb_game_total_model_v1.py"
    model.write_text(model.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

    with pytest.raises(BackendPreservationFailure, match="BACKEND_BLOB_DRIFT"):
        validate_backend_preservation(tmp_path)


def test_step2_preserves_step11_and_step12_contracts() -> None:
    result = validate_backend_preservation(ROOT)
    assert result["step11_model_version"] == "CFB GAME TOTAL MODEL V1 • STEP 11 DISTRIBUTION"
    assert result["step12_model_version"] == "CFB GAME TOTAL FINAL V1 • STEP 12 FINAL SYNTHESIS + RANKING"
    assert result["step12_betting_pick_active"] is False
    assert result["step12_final_forecast_active"] is True


def test_step2_is_guard_only_not_product_rewrite() -> None:
    guard_source = (ROOT / "devsystem/cfb_game_total_backend_preservation_step2_v1.py").read_text(encoding="utf-8")
    assert "streamlit" not in guard_source
    assert "requests" not in guard_source
    assert "project_distribution(" not in guard_source
    assert "synthesize(" not in guard_source
