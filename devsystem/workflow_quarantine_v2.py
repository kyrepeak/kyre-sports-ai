"""Monster Speed V3 Step 1 — frozen workflow quarantine validator."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "devsystem" / "workflow_quarantine_v2.json"


class WorkflowQuarantineFailure(RuntimeError):
    pass


def _on_block(source: str) -> str:
    lines = source.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines)
            if line.strip() == "on:" and not line.startswith(" ")
        )
    except StopIteration as exc:
        raise WorkflowQuarantineFailure("workflow missing top-level on block") from exc

    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.startswith((" ", "#")):
            end = i
            break
    return "\n".join(lines[start:end])


def validate(root: Path = ROOT) -> dict:
    registry = json.loads((root / "devsystem/workflow_quarantine_v2.json").read_text(encoding="utf-8"))
    if registry.get("version") != 2:
        raise WorkflowQuarantineFailure("registry version drift")
    if registry.get("status") != "FROZEN":
        raise WorkflowQuarantineFailure("registry must remain FROZEN")

    entries = registry.get("workflows")
    if not isinstance(entries, list) or len(entries) != 16:
        raise WorkflowQuarantineFailure("expected exactly 16 frozen workflow entries")

    automatic = []
    missing_dispatch = []
    missing_jobs = []
    for entry in entries:
        rel = entry["path"]
        path = root / rel
        if not path.is_file():
            raise WorkflowQuarantineFailure(f"missing quarantined workflow: {rel}")
        source = path.read_text(encoding="utf-8")
        block = _on_block(source)
        if "workflow_dispatch:" not in block:
            missing_dispatch.append(rel)
        if any(token in block for token in ("pull_request:", "push:", "schedule:")):
            automatic.append(rel)
        if "jobs:" not in source:
            missing_jobs.append(rel)

    if automatic:
        raise WorkflowQuarantineFailure("automatic triggers restored: " + ", ".join(automatic))
    if missing_dispatch:
        raise WorkflowQuarantineFailure("manual dispatch missing: " + ", ".join(missing_dispatch))
    if missing_jobs:
        raise WorkflowQuarantineFailure("workflow jobs missing: " + ", ".join(missing_jobs))

    result = {
        "status": "GREEN",
        "quarantined_workflows": len(entries),
        "automatic_triggers_after": 0,
        "manual_dispatch_preserved": len(entries),
        "baseline_pull_request_automatic": registry["baseline"]["pull_request_automatic"],
        "baseline_push_automatic": registry["baseline"]["push_automatic"],
    }
    print("MONSTER_SPEED_V3_STEP1_QUARANTINE_GREEN")
    print("MONSTER_SPEED_V3_STEP1_FROZEN_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    validate()
