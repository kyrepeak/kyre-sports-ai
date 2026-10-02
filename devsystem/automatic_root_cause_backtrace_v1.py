"""MONSTER V7 Step 2 — Automatic Root-Cause Backtrace V1.

Consumes the frozen MONSTER V7 Step-1 causal state lineage graph and turns a
stalled or bad downstream state into a deterministic root-cause attribution.

The engine does not blame the event closest to the symptom. Given a proven-good
state digest (or an explicit last-known-good WRITE), it walks the target field's
WRITE generations backward from the failing target, reconstructs the Step-1
causal path, then identifies the *first* WRITE after the known-good anchor that
diverged from the expected state.

If the lineage does not contain enough evidence for causal attribution, the
engine fails closed with NO_CAUSAL_DIVERGENCE_FOUND. It never guesses, never
fetches network data, and never grants mutation authority.
"""
from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.causal_state_lineage_graph_v1 import (
    VERSION as LINEAGE_VERSION,
    CausalStateLineageFailure,
    backtrace as lineage_backtrace,
    validate_graph,
)

VERSION = "MONSTER_V7_AUTOMATIC_ROOT_CAUSE_BACKTRACE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
STEP1_REQUIRED_VERSION = "MONSTER_V7_CAUSAL_STATE_LINEAGE_GRAPH_V1"

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_ALLOWED_TRIGGERS = {
    "PROGRESS_STALL",
    "BAD_FINAL_STATE",
    "STATE_REGRESSION",
    "DOWNSTREAM_MISMATCH",
}


class AutomaticRootCauseBacktraceFailure(RuntimeError):
    pass


