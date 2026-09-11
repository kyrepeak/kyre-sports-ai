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
            "_history_source_created_at": "2026-09-08T15:00:00Z",
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
            "_history_source_created_at": "2026-09-10T04:30:00+00:00",
            "triage": {"failures": [{"failure_fingerprint": "KYRE-CI-ABC123"}]},
        },
    ]

    summary = history.attach_recurrence(
        report,
        packets,
        current_run_id="999",
        current_run_created_at="2026-09-11T08:00:00Z",
    )
    primary = report["primary"]
    assert primary["recurrence_status"] == "recurring"
    assert primary["recurrence_confidence"] == "confirmed"
    assert primary["recurrence_timing_confidence"] == "confirmed"
    assert primary["recurrence_age_confidence"] == "confirmed"
    assert primary["prior_occurrence_count"] == 2
    assert primary["known_occurrence_count"] == 3
    assert primary["prior_run_ids"] == ["101", "102"]
    assert primary["prior_first_seen_at"] == "2026-09-08T15:00:00Z"
    assert primary["prior_last_seen_at"] == "2026-09-10T04:30:00Z"
    assert primary["prior_last_seen_age_seconds"] == 99000
    assert primary["prior_last_seen_age"] == "1d 3h 30m"
    assert summary["history_available"] is True
    assert summary["timestamped_packets"] == 2
    assert summary["current_run_created_at"] == "2026-09-11T08:00:00Z"
    assert summary["claims_flakiness"] is False
    assert summary["claims_cadence"] is False


def test_partial_or_invalid_timestamps_never_create_fake_chronology_or_age():
    history = _load("failure_history_partial_timing", "devsystem/failure_history_v1.py")
    report = {
        "failures": [{"failure_fingerprint": "KYRE-CI-SAME"}],
        "primary": {"failure_fingerprint": "KYRE-CI-SAME"},
    }
    packets = [
        {
            "run_id": "201",
            "_history_source_created_at": "not-a-time",
            "triage": {"failures": [{"failure_fingerprint": "KYRE-CI-SAME"}]},
        },
        {
            "run_id": "202",
            "_history_source_created_at": "2026-09-09T01:02:03Z",
            "triage": {"failures": [{"failure_fingerprint": "KYRE-CI-SAME"}]},
        },
    ]
    history.attach_recurrence(
        report,
        packets,
        current_run_id="999",
        current_run_created_at="2026-09-11T01:02:03Z",
    )
    primary = report["primary"]
    assert primary["recurrence_status"] == "recurring"
    assert primary["recurrence_timing_confidence"] == "partial"
    assert primary["recurrence_age_confidence"] == "unavailable"
    assert primary["prior_first_seen_at"] == "2026-09-09T01:02:03Z"
    assert primary["prior_last_seen_at"] == "2026-09-09T01:02:03Z"
    assert primary["prior_last_seen_age_seconds"] is None
    assert primary["prior_last_seen_age"] == ""


def test_current_run_is_not_counted_as_prior_occurrence():
    history = _load("failure_history_current_run", "devsystem/failure_history_v1.py")
    report = {
        "failures": [{"failure_fingerprint": "KYRE-CI-SAME"}],
        "primary": {"failure_fingerprint": "KYRE-CI-SAME"},
    }
    packets = [
        {
            "run_id": "200",
            "_history_source_created_at": "2026-09-10T00:00:00Z",
            "triage": {"failures": [{"failure_fingerprint": "KYRE-CI-SAME"}]},
        }
    ]
    history.attach_recurrence(
        report,
        packets,
        current_run_id="200",
        current_run_created_at="2026-09-11T00:00:00Z",
    )
    assert report["primary"]["recurrence_status"] == "not-seen-in-history"
    assert report["primary"]["recurrence_timing_confidence"] == "not-applicable"
    assert report["primary"]["recurrence_age_confidence"] == "not-applicable"
    assert report["primary"]["prior_occurrence_count"] == 0
    assert report["primary"]["prior_first_seen_at"] == ""
    assert report["primary"]["prior_last_seen_at"] == ""
    assert report["primary"]["prior_last_seen_age_seconds"] is None


