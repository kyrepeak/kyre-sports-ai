from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "devsystem" / "production_verify_v5.py"
WORKFLOW = ROOT / ".github" / "workflows" / "devsystem-production-verification.yml"


def _read(path: Path) -> str:
    assert path.exists(), f"missing required V163 production V5 proof file: {path}"
    return path.read_text(encoding="utf-8")


def test_v5_reads_event_identity_from_outer_or_streamlit_app_frame_url():
    source = _read(VERIFIER)
    assert 'FROZEN_VERIFIER = "devsystem.production_verify_v3"' in source
    assert 'EXPECTED_ROUTER = "streamlit_memory_lazy_router_v159"' in source
    assert 'EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"' in source
    assert "page.url" in source
    assert "matched_frame.url" in source
    assert "_event_id_from_urls" in source


def test_v5_preserves_v163_surface_and_fails_closed_without_event_identity():
    source = _read(VERIFIER)
    assert 'GAME_TOTAL_REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V163_PRODUCTION_ACTIVE"' in source
    assert 'GAME_SELECTOR_REQUIRED_TEXT = "GAMES ON THIS DAY"' in source
    assert "selected ESPN event_id was not persisted" in source
    assert "prior.run(artifact_dir=artifacts)" in source


def test_production_workflow_runs_v5_and_self_tests_it():
    source = _read(WORKFLOW)
    assert 'devsystem/production_verify_v5.py' in source
    assert 'tests/test_devsystem_production_verify_v5.py' in source
    assert 'python devsystem/production_verify_v5.py' in source
