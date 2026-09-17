from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "devsystem" / "production_verify_v5.py"
WORKFLOW = ROOT / ".github" / "workflows" / "devsystem-production-verification.yml"


def _read(path: Path) -> str:
    assert path.exists(), f"missing required V164 production proof file: {path}"
    return path.read_text(encoding="utf-8")


def test_v5_requires_v160_v164_and_frame_aware_event_identity():
    source = _read(VERIFIER)
    assert 'FROZEN_VERIFIER = "devsystem.production_verify_v3"' in source
    assert 'SUPERSEDED_VERIFIER = "devsystem.production_verify_v4"' in source
    assert 'EXPECTED_ROUTER = "streamlit_memory_lazy_router_v160"' in source
    assert 'GAME_TOTAL_REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V164_PRODUCTION_ACTIVE"' in source
    assert 'EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"' in source
    assert "frame.url" in source
    assert "prior.run(artifact_dir=artifacts)" in source


def test_v5_requires_deployed_render_official_games_identity_contract():
    source = _read(VERIFIER)
    assert 'OFFICIAL_GAMES_ENDPOINT = "/api/v1/cfb/identity/official-games"' in source
    assert '"synthetic_ids"' in source
    assert '"sportsbook_projection_influence_pct"' in source
    assert "0.0" in source
    assert "selected official event_id was not persisted" in source


def test_production_workflow_runs_v5_and_self_tests_it():
    source = _read(WORKFLOW)
    assert 'devsystem/production_verify_v5.py' in source
    assert 'tests/test_devsystem_production_verify_v5.py' in source
    assert 'python devsystem/production_verify_v5.py' in source
