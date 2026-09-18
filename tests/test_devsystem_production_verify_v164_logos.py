from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "devsystem" / "production_verify_v164_logos.py"


def test_v164_production_verifier_preserves_v163_gate_and_exact_logo_checks():
    source = VERIFIER.read_text(encoding="utf-8")
    assert "from devsystem import production_verify_v5 as v163" in source
    assert "prior = v163.run()" not in source
    assert '"required_separate_gate": "DevSystem production verification V5"' in source
    assert "_wait_for_top_level_selection" in source
    assert "_event_from_url(page.url)" in source
    assert "_wait_for_event_query" not in source
    assert 'REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V164_PRODUCTION_ACTIVE"' in source
    assert 'REQUIRED_PATCH_MARKER = "CFB_GAME_TOTAL_V164_BLANK_EVENT_ID_HANDOFF_PATCH_ACTIVE"' in source
    assert "_wait_for_v164_patch_deployment" in source
    assert "page.reload(" in source
    assert "time.monotonic()" in source
    assert 'CERT_EVENT_ID = "401869940"' in source
    assert 'AWAY_TEAM_ID = "324"' in source
    assert 'HOME_TEAM_ID = "48"' in source
    assert 'img.gt159-logo' in source
    assert 'img.gt160-evidence-logo' in source
    assert "naturalWidth" in source
    assert "CFB_GAME_TOTAL_V164_PRODUCTION_LOGOS_GREEN" in source



def test_v164_production_verifier_requires_complete_step1_identity_surface():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'REQUIRED_STEP1_MARKER = "CFB_GAME_TOTAL_STEP1_TEAM_IDENTITY_ACCORDION_ACTIVE"' in source
    assert "_assert_step1_identity" in source
    assert 'details[data-testid="gt157-step-1"]' in source
    assert 'data-testid="gt165-step1-away"' in source
    assert 'data-testid="gt165-step1-home"' in source
    assert '"img.gt165-idlogo"' in source
    assert '"Needs data:" in text' in source
    assert 'state != "READY"' in source
    assert '"IDENTITY VERIFIED"' in source



def test_v164_production_verifier_waits_for_exact_step1_profile_patch():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'REQUIRED_STEP1_PROFILE_MARKER = "CFB_GAME_TOTAL_STEP1_FAST_EXACT_PROFILE_ACTIVE"' in source
    assert "REQUIRED_STEP1_PROFILE_MARKER in dom_text" in source
    assert "missing Step 1 exact-profile marker" in source



def test_v164_deployment_gate_reads_hidden_markers_from_dom_text():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'frame.locator("body").text_content()' in source
    assert "REQUIRED_STEP1_PROFILE_MARKER in dom_text" in source
    assert "REQUIRED_STEP1_MARKER in dom_text" in source
    assert "REQUIRED_PATCH_MARKER in dom_text" in source
    assert "return frame, dom_text, scans" in source


def test_v164_production_verifier_waits_for_full_streamlit_logo_surface():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'images.nth(0).wait_for(state="attached", timeout=render_timeout_ms)' in source
    assert 'images.nth(1).wait_for(state="attached", timeout=render_timeout_ms)' in source
    assert 'step.wait_for(state="attached", timeout=30000)' in source



def test_v164_production_verifier_requires_step2_performance_profile_surface():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'REQUIRED_STEP2_MARKER = "CFB_GAME_TOTAL_STEP2_PERFORMANCE_PROFILE_V2_ACTIVE"' in source
    assert "REQUIRED_STEP2_MARKER in dom_text" in source
    assert "_assert_step2_performance_profile" in source
    assert 'details[data-testid="gt157-step-2"]' in source
    assert 'data-testid="gt167-step2-away"' in source
    assert 'data-testid="gt167-step2-home"' in source
    assert 'data-testid="gt167-step2-insights"' in source
    assert 'data-testid="gt167-step2-summary"' in source
    assert '"img.gt167-logo"' in source
    assert '"READY", "CHECK"' in source
    assert '"step2_team_performance_profile": step2' in source



def test_v164_step2_required_text_check_is_case_normalized():
    source = VERIFIER.read_text(encoding="utf-8")
    assert "live_text_upper = text.upper()" in source
    assert "label.upper() not in live_text_upper" in source



def test_v164_production_verifier_requires_step3_current_form_surface():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'REQUIRED_STEP3_MARKER = "CFB_GAME_TOTAL_STEP3_CURRENT_FORM_OPPONENT_QUALITY_ACTIVE"' in source
    assert "REQUIRED_STEP3_MARKER in dom_text" in source
    assert "_assert_step3_current_form" in source
    assert 'details[data-testid="gt157-step-3"]' in source
    assert 'data-testid="gt168-step3-away"' in source
    assert 'data-testid="gt168-step3-home"' in source
    assert 'data-testid="gt168-step3-comparison"' in source
    assert 'data-testid="gt168-step3-takeaways"' in source
    assert 'data-testid="gt168-step3-edge"' in source
    assert '"img.gt168-logo"' in source
    assert '"step3_current_form_opponent_quality": step3' in source


def test_v164_step3_required_text_check_is_case_normalized():
    source = VERIFIER.read_text(encoding="utf-8")
    assert "label.upper() not in live_text_upper" in source



def test_v164_production_verifier_requires_step4_matchup_surface():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'REQUIRED_STEP4_MARKER = "CFB_GAME_TOTAL_STEP4_MATCHUP_OFF_DEF_PASS_RUSH_EPA_ACTIVE"' in source
    assert "REQUIRED_STEP4_MARKER in dom_text" in source
    assert "_assert_step4_matchup" in source
    assert 'details[data-testid="gt157-step-4"]' in source
    assert 'data-testid="gt170-step4-away-off-home-def"' in source
    assert 'data-testid="gt170-step4-home-off-away-def"' in source
    assert 'data-testid="gt170-step4-matchup-read"' in source
    assert 'data-testid="gt170-step4-epa-integrity"' in source
    assert '"img.gt170-logo"' in source
    assert '"step4_matchup": step4' in source
    assert "Step 4 Matchup must render collapsed by default" in source



def test_v164_step3_production_proof_locks_live_completeness_contract():
    source = VERIFIER.read_text(encoding="utf-8")
    assert '"INSUFFICIENT SAMPLE" in live_text_upper' in source
    assert 'game_rows_by_side' in source
    assert 'game_count < 2' in source
    assert 'expected at least 2 verified completed-game' in source
    assert 'NO VERIFIED COMPLETED-GAME ROWS' in source
    assert 'Opponent Quality expected 5 rows' in source
    assert 'opponent_quality_values' in source
    assert 'state != "READY"' in source
    assert 'certified matchup must be fully READY' in source
    assert 'Step 3 READY contains blank Opponent Quality values' in source
    assert 'data-testid="gt168-step3-status-reason"' in source
    assert 'Step 3 READY must not render a CHECK/DATA LIMITED reason' in source
