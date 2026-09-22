"""CFB Over/Under Market Adapter V2 — Step 5A freshness firewall.

Additive wrapper above permanently frozen Market Adapter V1.

V2 does not change projection math or market matching. It adds an independent
consumer-side freshness and identity guard before any sportsbook total can be
attached to a Streamlit schedule row.

The live market remains context/threshold only with 0% projection weight.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_market_adapter_v1 as frozen

MODEL_VERSION = "CFB O/U MARKET ADAPTER V2 • STEP 5A FRESHNESS FIREWALL"
FROZEN_ADAPTER = "cfb_over_under_market_adapter_v1"
API_BASE_ENV = frozen.API_BASE_ENV
API_PATH = frozen.API_PATH
DEFAULT_API_BASE = frozen.DEFAULT_API_BASE
MAX_MARKET_AGE_SECONDS = 300.0
MAX_FUTURE_SKEW_SECONDS = 60.0
_ALLOWED_CURRENT_LINE_STATUS = {"active", "open"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(value: Any, field: str) -> datetime:
    text = _clean(value)
    if not text:
        raise ValueError(f"unsafe_missing_timestamp:{field}")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"unsafe_invalid_timestamp:{field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"unsafe_naive_timestamp:{field}")
    return parsed.astimezone(timezone.utc)


def _age_seconds(
    value: Any,
    *,
    field: str,
    now_utc: datetime,
) -> float:
    parsed = _aware_utc(value, field)
    age = (now_utc - parsed).total_seconds()
    if not math.isfinite(age):
        raise ValueError(f"unsafe_nonfinite_age:{field}")
    if age < -MAX_FUTURE_SKEW_SECONDS:
        raise ValueError(f"unsafe_future_timestamp:{field}")
    return max(0.0, float(age))


def validate_fresh_payload(
    payload: Mapping[str, Any],
    *,
    requested_sportsbook: str,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Validate freshness without changing the frozen Step 4 payload."""
    if not isinstance(payload, Mapping):
        raise ValueError("unsafe_payload_not_mapping")

    now = now_utc or _utc_now()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("unsafe_now_must_be_timezone_aware")
    now = now.astimezone(timezone.utc)

    expected_book = _clean(requested_sportsbook)
    if not expected_book:
        raise ValueError("unsafe_missing_requested_sportsbook")

    captured_age = _age_seconds(
        payload.get("captured_at_utc"),
        field="captured_at_utc",
        now_utc=now,
    )
    if captured_age > MAX_MARKET_AGE_SECONDS:
        raise ValueError(
            f"stale_capture:{captured_age:.3f}>{MAX_MARKET_AGE_SECONDS:.0f}"
        )

    rows = payload.get("games")
    if not isinstance(rows, list):
        raise ValueError("unsafe_games_not_list")

    line_ages: list[float] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("unsafe_malformed_market_row")

        game_id = _clean(row.get("game_id"))
        if not game_id or not game_id.isdigit():
            raise ValueError("unsafe_non_official_event_id")

        sportsbook = _clean(row.get("sportsbook"))
        if sportsbook.casefold() != expected_book.casefold():
            raise ValueError(
                f"unsafe_sportsbook_mismatch:{sportsbook or 'missing'}"
            )

        line_status = _clean(row.get("line_status")).casefold()
        if line_status not in _ALLOWED_CURRENT_LINE_STATUS:
            raise ValueError(
                f"unsafe_noncurrent_line_status:{line_status or 'missing'}"
            )

        line_age = _age_seconds(
            row.get("line_updated_at_utc"),
            field=f"line_updated_at_utc:{game_id}",
            now_utc=now,
        )
        if line_age > MAX_MARKET_AGE_SECONDS:
            raise ValueError(
                f"stale_line:{game_id}:{line_age:.3f}>{MAX_MARKET_AGE_SECONDS:.0f}"
            )
        line_ages.append(line_age)

    return {
        "freshness_status": "FRESH",
        "captured_age_seconds": round(captured_age, 3),
        "max_line_age_seconds": round(max(line_ages, default=captured_age), 3),
        "max_allowed_age_seconds": MAX_MARKET_AGE_SECONDS,
        "future_skew_tolerance_seconds": MAX_FUTURE_SKEW_SECONDS,
        "sportsbook_identity_verified": True,
        "official_event_ids_numeric": True,
        "current_line_status_verified": True,
        "rows_verified": len(rows),
        "projection_weight": 0.0,
        "market_context_only": True,
        "may_modify_projection": False,
    }


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


@st.cache_data(ttl=60, show_spinner=False)
def load_odds_for_date(
    target_date: Any,
    sportsbook: str = "FanDuel",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load frozen V1 odds, then independently reject stale/unsafe context."""
    book = _clean(sportsbook) or "FanDuel"
    payload, diag = frozen.load_odds_for_date(target_date, book)
    base_diag = dict(diag or {})

    if _clean(base_diag.get("status")) != "GREEN":
        base_diag.update(
            {
                "version": MODEL_VERSION,
                "freshness_status": "UNAVAILABLE",
                "max_allowed_age_seconds": MAX_MARKET_AGE_SECONDS,
                "projection_weight": 0.0,
                "market_context_only": True,
                "may_modify_projection": False,
            }
        )
        return payload, base_diag

    try:
        freshness = validate_fresh_payload(
            payload,
            requested_sportsbook=book,
            now_utc=_utc_now(),
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:300]
        reason = _clean(exc)
        state = "STALE" if reason.startswith("stale_") else "UNSAFE"
        return _empty_safe_payload(payload), {
            **base_diag,
            "status": state,
            "version": MODEL_VERSION,
            "freshness_status": state,
            "game_count": 0,
            "identity_verified_rows": 0,
            "max_allowed_age_seconds": MAX_MARKET_AGE_SECONDS,
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
            "error": error,
        }

    return payload, {
        **base_diag,
        **freshness,
        "status": "GREEN",
        "version": MODEL_VERSION,
        "error": "",
    }


# Frozen V1 owns official ESPN event-ID-only attachment. V2 only gates whether
# a payload is fresh/safe enough to reach that already-frozen attachment path.
attach_market_lines = frozen.attach_market_lines
market_line = frozen.market_line


def clear_market_cache() -> None:
    try:
        load_odds_for_date.clear()
    except Exception:
        pass
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
    "attach_market_lines",
    "clear_market_cache",
    "load_odds_for_date",
    "market_line",
    "validate_fresh_payload",
]
