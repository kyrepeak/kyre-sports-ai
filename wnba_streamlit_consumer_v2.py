"""Step 18C reliability adapter for the certified WNBA consumer GET."""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping

from wnba_api_client_v1 import KyreWNBAAPIClient, KyreWNBAAPIError
import wnba_streamlit_consumer_v1 as v1

MODEL_VERSION = "WNBA STREAMLIT CONSUMER V2 • STEP 18C RELIABILITY"
EXPECTED_STEP17D_SHA = "8448984adc779fb9af7c7a8187b0eaeb67d034c8"
READ_TIMEOUT_SECONDS = 20.0
READ_ATTEMPTS = 3


class WNBAStreamlitConsumerReliabilityError(RuntimeError):
    pass


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WNBAStreamlitConsumerReliabilityError(f"{label} must be an object.")
    return deepcopy(dict(value))


def _number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise WNBAStreamlitConsumerReliabilityError(f"{label} must be numeric.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStreamlitConsumerReliabilityError(f"{label} must be numeric.") from exc
    if not math.isfinite(result):
        raise WNBAStreamlitConsumerReliabilityError(f"{label} must be finite.")
    return result


def _hex64(value: object, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise WNBAStreamlitConsumerReliabilityError(f"{label} must be a SHA-256 digest.")
    return text


def normalize_consumer_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    body = _mapping(payload, "consumer response")
    snapshot = _mapping(body.get("snapshot"), "consumer snapshot")
    board = _mapping(body.get("board"), "consumer board")
    lineage = _mapping(body.get("lineage"), "consumer lineage")
    effective_stale = bool(snapshot.get("stale"))
    snapshot_hash = snapshot.get("snapshot_content_sha256")

    if snapshot_hash is not None:
        _hex64(snapshot_hash, "snapshot hash")
        age = _number(snapshot.get("age_seconds"), "snapshot age")
        threshold = _number(snapshot.get("stale_after_seconds"), "snapshot stale threshold")
        if age < 0.0 or not 30.0 <= threshold <= 900.0:
            raise WNBAStreamlitConsumerReliabilityError("Snapshot freshness metadata is outside the certified range.")
        effective_stale = effective_stale or age > threshold + 1.0
        if lineage.get("step17d_frozen_runtime_sha") != EXPECTED_STEP17D_SHA:
            raise WNBAStreamlitConsumerReliabilityError("Consumer Step-17D lineage drift.")
        _hex64(lineage.get("source_step13c_reliability_content_sha256"), "Step-13C source hash")
        _hex64(lineage.get("source_step13a_scheduler_content_sha256"), "Step-13A source hash")

    cards = board.get("primary_top_cards")
    if not isinstance(cards, list):
        raise WNBAStreamlitConsumerReliabilityError("Primary cards must be an array.")
    if board.get("top_n_forced") is not False:
        raise WNBAStreamlitConsumerReliabilityError("Forced or padded top-N board refused.")
    available = board.get("available")
    if not isinstance(available, bool):
        raise WNBAStreamlitConsumerReliabilityError("Board availability must be boolean.")
    if available:
        try:
            displayed = int(board.get("top_card_count"))
            qualified = int(board.get("qualified_prop_count"))
        except (TypeError, ValueError) as exc:
            raise WNBAStreamlitConsumerReliabilityError("Available board counts are invalid.") from exc
        if displayed != len(cards) or displayed <= 0 or qualified < displayed:
            raise WNBAStreamlitConsumerReliabilityError("Available board count identity is inconsistent.")
    elif cards or board.get("top_card_count") not in {None, 0}:
        raise WNBAStreamlitConsumerReliabilityError("Unavailable board leaked displayed cards.")

    adjusted = deepcopy(body)
    adjusted["snapshot"]["stale"] = effective_stale
    view = v1.normalize_consumer_payload(adjusted)
    if view.get("state") != "ready" and view.get("cards"):
        raise WNBAStreamlitConsumerReliabilityError("Non-ready state leaked cards.")
    view["snapshot"]["effective_stale"] = effective_stale
    view["read_policy"] = {
        "timeout_seconds": READ_TIMEOUT_SECONDS,
        "attempts": READ_ATTEMPTS,
        "render_free_cold_start_aware": True,
    }
    return view


def load_latest_daily_picks(client: KyreWNBAAPIClient | None = None) -> dict[str, Any]:
    active = client or KyreWNBAAPIClient(timeout_seconds=READ_TIMEOUT_SECONDS, attempts=READ_ATTEMPTS)
    try:
        return normalize_consumer_payload(active.consumer_latest())
    except (KyreWNBAAPIError, v1.WNBAStreamlitConsumerError, WNBAStreamlitConsumerReliabilityError) as exc:
        return {
            "state": "error", "enabled": True, "available": False,
            "reason": "consumer_read_failed", "error_type": type(exc).__name__,
            "slate_date": None, "health": None, "cards": [], "board_meta": {},
            "snapshot": {}, "runtime": {},
            "read_policy": {"timeout_seconds": READ_TIMEOUT_SECONDS, "attempts": READ_ATTEMPTS, "render_free_cold_start_aware": True},
        }


__all__ = ["EXPECTED_STEP17D_SHA", "MODEL_VERSION", "READ_ATTEMPTS", "READ_TIMEOUT_SECONDS", "WNBAStreamlitConsumerReliabilityError", "load_latest_daily_picks", "normalize_consumer_payload"]
