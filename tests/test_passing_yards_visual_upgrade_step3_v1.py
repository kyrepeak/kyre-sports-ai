from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(name: str) -> str:
    return (ROOT / name).read_text()

def test_step3_is_presentation_only_over_step2() -> None:
    body = read("nfl_passing_yards_hub_v48.py")
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v47"' in body
    assert "PRESENTATION_ONLY = True" in body
    assert "MAY_MODIFY_PROJECTION = False" in body
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in body

def test_step3_reuses_frozen_payloads_for_steps_7_8_9() -> None:
    body = read("nfl_passing_yards_hub_v48.py")
    assert '_piece(captured, "projection", index)' in body
    assert '_piece(captured, "context", index)' in body
    assert '_piece(captured, "distribution", index)' in body
    assert '_evidence_step(7, "Baseline Projection", projection)' in body
    assert '_evidence_step(8, "Context + Uncertainty", context)' in body
    assert '_evidence_step(9, "Distribution + Probability", distribution)' in body

def test_step3_has_premium_evidence_board_contract() -> None:
    body = read("nfl_passing_yards_hub_v48.py")
    assert 'data-passing-yards-evidence="v48"' in body
    assert "Steps 7–9 Evidence Board" in body
    assert 'data-step="{step}"' in body
    assert "STEPS 7-9 VERIFIED" in body

def test_step3_replaces_only_step2_final_builder() -> None:
    body = read("nfl_passing_yards_hub_v48.py")
    assert "original_builder = prior._premium_command_center_html" in body
    assert "prior._premium_command_center_html = _steps_7_9_command_center_html" in body
    assert "prior._premium_command_center_html = original_builder" in body

def test_step3_router_advances_only_passing_yards() -> None:
    body = read("streamlit_memory_lazy_router_v194.py")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v193"' in body
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v48"' in body
    assert 'if sport != "NFL" or market != PASSING_MARKET:' in body
    assert "return prior.render_app()" in body

def test_step3_app_boots_v194() -> None:
    app = read("app.py")
    assert "from streamlit_memory_lazy_router_v194 import record_bootstrap_import_ms, render_app" in app
