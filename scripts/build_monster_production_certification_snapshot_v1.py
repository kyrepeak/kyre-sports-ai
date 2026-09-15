"""Build deterministic Monster Production Certification V1 snapshots.

This module is intentionally read-only. V1 classifies already-collected evidence;
it does not deploy, mutate Render, or alter sports runtime/projection behavior.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any
from urllib.request import Request, urlopen

VERSION = "MONSTER_PRODUCTION_CERTIFICATION_V1"
ALLOWED_HTTP_METHODS = frozenset({"GET"})
HTTP_TIMEOUT_SECONDS = 20
MAX_JSON_BYTES = 2_000_000
_GREEN_GUARD_VALUES = frozenset({"green", "success", "passed", "pass", "ok", "true"})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _valid_sha(value: Any) -> bool:
    text = _text(value).lower()
    return len(text) == 40 and all(char in "0123456789abcdef" for char in text)


def _normalized_guard_value(value: Any) -> str:
    return _text(value).lower()


def get_json(url: str, *, opener=urlopen) -> dict[str, Any]:
    """Fetch one JSON object with a bounded, GET-only request."""
    request = Request(
        str(url),
        headers={
            "Accept": "application/json",
            "User-Agent": "KyreSportsAI-MonsterProductionCertificationV1/1.0",
        },
        method="GET",
    )
    with opener(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        status = int(getattr(response, "status", 0) or 0)
        if status != 200:
            raise RuntimeError(f"GET {url} returned HTTP {status}")
        raw = response.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise RuntimeError(f"GET {url} exceeded {MAX_JSON_BYTES} bytes")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"GET {url} returned non-object JSON")
    return payload


def collect_runtime_health(
    base_url: str,
    *,
    fetch_json=get_json,
) -> dict[str, dict[str, Any]]:
    """Read only the certified liveness and readiness endpoints."""
    base = str(base_url).rstrip("/")
    return {
        "health": fetch_json(f"{base}/health"),
        "readiness": fetch_json(f"{base}/health/ready"),
    }


def normalize_render_evidence(
    service: Mapping[str, Any],
    deploy: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize the read-only Render service/deploy shape used by the classifier."""
    service_map = _mapping(service) or {}
    deploy_map = _mapping(deploy) or {}
    commit_map = _mapping(deploy_map.get("commit")) or {}
    return {
        "branch": _text(service_map.get("branch")),
        "commit": _text(commit_map.get("id")).lower(),
        "status": _text(deploy_map.get("status")).lower(),
        "service_id": _text(service_map.get("id")),
        "deploy_id": _text(deploy_map.get("id")),
        "auto_deploy": _text(service_map.get("autoDeploy")).lower(),
    }


