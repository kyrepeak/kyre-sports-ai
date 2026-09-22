from __future__ import annotations

import copy

import pytest

from sports_api.monster_control_plane_v1 import (
    AUTHORITATIVE_MERGE_GATE,
    AUTO_FIX,
    CONTROL_PLANE_VERSION,
    FUZZY_MATCHING,
    MAY_MODIFY_PROJECTION,
    MAY_MODIFY_RUNTIME,
    MAY_MODIFY_SOURCE_DATA,
    NETWORK_CALLS,
    PROJECTION_WEIGHT,
    REPLACES_DEVSYSTEM_FINAL_GATE,
    build_control_report,
    parse_span_spec,
    protection_snapshot,
)


KNOWN_CFB_SIGNATURE = "cfb ou cold start eagerly imports historical router spine before active page"


def _passing_certification(_repo_root):
    return {
        "certification_version": "MONSTER_ONE_COMMAND_CERTIFICATION_V1",
        "status": "PASS",
        "required_check_count": 7,
        "executed_check_count": 7,
        "passed_check_count": 7,
        "failed_check_count": 0,
        "all_required_executed": True,
        "protections": {"projection_weight": 0.0},
        "results": [],
    }


def _failing_certification(_repo_root):
    return {
        "certification_version": "MONSTER_ONE_COMMAND_CERTIFICATION_V1",
        "status": "FAIL",
        "required_check_count": 7,
        "executed_check_count": 7,
        "passed_check_count": 6,
        "failed_check_count": 1,
        "all_required_executed": True,
        "protections": {"projection_weight": 0.0},
        "results": [{"check_id": "step6_failure_memory", "status": "FAIL"}],
    }


def test_control_plane_protections_are_read_only_and_frozen_safe():
    assert CONTROL_PLANE_VERSION == "MONSTER_CONTROL_PLANE_V1"
    assert PROJECTION_WEIGHT == 0.0
    assert MAY_MODIFY_PROJECTION is False
    assert MAY_MODIFY_SOURCE_DATA is False
    assert MAY_MODIFY_RUNTIME is False
    assert NETWORK_CALLS is False
    assert FUZZY_MATCHING is False
    assert AUTO_FIX is False
    assert REPLACES_DEVSYSTEM_FINAL_GATE is False
    assert AUTHORITATIVE_MERGE_GATE == "devsystem-final-gate"

    protections = protection_snapshot()
    assert protections["projection_weight"] == 0.0
    assert protections["auto_fix"] is False
    assert protections["authoritative_merge_gate"] == "devsystem-final-gate"


def test_parse_span_spec_supports_category_and_rejects_bad_values():
    parsed = parse_span_spec("market.fetch=1234.5:market")
    assert parsed == {
        "stage": "market.fetch",
        "total_ms": 1234.5,
        "calls": 1,
        "category": "market",
    }

    plain = parse_span_spec("render.cards=250")
    assert plain["stage"] == "render.cards"
    assert plain["total_ms"] == 250.0
    assert "category" not in plain

    with pytest.raises(ValueError):
        parse_span_spec("missing-equals")
    with pytest.raises(ValueError):
        parse_span_spec("api.fetch=not-a-number")
    with pytest.raises(ValueError):
        parse_span_spec("api.fetch=-1")


def test_idle_control_plane_is_ready_without_running_expensive_certification():
    report = build_control_report(
        ".",
        include_matrix=False,
        certify=False,
    )
    assert report["status"] == "READY"
    assert report["signals"]["performance"]["status"] == "NOT_REQUESTED"
    assert report["signals"]["failure_memory"]["status"] == "NOT_REQUESTED"
    assert report["signals"]["dependency"]["status"] == "NOT_REQUESTED"
    assert report["signals"]["test_matrix"]["status"] == "NOT_REQUESTED"
    assert report["signals"]["certification"]["status"] == "NOT_REQUESTED"
    assert "cfb-critical" in report["recommended_tests"]
    assert "devsystem-final-gate" in report["recommended_tests"]
    assert report["signals"]["observability"]["status"] == "ok"
    assert report["signals"]["error_radar"]["version"] == "MONSTER_ERROR_RADAR_V1"


