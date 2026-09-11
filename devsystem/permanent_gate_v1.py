"""Step 9 permanent DevSystem contract validator."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "devsystem" / "devsystem_manifest_v1.json"
PHASE2_CLOSURE = ROOT / "devsystem" / "phase2_closure_v1.json"
EXPECTED_DOMAINS = {"cfb", "mlb", "wnba", "nfl", "nba", "nhl", "soccer"}
REQUIRED_DEVSYSTEM_FILES = (
    "devsystem/change_classifier_v1.py",
    "devsystem/final_gate_v1.py",
    "devsystem/failure_triage_v1.py",
    "devsystem/failure_packet_v1.py",
    "devsystem/failure_log_excerpt_v1.py",
    "devsystem/failure_fingerprint_v1.py",
    "devsystem/failure_history_v1.py",
    "devsystem/browser_qa_v1.py",
    "devsystem/production_verify_v1.py",
    "devsystem/production_targets_v1.json",
    "devsystem/production_contract_v1.py",
    "devsystem/regression_shield_v1.py",
    "devsystem/phase2_closure_v1.json",
    "tests/test_devsystem_failure_triage_v1.py",
    "tests/test_devsystem_failure_packet_v1.py",
    "tests/test_devsystem_failure_log_excerpt_v1.py",
    "tests/test_devsystem_failure_fingerprint_v1.py",
    "tests/test_devsystem_failure_history_v1.py",
    "sports_api/observability_v1.py",
    "devsystem/README.md",
    ".github/pull_request_template.md",
    ".github/workflows/devsystem-targeted-ci.yml",
    ".github/workflows/devsystem-failure-packet-v1.yml",
    ".github/workflows/devsystem-production-verification.yml",
    ".github/workflows/devsystem-api-observability-v1.yml",
)


class PermanentGateFailure(RuntimeError):
    pass


def validate() -> dict:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise PermanentGateFailure("DevSystem manifest version drift")

    closure = json.loads(PHASE2_CLOSURE.read_text(encoding="utf-8"))
    if closure.get("version") != 1 or closure.get("status") != "certified":
        raise PermanentGateFailure("Phase 2 closure certification drift")
    if closure.get("completed_steps") != 12:
        raise PermanentGateFailure("Phase 2 closure step count drift")

    domains = payload.get("domains")
    if not isinstance(domains, dict) or set(domains) != EXPECTED_DOMAINS:
        raise PermanentGateFailure(
            f"domain registry drift: expected={sorted(EXPECTED_DOMAINS)} "
            f"actual={sorted(domains or {})}"
        )

    missing = [path for path in REQUIRED_DEVSYSTEM_FILES if not (ROOT / path).is_file()]
    if missing:
        raise PermanentGateFailure(f"permanent DevSystem files missing: {missing}")

    active: list[str] = []
    inactive: list[str] = []
    missing_tests: list[str] = []
    invalid_contracts: list[str] = []

    for key, cfg in sorted(domains.items()):
        status = cfg.get("status")
        tests = cfg.get("critical_tests")
        job = cfg.get("critical_job")
        if not isinstance(tests, list):
            invalid_contracts.append(f"{key}: critical_tests must be a list")
            continue
        if status == "active":
            active.append(key)
            if not job:
                invalid_contracts.append(f"{key}: active domain missing critical_job")
            if not tests:
                invalid_contracts.append(f"{key}: active domain has no critical tests")
            for test_path in tests:
                if not (ROOT / test_path).is_file():
                    missing_tests.append(f"{key}:{test_path}")
        elif status in {"legacy_unprotected", "planned"}:
            inactive.append(key)
            if job or tests:
                invalid_contracts.append(f"{key}: inactive domain may not claim a protected test lane")
        else:
            invalid_contracts.append(f"{key}: unsupported status {status!r}")

    if missing_tests:
        raise PermanentGateFailure("critical tests missing: " + " | ".join(missing_tests))
    if invalid_contracts:
        raise PermanentGateFailure("manifest contract invalid: " + " | ".join(invalid_contracts))

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    required_workflow_markers = (
        "python devsystem/change_classifier_v1.py",
        "permanent-contract:",
        "devsystem-final-gate:",
        'allowed="success skipped"',
        "DEVSYSTEM_FINAL_GATE_GREEN",
    )
    workflow_missing = [m for m in required_workflow_markers if m not in workflow]
    for key in active:
        job = str(domains[key]["critical_job"])
        if f"  {job}:" not in workflow:
            workflow_missing.append(f"job:{job}")
    if workflow_missing:
        raise PermanentGateFailure("targeted CI permanent markers missing: " + " | ".join(workflow_missing))

    failure_packet_workflow = (ROOT / ".github/workflows/devsystem-failure-packet-v1.yml").read_text(encoding="utf-8")
    failure_packet_markers = (
        "actions/jobs/{job_id}/logs",
        "extract_log_excerpt",
        'lane["log_excerpt"] = log_excerpt',
        "tests/test_devsystem_failure_log_excerpt_v1.py",
        "tests/test_devsystem_failure_fingerprint_v1.py",
        "tests/test_devsystem_failure_history_v1.py",
        "Collect prior failure fingerprint history",
        "actions/artifacts?per_page=100&page={page}",
        "collection_complete = False",
        "DEVSYSTEM_FAILURE_HISTORY_ARTIFACT_UNAVAILABLE",
        "DEVSYSTEM_FAILURE_HISTORY_UNAVAILABLE",
        "DEVSYSTEM_FAILURE_HISTORY_LIVE_CERTIFIED",
        'packet["_history_source_created_at"] = str(source_run.get("created_at") or "")',
        "DEVSYSTEM_FAILURE_CURRENT_SOURCE_TIMESTAMP",
        "DEVSYSTEM_FAILURE_CURRENT_SOURCE_TIMESTAMP_UNAVAILABLE",
        'source_created_at = str(current_source_run.get("created_at") or "")',
        "--source-created-at",
        "current_timestamp=",
        "timestamps=",
        "class NoRedirect",
        "Do not forward GH_TOKEN off github.com.",
        "--history-json",
        "retention-days: 30",
        "DEVSYSTEM_FAILURE_LOG_EXCERPT_UNAVAILABLE",
        "Upload failure packet evidence",
    )
    packet_missing = [marker for marker in failure_packet_markers if marker not in failure_packet_workflow]
    if packet_missing:
        raise PermanentGateFailure("failure packet log/history evidence drift: " + " | ".join(packet_missing))

    triage_source = (ROOT / "devsystem/failure_triage_v1.py").read_text(encoding="utf-8")
    remediation_markers = (
        '"remediation_class": "deterministic-regression"',
        '"remediation_class": "transient-capable"',
        '"retry_policy": "do-not-retry"',
        '"retry_policy": "retry-once-after-inspection"',
        '"retry_policy": "investigate-first"',
    )
    remediation_missing = [marker for marker in remediation_markers if marker not in triage_source]
    if remediation_missing:
        raise PermanentGateFailure("failure remediation policy drift: " + " | ".join(remediation_missing))

    fingerprint_source = (ROOT / "devsystem/failure_fingerprint_v1.py").read_text(encoding="utf-8")
    packet_source = (ROOT / "devsystem/failure_packet_v1.py").read_text(encoding="utf-8")
    fingerprint_markers = (
        "KYRE-CI-",
        "sha256",
        "failure_fingerprint",
        "attach_fingerprints",
    )
    fingerprint_missing = [marker for marker in fingerprint_markers if marker not in fingerprint_source]
    if "attach_fingerprints(report)" not in packet_source:
        fingerprint_missing.append("packet:attach_fingerprints(report)")
    if "Failure fingerprint" not in packet_source:
        fingerprint_missing.append("packet:Failure fingerprint")
    if fingerprint_missing:
        raise PermanentGateFailure("failure fingerprint contract drift: " + " | ".join(fingerprint_missing))

    history_source = (ROOT / "devsystem/failure_history_v1.py").read_text(encoding="utf-8")
    history_markers = (
        "attach_recurrence",
        '"recurring"',
        '"not-seen-in-history"',
        '"history-unavailable"',
        '"prior_occurrence_count"',
        '"recurrence_timing_confidence"',
        '"prior_first_seen_at"',
        '"prior_last_seen_at"',
        '"recurrence_age_confidence"',
        '"prior_last_seen_age_seconds"',
        '"prior_last_seen_age"',
        '"current_run_created_at"',
        '"claims_flakiness": False',
        '"claims_cadence": False',
    )
    history_missing = [marker for marker in history_markers if marker not in history_source]
    if "history_module.attach_recurrence" not in packet_source:
        history_missing.append("packet:history_module.attach_recurrence")
    if "Prior occurrences in bounded history" not in packet_source:
        history_missing.append("packet:Prior occurrences in bounded history")
    if "Prior last occurrence (UTC)" not in packet_source:
        history_missing.append("packet:Prior last occurrence (UTC)")
    if "Age since prior matching occurrence" not in packet_source:
        history_missing.append("packet:Age since prior matching occurrence")
    if "Source run created (UTC)" not in packet_source:
        history_missing.append("packet:Source run created (UTC)")
    if history_missing:
        raise PermanentGateFailure("failure recurrence history drift: " + " | ".join(history_missing))

    prod = (ROOT / ".github/workflows/devsystem-production-verification.yml").read_text(encoding="utf-8")
    if "branches: [main]" not in prod:
        raise PermanentGateFailure("production verification must remain main-only")

    api_observability = (ROOT / ".github/workflows/devsystem-api-observability-v1.yml").read_text(encoding="utf-8")
    api_required_markers = (
        "api-observability:",
        "tests/test_sports_api_observability_v1.py",
        "tests/test_devsystem_production_contract_v1.py",
        "sports_api/observability_v1.py",
    )
    api_missing = [marker for marker in api_required_markers if marker not in api_observability]
    if api_missing:
        raise PermanentGateFailure("API observability workflow drift: " + " | ".join(api_missing))

    result = {
        "status": "GREEN",
        "active_domains": active,
        "blocked_until_activated": inactive,
        "stable_final_gate": payload["policy"]["stable_final_gate"],
        "critical_test_count": sum(len(domains[key]["critical_tests"]) for key in active),
        "api_observability_permanent": True,
        "phase2_certified": True,
        "phase2_completed_steps": closure["completed_steps"],
        "predictive_failure_triage_permanent": True,
        "automatic_failure_evidence_wiring_permanent": True,
        "failed_job_log_evidence_permanent": True,
        "failure_remediation_policy_permanent": True,
        "stable_failure_fingerprint_permanent": True,
        "failure_packet_self_health_permanent": True,
        "failure_recurrence_history_permanent": True,
        "failure_recurrence_chronology_permanent": True,
        "failure_recurrence_age_permanent": True,
    }
    print("DEVSYSTEM_PERMANENT_CONTRACT_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    validate()
