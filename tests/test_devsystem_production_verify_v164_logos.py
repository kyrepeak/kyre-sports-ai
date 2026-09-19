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
    assert 'REQUIRED_HEARTBEAT = "CFB_GAME_TOTAL_V165_STEP4_MATCHUP_ACTIVE"' in source
    assert 'REQUIRED_PATCH_MARKER = "CFB_GAME_TOTAL_V164_BLANK_EVENT_ID_HANDOFF_PATCH_ACTIVE"' in source
    assert "_wait_for_v164_patch_deployment" in source
    assert "page.reload(" in source
    assert "time.monotonic()" in source
    assert 'CERT_DATE = "2026-09-18"' in source
    assert 'CERT_EVENT_ID = "401858226"' in source
    assert 'AWAY_TEAM = "Miami"' in source
    assert 'AWAY_TEAM_ID = "2390"' in source
    assert 'HOME_TEAM = "Wake Forest"' in source
    assert 'HOME_TEAM_ID = "154"' in source
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
    wait_block = source.split("def _wait_for_v164_patch_deployment", 1)[1].split(
        "def _assert_step1_identity", 1
    )[0]
    assert "REQUIRED_STEP1_PROFILE_MARKER in dom_text" not in wait_block
    assert "if REQUIRED_STEP1_PROFILE_MARKER not in body:" in source
    assert "missing Step 1 exact-profile marker" in source



def test_v164_deployment_gate_uses_step5_dom_marker():
    source = VERIFIER.read_text(encoding="utf-8")
    wait_block = source.split("def _wait_for_v164_patch_deployment", 1)[1].split(
        "def _assert_step1_identity", 1
    )[0]
    assert "STEP5_ROOT_SELECTOR" in wait_block
    assert 'get_attribute("data-step5-marker")' in wait_block
    assert "last_marker == REQUIRED_STEP5_MARKER" in wait_block
    assert "REQUIRED_HEARTBEAT in dom_text" not in wait_block
    assert "REQUIRED_PATCH_MARKER in dom_text" not in wait_block
    assert "REQUIRED_STEP5_MARKER in dom_text" not in wait_block


def test_v176_step5_root_selector_is_marker_specific():
    source = VERIFIER.read_text(encoding="utf-8")
    assert "STEP5_ROOT_SELECTOR = (" in source
    assert 'details.gt168-step5[data-testid="gt157-step-5"]' in source
    assert 'f\'[data-step5-marker="{REQUIRED_STEP5_MARKER}"]\'' in source
    wait_block = source.split("def _wait_for_v164_patch_deployment", 1)[1].split(
        "def _assert_step1_identity", 1
    )[0]
    assert "step5_roots = frame.locator(STEP5_ROOT_SELECTOR)" in wait_block
    assert "if last_root_count >= 1:" in wait_block
    step5_block = source.split("def _assert_step5_pace", 1)[1].split(
        "def verify_live_v164", 1
    )[0]
    assert "step = frame.locator(STEP5_ROOT_SELECTOR)" in step5_block


def test_v164_production_verifier_waits_for_full_streamlit_logo_surface():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'images.nth(0).wait_for(state="attached", timeout=render_timeout_ms)' in source
    assert 'images.nth(1).wait_for(state="attached", timeout=render_timeout_ms)' in source
    assert 'step.wait_for(state="attached", timeout=30000)' in source



def test_v164_production_verifier_requires_step2_performance_profile_surface():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'REQUIRED_STEP2_MARKER = "CFB_GAME_TOTAL_STEP2_PERFORMANCE_PROFILE_V2_ACTIVE"' in source
    assert "REQUIRED_STEP2_MARKER in dom_text" not in source.split(
        "def _wait_for_v164_patch_deployment", 1
    )[1].split("def _assert_step1_identity", 1)[0]
    assert "if REQUIRED_STEP2_MARKER not in body:" in source
    assert "_assert_step2_performance_profile" in source
    assert 'details[data-testid="gt157-step-2"]' in source
    assert 'data-testid="gt167-step2-away"' in source
    assert 'data-testid="gt167-step2-home"' in source
    assert 'data-testid="gt167-step2-insights"' in source
    assert 'data-testid="gt167-step2-summary"' in source
    assert '"img.gt167-logo"' in source
    assert 'state != "READY"' in source
    assert "Step 2 certified matchup must be fully READY" in source
    assert "Step 2 READY contains blank universal metric values" in source
    assert "Step 2 READY must not render a Data still limited warning" in source
    assert "Step 2 {side_name} READY record is stale/empty" in source
    assert '"0-0", "0-0-0"' in source
    assert '"step2_team_performance_profile": step2' in source