def _text(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise AutomaticRootCauseBacktraceFailure(f"{field} is required")
    return out


def _digest(value: Any, field: str) -> str:
    out = str(value or "").strip().lower()
    if not _DIGEST.fullmatch(out):
        raise AutomaticRootCauseBacktraceFailure(
            f"{field} must be sha256:<64 lowercase hex>"
        )
    return out


def _normalize_incident(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AutomaticRootCauseBacktraceFailure("incident must be an object")
    out = deepcopy(dict(value))
    out["incident_id"] = _text(out.get("incident_id"), "incident_id")
    out["field"] = _text(out.get("field"), "field")
    trigger = _text(out.get("trigger"), "trigger").upper()
    if trigger not in _ALLOWED_TRIGGERS:
        raise AutomaticRootCauseBacktraceFailure(
            f"unsupported incident trigger: {trigger}"
        )
    out["trigger"] = trigger

    target = str(out.get("target_event_id") or "").strip()
    out["target_event_id"] = target

    expected = str(out.get("expected_value_digest") or "").strip().lower()
    if expected:
        expected = _digest(expected, "expected_value_digest")
    out["expected_value_digest"] = expected

    anchor = str(out.get("last_known_good_write_id") or "").strip()
    out["last_known_good_write_id"] = anchor

    try:
        progress = float(out.get("observed_progress_percent", 0.0))
    except (TypeError, ValueError) as exc:
        raise AutomaticRootCauseBacktraceFailure(
            "observed_progress_percent must be numeric"
        ) from exc
    if progress < 0.0 or progress > 100.0:
        raise AutomaticRootCauseBacktraceFailure(
            "observed_progress_percent must be between 0 and 100"
        )
    out["observed_progress_percent"] = progress

    if not expected and not anchor:
        # This is intentionally accepted. The engine will return a fail-closed
        # no-attribution result instead of guessing.
        out["evidence_sufficient_for_value_attribution"] = False
    else:
        out["evidence_sufficient_for_value_attribution"] = True
    return out


def _event_index(graph: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(event["event_id"]): deepcopy(dict(event))
        for event in graph["events"]
    }


def _writes_for_field(
    graph: Mapping[str, Any],
    field: str,
) -> list[dict[str, Any]]:
    return [
        deepcopy(dict(event))
        for event in graph["events"]
        if event["kind"] == "WRITE" and event["field"] == field
    ]


def _resolve_target(
    graph: Mapping[str, Any],
    *,
    field: str,
    target_event_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    index = _event_index(graph)
    if target_event_id:
        target = index.get(target_event_id)
        if target is None:
            raise AutomaticRootCauseBacktraceFailure(
                f"unknown target_event_id: {target_event_id}"
            )
        if target["field"] != field:
            raise AutomaticRootCauseBacktraceFailure(
                "target_event_id field does not match incident field"
            )
    else:
        field_events = [
            deepcopy(dict(event))
            for event in graph["events"]
            if event["field"] == field
        ]
        if not field_events:
            raise AutomaticRootCauseBacktraceFailure(
                f"incident field has no lineage events: {field}"
            )
        target = field_events[-1]

    if target["kind"] == "WRITE":
        source_write = target
    else:
        source_id = str(target["source_write_event_id"])
        source_write = index.get(source_id)
        if source_write is None or source_write["kind"] != "WRITE":
            # A validated Step-1 graph should make this impossible, but keep
            # this layer fail closed in case its dependency contract changes.
            raise AutomaticRootCauseBacktraceFailure(
                "target READ source WRITE unavailable"
            )
    return target, source_write


def _no_attribution(
    *,
    graph: Mapping[str, Any],
    incident: Mapping[str, Any],
    target: Mapping[str, Any],
    target_write: Mapping[str, Any],
    writers_examined: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    trace = lineage_backtrace(graph, target["event_id"])
    return {
        "version": VERSION,
        "lineage_version": LINEAGE_VERSION,
        "incident_id": incident["incident_id"],
        "trigger": incident["trigger"],
        "field": incident["field"],
        "decision": "NO_CAUSAL_DIVERGENCE_FOUND",
        "root_cause_found": False,
        "reason": reason,
        "target_event_id": target["event_id"],
        "target_step_id": target["step_id"],
        "target_write_event_id": target_write["event_id"],
        "target_write_step_id": target_write["step_id"],
        "writers_examined": writers_examined,
        "writer_count_examined": len(writers_examined),
        "causal_path": trace["causal_path"],
        "affected_consumers": [],
        "next_legal_action": "INSPECT_NON_LINEAGE_BLOCKER",
        "mutation_authority": False,
    }


def automatic_backtrace(
    graph: Mapping[str, Any],
    incident: Mapping[str, Any],
) -> dict[str, Any]:
    """Find the first state writer that diverged after proven-good evidence."""
    try:
        verified = validate_graph(graph)
    except CausalStateLineageFailure as exc:
        raise AutomaticRootCauseBacktraceFailure(
            f"Step-1 lineage validation failed: {exc}"
        ) from exc

    if verified.get("version") != STEP1_REQUIRED_VERSION:
        raise AutomaticRootCauseBacktraceFailure(
            "Step-1 lineage version mismatch"
        )

    item = _normalize_incident(incident)
    field = item["field"]
    writes = _writes_for_field(verified, field)
    if not writes:
        raise AutomaticRootCauseBacktraceFailure(
            f"incident field has no WRITE lineage: {field}"
        )

    target, target_write = _resolve_target(
        verified,
        field=field,
        target_event_id=item["target_event_id"],
    )
    target_sequence = int(target_write["sequence"])
    eligible_writes = [
        row for row in writes if int(row["sequence"]) <= target_sequence
    ]
    if not eligible_writes:
        raise AutomaticRootCauseBacktraceFailure(
            "target has no eligible WRITE history"
        )

    index = _event_index(verified)
    anchor: dict[str, Any] | None = None
    anchor_id = item["last_known_good_write_id"]
    expected_digest = item["expected_value_digest"]

    if anchor_id:
        candidate = index.get(anchor_id)
        if candidate is None or candidate["kind"] != "WRITE":
            raise AutomaticRootCauseBacktraceFailure(
                "last_known_good_write_id must reference a WRITE"
            )
        if candidate["field"] != field:
            raise AutomaticRootCauseBacktraceFailure(
                "last-known-good WRITE field mismatch"
            )
        if int(candidate["sequence"]) > target_sequence:
            raise AutomaticRootCauseBacktraceFailure(
                "last-known-good WRITE occurs after target"
            )
        anchor = candidate
        if expected_digest and candidate["value_digest"] != expected_digest:
            raise AutomaticRootCauseBacktraceFailure(
                "last-known-good WRITE does not match expected_value_digest"
            )
        if not expected_digest:
            expected_digest = str(candidate["value_digest"])

    if not anchor and expected_digest:
        matching = [
            row
            for row in eligible_writes
            if row["value_digest"] == expected_digest
        ]
        if matching:
            # The closest proven-good value before the symptom minimizes
            # irrelevant history while still locating the first regression.
            anchor = matching[-1]

    reverse_writers = [
        {
            "event_id": row["event_id"],
            "step_id": row["step_id"],
            "generation": row["generation"],
            "sequence": row["sequence"],
            "value_digest": row["value_digest"],
        }
        for row in reversed(eligible_writes)
    ]

    if not expected_digest or anchor is None:
        return _no_attribution(
            graph=verified,
            incident=item,
            target=target,
            target_write=target_write,
            writers_examined=reverse_writers,
            reason="INSUFFICIENT_PROVEN_GOOD_VALUE_EVIDENCE",
        )

    after_anchor = [
        row
        for row in eligible_writes
        if int(row["sequence"]) > int(anchor["sequence"])
    ]
    divergent = [
        row for row in after_anchor
        if row["value_digest"] != expected_digest
    ]
    if not divergent:
        return _no_attribution(
            graph=verified,
            incident=item,
            target=target,
            target_write=target_write,
            writers_examined=reverse_writers,
            reason="TARGET_PATH_NEVER_DIVERGED_FROM_EXPECTED_VALUE",
        )

    # Root cause is the first bad writer after the closest proven-good anchor,
    # not the last bad writer closest to the symptom.
    root = divergent[0]

    # Verify that every later WRITE up to the target is reachable through the
    # per-field parent chain. Step 1 enforces this, but this explicit check
    # makes the attribution contract self-describing.
    parent_chain: list[str] = []
    cursor = target_write
    seen: set[str] = set()
    while True:
        cid = str(cursor["event_id"])
        if cid in seen:
            raise AutomaticRootCauseBacktraceFailure(
                "writer parent chain cycle detected"
            )
        seen.add(cid)
        parent_chain.append(cid)
        if cid == anchor["event_id"]:
            break
        parent_id = str(cursor.get("parent_write_event_id") or "")
        if not parent_id:
            return _no_attribution(
                graph=verified,
                incident=item,
                target=target,
                target_write=target_write,
                writers_examined=reverse_writers,
                reason="TARGET_NOT_CAUSALLY_CONNECTED_TO_PROVEN_GOOD_ANCHOR",
            )
        parent = index.get(parent_id)
        if parent is None or parent["kind"] != "WRITE" or parent["field"] != field:
            raise AutomaticRootCauseBacktraceFailure(
                "writer parent chain is invalid"
            )
        cursor = parent

    if root["event_id"] not in parent_chain:
        return _no_attribution(
            graph=verified,
            incident=item,
            target=target,
            target_write=target_write,
            writers_examined=reverse_writers,
            reason="DIVERGENT_WRITE_NOT_ON_TARGET_PARENT_CHAIN",
        )

    trace = lineage_backtrace(verified, target["event_id"])

    affected_consumers: list[dict[str, Any]] = []
    for event in verified["events"]:
        if event["kind"] != "READ" or event["field"] != field:
            continue
        source = index[event["source_write_event_id"]]
        if (
            int(event["sequence"]) >= int(root["sequence"])
            and int(event["sequence"]) <= int(target["sequence"])
            and source["value_digest"] != expected_digest
        ):
            affected_consumers.append(
                {
                    "event_id": event["event_id"],
                    "step_id": event["step_id"],
                    "source_write_event_id": source["event_id"],
                    "source_write_step_id": source["step_id"],
                    "source_generation": source["generation"],
                }
            )

    return {
        "version": VERSION,
        "lineage_version": LINEAGE_VERSION,
        "incident_id": item["incident_id"],
        "trigger": item["trigger"],
        "field": field,
        "decision": "ROOT_CAUSE_IDENTIFIED",
        "root_cause_found": True,
        "root_cause_class": "FIRST_VALUE_DIVERGENCE_AFTER_PROVEN_GOOD",
        "root_cause_event_id": root["event_id"],
        "root_cause_step_id": root["step_id"],
        "root_cause_generation": root["generation"],
        "root_cause_sequence": root["sequence"],
        "root_cause_value_digest": root["value_digest"],
        "proven_good_event_id": anchor["event_id"],
        "proven_good_step_id": anchor["step_id"],
        "proven_good_generation": anchor["generation"],
        "expected_value_digest": expected_digest,
        "target_event_id": target["event_id"],
        "target_step_id": target["step_id"],
        "target_write_event_id": target_write["event_id"],
        "target_write_step_id": target_write["step_id"],
        "writers_examined": reverse_writers,
        "writer_count_examined": len(reverse_writers),
        "writer_parent_chain_from_target": parent_chain,
        "causal_path": trace["causal_path"],
        "affected_consumers": affected_consumers,
        "affected_consumer_steps": [
            row["step_id"] for row in affected_consumers
        ],
        "observed_progress_percent": item["observed_progress_percent"],
        "next_legal_action": "PATCH_ROOT_CAUSE_WRITER",
        "patch_owner_step_id": root["step_id"],
        "symptom_step_is_root_cause": target["step_id"] == root["step_id"],
        "mutation_authority": False,
    }


def _sample_graph() -> tuple[dict[str, Any], str]:
    from devsystem.causal_state_lineage_graph_v1 import seal_graph, value_digest

    good = value_digest({"selection": "V9"})
    bad7 = value_digest({"selection": "V7"})
    bad6 = value_digest({"selection": "V6"})
    graph = seal_graph(
        {
            "schema_version": 1,
            "version": STEP1_REQUIRED_VERSION,
            "revision": 1,
            "protections": {
                "exact_writer_required": True,
                "exact_consumer_required": True,
                "monotonic_generation_required": True,
                "stale_consumption_fails_closed": True,
                "conflicting_generation_fails_closed": True,
                "causal_dependencies_must_precede": True,
                "tamper_evident": True,
                "step_2a_required_for_mutation": True,
                "scope_lease_required_for_mutation": True,
                "mutation_authority": False,
            },
            "events": [
                {
                    "event_id": "step9-good",
                    "sequence": 1,
                    "kind": "WRITE",
                    "step_id": "STEP_9",
                    "field": "market.selection",
                    "generation": 1,
                    "value_digest": good,
                    "parent_write_event_id": "",
                    "depends_on_write_ids": [],
                },
                {
                    "event_id": "step8-read-good",
                    "sequence": 2,
                    "kind": "READ",
                    "step_id": "STEP_8",
                    "field": "market.selection",
                    "source_write_event_id": "step9-good",
                    "observed_generation": 1,
                },
                {
                    "event_id": "step7-overwrite",
                    "sequence": 3,
                    "kind": "WRITE",
                    "step_id": "STEP_7",
                    "field": "market.selection",
                    "generation": 2,
                    "value_digest": bad7,
                    "parent_write_event_id": "step9-good",
                    "depends_on_write_ids": ["step9-good"],
                },
                {
                    "event_id": "step7-read-bad",
                    "sequence": 4,
                    "kind": "READ",
                    "step_id": "STEP_7_CERT",
                    "field": "market.selection",
                    "source_write_event_id": "step7-overwrite",
                    "observed_generation": 2,
                },
                {
                    "event_id": "step6-propagate",
                    "sequence": 5,
                    "kind": "WRITE",
                    "step_id": "STEP_6",
                    "field": "market.selection",
                    "generation": 3,
                    "value_digest": bad6,
                    "parent_write_event_id": "step7-overwrite",
                    "depends_on_write_ids": ["step7-overwrite"],
                },
                {
                    "event_id": "final-read",
                    "sequence": 6,
                    "kind": "READ",
                    "step_id": "FINAL_CERT",
                    "field": "market.selection",
                    "source_write_event_id": "step6-propagate",
                    "observed_generation": 3,
                },
            ],
        }
    )
    return graph, good


def contract_self_test() -> dict[str, Any]:
    graph, good = _sample_graph()
    result = automatic_backtrace(
        graph,
        {
            "incident_id": "stall-97-7",
            "trigger": "PROGRESS_STALL",
            "field": "market.selection",
            "target_event_id": "final-read",
            "expected_value_digest": good,
            "last_known_good_write_id": "step9-good",
            "observed_progress_percent": 97.7,
        },
    )

    no_guess = automatic_backtrace(
        graph,
        {
            "incident_id": "no-evidence",
            "trigger": "BAD_FINAL_STATE",
            "field": "market.selection",
            "target_event_id": "final-read",
            "observed_progress_percent": 99.0,
        },
    )

    pre_regression = automatic_backtrace(
        graph,
        {
            "incident_id": "before-overwrite",
            "trigger": "DOWNSTREAM_MISMATCH",
            "field": "market.selection",
            "target_event_id": "step8-read-good",
            "expected_value_digest": good,
            "last_known_good_write_id": "step9-good",
            "observed_progress_percent": 60.0,
        },
    )

    tampered = deepcopy(graph)
    tampered["events"][2]["step_id"] = "HIDDEN_WRITER"
    tamper_blocked = False
    try:
        automatic_backtrace(
            tampered,
            {
                "incident_id": "tamper",
                "trigger": "STATE_REGRESSION",
                "field": "market.selection",
                "target_event_id": "final-read",
                "expected_value_digest": good,
                "last_known_good_write_id": "step9-good",
            },
        )
    except AutomaticRootCauseBacktraceFailure as exc:
        tamper_blocked = "Step-1 lineage validation failed" in str(exc)

    result_summary = {
        "status": "GREEN",
        "version": VERSION,
        "step1_version_bound": LINEAGE_VERSION == STEP1_REQUIRED_VERSION,
        "first_divergent_writer_identified": (
            result["root_cause_event_id"] == "step7-overwrite"
            and result["root_cause_step_id"] == "STEP_7"
        ),
        "nearest_symptom_writer_not_misblamed": (
            result["target_write_step_id"] == "STEP_6"
            and result["root_cause_step_id"] == "STEP_7"
        ),
        "backward_writer_chain_recorded": (
            result["writer_parent_chain_from_target"]
            == ["step6-propagate", "step7-overwrite", "step9-good"]
        ),
        "affected_consumers_recorded": (
            result["affected_consumer_steps"] == ["STEP_7_CERT", "FINAL_CERT"]
        ),
        "causal_path_recorded": (
            result["causal_path"][-1]["event_id"] == "final-read"
        ),
        "progress_stall_context_preserved": (
            result["observed_progress_percent"] == 97.7
        ),
        "insufficient_evidence_never_guesses": (
            no_guess["decision"] == "NO_CAUSAL_DIVERGENCE_FOUND"
            and no_guess["root_cause_found"] is False
        ),
        "pre_regression_target_not_falsely_blamed": (
            pre_regression["decision"] == "NO_CAUSAL_DIVERGENCE_FOUND"
        ),
        "tampered_step1_lineage_fails_closed": tamper_blocked,
        "patch_owner_is_root_writer": (
            result["next_legal_action"] == "PATCH_ROOT_CAUSE_WRITER"
            and result["patch_owner_step_id"] == "STEP_7"
        ),
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }
    required = (
        "step1_version_bound",
        "first_divergent_writer_identified",
        "nearest_symptom_writer_not_misblamed",
        "backward_writer_chain_recorded",
        "affected_consumers_recorded",
        "causal_path_recorded",
        "progress_stall_context_preserved",
        "insufficient_evidence_never_guesses",
        "pre_regression_target_not_falsely_blamed",
        "tampered_step1_lineage_fails_closed",
        "patch_owner_is_root_writer",
    )
    if not all(result_summary[name] is True for name in required):
        raise AutomaticRootCauseBacktraceFailure(
            "automatic root-cause backtrace self-test failed"
        )
    if (
        result_summary["network_calls"]
        or result_summary["auto_mutate"]
        or result_summary["may_modify_product_runtime"]
        or result_summary["mutation_authority_granted"]
    ):
        raise AutomaticRootCauseBacktraceFailure(
            "read-only safety invariant failed"
        )
    return result_summary


def main() -> int:
    result = contract_self_test()
    print("MONSTER_V7_STEP2_AUTOMATIC_ROOT_CAUSE_BACKTRACE_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AutomaticRootCauseBacktraceFailure as exc:
        print(f"MONSTER_V7_STEP2_AUTOMATIC_ROOT_CAUSE_BACKTRACE_BLOCKED: {exc}")
        raise SystemExit(1)
