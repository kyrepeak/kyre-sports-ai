from __future__ import annotations

import inspect

from devsystem import production_verify_step6_v184 as verifier


def test_v184_step6_production_contract_is_strict_and_current_route_driven():
    source = inspect.getsource(verifier.verify_live_step6)
    wait_source = inspect.getsource(verifier._wait_for_live_step6)
    assert "CERT_EVENT_ID" not in source
    assert "CERT_DATE" not in source
    assert "ROUTE_QUERY_SPORT" in source
    assert "ROUTE_QUERY_MARKET" in source
    assert "_event_from_url" in source
    assert "STEP6_ROOT_SELECTOR" in wait_source
    assert "for index, frame in enumerate(page.frames)" in wait_source
    assert "page.reload" in wait_source
    assert "_wait_for_v164_patch_deployment" not in wait_source
    assert "production_verify_v164_logos" not in inspect.getsource(verifier)
    assert "full.v163" not in inspect.getsource(verifier)


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
