"""Monster Live Bridge V1 — one read-only operational picture across live evidence.

The module performs no external network calls. ChatGPT/connectors collect GitHub,
Render, and PostHog evidence and feed sanitized snapshots into this deterministic
bridge. Existing Runtime Lab, Continuity, Failure Memory, Dependency Map,
Performance Profiler, Test Matrix, Error Radar, and Certification evidence are
combined into one release/incident packet.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from sports_api.monster_continuity_v1 import build_resume_packet, validate_checkpoint
from sports_api.monster_incident_autopacket_v1 import IncidentInput, build_incident_packet
from sports_api.monster_targeted_fix_planner_v1 import build_fix_plan

LIVE_BRIDGE_VERSION = "MONSTER_LIVE_BRIDGE_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False
AUTO_FIX = False
FUZZY_MATCHING = False
AUTHORITATIVE_MERGE_GATE = "devsystem-final-gate"

SOURCE_STATES = {"AVAILABLE", "UNAVAILABLE", "NOT_CONFIGURED", "STALE"}
FINAL_GATE_PASS = {"PASS", "PASSED", "SUCCESS", "GREEN"}
FINAL_GATE_FAIL = {"FAIL", "FAILED", "FAILURE", "ERROR", "RED"}
RENDER_FAIL_STATES = {"FAILED", "CANCELED", "CANCELLED", "ERROR"}
MAX_TEXT_CHARS = 1600
MAX_LIST_ITEMS = 50
MAX_DEPTH = 8

_SECRET_KEY_RE = re.compile(
    r"(?i)(authorization|cookie|set-cookie|api[-_]?key|token|secret|password|passwd|credential|private[-_]?key)"
)
_SECRET_VALUE_RE = re.compile(r"(?i)\b(?:bearer|basic)\s+[^\s,;]+")
_URL_USERINFO_RE = re.compile(r"(?i)(https?://)[^/\s:@]+:[^@\s/]+@")
_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:token|api[-_]?key|secret|password|passwd|authorization|auth)=)[^&#\s]+"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_text(value: Any, *, limit: int = MAX_TEXT_CHARS) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = _SECRET_VALUE_RE.sub("<redacted>", text)
    text = _URL_USERINFO_RE.sub(r"\1<redacted>@", text)
    text = _QUERY_SECRET_RE.sub(lambda match: f"{match.group(1)}<redacted>", text)
    return text[:limit]


def _sanitize(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if _SECRET_KEY_RE.search(str(key)):
        return "<redacted>"
    if depth >= MAX_DEPTH:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:MAX_LIST_ITEMS]:
            child_key = _safe_text(raw_key, limit=160)
            result[child_key] = _sanitize(raw_value, key=child_key, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item, depth=depth + 1) for item in list(value)[:MAX_LIST_ITEMS]]
    return _safe_text(value)


def _norm_state(value: str) -> str:
    state = str(value or "").upper().strip()
    if state not in SOURCE_STATES:
        raise ValueError(f"Unsupported source state: {state}")
    return state


def _norm_gate(value: Any) -> str:
    return str(value or "UNKNOWN").upper().strip()


def _safe_list(values: Sequence[Any] | None) -> list[str]:
    result: list[str] = []
    for item in list(values or ())[:MAX_LIST_ITEMS]:
        text = _safe_text(item)
        if text and text not in result:
            result.append(text)
    return result


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    source: str
    status: str
    data: Mapping[str, Any] = field(default_factory=dict)
    observed_at_utc: str = field(default_factory=_utc_now)
    note: str = ""

    def __post_init__(self) -> None:
        _norm_state(self.status)
        if not str(self.source or "").strip():
            raise ValueError("source must be non-empty")

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": _safe_text(self.source, limit=80),
            "status": _norm_state(self.status),
            "observed_at_utc": _safe_text(self.observed_at_utc, limit=80),
            "data": _sanitize(dict(self.data)),
            "note": _safe_text(self.note),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SourceEvidence":
        return cls(
            source=str(payload.get("source") or "unknown"),
            status=str(payload.get("status") or "NOT_CONFIGURED"),
            data=dict(payload.get("data") or {}),
            observed_at_utc=str(payload.get("observed_at_utc") or _utc_now()),
            note=str(payload.get("note") or ""),
        )


def github_evidence(
    *,
    main_sha: str,
    working_branch: str = "main",
    working_sha: str = "",
    pr_number: int | None = None,
    changed_files: Sequence[str] = (),
    final_gate: str = "UNKNOWN",
    unresolved_review_threads: int = 0,
    expected_deploy_sha: str = "",
    expected_deploy_branch: str = "main",
    status: str = "AVAILABLE",
    observed_at_utc: str | None = None,
    note: str = "",
) -> SourceEvidence:
    return SourceEvidence(
        source="github",
        status=status,
        observed_at_utc=observed_at_utc or _utc_now(),
        note=note,
        data={
            "main_sha": _safe_text(main_sha, limit=80),
            "working_branch": _safe_text(working_branch, limit=240),
            "working_sha": _safe_text(working_sha or main_sha, limit=80),
            "pr_number": int(pr_number) if pr_number is not None else None,
            "changed_files": _safe_list(changed_files),
            "final_gate": _norm_gate(final_gate),
            "unresolved_review_threads": max(0, int(unresolved_review_threads)),
            "expected_deploy_sha": _safe_text(expected_deploy_sha or main_sha, limit=80),
            "expected_deploy_branch": _safe_text(expected_deploy_branch or "main", limit=240),
        },
    )


def render_evidence(
    *,
    service_id: str = "",
    service_name: str = "",
    branch: str = "",
    deployed_commit: str = "",
    deploy_id: str = "",
    deploy_status: str = "UNKNOWN",
    log_lines: Sequence[str] = (),
    metrics: Mapping[str, Any] | None = None,
    status: str = "AVAILABLE",
    observed_at_utc: str | None = None,
    note: str = "",
) -> SourceEvidence:
    return SourceEvidence(
        source="render",
        status=status,
        observed_at_utc=observed_at_utc or _utc_now(),
        note=note,
        data={
            "service_id": _safe_text(service_id, limit=160),
            "service_name": _safe_text(service_name, limit=240),
            "branch": _safe_text(branch, limit=240),
            "deployed_commit": _safe_text(deployed_commit, limit=80),
            "deploy_id": _safe_text(deploy_id, limit=160),
            "deploy_status": _norm_gate(deploy_status),
            "log_lines": _safe_list(log_lines),
            "metrics": _sanitize(dict(metrics or {})),
        },
    )


def posthog_evidence(
    *,
    project: str = "",
    active_issue_count: int = 0,
    recent_issues: Sequence[Mapping[str, Any]] = (),
    slow_request_count: int | None = None,
    latest_fingerprints: Sequence[str] = (),
    status: str = "AVAILABLE",
    observed_at_utc: str | None = None,
    note: str = "",
) -> SourceEvidence:
    return SourceEvidence(
        source="posthog",
        status=status,
        observed_at_utc=observed_at_utc or _utc_now(),
        note=note,
        data={
            "project": _safe_text(project, limit=240),
            "active_issue_count": max(0, int(active_issue_count)),
            "recent_issues": _sanitize(list(recent_issues)[:25]),
            "slow_request_count": None if slow_request_count is None else max(0, int(slow_request_count)),
            "latest_fingerprints": _safe_list(latest_fingerprints),
        },
    )


def unavailable_source(source: str, *, note: str = "", state: str = "UNAVAILABLE") -> SourceEvidence:
    return SourceEvidence(source=source, status=state, data={}, note=note)


def compare_deployment_parity(github: SourceEvidence, render: SourceEvidence) -> dict[str, Any]:
    gh = github.as_dict()
    rd = render.as_dict()
    if gh["status"] != "AVAILABLE" or rd["status"] != "AVAILABLE":
        return {
            "status": "UNKNOWN",
            "blocking": False,
            "reasons": ["GitHub and Render must both be AVAILABLE for deployment parity."],
        }

    expected_sha = str(gh["data"].get("expected_deploy_sha") or "")
    expected_branch = str(gh["data"].get("expected_deploy_branch") or "")
    deployed_sha = str(rd["data"].get("deployed_commit") or "")
    deployed_branch = str(rd["data"].get("branch") or "")
    reasons: list[str] = []
    if not deployed_sha:
        reasons.append("Render deployed commit is unavailable.")
    elif expected_sha and deployed_sha != expected_sha:
        reasons.append(f"deployed commit drift: expected={expected_sha} render={deployed_sha}")
    if expected_branch and deployed_branch and expected_branch != deployed_branch:
        reasons.append(f"deployed branch drift: expected={expected_branch} render={deployed_branch}")
    return {
        "status": "DRIFT" if reasons else "ALIGNED",
        "blocking": bool(reasons),
        "expected_sha": expected_sha,
        "deployed_sha": deployed_sha,
        "expected_branch": expected_branch,
        "deployed_branch": deployed_branch,
        "reasons": reasons,
    }


def _certification_summary(receipt: Mapping[str, Any] | None) -> dict[str, Any]:
    if receipt is None:
        return {"status": "NOT_PROVIDED", "blocking": False, "provided": False}
    safe = _sanitize(dict(receipt))
    status = _norm_gate(safe.get("status"))
    failed = int(safe.get("failed_check_count") or 0)
    return {
        "status": status,
        "blocking": status not in FINAL_GATE_PASS or failed > 0,
        "provided": True,
        "passed_check_count": int(safe.get("passed_check_count") or 0),
        "required_check_count": int(safe.get("required_check_count") or 0),
        "failed_check_count": failed,
    }


def _has_incident(incident: IncidentInput) -> bool:
    return bool(
        incident.symptom
        or incident.target
        or incident.request_id
        or incident.error_fingerprint
        or incident.failure_signature
        or incident.replay_artifact is not None
        or incident.total_ms is not None
    )


def build_live_bridge(
    incident: IncidentInput,
    *,
    github: SourceEvidence,
    render: SourceEvidence | None = None,
    posthog: SourceEvidence | None = None,
    continuity_checkpoint: Mapping[str, Any] | None = None,
    certification_receipt: Mapping[str, Any] | None = None,
    current_branch: str | None = None,
    current_commit: str | None = None,
    current_main_commit: str | None = None,
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    render = render or unavailable_source(
        "render", state="NOT_CONFIGURED", note="Render evidence was not supplied."
    )
    posthog = posthog or unavailable_source(
        "posthog", state="NOT_CONFIGURED", note="PostHog evidence was not supplied."
    )

    active_incident = _has_incident(incident)
    incident_packet = build_incident_packet(incident, repo_root=repo_root)
    fix_plan = build_fix_plan(incident_packet) if active_incident else None

    continuity: dict[str, Any] | None = None
    if continuity_checkpoint is not None:
        continuity = build_resume_packet(
            validate_checkpoint(continuity_checkpoint),
            current_branch=current_branch,
            current_commit=current_commit,
            current_main_commit=current_main_commit,
        )

    gh = github.as_dict()
    rd = render.as_dict()
    ph = posthog.as_dict()
    parity = compare_deployment_parity(github, render)
    certification = _certification_summary(certification_receipt)

    blockers: list[str] = []
    warnings: list[str] = []
    signals: list[str] = []

    gate = _norm_gate(gh["data"].get("final_gate"))
    if gate in FINAL_GATE_FAIL:
        blockers.append(f"GitHub {AUTHORITATIVE_MERGE_GATE} is {gate}.")
    elif gate not in FINAL_GATE_PASS:
        warnings.append(f"GitHub {AUTHORITATIVE_MERGE_GATE} status is {gate}.")

    unresolved = int(gh["data"].get("unresolved_review_threads") or 0)
    if unresolved:
        blockers.append(f"GitHub PR has {unresolved} unresolved review thread(s).")

    if parity.get("blocking"):
        blockers.extend(str(item) for item in parity.get("reasons") or [])

    render_deploy_status = _norm_gate(rd["data"].get("deploy_status"))
    if rd["status"] == "AVAILABLE" and render_deploy_status in RENDER_FAIL_STATES:
        blockers.append(f"Render deploy status is {render_deploy_status}.")

    if certification.get("blocking"):
        blockers.append(f"Monster certification status is {certification.get('status')}.")
    elif not certification.get("provided"):
        warnings.append("Monster certification receipt was not provided.")

    if continuity is not None:
        if continuity.get("status") == "REVALIDATE":
            blockers.append("Continuity checkpoint detected repository drift and requires revalidation.")
        elif continuity.get("status") == "BLOCKED":
            blockers.append("Continuity checkpoint is blocked.")
        # COMPLETE is informational only; it must never manufacture an incident/action signal.

    for source in (gh, rd, ph):
        if source["status"] in {"UNAVAILABLE", "STALE"}:
            warnings.append(f"{source['source']} evidence is {source['status']}.")
        elif source["status"] == "NOT_CONFIGURED":
            warnings.append(f"{source['source']} evidence is NOT_CONFIGURED.")

    active_issues = int(ph["data"].get("active_issue_count") or 0)
    if ph["status"] == "AVAILABLE" and active_issues:
        signals.append(f"PostHog reports {active_issues} active error issue(s) in the supplied window.")

    slow_count = ph["data"].get("slow_request_count")
    if ph["status"] == "AVAILABLE" and isinstance(slow_count, int) and slow_count > 0:
        signals.append(f"PostHog reports {slow_count} slow request signal(s) in the supplied window.")

    if blockers:
        overall = "BLOCKED"
    elif active_incident and fix_plan and fix_plan.get("status") == "PLAN_READY":
        overall = "ACTION_REQUIRED"
    elif active_incident:
        # An unresolved incident is never HEALTHY just because no exact fix is known yet.
        overall = "DEGRADED"
    elif signals:
        overall = "ACTION_REQUIRED"
    elif warnings:
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    cert_pass = certification.get("provided") and certification.get("status") in FINAL_GATE_PASS
    fully_proved = (
        not blockers
        and gate in FINAL_GATE_PASS
        and parity.get("status") == "ALIGNED"
        and unresolved == 0
        and bool(cert_pass)
    )
    if blockers:
        release_status = "BLOCKED"
    elif fully_proved:
        release_status = "READY"
    else:
        release_status = "UNKNOWN"

    if blockers:
        next_action = blockers[0]
    elif fix_plan and fix_plan.get("next_action"):
        next_action = _safe_text(fix_plan.get("next_action"))
    elif signals:
        next_action = signals[0]
    elif warnings:
        next_action = warnings[0]
    else:
        next_action = "No immediate action required; live evidence is aligned and green."

    return {
        "version": LIVE_BRIDGE_VERSION,
        "status": overall,
        "release": {
            "status": release_status,
            "authoritative_merge_gate": AUTHORITATIVE_MERGE_GATE,
            "blockers": _safe_list(blockers),
            "warnings": _safe_list(warnings),
        },
        "sources": {"github": gh, "render": rd, "posthog": ph},
        "deployment_parity": parity,
        "continuity": continuity,
        "certification": certification,
        "incident": {
            "active": active_incident,
            "packet": incident_packet,
            "fix_plan": fix_plan,
        },
        "signals": _safe_list(signals),
        "next_action": next_action,
        "protections": {
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
            "may_modify_runtime": MAY_MODIFY_RUNTIME,
            "network_calls": NETWORK_CALLS,
            "auto_fix": AUTO_FIX,
            "fuzzy_matching": FUZZY_MATCHING,
        },
    }


def _load_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _incident_from_mapping(payload: Mapping[str, Any]) -> IncidentInput:
    allowed = {
        "title", "symptom", "target", "request_id", "error_fingerprint",
        "failure_signature", "sport", "route", "surface", "total_ms",
    }
    data = {key: payload[key] for key in allowed if key in payload}
    data.setdefault("title", "Monster Live Bridge snapshot")
    data.setdefault("symptom", "")
    return IncidentInput(**data)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monster Live Bridge V1")
    parser.add_argument("--incident", required=True, help="Incident JSON")
    parser.add_argument("--github", required=True, help="Normalized GitHub SourceEvidence JSON")
    parser.add_argument("--render", help="Normalized Render SourceEvidence JSON")
    parser.add_argument("--posthog", help="Normalized PostHog SourceEvidence JSON")
    parser.add_argument("--checkpoint", help="Monster Continuity checkpoint JSON")
    parser.add_argument("--certification", help="Monster certification receipt JSON")
    parser.add_argument("--current-branch")
    parser.add_argument("--current-commit")
    parser.add_argument("--current-main-commit")
    parser.add_argument("--repo-root", default=".")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    incident_payload = _load_json(args.incident) or {}
    github_payload = _load_json(args.github) or {}
    render_payload = _load_json(args.render)
    posthog_payload = _load_json(args.posthog)
    checkpoint = _load_json(args.checkpoint)
    certification = _load_json(args.certification)

    report = build_live_bridge(
        _incident_from_mapping(incident_payload),
        github=SourceEvidence.from_dict(github_payload),
        render=SourceEvidence.from_dict(render_payload) if render_payload else None,
        posthog=SourceEvidence.from_dict(posthog_payload) if posthog_payload else None,
        continuity_checkpoint=checkpoint,
        certification_receipt=certification,
        current_branch=args.current_branch,
        current_commit=args.current_commit,
        current_main_commit=args.current_main_commit,
        repo_root=args.repo_root,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AUTHORITATIVE_MERGE_GATE",
    "AUTO_FIX",
    "FUZZY_MATCHING",
    "LIVE_BRIDGE_VERSION",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RUNTIME",
    "MAY_MODIFY_SOURCE_DATA",
    "NETWORK_CALLS",
    "PROJECTION_WEIGHT",
    "SourceEvidence",
    "build_live_bridge",
    "compare_deployment_parity",
    "github_evidence",
    "posthog_evidence",
    "render_evidence",
    "unavailable_source",
]