def test_v164_step2_required_text_check_is_case_normalized():
    source = VERIFIER.read_text(encoding="utf-8")
    assert "live_text_upper = text.upper()" in source
    assert "label.upper() not in live_text_upper" in source



def test_v164_production_verifier_requires_step3_current_form_surface():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'REQUIRED_STEP3_MARKER = "CFB_GAME_TOTAL_STEP3_CURRENT_FORM_OPPONENT_QUALITY_ACTIVE"' in source
    assert "REQUIRED_STEP3_MARKER in dom_text" not in source.split(
        "def _wait_for_v164_patch_deployment", 1
    )[1].split("def _assert_step1_identity", 1)[0]
    assert "if REQUIRED_STEP3_MARKER not in body:" in source
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
    assert 'REQUIRED_STEP4_MARKER = "CFB_GAME_TOTAL_V165_STEP4_MATCHUP_ACTIVE"' in source
    assert 'REQUIRED_STEP4_DEPLOYMENT_MARKER = "CFB_GAME_TOTAL_STEP4_MULTISOURCE_FULL_COVERAGE_ACTIVE"' in source
    assert 'REQUIRED_STEP4_VISUAL_MARKER = "CFB_GAME_TOTAL_STEP4_V166_VISUAL_TARGET_ACTIVE"' in source
    assert 'REQUIRED_STEP4_GRADE_MARKER = "CFB_GAME_TOTAL_STEP4_V167_REAL_GRADES_ACTIVE"' in source
    wait_block = source.split("def _wait_for_v164_patch_deployment", 1)[1].split(
        "def _assert_step1_identity", 1
    )[0]
    assert "REQUIRED_STEP4_MARKER in dom_text" not in wait_block
    assert "REQUIRED_STEP4_DEPLOYMENT_MARKER in dom_text" not in wait_block
    assert "REQUIRED_STEP4_VISUAL_MARKER in dom_text" not in wait_block
    assert "REQUIRED_STEP4_GRADE_MARKER in dom_text" not in wait_block
    assert "if REQUIRED_STEP4_MARKER not in body:" in source
    assert "if REQUIRED_STEP4_VISUAL_MARKER not in body:" in source
    assert "if REQUIRED_STEP4_GRADE_MARKER not in body:" in source
    assert "_assert_step4_matchup" in source
    assert 'details[data-testid="gt157-step-4"]' in source
    assert 'data-testid="gt165-step4-away-off-home-def"' in source
    assert 'data-testid="gt165-step4-home-off-away-def"' in source
    assert 'data-testid="gt165-step4-source-integrity"' in source
    assert 'data-testid="gt165-step4-advanced-integrity"' in source
    assert '"img.gt165-logo"' in source
    assert '"step4_matchup": step4' in source
    assert "Step 4 V165 Matchup must render expanded by default" in source
    assert "v165_step4_verified" in source
    assert '"Pass Yds/G"' in source
    assert '"Rush Yds/G"' in source
    assert '"3rd Down"' in source
    assert '"Red Zone"' in source
    assert '"Turnover Pressure"' in source
    assert 'state != "READY"' in source
    assert 'get_attribute("data-step4-coverage")' not in source
    assert 'coverage != "100"' not in source
    assert 'step.locator(".gt165-metric.limited").count()' in source
    assert '"VISIBLE MATCHUP COVERAGE: 100%"' in source
    assert '"CFBSTATS"' in source
    assert '"MULTI-SOURCE"' in source
    assert '"coverage": coverage' not in source
    assert '"limited_tiles": limited_tiles' in source

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



def test_v164_step3_failure_prints_live_hydration_diagnostics():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'get_attribute("data-step3-diag")' in source
    assert "diag={diag_attr[:9000]!r}" in source


def test_v164_step4_completeness_checks_are_scoped_to_step4_not_step1():
    source = VERIFIER.read_text(encoding="utf-8")
    step1 = source.split("def _assert_step1_identity", 1)[1].split(
        "def _assert_step2_performance_profile", 1
    )[0]
    step4 = source.split("def _assert_step4_matchup", 1)[1].split(
        "def verify_live_v164", 1
    )[0]

    assert 'get_attribute("data-step4-coverage")' not in step1
    assert 'step.locator(".gt165-metric.limited").count()' not in step1
    assert 'get_attribute("data-step4-coverage")' not in step4
    assert 'coverage != "100"' not in step4
    assert 'state != "READY"' in step4
    assert 'step.locator(".gt165-metric.limited").count()' in step4
    assert 'VISIBLE MATCHUP COVERAGE: 100%' in step4
    assert '"limited_tiles": limited_tiles' in step4


