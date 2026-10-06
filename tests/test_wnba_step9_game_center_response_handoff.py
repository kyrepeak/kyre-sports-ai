from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_step9_game_handoff.py"
APP = ROOT / "app.py"


def _overlay_source() -> str:
    return OVERLAY.read_text(encoding="utf-8") if OVERLAY.exists() else ""


def test_step9_game_center_handoff_reuses_exact_prefetch_payload():
    source = _overlay_source()

    assert OVERLAY.exists(), "Step-9 Game Center response-handoff overlay is missing"
    assert "FROZEN_PARENT_ROUTER = \"streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration\"" in source
    assert "NETWORK_CALLS_ADDED = 0" in source
    assert "PROJECTION_MATH_CHANGED = False" in source
    assert "MODEL_MATH_CHANGED = False" in source
    assert "MARKET_MATH_CHANGED = False" in source
    assert "DATA_MEANING_CHANGED = False" in source
    assert "def _prefetch_game_with_handoff(" in source
    assert "performance._FROZEN_GAME_LOADER(*args)" in source
    assert "def _observe_game_center_with_handoff(" in source
    assert "return deepcopy(dict(payload))" in source
    assert "performance._prefetch_game = _prefetch_game_with_handoff" in source
    assert "performance._observe_game_center = _observe_game_center_with_handoff" in source
    assert "performance._prefetch_game = original_prefetch_game" in source
    assert "performance._observe_game_center = original_observe_game_center" in source


def test_step9_overlay_does_not_reimplement_basketball_math_or_provider_fetches():
    source = _overlay_source()

    forbidden = (
        "requests.",
        "httpx.",
        "role_projection_for_game(",
        "projected_pts",
        "projected_reb",
        "projected_ast",
        "projected_pra",
        "SPORTSBOOK",
        "monte_carlo",
    )
    assert all(token not in source for token in forbidden)
