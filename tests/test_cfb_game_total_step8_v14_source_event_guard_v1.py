from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "cfb_game_total_clean_page_v14.py"


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment
            return segment
    raise AssertionError(f"missing function {name}")


def _execute_sync(*, query_event: str, sync_event: str, game_event: str):
    source = SELECTOR.read_text(encoding="utf-8")
    helper_source = _function_source(source, "_sync_frozen_matchup_state")
    writes: list[str] = []
    clears: list[bool] = []
    session_state: dict[str, object] = {}
    namespace = {
        "date": object,
        "Sequence": object,
        "Mapping": object,
        "Any": object,
        "MATCHUP_STATE_KEY_PREFIX": "cfb_v152_game_total_matchup_",
        "st": SimpleNamespace(session_state=session_state),
        "_selector_sync_event_id": lambda: sync_event,
        "_query_event_id": lambda: query_event,
        "_selected_game_index": lambda games, event_id: 0,
        "_game_id": lambda game: str(game.get("espn_event_id") or ""),
        "_set_query_event_id": lambda event_id: writes.append(str(event_id)),
        "_clear_selector_sync": lambda: clears.append(True),
    }
    exec(helper_source, namespace)
    result = namespace["_sync_frozen_matchup_state"](
        "2026-10-17",
        [{"espn_event_id": game_event}],
    )
    return result, writes, clears, session_state


def test_initial_page1_default_selection_never_publishes_event_without_real_card_tap():
    result, writes, clears, session_state = _execute_sync(
        query_event="",
        sync_event="",
        game_event="401858490",
    )
    assert result == 0
    assert writes == []
    assert clears == []
    assert session_state["cfb_v152_game_total_matchup_2026-10-17"] == 0


def test_real_card_tap_may_preserve_exact_matching_event_then_consumes_sync_marker():
    result, writes, clears, session_state = _execute_sync(
        query_event="401858490",
        sync_event="401858490",
        game_event="401858490",
    )
    assert result == 0
    assert writes == ["401858490"]
    assert clears == [True]
    assert session_state["cfb_v152_game_total_matchup_2026-10-17"] == 0
