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


def test_v163_game_forms_promote_selection_to_top_level_browser_url():
    source = (ROOT / "cfb_game_total_clean_page_v14.py").read_text(
        encoding="utf-8"
    )
    assert '<form class="gt163-game-form" action="/" method="get" target="_top">' in source
    assert 'button type="submit"' in source
    assert 'name="{EVENT_QUERY_KEY}"' in source
    assert 'target="_self"' not in source


def test_v5_proves_switch_and_hard_refresh_persistence_without_weakening_gate():
    source = (ROOT / "devsystem" / "production_verify_v5.py").read_text(
        encoding="utf-8"
    )
    assert "_switch_target" in source
    assert "_wait_for_top_level_selection" in source
    assert "page.reload" in source
    assert 'target_scope != "_top"' in source
    assert 'method != "get"' in source
    assert 'hidden_event_value != target_event' in source
    assert "_event_from_url(page.url) != target_event" in source
    assert "reloaded_event != target_event" in source
    assert "production_verify_v3" in source
    assert "production_verify_v4" in source