def test_v164_step4_completeness_checks_live_only_inside_step4_verifier():
    source = VERIFIER.read_text(encoding="utf-8")
    step1_start = source.index("def _assert_step1_identity")
    step2_start = source.index("def _assert_step2_performance_profile")
    step4_start = source.index("def _assert_step4_matchup")
    verify_start = source.index("def verify_live_v164")
    step1_block = source[step1_start:step2_start]
    step4_block = source[step4_start:verify_start]
    assert "data-step4-coverage" not in step1_block
    assert ".gt165-metric.limited" not in step1_block
    assert ".gt165-metric.limited" in step4_block
    assert "VISIBLE MATCHUP COVERAGE: 100%" in step4_block
    assert "state != \"READY\"" in step4_block


def test_v164_verifier_has_no_stale_coverage_return_reference():
    source = VERIFIER.read_text(encoding="utf-8")
    assert '"coverage": coverage' not in source
    step4_start = source.index("def _assert_step4_matchup")
    verify_start = source.index("def verify_live_v164")
    step4_block = source[step4_start:verify_start]
    assert '"limited_tiles": limited_tiles' in step4_block


def test_v164_step4_visual_step2_requires_four_matchup_logos():
    source = VERIFIER.read_text(encoding="utf-8")
    step4 = source.split("def _assert_step4_matchup", 1)[1].split(
        "def verify_live_v164", 1
    )[0]
    assert '_assert_exact_logo_count(frame, "img.gt165-logo", 4, "Step 4 V165 matchup")' in step4
    assert '_assert_exact_pair(frame, "img.gt165-logo", "Step 4 V165 matchup")' not in step4
    assert "def _assert_exact_logo_count(" in source
    assert 'for team_id in (AWAY_TEAM_ID, HOME_TEAM_ID):' in source


def test_v164_step4_v167_real_grade_contract_is_hard_gated():
    source = VERIFIER.read_text(encoding="utf-8")
    step4 = source.split("def _assert_step4_matchup", 1)[1].split(
        "def verify_live_v164", 1
    )[0]
    assert 'get_attribute("data-step4-grade-marker")' in step4
    assert "Step 4 grade marker mismatch" in step4
    assert 'get_attribute("data-grade")' in step4
    assert 'allowed_grades = {"A", "A-", "B+", "B", "C+", "C", "D"}' in step4
    assert "Step 4 READY expected 12 explicit grades" in step4
    assert "Step 4 READY contains placeholder/invalid grades" in step4
    assert '"grades": grades' in step4
    assert '"v167_step4_real_grades_verified": True' in step4


def test_v164_step4_v166_visual_freeze_contract_is_hard_gated():
    source = VERIFIER.read_text(encoding="utf-8")
    step4 = source.split("def _assert_step4_matchup", 1)[1].split(
        "def verify_live_v164", 1
    )[0]
    assert 'get_attribute("data-step4-visual-marker")' in step4
    assert "Step 4 visual marker mismatch" in step4
    assert '"coverage_pills": 1' in step4
    assert '"matchup_ribbons": 2' in step4
    assert '"team_headers": 4' in step4
    assert '"vs_badges": 2' in step4
    assert '"stat_tiles": 12' in step4
    assert '"edge_cards": 2' in step4
    assert '"risk_cards": 2' in step4
    assert '"impact_cards": 2' in step4
    assert '"integrity_icons": 2' in step4
    assert "Step 4 V166 visual anatomy mismatch" in step4
    assert '"v166_step4_visual_verified": True' in step4



def test_v164_waits_for_step5_dom_then_runs_strict_surface_assertions():
    source = VERIFIER.read_text(encoding="utf-8")
    wait_block = source.split("def _wait_for_v164_patch_deployment", 1)[1].split(
        "def _assert_step1_identity", 1
    )[0]
    assert "STEP5_ROOT_SELECTOR" in wait_block
    assert 'get_attribute("data-step5-marker")' in wait_block
    assert "last_marker == REQUIRED_STEP5_MARKER" in wait_block

    live_block = source.split("def verify_live_v164", 1)[1]
    assert "if REQUIRED_HEARTBEAT not in body:" in live_block
    assert "if REQUIRED_PATCH_MARKER not in body:" in live_block
    assert "if REQUIRED_STEP1_MARKER not in body:" in live_block
    assert "if REQUIRED_STEP2_MARKER not in body:" in live_block
    assert "if REQUIRED_STEP3_MARKER not in body:" in live_block
    assert "if REQUIRED_STEP4_MARKER not in body:" in live_block
    assert "if REQUIRED_STEP5_MARKER not in body:" not in live_block

    step5 = source.split("def _assert_step5_pace", 1)[1].split(
        "def verify_live_v164", 1
    )[0]
    assert 'get_attribute("data-step5-data-marker")' in step5
    assert 'get_attribute("data-step5-visual-marker")' in step5


