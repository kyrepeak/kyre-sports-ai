"""WNBA Step 12C: consumer-ready live board runtime over frozen Step 12B.

Step 12B owns live sportsbook discovery, official identity reconciliation,
market-driven Step-8 assembly, five-million-draw Monte Carlo, and the frozen
Step-9/10/11/12A analytical chain. Step 12C does not change any of that math.

This layer calls exactly one Step-12B job and renders its already-qualified
Step-9 decisions into a compact application-facing board contract. It preserves
frozen ranking order and surfaces player identity, selected side/line/book/price,
model probability, fair odds, no-vig market probability, edge, EV, consensus,
quote freshness, 5M convergence, controller/circuit status, and next-refresh
state.

Step 12C remains default-OFF, caller-driven, shadow-only, and read-only. It does
not start a scheduler, persist state, mutate Supabase, expose a public FastAPI
route, authenticate to a sportsbook, use cookies, or perform a wager.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from typing import Any

from sports_api import wnba_step12b_live_runtime_assembly as step12b

SOURCE = "Kyre Sports API WNBA Step 12C consumer live board runtime"
SCHEMA_VERSION = "wnba_step_12c_live_board_runtime_v1"
REQUEST_SCHEMA_VERSION = "wnba_step_12c_live_board_request_v1"
MODEL_VERSION = "wnba_step12c_frozen_ranked_board_presentation_2026_regular_v1"
STEP12B_FROZEN_SHA = "a109be6116fde66e6857d6c676c0f08790a334f3"
STEP12C_LIVE_BOARD_RUNTIME_ENABLED_ENV = "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED"

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
BACKGROUND_SCHEDULER_ALLOWED = False
PERSISTENCE_ALLOWED = False
SUPABASE_WRITE_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
WAGERING_ALLOWED = False

CERTIFIED_SIMULATIONS = step12b.CERTIFIED_SIMULATIONS
CERTIFIED_BATCH_SIZE = step12b.CERTIFIED_BATCH_SIZE
MAX_BOARD_CARDS = 20
_LINE_TOLERANCE = 1e-9

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)

_REQUEST_REQUIRED_FIELDS = {
    "data_type",
    "schema_version",
    "season",
    "slate_date",
}
_REQUEST_OPTIONAL_FIELDS = {
    "evaluated_at_utc",
    "previous_state",
    "controller_policy",
    "refresh_policy",
    "qualification_policy",
    "request_content_sha256",
}

_STAT_LABELS = {
    "points": "Points",
    "rebounds": "Rebounds",
    "assists": "Assists",
    "pra": "PRA",
}


class WNBAStep12LiveBoardDisabledError(RuntimeError):
    """Raised when Step 12C is not isolated behind its required safety gates."""


class WNBAStep12LiveBoardInputError(ValueError):
    """Raised when the Step-12C request is malformed."""


class WNBAStep12LiveBoardIntegrityError(ValueError):
    """Raised when frozen Step-12B/Step-9/Step-10 evidence is malformed or drifted."""


class WNBAStep12LiveBoardNotReadyError(RuntimeError):
    """Raised when a supposedly healthy Step-12B cycle cannot expose a safe board."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step12c_live_board_runtime_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP12C_LIVE_BOARD_RUNTIME_ENABLED_ENV))


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _valid_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step12c_live_board_runtime_enabled(source):
        raise WNBAStep12LiveBoardDisabledError(
            f"Step 12C requires {STEP12C_LIVE_BOARD_RUNTIME_ENABLED_ENV}=true."
        )
    if not step12b.step12b_live_runtime_assembly_enabled(source):
        raise WNBAStep12LiveBoardDisabledError(
            "Step 12C requires the frozen Step-12B live-runtime gate."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep12LiveBoardDisabledError(
            "Step 12C refuses production/scheduler/persistence/write switches: "
            + ", ".join(bad)
        )
    constants = {
        "step12c_default": DEFAULT_ENABLED,
        "step12c_production": PRODUCTION_ACTIVATION_ALLOWED,
        "step12c_scheduler": BACKGROUND_SCHEDULER_ALLOWED,
        "step12c_persistence": PERSISTENCE_ALLOWED,
        "step12c_supabase": SUPABASE_WRITE_ALLOWED,
        "step12c_public_api": PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step12c_wagering": WAGERING_ALLOWED,
        "step12b_default": step12b.DEFAULT_ENABLED,
        "step12b_production": step12b.PRODUCTION_ACTIVATION_ALLOWED,
        "step12b_scheduler": step12b.BACKGROUND_SCHEDULER_ALLOWED,
        "step12b_persistence": step12b.PERSISTENCE_ALLOWED,
        "step12b_supabase": step12b.SUPABASE_WRITE_ALLOWED,
        "step12b_public_api": step12b.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step12b_wagering": step12b.WAGERING_ALLOWED,
    }
    drift = [name for name, value in constants.items() if value is not False]
    if drift:
        raise WNBAStep12LiveBoardDisabledError(
            "Step 12C safety constant drift: " + ", ".join(drift)
        )
    if step12b.STEP12A_FROZEN_SHA != "4523abb8b230e8e29d9f9d298232dfb8948fc883":
        raise WNBAStep12LiveBoardDisabledError("Step 12B frozen Step-12A lineage drift.")


def _strict_season(value: Any) -> int:
    if isinstance(value, bool):
        raise WNBAStep12LiveBoardInputError("Step 12C season must be integer 2026.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep12LiveBoardInputError("Step 12C season must be integer 2026.") from exc
    if result != 2026:
        raise WNBAStep12LiveBoardInputError(
            "Step 12C is certified for the 2026 Regular Season only."
        )
    return result


def _strict_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise WNBAStep12LiveBoardInputError(
            "Step 12C slate_date must be YYYY-MM-DD."
        ) from exc
    if parsed.isoformat() != text:
        raise WNBAStep12LiveBoardInputError(
            "Step 12C slate_date must be canonical YYYY-MM-DD."
        )
    return text


def _utc(value: Any, label: str, *, default_now: bool = False) -> datetime:
    if value is None and default_now:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise WNBAStep12LiveBoardInputError(
                f"Step 12C {label} must be timezone-aware ISO-8601."
            ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WNBAStep12LiveBoardInputError(
            f"Step 12C {label} must include a timezone offset."
        )
    return parsed.astimezone(timezone.utc)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise WNBAStep12LiveBoardIntegrityError(f"Step 12C {label} must be numeric.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep12LiveBoardIntegrityError(
            f"Step 12C {label} must be numeric."
        ) from exc
    if not math.isfinite(result):
        raise WNBAStep12LiveBoardIntegrityError(f"Step 12C {label} must be finite.")
    return result


def _probability(value: Any, label: str) -> float:
    result = _number(value, label)
    if not 0.0 <= result <= 1.0:
        raise WNBAStep12LiveBoardIntegrityError(
            f"Step 12C {label} must be a probability from 0 through 1."
        )
    return result


def _request_surface(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in request.items()
        if key != "request_content_sha256"
    }


def build_step12c_request(
    *,
    season: int,
    slate_date: str,
    evaluated_at: datetime | str | None = None,
    previous_state: Mapping[str, Any] | None = None,
    controller_policy: Mapping[str, Any] | None = None,
    refresh_policy: Mapping[str, Any] | None = None,
    qualification_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request = {
        "data_type": "wnba_step12c_live_board_request",
        "schema_version": REQUEST_SCHEMA_VERSION,
        "season": _strict_season(season),
        "slate_date": _strict_date(slate_date),
        "evaluated_at_utc": _utc(
            evaluated_at, "evaluated_at", default_now=True
        ).isoformat(),
        "previous_state": None if previous_state is None else deepcopy(dict(previous_state)),
        "controller_policy": dict(controller_policy or {}),
        "refresh_policy": dict(refresh_policy or {}),
        "qualification_policy": dict(qualification_policy or {}),
    }
    request["request_content_sha256"] = _canonical_hash(request)
    return request


def _validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise WNBAStep12LiveBoardInputError("Step 12C request must be an object.")
    keys = set(request)
    unknown = sorted(keys - _REQUEST_REQUIRED_FIELDS - _REQUEST_OPTIONAL_FIELDS)
    missing = sorted(_REQUEST_REQUIRED_FIELDS - keys)
    if unknown:
        raise WNBAStep12LiveBoardInputError(
            "Unknown Step-12C request fields: " + ", ".join(unknown)
        )
    if missing:
        raise WNBAStep12LiveBoardInputError(
            "Missing Step-12C request fields: " + ", ".join(missing)
        )
    if request.get("data_type") != "wnba_step12c_live_board_request":
        raise WNBAStep12LiveBoardInputError("Step 12C request data_type drift.")
    if request.get("schema_version") != REQUEST_SCHEMA_VERSION:
        raise WNBAStep12LiveBoardInputError("Step 12C request schema_version drift.")
    season = _strict_season(request.get("season"))
    slate = _strict_date(request.get("slate_date"))
    evaluated = _utc(request.get("evaluated_at_utc"), "evaluated_at", default_now=True)
    for label in ("controller_policy", "refresh_policy", "qualification_policy"):
        value = request.get(label) or {}
        if not isinstance(value, Mapping):
            raise WNBAStep12LiveBoardInputError(f"Step 12C {label} must be an object.")
    previous = request.get("previous_state")
    if previous is not None and not isinstance(previous, Mapping):
        raise WNBAStep12LiveBoardInputError("Step 12C previous_state must be an object or null.")
    observed = str(request.get("request_content_sha256") or "").strip().lower()
    expected = _canonical_hash(_request_surface(request))
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep12LiveBoardIntegrityError(
            "Step 12C request content hash mismatch."
        )
    return {
        "season": season,
        "slate_date": slate,
        "evaluated_at": evaluated,
        "previous_state": None if previous is None else deepcopy(dict(previous)),
        "controller_policy": dict(request.get("controller_policy") or {}),
        "refresh_policy": dict(request.get("refresh_policy") or {}),
        "qualification_policy": dict(request.get("qualification_policy") or {}),
        "request_content_sha256": observed,
    }


def _step12b_hash_surface(result: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "data_type",
        "schema_version",
        "request_content_sha256",
        "status",
        "health",
        "slate_date",
        "provider_discovery",
        "market_overlap",
        "projection_assembly",
        "runtime_summary",
        "lineage",
        "guardrails",
    )
    return {key: deepcopy(result.get(key)) for key in required}


def _verify_step12b_result(result: Mapping[str, Any], slate_date: str) -> str:
    if not isinstance(result, Mapping):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C parent Step-12B result must be an object.")
    if result.get("data_type") != "wnba_step12b_live_runtime_assembly_response":
        raise WNBAStep12LiveBoardIntegrityError("Step 12C received wrong Step-12B data type.")
    if result.get("schema_version") != step12b.SCHEMA_VERSION:
        raise WNBAStep12LiveBoardIntegrityError("Step 12C received wrong Step-12B schema.")
    if result.get("slate_date") != slate_date:
        raise WNBAStep12LiveBoardIntegrityError("Step 12C Step-12B slate identity mismatch.")
    observed = str(result.get("runtime_content_sha256") or "").strip().lower()
    expected = _canonical_hash(_step12b_hash_surface(result))
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep12LiveBoardIntegrityError(
            "Step 12C detected Step-12B runtime content-hash mismatch."
        )
    lineage = result.get("lineage")
    if not isinstance(lineage, Mapping):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C Step-12B lineage is missing.")
    if lineage.get("step12a_frozen_sha") != step12b.STEP12A_FROZEN_SHA:
        raise WNBAStep12LiveBoardIntegrityError("Step 12C Step-12B frozen Step-12A lineage drift.")
    guards = result.get("guardrails")
    if not isinstance(guards, Mapping):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C Step-12B guardrails are missing.")
    for key in (
        "scheduler_started",
        "background_worker_started",
        "sleep_performed",
        "state_persisted",
        "public_fastapi_route_added",
        "supabase_mutated",
        "persistence_mutated",
        "production_runtime_enabled",
        "production_activation_allowed",
        "wager_action_performed",
        "authentication_used",
        "cookies_used",
        "paid_odds_vendor_used",
        "basketball_model_modified",
        "step8_distribution_modified_after_generation",
    ):
        if guards.get(key) is not False:
            raise WNBAStep12LiveBoardIntegrityError(
                f"Step 12C parent Step-12B safety guard drift: {key}."
            )
    return observed


def _nested_runtime(result: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any] | None, Mapping[str, Any] | None]:
    parent = result.get("step12a_result")
    if not isinstance(parent, Mapping):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C Step-12A result is missing from Step 12B.")
    tick = parent.get("step11e_tick")
    if not isinstance(tick, Mapping):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C Step-11E tick is missing from Step 12B.")
    shadow = tick.get("shadow_board_result")
    if shadow is not None and not isinstance(shadow, Mapping):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C shadow board result is malformed.")
    pipeline = shadow.get("pipeline_result") if isinstance(shadow, Mapping) else None
    if pipeline is not None and not isinstance(pipeline, Mapping):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C frozen pipeline result is malformed.")
    return tick, shadow, pipeline


def _decimal_to_american(decimal_odds: float) -> int | None:
    if not math.isfinite(decimal_odds) or decimal_odds <= 1.0:
        return None
    if abs(decimal_odds - 2.0) < 1e-12:
        return 100
    if decimal_odds > 2.0:
        return int(round((decimal_odds - 1.0) * 100.0))
    return int(round(-100.0 / (decimal_odds - 1.0)))


def _fair_price(probability: float) -> dict[str, Any]:
    if probability <= 0.0:
        return {
            "available": False,
            "probability": 0.0,
            "percentage": 0.0,
            "decimal_odds": None,
            "american_odds": None,
        }
    if probability >= 1.0:
        return {
            "available": False,
            "probability": 1.0,
            "percentage": 100.0,
            "decimal_odds": 1.0,
            "american_odds": None,
        }
    decimal = 1.0 / probability
    return {
        "available": True,
        "probability": round(probability, 10),
        "percentage": round(probability * 100.0, 6),
        "decimal_odds": round(decimal, 8),
        "american_odds": _decimal_to_american(decimal),
    }


def _market_records(pipeline: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cycle = pipeline.get("refresh_cycle")
    snapshot = cycle.get("market_snapshot") if isinstance(cycle, Mapping) else None
    records = snapshot.get("records") if isinstance(snapshot, Mapping) else None
    if not isinstance(records, list) or not records:
        raise WNBAStep12LiveBoardNotReadyError(
            "Step 12C healthy board requires eligible frozen Step-10 market records."
        )
    return records


def _selected_quote(
    candidate: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    game_id = str(candidate.get("game_id") or "")
    try:
        player_id = int(candidate.get("player_id"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep12LiveBoardIntegrityError("Step 12C candidate player identity is invalid.") from exc
    stat = str(candidate.get("stat") or "")
    sportsbook = str(candidate.get("sportsbook") or "")
    line = _number(candidate.get("line"), "candidate line")
    matches = []
    for row in records:
        if not isinstance(row, Mapping):
            continue
        try:
            row_player = int(row.get("player_id"))
            row_line = float(row.get("line"))
        except (TypeError, ValueError):
            continue
        if (
            str(row.get("game_id") or "") == game_id
            and row_player == player_id
            and str(row.get("stat") or "") == stat
            and str(row.get("sportsbook") or "").casefold() == sportsbook.casefold()
            and abs(row_line - line) <= _LINE_TOLERANCE
        ):
            matches.append(row)
    if len(matches) != 1:
        raise WNBAStep12LiveBoardIntegrityError(
            "Step 12C requires exactly one frozen market quote for each selected card."
        )
    return matches[0]


def _projection_by_hash(result: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    assembly = result.get("projection_assembly")
    rows = assembly.get("targets") if isinstance(assembly, Mapping) else None
    if not isinstance(rows, list):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C Step-12B projection assembly is missing.")
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise WNBAStep12LiveBoardIntegrityError("Step 12C projection target metadata is malformed.")
        digest = str(row.get("result_content_sha256") or "").strip().lower()
        if not _valid_sha256(digest) or digest in indexed:
            raise WNBAStep12LiveBoardIntegrityError("Step 12C projection target hash is invalid or duplicated.")
        if row.get("simulations") != CERTIFIED_SIMULATIONS or row.get("converged") is not True:
            raise WNBAStep12LiveBoardIntegrityError(
                "Step 12C accepts only certified converged 5M Step-8 targets."
            )
        indexed[digest] = row
    return indexed


def _card(
    candidate: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    projections: Mapping[str, Mapping[str, Any]],
    *,
    display_rank: int,
    ranking: str,
) -> dict[str, Any]:
    if candidate.get("qualified") is not True:
        raise WNBAStep12LiveBoardIntegrityError("Step 12C refuses to display an unqualified primary card.")
    side = str(candidate.get("side") or "").casefold()
    if side not in {"over", "under"}:
        raise WNBAStep12LiveBoardIntegrityError("Step 12C candidate side must be over or under.")
    stat = str(candidate.get("stat") or "")
    if stat not in _STAT_LABELS:
        raise WNBAStep12LiveBoardIntegrityError("Step 12C candidate stat is unsupported.")
    quote = _selected_quote(candidate, records)
    selected_market_odds = quote.get("over_odds") if side == "over" else quote.get("under_odds")
    if selected_market_odds != candidate.get("american_odds"):
        raise WNBAStep12LiveBoardIntegrityError(
            "Step 12C selected market quote price disagrees with frozen Step-9 candidate."
        )
    probability = _probability(candidate.get("model_probability"), "model probability")
    raw_win = _probability(candidate.get("model_raw_win_probability"), "raw win probability")
    push = _probability(candidate.get("model_push_probability"), "push probability")
    if raw_win + push > 1.0 + 2e-8:
        raise WNBAStep12LiveBoardIntegrityError("Step 12C raw win + push probability exceeds one.")
    market_probability = _probability(
        candidate.get("same_line_market_no_vig_probability"),
        "same-line no-vig probability",
    )
    edge = _number(
        candidate.get("same_line_consensus_edge_probability"),
        "same-line consensus edge",
    )
    if abs((probability - market_probability) - edge) > 2e-7:
        raise WNBAStep12LiveBoardIntegrityError(
            "Step 12C frozen probability/no-vig/edge identity is inconsistent."
        )
    lineage = candidate.get("lineage")
    step8_hash = str(lineage.get("step8_result_content_sha256") or "").lower() if isinstance(lineage, Mapping) else ""
    projection = projections.get(step8_hash)
    if projection is None:
        raise WNBAStep12LiveBoardIntegrityError(
            "Step 12C card cannot be tied to a certified Step-8 projection target."
        )
    line = round(_number(candidate.get("line"), "candidate line"), 6)
    rank_value = candidate.get("rank")
    if isinstance(rank_value, bool) or not isinstance(rank_value, int) or rank_value <= 0:
        raise WNBAStep12LiveBoardIntegrityError("Step 12C frozen candidate rank is invalid.")
    quote_age = _number(quote.get("market_age_seconds_at_evaluation"), "quote age")
    captured = str(quote.get("market_captured_at_utc") or "")
    _utc(captured, "market capture")
    fair = _fair_price(probability)
    return {
        "display_rank": display_rank,
        "frozen_rank": rank_value,
        "ranking": ranking,
        "candidate_id": candidate.get("candidate_id"),
        "qualification": "qualified",
        "player": {
            "player_id": int(candidate["player_id"]),
            "player_name": str(quote.get("player_name") or "").strip(),
            "team_key": candidate.get("team_key"),
            "opponent_team_key": candidate.get("opponent_team_key"),
            "game_id": candidate.get("game_id"),
        },
        "prop": {
            "stat": stat,
            "stat_label": _STAT_LABELS[stat],
            "side": side,
            "line": line,
            "pick": f"{side.upper()} {line:g}",
        },
        "market": {
            "sportsbook": candidate.get("sportsbook"),
            "american_odds": selected_market_odds,
            "decimal_odds": round(_number(candidate.get("decimal_odds"), "market decimal odds"), 8),
            "captured_at_utc": captured,
            "age_seconds_at_evaluation": round(quote_age, 3),
        },
        "model": {
            "resolved_fair_probability": round(probability, 10),
            "resolved_fair_percentage": round(probability * 100.0, 6),
            "raw_win_probability": round(raw_win, 10),
            "raw_win_percentage": round(raw_win * 100.0, 6),
            "push_probability": round(push, 10),
            "push_percentage": round(push * 100.0, 6),
            "fair_price": fair,
            "simulations": CERTIFIED_SIMULATIONS,
            "batch_size": CERTIFIED_BATCH_SIZE,
            "converged": True,
        },
        "consensus": {
            "no_vig_probability": round(market_probability, 10),
            "no_vig_percentage": round(market_probability * 100.0, 6),
            "edge_probability": round(edge, 10),
            "edge_percentage_points": round(edge * 100.0, 6),
            "book_count_at_exact_line": int(candidate.get("same_line_book_count")),
            "market_probability_range_percentage_points": round(
                _number(
                    candidate.get("same_line_market_probability_range_percentage_points"),
                    "market probability range",
                ),
                6,
            ),
        },
        "value": {
            "ev_per_unit": round(_number(candidate.get("ev_per_unit"), "EV per unit"), 10),
            "ev_roi_percentage": round(
                _number(candidate.get("ev_roi_percentage"), "EV ROI percentage"), 6
            ),
        },
        "qualification_margin": deepcopy(candidate.get("qualification_margin") or {}),
        "lineage": {
            "step8_result_content_sha256": step8_hash,
            "step9a_pricing_content_sha256": lineage.get("step9a_pricing_content_sha256"),
            "step9b_comparison_content_sha256": lineage.get("step9b_comparison_content_sha256"),
            "step9c_consensus_content_sha256": lineage.get("step9c_consensus_content_sha256"),
        },
    }


def _board_surface(
    result: Mapping[str, Any],
    tick: Mapping[str, Any],
    shadow: Mapping[str, Any] | None,
    pipeline: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    execution = tick.get("execution") or {}
    state = tick.get("automation_state") or {}
    circuit = tick.get("circuit_breaker") or {}
    runtime = {
        "status": tick.get("status"),
        "health": tick.get("health"),
        "evaluated_at_utc": tick.get("evaluated_at_utc"),
        "cycle_due": execution.get("cycle_due"),
        "cycle_executed": execution.get("cycle_executed"),
        "cycle_outcome": execution.get("cycle_outcome"),
        "skip_reason": execution.get("skip_reason"),
        "circuit_state": circuit.get("state_after"),
        "consecutive_failures": circuit.get("consecutive_failures_after"),
        "next_refresh_due_at_utc": state.get("next_refresh_due_at_utc"),
        "circuit_open_until_utc": state.get("circuit_open_until_utc"),
        "controller_state_content_sha256": state.get("state_content_sha256"),
    }
    if shadow is None or pipeline is None:
        if tick.get("health") == "healthy" or execution.get("cycle_outcome") == "shadow_board_ready":
            raise WNBAStep12LiveBoardNotReadyError(
                "Step 12C healthy controller result is missing its frozen shadow board."
            )
        return {
            "available": False,
            "reason": execution.get("cycle_outcome") or tick.get("status") or "board_unavailable",
            "requested_top_card_count": None,
            "qualified_prop_count": 0,
            "primary_top_cards": [],
            "value_ranking": [],
        }, runtime

    board = pipeline.get("board")
    cycle = pipeline.get("refresh_cycle")
    if not isinstance(board, Mapping) or not isinstance(cycle, Mapping):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C frozen board or refresh cycle is missing.")
    if cycle.get("snapshot_source") != "current_refresh":
        raise WNBAStep12LiveBoardIntegrityError(
            "Step 12C live board accepts only a current-refresh frozen market snapshot."
        )
    market_snapshot = cycle.get("market_snapshot")
    if not isinstance(market_snapshot, Mapping):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C frozen market snapshot is missing.")
    records = _market_records(pipeline)
    projections = _projection_by_hash(result)
    top_cards_obj = board.get("top_cards")
    rankings = board.get("rankings")
    summary = board.get("qualification_summary")
    policy = board.get("qualification_policy")
    snapshot_meta = market_snapshot.get("snapshot")
    if not all(isinstance(item, Mapping) for item in (top_cards_obj, rankings, summary, policy, snapshot_meta)):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C frozen board metadata is incomplete.")
    primary = top_cards_obj.get("primary")
    value = rankings.get("value")
    if not isinstance(primary, list) or not isinstance(value, list):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C frozen ranking arrays are missing.")
    if len(primary) > MAX_BOARD_CARDS:
        raise WNBAStep12LiveBoardIntegrityError("Step 12C primary card count exceeds display safety limit.")
    primary_cards = [
        _card(candidate, records, projections, display_rank=index + 1, ranking="pure_probability")
        for index, candidate in enumerate(primary)
    ]
    value_cards = [
        _card(candidate, records, projections, display_rank=index + 1, ranking="value")
        for index, candidate in enumerate(value[:MAX_BOARD_CARDS])
    ]
    requested = int(policy.get("top_n_requested"))
    qualified_count = int(summary.get("qualified_prop_count"))
    if int(summary.get("top_card_count")) != len(primary_cards):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C frozen top-card count drift.")
    runtime.update(
        {
            "snapshot_source": cycle.get("snapshot_source"),
            "sportsbooks": deepcopy((market_snapshot.get("snapshot") or {}).get("unique_sportsbooks") or []),
            "eligible_market_record_count": snapshot_meta.get("eligible_record_count"),
            "latest_market_capture_utc": snapshot_meta.get("board_latest_capture_utc"),
            "earliest_market_capture_utc": snapshot_meta.get("board_earliest_capture_utc"),
            "board_capture_spread_seconds": snapshot_meta.get("board_capture_spread_seconds"),
            "board_synchronized": snapshot_meta.get("board_synchronized"),
        }
    )
    board_surface = {
        "available": True,
        "ranking_method": top_cards_obj.get("selection_method"),
        "requested_top_card_count": requested,
        "qualified_prop_count": qualified_count,
        "top_card_count": len(primary_cards),
        "full_requested_board_available": summary.get("full_requested_board_available") is True,
        "top_n_forced": False,
        "primary_top_cards": primary_cards,
        "value_ranking": value_cards,
    }
    return board_surface, runtime


def run_step12c_live_board_job(
    request: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    draftkings_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    fanduel_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_requester: Callable[..., Any] | None = None,
    fanduel_requester: Callable[..., Any] | None = None,
    roster_loader: Callable[[int], Mapping[str, Any]] | None = None,
    projection_loader: Callable[..., Mapping[str, Any]] | None = None,
    step12a_runner: Callable[..., Mapping[str, Any]] | None = None,
    step12b_runner: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute one frozen Step-12B runtime and render its application-facing board."""
    _assert_safe_environment(env)
    normalized = _validate_request(request)
    parent_request = step12b.build_step12b_request(
        season=normalized["season"],
        slate_date=normalized["slate_date"],
        evaluated_at=normalized["evaluated_at"],
        previous_state=normalized["previous_state"],
        controller_policy=normalized["controller_policy"],
        refresh_policy=normalized["refresh_policy"],
        qualification_policy=normalized["qualification_policy"],
    )
    runner = step12b_runner or step12b.run_step12b_live_runtime_job
    parent_result = runner(
        parent_request,
        env=env,
        draftkings_fetcher=draftkings_fetcher,
        fanduel_fetcher=fanduel_fetcher,
        draftkings_requester=draftkings_requester,
        fanduel_requester=fanduel_requester,
        roster_loader=roster_loader,
        projection_loader=projection_loader,
        step12a_runner=step12a_runner,
    )
    parent_hash = _verify_step12b_result(parent_result, normalized["slate_date"])
    tick, shadow, pipeline = _nested_runtime(parent_result)
    board, runtime = _board_surface(parent_result, tick, shadow, pipeline)
    state = tick.get("automation_state")
    if not isinstance(state, Mapping):
        raise WNBAStep12LiveBoardIntegrityError("Step 12C controller state is missing.")

    response = {
        "data_type": "wnba_step12c_live_board_runtime_response",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "request_content_sha256": normalized["request_content_sha256"],
        "status": parent_result.get("status"),
        "health": parent_result.get("health"),
        "slate_date": normalized["slate_date"],
        "runtime": runtime,
        "board": board,
        "controller_state_for_next_caller_tick": deepcopy(dict(state)),
        "diagnostics": {
            "provider_discovery": deepcopy(parent_result.get("provider_discovery") or {}),
            "market_overlap": deepcopy(parent_result.get("market_overlap") or {}),
            "projection_assembly": deepcopy(parent_result.get("projection_assembly") or {}),
            "runtime_summary": deepcopy(parent_result.get("runtime_summary") or {}),
        },
        "lineage": {
            "step12b_frozen_sha": STEP12B_FROZEN_SHA,
            "step12b_runtime_content_sha256": parent_hash,
            "step12b_request_content_sha256": parent_result.get("request_content_sha256"),
            "step12a_frozen_sha": (parent_result.get("lineage") or {}).get("step12a_frozen_sha"),
            "step11e_frozen_sha": (parent_result.get("lineage") or {}).get("step11e_frozen_sha"),
            "step8_frozen_sha": (parent_result.get("lineage") or {}).get("step8_frozen_sha"),
            "step10_pipeline_content_sha256": (
                (shadow.get("lineage") or {}).get("step10_pipeline_content_sha256")
                if isinstance(shadow, Mapping)
                else None
            ),
            "step9_ranking_content_sha256": (
                (shadow.get("lineage") or {}).get("step9_ranking_content_sha256")
                if isinstance(shadow, Mapping)
                else None
            ),
        },
        "guardrails": {
            "shadow_only": True,
            "caller_driven_job_only": True,
            "presentation_layer_only": True,
            "frozen_step12b_called_once": True,
            "frozen_step9_ranking_order_preserved": True,
            "frozen_step9_qualification_preserved": True,
            "frozen_step9_model_probability_preserved": True,
            "frozen_step9_market_price_preserved": True,
            "fair_odds_are_deterministic_format_of_frozen_model_probability": True,
            "sportsbook_network_fetch_added_by_step12c": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "market_probability_recomputed": False,
            "consensus_recomputed": False,
            "qualification_recomputed": False,
            "ranking_recomputed": False,
            "scheduler_started": False,
            "background_worker_started": False,
            "sleep_performed": False,
            "state_persisted": False,
            "caller_must_resupply_state": True,
            "public_fastapi_route_added": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "wager_action_performed": False,
            "authentication_used": False,
            "cookies_used": False,
            "paid_odds_vendor_used": False,
        },
    }
    surface = {
        key: value for key, value in response.items()
        if key not in {"generated_at_utc", "board_content_sha256"}
    }
    response["board_content_sha256"] = _canonical_hash(surface)
    _assert_safe_environment(env)
    return response


__all__ = [
    "CERTIFIED_BATCH_SIZE",
    "CERTIFIED_SIMULATIONS",
    "DEFAULT_ENABLED",
    "MODEL_VERSION",
    "REQUEST_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "STEP12B_FROZEN_SHA",
    "STEP12C_LIVE_BOARD_RUNTIME_ENABLED_ENV",
    "WNBAStep12LiveBoardDisabledError",
    "WNBAStep12LiveBoardInputError",
    "WNBAStep12LiveBoardIntegrityError",
    "WNBAStep12LiveBoardNotReadyError",
    "build_step12c_request",
    "run_step12c_live_board_job",
    "step12c_live_board_runtime_enabled",
]
