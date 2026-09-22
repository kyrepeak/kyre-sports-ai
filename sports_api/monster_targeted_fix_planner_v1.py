"""Monster Runtime Lab V1 — deterministic smallest-safe-fix planning.

Consumes a sanitized Incident Autopacket and produces a *plan*, never an edit.
The planner is conservative: deployment drift blocks code changes; insufficient
evidence yields NEED_MORE_EVIDENCE; exact historical/replay evidence narrows the
recommended inspection surface and mandatory tests.
"""
from __future__ import annotations

from typing import Any, Mapping

from sports_api.monster_runtime_replay_v1 import CFB_PROTECTED_503_DETAIL

PLANNER_VERSION = "MONSTER_TARGETED_FIX_PLANNER_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
MAY_MODIFY_RUNTIME = False
AUTO_FIX = False
FUZZY_MATCHING = False

PERMANENT_FORBIDDEN_SCOPE = (
    "frozen projection/model math unless the incident proves model ownership",
    "fuzzy game/team/player identity matching",
    "synthetic official IDs",
    "sportsbook influence on frozen projection math",
    "unrelated sport pages or routers",
    "broad refactors before exact reproduction",
)


def _signals(packet: Mapping[str, Any]) -> Mapping[str, Any]:
    value = packet.get("signals")
    return value if isinstance(value, Mapping) else {}


def _replay_artifact(packet: Mapping[str, Any]) -> Mapping[str, Any] | None:
    replay = _signals(packet).get("replay")
    if not isinstance(replay, Mapping):
        return None
    artifact = replay.get("artifact")
    return artifact if isinstance(artifact, Mapping) else None


def _exact_protected_cfb_503(packet: Mapping[str, Any]) -> bool:
    artifact = _replay_artifact(packet)
    if not artifact or int(artifact.get("status_code") or 0) != 503:
        return False
    body = artifact.get("json_body")
    return isinstance(body, Mapping) and body.get("detail") == CFB_PROTECTED_503_DETAIL


def _memory_record(packet: Mapping[str, Any]) -> Mapping[str, Any] | None:
    memory = _signals(packet).get("failure_memory")
    if not isinstance(memory, Mapping) or not memory.get("found") or not memory.get("exact"):
        return None
    records = memory.get("records")
    if not isinstance(records, list) or not records or not isinstance(records[0], Mapping):
        return None
    return records[0]


