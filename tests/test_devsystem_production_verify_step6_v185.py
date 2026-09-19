from __future__ import annotations

import inspect

from devsystem import production_verify_step6_v185 as verifier


def test_v185_production_verifier_requires_fresh_visual_markers_and_frozen_contract():
    module_source = inspect.getsource(verifier)
    assert "CFB_GAME_TOTAL_V185_STEP6_PRODUCTION_GREEN" in module_source
    assert "CFB_GAME_TOTAL_STEP6_V185_VISUAL_PARITY_ACTIVE" in module_source
    assert "CFB_GAME_TOTAL_STEP6_TARGET_MOCK_PARITY_ACTIVE" in module_source
    assert "frozen._assert_step6(root)" in module_source
    assert "frozen.CERT_CANDIDATES" in module_source
    assert "frozen.CERT_QUERY_KEY" in module_source
    assert "frozen._load_streamlit_url()" in module_source


def test_v185_visual_assertion_locks_target_geometry_and_full_width():
    source = inspect.getsource(verifier._assert_v185_visual)
    assert 'root.locator(".gt185-s6-battlepair").count()' in source
    assert 'root.locator(".gt185-s6-panel.offense").count()' in source
    assert 'root.locator(".gt185-s6-panel.defense").count()' in source
    assert 'root.locator(\'[data-testid="gt185-step6-defense-tile"]\').count()' in source
    assert 'root.locator(".gt185-s6-matchup").count()' in source
    assert 'root.locator(".gt185-s6-env").count()' in source
    assert 'root.locator(".gt185-s6-insights").count()' in source
    assert '"gridColumnStart"' in source
    assert '"gridColumnEnd"' in source
    assert 'width / parent_width < 0.94' in source
    assert '"💥 Scoring Creation"' in source
    assert '"SCORING PREVENTION"' in source
    assert '"SCORING ENVIRONMENT"' in source
    assert '"MATCHUP READ"' in source


def test_v185_wait_gate_cannot_accept_stale_v184_surface():
    source = inspect.getsource(verifier._wait_for_live_v185)
    assert "STEP6_ROOT_SELECTOR" in source
    assert "page.reload" in source
    assert "V185 Step 6 visual-parity root not live yet" in source
    assert verifier.STEP6_VISUAL_MARKER == "CFB_GAME_TOTAL_STEP6_V185_VISUAL_PARITY_ACTIVE"
    assert verifier.STEP6_PARITY_MARKER == "CFB_GAME_TOTAL_STEP6_TARGET_MOCK_PARITY_ACTIVE"
