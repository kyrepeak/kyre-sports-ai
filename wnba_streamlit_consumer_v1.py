"""Step 18B — fail-closed Streamlit adapter for the certified WNBA consumer GET.

This module converts the Step-18A API response into a tiny UI-facing state.
It never runs a model, starts a scheduler, talks to a sportsbook, writes a
checkpoint, or caches an old pick. A stale or unavailable snapshot therefore
stays unavailable instead of falling back to legacy on-demand Daily Picks math.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any, Mapping

from wnba_api_client_v1 import KyreWNBAAPIClient, KyreWNBAAPIError

EXPECTED_DATA_TYPE = "wnba_step18a_streamlit_consumer_latest"
EXPECTED_SCHEMA_VERSION = "wnba_step_18a_streamlit_consumer_v1"
MODEL_VERSION = "WNBA STREAMLIT CONSUMER V1 • STEP 18B READ-ONLY LATEST BOARD"
MAX_PRIMARY_CARDS = 20


class WNBAStreamlitConsumerError(RuntimeError):
    """Raised when the hosted consumer contract is malformed."""


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WNBAStreamlitConsumerError(f"{label} must be an object.")
    return deepcopy(dict(value))


def _bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise WNBAStreamlitConsumerError(f"{label} must be boolean.")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise WNBAStreamlitConsumerError(f"{label} must be numeric.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStreamlitConsumerError(f"{label} must be numeric.") from exc
    if not math.isfinite(result):
        raise WNBAStreamlitConsumerError(f"{label} must be finite.")
    return result


def _hex64(value: object, label: str, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise WNBAStreamlitConsumerError(f"{label} must be a SHA-256 digest.")
    return text


def _validate_card(card: object, index: int) -> dict[str, Any]:
    row = _mapping(card, f"primary card {index}")
    if row.get("qualification") != "qualified":
        raise WNBAStreamlitConsumerError("Consumer refuses an unqualified primary card.")
    try:
        display_rank = int(row.get("display_rank"))
    except (TypeError, ValueError) as exc:
        raise WNBAStreamlitConsumerError("Primary card display rank is invalid.") from exc
    if display_rank != index:
        raise WNBAStreamlitConsumerError("Primary card display ranking is not contiguous.")
    player = _mapping(row.get("player"), "card player")
    prop = _mapping(row.get("prop"), "card prop")
    market = _mapping(row.get("market"), "card market")
    model = _mapping(row.get("model"), "card model")
    consensus = _mapping(row.get("consensus"), "card consensus")
    value = _mapping(row.get("value"), "card value")
    if not str(player.get("player_name") or "").strip():
        raise WNBAStreamlitConsumerError("Primary card player name is missing.")
    if str(prop.get("side") or "").casefold() not in {"over", "under"}:
        raise WNBAStreamlitConsumerError("Primary card side is invalid.")
    if str(prop.get("stat") or "").casefold() not in {"points", "rebounds", "assists", "pra"}:
        raise WNBAStreamlitConsumerError("Primary card stat is unsupported.")
    _number(prop.get("line"), "card line")
    probability = _number(model.get("resolved_fair_probability"), "card model probability")
    if not 0.0 <= probability <= 1.0:
        raise WNBAStreamlitConsumerError("Card model probability must be 0..1.")
    if int(model.get("simulations") or 0) != 5_000_000 or model.get("converged") is not True:
        raise WNBAStreamlitConsumerError("Consumer accepts only converged 5M primary cards.")
    _number(consensus.get("no_vig_probability"), "card no-vig probability")
    _number(consensus.get("edge_percentage_points"), "card edge")
    _number(value.get("ev_roi_percentage"), "card EV")
    if not str(market.get("sportsbook") or "").strip():
        raise WNBAStreamlitConsumerError("Primary card sportsbook is missing.")
    return row


def normalize_consumer_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate Step-18A response and map it to one truthful display state."""
    body = _mapping(payload, "consumer response")
    if body.get("data_type") != EXPECTED_DATA_TYPE:
        raise WNBAStreamlitConsumerError("Consumer API data_type drift.")
    if body.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise WNBAStreamlitConsumerError("Consumer API schema drift.")

    enabled = _bool(body.get("enabled"), "consumer enabled")
    available = _bool(body.get("available"), "consumer available")
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise WNBAStreamlitConsumerError("Consumer reason is missing.")
    board = _mapping(body.get("board"), "consumer board")
    snapshot = _mapping(body.get("snapshot"), "consumer snapshot")
    runtime = _mapping(body.get("runtime"), "consumer runtime")
    semantics = _mapping(body.get("semantics"), "consumer semantics")

    if semantics.get("read_only_get") is not True or semantics.get("in_memory_snapshot_only") is not True:
        raise WNBAStreamlitConsumerError("Consumer endpoint no longer attests read-only in-memory semantics.")
    for key in (
        "database_connection_opened",
        "database_read_performed",
        "database_write_performed",
        "scheduler_started",
        "scheduler_cycle_triggered",
        "sportsbook_network_called",
        "projection_run",
        "monte_carlo_run",
        "wager_action_performed",
        "database_secret_exposed",
        "new_render_service_created",
    ):
        if semantics.get(key) is not False:
            raise WNBAStreamlitConsumerError(f"Unsafe consumer semantic drift: {key}.")

    stale = _bool(snapshot.get("stale"), "snapshot stale")
    snapshot_hash = _hex64(snapshot.get("snapshot_content_sha256"), "snapshot hash", allow_none=True)
    board_available = _bool(board.get("available"), "board available")
    cards_raw = board.get("primary_top_cards")
    if not isinstance(cards_raw, list):
        raise WNBAStreamlitConsumerError("Primary top cards must be an array.")
    if len(cards_raw) > MAX_PRIMARY_CARDS:
        raise WNBAStreamlitConsumerError("Primary card count exceeds consumer safety limit.")

    if available != board_available:
        raise WNBAStreamlitConsumerError("Consumer and board availability disagree.")
    if stale and available:
        # The API can expose a stale historical snapshot as available; Streamlit
        # deliberately hides stale cards until a fresh scheduler cycle arrives.
        state = "stale"
    elif not enabled:
        state = "disabled"
    elif snapshot_hash is None:
        state = "waiting"
    elif not available:
        state = "unavailable"
    else:
        state = "ready"

    cards: list[dict[str, Any]] = []
    if state == "ready":
        for index, card in enumerate(cards_raw, start=1):
            cards.append(_validate_card(card, index))
        if not cards:
            raise WNBAStreamlitConsumerError("Available consumer board has no primary cards.")
    # Fail closed: no cards are returned for stale/disabled/waiting/unavailable.

    return {
        "state": state,
        "enabled": enabled,
        "available": state == "ready",
        "reason": reason,
        "slate_date": body.get("slate_date"),
        "health": body.get("health"),
        "cards": cards,
        "board_meta": {
            "requested_top_card_count": board.get("requested_top_card_count"),
            "qualified_prop_count": board.get("qualified_prop_count"),
            "top_card_count": board.get("top_card_count"),
            "full_requested_board_available": board.get("full_requested_board_available"),
        },
        "snapshot": snapshot,
        "runtime": runtime,
    }


def load_latest_daily_picks(client: KyreWNBAAPIClient | None = None) -> dict[str, Any]:
    active = client or KyreWNBAAPIClient()
    try:
        payload = active.consumer_latest()
        return normalize_consumer_payload(payload)
    except (KyreWNBAAPIError, WNBAStreamlitConsumerError) as exc:
        return {
            "state": "error",
            "enabled": True,
            "available": False,
            "reason": "consumer_read_failed",
            "error_type": type(exc).__name__,
            "slate_date": None,
            "health": None,
            "cards": [],
            "board_meta": {},
            "snapshot": {},
            "runtime": {},
        }


__all__ = [
    "EXPECTED_DATA_TYPE",
    "EXPECTED_SCHEMA_VERSION",
    "MODEL_VERSION",
    "WNBAStreamlitConsumerError",
    "load_latest_daily_picks",
    "normalize_consumer_payload",
]