def _dependency(packet: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = _signals(packet).get("dependency")
    return value if isinstance(value, Mapping) and value.get("status") == "OK" else None


def _recommended_scope(packet: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    inspect: list[str] = []
    edit_candidates: list[str] = []
    incident = packet.get("incident") if isinstance(packet.get("incident"), Mapping) else {}
    target = str(incident.get("target") or "").strip()
    if target:
        # A caller-supplied target is always useful for inspection, but it is not
        # an edit recommendation until deterministic evidence supports a fix.
        inspect.append(target)

    record = _memory_record(packet)
    if record:
        for path in record.get("files") or []:
            path = str(path)
            if path and path not in inspect:
                inspect.append(path)
            if path and path not in edit_candidates:
                edit_candidates.append(path)

    dependency = _dependency(packet)
    if dependency:
        for module in dependency.get("direct_dependencies") or []:
            module = str(module)
            if module and module not in inspect:
                inspect.append(module)

    if _exact_protected_cfb_503(packet):
        for path in (
            "devsystem/production_verify_v1.py",
            "tests/test_devsystem_production_verify_v1.py",
        ):
            if path not in inspect:
                inspect.append(path)
            if path not in edit_candidates:
                edit_candidates.append(path)

    return inspect[:20], edit_candidates[:8]


def build_fix_plan(packet: Mapping[str, Any]) -> dict[str, Any]:
    signals = _signals(packet)
    parity = signals.get("parity") if isinstance(signals.get("parity"), Mapping) else None
    performance = signals.get("performance") if isinstance(signals.get("performance"), Mapping) else None
    memory_record = _memory_record(packet)
    dependency = _dependency(packet)
    replay = _replay_artifact(packet)

    if parity and parity.get("status") == "DRIFT":
        return {
            "version": PLANNER_VERSION,
            "status": "BLOCKED_BY_PARITY",
            "root_cause_confidence": "HIGH",
            "root_cause": "Source and deployed runtime are not aligned; code diagnosis is not trustworthy yet.",
            "next_action": "Align/verify the intended deployment commit and branch, then rerun the same replay.",
            "inspect_first": [],
            "edit_candidates": [],
            "forbidden_scope": list(PERMANENT_FORBIDDEN_SCOPE),
            "required_tests": list(packet.get("recommended_tests") or []),
            "protections": _protections(),
        }

    evidence: list[str] = []
    root_cause = ""
    confidence = "LOW"
    next_action = ""

    if memory_record:
        root_cause = str(memory_record.get("root_cause") or "")
        confidence = "HIGH"
        evidence.append(f"exact_failure_memory:{memory_record.get('memory_id')}")
        first = (memory_record.get("check_first") or ["Inspect verified historical fix."])[0]
        next_action = str(first)

    if _exact_protected_cfb_503(packet):
        evidence.append("exact_replay:cfb_protected_503")
        if not root_cause:
            root_cause = (
                "The caller received the documented CFB incomplete-identity HTTP 503. "
                "Inspect whether generic HTTP error handling prevents the caller-specific body contract from being evaluated."
            )
            confidence = "HIGH"
            next_action = (
                "Keep the backend/model untouched; reproduce both the protected 503 and normal 200 through the verifier boundary, "
                "then change only verifier/request handling if the body is being preempted."
            )

    if performance and performance.get("grade") in {"SLOW", "CRITICAL"}:
        evidence.append(f"performance:{performance.get('bottleneck')}")
        if not root_cause:
            root_cause = (
                f"Measured hotspot is {performance.get('bottleneck')} "
                f"({performance.get('bottleneck_ms')} ms)."
            )
            confidence = "MEDIUM"
            next_action = str(performance.get("guidance") or "Instrument one level deeper.")

    if dependency:
        evidence.append(
            f"dependency:risk={dependency.get('risk')},blast_radius={dependency.get('blast_radius')}"
        )

    if replay:
        evidence.append(f"replay:http={replay.get('status_code')}")

    inspect_first, edit_candidates = _recommended_scope(packet)
    if not root_cause:
        status = "NEED_MORE_EVIDENCE"
        next_action = "Capture/replay the failing request and identify a deterministic failing boundary before editing code."
        # An unproven target remains inspection-only. Never suggest a code edit
        # merely because the caller happened to name a file.
        edit_candidates = []
    else:
        status = "PLAN_READY"

    required_tests = list(dict.fromkeys(str(item) for item in packet.get("recommended_tests") or []))
    if _exact_protected_cfb_503(packet):
        for test in (
            "tests/test_devsystem_production_verify_v1.py",
            "cfb-critical",
            "browser-qa",
            "devsystem-final-gate",
        ):
            if test not in required_tests:
                required_tests.append(test)

    proof = [
        "Reproduce the original failure deterministically before the edit.",
        "Prove the repaired case passes without weakening neighboring hard-fail cases.",
        "Run the dependency-selected regression lanes.",
        "Require devsystem-final-gate before merge.",
    ]
    if _exact_protected_cfb_503(packet):
        proof.insert(1, "Prove exact protected 503 is accepted and wrong 503 detail/other 5xx/malformed JSON still hard-fail.")

    return {
        "version": PLANNER_VERSION,
        "status": status,
        "root_cause_confidence": confidence,
        "root_cause": root_cause,
        "evidence": evidence,
        "next_action": next_action,
        "inspect_first": inspect_first,
        "edit_candidates": edit_candidates,
        "forbidden_scope": list(PERMANENT_FORBIDDEN_SCOPE),
        "required_tests": required_tests,
        "proof_before_merge": proof,
        "protections": _protections(),
    }


def _protections() -> dict[str, Any]:
    return {
        "projection_weight": PROJECTION_WEIGHT,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
        "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
        "may_modify_runtime": MAY_MODIFY_RUNTIME,
        "auto_fix": AUTO_FIX,
        "fuzzy_matching": FUZZY_MATCHING,
    }


__all__ = [
    "AUTO_FIX",
    "FUZZY_MATCHING",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RUNTIME",
    "MAY_MODIFY_SOURCE_DATA",
    "PERMANENT_FORBIDDEN_SCOPE",
    "PLANNER_VERSION",
    "PROJECTION_WEIGHT",
    "build_fix_plan",
]
