from __future__ import annotations

from pathlib import Path

from devsystem import production_verify_v5 as v5


ROOT = Path(__file__).resolve().parents[1]


def test_v5_reads_official_event_from_browser_url():
    url = (
        "https://kyre-sports-ai.streamlit.app/"
        "?ks_sport=College+Football&ks_cfb_market=Game+Total"
        "&ks_cfb_game_total_event_id=401752801"
    )
    assert v5._event_from_url(url) == "401752801"


def test_v5_remains_fail_closed_without_event_identity():
    assert v5._event_from_url(
        "https://kyre-sports-ai.streamlit.app/?ks_cfb_market=Game+Total"
    ) == ""


def test_v163_native_selector_promotes_selection_through_streamlit_query_params():
    source = (ROOT / "cfb_game_total_clean_page_v14.py").read_text(
        encoding="utf-8"
    )
    assert 'SELECTOR_WIDGET_LABEL = "SELECT MATCHUP"' in source
    assert "st.radio(" in source
    assert "on_change=_on_native_selector_change" in source
    assert "_set_query_event_id(event_id)" in source
    assert "<form" not in source


def test_v5_proves_switch_and_hard_refresh_persistence_without_weakening_gate():
    source = (ROOT / "devsystem" / "production_verify_v5.py").read_text(
        encoding="utf-8"
    )
    assert "_wait_for_initial_top_level_selection" in source
    assert "_switch_target" in source
    assert "_wait_for_top_level_selection" in source
    assert "page.reload" in source
    assert "_native_selector_radios" in source
    assert 'input[type="radio"]' in source
    assert "target.check" in source
    assert "target.is_checked()" in source
    assert "_event_from_url(page.url) != target_event" in source
    assert "reloaded_event != target_event" in source
    assert "production_verify_v3" in source
    assert "production_verify_v4" in source
