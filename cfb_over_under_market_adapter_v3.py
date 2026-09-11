"""CFB Over/Under Market Adapter V3 — freshness-safe snapshot reuse.

Additive performance wrapper above certified Market Adapter V2.

V3 reduces repeated live-odds waits during an active Streamlit session by
reusing a successful V2 market snapshot for up to 240 seconds. The cached
snapshot is *not* trusted blindly: V2's 300-second freshness/identity firewall
is re-run on every public access. If a cached snapshot becomes stale or unsafe,
V3 clears its snapshot cache, forces one refresh through V2, and fails closed if
the refreshed payload is still unavailable/stale/unsafe.

Projection math and market attachment remain unchanged. Sportsbook data stays
context/threshold only with exactly 0.0% projection influence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_market_adapter_v2 as frozen

MODEL_VERSION = "CFB O/U MARKET ADAPTER V3 • FRESHNESS-SAFE SNAPSHOT REUSE"
FROZEN_ADAPTER = "cfb_over_under_market_adapter_v2"
API_BASE_ENV = frozen.API_BASE_ENV
API_PATH = frozen.API_PATH
DEFAULT_API_BASE = frozen.DEFAULT_API_BASE
MAX_MARKET_AGE_SECONDS = frozen.MAX_MARKET_AGE_SECONDS
MAX_FUTURE_SKEW_SECONDS = frozen.MAX_FUTURE_SKEW_SECONDS
SNAPSHOT_CACHE_TTL_SECONDS = 240.0


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _empty_safe_payload(source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = source if isinstance(source, Mapping) else {}
    return {
        "step": 3,
        "schema_version": "cfb_odds_v1",
        "captured_at_utc": _clean(source.get("captured_at_utc")),
        "source": _clean(source.get("source")),
        "game_count": 0,
        "games": [],
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
        "diagnostics": dict(source.get("diagnostics") or {}),
    }


@st.cache_data(ttl=SNAPSHOT_CACHE_TTL_SECONDS, show_spinner=False)
def _load_market_snapshot(
    target_date: Any,
    sportsbook: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reuse only the certified V2 result; no market semantics are changed."""
    return frozen.load_odds_for_date(target_date, sportsbook)


def _clear_snapshot_cache() -> None:
    try:
        _load_market_snapshot.clear()
    except Exception:
        pass


def _safe_diag(
    base_diag: Mapping[str, Any] | None,
    *,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    return {
        **dict(base_diag or {}),
        "status": status,
        "version": MODEL_VERSION,
        "freshness_status": status,
        "snapshot_cache_ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS,
        "freshness_revalidated_on_access": True,
        "game_count": 0,
        "identity_verified_rows": 0,
        "max_allowed_age_seconds": MAX_MARKET_AGE_SECONDS,
        "projection_weight": 0.0,
        "market_context_only": True,
        "may_modify_projection": False,
        "error": error,
    }


def _validate_access(
    payload: Mapping[str, Any],
    *,
    sportsbook: str,
) -> dict[str, Any]:
    return frozen.validate_fresh_payload(
        payload,
        requested_sportsbook=sportsbook,
        now_utc=_utc_now(),
    )


def load_odds_for_date(
    target_date: Any,
    sportsbook: str = "FanDuel",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load a cached V2 snapshot while rechecking freshness every access.

    Successful snapshots can avoid repeated network waits for up to 240 seconds.
    A stale/unsafe cached snapshot is never returned to the page: V3 clears the
    snapshot cache, attempts one certified V2 refresh, then fails closed.
    """
    book = _clean(sportsbook) or "FanDuel"
    payload, diag = _load_market_snapshot(target_date, book)
    base_diag = dict(diag or {})

    if _clean(base_diag.get("status")) != "GREEN":
        # Do not intentionally retain an unavailable/unsafe snapshot at the V3
        # layer. V2 still owns its short failure/cache behavior.
        _clear_snapshot_cache()
        status = _clean(base_diag.get("status")) or "UNAVAILABLE"
        return payload, {
            **base_diag,
            "version": MODEL_VERSION,
            "freshness_status": _clean(base_diag.get("freshness_status")) or status,
            "snapshot_cache_ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS,
            "freshness_revalidated_on_access": True,
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        }

    try:
        freshness = _validate_access(payload, sportsbook=book)
    except Exception:
        # The cached snapshot may have aged past the freshness firewall before
        # its 240-second cache TTL. Force one refresh rather than serving it.
        _clear_snapshot_cache()
        payload, diag = _load_market_snapshot(target_date, book)
        base_diag = dict(diag or {})
        if _clean(base_diag.get("status")) != "GREEN":
            _clear_snapshot_cache()
            status = _clean(base_diag.get("status")) or "UNAVAILABLE"
            return payload, {
                **base_diag,
                "version": MODEL_VERSION,
                "freshness_status": _clean(base_diag.get("freshness_status")) or status,
                "snapshot_cache_ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS,
                "freshness_revalidated_on_access": True,
                "projection_weight": 0.0,
                "market_context_only": True,
                "may_modify_projection": False,
            }
        try:
            freshness = _validate_access(payload, sportsbook=book)
        except Exception as exc:
            _clear_snapshot_cache()
            reason = _clean(exc)
            state = "STALE" if reason.startswith("stale_") else "UNSAFE"
            error = f"{type(exc).__name__}: {exc}"[:300]
            return _empty_safe_payload(payload), _safe_diag(
                base_diag,
                status=state,
                error=error,
            )

    return payload, {
        **base_diag,
        **freshness,
        "status": "GREEN",
        "version": MODEL_VERSION,
        "snapshot_cache_ttl_seconds": SNAPSHOT_CACHE_TTL_SECONDS,
        "freshness_revalidated_on_access": True,
        "error": "",
    }


# Certified V2/V1 own official ESPN event-ID-only attachment. V3 changes only
# successful snapshot reuse frequency before that unchanged attachment path.
attach_market_lines = frozen.attach_market_lines
market_line = frozen.market_line
validate_fresh_payload = frozen.validate_fresh_payload


def clear_market_cache() -> None:
    _clear_snapshot_cache()
    try:
        frozen.clear_market_cache()
    except Exception:
        pass


__all__ = [
    "API_BASE_ENV",
    "API_PATH",
    "DEFAULT_API_BASE",
    "FROZEN_ADAPTER",
    "MAX_FUTURE_SKEW_SECONDS",
    "MAX_MARKET_AGE_SECONDS",
    "MODEL_VERSION",
    "SNAPSHOT_CACHE_TTL_SECONDS",
    "attach_market_lines",
    "clear_market_cache",
    "load_odds_for_date",
    "market_line",
    "validate_fresh_payload",
]
