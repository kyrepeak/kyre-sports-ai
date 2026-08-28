"""Step 10E: join the frozen Step-10 market refresh stack to frozen Step 9.

The caller supplies provider refresh attempts plus certified Step-8 distributions.
This module runs Step 10D, consumes only its reconciled eligible Step-10C records,
joins them to the matching Step-8 player distribution, then invokes the frozen
Step-9 A→D pricing/market/consensus/ranking chain. It performs no provider network
fetch, sleeping, scheduling, persistence, Supabase write, or production activation.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any, Mapping, Sequence

from sports_api import wnba_step10_release_freeze as release
from sports_api import wnba_step10_refresh_controller as step10d
from sports_api import wnba_step9_release_freeze as step9_release
from sports_api.api import wnba_step9_market_board as step9api
from sports_api.wnba_step9_qualification_ranking import build_step9d_qualification_ranking

SOURCE = "Kyre Sports API WNBA Step 10E full live-market board pipeline"
SCHEMA_VERSION = "wnba_step_10e_live_market_pipeline_v1"
MODEL_VERSION = "wnba_step10e_refresh_to_frozen_step9_board_2026_regular_v1"
RELEASE_ID = release.RELEASE_ID

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep10LivePipelineDisabledError(RuntimeError):
    """Raised when Step 10E is not isolated behind every required gate."""


class WNBAStep10LivePipelineNotReadyError(RuntimeError):
    """Raised when no reconciled Step-10 market can be joined to Step 8."""


class WNBAStep10LivePipelineInputError(ValueError):
    """Raised for malformed or ambiguous Step-8 join inputs."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep10LivePipelineDisabledError(
            "Step 10E refuses production/scheduler switches: " + ", ".join(bad)
        )
    if not release.step10_fastapi_enabled(source):
        raise WNBAStep10LivePipelineDisabledError(
            f"Step 10E requires {release.STEP10_FASTAPI_ENABLED_ENV}=true."
        )
    if not step9_release.step9_fastapi_enabled(source):
        raise WNBAStep10LivePipelineDisabledError(
            f"Step 10E requires frozen Step 9 gate {step9_release.STEP9_FASTAPI_ENABLED_ENV}=true."
        )
    if not step10d.step10d_refresh_controller_enabled(source):
        raise WNBAStep10LivePipelineDisabledError(
            "Step 10E requires the frozen Step-10D refresh-controller gate."
        )
    if step10d.STEP10C_FROZEN_HEAD_SHA != release.STEP10C_FROZEN_SHA:
        raise WNBAStep10LivePipelineDisabledError("Step 10D frozen Step-10C lineage drift.")
    if step9_release.RELEASE_ID != "wnba_step9_market_board_2026_regular_season_frozen_v1":
        raise WNBAStep10LivePipelineDisabledError("Frozen Step-9 release identity drift.")


def _evaluation_time(value: datetime | None) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBAStep10LivePipelineInputError("Step 10E evaluated_at must be timezone-aware.")
    return result.astimezone(timezone.utc)


def _distribution_identity(distribution: Mapping[str, Any]) -> tuple[str, int]:
    if not isinstance(distribution, Mapping):
        raise WNBAStep10LivePipelineInputError("Each Step-8 distribution must be an object.")
    game_id = str(distribution.get("game_id") or "").strip()
    if not game_id:
        raise WNBAStep10LivePipelineInputError("Each Step-8 distribution requires game_id.")
    try:
        player_id = int(distribution.get("player_id"))
    except (TypeError, ValueError) as exc:
        raise WNBAStep10LivePipelineInputError(
            "Each Step-8 distribution requires a positive integer player_id."
        ) from exc
    if player_id <= 0:
        raise WNBAStep10LivePipelineInputError(
            "Each Step-8 distribution requires a positive integer player_id."
        )
    return game_id, player_id


