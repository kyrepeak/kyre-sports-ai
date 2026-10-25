"""API2-only authority boundary."""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping

VERSION = "API2_ISOLATION_GUARD_V1"
API2_BASE_REF = "refs/heads/api2-main"

class IsolationViolation(RuntimeError):
    pass

def _walk(value: Any, path: str = "root"):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    else:
        yield path, value

def validate_api2_authority(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise IsolationViolation("API2_AUTHORITY_NOT_OBJECT")
    data = deepcopy(dict(value))
    foreign = "mon" + "ster"
    for path, item in _walk(data):
        if isinstance(item, str) and foreign in item.lower():
            raise IsolationViolation(f"API2_FOREIGN_AUTHORITY_REFERENCE:{path}")
    if "system" in data and str(data["system"]).lower() != "api2":
        raise IsolationViolation("API2_SYSTEM_IDENTITY_MISMATCH")
    base_ref = data.get("base_ref") or data.get("authoritative_base_ref")
    if base_ref is not None and base_ref != API2_BASE_REF:
        raise IsolationViolation("API2_BASE_REF_MISMATCH")
    for key in ("authoritative_branch", "branch"):
        branch = data.get(key)
        if branch is not None and not str(branch).startswith("api2-"):
            raise IsolationViolation(f"API2_BRANCH_NAMESPACE_VIOLATION:{key}")
    for key in ("problem_id", "proof_path"):
        identity = data.get(key)
        if identity is not None and not str(identity).startswith("api2-"):
            raise IsolationViolation(f"API2_IDENTITY_NAMESPACE_VIOLATION:{key}")
    return data
