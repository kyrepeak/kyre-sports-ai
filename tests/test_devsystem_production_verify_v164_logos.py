from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "devsystem" / "production_verify_v164_logos.py"


def test_v164_production_verifier_preserves_v163_gate_and_exact_logo_checks():
    source = VERIFIER.read_text(encoding="utf-8")
    assert "from devsystem import production_verify_v5 as v163" in source
    assert "prior = v163.run()" in source
    assert 'REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V164_PRODUCTION_ACTIVE"' in source
    assert 'CERT_EVENT_ID = "401869940"' in source
    assert 'AWAY_TEAM_ID = "324"' in source
    assert 'HOME_TEAM_ID = "48"' in source
    assert 'img.gt159-logo' in source
    assert 'img.gt160-evidence-logo' in source
    assert "naturalWidth" in source
    assert "CFB_GAME_TOTAL_V164_PRODUCTION_LOGOS_GREEN" in source
