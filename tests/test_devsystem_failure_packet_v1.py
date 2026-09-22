from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "devsystem" / "failure_packet_v1.py"
    spec = importlib.util.spec_from_file_location("failure_packet_v1", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packet_is_green_when_lanes_are_success_or_skipped(tmp_path):
    module = _load()
    packet = module.build_packet(
        {
            "classify": {"result": "success"},
            "browser-qa": {"result": "skipped"},
        },
        run_id="123",
        sha="abc",
        ref="refs/pull/1/merge",
    )
    assert packet["schema"] == "KYRE_DEVSYSTEM_FAILURE_PACKET_V1"
    assert packet["status"] == "GREEN"
    assert packet["triage"]["primary"] is None

    module.write_packet(packet, tmp_path)
    assert (tmp_path / "failure-packet.json").exists()
    assert "No failed DevSystem lanes" in (tmp_path / "failure-packet.md").read_text()


def test_packet_routes_cfb_failure_to_first_cfb_evidence(tmp_path):
    module = _load()
    packet = module.build_packet(
        {
            "classify": {"result": "success"},
            "cfb-critical": {"result": "failure"},
            "mlb-critical": {"result": "success"},
        }
    )
    primary = packet["triage"]["primary"]
    assert packet["status"] == "FAILURES_FOUND"
    assert primary["job"] == "cfb-critical"
    assert primary["layer"] == "cfb"
    assert primary["retry_policy"] == "investigate-first"
    assert "frozen projection math" in primary["inspect_first"]
    assert "official-ID" in primary["inspect_first"]

    module.write_packet(packet, tmp_path)
    markdown = (tmp_path / "failure-packet.md").read_text()
    assert "CFB" in markdown
    assert "cfb-critical" in markdown
    assert "Inspect first" in markdown
    assert "Retry policy" in markdown


def test_packet_captures_all_failed_lanes_in_deterministic_order():
    module = _load()
    packet = module.build_packet(
        {
            "wnba-critical": {"result": "failure"},
            "browser-qa": {"result": "cancelled"},
            "classify": {"result": "success"},
        }
    )
    jobs = [item["job"] for item in packet["triage"]["failures"]]
    assert jobs == ["browser-qa", "wnba-critical"]
    assert packet["triage"]["primary"]["job"] == "browser-qa"


def test_failed_step_evidence_automatically_triggers_browser_signature(tmp_path):
    module = _load()
    needs = {
        "browser-qa": {"result": "failure"},
        "cfb-critical": {"result": "success"},
    }
    packet = module.build_packet(
        needs,
        failed_steps={
            "browser-qa": [
                "Drive the real Streamlit UI with Playwright: locator timeout waiting for combobox"
            ]
        },
    )
    primary = packet["triage"]["primary"]
    assert primary["job"] == "browser-qa"
    assert primary["evidence_signal"] == "browser-selector-race"
    assert primary["confidence"] == "high"
    assert primary["remediation_class"] == "transient-capable"
    assert primary["retry_policy"] == "retry-once-after-inspection"
    assert "selector/readiness" in primary["diagnosis"]
    # Packet enrichment must not mutate the caller's raw needs payload.
    assert "evidence" not in needs["browser-qa"]

    module.write_packet(packet, tmp_path)
    markdown = (tmp_path / "failure-packet.md").read_text()
    assert "browser-selector-race" in markdown
    assert "**Confidence:** high" in markdown
    assert "**Remediation class:** transient-capable" in markdown
    assert "**Retry policy:** retry-once-after-inspection" in markdown


def test_failed_step_assertion_evidence_refines_sport_lane_without_changing_owner():
    module = _load()
    packet = module.build_packet(
        {"cfb-critical": {"result": "failure"}},
        failed_steps={
            "cfb-critical": [
                "FAILED tests/test_cfb_guard.py::test_frozen_contract - AssertionError"
            ]
        },
    )
    primary = packet["triage"]["primary"]
    assert primary["job"] == "cfb-critical"
    assert primary["layer"] == "cfb"
    assert primary["evidence_signal"] == "test-assertion"
    assert primary["confidence"] == "high"
    assert primary["remediation_class"] == "deterministic-regression"
    assert primary["retry_policy"] == "do-not-retry"


def test_unknown_failed_step_evidence_stays_low_confidence():
    module = _load()
    packet = module.build_packet(
        {"mlb-critical": {"result": "failure"}},
        failed_steps={"mlb-critical": ["Run current MLB critical path ended unexpectedly"]},
    )
    primary = packet["triage"]["primary"]
    assert primary["job"] == "mlb-critical"
    assert primary["evidence_signal"] == "unclassified-evidence"
    assert primary["confidence"] == "low"
    assert primary["remediation_class"] == "unknown"
    assert primary["retry_policy"] == "investigate-first"


def test_explicit_lane_evidence_wins_over_failed_step_fallback():
    module = _load()
    packet = module.build_packet(
        {
            "core-smoke": {
                "result": "failure",
                "evidence": "ModuleNotFoundError: No module named 'sports_api'",
            }
        },
        failed_steps={"core-smoke": ["timeout waiting for unrelated cleanup"]},
    )
    primary = packet["triage"]["primary"]
    assert primary["evidence_signal"] == "python-import"
    assert primary["confidence"] == "high"
    assert primary["retry_policy"] == "do-not-retry"
