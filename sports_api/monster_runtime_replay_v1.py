"""Monster Runtime Lab V1 — deterministic HTTP reproduction and replay.

Developer-only tooling. No network calls, no production mutation, no model math.
It creates requests-compatible replay sessions so a verifier/adapter can be run
against exact HTTP status/body/timeout cases without touching a live provider.
"""
from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

import requests

REPLAY_VERSION = "MONSTER_RUNTIME_REPLAY_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False
NETWORK_CALLS = False

_SECRET_KEY_RE = re.compile(r"(?i)(authorization|cookie|set-cookie|api[-_]?key|token|secret|password|passwd)")
_SECRET_VALUE_RE = re.compile(r"(?i)(bearer\s+\S+|basic\s+\S+)")


@dataclass(frozen=True, slots=True)
class ResponseFixture:
    status_code: int
    json_body: Any = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    text_body: str | None = None
    timeout: bool = False
    malformed_json: bool = False
    delay_ms: float = 0.0

    def __post_init__(self) -> None:
        if not 100 <= int(self.status_code) <= 599:
            raise ValueError("status_code must be a valid HTTP status")
        if float(self.delay_ms) < 0:
            raise ValueError("delay_ms must be >= 0")


@dataclass(frozen=True, slots=True)
class ExchangeRecord:
    method: str
    url: str
    params: Mapping[str, Any]
    status_code: int | None
    request_id: str
    headers: Mapping[str, str]
    body_shape: Any
    outcome: str
    duration_ms: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "params": dict(self.params),
            "status_code": self.status_code,
            "request_id": self.request_id,
            "headers": dict(self.headers),
            "body_shape": copy.deepcopy(self.body_shape),
            "outcome": self.outcome,
            "duration_ms": round(float(self.duration_ms), 2),
        }


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    if _SECRET_VALUE_RE.search(text):
        return "<redacted>"
    return text[:160]


def sanitize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if _SECRET_KEY_RE.search(key):
            result[key] = "<redacted>"
        elif isinstance(raw_value, Mapping):
            result[key] = sanitize_mapping(raw_value)
        elif isinstance(raw_value, (list, tuple)):
            result[key] = [
                sanitize_mapping(item) if isinstance(item, Mapping) else _safe_scalar(item)
                for item in raw_value[:25]
            ]
        else:
            result[key] = _safe_scalar(raw_value)
    return result


def body_shape(value: Any, *, depth: int = 0) -> Any:
    """Return structure/type information without retaining arbitrary payload data."""
    if depth >= 4:
        return "..."
    if isinstance(value, Mapping):
        shaped: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:50]:
            key = str(raw_key)
            if _SECRET_KEY_RE.search(key):
                shaped[key] = "<redacted>"
            else:
                shaped[key] = body_shape(raw_value, depth=depth + 1)
        return shaped
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "sample": [body_shape(item, depth=depth + 1) for item in value[:3]],
        }
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "str"


class ReplayResponse:
    def __init__(self, fixture: ResponseFixture, *, url: str) -> None:
        self._fixture = fixture
        self.status_code = int(fixture.status_code)
        self.url = url
        self.headers = dict(fixture.headers)
        if fixture.text_body is not None:
            self.text = fixture.text_body
        else:
            try:
                self.text = json.dumps(fixture.json_body)
            except TypeError:
                self.text = str(fixture.json_body)

    def json(self) -> Any:
        if self._fixture.malformed_json:
            raise ValueError("Monster replay: malformed JSON")
        return copy.deepcopy(self._fixture.json_body)

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            response = requests.Response()
            response.status_code = self.status_code
            response.url = self.url
            response._content = self.text.encode("utf-8", errors="replace")
            raise requests.HTTPError(
                f"{self.status_code} replay response for {self.url}",
                response=response,
            )


