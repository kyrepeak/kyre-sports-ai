from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "wnba_pra_player_intelligence_v2_step4.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "streamlit_memory_lazy_router_wnba_nav_v2_step4.py").read_text(encoding="utf-8")
STEP3 = (ROOT / "wnba_pra_game_center_v2_step3.py").read_text(encoding="utf-8")
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


def test_step4_keeps_network_and_consumer_modules_lazy():
    imports = _top_imports(PAGE)
    assert "wnba_api_client_v1" not in imports
    assert "wnba_streamlit_consumer_v2" not in imports
    assert "sports_api" not in imports
    assert "from wnba_api_client_v1 import KyreWNBAAPIClient" in PAGE
    assert "from wnba_streamlit_consumer_v2 import normalize_consumer_payload" in PAGE


def test_step4_two_parallel_read_contract_is_bounded():
    assert "ThreadPoolExecutor(max_workers=2)" in PAGE
    assert "pool.submit(_read_consumer)" in PAGE
    assert "pool.submit(_read_history, int(player_id))" in PAGE
    assert "API_TIMEOUT_SECONDS = 5.0" in PAGE
    assert "API_ATTEMPTS = 1" in PAGE
    assert "CACHE_TTL_SECONDS = 60" in PAGE
    assert '"network_reads_per_uncached_render_max": 2' in PAGE
    assert '"network_reads_parallel": True' in PAGE


def test_step4_does_not_run_model_sportsbook_or_monte_carlo():
    for token in (
        '"streamlit_projection_runs": 0',
        '"streamlit_sportsbook_calls": 0',
        '"streamlit_qualification_runs": 0',
        '"streamlit_ranking_runs": 0',
        '"streamlit_monte_carlo_runs": 0',
        '"projection_math_changed": False',
        '"market_math_changed": False',
        '"sportsbook_projection_influence": 0.0',
        '"missing_context_fails_closed_to_na": True',
    ):
        assert token in PAGE


def test_step4_exact_pra_card_is_exact_identity_only():
    assert 'pid == int(player_id)' in PAGE
    assert '_text(player.get("game_id")) == str(game_id)' in PAGE
    assert '_text(prop.get("stat")).casefold() == "pra"' in PAGE
    assert '"ambiguous_exact_pra_cards"' in PAGE
    assert '"no_qualified_exact_pra_card"' in PAGE


def test_step4_contains_required_intelligence_surface():
    for token in (
        "Final Qualified Decision",
        "MODEL",
        "NO-VIG",
        "EDGE",
        "EV ROI",
        "MC RUNS",
        "Recent Form",
        "Matchup + Pace",
        "Minutes, Role, Usage + Availability",
        "Same-Opponent H2H Context",
        "Advanced diagnostics",
        "NO QUALIFIED PRA CARD",
        "N/A — not exposed by read-only payload",
        "N/A — not carried into frozen Step-3 snapshot",
    ):
        assert token in PAGE


def test_step4_reuses_frozen_step3_and_back_navigation():
    assert "return slate.render_slate_page()" in PAGE
    assert "return game_center.render_game_center(state)" in PAGE
    assert "navigation.go_to_game(game_id)" in PAGE
    assert '"step": "3/7"' in STEP3


def test_step4_router_freezes_prior_layers_and_other_sports():
    assert 'FROZEN_NAVIGATION = "wnba_pra_navigation_v2_step1"' in ROUTER
    assert 'FROZEN_SLATE = "wnba_pra_slate_v2_step2"' in ROUTER
    assert 'FROZEN_GAME_CENTER = "wnba_pra_game_center_v2_step3"' in ROUTER
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"' in ROUTER
    assert 'OWNED_MARKET = "PRA"' in ROUTER
    assert "return frozen_renderer(market)" in ROUTER
    assert "MAY_MODIFY_WNBA_MODEL = False" in ROUTER
    assert "MAY_MODIFY_OTHER_SPORTS = False" in ROUTER


def test_app_activates_step4_and_preserves_step3_freeze_marker():
    assert "from streamlit_memory_lazy_router_wnba_nav_v2_step4 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen WNBA Navigation V2 Step 3 compatibility" in APP
