from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PAGE1 = ROOT / "cfb_game_total_clean_page_v43.py"


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment
            return segment
    raise AssertionError(f"missing function {name}")


def test_step8_page1_default_selection_does_not_publish_event_query():
    source = PAGE1.read_text(encoding="utf-8")
    assert "PAGE1_AUTO_EVENT_QUERY_WRITE = False" in source
    helper_source = _function_source(source, "_sync_page1_matchup_without_auto_event")

    writes: list[str] = []
    owner = SimpleNamespace(
        MATCHUP_STATE_KEY_PREFIX="cfb_v152_game_total_matchup_",
        st=SimpleNamespace(session_state={}),
        _query_event_id=lambda: "",
        _selector_sync_event_id=lambda: "",
        _selected_game_index=lambda games, event_id: 0,
        _clear_selector_sync=lambda: None,
        _set_query_event_id=lambda event_id: writes.append(str(event_id)),
    )
    namespace = {"selector_owner": owner}
    exec(helper_source, namespace)
    selected_day = SimpleNamespace(__str__=lambda self: "2026-10-10")
    selected_day.isoformat = lambda: "2026-10-10"
    result = namespace["_sync_page1_matchup_without_auto_event"](
        selected_day,
        [{"espn_event_id": "401856824"}],
    )
    assert result == 0
    assert writes == []
    assert owner.st.session_state["cfb_v152_game_total_matchup_2026-10-10"] == 0


def test_step8_page1_owner_scopes_sync_override_to_one_render():
    source = PAGE1.read_text(encoding="utf-8")
    render_source = _function_source(source, "render_game_total_hub")
    assert "original_sync = selector_owner._sync_frozen_matchup_state" in render_source
    assert "selector_owner._sync_frozen_matchup_state = _sync_page1_matchup_without_auto_event" in render_source
    assert "selector_owner._sync_frozen_matchup_state = original_sync" in render_source


def test_step8_page1_selector_override_is_serialized_across_sessions():
    source = PAGE1.read_text(encoding="utf-8")
    render_source = _function_source(source, "render_game_total_hub")
    assert "from threading import RLock" in source
    assert "_PAGE1_SYNC_LOCK = RLock()" in source
    assert "with _PAGE1_SYNC_LOCK:" in render_source

    lock_pos = render_source.index("with _PAGE1_SYNC_LOCK:")
    capture_pos = render_source.index("original_sync = selector_owner._sync_frozen_matchup_state")
    swap_pos = render_source.index("selector_owner._sync_frozen_matchup_state = _sync_page1_matchup_without_auto_event")
    restore_pos = render_source.index("selector_owner._sync_frozen_matchup_state = original_sync")
    assert lock_pos < capture_pos < swap_pos < restore_pos