class ReplaySession:
    """requests.Session-shaped deterministic route table with exchange capture."""

    def __init__(self) -> None:
        self._routes: dict[str, list[ResponseFixture]] = {}
        self.exchanges: list[ExchangeRecord] = []
        self._counter = 0

    def register(self, url: str, *fixtures: ResponseFixture) -> None:
        if not fixtures:
            raise ValueError("At least one fixture is required")
        self._routes[str(url)] = list(fixtures)

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        timeout: float | int | None = None,
        allow_redirects: bool = True,
        **_: Any,
    ) -> ReplayResponse:
        del timeout, allow_redirects
        target = str(url)
        queue = self._routes.get(target)
        if not queue:
            raise AssertionError(f"No Monster replay fixture registered for {target}")
        fixture = queue[0] if len(queue) == 1 else queue.pop(0)
        self._counter += 1
        request_id = str(fixture.headers.get("X-Request-ID") or f"monster-replay-{self._counter:04d}")
        started = time.perf_counter()
        if fixture.delay_ms:
            time.sleep(float(fixture.delay_ms) / 1000.0)
        if fixture.timeout:
            duration_ms = (time.perf_counter() - started) * 1000.0
            self.exchanges.append(
                ExchangeRecord(
                    method="GET",
                    url=target,
                    params=sanitize_mapping(dict(params or {})),
                    status_code=None,
                    request_id=request_id,
                    headers=sanitize_mapping(dict(fixture.headers)),
                    body_shape=None,
                    outcome="timeout",
                    duration_ms=duration_ms,
                )
            )
            raise requests.Timeout(f"Monster replay timeout for {target}")

        response = ReplayResponse(fixture, url=target)
        duration_ms = (time.perf_counter() - started) * 1000.0
        self.exchanges.append(
            ExchangeRecord(
                method="GET",
                url=target,
                params=sanitize_mapping(dict(params or {})),
                status_code=response.status_code,
                request_id=request_id,
                headers=sanitize_mapping(dict(fixture.headers)),
                body_shape=body_shape(fixture.json_body),
                outcome="response",
                duration_ms=duration_ms,
            )
        )
        return response

    def receipt(self) -> dict[str, Any]:
        return {
            "version": REPLAY_VERSION,
            "exchange_count": len(self.exchanges),
            "exchanges": [item.as_dict() for item in self.exchanges],
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
            "network_calls": NETWORK_CALLS,
        }


CFB_PROTECTED_503_DETAIL = (
    "CFB odds endpoint is not ready: market identity coverage is incomplete"
)


def canonical_http_scenarios() -> dict[str, ResponseFixture]:
    return {
        "200": ResponseFixture(200, {"status": "ok"}),
        "404": ResponseFixture(404, {"detail": "not found"}),
        "429": ResponseFixture(429, {"detail": "rate limited"}),
        "500": ResponseFixture(500, {"detail": "internal error"}),
        "502": ResponseFixture(502, {"detail": "bad gateway"}),
        "503": ResponseFixture(503, {"detail": CFB_PROTECTED_503_DETAIL}),
        "timeout": ResponseFixture(200, {"status": "late"}, timeout=True),
        "malformed_json": ResponseFixture(200, {}, text_body="not-json", malformed_json=True),
    }


def legacy_json_helper(session: ReplaySession, url: str) -> tuple[int, dict[str, Any]]:
    """Reproduce the pre-PR-440 helper ordering: status raise before body inspection."""
    response = session.get(url, timeout=60.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("Expected JSON object")
    return response.status_code, payload


def body_aware_json_helper(session: ReplaySession, url: str) -> tuple[int, dict[str, Any]]:
    """Preserve non-2xx JSON so caller-specific safety contracts can inspect it."""
    response = session.get(url, timeout=60.0)
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("Expected JSON object")
    return response.status_code, payload


__all__ = [
    "CFB_PROTECTED_503_DETAIL",
    "ExchangeRecord",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_SOURCE_DATA",
    "NETWORK_CALLS",
    "PROJECTION_WEIGHT",
    "REPLAY_VERSION",
    "ReplayResponse",
    "ReplaySession",
    "ResponseFixture",
    "body_aware_json_helper",
    "body_shape",
    "canonical_http_scenarios",
    "legacy_json_helper",
    "sanitize_mapping",
]
