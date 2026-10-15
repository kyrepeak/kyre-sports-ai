from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V42 = ROOT / "cfb_game_total_clean_page_v42.py"
V44 = ROOT / "cfb_game_total_clean_page_v44.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"


def _nested_function(source: str, outer_name: str, inner_name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    outer = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == outer_name
    )
    return next(
        node
        for node in outer.body
        if isinstance(node, ast.FunctionDef) and node.name == inner_name
    )


def test_date_change_uses_pinned_selected_day_snapshot_without_runtimeerror():
    """Execute the exact nested loader without importing the Streamlit product stack."""
    source = V44.read_text(encoding="utf-8")
    loader_node = _nested_function(
        source,
        "_render_snapshot_without_stale_date_runtimeerror",
        "snapshot_loader",
    )
    loader_source = ast.get_source_segment(source, loader_node)
    assert loader_source
    assert "raise RuntimeError" not in loader_source
    assert "requested_day = selected_day" in loader_source

    selected_day = date(2026, 10, 17)
    stale_downstream_day = date(2026, 10, 10)
    snapshot = (
        {
            "event_id": "step2-game-1",
            "away_team": "Away",
            "home_team": "Home",
        },
    )
    module = ast.Module(body=[loader_node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"selected_day": selected_day, "snapshot": snapshot}
    exec(compile(module, str(V44), "exec"), namespace)

    result = namespace["snapshot_loader"](stale_downstream_day)

    assert result == list(snapshot)
    assert result is not snapshot
    assert result[0] is not snapshot[0]


def test_step2_successor_preserves_frozen_v42_and_does_not_expand_scope():
    source = V44.read_text(encoding="utf-8")
    v42 = V42.read_text(encoding="utf-8")

    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v43"' in source
    assert "STALE_DOWNSTREAM_DAY_USES_PINNED_SNAPSHOT = True" in source
    assert "snapshot = tuple(dict(game) for game in original_loader(selected_day))" in source
    assert source.count("original_loader(selected_day)") == 1
    assert "snapshot_owner.games_owner._load_games = snapshot_loader" in source
    assert "snapshot_owner.games_owner._load_games = original_loader" in source
    assert "raise RuntimeError(" in v42
    assert "NETWORK_CALLS_ADDED = 0" in source
    assert "NEW_PROVIDER_PATHS_ADDED = 0" in source
    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "MAY_MODIFY_PAGE2 = False" in source


def test_step2_router_keeps_v43_owner_and_installs_v44_runtime_seam():
    router = ROUTER.read_text(encoding="utf-8")
    assert 'PAGE1_NATIVE_ROUTE = "cfb_game_total_clean_page_v43"' in router
    assert "import cfb_game_total_clean_page_v42 as snapshot_owner" in router
    assert "import cfb_game_total_clean_page_v44 as runtime_repair" in router
    assert (
        "snapshot_owner.render_game_total_hub = "
        "runtime_repair._render_snapshot_without_stale_date_runtimeerror"
    ) in router
    assert "snapshot_owner.render_game_total_hub = original_snapshot_render" in router
    assert 'PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"' in router