def _step8_index(step8_distributions: Sequence[Mapping[str, Any]]) -> dict[tuple[str, int], Mapping[str, Any]]:
    if isinstance(step8_distributions, (str, bytes)) or not isinstance(step8_distributions, Sequence):
        raise WNBAStep10LivePipelineInputError("step8_distributions must be a sequence.")
    if not 1 <= len(step8_distributions) <= 250:
        raise WNBAStep10LivePipelineInputError("Step 10E requires 1 through 250 Step-8 distributions.")
    indexed: dict[tuple[str, int], Mapping[str, Any]] = {}
    for distribution in step8_distributions:
        identity = _distribution_identity(distribution)
        if identity in indexed:
            raise WNBAStep10LivePipelineInputError(
                f"Duplicate Step-8 distribution identity: game={identity[0]} player={identity[1]}."
            )
        indexed[identity] = distribution
    return indexed


def _group_market_records(records: Sequence[Mapping[str, Any]]) -> dict[tuple[str, int, str], list[Mapping[str, Any]]]:
    grouped: dict[tuple[str, int, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in records:
        identity = (
            str(row["game_id"]),
            int(row["player_id"]),
            str(row["stat"]),
        )
        grouped[identity].append(row)
    return dict(grouped)


def build_step10e_live_market_board(
    *,
    provider_refreshes: Sequence[Mapping[str, Any]],
    step8_distributions: Sequence[Mapping[str, Any]],
    last_good_snapshot: Mapping[str, Any] | None = None,
    expected_sportsbooks: Sequence[str] | None = None,
    refresh_policy: Mapping[str, Any] | None = None,
    qualification_policy: Mapping[str, Any] | None = None,
    evaluated_at: datetime | None = None,
    cycle_started_at: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build the full frozen Step-10 → Step-9 board from caller-supplied refresh data."""
    _assert_safe_environment(env)
    evaluated = _evaluation_time(evaluated_at)
    distributions = _step8_index(step8_distributions)

    refresh_options = dict(refresh_policy or {})
    allowed_refresh = {
        "refresh_interval_seconds",
        "max_attempts_per_provider",
        "retry_base_seconds",
        "retry_multiplier",
        "retry_max_seconds",
        "allow_last_good_fallback",
        "max_last_good_age_seconds",
        "max_quote_age_seconds",
        "max_market_sync_seconds",
        "max_board_sync_seconds",
        "require_board_synchronized",
    }
    unknown_refresh = sorted(set(refresh_options) - allowed_refresh)
    if unknown_refresh:
        raise WNBAStep10LivePipelineInputError(
            "Unknown Step-10 refresh policy fields: " + ", ".join(unknown_refresh)
        )

    cycle = step10d.run_step10d_refresh_cycle(
        provider_refreshes,
        evaluated_at=evaluated,
        cycle_started_at=cycle_started_at,
        last_good_snapshot=last_good_snapshot,
        expected_sportsbooks=expected_sportsbooks,
        env=env,
        **refresh_options,
    )
    if cycle.get("status") not in {"ready", "degraded_last_good"}:
        raise WNBAStep10LivePipelineNotReadyError(
            f"Step 10D refresh cycle is not board-ready: {cycle.get('status')!r}."
        )
    market_snapshot = cycle.get("market_snapshot")
    if not isinstance(market_snapshot, Mapping) or not market_snapshot.get("records"):
        raise WNBAStep10LivePipelineNotReadyError("Step 10D returned no eligible market records.")

    try:
        policy = step9api.Step9QualificationPolicy(**dict(qualification_policy or {}))
    except Exception as exc:  # Pydantic validation error: keep API-independent surface simple.
        raise WNBAStep10LivePipelineInputError(f"Invalid Step-9 qualification policy: {exc}") from exc

    grouped = _group_market_records(market_snapshot["records"])
    consensuses: list[dict[str, Any]] = []
    prop_summaries: list[dict[str, Any]] = []
    unmatched_market_families: list[dict[str, Any]] = []
    matched_distribution_ids: set[tuple[str, int]] = set()

    for (game_id, player_id, stat), rows in sorted(grouped.items(), key=lambda item: item[0]):
        distribution = distributions.get((game_id, player_id))
        if distribution is None:
            unmatched_market_families.append({
                "game_id": game_id,
                "player_id": player_id,
                "stat": stat,
                "eligible_offer_count": len(rows),
            })
            continue
        offers = [
            step9api.Step9SportsbookOffer(
                sportsbook=str(row["sportsbook"]),
                line=float(row["line"]),
                over_odds=int(row["over_odds"]),
                under_odds=int(row["under_odds"]),
                market_captured_at_utc=str(row["market_captured_at_utc"]),
            )
            for row in rows
        ]
        # Frozen Step 9 requires at least two sportsbook offers for a prop. A market
        # family with one surviving quote stays visible in diagnostics but is not
        # promoted into the ranking chain.
        if len(offers) < 2:
            unmatched_market_families.append({
                "game_id": game_id,
                "player_id": player_id,
                "stat": stat,
                "eligible_offer_count": len(offers),
                "reason": "fewer_than_two_eligible_offers",
            })
            continue
        prop = step9api.Step9PropInput(
            step8_distribution=dict(distribution),
            stat=stat,
            offers=offers,
        )
        consensus, summary = step9api._build_prop_consensus(
            prop,
            policy=policy,
            evaluated_at=evaluated,
        )
        consensuses.append(consensus)
        prop_summaries.append(summary)
        matched_distribution_ids.add((game_id, player_id))

    if not consensuses:
        raise WNBAStep10LivePipelineNotReadyError(
            "No Step-10 market family with two or more eligible offers matched a supplied Step-8 distribution."
        )

    board = build_step9d_qualification_ranking(
        consensuses,
        top_n=policy.top_n,
        minimum_model_probability=policy.minimum_model_probability,
        minimum_ev=policy.minimum_ev,
        minimum_consensus_edge=policy.minimum_consensus_edge,
        minimum_books_at_line=policy.minimum_books_at_line,
        maximum_consensus_range_percentage_points=(
            policy.maximum_consensus_range_percentage_points
        ),
        max_board_snapshot_spread_seconds=policy.max_board_snapshot_spread_seconds,
        require_fresh_snapshots=policy.require_fresh_market,
        require_synchronized_snapshots=policy.require_synchronized_snapshots,
        one_selection_per_player=policy.one_selection_per_player,
    )

    unmatched_step8 = [
        {"game_id": game_id, "player_id": player_id}
        for game_id, player_id in sorted(set(distributions) - matched_distribution_ids)
    ]

    result = {
        "data_type": "wnba_step10_live_market_board_pipeline_response_v1",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluated_at_utc": evaluated.isoformat(),
        "refresh_cycle": cycle,
        "pipeline": {
            "order": [
                "step10a", "step10b", "step10c", "step10d",
                "step9a", "step9b", "step9c", "step9d",
            ],
            "matched_prop_count": len(consensuses),
            "props": prop_summaries,
            "unmatched_market_families": unmatched_market_families,
            "unmatched_step8_distributions": unmatched_step8,
        },
        "board": board,
        "lineage": {
            "step8_frozen_sha": release.STEP8_FROZEN_SHA,
            "step9_frozen_sha": release.STEP9_FROZEN_SHA,
            "step10a_frozen_sha": release.STEP10A_FROZEN_SHA,
            "step10b_frozen_sha": release.STEP10B_FROZEN_SHA,
            "step10c_frozen_sha": release.STEP10C_FROZEN_SHA,
            "step10d_frozen_sha": release.STEP10D_FROZEN_SHA,
            "refresh_cycle_id": cycle.get("refresh_cycle_id"),
            "refresh_cycle_content_sha256": cycle.get("refresh_cycle_content_sha256"),
            "step10c_snapshot_content_sha256": market_snapshot.get("snapshot_content_sha256"),
            "snapshot_source": cycle.get("snapshot_source"),
            "step9_release_id": step9_release.RELEASE_ID,
        },
        "guardrails": {
            "caller_supplied_provider_attempts_consumed": True,
            "sportsbook_network_fetch_performed": False,
            "retry_sleep_performed": False,
            "market_snapshot_reconciled": True,
            "step9_called_after_market_reconciliation": True,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "vig_removed": True,
            "edge_calculated": True,
            "expected_value_calculated": True,
            "cross_sportsbook_consensus_calculated": True,
            "cross_prop_ranking_calculated": True,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    hash_surface = {
        key: value for key, value in result.items()
        if key not in {"generated_at_utc", "pipeline_content_sha256"}
    }
    result["pipeline_content_sha256"] = _canonical_hash(hash_surface)
    _assert_safe_environment(env)
    return result
