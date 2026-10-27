"""KYRE GUARDIAN Step 2A and Anti-Loop control primitives."""
from __future__ import annotations

import re

_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def _require_sha(value: str, label: str) -> str:
    text = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(text):
        raise RuntimeError(f"{label} must be an exact git SHA")
    return text


def validate_step2a(
    *,
    system: str,
    locked_base_sha: str,
    current_main_sha: str,
    active_problem: str,
    active_lane_count: int,
    branch: str,
    pr_number: int,
    proof_complete: bool = False,
    freeze_requested: bool = False,
) -> None:
    """Enforce one exact-head Guardian lane and proof-before-freeze."""
    if str(system or "").strip() != "KYRE_GUARDIAN":
        raise RuntimeError("Guardian Step 2A system authority mismatch")

    locked = _require_sha(locked_base_sha, "locked base SHA")
    current = _require_sha(current_main_sha, "current main SHA")
    if locked != current:
        raise RuntimeError("authoritative main changed")

    if not str(active_problem or "").strip():
        raise RuntimeError("Guardian Step 2A requires one active problem")
    if int(active_lane_count) != 1:
        raise RuntimeError("exactly one active Guardian lane is required")
    if not str(branch or "").strip():
        raise RuntimeError("Guardian Step 2A requires one authoritative branch")
    if int(pr_number) <= 0:
        raise RuntimeError("Guardian Step 2A requires one authoritative PR")
    if bool(freeze_requested) and not bool(proof_complete):
        raise RuntimeError("proof-before-freeze violation")


def validate_anti_loop(
    *,
    run_attempt: int,
    previous_input_fingerprint: str,
    current_input_fingerprint: str,
) -> None:
    """Reject a retry when no material input changed after the first attempt."""
    attempt = int(run_attempt)
    if attempt < 1:
        raise RuntimeError("run attempt must be positive")

    previous = str(previous_input_fingerprint or "").strip()
    current = str(current_input_fingerprint or "").strip()
    if not previous or not current:
        raise RuntimeError("Anti-Loop requires input fingerprints")
    if attempt > 1 and previous == current:
        raise RuntimeError("blind retry blocked")
