from __future__ import annotations

import inspect

from devsystem import production_verify_step6_v184 as verifier


def test_v184_step6_production_contract_is_strict_multi_target_and_snapshot_isolated():
    source = inspect.getsource(verifier.verify_live_step6)
    wait_source = inspect.getsource(verifier._wait_for_live_step6)
    scan_source = inspect.getsource(verifier._scan_step6_cert_frame)
    module_source = inspect.getsource(verifier)
    assert "ROUTE_QUERY_SPORT" in source
    assert "ROUTE_QUERY_MARKET" in source
    assert "_event_from_url" in source
    assert "STEP6_ROOT_SELECTOR" in wait_source
    assert "_scan_step6_cert_frame" in wait_source
    assert "CERT_SURFACE_SELECTOR" in scan_source
    assert "STEP6_ROOT_SELECTOR" in scan_source
    assert "cert_count > 0 and root_count > 0" in scan_source
    assert "v163_nav._find_v163_frame" not in wait_source
    assert "page.reload" in wait_source
    assert "_wait_for_v164_patch_deployment" not in wait_source
    assert "_wait_for_top_level_selection" not in wait_source
    assert "production_verify_v164_logos" not in module_source
    assert "production_verify_v5 as v163_nav" not in module_source
    assert "def _scan_step6_cert_frame" in module_source
    assert 'CERT_QUERY_KEY = "ks_cfb_step6_cert"' in module_source
    assert "CFB_GAME_TOTAL_V184_STEP6_CERT_SNAPSHOT_V1_ACTIVE" in module_source
    assert '"401869940"' in module_source
    assert '"401856685"' in module_source
    assert "for index, candidate in enumerate(CERT_CANDIDATES" in source
    assert 'CERT_QUERY_KEY: "1"' in source
    assert 'data-testid="gt184-step6-cert-surface"' in module_source
    assert "CERT_SURFACE_SELECTOR" in source
    assert "event_id != cert_event_id" in source
    assert "selected_date != cert_date" in source


def test_v184_step6_assertion_requires_ready_100_and_12_of_12():
    source = inspect.getsource(verifier._assert_step6)
    assert 'state != "READY"' in source
    assert 'coverage != "100"' in source
    assert 'ready_attr != "12"' in source
    assert "tile_count != 12" in source
    assert "ready_tiles != 12" in source
    assert '"DATA LIMITED" in body_text' in source
    assert '"SPORTSBOOK INFLUENCE 0.0%" not in body_text' in source
    assert '"PROJECTION MUTATION OFF" not in body_text' in source


def test_v184_step6_production_markers_are_stable():
    assert verifier.STEP6_MARKER == "CFB_GAME_TOTAL_STEP6_SCORING_CREATION_ACTIVE"
    assert (
        verifier.STEP6_DEPLOYMENT_MARKER
        == "CFB_GAME_TOTAL_STEP6_V184_DEPLOYMENT_ACTIVE"
    )
    assert verifier.GREEN_MARKER == "CFB_GAME_TOTAL_V184_STEP6_PRODUCTION_GREEN"
