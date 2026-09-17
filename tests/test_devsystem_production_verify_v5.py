from __future__ import annotations

from pathlib import Path

from devsystem import production_verify_v5 as v5


ROOT = Path(__file__).resolve().parents[1]


def test_v5_reads_event_from_streamlit_app_frame_when_outer_wrapper_has_none():
    outer = (
        "https://kyre-sports-ai.streamlit.app/"
        "?ks_sport=College+Football&ks_cfb_market=Game+Total"
    )
    frame = (
        "https://kyre-sports-ai.streamlit.app/~/+/"
        "?ks_sport=College+Football&ks_cfb_market=Game+Total"
        "&ks_cfb_game_total_event_id=401752801"
    )
    assert v5._event_from_candidates(frame, outer) == "401752801"


def test_v5_prefers_the_actual_app_frame_event_over_outer_wrapper_state():
    outer = (
        "https://kyre-sports-ai.streamlit.app/"
        "?ks_cfb_game_total_event_id=OLD"
    )
    frame = (
        "https://kyre-sports-ai.streamlit.app/~/+/"
        "?ks_cfb_game_total_event_id=401752999"
    )
    assert v5._event_from_candidates(frame, outer) == "401752999"


def test_v5_remains_fail_closed_when_no_event_is_persisted_anywhere():
    assert v5._event_from_candidates(
        "https://kyre-sports-ai.streamlit.app/~/+/?ks_cfb_market=Game+Total",
        "https://kyre-sports-ai.streamlit.app/?ks_cfb_market=Game+Total",
    ) == ""


def test_v5_keeps_selected_card_cross_check_and_does_not_modify_page_logic():
    source = (ROOT / "devsystem" / "production_verify_v5.py").read_text(
        encoding="utf-8"
    )
    assert "_selected_link_event" in source
    assert "selected_card_event != selected_event" in source
    assert "production_verify_v3" in source
    assert "production_verify_v4" in source
    assert "cfb_game_total_clean_page_v14.py" not in source