def test_control_plane_connects_profiler_failure_memory_and_test_matrix():
    spans = [
        {"stage": "bootstrap.router", "total_ms": 2800.0, "category": "import"},
        {"stage": "render.cards", "total_ms": 400.0, "category": "render"},
    ]
    original = copy.deepcopy(spans)

    report = build_control_report(
        ".",
        signature=KNOWN_CFB_SIGNATURE,
        sport="CFB",
        total_ms=3600.0,
        spans=spans,
        surface="streamlit",
        path="cfb-over-under",
        include_matrix=True,
        certify=False,
    )

    assert spans == original
    assert report["status"] == "INVESTIGATE"
    performance = report["signals"]["performance"]
    assert performance["grade"] == "CRITICAL"
    assert performance["bottleneck"] == "bootstrap.router"
    assert performance["bottleneck_category"] == "import"

    memory = report["signals"]["failure_memory"]
    assert memory["status"] == "FOUND"
    assert memory["exact"] is True
    assert memory["records"][0]["memory_id"] == "cfb-ou-historical-router-cold-start"

    matrix = report["signals"]["test_matrix"]
    assert matrix["passed"] is True
    assert matrix["scenario_count"] >= 20
    assert matrix["projection_weight"] == 0.0

    sources = {item["source"] for item in report["next_actions"]}
    assert "performance_profiler" in sources
    assert "failure_memory" in sources
    assert "cfb-critical" in report["recommended_tests"]
    assert "browser-qa" in report["recommended_tests"]


def test_control_plane_maps_its_own_blast_radius_without_production_entrypoints():
    report = build_control_report(
        ".",
        target="sports_api/monster_control_plane_v1.py",
        include_matrix=False,
        certify=False,
    )
    dependency = report["signals"]["dependency"]
    assert dependency["status"] == "OK"
    assert dependency["path"] == "sports_api/monster_control_plane_v1.py"
    assert dependency["impacted_entrypoints"] == []
    assert report["protections"]["may_modify_runtime"] is False


def test_missing_dependency_target_fails_closed():
    report = build_control_report(
        ".",
        target="sports_api/does_not_exist_monster_v999.py",
        include_matrix=False,
        certify=False,
    )
    assert report["status"] == "BLOCKED"
    assert report["signals"]["dependency"]["status"] == "NOT_FOUND"
    assert report["next_actions"][0]["priority"] == "P0"


def test_negative_total_is_blocked_instead_of_hidden():
    report = build_control_report(
        ".",
        total_ms=-1.0,
        include_matrix=False,
        certify=False,
    )
    assert report["status"] == "BLOCKED"
    assert report["signals"]["performance"]["status"] == "INVALID_INPUT"


def test_passing_certification_is_embedded_in_control_report():
    report = build_control_report(
        ".",
        include_matrix=False,
        certify=True,
        certification_func=_passing_certification,
    )
    certification = report["signals"]["certification"]
    assert certification["status"] == "PASS"
    assert certification["passed_check_count"] == 7
    assert report["status"] == "READY"


def test_failing_certification_blocks_and_recommends_certification_lane():
    report = build_control_report(
        ".",
        include_matrix=False,
        certify=True,
        certification_func=_failing_certification,
    )
    assert report["status"] == "BLOCKED"
    assert report["signals"]["certification"]["status"] == "FAIL"
    assert "monster-one-command-certification" in report["recommended_tests"]
    assert report["next_actions"][0]["source"] == "certification"


def test_unknown_exact_memory_signature_is_not_forced_to_a_historical_fix():
    report = build_control_report(
        ".",
        signature="this exact failure has never been curated",
        include_matrix=False,
        certify=False,
    )
    memory = report["signals"]["failure_memory"]
    assert memory["status"] == "NOT_FOUND"
    assert memory["found"] is False
    assert memory["exact"] is True
    assert memory["fuzzy_matching"] is False
    assert report["status"] == "READY"
