"""Step 19A: fail-closed verifier for the certified WNBA /consumer/latest GET.

The verifier is deliberately read-only.  It validates the real Step-18A consumer
response shape and refuses stale, degraded, unavailable, one-book, or otherwise
unsafe snapshots.  It does not start a scheduler, call a sportsbook, run a model,
open a database connection, write persistence, or place a wager.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
from typing import Any, Mapping

EXPECTED_DATA_TYPE = "wnba_step18a_streamlit_consumer_latest"
EXPECTED_SCHEMA_VERSION = "wnba_step_18a_streamlit_consumer_v1"
MODEL_VERSION = "wnba_step19a_consumer_latest_fail_closed_verifier_v1"
CERTIFIED_SIMULATIONS = 5_000_000
MIN_BOOKS_AT_EXACT_LINE = 2
MAX_STALE_AFTER_SECONDS = 900.0
MIN_STALE_AFTER_SECONDS = 30.0
STALE_TOLERANCE_SECONDS = 1.0

_SAFE_FALSE_SEMANTICS = (
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
)


class WNBAStep19AConsumerVerificationError(RuntimeError):
    """Raised when /consumer/latest is not a genuinely healthy current snapshot."""


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WNBAStep19AConsumerVerificationError(f"{label} must be an object.")
    return deepcopy(dict(value))


def _bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise WNBAStep19AConsumerVerificationError(f"{label} must be boolean.")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise WNBAStep19AConsumerVerificationError(f"{label} must be numeric.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep19AConsumerVerificationError(f"{label} must be numeric.") from exc
    if not math.isfinite(result):
        raise WNBAStep19AConsumerVerificationError(f"{label} must be finite.")
    return result


def _hex64(value: object, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise WNBAStep19AConsumerVerificationError(f"{label} must be a SHA-256 digest.")
    return text


def _utc(value: object, label: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise WNBAStep19AConsumerVerificationError(
            f"{label} must be timezone-aware ISO-8601."
        ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBAStep19AConsumerVerificationError(
            f"{label} must include a timezone offset."
        )
    return result.astimezone(timezone.utc)


def _validate_semantics(body: Mapping[str, Any]) -> None:
    semantics = _mapping(body.get("semantics"), "consumer semantics")
    if semantics.get("read_only_get") is not True:
        raise WNBAStep19AConsumerVerificationError(
            "Consumer endpoint no longer attests read-only GET semantics."
        )
    if semantics.get("in_memory_snapshot_only") is not True:
        raise WNBAStep19AConsumerVerificationError(
            "Consumer endpoint no longer attests in-memory snapshot-only semantics."
        )
    for key in _SAFE_FALSE_SEMANTICS:
        if semantics.get(key) is not False:
            raise WNBAStep19AConsumerVerificationError(
                f"Unsafe consumer semantic drift: {key}."
            )


def _validate_runtime(runtime: Mapping[str, Any]) -> None:
    # Step-18A originally exposed only next_refresh_due_at_utc here.  Newer
    # deployments may expose richer scheduler state.  When a readiness field is
    # present it must agree with a healthy, recovered, closed-circuit snapshot.
    health = runtime.get("health")
    if health is not None and str(health).strip().casefold() != "healthy":
        raise WNBAStep19AConsumerVerificationError(
            f"Consumer runtime health is not healthy: {health!r}."
        )
    status = runtime.get("status")
    if status is not None and str(status).strip().casefold() not in {
        "healthy",
        "half_open_recovered",
    }:
        raise WNBAStep19AConsumerVerificationError(
            f"Consumer runtime status is not ready: {status!r}."
        )
    outcome = runtime.get("cycle_outcome")
    if outcome is not None and str(outcome).strip() != "shadow_board_ready":
        raise WNBAStep19AConsumerVerificationError(
            f"Consumer runtime cycle outcome is not ready: {outcome!r}."
        )
    circuit = runtime.get("circuit_state")
    if circuit is not None and str(circuit).strip().casefold() != "closed":
        raise WNBAStep19AConsumerVerificationError(
            f"Consumer runtime circuit is not closed: {circuit!r}."
        )
    next_due = runtime.get("next_refresh_due_at_utc")
    if next_due is not None:
        _utc(next_due, "runtime next_refresh_due_at_utc")


def _validate_card(card: object, index: int) -> tuple[dict[str, Any], int, str]:
    row = _mapping(card, f"primary card {index}")
    if row.get("qualification") != "qualified":
        raise WNBAStep19AConsumerVerificationError(
            f"Primary card {index} is not qualified."
        )
    try:
        display_rank = int(row.get("display_rank"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep19AConsumerVerificationError(
            f"Primary card {index} display_rank is invalid."
        ) from exc
    if display_rank != index:
        raise WNBAStep19AConsumerVerificationError(
            "Primary card display ranking is not contiguous."
        )

    prop = _mapping(row.get("prop"), f"primary card {index} prop")
    stat = str(prop.get("stat") or "").strip().casefold()
    if stat not in {"points", "rebounds", "assists", "pra"}:
        raise WNBAStep19AConsumerVerificationError(
            f"Primary card {index} stat is unsupported."
        )
    if str(prop.get("side") or "").strip().casefold() not in {"over", "under"}:
        raise WNBAStep19AConsumerVerificationError(
            f"Primary card {index} side is invalid."
        )
    _number(prop.get("line"), f"primary card {index} line")

    model = _mapping(row.get("model"), f"primary card {index} model")
    if int(model.get("simulations") or 0) != CERTIFIED_SIMULATIONS:
        raise WNBAStep19AConsumerVerificationError(
            f"Primary card {index} does not use certified 5M simulations."
        )
    if model.get("converged") is not True:
        raise WNBAStep19AConsumerVerificationError(
            f"Primary card {index} simulation did not converge."
        )
    probability = _number(
        model.get("resolved_fair_probability"),
        f"primary card {index} fair probability",
    )
    if not 0.0 <= probability <= 1.0:
        raise WNBAStep19AConsumerVerificationError(
            f"Primary card {index} fair probability is outside 0..1."
        )

    consensus = _mapping(row.get("consensus"), f"primary card {index} consensus")
    try:
        book_count = int(consensus.get("book_count_at_exact_line"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep19AConsumerVerificationError(
            f"Primary card {index} exact-line book count is invalid."
        ) from exc
    if book_count < MIN_BOOKS_AT_EXACT_LINE:
        raise WNBAStep19AConsumerVerificationError(
            f"Primary card {index} violates the two-sportsbook exact-line requirement."
        )

    market = _mapping(row.get("market"), f"primary card {index} market")
    sportsbook = str(market.get("sportsbook") or "").strip()
    if not sportsbook:
        raise WNBAStep19AConsumerVerificationError(
            f"Primary card {index} sportsbook is missing."
        )
    return row, book_count, stat


def verify_consumer_latest(
    payload: Mapping[str, Any],
    *,
    evaluated_at: datetime | str | None = None,
    expected_slate_date: str | None = None,
) -> dict[str, Any]:
    """Verify that the real Step-18A consumer response is healthy and ready.

    HTTP 200 alone is intentionally insufficient.  A successful verification
    requires an enabled, available, fresh, non-degraded, closed-circuit board
    with internally consistent counts, safe GET semantics, converged 5M cards,
    and at least two sportsbooks at each card's exact line.
    """
    body = _mapping(payload, "consumer response")
    if body.get("data_type") != EXPECTED_DATA_TYPE:
        raise WNBAStep19AConsumerVerificationError("Consumer API data_type drift.")
    if body.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise WNBAStep19AConsumerVerificationError("Consumer API schema drift.")

    if _bool(body.get("enabled"), "consumer enabled") is not True:
        raise WNBAStep19AConsumerVerificationError("Consumer endpoint is disabled.")
    if _bool(body.get("available"), "consumer available") is not True:
        raise WNBAStep19AConsumerVerificationError("Consumer snapshot is unavailable.")

    reason = str(body.get("reason") or "").strip()
    if reason != "board_ready":
        raise WNBAStep19AConsumerVerificationError(
            f"Consumer snapshot reason is not board_ready: {reason!r}."
        )
    if str(body.get("health") or "").strip().casefold() != "healthy":
        raise WNBAStep19AConsumerVerificationError(
            f"Consumer health is not healthy: {body.get('health')!r}."
        )

    slate_date = str(body.get("slate_date") or "").strip()
    if not slate_date:
        raise WNBAStep19AConsumerVerificationError("Consumer slate_date is missing.")
    if expected_slate_date is not None and slate_date != str(expected_slate_date):
        raise WNBAStep19AConsumerVerificationError(
            f"Consumer slate mismatch: expected {expected_slate_date}, received {slate_date}."
        )

    _validate_semantics(body)

    snapshot = _mapping(body.get("snapshot"), "consumer snapshot")
    if _bool(snapshot.get("stale"), "snapshot stale") is True:
        raise WNBAStep19AConsumerVerificationError("Consumer snapshot is stale.")
    snapshot_hash = _hex64(snapshot.get("snapshot_content_sha256"), "snapshot hash")
    captured_at = _utc(snapshot.get("captured_at_utc"), "snapshot captured_at_utc")
    age = _number(snapshot.get("age_seconds"), "snapshot age_seconds")
    threshold = _number(
        snapshot.get("stale_after_seconds"), "snapshot stale_after_seconds"
    )
    if age < 0.0:
        raise WNBAStep19AConsumerVerificationError("Snapshot age cannot be negative.")
    if not MIN_STALE_AFTER_SECONDS <= threshold <= MAX_STALE_AFTER_SECONDS:
        raise WNBAStep19AConsumerVerificationError(
            "Snapshot stale threshold is outside the certified 30..900 second range."
        )
    if age > threshold + STALE_TOLERANCE_SECONDS:
        raise WNBAStep19AConsumerVerificationError(
            "Consumer snapshot is effectively stale even though stale=false."
        )

    if evaluated_at is not None:
        evaluated = (
            evaluated_at.astimezone(timezone.utc)
            if isinstance(evaluated_at, datetime) and evaluated_at.tzinfo is not None
            else _utc(evaluated_at, "evaluated_at")
        )
        if isinstance(evaluated_at, datetime) and (
            evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None
        ):
            raise WNBAStep19AConsumerVerificationError(
                "evaluated_at must include a timezone offset."
            )
        if captured_at > evaluated + __import__("datetime").timedelta(seconds=5):
            raise WNBAStep19AConsumerVerificationError(
                "Consumer snapshot capture time is implausibly in the future."
            )

    board = _mapping(body.get("board"), "consumer board")
    if _bool(board.get("available"), "board available") is not True:
        raise WNBAStep19AConsumerVerificationError(
            "Consumer says available but nested board is unavailable."
        )
    if board.get("top_n_forced") is not False:
        raise WNBAStep19AConsumerVerificationError(
            "Forced or padded top-N consumer board refused."
        )
    cards = board.get("primary_top_cards")
    if not isinstance(cards, list):
        raise WNBAStep19AConsumerVerificationError(
            "Primary top cards must be an array."
        )
    try:
        displayed = int(board.get("top_card_count"))
        qualified = int(board.get("qualified_prop_count"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep19AConsumerVerificationError(
            "Consumer board counts are invalid."
        ) from exc
    if displayed <= 0 or displayed != len(cards) or qualified < displayed:
        raise WNBAStep19AConsumerVerificationError(
            "Ready consumer board count identity is inconsistent."
        )

    validated_cards: list[dict[str, Any]] = []
    exact_line_book_counts: list[int] = []
    stats: set[str] = set()
    sportsbooks: set[str] = set()
    for index, card in enumerate(cards, start=1):
        row, book_count, stat = _validate_card(card, index)
        validated_cards.append(row)
        exact_line_book_counts.append(book_count)
        stats.add(stat)
        sportsbooks.add(str((row.get("market") or {}).get("sportsbook") or "").strip())

    runtime = _mapping(body.get("runtime"), "consumer runtime")
    _validate_runtime(runtime)

    lineage = body.get("lineage")
    if lineage is not None:
        lineage_map = _mapping(lineage, "consumer lineage")
        for key, value in lineage_map.items():
            if key.endswith(("_sha256", "_content_sha256")) and value is not None:
                _hex64(value, f"consumer lineage {key}")

    return {
        "data_type": "wnba_step19a_consumer_verification",
        "model_version": MODEL_VERSION,
        "ready": True,
        "health": "healthy",
        "reason": "board_ready",
        "slate_date": slate_date,
        "snapshot_content_sha256": snapshot_hash,
        "snapshot_captured_at_utc": captured_at.isoformat(),
        "snapshot_age_seconds": age,
        "snapshot_stale_after_seconds": threshold,
        "top_card_count": displayed,
        "qualified_prop_count": qualified,
        "minimum_exact_line_book_count": min(exact_line_book_counts),
        "stats": sorted(stats),
        "selected_sportsbooks": sorted(sportsbooks),
        "read_only": True,
        "production_or_write_action_performed": False,
    }


__all__ = [
    "CERTIFIED_SIMULATIONS",
    "EXPECTED_DATA_TYPE",
    "EXPECTED_SCHEMA_VERSION",
    "MIN_BOOKS_AT_EXACT_LINE",
    "MODEL_VERSION",
    "WNBAStep19AConsumerVerificationError",
    "verify_consumer_latest",
]
