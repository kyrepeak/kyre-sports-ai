from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "devsystem/wnba_pra_speed_v3_step9_final_cert.py"


def _source() -> str:
    return CERT.read_text(encoding="utf-8")


def test_step9_uses_segmented_streamlit_date_commit_and_patches_both_date_owners():
    source = _source()

    assert "def _set_future_slate_date_segmented(page, frame, target: str)" in source
    assert "[data-testid=\"stDateInput\"]" in source
    assert "get_by_role(\"spinbutton\")" in source
    assert "parts[\"month\"].fill" in source
    assert "parts[\"day\"].fill" in source
    assert "parts[\"year\"].fill" in source
    assert "parts[\"day\"].press(\"Tab\")" in source
    assert "nav_profile._set_date_with_game = _set_future_slate_date_segmented" in source
    assert "step5_profile._set_date_with_game = _set_future_slate_date_segmented" in source
    assert "nav_profile._set_date_with_game = original_nav_set_date" in source
    assert "step5_profile._set_date_with_game = original_step5_set_date" in source
    assert "WNBA_PRA_SPEED_V3_STEP9_SEGMENTED_DATE_GREEN" in source


def test_step9_caps_game_center_setup_wait_and_restores_frozen_budget():
    source = _source()

    assert "STEP9_GAME_SETUP_TIMEOUT_SECONDS = 30.0" in source
    assert "original_step5_game_setup_timeout = step5_profile.PROFILE_GAME_SETUP_TIMEOUT_SECONDS" in source
    assert "step5_profile.PROFILE_GAME_SETUP_TIMEOUT_SECONDS = STEP9_GAME_SETUP_TIMEOUT_SECONDS" in source
    assert "step5_profile.PROFILE_GAME_SETUP_TIMEOUT_SECONDS = original_step5_game_setup_timeout" in source
    assert "WNBA_PRA_SPEED_V3_STEP9_GAME_SETUP_FAIL_FAST_GREEN" in source