def _unknown_reasons(
    *,
    github: Mapping[str, Any],
    render: Mapping[str, Any],
    health: Mapping[str, Any],
    readiness: Mapping[str, Any],
    guards: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []

    if not _text(github.get("branch")):
        reasons.append("github branch missing")
    if not _valid_sha(github.get("commit")):
        reasons.append("github commit missing or malformed")

    if not _text(render.get("branch")):
        reasons.append("render branch missing")
    if not _valid_sha(render.get("commit")):
        reasons.append("render commit missing or malformed")
    if "status" not in render:
        reasons.append("render status missing")

    health_deployment = _mapping(health.get("deployment"))
    if health_deployment is None:
        reasons.append("health deployment missing")
    else:
        if not _text(health_deployment.get("branch")):
            reasons.append("health branch missing")
        if not _valid_sha(health_deployment.get("commit")):
            reasons.append("health commit missing or malformed")

    readiness_checks = _mapping(readiness.get("checks"))
    readiness_deployment = _mapping(readiness.get("deployment"))
    if readiness_checks is None:
        reasons.append("readiness checks missing")
    if readiness_deployment is None:
        reasons.append("readiness deployment missing")
    else:
        if not _text(readiness_deployment.get("branch")):
            reasons.append("readiness branch missing")
        if not _valid_sha(readiness_deployment.get("commit")):
            reasons.append("readiness commit missing or malformed")

    if not guards:
        reasons.append("required guard evidence missing")

    return reasons


def build_snapshot(
    *,
    github: Mapping[str, Any],
    render: Mapping[str, Any],
    health: Mapping[str, Any],
    readiness: Mapping[str, Any],
    guards: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    """Return one deterministic certification snapshot from normalized evidence."""
    github_map = _mapping(github) or {}
    render_map = _mapping(render) or {}
    health_map = _mapping(health) or {}
    readiness_map = _mapping(readiness) or {}
    guards_map = _mapping(guards) or {}

    health_deployment = _mapping(health_map.get("deployment")) or {}
    readiness_checks = _mapping(readiness_map.get("checks")) or {}
    readiness_deployment = _mapping(readiness_map.get("deployment")) or {}

    unknown = _unknown_reasons(
        github=github_map,
        render=render_map,
        health=health_map,
        readiness=readiness_map,
        guards=guards_map,
    )

    identity = {
        "github_branch": _text(github_map.get("branch")),
        "github_commit": _text(github_map.get("commit")).lower(),
        "render_branch": _text(render_map.get("branch")),
        "render_commit": _text(render_map.get("commit")).lower(),
        "health_branch": _text(health_deployment.get("branch")),
        "health_commit": _text(health_deployment.get("commit")).lower(),
    }
    normalized_guards = {
        str(name): _normalized_guard_value(value)
        for name, value in sorted(guards_map.items(), key=lambda item: str(item[0]))
    }

    state = "GREEN"
    reasons: list[str] = []

    if unknown:
        state = "UNKNOWN"
        reasons = unknown
    elif _text(render_map.get("status")).lower() != "live":
        state = "DEPLOY_FAILED"
        reasons = [f"render status is {_text(render_map.get('status')) or 'missing'}"]
    elif _text(health_map.get("status")).lower() != "ok":
        state = "RUNTIME_PROOF_FAILED"
        reasons = [f"health status is {_text(health_map.get('status')) or 'missing'}"]
    else:
        readiness_ok = (
            _text(readiness_map.get("status")).lower() == "ready"
            and readiness_checks.get("process_running") is True
            and readiness_checks.get("python_runtime") is True
            and readiness_checks.get("deployment_identity_available") is True
            and readiness_checks.get("runtime_branch_alignment") is True
            and readiness_deployment.get("aligned") is True
            and health_deployment.get("branch_aligned") is True
        )
        if not readiness_ok:
            state = "NOT_READY"
            reasons = ["runtime readiness or branch alignment is not green"]
        else:
            render_commit = identity["render_commit"]
            health_commit = identity["health_commit"]
            readiness_commit = _text(readiness_deployment.get("commit")).lower()
            render_branch = identity["render_branch"]
            health_branch = identity["health_branch"]
            readiness_branch = _text(readiness_deployment.get("branch"))

            if (
                render_commit != health_commit
                or health_commit != readiness_commit
                or render_branch != health_branch
                or health_branch != readiness_branch
            ):
                state = "IDENTITY_CONFLICT"
                reasons = ["Render, health, and readiness deployment identity disagree"]
            elif identity["github_commit"] != render_commit:
                state = "PRODUCTION_LAG"
                reasons = ["deployed production commit differs from intended GitHub commit"]
            else:
                failed_guards = [
                    name
                    for name, value in normalized_guards.items()
                    if value not in _GREEN_GUARD_VALUES
                ]
                if failed_guards:
                    state = "GUARD_FAILED"
                    reasons = [f"required guard not green: {name}" for name in failed_guards]

    return {
        "version": VERSION,
        "observed_at_utc": _text(observed_at),
        "state": state,
        "certified": state == "GREEN",
        "identity": identity,
        "render_status": _text(render_map.get("status")).lower(),
        "health_status": _text(health_map.get("status")).lower(),
        "readiness": {
            "status": _text(readiness_map.get("status")).lower(),
            "checks": {
                key: readiness_checks.get(key)
                for key in (
                    "process_running",
                    "python_runtime",
                    "deployment_identity_available",
                    "runtime_branch_alignment",
                )
            },
            "deployment_aligned": readiness_deployment.get("aligned"),
        },
        "guards": normalized_guards,
        "reasons": reasons,
    }


def certification_exit_code(snapshot: Mapping[str, Any]) -> int:
    """Return zero only for an explicitly certified GREEN snapshot."""
    return 0 if snapshot.get("state") == "GREEN" and snapshot.get("certified") is True else 1
