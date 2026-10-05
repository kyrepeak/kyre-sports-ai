from __future__ import annotations

import json

from devsystem import nfl_live_game_repair_step5_final_cert_v1 as cert


def test_step5_scope_is_final_proof_only():
    assert cert.MISSION_STEP == "5/5"
    assert cert.MAY_MODIFY_PRODUCT_RUNTIME is False
    assert cert.MAY_MODIFY_ROUTER is False
    assert cert.MAY_MODIFY_PROJECTION is False
    assert cert.MAY_MODIFY_PROBABILITY is False
    assert cert.MAY_MODIFY_RANKING is False
    assert cert.MAY_MODIFY_SPORTSBOOK is False
    assert cert.API2_USED is False


def test_step5_repository_contract_pins_frozen_runtime():
    proof = cert.verify_repository_contract()
    assert proof["status"] == "GREEN"
    assert proof["rushing_frozen_exact"] is True
    assert proof["receiving_frozen_exact"] is True
    assert proof["shared_gate_frozen_exact"] is True
    assert proof["router_owners_exact"] is True
    assert proof["production_target_canonical"] is True


def test_step5_uses_single_canonical_production_target():
    targets = json.loads(cert.PRODUCTION_TARGETS_PATH.read_text(encoding="utf-8"))
    expected = targets["streamlit"]["url"].rstrip("/")
    assert cert.production_base_url() == expected
    assert cert.production_base_url() == "https://pickvault.streamlit.app"
    assert cert.production_base_url() != cert.LEGACY_STREAMLIT_HOST


def test_step5_pregame_live_final_lifecycle_is_green():
    lifecycle = cert.certify_synthetic_lifecycle()
    assert lifecycle["status"] == "GREEN"
    for page in ("rushing", "receiving"):
        assert lifecycle[page]["pregame_pending"]["ready"] is True
        assert lifecycle[page]["pregame_confirmed"]["ready"] is True
        assert lifecycle[page]["live"]["ready"] is True
        assert lifecycle[page]["live"]["identity_state"] == "LIVE"
        assert lifecycle[page]["live"]["prop_market_open"] is False
        assert lifecycle[page]["final"]["ready"] is False
        assert lifecycle[page]["final"]["fail_closed"] is True


def test_step5_responsive_contract_uses_fresh_browser_per_viewport():
    assert cert.RESPONSIVE_VIEWPORTS == ((390, 844), (768, 1024), (1440, 1000))
    assert cert.FRESH_BROWSER_PER_VIEWPORT is True
    assert cert.PUBLIC_ROUTES == (("NFL", "Rushing Yards"), ("NFL", "Receiving Yards"))
