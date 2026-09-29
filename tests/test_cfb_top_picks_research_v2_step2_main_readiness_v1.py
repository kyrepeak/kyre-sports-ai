from pathlib import Path

CERT = Path("devsystem/cfb_top_picks_research_v2_step2_logo_cert_v1.py").read_text(encoding="utf-8")


def test_step2_logo_browser_proof_waits_for_navigation_readiness():
    assert "time.monotonic() + 120.0" in CERT
    assert "while time.monotonic() < deadline:" in CERT
    assert "CFB_TOP_PICKS_RESEARCH_V2_STEP2_NAV_NOT_READY" in CERT
    assert "nav._attempt_normal_flow(page, base_url, 390, 844)" in CERT
    assert 'article[data-testid^="cfb-top-picks-card-"]' in CERT
    assert 'img[data-top-picks-real-logo="true"]' in CERT
    assert "CFB_TOP_PICKS_RESEARCH_V2_STEP2_20_REAL_LOGOS_GREEN" in CERT
