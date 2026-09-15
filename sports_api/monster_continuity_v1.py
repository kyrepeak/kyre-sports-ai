"""Monster Continuity Layer V1 — durable, resumable engineering checkpoints.

Developer-only tooling. It creates tiny, versioned, sanitized checkpoints that
survive chat streaming interruptions. It performs no live network calls and
never edits production/model/source data automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

CONTINUITY_VERSION = "MONSTER_CONTINUITY_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False
AUTO_FIX = False

MAX_CHECKPOINT_BYTES = 32768
MAX_TEXT_CHARS = 1200
MAX_LIST_ITEMS = 40
MAX_SANITIZE_DEPTH = 8

LEDGER_BEGIN = "<!-- MONSTER_CONTINUITY_V1:BEGIN -->"
LEDGER_END = "<!-- MONSTER_CONTINUITY_V1:END -->"

_TASK_STATES = {"ACTIVE", "BLOCKED", "READY_TO_MERGE", "COMPLETE"}
_STEP_STATES = {"PENDING", "IN_PROGRESS", "BLOCKED", "GREEN", "COMPLETE"}
_SECRET_KEY_RE = re.compile(
    r"(?i)(authorization|cookie|set-cookie|api[-_]?key|token|secret|password|passwd|credential)"
)
_SECRET_VALUE_RE = re.compile(r"(?i)\b(?:bearer|basic)\s+[^\s,;]+")
_URL_USERINFO_RE = re.compile(r"(?i)(https?://)[^/\s:@]+:[^@\s/]+@")
_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:token|api[-_]?key|secret|password|passwd|authorization|auth)=)[^&#\s]+"
)
_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("created_at_utc must be non-empty")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("created_at_utc must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _safe_text(value: Any, *, limit: int = MAX_TEXT_CHARS) -> str:
    text = str(value or "")
    text = _SECRET_VALUE_RE.sub("<redacted>", text)
    text = _URL_USERINFO_RE.sub(r"\1<redacted>@", text)
    text = _QUERY_SECRET_RE.sub(lambda match: f"{match.group(1)}<redacted>", text)
    return text[:limit]


def _sanitize_value(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if _SECRET_KEY_RE.search(str(key)):
        return "<redacted>"
    if depth >= MAX_SANITIZE_DEPTH:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:MAX_LIST_ITEMS]:
            child_key = _safe_text(raw_key, limit=120)
            result[child_key] = _sanitize_value(raw_value, key=child_key, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(item, depth=depth + 1) for item in list(value)[:MAX_LIST_ITEMS]]
    return _safe_text(value)


def _safe_list(values: Iterable[Any] | None, *, limit: int = MAX_LIST_ITEMS) -> list[str]:
    result: list[str] = []
    for item in list(values or [])[:limit]:
        text = _safe_text(item)
        if text and text not in result:
            result.append(text)
    return result


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _checkpoint_id(payload_without_id: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload_without_id).encode("utf-8")).hexdigest()[:16].upper()
    return f"MCP-{digest}"


@dataclass(frozen=True, slots=True)
class CheckpointInput:
    task_id: str
    task_title: str
    repo: str
    source_branch: str
    source_commit: str
    main_commit: str
    current_step: str
    step_title: str
    next_action: str
    task_status: str = "ACTIVE"
    step_status: str = "IN_PROGRESS"
    pr_number: int | None = None
    completed_steps: Sequence[str] = field(default_factory=tuple)
    remaining_steps: Sequence[str] = field(default_factory=tuple)
    last_green_evidence: Sequence[str] = field(default_factory=tuple)
    blockers: Sequence[str] = field(default_factory=tuple)
    in_scope: Sequence[str] = field(default_factory=tuple)
    forbidden_scope: Sequence[str] = field(default_factory=tuple)
    created_at_utc: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


def build_checkpoint(value: CheckpointInput) -> dict[str, Any]:
    task_status = str(value.task_status or "").upper()
    step_status = str(value.step_status or "").upper()
    if task_status not in _TASK_STATES:
        raise ValueError(f"Unsupported task_status: {task_status}")
    if step_status not in _STEP_STATES:
        raise ValueError(f"Unsupported step_status: {step_status}")

    created_at = value.created_at_utc or _utc_now()
    _parse_utc(created_at)

    body: dict[str, Any] = {
        "version": CONTINUITY_VERSION,
        "created_at_utc": created_at,
        "task": {
            "id": _safe_text(value.task_id, limit=160),
            "title": _safe_text(value.task_title, limit=300),
            "status": task_status,
        },
        "repo": _safe_text(value.repo, limit=240),
        "source": {
            "branch": _safe_text(value.source_branch, limit=240),
            "commit": _safe_text(value.source_commit, limit=80),
            "main_commit": _safe_text(value.main_commit, limit=80),
            "pr_number": int(value.pr_number) if value.pr_number is not None else None,
        },
        "progress": {
            "current_step": _safe_text(value.current_step, limit=120),
            "step_title": _safe_text(value.step_title, limit=300),
            "step_status": step_status,
            "completed_steps": _safe_list(value.completed_steps, limit=24),
            "remaining_steps": _safe_list(value.remaining_steps, limit=24),
        },
        "last_green_evidence": _safe_list(value.last_green_evidence),
        "blockers": _safe_list(value.blockers),
        "next_action": _safe_text(value.next_action),
        "scope": {
            "in_scope": _safe_list(value.in_scope),
            "forbidden": _safe_list(value.forbidden_scope),
        },
        "metadata": _sanitize_value(dict(value.metadata or {})),
        "protections": {
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
            "may_modify_runtime": MAY_MODIFY_RUNTIME,
            "network_calls": NETWORK_CALLS,
            "auto_fix": AUTO_FIX,
        },
    }
    checkpoint = dict(body)
    checkpoint["checkpoint_id"] = _checkpoint_id(body)
    validate_checkpoint(checkpoint)
    return checkpoint


def validate_checkpoint(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Checkpoint root must be an object")
    if payload.get("version") != CONTINUITY_VERSION:
        raise ValueError("Unsupported continuity checkpoint version")

    required_top = {
        "version", "checkpoint_id", "created_at_utc", "task", "repo", "source",
        "progress", "last_green_evidence", "blockers", "next_action", "scope",
        "metadata", "protections",
    }
    missing = sorted(required_top.difference(payload.keys()))
    if missing:
        raise ValueError(f"Checkpoint missing required fields: {', '.join(missing)}")

    _parse_utc(str(payload.get("created_at_utc") or ""))
    task = payload.get("task")
    source = payload.get("source")
    progress = payload.get("progress")
    scope = payload.get("scope")
    if not all(isinstance(item, Mapping) for item in (task, source, progress, scope)):
        raise ValueError("Checkpoint task/source/progress/scope fields must be objects")

    if not str(task.get("id") or "").strip() or not str(task.get("title") or "").strip():
        raise ValueError("task.id and task.title must be non-empty")
    if str(task.get("status") or "") not in _TASK_STATES:
        raise ValueError("task.status is invalid")

    repo = str(payload.get("repo") or "")
    if not _REPO_RE.match(repo):
        raise ValueError("repo must be in owner/name form")

    for field_name in ("branch", "commit", "main_commit"):
        if not str(source.get(field_name) or "").strip():
            raise ValueError(f"source.{field_name} must be non-empty")
    if not _SHA_RE.match(str(source.get("commit"))):
        raise ValueError("source.commit must look like a git SHA")
    if not _SHA_RE.match(str(source.get("main_commit"))):
        raise ValueError("source.main_commit must look like a git SHA")
    if source.get("pr_number") is not None and int(source["pr_number"]) <= 0:
        raise ValueError("source.pr_number must be positive")

    if not str(progress.get("current_step") or "").strip() or not str(progress.get("step_title") or "").strip():
        raise ValueError("progress current_step and step_title must be non-empty")
    if str(progress.get("step_status") or "") not in _STEP_STATES:
        raise ValueError("progress.step_status is invalid")

    for list_field in (
        payload.get("last_green_evidence"), payload.get("blockers"),
        progress.get("completed_steps"), progress.get("remaining_steps"),
        scope.get("in_scope"), scope.get("forbidden"),
    ):
        if not isinstance(list_field, list):
            raise ValueError("Checkpoint list fields must be arrays")
        if len(list_field) > MAX_LIST_ITEMS:
            raise ValueError("Checkpoint list field exceeds item limit")

    expected_protections = {
        "projection_weight": 0.0,
        "may_modify_projection": False,
        "may_modify_source_data": False,
        "may_modify_runtime": False,
        "network_calls": False,
        "auto_fix": False,
    }
    if not isinstance(payload.get("protections"), Mapping) or dict(payload["protections"]) != expected_protections:
        raise ValueError("Checkpoint safety protections were modified")

    without_id = dict(payload)
    supplied_id = str(without_id.pop("checkpoint_id", ""))
    if supplied_id != _checkpoint_id(without_id):
        raise ValueError("Checkpoint fingerprint mismatch")

    if len((_canonical_json(payload) + "\n").encode("utf-8")) > MAX_CHECKPOINT_BYTES:
        raise ValueError("Checkpoint exceeds safety size limit")
    return dict(payload)


def write_checkpoint(path: str | Path, checkpoint: Mapping[str, Any]) -> Path:
    payload = validate_checkpoint(checkpoint)
    target = Path(path)
    if target.suffix.lower() != ".json":
        raise ValueError("Checkpoint output path must use .json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def read_checkpoint(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Checkpoint file root must be an object")
    return validate_checkpoint(payload)


def assess_drift(
    checkpoint: Mapping[str, Any], *, current_branch: str | None = None,
    current_commit: str | None = None, current_main_commit: str | None = None,
) -> dict[str, Any]:
    payload = validate_checkpoint(checkpoint)
    source = payload["source"]
    reasons: list[str] = []
    if current_branch and str(current_branch) != str(source["branch"]):
        reasons.append(f"branch changed: checkpoint={source['branch']} current={_safe_text(current_branch, limit=240)}")
    if current_commit and str(current_commit) != str(source["commit"]):
        reasons.append(f"head changed: checkpoint={source['commit']} current={_safe_text(current_commit, limit=80)}")
    if current_main_commit and str(current_main_commit) != str(source["main_commit"]):
        reasons.append(f"main advanced: checkpoint={source['main_commit']} current={_safe_text(current_main_commit, limit=80)}")
    return {"status": "DRIFT" if reasons else "ALIGNED", "requires_revalidation": bool(reasons), "reasons": reasons}


def build_resume_packet(
    checkpoint: Mapping[str, Any], *, current_branch: str | None = None,
    current_commit: str | None = None, current_main_commit: str | None = None,
) -> dict[str, Any]:
    payload = validate_checkpoint(checkpoint)
    drift = assess_drift(
        payload, current_branch=current_branch, current_commit=current_commit,
        current_main_commit=current_main_commit,
    )
    task = payload["task"]
    progress = payload["progress"]
    if task["status"] == "COMPLETE":
        status = "COMPLETE"
    elif drift["requires_revalidation"]:
        status = "REVALIDATE"
    elif payload["blockers"] or task["status"] == "BLOCKED" or progress["step_status"] == "BLOCKED":
        status = "BLOCKED"
    else:
        status = "READY_TO_RESUME"

    instruction = (
        f"Resume {task['title']} at {progress['current_step']} — {progress['step_title']}. "
        f"Next action: {payload['next_action'] or 'Re-check the current task state.'}"
    )
    if status == "REVALIDATE":
        instruction = "Repository state drifted since the checkpoint. Revalidate identity and gates first. " + instruction
    elif status == "BLOCKED":
        instruction = "The checkpoint is blocked. Resolve the recorded blocker before editing. " + instruction
    elif status == "COMPLETE":
        instruction = f"{task['title']} is marked complete; do not redo completed work."

    return {
        "version": CONTINUITY_VERSION,
        "status": status,
        "checkpoint_id": payload["checkpoint_id"],
        "task": dict(task),
        "source": dict(payload["source"]),
        "progress": dict(progress),
        "last_green_evidence": list(payload["last_green_evidence"]),
        "blockers": list(payload["blockers"]),
        "next_action": payload["next_action"],
        "scope": dict(payload["scope"]),
        "drift": drift,
        "resume_instruction": instruction,
        "protections": dict(payload["protections"]),
    }


def render_ledger_comment(checkpoint: Mapping[str, Any]) -> str:
    payload = validate_checkpoint(checkpoint)
    task = payload["task"]
    progress = payload["progress"]
    source = payload["source"]
    pr_text = f"PR #{source['pr_number']}" if source.get("pr_number") else "No PR yet"
    json_blob = json.dumps(payload, indent=2, sort_keys=True)
    return (
        f"{LEDGER_BEGIN}\n### 👹 Monster Continuity Checkpoint\n"
        f"**Task:** {task['title']}  \n**Checkpoint:** `{payload['checkpoint_id']}`  \n"
        f"**Step:** {progress['current_step']} — {progress['step_title']} ({progress['step_status']})  \n"
        f"**Source:** `{source['branch']}` @ `{source['commit']}` · {pr_text}  \n"
        f"**Next:** {payload['next_action'] or 'Re-check current task state.'}\n\n"
        f"```json\n{json_blob}\n```\n{LEDGER_END}"
    )


def extract_ledger_checkpoint(comment: str) -> dict[str, Any]:
    text = str(comment or "")
    start = text.rfind(LEDGER_BEGIN)
    end = text.find(LEDGER_END, start + len(LEDGER_BEGIN)) if start >= 0 else -1
    if start < 0 or end < 0:
        raise ValueError("Monster continuity ledger markers not found")
    section = text[start + len(LEDGER_BEGIN):end]
    match = re.search(r"```json\s*(\{.*\})\s*```", section, flags=re.DOTALL)
    if not match:
        raise ValueError("Monster continuity JSON block not found")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError("Monster continuity ledger payload must be an object")
    return validate_checkpoint(payload)


def select_latest_checkpoint(checkpoints: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    validated = [validate_checkpoint(item) for item in checkpoints]
    if not validated:
        raise ValueError("At least one checkpoint is required")
    return max(validated, key=lambda item: _parse_utc(str(item["created_at_utc"])))


def _json_print(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monster Continuity Layer V1")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a continuity checkpoint")
    create.add_argument("--task-id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--repo", required=True)
    create.add_argument("--branch", required=True)
    create.add_argument("--commit", required=True)
    create.add_argument("--main-commit", required=True)
    create.add_argument("--step", required=True)
    create.add_argument("--step-title", required=True)
    create.add_argument("--next-action", required=True)
    create.add_argument("--task-status", default="ACTIVE")
    create.add_argument("--step-status", default="IN_PROGRESS")
    create.add_argument("--pr", type=int)
    create.add_argument("--completed", action="append", default=[])
    create.add_argument("--remaining", action="append", default=[])
    create.add_argument("--proof", action="append", default=[])
    create.add_argument("--blocker", action="append", default=[])
    create.add_argument("--in-scope", action="append", default=[])
    create.add_argument("--forbidden", action="append", default=[])
    create.add_argument("--created-at")
    create.add_argument("--output", required=True)

    resume = sub.add_parser("resume", help="Build a resume packet")
    resume.add_argument("--checkpoint", required=True)
    resume.add_argument("--current-branch")
    resume.add_argument("--current-commit")
    resume.add_argument("--current-main-commit")

    validate = sub.add_parser("validate", help="Validate a checkpoint")
    validate.add_argument("--checkpoint", required=True)

    ledger = sub.add_parser("ledger-comment", help="Render a GitHub-ledger-safe comment")
    ledger.add_argument("--checkpoint", required=True)

    parse_ledger = sub.add_parser("parse-ledger", help="Parse a saved ledger comment")
    parse_ledger.add_argument("--comment-file", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "create":
        checkpoint = build_checkpoint(CheckpointInput(
            task_id=args.task_id, task_title=args.title, repo=args.repo,
            source_branch=args.branch, source_commit=args.commit, main_commit=args.main_commit,
            current_step=args.step, step_title=args.step_title, next_action=args.next_action,
            task_status=args.task_status, step_status=args.step_status, pr_number=args.pr,
            completed_steps=args.completed, remaining_steps=args.remaining,
            last_green_evidence=args.proof, blockers=args.blocker, in_scope=args.in_scope,
            forbidden_scope=args.forbidden, created_at_utc=args.created_at,
        ))
        path = write_checkpoint(args.output, checkpoint)
        _json_print({"status": "CHECKPOINT_WRITTEN", "path": str(path), "checkpoint_id": checkpoint["checkpoint_id"]})
        return 0
    if args.command == "resume":
        _json_print(build_resume_packet(
            read_checkpoint(args.checkpoint), current_branch=args.current_branch,
            current_commit=args.current_commit, current_main_commit=args.current_main_commit,
        ))
        return 0
    if args.command == "validate":
        payload = read_checkpoint(args.checkpoint)
        _json_print({"status": "VALID", "checkpoint_id": payload["checkpoint_id"]})
        return 0
    if args.command == "ledger-comment":
        print(render_ledger_comment(read_checkpoint(args.checkpoint)))
        return 0
    if args.command == "parse-ledger":
        payload = extract_ledger_checkpoint(Path(args.comment_file).read_text(encoding="utf-8"))
        _json_print(payload)
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
