"""MONSTER Coding Intelligence V1 Step 1 — Intelligence Case Contract.

Pure problem-understanding contract only. This module normalizes engineering
case input before diagnosis. It performs no network calls, grants no mutation
authority, and intentionally contains no evidence ranking, hypothesis, or
root-cause logic.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

VERSION = "MONSTER_CODING_INTELLIGENCE_V1_STEP1_CASE_CONTRACT_V1"
SCHEMA_VERSION = 1
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0

_REQUIRED_FIELDS = frozenset({
    "workstream_id",
    "goal",
    "visible_symptom",
    "success_condition",
    "solved_when",
})
_OPTIONAL_FIELDS = frozenset({
    "constraints",
    "do_not_change",
    "required_changes",
    "affected_systems",
    "environment",
    "current_known_state",
    "suspected_subsystems",
})
_ALLOWED_INPUT_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS
_COLLECTION_FIELDS = (
    "constraints",
    "do_not_change",
    "required_changes",
    "affected_systems",
    "current_known_state",
    "suspected_subsystems",
)
_SEMANTIC_FIELDS = (
    "workstream_id",
    "goal",
    "visible_symptom",
    "success_condition",
    "solved_when",
    "constraints",
    "do_not_change",
    "required_changes",
    "affected_systems",
    "environment",
    "current_known_state",
    "suspected_subsystems",
)
_WORKSTREAM_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")
_IMPLEMENTATION_ONLY_SUCCESS = frozenset({
    "merge",
    "merge pr",
    "open pr",
    "deploy",
    "commit",
    "push",
    "patch",
    "edit file",
})


class IntelligenceCaseValidationFailure(RuntimeError):
    """Raised when an Intelligence Case violates the Step-1 contract."""


def _normalize_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise IntelligenceCaseValidationFailure(f"{field} must be text")
    text = unicodedata.normalize("NFKC", value)
    text = " ".join(text.split()).strip()
    text = text.rstrip(".").rstrip()
    text = text.casefold()
    if not text:
        raise IntelligenceCaseValidationFailure(f"{field} must not be empty")
    return text


def _normalize_workstream(value: Any) -> str:
    text = _normalize_text(value, field="workstream_id")
    if not _WORKSTREAM_RE.fullmatch(text):
        raise IntelligenceCaseValidationFailure("workstream_id has invalid characters")
    return text


def _normalize_collection(value: Any, *, field: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise IntelligenceCaseValidationFailure(f"{field} must be a collection or null")
    normalized = [_normalize_text(item, field=field) for item in value]
    return sorted(set(normalized))


def _normalize_optional_text(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    return _normalize_text(value, field=field)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _case_id(semantic: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(_canonical(semantic).encode("utf-8")).hexdigest()
    return "CASE-" + digest[:24].upper()


def _reject_implementation_only_success(field: str, value: str) -> None:
    if value in _IMPLEMENTATION_ONLY_SUCCESS:
        raise IntelligenceCaseValidationFailure(
            f"{field} must describe an observable outcome, not only an implementation action"
        )


def normalize_intelligence_case(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one pre-diagnosis Intelligence Case."""
    if not isinstance(packet, Mapping):
        raise IntelligenceCaseValidationFailure("case packet must be a mapping")

    raw = dict(packet)
    unknown = sorted(set(raw) - _ALLOWED_INPUT_FIELDS)
    if unknown:
        raise IntelligenceCaseValidationFailure(
            "unknown or later-step fields are forbidden: " + ", ".join(unknown)
        )

    missing = sorted(_REQUIRED_FIELDS - set(raw))
    if missing:
        raise IntelligenceCaseValidationFailure(
            "missing required fields: " + ", ".join(missing)
        )

    semantic: dict[str, Any] = {
        "workstream_id": _normalize_workstream(raw["workstream_id"]),
        "goal": _normalize_text(raw["goal"], field="goal"),
        "visible_symptom": _normalize_text(raw["visible_symptom"], field="visible_symptom"),
        "success_condition": _normalize_text(raw["success_condition"], field="success_condition"),
        "solved_when": _normalize_text(raw["solved_when"], field="solved_when"),
    }

    for field in _COLLECTION_FIELDS:
        semantic[field] = _normalize_collection(raw.get(field), field=field)
    semantic["environment"] = _normalize_optional_text(raw.get("environment"), field="environment")

    _reject_implementation_only_success("success_condition", semantic["success_condition"])
    _reject_implementation_only_success("solved_when", semantic["solved_when"])

    required_changes = semantic["required_changes"]
    do_not_change = semantic["do_not_change"]
    if required_changes is not None and do_not_change is not None:
        conflict = sorted(set(required_changes) & set(do_not_change))
        if conflict:
            raise IntelligenceCaseValidationFailure(
                "required_changes conflicts with do_not_change: " + ", ".join(conflict)
            )

    normalized = {
        "schema_version": SCHEMA_VERSION,
        "version": VERSION,
        "case_id": _case_id({field: semantic[field] for field in _SEMANTIC_FIELDS}),
        **semantic,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
    }
    return normalized


def serialize_intelligence_case(packet: Mapping[str, Any]) -> str:
    """Serialize a normalized case as canonical deterministic JSON."""
    return _canonical(normalize_intelligence_case(packet))


def _display(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, list):
        return "none" if not value else ", ".join(value)
    return str(value)


def render_intelligence_case(packet: Mapping[str, Any]) -> str:
    """Render a normalized case in a fixed human-readable order."""
    case = normalize_intelligence_case(packet)
    return "\n".join([
        "MONSTER CODING INTELLIGENCE — INTELLIGENCE CASE",
        f"Case ID: {case['case_id']}",
        f"Workstream: {case['workstream_id']}",
        f"Goal: {case['goal']}",
        f"Visible Symptom: {case['visible_symptom']}",
        f"Success Condition: {case['success_condition']}",
        f"Solved When: {case['solved_when']}",
        f"Constraints: {_display(case['constraints'])}",
        f"Do Not Change: {_display(case['do_not_change'])}",
        f"Required Changes: {_display(case['required_changes'])}",
        f"Affected Systems: {_display(case['affected_systems'])}",
        f"Environment: {_display(case['environment'])}",
        f"Current Known State: {_display(case['current_known_state'])}",
        f"Suspected Subsystems: {_display(case['suspected_subsystems'])}",
        f"Mutation Authority: {str(case['mutation_authority_granted']).lower()}",
        f"GitHub Actions Fallback: {case['github_actions_fallback']}",
    ])
