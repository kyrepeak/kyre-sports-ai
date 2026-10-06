from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

AUTHORIZATION_TOKEN = "KYRE_EXPLICIT_AUTHORIZATION"
MANIFEST = Path("devsystem/runless_legacy_proof_workflows_v1.txt")


@dataclass(frozen=True)
class FallbackAuthorization:
    authorized: bool
    reason: str


@dataclass(frozen=True)
class AuditResult:
    green: bool
    failures: tuple[str, ...]
    checked: tuple[str, ...]


def authorize_manual_actions_fallback(explicit_authorization: str | None) -> FallbackAuthorization:
    if explicit_authorization == AUTHORIZATION_TOKEN:
        return FallbackAuthorization(True, "EXPLICIT_KYRE_AUTHORIZATION_PRESENT")
    return FallbackAuthorization(False, "EXPLICIT_KYRE_AUTHORIZATION_REQUIRED")


def _manifest_paths(root: Path) -> tuple[str, ...]:
    manifest = root / MANIFEST
    if not manifest.is_file():
        return ()
    return tuple(
        line.strip()
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _top_level_trigger_block(text: str) -> str:
    lines = text.splitlines()
    inside = False
    out: list[str] = []
    for line in lines:
        if not inside and re.match(r"^on\s*:\s*$", line):
            inside = True
            continue
        if inside:
            if line and not line.startswith((" ", "\t")):
                break
            out.append(line)
    return "\n".join(out)


def audit_legacy_workflows(root: Path) -> AuditResult:
    root = Path(root)
    paths = _manifest_paths(root)
    failures: list[str] = []
    if not paths:
        failures.append("RUNLESS_FALLBACK_MANIFEST_MISSING_OR_EMPTY")
    for relative in paths:
        path = root / relative
        if not path.is_file():
            failures.append(f"MISSING:{relative}")
            continue
        block = _top_level_trigger_block(path.read_text(encoding="utf-8"))
        if not re.search(r"(?m)^\s{2}workflow_dispatch\s*:", block):
            failures.append(f"NO_MANUAL_TRIGGER:{relative}")
        if re.search(r"(?m)^\s{2}(pull_request|push)\s*:", block):
            failures.append(f"AUTOMATIC_TRIGGER:{relative}")
    return AuditResult(not failures, tuple(failures), paths)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = audit_legacy_workflows(Path(args.root))
    if result.green:
        print(f"RUNLESS_ACTIONS_FALLBACK_POLICY_GREEN checked={len(result.checked)}")
        return 0
    print("RUNLESS_ACTIONS_FALLBACK_POLICY_RED")
    for failure in result.failures:
        print(failure)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
