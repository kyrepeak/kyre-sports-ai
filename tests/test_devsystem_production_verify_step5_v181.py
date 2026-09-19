from __future__ import annotations

import inspect

from devsystem import production_verify_step5_v181 as verifier


def test_v181_reuses_authoritative_step5_production_contract():
    source = inspect.getsource(verifier.verify_live_step5)
    assert "_wait_for_v164_patch_deployment" in source
    assert "_assert_step5_pace" in source
    assert "REQUIRED_STEP5_DEPLOYMENT_MARKER" in source
    assert '"READY"' in source
    assert "pace_coverage" in source
    assert "tile_count" in source
    assert "v168_step5_verified" in source


def test_v181_does_not_gate_on_frozen_steps_1_through_4():
    source = inspect.getsource(verifier.verify_live_step5)
    assert "_assert_step1_identity" not in source
    assert "_assert_step2_performance_profile" not in source
    assert "_assert_step3_current_form" not in source
    assert "_assert_step4_matchup" not in source


def test_v181_green_marker_is_stable():
    assert verifier.GREEN_MARKER == "CFB_GAME_TOTAL_V181_STEP5_PRODUCTION_GREEN"



def test_v184_cert_follows_current_live_event_instead_of_stale_fixed_event():
    source = inspect.getsource(verifier.verify_live_step5)
    assert "CERT_EVENT_ID" not in source
    assert "CERT_DATE" not in source
    assert "ROUTE_QUERY_SPORT" in source
    assert "ROUTE_QUERY_MARKET" in source
    assert "_event_from_url(page.url)" in source
    assert "_event_from_url(frame.url)" in source
    assert "current live Game Total event did not persist" in source
