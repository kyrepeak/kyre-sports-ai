"""Gated synthetic telemetry probe used only for Monster production certification.

The probe emits one harmless custom transport event plus one caught synthetic
exception through the shared PostHog client. It never raises into a user request
and is disabled unless MONSTER_TELEMETRY_PROBE_ENABLED=1.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import threading
from typing import Any

from sports_api.posthog_error_radar_v1 import (
    capture_runtime_exception,
    get_posthog_client,
    radar_status,
)

PROBE_VERSION = "MONSTER_TELEMETRY_PROBE_V1"
PROBE_FINGERPRINT = "MONSTER-A6-PROBE-V1"
PROBE_PATH = "/health/telemetry/probe"
TRANSPORT_EVENT = "monster_a6_transport_probe"
TRANSPORT_DISTINCT_ID = "monster-a6-certification"

_LOG = logging.getLogger(__name__)
_PROBE_LOCK = threading.Lock()
_PROBE_RESULT: dict[str, Any] | None = None


def telemetry_probe_enabled() -> bool:
    return os.getenv("MONSTER_TELEMETRY_PROBE_ENABLED", "").strip() == "1"


def run_telemetry_probe() -> dict[str, Any]:
    """Queue and flush one custom event plus one harmless synthetic exception."""
    if not telemetry_probe_enabled():
        return {
            "status": "disabled",
            "accepted": False,
            "probe_version": PROBE_VERSION,
        }

    timestamp = datetime.now(timezone.utc)
    marker = f"monster-a6-{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}"
    client = get_posthog_client()

    transport_queued = False
    transport_error: str | None = None
    if client is not None:
        try:
            client.capture(
                TRANSPORT_EVENT,
                distinct_id=TRANSPORT_DISTINCT_ID,
                properties={
                    "$process_person_profile": False,
                    "monster_certification_probe": marker,
                    "synthetic_certification_probe": True,
                    "probe_version": PROBE_VERSION,
                    "probe_timestamp_utc": timestamp.isoformat(),
                    "probe_kind": "transport",
                },
            )
            transport_queued = True
        except Exception as exc_transport:  # certification must stay fail-open
            transport_error = f"{type(exc_transport).__name__}: {exc_transport}"

    exc = RuntimeError("Monster certification synthetic exception probe")
    exception_accepted = capture_runtime_exception(
        exc,
        error_fingerprint=PROBE_FINGERPRINT,
        surface="sports_api",
        path=PROBE_PATH,
        method="GET",
        properties={
            "monster_certification_probe": marker,
            "synthetic_certification_probe": True,
            "probe_version": PROBE_VERSION,
            "probe_timestamp_utc": timestamp.isoformat(),
            "probe_kind": "exception",
        },
    )

    flushed = False
    flush_error: str | None = None
    if client is not None and (transport_queued or exception_accepted):
        try:
            client.flush()
            flushed = True
        except Exception as exc_flush:  # certification must stay fail-open
            flush_error = f"{type(exc_flush).__name__}: {exc_flush}"

    radar = radar_status()
    return {
        "status": "flushed" if flushed else "not_flushed",
        "accepted": bool(exception_accepted),
        "transport_queued": transport_queued,
        "transport_error": transport_error,
        "flushed": flushed,
        "flush_error": flush_error,
        "marker": marker,
        "probe_version": PROBE_VERSION,
        "radar": radar,
    }


def run_telemetry_probe_once() -> dict[str, Any]:
    """Emit at most one certification batch per process and cache the result."""
    global _PROBE_RESULT
    if not telemetry_probe_enabled():
        return {
            "status": "disabled",
            "accepted": False,
            "probe_version": PROBE_VERSION,
        }

    with _PROBE_LOCK:
        if _PROBE_RESULT is None:
            _PROBE_RESULT = run_telemetry_probe()
            radar = _PROBE_RESULT.get("radar") or {}
            _LOG.warning(
                "MONSTER_A6_TELEMETRY_PROBE status=%s exception_accepted=%s transport_queued=%s flushed=%s marker=%s host=%s configured=%s transport_error=%s flush_error=%s",
                _PROBE_RESULT.get("status"),
                _PROBE_RESULT.get("accepted"),
                _PROBE_RESULT.get("transport_queued"),
                _PROBE_RESULT.get("flushed"),
                _PROBE_RESULT.get("marker"),
                radar.get("host"),
                radar.get("configured"),
                _PROBE_RESULT.get("transport_error"),
                _PROBE_RESULT.get("flush_error"),
            )
        return dict(_PROBE_RESULT)
