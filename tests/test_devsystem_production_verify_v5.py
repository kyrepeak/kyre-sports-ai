from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "devsystem" / "production_verify_v5.py"
WORKFLOW = ROOT / ".github" / "workflows" / "devsystem-production-verification.yml"


def _read(path: Path) -> str:
    assert path.exists(), f"missing V163 production V5 proof file: {path}"
    return path.read_text(encoding="utf-8")


def test_v5_certifies_real_game_click_top_url_and_refresh_persistence():
    source = _read(VERIFIER)
    assert 'FROZEN_VERIFIER = "devsystem.production_verify_v3"' in source
    assert 'EXPECTED_ROUTER = "streamlit_memory_lazy_router_v159"' in source
    assert 'EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"' in source
    assert 'GAME_SELECTOR_REQUIRED_TEXT = "GAMES ON THIS DAY"' in source
    assert "target.click" in source
    assert "page.url" in source
    assert "page.reload" in source
    assert "_selected_link_event" in source
    assert "clicked ESPN event_id was not persisted in top-level URL" in source
    assert "selected ESPN event_id did not survive hard refresh" in source


def test_v5_preserves_frozen_v3_and_v163_surface_contract():
    source = _read(VERIFIER)
    assert 'GAME_TOTAL_REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V163_PRODUCTION_ACTIVE"' in source
    assert "prior.run(artifact_dir=artifacts)" in source
    assert 'result["production_verifier"] = "V5"' in source


def test_production_workflow_runs_v5_and_preserves_v4_marker():
    source = _read(WORKFLOW)
    assert 'devsystem/production_verify_v5.py' in source
    assert 'tests/test_devsystem_production_verify_v5.py' in source
    assert 'python devsystem/production_verify_v5.py' in source
    assert 'python devsystem/production_verify_v4.py' in source
