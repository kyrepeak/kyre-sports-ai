"""WNBA Step 6E: read-only DraftKings endpoint discovery and validation.

This module does not place wagers, use an account session, or bypass access
controls. It performs bounded GET-only probes against explicitly enumerated
public DraftKings sportsbook JSON endpoint families, validates that a response
belongs to the WNBA league, and checks whether Step 6D can normalize supported
player props from it.

Step 6E intentionally keeps live endpoint selection separate from Step 6D's
frozen collector. A candidate is usable only after a live probe verifies a
successful JSON response with WNBA identity and supported normalized offers.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any
from urllib.parse import urlparse

import httpx

from sports_api.collectors.wnba_draftkings_direct import (
    DEFAULT_USER_AGENT,
    MAX_RESPONSE_BYTES,
    normalize_draftkings_document,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6E DraftKings endpoint discovery"
MODEL_VERSION = "wnba_step_6e_draftkings_endpoint_discovery_v1"
SCHEMA_VERSION = MODEL_VERSION

# Current 2026 DraftKings sportsbook league identity observed by multiple
# independent public references. The old 88671423 identifier was an earlier
# event-group family and is retained only as a historical fallback probe.
WNBA_LEAGUE_ID = "94682"
WNBA_TEMPLATE_ID = "f0613a94-e73b-4ae6-bf2c-2abafc297015"
HISTORICAL_WNBA_EVENT_GROUP_ID = "88671423"

DISCOVERY_TIMEOUT_ENV = "WNBA_DRAFTKINGS_DISCOVERY_TIMEOUT_SECONDS"
DISCOVERY_CANDIDATES_ENV = "WNBA_DRAFTKINGS_DISCOVERY_CANDIDATES_JSON"
DEFAULT_TIMEOUT_SECONDS = 12.0
MAX_TIMEOUT_SECONDS = 30.0
MAX_CANDIDATES = 8

# 1000074 is a currently observed basketball Player Props category in the
# modern sportscontent family. Step 6E never assumes it is valid for WNBA: the
# live probe must prove WNBA identity and produce supported normalized offers.
DEFAULT_CANDIDATES: tuple[dict[str, str], ...] = (
    {
        "candidate_id": "modern_dkusoh_player_props",
        "family": "sportscontent_category",
        "url": "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/94682/categories/1000074",
    },
    {
        "candidate_id": "modern_dkusoh_league",
        "family": "sportscontent_league",
        "url": "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/94682",
    },
    {
        "candidate_id": "v5_current_league_id",
        "family": "eventgroups_v5",
        "url": "https://sportsbook-nash.draftkings.com/sites/US-SB/api/v5/eventgroups/94682?format=json",
    },
    {
        "candidate_id": "v5_historical_event_group",
        "family": "eventgroups_v5_historical",
        "url": "https://sportsbook-nash.draftkings.com/sites/US-SB/api/v5/eventgroups/88671423?format=json",
    },
)


class WNBADraftKingsDiscoveryInputError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _allowed_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold()
    return (
        parsed.scheme == "https"
        and bool(host)
        and (host == "draftkings.com" or host.endswith(".draftkings.com"))
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def _timeout(env: Mapping[str, str]) -> float:
    raw = _clean(env.get(DISCOVERY_TIMEOUT_ENV))
    if raw is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError as exc:
        raise WNBADraftKingsDiscoveryInputError(f"{DISCOVERY_TIMEOUT_ENV} must be numeric.") from exc
    if not 0.5 <= value <= MAX_TIMEOUT_SECONDS:
        raise WNBADraftKingsDiscoveryInputError(
            f"{DISCOVERY_TIMEOUT_ENV} must be between 0.5 and {MAX_TIMEOUT_SECONDS} seconds."
        )
    return value


def resolve_discovery_candidates(
    candidates: Sequence[Mapping[str, Any]] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    environment = _environment(env)
    if candidates is None:
        raw = _clean(environment.get(DISCOVERY_CANDIDATES_ENV))
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise WNBADraftKingsDiscoveryInputError(
                    f"{DISCOVERY_CANDIDATES_ENV} must be valid JSON."
                ) from exc
            if not isinstance(parsed, list):
                raise WNBADraftKingsDiscoveryInputError(
                    f"{DISCOVERY_CANDIDATES_ENV} must be a JSON array."
                )
            candidates = parsed
        else:
            candidates = DEFAULT_CANDIDATES

    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise WNBADraftKingsDiscoveryInputError("Discovery candidates must be a sequence.")
    if not candidates or len(candidates) > MAX_CANDIDATES:
        raise WNBADraftKingsDiscoveryInputError(
            f"Step 6E requires 1 through {MAX_CANDIDATES} endpoint candidates."
        )

    result: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for index, row in enumerate(candidates):
        if not isinstance(row, Mapping):
            raise WNBADraftKingsDiscoveryInputError("Every discovery candidate must be an object.")
        candidate_id = _clean(row.get("candidate_id")) or f"candidate_{index + 1}"
        family = _clean(row.get("family")) or "custom"
        url = _clean(row.get("url"))
        if not url or not _allowed_url(url):
            raise WNBADraftKingsDiscoveryInputError(
                "Step 6E accepts HTTPS draftkings.com candidate URLs only."
            )
        if candidate_id in seen_ids:
            raise WNBADraftKingsDiscoveryInputError("Discovery candidate ids must be unique.")
        if url in seen_urls:
            continue
        result.append({"candidate_id": candidate_id, "family": family, "url": url})
        seen_ids.add(candidate_id)
        seen_urls.add(url)
    return result


def get_endpoint_discovery_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _environment(env)
    try:
        candidates = resolve_discovery_candidates(env=environment)
        timeout = _timeout(environment)
        blocker = None
    except WNBADraftKingsDiscoveryInputError as exc:
        candidates = []
        timeout = DEFAULT_TIMEOUT_SECONDS
        blocker = str(exc)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6e_draftkings_endpoint_discovery_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "wnba_league_id": WNBA_LEAGUE_ID,
        "wnba_template_id": WNBA_TEMPLATE_ID,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "request_timeout_seconds": timeout,
        "configuration_ready": blocker is None and bool(candidates),
        "configuration_blocker": blocker,
        "live_probe_performed": False,
        "live_endpoint_verified": False,
        "safety": {
            "http_method": "GET",
            "authentication_used": False,
            "cookies_used": False,
            "wager_actions": False,
            "paid_odds_vendor_used": False,
            "step_6d_auto_enabled": False,
        },
    }


def _response_json(response: Any) -> tuple[int | None, Any | None, str | None]:
    status = getattr(response, "status_code", None)
    if status != 200:
        return status, None, f"http_{status if status is not None else 'unknown'}"
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)) and len(content) > MAX_RESPONSE_BYTES:
        return status, None, "response_too_large"
    try:
        return status, response.json(), None
    except Exception:
        return status, None, "invalid_json"


def _document_mentions_wnba(document: Any) -> bool:
    if not isinstance(document, dict):
        return False
    encoded = json.dumps(document, ensure_ascii=False, default=str).casefold()
    if '"94682"' in encoded or ':94682' in encoded:
        return True
    if '"wnba"' in encoded or "wnba" in encoded:
        return True
    return False


def _document_shape(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        return {
            "json_object": False,
            "event_count": 0,
            "market_count": 0,
            "selection_count": 0,
        }
    event_group = document.get("eventGroup") if isinstance(document.get("eventGroup"), dict) else {}
    events = document.get("events") if isinstance(document.get("events"), list) else event_group.get("events")
    markets = document.get("markets") if isinstance(document.get("markets"), list) else []
    selections = document.get("selections") if isinstance(document.get("selections"), list) else []
    return {
        "json_object": True,
        "event_count": len(events) if isinstance(events, list) else 0,
        "market_count": len(markets),
        "selection_count": len(selections),
    }


def _get(url: str, *, timeout_seconds: float, requester: Callable[..., Any] | None) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": "https://sportsbook.draftkings.com/leagues/basketball/wnba",
        "Origin": "https://sportsbook.draftkings.com",
    }
    if requester is not None:
        try:
            return requester(url, headers=headers, timeout=timeout_seconds)
        except TypeError:
            return requester("GET", url, headers=headers, timeout=timeout_seconds)
    with httpx.Client(timeout=timeout_seconds, follow_redirects=False, headers=headers) as client:
        return client.get(url)


def probe_draftkings_wnba_endpoints(
    candidates: Sequence[Mapping[str, Any]] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    environment = _environment(env)
    resolved = resolve_discovery_candidates(candidates, env=environment)
    timeout_seconds = _timeout(environment)
    attempts: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []

    for candidate in resolved:
        started = _now_iso()
        status: int | None = None
        document: Any | None = None
        error: str | None = None
        network_error: str | None = None
        try:
            response = _get(candidate["url"], timeout_seconds=timeout_seconds, requester=requester)
            status, document, error = _response_json(response)
        except Exception as exc:
            network_error = type(exc).__name__
            error = "request_failed"

        shape = _document_shape(document)
        wnba_identity = _document_mentions_wnba(document)
        normalized_offers: list[dict[str, Any]] = []
        if document is not None:
            try:
                normalized_offers = normalize_draftkings_document(document, captured_at_utc=started)
            except Exception:
                normalized_offers = []
        stats = sorted({str(row.get("stat")) for row in normalized_offers if row.get("stat")})
        usable = bool(status == 200 and error is None and wnba_identity and normalized_offers)
        attempt = {
            "candidate_id": candidate["candidate_id"],
            "family": candidate["family"],
            "url": candidate["url"],
            "host": (urlparse(candidate["url"]).hostname or "").casefold(),
            "started_at_utc": started,
            "http_status": status,
            "response_error": error,
            "network_error_type": network_error,
            "wnba_identity_verified": wnba_identity,
            "shape": shape,
            "normalized_offer_count": len(normalized_offers),
            "supported_stats": stats,
            "usable_for_step6d": usable,
        }
        attempts.append(attempt)
        if usable:
            verified.append(attempt)

    selected = verified[0] if verified else None
    fingerprint = _hash(
        {
            "wnba_league_id": WNBA_LEAGUE_ID,
            "attempts": attempts,
            "selected_candidate_id": selected.get("candidate_id") if selected else None,
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6e_draftkings_endpoint_probe",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now_iso(),
        "wnba_league_id": WNBA_LEAGUE_ID,
        "wnba_template_id": WNBA_TEMPLATE_ID,
        "live_probe_performed": True,
        "live_endpoint_verified": selected is not None,
        "selected_candidate": selected,
        "verified_candidate_count": len(verified),
        "attempts": attempts,
        "probe_fingerprint_sha256": fingerprint,
        "safety": {
            "http_methods": ["GET"],
            "authentication_used": False,
            "cookies_used": False,
            "wager_action_performed": False,
            "paid_odds_vendor_used": False,
            "step_6d_auto_enabled": False,
        },
    }
