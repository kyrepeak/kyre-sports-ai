from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V14 = ROOT / "cfb_game_total_clean_page_v14.py"


def _function_source(text: str, name: str) -> str:
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            segment = ast.get_source_segment(text, node)
            assert segment
            return segment
    raise AssertionError(f"function not found: {name}")


def test_initial_page1_selection_never_writes_event_query() -> None:
    source = V14.read_text(encoding="utf-8")
    sync_source = _function_source(source, "_sync_frozen_matchup_state")

    assert "sync_event_id = _selector_sync_event_id()" in sync_source
    assert "selected_index = _selected_game_index(games, _query_event_id())" in sync_source
    assert "_set_query_event_id" not in sync_source
    assert "if sync_event_id:" in sync_source
    assert "_clear_selector_sync()" in sync_source
    assert "st.session_state" in sync_source
