"""Monster Runtime Lab V1 — integrated reproduction-to-fix-plan command.

One read-only developer command connects:
reproduction -> sanitized replay artifact -> incident autopacket -> trace/parity
-> dependency/test selection -> smallest-safe-fix plan.

It performs no live network calls and never edits production/model/source data.
Live GitHub/Render/PostHog evidence can be supplied by the caller or ChatGPT
connectors and folded into the Incident Autopacket separately.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import requests

from sports_api.monster_incident_autopacket_v1 import IncidentInput, build_incident_packet
from sports_api.monster_runtime_capture_v1 import ReplayArtifact, capture_response, write_artifact
from sports_api.monster_runtime_replay_v1 import (
    ReplaySession,
    body_aware_json_helper,
    canonical_http_scenarios,
    legacy_json_helper,
)
from sports_api.monster_runtime_trace_v1 import ParityIdentity
from sports_api.monster_targeted_fix_planner_v1 import build_fix_plan

RUNTIME_LAB_VERSION = "MONSTER_RUNTIME_LAB_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False
AUTO_FIX = False
FUZZY_MATCHING = False


def _reproduce(url: str, artifact: ReplayArtifact) -> dict[str, Any]:
    legacy_session = ReplaySession()
    legacy_session.register(url, artifact.to_fixture())
    legacy: dict[str, Any]
    try:
        status, payload = legacy_json_helper(legacy_session, url)
        legacy = {
            "outcome": "returned",
            "status_code": status,
            "payload": payload,
        }
    except requests.HTTPError as exc:
        legacy = {
            "outcome": "raised_http_error",
            "status_code": getattr(exc.response, "status_code", None),
            "error_type": type(exc).__name__,
        }
    except requests.Timeout as exc:
        legacy = {"outcome": "timeout", "status_code": None, "error_type": type(exc).__name__}
    except Exception as exc:
        legacy = {"outcome": "raised", "status_code": None, "error_type": type(exc).__name__}

    body_session = ReplaySession()
    body_session.register(url, artifact.to_fixture())
    aware: dict[str, Any]
    try:
        status, payload = body_aware_json_helper(body_session, url)
        aware = {
            "outcome": "returned",
            "status_code": status,
            "payload": payload,
        }
    except requests.Timeout as exc:
        aware = {"outcome": "timeout", "status_code": None, "error_type": type(exc).__name__}
    except Exception as exc:
        aware = {"outcome": "raised", "status_code": None, "error_type": type(exc).__name__}

    return {
        "legacy_helper": legacy,
        "body_aware_helper": aware,
        "legacy_receipt": legacy_session.receipt(),
        "body_aware_receipt": body_session.receipt(),
    }


def run_runtime_lab(
    *,
    repo_root: str | Path = ".",
    scenario: str = "503",
    url: str = "https://runtime.invalid/api/v1/cfb/odds",
    target: str = "",
    sport: str = "",
    title: str = "Runtime incident",
    symptom: str = "",
    failure_signature: str = "",
    source_branch: str = "",
    source_commit: str = "",
    runtime_branch: str = "",
    runtime_commit: str = "",
    expected_runtime_branch: str = "",
) -> dict[str, Any]:
    scenarios = canonical_http_scenarios()
    if scenario not in scenarios:
        raise ValueError(f"Unknown runtime replay scenario: {scenario}")

    fixture = scenarios[scenario]
    artifact = capture_response(
        route_key=f"scenario-{scenario}",
        url=url,
        status_code=fixture.status_code,
        json_body=fixture.json_body,
        headers=fixture.headers,
        malformed_json=fixture.malformed_json,
        timeout=fixture.timeout,
        note=f"Generated from canonical Runtime Lab scenario {scenario}",
    )
    reproduction = _reproduce(artifact.url, artifact)

    parity: ParityIdentity | None = None
    supplied_identity = any(
        [source_branch, source_commit, runtime_branch, runtime_commit, expected_runtime_branch]
    )
    if supplied_identity:
        parity = ParityIdentity(
            source_branch=source_branch or "unknown",
            source_commit=source_commit or "unknown",
            runtime_branch=runtime_branch or "unknown",
            runtime_commit=runtime_commit or "unknown",
            expected_runtime_branch=expected_runtime_branch or runtime_branch or source_branch or "unknown",
        )

    incident = IncidentInput(
        title=title,
        symptom=symptom or f"Replay scenario {scenario}",
        target=target,
        failure_signature=failure_signature,
        sport=sport,
        route=artifact.url,
        surface="runtime-lab",
        parity_identity=parity,
        replay_artifact=artifact,
    )
    packet = build_incident_packet(incident, repo_root=repo_root)
    plan = build_fix_plan(packet)

    if plan["status"] == "PLAN_READY":
        status = "READY_TO_PATCH"
    elif plan["status"] == "BLOCKED_BY_PARITY":
        status = "BLOCKED"
    else:
        status = "NEED_MORE_EVIDENCE"

    return {
        "version": RUNTIME_LAB_VERSION,
        "status": status,
        "scenario": scenario,
        "replay_artifact": {
            "fingerprint": artifact.fingerprint,
            "payload": artifact.as_dict(),
        },
        "reproduction": reproduction,
        "incident_packet": packet,
        "fix_plan": plan,
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


def _human(report: dict[str, Any]) -> str:
    plan = report["fix_plan"]
    reproduction = report["reproduction"]
    lines = [
        f"👹 {RUNTIME_LAB_VERSION} — {report['status']}",
        f"Scenario: {report['scenario']} • artifact={report['replay_artifact']['fingerprint']}",
        (
            "Legacy helper: "
            f"{reproduction['legacy_helper']['outcome']} "
            f"HTTP={reproduction['legacy_helper'].get('status_code')}"
        ),
        (
            "Body-aware helper: "
            f"{reproduction['body_aware_helper']['outcome']} "
            f"HTTP={reproduction['body_aware_helper'].get('status_code')}"
        ),
        f"Plan: {plan['status']} • confidence={plan['root_cause_confidence']}",
        f"Root cause: {plan['root_cause'] or 'not yet proven'}",
        f"Next: {plan['next_action']}",
        "Edit candidates: " + (", ".join(plan.get("edit_candidates") or []) or "none"),
        "Required tests: " + (", ".join(plan.get("required_tests") or []) or "none"),
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monster Runtime Lab V1")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--scenario",
        default="503",
        choices=sorted(canonical_http_scenarios()),
        help="Deterministic HTTP replay scenario.",
    )
    parser.add_argument("--url", default="https://runtime.invalid/api/v1/cfb/odds")
    parser.add_argument("--target", default="")
    parser.add_argument("--sport", default="")
    parser.add_argument("--title", default="Runtime incident")
    parser.add_argument("--symptom", default="")
    parser.add_argument("--failure-signature", default="")
    parser.add_argument("--source-branch", default="")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--runtime-branch", default="")
    parser.add_argument("--runtime-commit", default="")
    parser.add_argument("--expected-runtime-branch", default="")
    parser.add_argument("--save-artifact", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_runtime_lab(
        repo_root=args.repo_root,
        scenario=args.scenario,
        url=args.url,
        target=args.target,
        sport=args.sport,
        title=args.title,
        symptom=args.symptom,
        failure_signature=args.failure_signature,
        source_branch=args.source_branch,
        source_commit=args.source_commit,
        runtime_branch=args.runtime_branch,
        runtime_commit=args.runtime_commit,
        expected_runtime_branch=args.expected_runtime_branch,
    )
    if args.save_artifact:
        artifact = capture_response(**{
            "route_key": report["replay_artifact"]["payload"]["route_key"],
            "url": report["replay_artifact"]["payload"]["url"],
            "status_code": report["replay_artifact"]["payload"]["status_code"],
            "json_body": report["replay_artifact"]["payload"]["json_body"],
            "headers": report["replay_artifact"]["payload"]["headers"],
            "params": report["replay_artifact"]["payload"]["params"],
            "method": report["replay_artifact"]["payload"]["method"],
            "malformed_json": report["replay_artifact"]["payload"]["malformed_json"],
            "timeout": report["replay_artifact"]["payload"]["timeout"],
            "note": report["replay_artifact"]["payload"]["note"],
        })
        write_artifact(args.save_artifact, artifact)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(_human(report))
    return 0 if report["status"] in {"READY_TO_PATCH", "NEED_MORE_EVIDENCE"} else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "AUTO_FIX",
    "FUZZY_MATCHING",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RUNTIME",
    "MAY_MODIFY_SOURCE_DATA",
    "NETWORK_CALLS",
    "PROJECTION_WEIGHT",
    "RUNTIME_LAB_VERSION",
    "run_runtime_lab",
]
