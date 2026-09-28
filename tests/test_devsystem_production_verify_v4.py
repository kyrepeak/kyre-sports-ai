from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "devsystem" / "production_verify_v4.py"
WORKFLOW = ROOT / ".github" / "workflows" / "devsystem-production-verification.yml"


def _read(path: Path) -> str:
    assert path.exists(), f"missing required V163 production proof file: {path}"
    return path.read_text(encoding="utf-8")


def test_v4_requires_exact_v165_router_heartbeat_and_game_selector():
    source = _read(VERIFIER)
    assert 'FROZEN_VERIFIER = "devsystem.production_verify_v3"' in source
    assert 'EXPECTED_ROUTER = "streamlit_memory_lazy_router_v161"' in source
    assert 'GAME_TOTAL_REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V165_STEP4_MATCHUP_ACTIVE"' in source
    assert 'GAME_SELECTOR_REQUIRED_TEXT = "GAMES ON THIS DAY"' in source
    assert 'EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"' in source
    assert "prior.run(artifact_dir=artifacts)" in source


def test_v4_fails_closed_when_v165_surface_is_stale():
    source = _read(VERIFIER)
    assert "GAME_TOTAL_REQUIRED_HEARTBEAT not in" in source
    assert "GAME_SELECTOR_REQUIRED_TEXT not in" in source
    assert "stale Streamlit Game Total V165 deployment" in source


def test_production_workflow_runs_v4_and_self_tests_it():
    source = _read(WORKFLOW)
    assert 'devsystem/production_verify_v4.py' in source
    assert 'tests/test_devsystem_production_verify_v4.py' in source
    assert 'python devsystem/production_verify_v4.py' in source


def test_v4_reads_event_id_from_matched_app_frame_not_outer_shell():
    source = _read(VERIFIER)
    assert "def _query_event_id(target)" in source
    assert "_query_event_id(matched_frame)" in source
    assert "_query_event_id(page)" not in source
    assert "_query_event_id(matched_frame, page)" not in source

    # Regression contract: the outer Community Cloud shell has no event ID,
    # while the matched Streamlit app frame persists the exact ESPN event ID.
    import importlib.util

    spec = importlib.util.spec_from_file_location("production_verify_v4_frame_test", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    class Target:
        def __init__(self, url: str):
            self.url = url

    outer_shell = Target(
        "https://kyre-sports-ai.streamlit.app/?"
        "ks_sport=College+Football&ks_cfb_market=Game+Total"
    )
    matched_frame = Target(
        "https://kyre-sports-ai.streamlit.app/~/+/?"
        "ks_sport=College+Football&ks_cfb_market=Game+Total&"
        "ks_cfb_game_total_event_id=401752992"
    )

    assert module._query_event_id(outer_shell) == ""
    assert module._query_event_id(matched_frame) == "401752992"
