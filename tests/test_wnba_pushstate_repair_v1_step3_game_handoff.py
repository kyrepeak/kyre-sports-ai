from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step7_final_integration.py"


def _function_body(source: str, name: str, next_name: str) -> str:
    return source.split(f"def {name}", 1)[1].split(f"def {next_name}", 1)[0]


def test_deep_route_handoff_is_session_only_after_jump_consumption():
    source = RUNTIME.read_text(encoding="utf-8")
    body = _function_body(source, "_pin_deep_wnba_session_route", "render_app")
    assert "navigation.PAGE_GAME" in body
    assert "navigation.PAGE_PLAYER" in body
    assert "st.session_state[deep_route.SHELL_SPORT_SESSION_KEY]" in body
    assert "st.session_state[deep_route.SHELL_MARKET_SESSION_KEY]" in body
    assert "st.query_params" not in body


def test_final_integration_temporarily_overrides_only_deep_shell_pin():
    source = RUNTIME.read_text(encoding="utf-8")
    assert "original_deep_pin = deep_route._pin_deep_wnba_shell_route" in source
    assert "deep_route._pin_deep_wnba_shell_route = _pin_deep_wnba_session_route" in source
    assert "deep_route._pin_deep_wnba_shell_route = original_deep_pin" in source
    assert 'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback"' in source
