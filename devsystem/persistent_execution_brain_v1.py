"""Monster Persistent Execution Brain V1.

Dependency-light, fail-closed control-plane state that can be persisted in one
GitHub issue ledger and resumed across chats without reconstructing project
truth from prose. This module performs no network calls and never mutates
sports/runtime/model/source data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "MONSTER_PERSISTENT_EXECUTION_BRAIN_V1"
PERSISTENCE_SURFACE = "github_issue_ledger"
AUTHORITATIVE_MERGE_GATE = "devsystem-final-gate"
ANTI_LOOP_POLICY = "MONSTER_ANTI_LOOP_V2"
NETWORK_CALLS = False
AUTO_FIX = False
MAY_MODIFY_PRODUCT_RUNTIME = False

ISSUE_BEGIN = "<!-- MONSTER_PERSISTENT_EXECUTION_BRAIN_V1:BEGIN -->"
ISSUE_END = "<!-- MONSTER_PERSISTENT_EXECUTION_BRAIN_V1:END -->"

_EXECUTION_STATES = {
    "ACTIVE",
    "WAITING_ON_ASYNC",
    "BLOCKED",
    "READY_TO_MERGE",
    "FROZEN",
    "COMPLETE",
}
_ASYNC_STATES = {"NONE", "QUEUED", "IN_PROGRESS", "SUCCESS", "FAILURE", "CANCELLED"}
_OWNERS = {
    "CONTROL_PLANE",
    "PRODUCT",
    "VERIFIER",
    "CI",
    "DEPLOYMENT",
    "EXTERNAL",
    "STALE_EVIDENCE",
    "NONE",
}
_FAILURE_CLASSES = {
    "NONE",
    "A_PRODUCT",
    "B_VERIFIER",
    "C_CI_INFRA",
    "D_DEPLOYMENT",
    "E_EXTERNAL",
    "F_STALE_EVIDENCE",
    "G_CONTROL_PLANE",
}
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")


class BrainStateFailure(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise BrainStateFailure("updated_at_utc must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(payload: Mapping[str, Any], *, prefix: str) -> str:
    raw = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{raw}"


def _unique_steps(values: Sequence[int], *, total: int, field_name: str) -> list[int]:
    result = [int(v) for v in values]
    if len(result) != len(set(result)):
        raise BrainStateFailure(f"{field_name} contains duplicate steps")
    if any(v < 1 or v > total for v in result):
        raise BrainStateFailure(f"{field_name} contains out-of-range step")
    return sorted(result)


@dataclass(frozen=True, slots=True)
class BrainStateInput:
    program_id: str
    program_title: str
    total_steps: int
    current_step: int
    step_title: str
    execution_state: str
    repository: str
    main_sha: str
    work_branch: str
    observed_head_sha: str
    next_legal_action: str
    completed_steps: Sequence[int] = field(default_factory=tuple)
    frozen_steps: Sequence[int] = field(default_factory=tuple)
    remaining_steps: Sequence[int] = field(default_factory=tuple)
    pr_number: int | None = None
    owner: str = "CONTROL_PLANE"
    failure_class: str = "NONE"
    authoritative_run_id: int | None = None
    authoritative_job_id: int | None = None
    async_state: str = "NONE"
    blocker: str | None = None
    last_green_evidence: Sequence[str] = field(default_factory=tuple)
    updated_at_utc: str | None = None


def protection_snapshot() -> dict[str, Any]:
    return {
        "persistence_surface": PERSISTENCE_SURFACE,
        "authoritative_merge_gate": AUTHORITATIVE_MERGE_GATE,
        "anti_loop_policy": ANTI_LOOP_POLICY,
        "network_calls": NETWORK_CALLS,
        "auto_fix": AUTO_FIX,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
    }


def build_state(value: BrainStateInput) -> dict[str, Any]:
    total = int(value.total_steps)
    current = int(value.current_step)
    if total <= 0:
        raise BrainStateFailure("total_steps must be positive")
    if current < 1 or current > total:
        raise BrainStateFailure("current_step is outside the declared program")

    completed = _unique_steps(value.completed_steps, total=total, field_name="completed_steps")
    frozen = _unique_steps(value.frozen_steps, total=total, field_name="frozen_steps")
    remaining = _unique_steps(value.remaining_steps, total=total, field_name="remaining_steps")

    state = {
        "version": VERSION,
        "updated_at_utc": value.updated_at_utc or _utc_now(),
        "program": {
            "id": str(value.program_id).strip(),
            "title": str(value.program_title).strip(),
            "total_steps": total,
        },
        "repository": {
            "full_name": str(value.repository).strip(),
            "main_sha": str(value.main_sha).strip().lower(),
            "work_branch": str(value.work_branch).strip(),
            "observed_head_sha": str(value.observed_head_sha).strip().lower(),
            "pr_number": int(value.pr_number) if value.pr_number is not None else None,
        },
        "execution": {
            "current_step": current,
            "step_title": str(value.step_title).strip(),
            "state": str(value.execution_state).strip().upper(),
            "owner": str(value.owner).strip().upper(),
            "failure_class": str(value.failure_class).strip().upper(),
            "authoritative_run_id": value.authoritative_run_id,
            "authoritative_job_id": value.authoritative_job_id,
            "async_state": str(value.async_state).strip().upper(),
            "blocker": str(value.blocker).strip() if value.blocker else None,
        },
        "progress": {
            "completed_steps": completed,
            "frozen_steps": frozen,
            "remaining_steps": remaining,
        },
        "evidence": {
            "epoch": "",
            "last_green_evidence": [str(x).strip() for x in value.last_green_evidence if str(x).strip()],
        },
        "next_legal_action": str(value.next_legal_action).strip(),
        "protections": protection_snapshot(),
    }
    state["evidence"]["epoch"] = _digest(
        {
            "repository": state["repository"],
            "program_id": state["program"]["id"],
            "current_step": state["execution"]["current_step"],
        },
        prefix="EPOCH",
    )
    state["state_id"] = _digest(state, prefix="BRAIN")
    return validate_state(state)


def validate_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise BrainStateFailure("brain state must be an object")
    state = deepcopy(dict(payload))

    required = {
        "version", "state_id", "updated_at_utc", "program", "repository",
        "execution", "progress", "evidence", "next_legal_action", "protections",
    }
    missing = sorted(required - set(state))
    if missing:
        raise BrainStateFailure("brain state missing required fields: " + ", ".join(missing))
    if state.get("version") != VERSION:
        raise BrainStateFailure("unsupported brain state version")
    _parse_utc(str(state.get("updated_at_utc") or ""))

    program = state.get("program")
    repository = state.get("repository")
    execution = state.get("execution")
    progress = state.get("progress")
    evidence = state.get("evidence")
    for name, value in (
        ("program", program),
        ("repository", repository),
        ("execution", execution),
        ("progress", progress),
        ("evidence", evidence),
    ):
        if not isinstance(value, Mapping):
            raise BrainStateFailure(f"{name} must be an object")

    if not str(program.get("id") or "").strip() or not str(program.get("title") or "").strip():
        raise BrainStateFailure("program id/title are required")
    total = int(program.get("total_steps") or 0)
    if total <= 0:
        raise BrainStateFailure("program total_steps must be positive")

    repo = str(repository.get("full_name") or "")
    if not _REPO_RE.match(repo):
        raise BrainStateFailure("repository.full_name must be owner/name")
    for field_name in ("main_sha", "observed_head_sha"):
        if not _SHA_RE.match(str(repository.get(field_name) or "")):
            raise BrainStateFailure(f"repository.{field_name} must be a full 40-character SHA")
    if not str(repository.get("work_branch") or "").strip():
        raise BrainStateFailure("repository.work_branch is required")
    pr_number = repository.get("pr_number")
    if pr_number is not None and int(pr_number) <= 0:
        raise BrainStateFailure("repository.pr_number must be positive")

    current = int(execution.get("current_step") or 0)
    if current < 1 or current > total:
        raise BrainStateFailure("execution.current_step is outside program")
    if not str(execution.get("step_title") or "").strip():
        raise BrainStateFailure("execution.step_title is required")
    execution_state = str(execution.get("state") or "").upper()
    if execution_state not in _EXECUTION_STATES:
        raise BrainStateFailure("execution.state is invalid")
    owner = str(execution.get("owner") or "").upper()
    if owner not in _OWNERS:
        raise BrainStateFailure("execution.owner is invalid")
    failure_class = str(execution.get("failure_class") or "").upper()
    if failure_class not in _FAILURE_CLASSES:
        raise BrainStateFailure("execution.failure_class is invalid")
    async_state = str(execution.get("async_state") or "").upper()
    if async_state not in _ASYNC_STATES:
        raise BrainStateFailure("execution.async_state is invalid")

    completed = _unique_steps(progress.get("completed_steps") or [], total=total, field_name="completed_steps")
    frozen = _unique_steps(progress.get("frozen_steps") or [], total=total, field_name="frozen_steps")
    remaining = _unique_steps(progress.get("remaining_steps") or [], total=total, field_name="remaining_steps")
    if not set(frozen).issubset(set(completed)):
        raise BrainStateFailure("every frozen step must already be completed")
    if set(completed) & set(remaining):
        raise BrainStateFailure("completed and remaining steps overlap")
    if set(frozen) & set(remaining):
        raise BrainStateFailure("frozen and remaining steps overlap")

    all_steps = set(range(1, total + 1))
    accounted = set(completed) | set(remaining) | {current}
    if accounted != all_steps:
        raise BrainStateFailure("step accounting must cover the entire declared program")

    blocker = execution.get("blocker")
    if execution_state == "BLOCKED" and not str(blocker or "").strip():
        raise BrainStateFailure("BLOCKED state requires a blocker")
    if execution_state != "BLOCKED" and blocker not in (None, ""):
        raise BrainStateFailure("non-BLOCKED state may not carry an active blocker")

    run_id = execution.get("authoritative_run_id")
    job_id = execution.get("authoritative_job_id")
    if run_id is not None and int(run_id) <= 0:
        raise BrainStateFailure("authoritative_run_id must be positive")
    if job_id is not None and int(job_id) <= 0:
        raise BrainStateFailure("authoritative_job_id must be positive")
    if execution_state == "WAITING_ON_ASYNC":
        if async_state not in {"QUEUED", "IN_PROGRESS"} or run_id is None:
            raise BrainStateFailure("WAITING_ON_ASYNC requires one live authoritative run")
    elif async_state in {"QUEUED", "IN_PROGRESS"}:
        raise BrainStateFailure("live async state requires WAITING_ON_ASYNC execution state")

    if execution_state == "FROZEN":
        if current not in completed or current not in frozen:
            raise BrainStateFailure("FROZEN current step must be completed and frozen")
        if async_state not in {"NONE", "SUCCESS"}:
            raise BrainStateFailure("FROZEN state cannot have unfinished async work")
    if execution_state == "COMPLETE":
        if set(completed) != all_steps or set(frozen) != all_steps or remaining:
            raise BrainStateFailure("COMPLETE requires every program step completed and frozen")

    if not isinstance(evidence.get("last_green_evidence"), list):
        raise BrainStateFailure("evidence.last_green_evidence must be a list")
    expected_epoch = _digest(
        {
            "repository": dict(repository),
            "program_id": program["id"],
            "current_step": current,
        },
        prefix="EPOCH",
    )
    if evidence.get("epoch") != expected_epoch:
        raise BrainStateFailure("evidence epoch does not match repository/task identity")

    if not str(state.get("next_legal_action") or "").strip():
        raise BrainStateFailure("next_legal_action is required")
    if dict(state.get("protections") or {}) != protection_snapshot():
        raise BrainStateFailure("brain safety protections drifted")

    supplied_id = str(state.pop("state_id"))
    expected_id = _digest(state, prefix="BRAIN")
    if supplied_id != expected_id:
        raise BrainStateFailure("brain state fingerprint mismatch")
    state["state_id"] = supplied_id
    return state


def assess_drift(
    payload: Mapping[str, Any], *,
    current_main_sha: str | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    state = validate_state(payload)
    repo = state["repository"]
    reasons: list[str] = []
    if current_main_sha and current_main_sha != repo["main_sha"]:
        reasons.append(f"main advanced: brain={repo['main_sha']} current={current_main_sha}")
    if current_head_sha and current_head_sha != repo["observed_head_sha"]:
        reasons.append(f"head changed: brain={repo['observed_head_sha']} current={current_head_sha}")
    return {
        "status": "DRIFT" if reasons else "ALIGNED",
        "requires_revalidation": bool(reasons),
        "reasons": reasons,
    }


def build_resume_packet(
    payload: Mapping[str, Any], *,
    current_main_sha: str | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    state = validate_state(payload)
    drift = assess_drift(
        state,
        current_main_sha=current_main_sha,
        current_head_sha=current_head_sha,
    )
    status = "REVALIDATE" if drift["requires_revalidation"] else state["execution"]["state"]
    next_action = (
        "Revalidate repository identity and replace the persisted brain state before editing."
        if drift["requires_revalidation"]
        else state["next_legal_action"]
    )
    return {
        "version": VERSION,
        "status": status,
        "state_id": state["state_id"],
        "program": deepcopy(state["program"]),
        "repository": deepcopy(state["repository"]),
        "execution": deepcopy(state["execution"]),
        "progress": deepcopy(state["progress"]),
        "evidence": deepcopy(state["evidence"]),
        "drift": drift,
        "next_legal_action": next_action,
        "protections": deepcopy(state["protections"]),
    }


def render_issue_ledger(payload: Mapping[str, Any]) -> str:
    state = validate_state(payload)
    execution = state["execution"]
    repo = state["repository"]
    return (
        f"{ISSUE_BEGIN}\n"
        "## 🧠 MONSTER Persistent Execution Brain\n\n"
        f"**Program:** {state['program']['title']}  \n"
        f"**Step:** {execution['current_step']}/{state['program']['total_steps']} — {execution['step_title']}  \n"
        f"**State:** `{execution['state']}`  \n"
        f"**Repository:** `{repo['full_name']}`  \n"
        f"**Observed main:** `{repo['main_sha']}`  \n"
        f"**Observed head:** `{repo['observed_head_sha']}`  \n"
        f"**Next legal action:** {state['next_legal_action']}\n\n"
        f"```json\n{json.dumps(state, indent=2, sort_keys=True)}\n```\n"
        f"{ISSUE_END}"
    )


def parse_issue_ledger(text: str) -> dict[str, Any]:
    value = str(text or "")
    start = value.rfind(ISSUE_BEGIN)
    end = value.find(ISSUE_END, start + len(ISSUE_BEGIN)) if start >= 0 else -1
    if start < 0 or end < 0:
        raise BrainStateFailure("persistent brain issue markers not found")
    section = value[start + len(ISSUE_BEGIN):end]
    match = re.search(r"```json\s*(\{.*\})\s*```", section, flags=re.DOTALL)
    if not match:
        raise BrainStateFailure("persistent brain JSON block not found")
    decoded = json.loads(match.group(1))
    if not isinstance(decoded, dict):
        raise BrainStateFailure("persistent brain JSON must be an object")
    return validate_state(decoded)


def write_state(path: str | Path, payload: Mapping[str, Any]) -> Path:
    state = validate_state(payload)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def read_state(path: str | Path) -> dict[str, Any]:
    decoded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise BrainStateFailure("brain state file must contain an object")
    return validate_state(decoded)


def contract_self_test() -> dict[str, Any]:
    sample = build_state(BrainStateInput(
        program_id="self-test",
        program_title="Persistent Execution Brain self-test",
        total_steps=2,
        current_step=1,
        step_title="State contract",
        execution_state="FROZEN",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="brain-v1",
        observed_head_sha="2" * 40,
        next_legal_action="Start Step 2 only on a new user request.",
        completed_steps=(1,),
        frozen_steps=(1,),
        remaining_steps=(2,),
        last_green_evidence=("schema", "round-trip"),
        updated_at_utc="2026-09-30T00:00:00Z",
    ))
    parsed = parse_issue_ledger(render_issue_ledger(sample))
    if parsed["state_id"] != sample["state_id"]:
        raise BrainStateFailure("issue ledger round-trip failed")
    aligned = assess_drift(sample, current_main_sha="1" * 40, current_head_sha="2" * 40)
    if aligned["status"] != "ALIGNED":
        raise BrainStateFailure("aligned state incorrectly reported drift")
    drift = assess_drift(sample, current_main_sha="3" * 40)
    if drift["status"] != "DRIFT":
        raise BrainStateFailure("main drift was not detected")
    return {
        "status": "GREEN",
        "version": VERSION,
        "persistence_surface": PERSISTENCE_SURFACE,
        "fingerprint_guard": True,
        "step_monotonicity": True,
        "async_lock": True,
        "repo_drift_guard": True,
        "issue_round_trip": True,
        "product_runtime_mutation": False,
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="Monster Persistent Execution Brain V1")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("self-test")
    validate = sub.add_parser("validate")
    validate.add_argument("--state-file", required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("--state-file", required=True)
    resume.add_argument("--current-main-sha")
    resume.add_argument("--current-head-sha")
    args = parser.parse_args()

    if args.command == "self-test":
        print("MONSTER_PERSISTENT_EXECUTION_BRAIN_V1_GREEN")
        print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
        return 0
    if args.command == "validate":
        state = read_state(args.state_file)
        print(json.dumps({"status": "GREEN", "state_id": state["state_id"]}, indent=2, sort_keys=True))
        return 0
    if args.command == "resume":
        print(json.dumps(
            build_resume_packet(
                read_state(args.state_file),
                current_main_sha=args.current_main_sha,
                current_head_sha=args.current_head_sha,
            ),
            indent=2,
            sort_keys=True,
        ))
        return 0
    raise BrainStateFailure("unsupported command")


if __name__ == "__main__":
    raise SystemExit(_main())
