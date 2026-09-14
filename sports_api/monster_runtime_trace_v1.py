"""Monster Runtime Lab V1 — request correlation and production parity.

Read-only developer tooling. It correlates sanitized request hops by request ID
and compares source/deployment identities supplied by existing observability or
CI. It does not contact GitHub, Render, PostHog, or any sportsbook itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

TRACE_VERSION = "MONSTER_RUNTIME_TRACE_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False


@dataclass(frozen=True, slots=True)
class TraceHop:
    request_id: str
    surface: str
    operation: str
    status: str = "ok"
    duration_ms: float | None = None
    commit: str = "unknown"
    branch: str = "unknown"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "surface": self.surface,
            "operation": self.operation,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "commit": self.commit,
            "branch": self.branch,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class TraceReport:
    request_id: str
    hops: tuple[TraceHop, ...]
    complete: bool
    missing_surfaces: tuple[str, ...]
    commit_consistent: bool
    branch_consistent: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": TRACE_VERSION,
            "request_id": self.request_id,
            "hop_count": len(self.hops),
            "complete": self.complete,
            "missing_surfaces": list(self.missing_surfaces),
            "commit_consistent": self.commit_consistent,
            "branch_consistent": self.branch_consistent,
            "hops": [hop.as_dict() for hop in self.hops],
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
            "may_modify_runtime": MAY_MODIFY_RUNTIME,
            "network_calls": NETWORK_CALLS,
        }


DEFAULT_EXPECTED_SURFACES = (
    "streamlit",
    "api",
    "verifier",
    "upstream",
)


def correlate_trace(
    hops: Iterable[TraceHop],
    *,
    request_id: str,
    expected_surfaces: Iterable[str] = DEFAULT_EXPECTED_SURFACES,
) -> TraceReport:
    selected = tuple(hop for hop in hops if hop.request_id == request_id)
    present = {hop.surface for hop in selected}
    expected = tuple(dict.fromkeys(str(item) for item in expected_surfaces))
    missing = tuple(item for item in expected if item not in present)

    commits = {hop.commit for hop in selected if hop.commit and hop.commit != "unknown"}
    branches = {hop.branch for hop in selected if hop.branch and hop.branch != "unknown"}
    return TraceReport(
        request_id=request_id,
        hops=selected,
        complete=not missing,
        missing_surfaces=missing,
        commit_consistent=len(commits) <= 1,
        branch_consistent=len(branches) <= 1,
    )


@dataclass(frozen=True, slots=True)
class ParityIdentity:
    source_branch: str
    source_commit: str
    runtime_branch: str
    runtime_commit: str
    expected_runtime_branch: str = ""
    service: str = ""
    service_id: str = ""
    schema_versions: Mapping[str, str] = field(default_factory=dict)
    dependency_versions: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParityReport:
    status: str
    issues: tuple[str, ...]
    checks: Mapping[str, bool]
    identity: ParityIdentity

    @property
    def aligned(self) -> bool:
        return self.status == "ALIGNED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": TRACE_VERSION,
            "status": self.status,
            "aligned": self.aligned,
            "issues": list(self.issues),
            "checks": dict(self.checks),
            "identity": {
                "source_branch": self.identity.source_branch,
                "source_commit": self.identity.source_commit,
                "runtime_branch": self.identity.runtime_branch,
                "runtime_commit": self.identity.runtime_commit,
                "expected_runtime_branch": self.identity.expected_runtime_branch,
                "service": self.identity.service,
                "service_id": self.identity.service_id,
                "schema_versions": dict(self.identity.schema_versions),
                "dependency_versions": dict(self.identity.dependency_versions),
            },
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
            "may_modify_runtime": MAY_MODIFY_RUNTIME,
            "network_calls": NETWORK_CALLS,
        }


def compare_production_parity(identity: ParityIdentity) -> ParityReport:
    issues: list[str] = []
    expected_branch = identity.expected_runtime_branch or identity.source_branch
    checks = {
        "source_commit_known": bool(identity.source_commit and identity.source_commit != "unknown"),
        "runtime_commit_known": bool(identity.runtime_commit and identity.runtime_commit != "unknown"),
        "runtime_branch_expected": identity.runtime_branch == expected_branch,
        "source_runtime_commit_equal": identity.source_commit == identity.runtime_commit,
    }
    if not checks["source_commit_known"]:
        issues.append("source commit identity unavailable")
    if not checks["runtime_commit_known"]:
        issues.append("runtime commit identity unavailable")
    if not checks["runtime_branch_expected"]:
        issues.append(
            f"runtime branch drift: expected={expected_branch!r} actual={identity.runtime_branch!r}"
        )
    if not checks["source_runtime_commit_equal"]:
        issues.append(
            "runtime commit differs from source commit: "
            f"source={identity.source_commit!r} runtime={identity.runtime_commit!r}"
        )

    # Empty version maps mean 'not supplied', not automatic failure. When both
    # sides are supplied by a caller, use `version_drift` below for exact checks.
    status = "ALIGNED" if not issues else "DRIFT"
    return ParityReport(status=status, issues=tuple(issues), checks=checks, identity=identity)


def version_drift(
    expected: Mapping[str, str],
    actual: Mapping[str, str],
) -> dict[str, dict[str, str]]:
    drift: dict[str, dict[str, str]] = {}
    for key in sorted(set(expected) | set(actual)):
        exp = str(expected.get(key, "<missing>"))
        got = str(actual.get(key, "<missing>"))
        if exp != got:
            drift[key] = {"expected": exp, "actual": got}
    return drift


def identity_from_observability(
    *,
    source_branch: str,
    source_commit: str,
    runtime: Mapping[str, Any],
    expected_runtime_branch: str = "",
    schema_versions: Mapping[str, str] | None = None,
    dependency_versions: Mapping[str, str] | None = None,
) -> ParityIdentity:
    return ParityIdentity(
        source_branch=str(source_branch),
        source_commit=str(source_commit),
        runtime_branch=str(runtime.get("deploy_branch") or runtime.get("branch") or "unknown"),
        runtime_commit=str(runtime.get("deploy_commit") or runtime.get("commit") or "unknown"),
        expected_runtime_branch=str(
            expected_runtime_branch
            or runtime.get("expected_runtime_branch")
            or source_branch
        ),
        service=str(runtime.get("service") or ""),
        service_id=str(runtime.get("service_id") or ""),
        schema_versions=dict(schema_versions or {}),
        dependency_versions=dict(dependency_versions or {}),
    )


__all__ = [
    "DEFAULT_EXPECTED_SURFACES",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RUNTIME",
    "MAY_MODIFY_SOURCE_DATA",
    "NETWORK_CALLS",
    "PROJECTION_WEIGHT",
    "ParityIdentity",
    "ParityReport",
    "TRACE_VERSION",
    "TraceHop",
    "TraceReport",
    "compare_production_parity",
    "correlate_trace",
    "identity_from_observability",
    "version_drift",
]
