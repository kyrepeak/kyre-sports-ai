"""Monster Runtime Lab V1 — sanitized request/response replay artifacts.

Turns an observed HTTP response into a reviewable, versioned JSON artifact that
can be replayed later by ``monster_runtime_replay_v1``. Raw credentials are
never retained. This module performs no network calls on its own.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from sports_api.monster_runtime_replay_v1 import (
    ReplaySession,
    ResponseFixture,
    sanitize_mapping,
)

CAPTURE_VERSION = "MONSTER_RUNTIME_CAPTURE_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
NETWORK_CALLS = False
MAX_ARTIFACT_BYTES = 262_144
MAX_SANITIZE_DEPTH = 8
MAX_SEQUENCE_ITEMS = 500

_ALLOWED_HEADER_PREFIXES = (
    "content-type",
    "cache-control",
    "retry-after",
    "x-request-id",
    "x-kyre-",
)


def _safe_url(value: str) -> str:
    parsed = urlsplit(str(value))
    # Never preserve HTTP userinfo (user:password@host), query strings, or
    # fragments in replay artifacts. Rebuild authority from hostname + port.
    hostname = parsed.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Captured URL contains an invalid port") from exc
    authority = f"{hostname}:{port}" if port is not None else hostname
    return urlunsplit((parsed.scheme, authority, parsed.path, "", ""))


def _safe_headers(headers: Mapping[str, Any] | None) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for key, value in dict(headers or {}).items():
        lowered = str(key).lower()
        if any(lowered == prefix or lowered.startswith(prefix) for prefix in _ALLOWED_HEADER_PREFIXES):
            selected[str(key)] = value
    return sanitize_mapping(selected)


def _sanitize_json_value(value: Any, *, depth: int = 0) -> Any:
    """Recursively sanitize arbitrary JSON-like values.

    Mapping keys still go through the shared secret-key redactor, while scalar
    values (including scalars nested inside lists/tuples) go through the same
    Bearer/Basic credential redaction used by Runtime Replay. Depth and sequence
    caps keep hostile or accidental payloads bounded before artifact sizing.
    """
    if depth >= MAX_SANITIZE_DEPTH:
        return "<max-depth>"
    if isinstance(value, Mapping):
        recursively_sanitized = {
            str(key): _sanitize_json_value(item, depth=depth + 1)
            for key, item in value.items()
        }
        return sanitize_mapping(recursively_sanitized)
    if isinstance(value, (list, tuple)):
        return [
            _sanitize_json_value(item, depth=depth + 1)
            for item in list(value)[:MAX_SEQUENCE_ITEMS]
        ]
    # Route a scalar through the shared value sanitizer without relying on a
    # private helper from monster_runtime_replay_v1.
    return sanitize_mapping({"value": value})["value"]


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True, slots=True)
class ReplayArtifact:
    route_key: str
    method: str
    url: str
    status_code: int
    headers: Mapping[str, Any]
    params: Mapping[str, Any]
    json_body: Any
    malformed_json: bool = False
    timeout: bool = False
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": CAPTURE_VERSION,
            "route_key": self.route_key,
            "method": self.method,
            "url": self.url,
            "status_code": int(self.status_code),
            "headers": dict(self.headers),
            "params": dict(self.params),
            "json_body": self.json_body,
            "malformed_json": bool(self.malformed_json),
            "timeout": bool(self.timeout),
            "note": self.note[:500],
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
            "network_calls": NETWORK_CALLS,
        }
        encoded = _canonical_json(payload).encode("utf-8")
        if len(encoded) > MAX_ARTIFACT_BYTES:
            raise ValueError("Replay artifact exceeds safety size limit")
        return payload

    @property
    def fingerprint(self) -> str:
        payload = self.as_dict().copy()
        payload.pop("note", None)
        digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:16].upper()
        return f"REPLAY-{digest}"

    def to_fixture(self) -> ResponseFixture:
        return ResponseFixture(
            status_code=self.status_code,
            json_body=self.json_body,
            headers={str(key): str(value) for key, value in self.headers.items()},
            timeout=self.timeout,
            malformed_json=self.malformed_json,
        )


def capture_response(
    *,
    route_key: str,
    url: str,
    status_code: int,
    json_body: Any,
    headers: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
    method: str = "GET",
    malformed_json: bool = False,
    timeout: bool = False,
    note: str = "",
) -> ReplayArtifact:
    key = str(route_key or "").strip()
    if not key:
        raise ValueError("route_key must be non-empty")
    artifact = ReplayArtifact(
        route_key=key,
        method=str(method or "GET").upper(),
        url=_safe_url(url),
        status_code=int(status_code),
        headers=_safe_headers(headers),
        params=sanitize_mapping(dict(params or {})),
        json_body=_sanitize_json_value(json_body),
        malformed_json=bool(malformed_json),
        timeout=bool(timeout),
        note=str(_sanitize_json_value(str(note or ""))),
    )
    artifact.as_dict()  # enforce size/safety now
    return artifact


def artifact_from_dict(payload: Mapping[str, Any]) -> ReplayArtifact:
    if payload.get("version") != CAPTURE_VERSION:
        raise ValueError("Unsupported replay artifact version")
    return capture_response(
        route_key=str(payload.get("route_key") or ""),
        url=str(payload.get("url") or ""),
        status_code=int(payload.get("status_code") or 0),
        json_body=payload.get("json_body"),
        headers=payload.get("headers") if isinstance(payload.get("headers"), Mapping) else {},
        params=payload.get("params") if isinstance(payload.get("params"), Mapping) else {},
        method=str(payload.get("method") or "GET"),
        malformed_json=bool(payload.get("malformed_json")),
        timeout=bool(payload.get("timeout")),
        note=str(payload.get("note") or ""),
    )


def write_artifact(path: str | Path, artifact: ReplayArtifact) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def read_artifact(path: str | Path) -> ReplayArtifact:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Replay artifact root must be a JSON object")
    return artifact_from_dict(payload)


def session_from_artifacts(*artifacts: ReplayArtifact) -> ReplaySession:
    session = ReplaySession()
    grouped: dict[str, list[ResponseFixture]] = {}
    for artifact in artifacts:
        grouped.setdefault(artifact.url, []).append(artifact.to_fixture())
    for url, fixtures in grouped.items():
        session.register(url, *fixtures)
    return session


__all__ = [
    "CAPTURE_VERSION",
    "MAX_ARTIFACT_BYTES",
    "MAX_SANITIZE_DEPTH",
    "MAX_SEQUENCE_ITEMS",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SOURCE_DATA",
    "NETWORK_CALLS",
    "PROJECTION_WEIGHT",
    "ReplayArtifact",
    "artifact_from_dict",
    "capture_response",
    "read_artifact",
    "session_from_artifacts",
    "write_artifact",
]
