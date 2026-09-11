"""Stable, secret-safe failure fingerprints for DevSystem incidents."""
from __future__ import annotations

import hashlib
import re
from typing import Any


def _normalize(value: str) -> str:
    text = (value or "").lower().strip()
    text = re.sub(r"https?://\S+", "<url>", text)
    text = re.sub(r"\b[0-9a-f]{7,64}\b", "<hex>", text)
    text = re.sub(r"\b\d+(?:\.\d+)?(?:ms|s|sec|secs|seconds|m|min|minutes)?\b", "<n>", text)
    text = re.sub(r"line\s+\d+", "line <n>", text)
    text = re.sub(r"/[^\s:]+", "<path>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500]


def failure_fingerprint(failure: dict[str, Any]) -> str:
    """Return a stable ID for the same lane/signal/error identity across runs."""
    parts = [
        str(failure.get("job") or "unknown"),
        str(failure.get("layer") or "unknown"),
        str(failure.get("evidence_signal") or "none"),
        _normalize(str(failure.get("evidence_match") or failure.get("diagnosis") or "")),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12].upper()
    return f"KYRE-CI-{digest}"


def attach_fingerprints(report: dict[str, Any]) -> dict[str, Any]:
    failures = report.get("failures") or []
    for failure in failures:
        failure["failure_fingerprint"] = failure_fingerprint(failure)
    primary = report.get("primary")
    if primary:
        primary["failure_fingerprint"] = failure_fingerprint(primary)
    return report
