from __future__ import annotations

import pytest


def test_v160_freshness_contract_constants() -> None:
    from devsystem import production_verify_v3 as verify

    assert verify.GAME_TOTAL_REQUIRED_HEARTBEAT == "CFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE"
    assert verify.EXPECTED_ROUTER == "streamlit_memory_lazy_router_v155"
    assert verify.GAME_TOTAL_MARKET == "Game Total"


def test_stale_streamlit_body_is_rejected() -> None:
    from devsystem import production_verify_v3 as verify

    stale = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE\nCFB GAME TOTAL • CLEAN PAGE V152 ACTIVE"
    with pytest.raises(verify.ProductionVerificationFailure, match="stale"):
        verify._assert_v160_heartbeat(stale)


def test_exact_v160_heartbeat_is_accepted() -> None:
    from devsystem import production_verify_v3 as verify

    body = "College Football Game Total\nCFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE"
    assert verify._assert_v160_heartbeat(body) == verify.GAME_TOTAL_REQUIRED_HEARTBEAT


def test_freshness_evidence_records_expected_commit_and_observed_build() -> None:
    from devsystem import production_verify_v3 as verify

    evidence = verify._build_freshness_evidence(
        expected_commit="abc123",
        observed_body="CFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE",
    )
    assert evidence == {
        "expected_commit": "abc123",
        "expected_router": "streamlit_memory_lazy_router_v155",
        "observed_router": "V155/V160",
        "observed_build_marker": "CFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE",
        "freshness_verified": True,
    }
