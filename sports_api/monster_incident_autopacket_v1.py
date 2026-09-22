"""Monster Runtime Lab V1 — deterministic incident autopacket.

Combines the existing Monster diagnostic layers into one reviewable case file.
The packet consumes local/replayed/sanitized evidence supplied by the caller; it
does not fetch GitHub, Render, PostHog, or sportsbook data on its own.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sports_api.monster_dependency_map_v1 import build_dependency_map
from sports_api.monster_failure_memory_v1 import lookup_failure
from sports_api.monster_performance_profiler_v1 import SpanSample, diagnose
from sports_api.monster_runtime_capture_v1 import ReplayArtifact
from sports_api.monster_runtime_trace_v1 import (
    ParityIdentity,
    TraceHop,
    compare_production_parity,
    correlate_trace,
)
from sports_api.monster_test_matrix_v1 import run_totals_matrix
from sports_api.observability_v1 import diagnostics_snapshot
from sports_api.posthog_error_radar_v1 import radar_status

AUTOPACKET_VERSION = "MONSTER_INCIDENT_AUTOPACKET_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False
AUTO_FIX = False
MAX_TEXT = 1500


def _clip(value: Any, limit: int = MAX_TEXT) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text[:limit]


def _safe_texts(values: Iterable[Any] | None, *, limit: int = 20) -> list[str]:
    return [_clip(item) for item in list(values or ())[:limit] if _clip(item)]


@dataclass(frozen=True, slots=True)
class IncidentInput:
    title: str
    symptom: str
    target: str = ""
    request_id: str = ""
    error_fingerprint: str = ""
    failure_signature: str = ""
    sport: str = ""
    route: str = ""
    surface: str = "unknown"
    total_ms: float | None = None
    spans: tuple[SpanSample, ...] = field(default_factory=tuple)
    trace_hops: tuple[TraceHop, ...] = field(default_factory=tuple)
    parity_identity: ParityIdentity | None = None
    replay_artifact: ReplayArtifact | None = None
    recent_commits: tuple[str, ...] = field(default_factory=tuple)
    render_log_lines: tuple[str, ...] = field(default_factory=tuple)
    posthog_context: Mapping[str, Any] = field(default_factory=dict)



def recommended_tests(
    *,
    sport: str,
    dependency: Mapping[str, Any] | None,
    memory: Mapping[str, Any] | None,
) -> list[str]:
    tests: set[str] = set()
    normalized_sport = str(sport or "").strip().lower()
    if normalized_sport in {"cfb", "college football", "college_football"}:
        tests.add("cfb-critical")
    elif normalized_sport == "mlb":
        tests.add("mlb-critical")
    elif normalized_sport == "wnba":
        tests.add("wnba-critical")
    elif normalized_sport == "nfl":
        tests.add("nfl-targeted")

    if dependency and dependency.get("status") == "OK":
        if dependency.get("impacted_entrypoints"):
            tests.update({"core-smoke", "browser-qa"})
        if dependency.get("protected_reach"):
            tests.add("regression-shield")
        if str(dependency.get("risk")) in {"HIGH", "CRITICAL"}:
            tests.add("permanent-contract")

    if memory and memory.get("found"):
        for record in memory.get("records") or []:
            for test in record.get("tests") or []:
                tests.add(str(test))

    # The authoritative merge veto stays required for any code incident.
    tests.add("devsystem-final-gate")
    return sorted(tests)


def _priority(
    *,
    performance: Mapping[str, Any] | None,
    parity: Mapping[str, Any] | None,
    dependency: Mapping[str, Any] | None,
    memory: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if parity and parity.get("status") == "DRIFT":
        actions.append({"priority": "P0", "action": "Resolve production/source parity drift before changing logic."})
    if memory and memory.get("found") and memory.get("exact"):
        record = (memory.get("records") or [{}])[0]
        first = (record.get("check_first") or ["Inspect the verified historical record."])[0]
        actions.append({"priority": "P1", "action": f"Exact Failure Memory hit: {first}"})
    if performance and performance.get("grade") in {"SLOW", "CRITICAL"}:
        actions.append(
            {
                "priority": "P1",
                "action": (
                    f"Inspect performance bottleneck {performance.get('bottleneck')} "
                    f"({performance.get('bottleneck_ms')} ms) before broad refactoring."
                ),
            }
        )
    if dependency and dependency.get("status") == "OK":
        actions.append(
            {
                "priority": "P2",
                "action": (
                    f"Constrain edits to the mapped target; blast radius={dependency.get('blast_radius')} "
                    f"risk={dependency.get('risk')}."
                ),
            }
        )
    if not actions:
        actions.append({"priority": "P2", "action": "Reproduce the incident first; evidence is not sufficient for a code change."})
    return actions


def build_incident_packet(
    incident: IncidentInput,
    *,
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()

    dependency: dict[str, Any] | None = None
    if incident.target:
        dependency = build_dependency_map(root).impact_report(incident.target)

    memory: dict[str, Any] | None = None
    if incident.error_fingerprint or incident.failure_signature:
        memory = lookup_failure(
            fingerprint=incident.error_fingerprint,
            signature=incident.failure_signature,
        ).as_dict()

    performance: dict[str, Any] | None = None
    if incident.total_ms is not None:
        performance = diagnose(
            total_ms=float(incident.total_ms),
            spans=list(incident.spans),
            surface=incident.surface,
            path=incident.route or incident.target or "unknown",
        )

    trace: dict[str, Any] | None = None
    if incident.request_id and incident.trace_hops:
        trace = correlate_trace(
            incident.trace_hops,
            request_id=incident.request_id,
        ).as_dict()

    parity: dict[str, Any] | None = None
    if incident.parity_identity is not None:
        parity = compare_production_parity(incident.parity_identity).as_dict()

    matrix: dict[str, Any] | None = None
    if incident.sport:
        try:
            matrix = run_totals_matrix(incident.sport).as_dict()
        except (KeyError, ValueError):
            matrix = {
                "status": "UNAVAILABLE_FOR_SPORT",
                "sport": incident.sport,
            }

    replay: dict[str, Any] | None = None
    if incident.replay_artifact is not None:
        replay = {
            "fingerprint": incident.replay_artifact.fingerprint,
            "artifact": incident.replay_artifact.as_dict(),
        }

    tests = recommended_tests(
        sport=incident.sport,
        dependency=dependency,
        memory=memory,
    )

    return {
        "version": AUTOPACKET_VERSION,
        "incident": {
            "title": _clip(incident.title),
            "symptom": _clip(incident.symptom),
            "target": incident.target,
            "route": incident.route,
            "surface": incident.surface,
            "sport": incident.sport,
            "request_id": incident.request_id,
            "error_fingerprint": incident.error_fingerprint,
        },
        "signals": {
            "observability": diagnostics_snapshot(),
            "error_radar": radar_status(),
            "replay": replay,
            "trace": trace,
            "parity": parity,
            "performance": performance,
            "failure_memory": memory,
            "dependency": dependency,
            "test_matrix": matrix,
        },
        "evidence": {
            "recent_commits": _safe_texts(incident.recent_commits),
            "render_log_lines": _safe_texts(incident.render_log_lines),
            "posthog_context": {
                str(key): _clip(value) for key, value in dict(incident.posthog_context).items()
            },
        },
        "priority_actions": _priority(
            performance=performance,
            parity=parity,
            dependency=dependency,
            memory=memory,
        ),
        "recommended_tests": tests,
        "protections": {
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
            "may_modify_runtime": MAY_MODIFY_RUNTIME,
            "network_calls": NETWORK_CALLS,
            "auto_fix": AUTO_FIX,
        },
    }


__all__ = [
    "AUTOPACKET_VERSION",
    "AUTO_FIX",
    "IncidentInput",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RUNTIME",
    "MAY_MODIFY_SOURCE_DATA",
    "NETWORK_CALLS",
    "PROJECTION_WEIGHT",
    "build_incident_packet",
    "recommended_tests",
]
