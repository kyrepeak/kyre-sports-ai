from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: str):
    target = ROOT / path
    spec = importlib.util.spec_from_file_location(name, target)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recurrence_is_confirmed_only_with_matching_historical_fingerprint():
    history = _load("failure_history_v1", "devsystem/failure_history_v1.py")
    report = {
        "failures": [
            {"job": "browser-qa", "failure_fingerprint": "KYRE-CI-ABC123"}
        ],
        "primary": {"job": "browser-qa", "failure_fingerprint": "KYRE-CI-ABC123"},
    }
    packets = [
        {
            "run_id": "101",
            "sha": "aaa",
            "ref": "branch-a",
            "triage": {
                "failures": [
                    {"failure_fingerprint": "KYRE-CI-ABC123"},
                    {"failure_fingerprint": "KYRE-CI-OTHER"},
                ]
            },
        },
        {
            "run_id": "102",
            "sha": "bbb",
            "ref": "branch-b",
            "triage": {"failures": [{"failure_fingerprint": "KYRE-CI-ABC123"}]},
        },
    ]

    summary = history.attach_recurrence(report, packets, current_run_id="999")
    primary = report["primary"]
    assert primary["recurrence_status"] == "recurring"
    assert primary["recurrence_confidence"] == "confirmed"
    assert primary["prior_occurrence_count"] == 2
    assert primary["known_occurrence_count"] == 3
    assert primary["prior_run_ids"] == ["101", "102"]
    assert summary["history_available"] is True
    assert summary["claims_flakiness"] is False


def test_current_run_is_not_counted_as_prior_occurrence():
    history = _load("failure_history_current_run", "devsystem/failure_history_v1.py")
    report = {
        "failures": [{"failure_fingerprint": "KYRE-CI-SAME"}],
        "primary": {"failure_fingerprint": "KYRE-CI-SAME"},
    }
    packets = [
        {
            "run_id": "200",
            "triage": {"failures": [{"failure_fingerprint": "KYRE-CI-SAME"}]},
        }
    ]
    history.attach_recurrence(report, packets, current_run_id="200")
    assert report["primary"]["recurrence_status"] == "not-seen-in-history"
    assert report["primary"]["prior_occurrence_count"] == 0


def test_missing_history_is_not_misreported_as_first_seen():
    history = _load("failure_history_unavailable", "devsystem/failure_history_v1.py")
    report = {
        "failures": [{"failure_fingerprint": "KYRE-CI-NEW"}],
        "primary": {"failure_fingerprint": "KYRE-CI-NEW"},
    }
    summary = history.attach_recurrence(report, None)
    assert report["primary"]["recurrence_status"] == "history-unavailable"
    assert report["primary"]["recurrence_confidence"] == "unavailable"
    assert summary["history_available"] is False


def test_empty_bounded_history_means_not_seen_in_history_only():
    history = _load("failure_history_empty", "devsystem/failure_history_v1.py")
    report = {
        "failures": [{"failure_fingerprint": "KYRE-CI-NEW"}],
        "primary": {"failure_fingerprint": "KYRE-CI-NEW"},
    }
    history.attach_recurrence(report, [])
    assert report["primary"]["recurrence_status"] == "not-seen-in-history"
    assert report["primary"]["recurrence_confidence"] == "bounded"


def test_failure_packet_integration_reuses_stable_fingerprint_for_recurrence(tmp_path):
    packet_module = _load("failure_packet_history", "devsystem/failure_packet_v1.py")
    needs = {
        "browser-qa": {
            "result": "failure",
            "evidence": "Playwright TimeoutError while waiting for locator combobox",
        }
    }
    prior = packet_module.build_packet(needs, run_id="300", history_packets=[])
    current = packet_module.build_packet(
        needs,
        run_id="301",
        history_packets=[prior],
    )
    primary = current["triage"]["primary"]
    assert primary["recurrence_status"] == "recurring"
    assert primary["prior_occurrence_count"] == 1
    assert primary["prior_run_ids"] == ["300"]
    assert current["history"]["packets_scanned"] == 1

    packet_module.write_packet(current, tmp_path)
    markdown = (tmp_path / "failure-packet.md").read_text()
    assert "**Recurrence:** recurring" in markdown
    assert "Prior occurrences in bounded history" in markdown