def test_v164_step5_v168_pace_surface_is_hard_gated():
    source = VERIFIER.read_text(encoding="utf-8")
    assert 'REQUIRED_STEP5_MARKER = "CFB_GAME_TOTAL_STEP5_PACE_POSSESSIONS_ACTIVE"' in source
    assert 'REQUIRED_STEP5_DATA_MARKER = "CFB_GAME_TOTAL_STEP5_NCAA_PBP_MULTISOURCE_ACTIVE"' in source
    assert 'REQUIRED_STEP5_VISUAL_MARKER = "CFB_GAME_TOTAL_STEP5_V168_VISUAL_TARGET_ACTIVE"' in source
    assert "def _assert_step5_pace(frame)" in source
    step5 = source.split("def _assert_step5_pace", 1)[1].split(
        "def verify_live_v164", 1
    )[0]
    assert "STEP5_ROOT_SELECTOR" in step5
    assert 'get_attribute("data-step5-marker")' in step5
    assert 'get_attribute("data-step5-data-marker")' in step5
    assert 'get_attribute("data-step5-visual-marker")' in step5
    assert 'data-testid="gt168-step5-stat-tile"' in step5
    assert "Step 5 expected 12 pace/possession tiles" in step5
    assert 'get_attribute("data-step5-state")' in step5
    assert 'state != "READY"' in step5
    assert 'get_attribute("data-step5-coverage")' in step5
    assert "coverage != 100" in step5
    assert 'get_attribute("data-ready")' in step5
    assert "Step 5 READY contains incomplete pace tiles" in step5
    assert 'get_attribute("data-step5-away-pbp-delivery")' in step5
    assert 'get_attribute("data-step5-home-pbp-delivery")' in step5
    assert '"sportsdataverse_github_raw"' in step5
    assert 'get_attribute("data-step5-away-pbp-games")' in step5
    assert 'get_attribute("data-step5-home-pbp-games")' in step5
    assert "Step 5 did not prove SportsDataverse PBP delivery for both teams" in step5
    assert "Step 5 requires at least one SportsDataverse completed game per team" in step5
    assert '"away_pbp_delivery": away_delivery' in step5
    assert '"home_pbp_delivery": home_delivery' in step5
    assert '"away_pbp_games": away_pbp_games' in step5
    assert '"home_pbp_games": home_pbp_games' in step5
    assert 'if "DATA LIMITED" in live_upper' in step5
    assert '"PACE & EXPECTED POSSESSIONS"' in step5
    assert '"EXPECTED GAME ENVIRONMENT"' in step5
    assert '"MATCHUP READ"' in step5
    assert '"BIGGEST ACCELERATOR"' in step5
    assert '"BIGGEST BRAKE"' in step5
    assert '"O/U IMPACT"' in step5
    assert '"DATA CONFIDENCE"' in step5
    assert '"pace_coverage": coverage' in step5
    assert '"v168_step5_verified": True' in step5
    assert '"step5_pace_expected_possessions": step5' in source



def test_v178_production_verifier_requires_nonblocking_step5_freshness():
    source = VERIFIER.read_text(encoding="utf-8")
    assert (
        'REQUIRED_STEP5_DEPLOYMENT_MARKER = '
        '"CFB_GAME_TOTAL_STEP5_V178_NONBLOCKING_ACTIVE"'
    ) in source
    assert 'data-step5-deployment-marker' in source
    assert "REQUIRED_STEP5_DEPLOYMENT_MARKER in last_body" in source
    assert "v178_heartbeat_seen" in source
    step5_block = source.split("def _assert_step5_pace", 1)[1].split(
        "def verify_live_v164", 1
    )[0]
    assert 'get_attribute("data-step5-deployment-marker")' in step5_block
    assert "Step 5 V178 deployment marker mismatch" in step5_block



def test_v185_step5_production_allows_verified_sportsdataverse_snapshot_delivery():
    source = VERIFIER.read_text(encoding="utf-8")
    step5_block = source.split("def _assert_step5_pace", 1)[1].split(
        "def verify_live_v164", 1
    )[0]
    assert '"sportsdataverse_github_raw"' in step5_block
    assert '"sportsdataverse_github_raw_snapshot"' in step5_block
