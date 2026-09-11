"""Monster One-Command Certification V1.

Developer-facing, read-only certification for the additive Monster Final Form
components. This command intentionally does not replace the frozen DevSystem or
its devsystem-final-gate; GitHub CI remains the authoritative merge veto.

Usage:
    python -m sports_api.monster_certification_v1
    python -m sports_api.monster_certification_v1 --json

The command executes the real Step 1-6 contract suites and emits a fail-closed
receipt with the exact command, status, duration, and concise failure evidence.
It performs no network calls and has no production runtime integration.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

CERTIFICATION_VERSION = "MONSTER_ONE_COMMAND_CERTIFICATION_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False
FUZZY_MATCHING = False
REPLACES_DEVSYSTEM_FINAL_GATE = False
AUTHORITATIVE_MERGE_GATE = "devsystem-final-gate"
MAX_EVIDENCE_CHARS = 3000


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    label: str
    command: tuple[str, ...]
    required_paths: tuple[str, ...]


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


Runner = Callable[[Sequence[str], Path], CommandResult]


def _python() -> str:
    return sys.executable


def certification_manifest() -> tuple[CheckSpec, ...]:
    """Return the immutable set of real Final Form contracts certified by V1."""
    py = _python()
    modules = (
        "sports_api/posthog_error_radar_v1.py",
        "sports_api/monster_performance_profiler_v1.py",
        "sports_api/monster_dependency_map_v1.py",
        "sports_api/monster_page_factory_v1.py",
        "sports_api/monster_test_matrix_v1.py",
        "sports_api/monster_failure_memory_v1.py",
    )
    return (
        CheckSpec(
            "final_form_compile",
            "Compile Monster Final Form Steps 1-6",
            (py, "-m", "py_compile", *modules),
            modules,
        ),
        CheckSpec(
            "step1_error_radar",
            "Step 1 — Error Radar contracts",
            (py, "-m", "pytest", "-q", "tests/test_monster_error_radar_v1.py", "tests/test_sports_api_observability_v1.py"),
            ("tests/test_monster_error_radar_v1.py", "tests/test_sports_api_observability_v1.py"),
        ),
        CheckSpec(
            "step2_performance_profiler",
            "Step 2 — Performance Profiler contracts",
            (py, "-m", "pytest", "-q", "tests/test_monster_performance_profiler_v1.py"),
            ("tests/test_monster_performance_profiler_v1.py",),
        ),
        CheckSpec(
            "step3_dependency_map",
            "Step 3 — Dependency Map contracts",
            (py, "-m", "pytest", "-q", "tests/test_monster_dependency_map_v1.py"),
            ("tests/test_monster_dependency_map_v1.py",),
        ),
        CheckSpec(
            "step4_page_factory",
            "Step 4 — Page Factory contracts",
            (py, "-m", "pytest", "-q", "tests/test_monster_page_factory_v1.py"),
            ("tests/test_monster_page_factory_v1.py",),
        ),
        CheckSpec(
            "step5_test_matrix",
            "Step 5 — Test Matrix contracts",
            (py, "-m", "pytest", "-q", "tests/test_monster_test_matrix_v1.py"),
            ("tests/test_monster_test_matrix_v1.py",),
        ),
        CheckSpec(
            "step6_failure_memory",
            "Step 6 — Failure Memory contracts",
            (py, "-m", "pytest", "-q", "tests/test_monster_failure_memory_v1.py"),
            ("tests/test_monster_failure_memory_v1.py",),
        ),
    )


def _default_runner(command: Sequence[str], cwd: Path) -> CommandResult:
    completed = subprocess.run(
        list(command),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )
    return CommandResult(completed.returncode, completed.stdout or "", completed.stderr or "")


def _clip(value: str, limit: int = MAX_EVIDENCE_CHARS) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _command_display(command: Sequence[str]) -> str:
    return " ".join(str(part) for part in command)


def _missing_paths(root: Path, paths: Iterable[str]) -> list[str]:
    return [path for path in paths if not (root / path).is_file()]


def _protection_snapshot() -> dict[str, object]:
    return {
        "projection_weight": PROJECTION_WEIGHT,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
        "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
        "may_modify_runtime": MAY_MODIFY_RUNTIME,
        "network_calls": NETWORK_CALLS,
        "fuzzy_matching": FUZZY_MATCHING,
        "replaces_devsystem_final_gate": REPLACES_DEVSYSTEM_FINAL_GATE,
        "authoritative_merge_gate": AUTHORITATIVE_MERGE_GATE,
    }


def run_certification(
    repo_root: str | Path = ".",
    *,
    runner: Runner = _default_runner,
    checks: Sequence[CheckSpec] | None = None,
    fail_fast: bool = False,
) -> dict[str, object]:
    """Execute every required local certification check and return a receipt.

    Missing files, runner exceptions, timeouts, and non-zero exits fail closed.
    No shell is used and the manifest contains no network operation.
    """
    root = Path(repo_root).resolve()
    manifest = tuple(checks or certification_manifest())
    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    results: list[dict[str, object]] = []

    for spec in manifest:
        check_started = time.perf_counter()
        missing = _missing_paths(root, spec.required_paths)
        if missing:
            results.append(
                {
                    "check_id": spec.check_id,
                    "label": spec.label,
                    "status": "FAIL",
                    "returncode": None,
                    "duration_ms": round((time.perf_counter() - check_started) * 1000.0, 2),
                    "command": _command_display(spec.command),
                    "reason": "required_path_missing",
                    "evidence": ", ".join(missing),
                }
            )
            if fail_fast:
                break
            continue

        try:
            outcome = runner(spec.command, root)
            passed = int(outcome.returncode) == 0
            evidence = _clip(outcome.stdout if passed else (outcome.stderr or outcome.stdout))
            results.append(
                {
                    "check_id": spec.check_id,
                    "label": spec.label,
                    "status": "PASS" if passed else "FAIL",
                    "returncode": int(outcome.returncode),
                    "duration_ms": round((time.perf_counter() - check_started) * 1000.0, 2),
                    "command": _command_display(spec.command),
                    "reason": "ok" if passed else "command_failed",
                    "evidence": evidence,
                }
            )
        except Exception as exc:  # fail closed by design
            results.append(
                {
                    "check_id": spec.check_id,
                    "label": spec.label,
                    "status": "FAIL",
                    "returncode": None,
                    "duration_ms": round((time.perf_counter() - check_started) * 1000.0, 2),
                    "command": _command_display(spec.command),
                    "reason": "runner_exception",
                    "evidence": _clip(f"{type(exc).__name__}: {exc}"),
                }
            )

        if fail_fast and results[-1]["status"] == "FAIL":
            break

    failed = [item for item in results if item["status"] != "PASS"]
    passed_count = len(results) - len(failed)
    all_required_executed = len(results) == len(manifest)
    status = "PASS" if not failed and all_required_executed else "FAIL"
    finished_at = datetime.now(timezone.utc)

    return {
        "certification_version": CERTIFICATION_VERSION,
        "status": status,
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        "finished_at": finished_at.isoformat().replace("+00:00", "Z"),
        "duration_ms": round((time.perf_counter() - started_perf) * 1000.0, 2),
        "repo_root": str(root),
        "required_check_count": len(manifest),
        "executed_check_count": len(results),
        "passed_check_count": passed_count,
        "failed_check_count": len(failed),
        "all_required_executed": all_required_executed,
        "protections": _protection_snapshot(),
        "results": results,
    }


def _human_report(receipt: dict[str, object]) -> str:
    icon = "✅" if receipt["status"] == "PASS" else "❌"
    lines = [
        f"{icon} {CERTIFICATION_VERSION}: {receipt['status']}",
        (
            f"Checks: {receipt['passed_check_count']}/{receipt['required_check_count']} passed "
            f"• {receipt['duration_ms']} ms"
        ),
    ]
    for item in receipt["results"]:  # type: ignore[index]
        marker = "✅" if item["status"] == "PASS" else "❌"
        lines.append(f"{marker} {item['check_id']} — {item['status']} ({item['duration_ms']} ms)")
        if item["status"] != "PASS":
            lines.append(f"   reason={item['reason']} evidence={item['evidence']}")
    lines.append(
        "Authoritative merge veto remains GitHub devsystem-final-gate; this local command does not replace it."
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Monster Final Form Steps 1-6 certification.")
    parser.add_argument("--repo-root", default=".", help="Repository root (default: current directory).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed check.")
    args = parser.parse_args(argv)

    receipt = run_certification(args.repo_root, fail_fast=args.fail_fast)
    if args.json:
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    else:
        print(_human_report(receipt))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
