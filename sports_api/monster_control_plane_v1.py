"""Monster Control Plane V1.

Read-only orchestration across the additive Monster Final Form toolchain.

The control plane does not change sports data, models, projections, routing, or
runtime state. It combines existing diagnostic/certification signals into one
prioritized report so a failure can follow the same sequence every time:

observe -> profile -> remember -> map impact -> test edge cases -> certify.

GitHub's frozen ``devsystem-final-gate`` remains the authoritative merge veto.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Callable

from sports_api.monster_certification_v1 import run_certification
from sports_api.monster_dependency_map_v1 import build_dependency_map
from sports_api.monster_failure_memory_v1 import lookup_failure
from sports_api.monster_performance_profiler_v1 import SpanSample, diagnose
from sports_api.monster_test_matrix_v1 import run_totals_matrix
from sports_api.observability_v1 import diagnostics_snapshot
from sports_api.posthog_error_radar_v1 import radar_status

CONTROL_PLANE_VERSION = "MONSTER_CONTROL_PLANE_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
NETWORK_CALLS = False
FUZZY_MATCHING = False
AUTO_FIX = False
REPLACES_DEVSYSTEM_FINAL_GATE = False
AUTHORITATIVE_MERGE_GATE = "devsystem-final-gate"

CertificationFunc = Callable[..., dict[str, object]]


def _clean(value: Any, *, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def parse_span_spec(value: str) -> dict[str, Any]:
    """Parse ``stage=milliseconds[:category]`` for the CLI."""
    text = _clean(value)
    if "=" not in text:
        raise ValueError("span must use stage=milliseconds[:category]")
    name, raw = text.split("=", 1)
    name = _clean(name, limit=160)
    raw = _clean(raw, limit=200)
    if not name or not raw:
        raise ValueError("span name and duration are required")

    category = ""
    duration_text = raw
    if ":" in raw:
        duration_text, category = raw.rsplit(":", 1)
        duration_text = duration_text.strip()
        category = _clean(category, limit=80)

    try:
        duration_ms = float(duration_text)
    except (TypeError, ValueError) as exc:
        raise ValueError("span duration must be numeric milliseconds") from exc
    if duration_ms < 0:
        raise ValueError("span duration cannot be negative")

    payload: dict[str, Any] = {"stage": name, "total_ms": duration_ms, "calls": 1}
    if category:
        payload["category"] = category
    return payload


def _span_samples(rows: Sequence[Mapping[str, Any]] | None) -> list[SpanSample]:
    samples: list[SpanSample] = []
    for row in rows or ():
        name = _clean(row.get("stage") or row.get("name"), limit=160)
        if not name:
            continue
        try:
            duration_ms = float(row.get("total_ms", row.get("duration_ms", 0.0)) or 0.0)
            calls = int(row.get("calls", 1) or 1)
        except (TypeError, ValueError):
            continue
        if duration_ms < 0:
            continue
        samples.append(
            SpanSample(
                name=name,
                duration_ms=duration_ms,
                category=_clean(row.get("category"), limit=80),
                calls=max(1, calls),
            )
        )
    return samples


def _not_requested(component: str) -> dict[str, Any]:
    return {"component": component, "status": "NOT_REQUESTED"}


def _memory_report(
    *,
    fingerprint: str = "",
    signature: str = "",
    signature_id_value: str = "",
    family: str = "",
    memory_id: str = "",
) -> dict[str, Any]:
    if not any(
        _clean(value)
        for value in (fingerprint, signature, signature_id_value, family, memory_id)
    ):
        return _not_requested("failure_memory")
    return lookup_failure(
        fingerprint=fingerprint,
        signature=signature,
        signature_id_value=signature_id_value,
        family=family,
        memory_id=memory_id,
    ).as_dict()


def _performance_report(
    *,
    total_ms: float | None,
    spans: Sequence[Mapping[str, Any]] | None,
    surface: str,
    path: str,
) -> dict[str, Any]:
    samples = _span_samples(spans)
    if total_ms is None and not samples:
        return _not_requested("performance_profiler")

    total = float(total_ms) if total_ms is not None else sum(item.duration_ms for item in samples)
    if total < 0:
        return {
            "component": "performance_profiler",
            "status": "INVALID_INPUT",
            "reason": "total_ms cannot be negative",
        }
    return diagnose(
        total_ms=total,
        spans=samples,
        surface=_clean(surface, limit=160) or "monster_control_plane",
        path=_clean(path, limit=240) or "unknown",
    )


def _dependency_report(repo_root: str | Path, target: str) -> dict[str, Any]:
    if not _clean(target):
        return _not_requested("dependency_map")
    return build_dependency_map(repo_root).impact_report(target)


def _matrix_report(sport: str, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return _not_requested("test_matrix")
    return run_totals_matrix(_clean(sport, limit=80) or "CFB").as_dict()


def _certification_report(
    repo_root: str | Path,
    *,
    enabled: bool,
    certification_func: CertificationFunc,
) -> dict[str, Any]:
    if not enabled:
        return _not_requested("certification")
    return dict(certification_func(repo_root))


def _recommended_tests(
    *,
    sport: str,
    memory: Mapping[str, Any],
    dependency: Mapping[str, Any],
    certification: Mapping[str, Any],
) -> list[str]:
    tests: set[str] = {"devsystem-final-gate"}
    sport_key = _clean(sport, limit=40).lower().replace(" ", "")
    sport_lane = {
        "cfb": "cfb-critical",
        "collegefootball": "cfb-critical",
        "mlb": "mlb-critical",
        "wnba": "wnba-critical",
    }.get(sport_key)
    if sport_lane:
        tests.add(sport_lane)

    records = memory.get("records", ()) if isinstance(memory, Mapping) else ()
    for record in records or ():
        if not isinstance(record, Mapping):
            continue
        for test_name in record.get("tests", ()) or ():
            cleaned = _clean(test_name, limit=120)
            if cleaned:
                tests.add(cleaned)

    if dependency.get("impacted_entrypoints"):
        tests.add("browser-qa")
    if dependency.get("protected_reach"):
        tests.add("regression-shield")
    if certification.get("status") == "FAIL":
        tests.add("monster-one-command-certification")
    return sorted(tests)


def _actions(
    *,
    radar: Mapping[str, Any],
    performance: Mapping[str, Any],
    memory: Mapping[str, Any],
    dependency: Mapping[str, Any],
    matrix: Mapping[str, Any],
    certification: Mapping[str, Any],
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []

    def add(priority: str, source: str, action: str) -> None:
        item = {"priority": priority, "source": source, "action": action}
        if item not in actions:
            actions.append(item)

    if certification.get("status") == "FAIL":
        add("P0", "certification", "Do not merge; fix the failing certification check first.")

    if matrix.get("status") != "NOT_REQUESTED" and matrix.get("passed") is False:
        add("P0", "test_matrix", "Keep the affected page fail-closed until the failing edge-case contract is fixed.")

    if dependency.get("status") == "NOT_FOUND":
        add("P0", "dependency_map", "Verify the target path/module before making a code change.")
    elif dependency.get("status") == "OK":
        protected = dependency.get("protected_reach") or []
        risk = str(dependency.get("risk") or "")
        if protected:
            add(
                "P0",
                "dependency_map",
                "Protected/frozen code is in dependency reach; prefer an additive downstream fix and retain regression shields.",
            )
        if risk in {"HIGH", "CRITICAL"}:
            add(
                "P1",
                "dependency_map",
                f"Blast-radius risk is {risk}; run targeted sport, browser, and final-gate checks before trust.",
            )

    grade = str(performance.get("grade") or "")
    if grade in {"SLOW", "CRITICAL"}:
        add(
            "P1" if grade == "SLOW" else "P0",
            "performance_profiler",
            _clean(performance.get("guidance"), limit=500),
        )

    if memory.get("found") is True:
        records = memory.get("records") or []
        if records and isinstance(records[0], Mapping):
            first = records[0]
            title = _clean(first.get("title"), limit=220)
            check_first = first.get("check_first") or []
            next_check = _clean(check_first[0], limit=420) if check_first else "Inspect the verified historical record."
            add("P1", "failure_memory", f"Seen before — {title}. First check: {next_check}")

    if radar.get("configured") is False:
        add(
            "P2",
            "error_radar",
            "Runtime PostHog telemetry is not configured in this environment; local diagnostics still work.",
        )

    if not actions:
        add("P3", "control_plane", "No blocking signal found; continue with the smallest additive change.")

    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return sorted(actions, key=lambda item: (order.get(item["priority"], 9), item["source"], item["action"]))


def _overall_status(
    *,
    performance: Mapping[str, Any],
    memory: Mapping[str, Any],
    dependency: Mapping[str, Any],
    matrix: Mapping[str, Any],
    certification: Mapping[str, Any],
) -> str:
    if certification.get("status") == "FAIL":
        return "BLOCKED"
    if matrix.get("status") != "NOT_REQUESTED" and matrix.get("passed") is False:
        return "BLOCKED"
    if dependency.get("status") == "NOT_FOUND":
        return "BLOCKED"
    if performance.get("status") == "INVALID_INPUT":
        return "BLOCKED"

    if str(performance.get("grade") or "") in {"SLOW", "CRITICAL"}:
        return "INVESTIGATE"
    if memory.get("found") is True:
        return "INVESTIGATE"
    if dependency.get("status") == "OK" and (
        dependency.get("protected_reach")
        or str(dependency.get("risk") or "") in {"HIGH", "CRITICAL"}
    ):
        return "INVESTIGATE"
    return "READY"


def protection_snapshot() -> dict[str, Any]:
    return {
        "projection_weight": PROJECTION_WEIGHT,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
        "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
        "may_modify_runtime": MAY_MODIFY_RUNTIME,
        "network_calls": NETWORK_CALLS,
        "fuzzy_matching": FUZZY_MATCHING,
        "auto_fix": AUTO_FIX,
        "replaces_devsystem_final_gate": REPLACES_DEVSYSTEM_FINAL_GATE,
        "authoritative_merge_gate": AUTHORITATIVE_MERGE_GATE,
    }


def build_control_report(
    repo_root: str | Path = ".",
    *,
    target: str = "",
    fingerprint: str = "",
    signature: str = "",
    signature_id_value: str = "",
    family: str = "",
    memory_id: str = "",
    sport: str = "CFB",
    total_ms: float | None = None,
    spans: Sequence[Mapping[str, Any]] | None = None,
    surface: str = "monster_control_plane",
    path: str = "unknown",
    include_matrix: bool = True,
    certify: bool = False,
    certification_func: CertificationFunc = run_certification,
) -> dict[str, Any]:
    """Build one read-only, deterministic Final Form diagnosis packet."""
    root = Path(repo_root).resolve()

    observability = diagnostics_snapshot()
    radar = radar_status()
    performance = _performance_report(total_ms=total_ms, spans=spans, surface=surface, path=path)
    memory = _memory_report(
        fingerprint=fingerprint,
        signature=signature,
        signature_id_value=signature_id_value,
        family=family,
        memory_id=memory_id,
    )
    dependency = _dependency_report(root, target)
    matrix = _matrix_report(sport, include_matrix)
    certification = _certification_report(root, enabled=certify, certification_func=certification_func)

    status = _overall_status(
        performance=performance,
        memory=memory,
        dependency=dependency,
        matrix=matrix,
        certification=certification,
    )
    return {
        "control_plane_version": CONTROL_PLANE_VERSION,
        "status": status,
        "incident": {
            "sport": _clean(sport, limit=80) or "CFB",
            "target": _clean(target, limit=300),
            "surface": _clean(surface, limit=160) or "monster_control_plane",
            "path": _clean(path, limit=240) or "unknown",
            "has_error_identifier": bool(
                any(_clean(value) for value in (fingerprint, signature, signature_id_value, family, memory_id))
            ),
            "has_performance_sample": total_ms is not None or bool(spans),
        },
        "signals": {
            "observability": observability,
            "error_radar": radar,
            "performance": performance,
            "failure_memory": memory,
            "dependency": dependency,
            "test_matrix": matrix,
            "certification": certification,
        },
        "recommended_tests": _recommended_tests(
            sport=sport,
            memory=memory,
            dependency=dependency,
            certification=certification,
        ),
        "next_actions": _actions(
            radar=radar,
            performance=performance,
            memory=memory,
            dependency=dependency,
            matrix=matrix,
            certification=certification,
        ),
        "protections": protection_snapshot(),
    }


def _human_report(report: Mapping[str, Any]) -> str:
    signals = report["signals"]
    perf = signals["performance"]
    memory = signals["failure_memory"]
    dependency = signals["dependency"]
    matrix = signals["test_matrix"]
    certification = signals["certification"]

    lines = [
        f"👹 {CONTROL_PLANE_VERSION} — {report['status']}",
        f"Target: {report['incident']['target'] or 'not supplied'}",
        f"Error Radar: {'configured' if signals['error_radar'].get('configured') else 'not configured here'}",
    ]
    if perf.get("grade"):
        lines.append(
            f"Performance: {perf['grade']} • {perf.get('total_ms', 0)} ms • bottleneck {perf.get('bottleneck', 'unknown')}"
        )
    else:
        lines.append("Performance: not requested")

    if memory.get("found") is True:
        first = (memory.get("records") or [{}])[0]
        lines.append(f"Failure Memory: SEEN BEFORE • {first.get('title', 'known incident')}")
    elif memory.get("status") == "NOT_REQUESTED":
        lines.append("Failure Memory: not requested")
    else:
        lines.append(f"Failure Memory: {memory.get('status', 'unknown')}")

    if dependency.get("status") == "OK":
        lines.append(
            f"Dependency Map: {dependency.get('risk')} • blast radius {dependency.get('blast_radius')} • "
            f"entrypoints {', '.join(dependency.get('impacted_entrypoints') or []) or 'none'}"
        )
    else:
        lines.append(f"Dependency Map: {dependency.get('status', 'not requested')}")

    if matrix.get("status") == "NOT_REQUESTED":
        lines.append("Test Matrix: not requested")
    else:
        lines.append(
            f"Test Matrix: {'PASS' if matrix.get('passed') else 'FAIL'} • "
            f"{matrix.get('passed_count', 0)}/{matrix.get('scenario_count', 0)}"
        )

    if certification.get("status") == "NOT_REQUESTED":
        lines.append("Certification: not requested")
    else:
        lines.append(
            f"Certification: {certification.get('status')} • "
            f"{certification.get('passed_check_count', 0)}/{certification.get('required_check_count', 0)}"
        )

    lines.append("Recommended tests: " + ", ".join(report["recommended_tests"]))
    lines.append("Next actions:")
    for item in report["next_actions"]:
        lines.append(f"  {item['priority']} [{item['source']}] {item['action']}")
    lines.append("Frozen authority: devsystem-final-gate remains the merge veto.")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monster Control Plane V1")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--target", default="", help="Repository-relative Python path or module for blast-radius analysis.")
    identifiers = parser.add_mutually_exclusive_group()
    identifiers.add_argument("--fingerprint", default="")
    identifiers.add_argument("--signature", default="")
    identifiers.add_argument("--signature-id", default="")
    identifiers.add_argument("--family", default="")
    identifiers.add_argument("--memory-id", default="")
    parser.add_argument("--sport", default="CFB")
    parser.add_argument("--surface", default="monster_control_plane")
    parser.add_argument("--path", default="unknown")
    parser.add_argument("--total-ms", type=float, default=None)
    parser.add_argument(
        "--span",
        action="append",
        default=[],
        help="Repeatable stage timing: stage=milliseconds[:category]",
    )
    parser.add_argument("--no-matrix", action="store_true")
    parser.add_argument("--certify", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        spans = [parse_span_spec(value) for value in args.span]
    except ValueError as exc:
        parser.error(str(exc))

    report = build_control_report(
        args.repo_root,
        target=args.target,
        fingerprint=args.fingerprint,
        signature=args.signature,
        signature_id_value=args.signature_id,
        family=args.family,
        memory_id=args.memory_id,
        sport=args.sport,
        total_ms=args.total_ms,
        spans=spans,
        surface=args.surface,
        path=args.path,
        include_matrix=not args.no_matrix,
        certify=args.certify,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(_human_report(report))
    return 1 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "AUTHORITATIVE_MERGE_GATE",
    "AUTO_FIX",
    "CONTROL_PLANE_VERSION",
    "FUZZY_MATCHING",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RUNTIME",
    "MAY_MODIFY_SOURCE_DATA",
    "NETWORK_CALLS",
    "PROJECTION_WEIGHT",
    "REPLACES_DEVSYSTEM_FINAL_GATE",
    "build_control_report",
    "main",
    "parse_span_spec",
    "protection_snapshot",
]
