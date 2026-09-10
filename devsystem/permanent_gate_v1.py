"""Step 6 permanent DevSystem contract validator."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "devsystem" / "devsystem_manifest_v1.json"
EXPECTED_DOMAINS = {"cfb", "mlb", "wnba", "nfl", "nba", "nhl", "soccer"}
REQUIRED_DEVSYSTEM_FILES = (
    "devsystem/change_classifier_v1.py",
    "devsystem/final_gate_v1.py",
    "devsystem/browser_qa_v1.py",
    "devsystem/production_verify_v1.py",
    "devsystem/production_targets_v1.json",
    "devsystem/regression_shield_v1.py",
    "devsystem/README.md",
    ".github/pull_request_template.md",
    ".github/workflows/devsystem-targeted-ci.yml",
    ".github/workflows/devsystem-production-verification.yml",
)


class PermanentGateFailure(RuntimeError):
    pass


def validate() -> dict:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise PermanentGateFailure("DevSystem manifest version drift")

    domains = payload.get("domains")
    if not isinstance(domains, dict) or set(domains) != EXPECTED_DOMAINS:
        raise PermanentGateFailure(
            f"domain registry drift: expected={sorted(EXPECTED_DOMAINS)} "
            f"actual={sorted(domains or {})}"
        )

    missing = [
        path for path in REQUIRED_DEVSYSTEM_FILES
        if not (ROOT / path).is_file()
    ]
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
                invalid_contracts.append(
                    f"{key}: inactive domain may not claim a protected test lane"
                )
        else:
            invalid_contracts.append(f"{key}: unsupported status {status!r}")

    if missing_tests:
        raise PermanentGateFailure("critical tests missing: " + " | ".join(missing_tests))
    if invalid_contracts:
        raise PermanentGateFailure("manifest contract invalid: " + " | ".join(invalid_contracts))

    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(
        encoding="utf-8"
    )
    required_workflow_markers = (
        "python devsystem/change_classifier_v1.py",
        "permanent-contract:",
        "devsystem-final-gate:",
        "python devsystem/final_gate_v1.py",
    )
    workflow_missing = [m for m in required_workflow_markers if m not in workflow]
    for key in active:
        job = str(domains[key]["critical_job"])
        if f"  {job}:" not in workflow:
            workflow_missing.append(f"job:{job}")
    if workflow_missing:
        raise PermanentGateFailure(
            "targeted CI permanent markers missing: " + " | ".join(workflow_missing)
        )

    prod = (ROOT / ".github/workflows/devsystem-production-verification.yml").read_text(
        encoding="utf-8"
    )
    if "branches: [main]" not in prod:
        raise PermanentGateFailure("production verification must remain main-only")

    result = {
        "status": "GREEN",
        "active_domains": active,
        "blocked_until_activated": inactive,
        "stable_final_gate": payload["policy"]["stable_final_gate"],
        "critical_test_count": sum(
            len(domains[key]["critical_tests"]) for key in active
        ),
    }
    print("DEVSYSTEM_PERMANENT_CONTRACT_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    validate()
