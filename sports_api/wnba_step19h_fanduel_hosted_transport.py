"""WNBA Step 19H: sanitized FanDuel hosted-transport diagnostic.

Step19G proved that the exact certified provider path is healthy from GitHub
Actions but FanDuel returns an undecodable response from the Render host. This
module observes that transport without weakening or replacing any frozen
provider behavior.

It interposes only by supplying a requester when the existing Step11C FanDuel
fetcher would otherwise create its own httpx client. The requester uses the same
GET-only, no-redirect, no-cookie/auth behavior and returns the untouched httpx
response to the frozen Step11C parser. No response body, query string, public
web key, market record, player data, cookie, or secret is retained.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import threading
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step19f_draftkings_identity as step19f

SOURCE = "Kyre Sports API WNBA Step19H FanDuel hosted transport diagnostic"
MODEL_VERSION = "wnba_step19h_fanduel_hosted_transport_v1"
MAX_EVENTS = 40

_ORIGINAL_FETCH_STEP11C = fanduel.fetch_step11c_fanduel_provider_bridge
_LOCK = threading.RLock()
_EVENTS: list[dict[str, Any]] = []
_INSTALLED = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: object, limit: int = 160) -> str:
    return " ".join(str(value or "").split())[:limit]


def _body_shape(content: bytes) -> tuple[str, str | None]:
    stripped = bytes(content).lstrip()
    if not stripped:
        return "empty", None
    if stripped.startswith(b"\xef\xbb\xbf"):
        after = stripped[3:].lstrip()
        if after.startswith(b"{"):
            return "utf8_bom_json_object", "ef"
        if after.startswith(b"["):
            return "utf8_bom_json_array", "ef"
        return "utf8_bom_other", "ef"
    first = stripped[:1]
    if first == b"{":
        kind = "json_object"
    elif first == b"[":
        kind = "json_array"
    elif first == b"<":
        kind = "markup_or_html"
    elif first in {b")", b"]"}:
        kind = "possible_json_guard_prefix"
    else:
        kind = "other"
    return kind, first.hex()


def _append(event: Mapping[str, Any]) -> None:
    normalized = deepcopy(dict(event))
    with _LOCK:
        _EVENTS.append(normalized)
        if len(_EVENTS) > MAX_EVENTS:
            del _EVENTS[:-MAX_EVENTS]


def _response_event(url: str, response: Any) -> dict[str, Any]:
    parsed = urlparse(str(url))
    content = getattr(response, "content", b"")
    body = bytes(content) if isinstance(content, (bytes, bytearray)) else b""
    shape, first_byte = _body_shape(body)
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        try:
            headers = dict(headers)
        except Exception:
            headers = {}
    try:
        response.json()
    except Exception as exc:
        json_decodable = False
        json_error_type = type(exc).__name__
    else:
        json_decodable = True
        json_error_type = None
    return {
        "captured_at_utc": _now(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path,
        "method": "GET",
        "status_code": getattr(response, "status_code", None),
        "content_type": _safe_text(headers.get("content-type")),
        "content_encoding": _safe_text(headers.get("content-encoding")),
        "content_length_header": _safe_text(headers.get("content-length")),
        "body_byte_length": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_shape": shape,
        "first_non_whitespace_byte_hex": first_byte,
        "json_decodable": json_decodable,
        "json_error_type": json_error_type,
        "query_captured": False,
        "body_captured": False,
        "response_headers_whitelisted_only": True,
    }


def _transport_error_event(url: str, exc: Exception) -> dict[str, Any]:
    parsed = urlparse(str(url))
    return {
        "captured_at_utc": _now(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path,
        "method": "GET",
        "status_code": None,
        "content_type": "",
        "content_encoding": "",
        "content_length_header": "",
        "body_byte_length": None,
        "body_sha256": None,
        "body_shape": "transport_exception_before_response",
        "first_non_whitespace_byte_hex": None,
        "json_decodable": False,
        "json_error_type": None,
        "transport_error_type": type(exc).__name__,
        "transport_error_message": _safe_text(exc, 200),
        "query_captured": False,
        "body_captured": False,
        "response_headers_whitelisted_only": True,
    }


def diagnostic_requester(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float,
) -> Any:
    """Perform the same public GET and retain only non-sensitive response metadata."""
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            headers=dict(headers or {}),
        ) as client:
            response = client.get(url, params=dict(params or {}))
    except Exception as exc:
        if (urlparse(str(url)).hostname or "").casefold() == "api.sportsbook.fanduel.com":
            _append(_transport_error_event(url, exc))
        raise
    if (urlparse(str(url)).hostname or "").casefold() == "api.sportsbook.fanduel.com":
        _append(_response_event(url, response))
    return response


def fetch_step11c_with_transport_probe(
    *,
    season: int,
    slate_date: str,
    evaluated_at: datetime | None = None,
    requester: Callable[..., Any] | None = None,
    roster_loader: Callable[[int], Mapping[str, Any]] | None = None,
    timeout_seconds: float = fanduel.DEFAULT_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Delegate unchanged to frozen Step11C, injecting the probe only for default transport."""
    effective_requester = requester if requester is not None else diagnostic_requester
    return _ORIGINAL_FETCH_STEP11C(
        season=season,
        slate_date=slate_date,
        evaluated_at=evaluated_at,
        requester=effective_requester,
        roster_loader=roster_loader,
        timeout_seconds=timeout_seconds,
        env=env,
    )


def install_step19h_fanduel_hosted_transport() -> dict[str, Any]:
    global _INSTALLED
    step19f.install_step19f_draftkings_identity()
    if fanduel.fetch_step11c_fanduel_provider_bridge is not fetch_step11c_with_transport_probe:
        fanduel.fetch_step11c_fanduel_provider_bridge = fetch_step11c_with_transport_probe
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    return {
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "installed": _INSTALLED,
        "fanduel_fetch_wrapper_active": (
            fanduel.fetch_step11c_fanduel_provider_bridge is fetch_step11c_with_transport_probe
        ),
        "request_method_changed": False,
        "redirect_policy_changed": False,
        "authentication_added": False,
        "cookies_added": False,
        "readiness_relaxed": False,
        "provider_retry_policy_modified": False,
        "projection_logic_modified": False,
        "controller_state_modified": False,
        "response_body_logged": False,
        "query_logged": False,
        "wagering_enabled": False,
    }


def get_step19h_fanduel_transport_status() -> dict[str, Any]:
    with _LOCK:
        events = deepcopy(_EVENTS)
    invalid = [event for event in events if event.get("json_decodable") is False]
    latest = events[-1] if events else None
    return {
        "data_type": "wnba_step19h_fanduel_hosted_transport",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": _INSTALLED,
        "captured_event_count": len(events),
        "invalid_json_event_count": len(invalid),
        "latest": latest,
        "events": events,
        "installation": installation_status(),
        "guardrails": {
            "metadata_only": True,
            "response_body_logged": False,
            "query_logged": False,
            "cookies_logged": False,
            "secrets_logged": False,
            "market_records_logged": False,
            "readiness_relaxed": False,
            "provider_behavior_changed": False,
        },
    }


def _clear_for_test() -> None:
    with _LOCK:
        _EVENTS.clear()


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "diagnostic_requester",
    "fetch_step11c_with_transport_probe",
    "get_step19h_fanduel_transport_status",
    "install_step19h_fanduel_hosted_transport",
    "installation_status",
]
