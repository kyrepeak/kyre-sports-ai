from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RunlessPlanRequired(RuntimeError):
    pass


@dataclass(frozen=True)
class RunlessProofPlan:
    task_id: str
    workstream: str
    commands: tuple[str, ...]
    artifacts: tuple[str, ...]
    dependencies: tuple[str, ...]
    freeze_token: str
    timeout_seconds: int
    public_probe: dict[str, Any] | None = None


def _validate_command(command: str) -> None:
    blocked = (";", "&&", "||", "`", "$(", ">", "<", "\n")
    if any(token in command for token in blocked):
        raise ValueError("RUNLESS_COMMAND_NOT_ALLOWLISTED")
    allowed = (
        "python -m pytest ",
        "python -m py_compile ",
        "python -m devsystem.",
    )
    if not command.startswith(allowed):
        raise ValueError("RUNLESS_COMMAND_NOT_ALLOWLISTED")


def load_plan(task_id: str, root: Path) -> RunlessProofPlan:
    path = Path(root) / "devsystem" / "runless_proof_plans" / f"{task_id}.json"
    if not path.is_file():
        raise RunlessPlanRequired(f"RUNLESS_PLAN_REQUIRED: {task_id}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    required = ("task_id", "workstream", "commands", "artifacts", "dependencies", "freeze_token", "timeout_seconds")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"RUNLESS_PLAN_INVALID: missing={','.join(missing)}")
    if raw["task_id"] != task_id:
        raise ValueError("RUNLESS_PLAN_TASK_ID_MISMATCH")
    commands = tuple(str(c) for c in raw["commands"])
    for command in commands:
        _validate_command(command)
    return RunlessProofPlan(
        task_id=str(raw["task_id"]),
        workstream=str(raw["workstream"]),
        commands=commands,
        artifacts=tuple(str(x) for x in raw["artifacts"]),
        dependencies=tuple(str(x) for x in raw["dependencies"]),
        freeze_token=str(raw["freeze_token"]),
        timeout_seconds=int(raw["timeout_seconds"]),
        public_probe=raw.get("public_probe"),
    )