def test_missing_history_is_not_misreported_as_first_seen():
    history = _load("failure_history_unavailable", "devsystem/failure_history_v1.py")
    report = {
        "failures": [{"failure_fingerprint": "KYRE-CI-NEW"}],
        "primary": {"failure_fingerprint": "KYRE-CI-NEW"},
    }
    summary = history.attach_recurrence(
        report,
        None,
        current_run_created_at="2026-09-11T00:00:00Z",
    )
    assert report["primary"]["recurrence_status"] == "history-unavailable"
    assert report["primary"]["recurrence_confidence"] == "unavailable"
    assert report["primary"]["recurrence_timing_confidence"] == "unavailable"
    assert report["primary"]["recurrence_age_confidence"] == "unavailable"
    assert summary["history_available"] is False


def test_empty_bounded_history_means_not_seen_in_history_only():
    history = _load("failure_history_empty", "devsystem/failure_history_v1.py")
    report = {
        "failures": [{"failure_fingerprint": "KYRE-CI-NEW"}],
        "primary": {"failure_fingerprint": "KYRE-CI-NEW"},
    }
    history.attach_recurrence(
        report,
        [],
        current_run_created_at="2026-09-11T00:00:00Z",
    )
    assert report["primary"]["recurrence_status"] == "not-seen-in-history"
    assert report["primary"]["recurrence_confidence"] == "bounded"
    assert report["primary"]["recurrence_timing_confidence"] == "not-applicable"
    assert report["primary"]["recurrence_age_confidence"] == "not-applicable"


def test_future_or_missing_current_timestamp_never_creates_negative_or_guessed_age():
    history = _load("failure_history_future_age", "devsystem/failure_history_v1.py")
    packets = [
        {
            "run_id": "future",
            "_history_source_created_at": "2026-09-12T00:00:00Z",
            "triage": {"failures": [{"failure_fingerprint": "KYRE-CI-SAME"}]},
        }
    ]
    for current_timestamp in ("2026-09-11T00:00:00Z", "", "2026-09-11T00:00:00"):
        report = {
            "failures": [{"failure_fingerprint": "KYRE-CI-SAME"}],
            "primary": {"failure_fingerprint": "KYRE-CI-SAME"},
        }
        history.attach_recurrence(
            report,
            packets,
            current_run_id="999",
            current_run_created_at=current_timestamp,
        )
        primary = report["primary"]
        assert primary["recurrence_status"] == "recurring"
        assert primary["recurrence_timing_confidence"] == "confirmed"
        assert primary["recurrence_age_confidence"] == "unavailable"
        assert primary["prior_last_seen_age_seconds"] is None
        assert primary["prior_last_seen_age"] == ""


def test_failure_packet_integration_reuses_stable_fingerprint_for_recurrence(tmp_path):
    packet_module = _load("failure_packet_history", "devsystem/failure_packet_v1.py")
    needs = {
        "browser-qa": {
            "result": "failure",
            "evidence": "Playwright TimeoutError while waiting for locator combobox",
        }
    }
    prior = packet_module.build_packet(needs, run_id="300", history_packets=[])
    prior["_history_source_created_at"] = "2026-09-10T12:34:56Z"
    current = packet_module.build_packet(
        needs,
        run_id="301",
        source_created_at="2026-09-11T12:34:56Z",
        history_packets=[prior],
    )
    primary = current["triage"]["primary"]
    assert primary["recurrence_status"] == "recurring"
    assert primary["recurrence_timing_confidence"] == "confirmed"
    assert primary["recurrence_age_confidence"] == "confirmed"
    assert primary["prior_occurrence_count"] == 1
    assert primary["prior_run_ids"] == ["300"]
    assert primary["prior_first_seen_at"] == "2026-09-10T12:34:56Z"
    assert primary["prior_last_seen_at"] == "2026-09-10T12:34:56Z"
    assert primary["prior_last_seen_age_seconds"] == 86400
    assert primary["prior_last_seen_age"] == "1d"
    assert current["source_created_at"] == "2026-09-11T12:34:56Z"
    assert current["history"]["packets_scanned"] == 1
    assert current["history"]["timestamped_packets"] == 1

    packet_module.write_packet(current, tmp_path)
    markdown = (tmp_path / "failure-packet.md").read_text()
    assert "**Recurrence:** recurring" in markdown
    assert "Prior occurrences in bounded history" in markdown
    assert "**Prior first occurrence (UTC):** 2026-09-10T12:34:56Z" in markdown
    assert "**Prior last occurrence (UTC):** 2026-09-10T12:34:56Z" in markdown
    assert "**Age since prior matching occurrence:** 1d" in markdown
    assert "**Age since prior matching occurrence (seconds):** 86400" in markdown
