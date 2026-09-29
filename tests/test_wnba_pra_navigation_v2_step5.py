from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PERF = (ROOT / "wnba_pra_performance_v2_step5.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "streamlit_memory_lazy_router_wnba_nav_v2_step5.py").read_text(encoding="utf-8")
STEP2 = (ROOT / "wnba_pra_slate_v2_step2.py").read_text(encoding="utf-8")
STEP3 = (ROOT / "wnba_pra_game_center_v2_step3.py").read_text(encoding="utf-8")
STEP4 = (ROOT / "wnba_pra_player_intelligence_v2_step4.py").read_text(encoding="utf-8")
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _top_imports(source: str) -> set[str]:
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_step5_keeps_heavy_data_modules_lazy():
    imports = _top_imports(PERF)
    assert "pandas" not in imports
    assert "numpy" not in imports
    assert "wnba_role_v28" not in imports
    assert "wnba_api_client_v1" not in imports
    assert "sports_api" not in imports


def test_step5_single_rerun_contract_and_known_navigation_keys():
    assert '"native_on_click_single_rerun": True' in PERF
    assert '"explicit_st_rerun_added": False' in PERF
    assert "st.rerun()" not in PERF
    assert 'kwargs["on_click"] = callback' in PERF
    for token in (
        "wnba_nav_v2_step2_open_",
        "wnba_nav_v2_step3_player_",
        "wnba_nav_v2_step3_back_slate",
        "wnba_nav_v2_step4_back_game",
    ):
        assert token in PERF
    # Freeze the upstream key contract so an un-intercepted explicit rerun cannot drift in silently.
    assert 'key=f"wnba_nav_v2_step2_open_{gid}"' in STEP2
    assert 'key=f"wnba_nav_v2_step3_player_{game_id}_{pid}"' in STEP3
    assert 'key="wnba_nav_v2_step3_back_slate"' in STEP3
    assert 'key="wnba_nav_v2_step4_back_game"' in STEP4


def test_step5_exact_selection_prefetch_only():
    for token in (
        '"speculative_prefetch": False',
        '"background_prefetch": False',
        '"prefetch_only_after_explicit_selection": True',
        '"prefetch_targets_per_click_max": 1',
        '"slate_prefetches_game_center": False',
        '"game_center_prefetches_player_before_selection": False',
        '"page3_heavy_model_prefetch": False',
    ):
        assert token in PERF
    assert "_prefetch_game(snapshot)" in PERF
    assert "_prefetch_player(str(game_id), player_id)" in PERF


def test_step5_same_session_split_reuse_suppresses_duplicate_consumer_read():
    assert 'SESSION_CONSUMER_CACHE = "ks_wnba_nav_v2_step5_consumer_cache"' in PERF
    assert 'SESSION_HISTORY_CACHE = "ks_wnba_nav_v2_step5_history_cache"' in PERF
    assert "consumer = _cached_consumer()" in PERF
    assert "history = _cached_history(pid)" in PERF
    assert "if consumer is None and history is None:" in PERF
    assert "if consumer is None:" in PERF
    assert "if history is None:" in PERF
    assert "duplicate_consumer_read_suppressed=bool(consumer_hit and not history_hit)" in PERF
    assert "SESSION_TTL_SECONDS = 60" in PERF


def test_step5_preserves_frozen_steps_and_math():
    for token in (
        '"frozen_steps_1_through_4_modified": False',
        '"streamlit_projection_runs_added": 0',
        '"streamlit_sportsbook_calls_added": 0',
        '"streamlit_monte_carlo_runs_added": 0',
        '"projection_math_changed": False',
        '"market_math_changed": False',
        '"sportsbook_projection_influence": 0.0',
    ):
        assert token in PERF
    assert '"step": "2/7"' in STEP2
    assert '"step": "3/7"' in STEP3
    assert '"step": "4/7"' in STEP4


def test_step5_router_freezes_prior_layers():
    assert 'FROZEN_NAVIGATION = "wnba_pra_navigation_v2_step1"' in ROUTER
    assert 'FROZEN_SLATE = "wnba_pra_slate_v2_step2"' in ROUTER
    assert 'FROZEN_GAME_CENTER = "wnba_pra_game_center_v2_step3"' in ROUTER
    assert 'FROZEN_PLAYER_INTELLIGENCE = "wnba_pra_player_intelligence_v2_step4"' in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"' in ROUTER
    assert "return frozen_renderer(market)" in ROUTER
    assert "MAY_MODIFY_WNBA_MODEL = False" in ROUTER
    assert "MAY_MODIFY_OTHER_SPORTS = False" in ROUTER


def test_app_activates_step5_and_preserves_step4_freeze_marker():
    assert "from streamlit_memory_lazy_router_wnba_nav_v2_step5 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen WNBA Navigation V2 Step 4 compatibility" in APP
