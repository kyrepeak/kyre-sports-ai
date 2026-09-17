from __future__ import annotations

import pytest


def test_v161_freshness_contract_constants() -> None:
    from devsystem import production_verify_v4 as verify

    assert verify.FROZEN_VERIFIER == "devsystem.production_verify_v3"
    assert verify.EXPECTED_ROUTER == "streamlit_memory_lazy_router_v156"
    assert verify.GAME_TOTAL_REQUIRED_HEARTBEAT == "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE"
    assert verify.GAME_TOTAL_MARKET == "Game Total"


def test_stale_v160_streamlit_body_is_rejected() -> None:
    from devsystem import production_verify_v4 as verify

    stale = "CFB_GAME_TOTAL_V160_PRODUCTION_ACTIVE\nGAME TOTAL ANALYSIS"
    with pytest.raises(verify.ProductionVerificationFailure, match="stale"):
        verify._assert_v161_heartbeat(stale)


def test_exact_v161_production_heartbeat_is_accepted() -> None:
    from devsystem import production_verify_v4 as verify

    body = "Kyre Sports AI\nCFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE\nGAME DAY\nGAME TOTAL ANALYSIS"
    assert verify._assert_v161_heartbeat(body) == verify.GAME_TOTAL_REQUIRED_HEARTBEAT


def test_v161_freshness_evidence_records_expected_commit_and_router() -> None:
    from devsystem import production_verify_v4 as verify

    evidence = verify._build_freshness_evidence(
        expected_commit="72add9a31304c66e8f13786da2929412c7ca24ab",
        observed_body="CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE",
    )
    assert evidence == {
        "expected_commit": "72add9a31304c66e8f13786da2929412c7ca24ab",
        "expected_router": "streamlit_memory_lazy_router_v156",
        "observed_router": "V156",
        "observed_build_marker": "CFB_GAME_TOTAL_V161_PRODUCTION_ACTIVE",
        "freshness_verified": True,
    }
