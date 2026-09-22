"""WNBA Step 11D: DraftKings + FanDuel live shadow board over frozen Step 10/9.

Step 11D is the first layer that can execute both certified sportsbook connectors
in one invocation and then feed their exact Step-10 provider-refresh objects into
the frozen Step-10E -> Step-9 market-board pipeline.

It is intentionally a *shadow* surface: explicit call only, no scheduler, no
persistence, no Supabase mutation, no public FastAPI route, no production runtime,
and no wagering action. Exact-line multi-book consensus remains owned by frozen
Step 9C/9D; different sportsbook lines are never blended into fake consensus.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any

from sports_api import wnba_step10_release_freeze as step10_freeze
from sports_api import wnba_step11_draftkings_provider as draftkings
from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step11_network_refresh_orchestrator as step11b
from sports_api.wnba_step10_live_pipeline import build_step10e_live_market_board

SOURCE = "Kyre Sports API WNBA Step 11D DraftKings + FanDuel live shadow board"
SCHEMA_VERSION = "wnba_step_11d_multibook_live_shadow_board_v1"
MODEL_VERSION = "wnba_step11d_two_provider_exact_line_shadow_board_2026_regular_v1"
RELEASE_ID = "wnba_step11d_multibook_shadow_board_2026_regular_season_v1"
STEP11D_MULTIBOOK_SHADOW_ENABLED_ENV = "WNBA_STEP11D_MULTIBOOK_SHADOW_ENABLED"

STEP11C_FROZEN_HEAD_SHA = "d33422b3b3807afa256ab6dca56ddea4fef24933"
STEP11B_FROZEN_HEAD_SHA = "26072ea38f3d540dc5771405e5c9df728a15f4ff"
STEP11A_FROZEN_HEAD_SHA = "695e7b45bd74fcb70c4f4fa6a886b4a054d06810"
STEP10_FROZEN_HEAD_SHA = "4341d178aa65806e9bc001c8759eccb4a003ea63"

SPORTSBOOKS = (draftkings.PROVIDER, fanduel.PROVIDER)
DEFAULT_PROVIDER_ATTEMPTS = 3
MAX_PROVIDER_ATTEMPTS = 5
_ERROR_CODE_RE = re.compile(r"[^A-Za-z0-9_.:-]+")

_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


class WNBAStep11MultiBookShadowDisabledError(RuntimeError):
    """Raised when Step 11D is not explicitly isolated behind its safety gates."""


class WNBAStep11MultiBookShadowInputError(ValueError):
    """Raised for malformed Step-11D invocation policy."""


class WNBAStep11MultiBookShadowIntegrityError(ValueError):
    """Raised when a provider bridge violates frozen lineage/hash/safety contracts."""


class WNBAStep11MultiBookShadowNotReadyError(RuntimeError):
    """Raised when both certified providers do not produce a current shadow snapshot."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step11d_multibook_shadow_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP11D_MULTIBOOK_SHADOW_ENABLED_ENV))


def _assert_safe_environment(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    bad = [name for name in _OFF_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep11MultiBookShadowDisabledError(
            "Step 11D refuses production/scheduler/sync switches: " + ", ".join(bad)
        )
    required_flags = (
        STEP11D_MULTIBOOK_SHADOW_ENABLED_ENV,
        draftkings.STEP11A_DRAFTKINGS_PROVIDER_ENABLED_ENV,
        step11b.STEP11B_NETWORK_REFRESH_ENABLED_ENV,
        fanduel.STEP11C_FANDUEL_PROVIDER_ENABLED_ENV,
        step10_freeze.STEP10_FASTAPI_ENABLED_ENV,
        "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED",
        "WNBA_STEP10B_MARKET_ADAPTER_ENABLED",
        "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED",
        "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED",
        "WNBA_STEP9_FASTAPI_ENABLED",
        "WNBA_STEP9_THRESHOLD_PRICING_ENABLED",
        "WNBA_STEP9B_MARKET_COMPARISON_ENABLED",
        "WNBA_STEP9C_MULTIBOOK_CONSENSUS_ENABLED",
        "WNBA_STEP9D_QUALIFICATION_RANKING_ENABLED",
    )
    missing = [name for name in required_flags if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep11MultiBookShadowDisabledError(
            "Step 11D requires isolated frozen gates: " + ", ".join(missing)
        )
    if step10_freeze.DEFAULT_ENABLED is not False:
        raise WNBAStep11MultiBookShadowDisabledError("Frozen Step 10 default-OFF contract drift.")
    if step10_freeze.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise WNBAStep11MultiBookShadowDisabledError("Frozen Step 10 production activation drift.")
    if draftkings.STEP10_FROZEN_SHA != STEP10_FROZEN_HEAD_SHA:
        raise WNBAStep11MultiBookShadowDisabledError("DraftKings frozen Step-10 lineage drift.")
    if fanduel.STEP11B_FROZEN_HEAD_SHA != STEP11B_FROZEN_HEAD_SHA:
        raise WNBAStep11MultiBookShadowDisabledError("FanDuel frozen Step-11B lineage drift.")
    if fanduel.STEP11A_FROZEN_HEAD_SHA != STEP11A_FROZEN_HEAD_SHA:
        raise WNBAStep11MultiBookShadowDisabledError("FanDuel frozen Step-11A lineage drift.")
    if fanduel.STEP10_FROZEN_HEAD_SHA != STEP10_FROZEN_HEAD_SHA:
        raise WNBAStep11MultiBookShadowDisabledError("FanDuel frozen Step-10 lineage drift.")


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _evaluation_time(value: datetime | None) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBAStep11MultiBookShadowInputError(
            "WNBA Step 11D evaluated_at must be timezone-aware."
        )
    return result.astimezone(timezone.utc)


def _attempt_limit(value: Any) -> int:
    if isinstance(value, bool):
        raise WNBAStep11MultiBookShadowInputError("provider_attempts must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAStep11MultiBookShadowInputError("provider_attempts must be an integer.") from exc
    if isinstance(value, float) and not value.is_integer():
        raise WNBAStep11MultiBookShadowInputError("provider_attempts must be an integer.")
    if not 1 <= result <= MAX_PROVIDER_ATTEMPTS:
        raise WNBAStep11MultiBookShadowInputError(
            f"provider_attempts must be from 1 through {MAX_PROVIDER_ATTEMPTS}."
        )
    return result


def _error_code(exc: Exception) -> str:
    text = _ERROR_CODE_RE.sub("_", type(exc).__name__).strip("_") or "provider_error"
    return text[:80]


def _bridge_hash_is_valid(bridge: Mapping[str, Any]) -> bool:
    surface = {
        key: value for key, value in bridge.items()
        if key not in {"generated_at_utc", "provider_bridge_content_sha256"}
    }
    return bridge.get("provider_bridge_content_sha256") == _canonical_hash(surface)


def _verify_bridge(
    bridge: Mapping[str, Any],
    *,
    provider: str,
) -> dict[str, Any]:
    if not isinstance(bridge, Mapping):
        raise WNBAStep11MultiBookShadowIntegrityError("Provider bridge must be an object.")
    if provider == draftkings.PROVIDER:
        expected = {
            "data_type": "wnba_step11a_draftkings_provider_bridge",
            "schema_version": draftkings.SCHEMA_VERSION,
            "model_version": draftkings.MODEL_VERSION,
            "release_id": draftkings.RELEASE_ID,
            "provider": draftkings.PROVIDER,
        }
        expected_adapter = draftkings.ADAPTER_TYPE
        lineage = bridge.get("lineage") or {}
        if lineage.get("step10_frozen_git_sha") != STEP10_FROZEN_HEAD_SHA:
            raise WNBAStep11MultiBookShadowIntegrityError("DraftKings Step-10 lineage drift.")
        if lineage.get("step10b_frozen_git_sha") != step10_freeze.STEP10B_FROZEN_SHA:
            raise WNBAStep11MultiBookShadowIntegrityError("DraftKings Step-10B lineage drift.")
    elif provider == fanduel.PROVIDER:
        expected = {
            "data_type": "wnba_step11c_fanduel_provider_bridge",
            "schema_version": fanduel.SCHEMA_VERSION,
            "model_version": fanduel.MODEL_VERSION,
            "release_id": fanduel.RELEASE_ID,
            "provider": fanduel.PROVIDER,
        }
        expected_adapter = fanduel.ADAPTER_TYPE
        lineage = bridge.get("lineage") or {}
        if lineage.get("step11b_frozen_git_sha") != STEP11B_FROZEN_HEAD_SHA:
            raise WNBAStep11MultiBookShadowIntegrityError("FanDuel Step-11B lineage drift.")
        if lineage.get("step11a_frozen_git_sha") != STEP11A_FROZEN_HEAD_SHA:
            raise WNBAStep11MultiBookShadowIntegrityError("FanDuel Step-11A lineage drift.")
        if lineage.get("step10_frozen_git_sha") != STEP10_FROZEN_HEAD_SHA:
            raise WNBAStep11MultiBookShadowIntegrityError("FanDuel Step-10 lineage drift.")
        if lineage.get("step10b_frozen_git_sha") != step10_freeze.STEP10B_FROZEN_SHA:
            raise WNBAStep11MultiBookShadowIntegrityError("FanDuel Step-10B lineage drift.")
    else:
        raise WNBAStep11MultiBookShadowInputError(f"Unsupported Step-11D provider {provider!r}.")

    for key, value in expected.items():
        if bridge.get(key) != value:
            raise WNBAStep11MultiBookShadowIntegrityError(
                f"{provider} frozen bridge {key} drift."
            )
    guards = bridge.get("guardrails") or {}
    for key in (
        "authentication_used",
        "cookies_used",
        "wager_action_performed",
        "paid_odds_vendor_used",
        "basketball_projection_changed",
        "step8_distribution_changed",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    ):
        if guards.get(key) is not False:
            raise WNBAStep11MultiBookShadowIntegrityError(
                f"{provider} safety guardrail {key} drift."
            )
    if guards.get("sportsbook_network_fetch_performed") is not True:
        raise WNBAStep11MultiBookShadowIntegrityError(
            f"Step 11D requires a network-wrapper {provider} bridge."
        )
    if guards.get("sportsbook_http_methods") != ["GET"]:
        raise WNBAStep11MultiBookShadowIntegrityError(
            f"Step 11D accepts GET-only {provider} sportsbook transport."
        )
    if not _bridge_hash_is_valid(bridge):
        raise WNBAStep11MultiBookShadowIntegrityError(
            f"{provider} provider bridge content hash mismatch."
        )
    refresh = bridge.get("provider_refresh")
    if not isinstance(refresh, Mapping) or set(refresh) != {"provider", "adapter_type", "attempts"}:
        raise WNBAStep11MultiBookShadowIntegrityError(
            f"{provider} provider_refresh shape drift."
        )
    if refresh.get("provider") != provider or refresh.get("adapter_type") != expected_adapter:
        raise WNBAStep11MultiBookShadowIntegrityError(
            f"{provider} provider_refresh identity drift."
        )
    attempts = refresh.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != 1:
        raise WNBAStep11MultiBookShadowIntegrityError(
            f"{provider} successful bridge must contain one Step-10 success attempt."
        )
    attempt = attempts[0]
    if not isinstance(attempt, Mapping) or attempt.get("ok") is not True or not isinstance(attempt.get("payload"), Mapping):
        raise WNBAStep11MultiBookShadowIntegrityError(
            f"{provider} successful bridge contains malformed payload attempt."
        )
    payload = dict(attempt["payload"])
    if payload.get("provider") != provider:
        raise WNBAStep11MultiBookShadowIntegrityError(
            f"{provider} payload provider identity drift."
        )
    return payload


def _provider_specs(
    draftkings_fetcher: Callable[..., Mapping[str, Any]] | None,
    fanduel_fetcher: Callable[..., Mapping[str, Any]] | None,
) -> tuple[dict[str, Any], ...]:
    return (
        {
            "provider": draftkings.PROVIDER,
            "adapter_type": draftkings.ADAPTER_TYPE,
            "fetcher": draftkings_fetcher or draftkings.fetch_step11a_draftkings_provider_bridge,
            "retryable": (
                draftkings.WNBAStep11DraftKingsProviderUpstreamError,
                draftkings.WNBAStep11DraftKingsProviderNotReadyError,
            ),
            "terminal": (
                draftkings.WNBAStep11DraftKingsProviderDisabledError,
                draftkings.WNBAStep11DraftKingsProviderIdentityError,
            ),
        },
        {
            "provider": fanduel.PROVIDER,
            "adapter_type": fanduel.ADAPTER_TYPE,
            "fetcher": fanduel_fetcher or fanduel.fetch_step11c_fanduel_provider_bridge,
            "retryable": (
                fanduel.WNBAStep11FanDuelProviderUpstreamError,
                fanduel.WNBAStep11FanDuelProviderNotReadyError,
            ),
            "terminal": (
                fanduel.WNBAStep11FanDuelProviderDisabledError,
                fanduel.WNBAStep11FanDuelProviderIdentityError,
            ),
        },
    )


def _same_line_audit(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, int, str, float], set[str]] = defaultdict(set)
    for row in records:
        key = (
            str(row.get("game_id")),
            int(row.get("player_id")),
            str(row.get("stat")),
            round(float(row.get("line")), 6),
        )
        groups[key].add(str(row.get("sportsbook")))
    exact_multibook = [
        {
            "game_id": key[0],
            "player_id": key[1],
            "stat": key[2],
            "line": key[3],
            "sportsbooks": sorted(books),
            "sportsbook_count": len(books),
        }
        for key, books in sorted(groups.items())
        if len(books) >= 2
    ]
    return {
        "exact_line_group_count": len(groups),
        "exact_line_multibook_group_count": len(exact_multibook),
        "exact_line_multibook_groups": exact_multibook,
        "different_lines_blended": False,
    }


def run_step11d_multibook_shadow_board(
    *,
    season: int,
    slate_date: str,
    step8_distributions: Sequence[Mapping[str, Any]],
    evaluated_at: datetime | None = None,
    cycle_started_at: datetime | None = None,
    provider_attempts: int = DEFAULT_PROVIDER_ATTEMPTS,
    refresh_policy: Mapping[str, Any] | None = None,
    qualification_policy: Mapping[str, Any] | None = None,
    draftkings_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    fanduel_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_requester: Callable[..., Any] | None = None,
    fanduel_requester: Callable[..., Any] | None = None,
    roster_loader: Callable[[int], Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Execute one current two-book shadow cycle and invoke frozen Step 10E/Step 9.

    Both DraftKings and FanDuel must succeed in the current invocation. This avoids
    calling a one-book snapshot "multi-book." Frozen Step 9 still independently
    requires exact same-line book counts before qualification.
    """
    _assert_safe_environment(env)
    if int(season) != 2026:
        raise WNBAStep11MultiBookShadowInputError(
            "Step 11D is certified for the 2026 Regular Season only."
        )
    evaluated = _evaluation_time(evaluated_at)
    limit = _attempt_limit(provider_attempts)

    provider_refreshes: list[dict[str, Any]] = []
    provider_results: list[dict[str, Any]] = []
    bridge_hashes: dict[str, str] = {}

    for spec in _provider_specs(draftkings_fetcher, fanduel_fetcher):
        provider = spec["provider"]
        requester = draftkings_requester if provider == draftkings.PROVIDER else fanduel_requester
        attempts: list[dict[str, Any]] = []
        bridge: Mapping[str, Any] | None = None
        payload: dict[str, Any] | None = None
        retryable_failures = 0
        for _attempt_number in range(1, limit + 1):
            try:
                candidate = spec["fetcher"](
                    season=int(season),
                    slate_date=str(slate_date),
                    evaluated_at=evaluated,
                    requester=requester,
                    roster_loader=roster_loader,
                    env=env,
                )
                payload = _verify_bridge(candidate, provider=provider)
            except spec["retryable"] as exc:
                retryable_failures += 1
                attempts.append({"ok": False, "error_code": _error_code(exc)})
                continue
            except spec["terminal"]:
                raise
            except WNBAStep11MultiBookShadowIntegrityError:
                raise
            except ValueError:
                raise
            bridge = candidate
            attempts.append({"ok": True, "payload": payload})
            break

        provider_refreshes.append({
            "provider": provider,
            "adapter_type": spec["adapter_type"],
            "attempts": attempts,
        })
        provider_results.append({
            "provider": provider,
            "attempt_limit": limit,
            "attempts_executed": len(attempts),
            "retryable_failures": retryable_failures,
            "succeeded": payload is not None,
            "bridge_content_sha256": (
                bridge.get("provider_bridge_content_sha256") if bridge is not None else None
            ),
        })
        if bridge is not None:
            bridge_hashes[provider] = str(bridge.get("provider_bridge_content_sha256"))

    succeeded = [row["provider"] for row in provider_results if row["succeeded"]]
    if set(succeeded) != set(SPORTSBOOKS):
        raise WNBAStep11MultiBookShadowNotReadyError(
            "Step 11D requires current successful DraftKings and FanDuel bridges; "
            f"succeeded={sorted(succeeded)}."
        )

    policy = dict(qualification_policy or {})
    if int(policy.get("minimum_books_at_line", 2)) < 2:
        raise WNBAStep11MultiBookShadowInputError(
            "Step 11D shadow board requires minimum_books_at_line >= 2."
        )
    policy.setdefault("minimum_books_at_line", 2)

    pipeline = build_step10e_live_market_board(
        provider_refreshes=provider_refreshes,
        step8_distributions=step8_distributions,
        expected_sportsbooks=list(SPORTSBOOKS),
        refresh_policy=refresh_policy,
        qualification_policy=policy,
        evaluated_at=evaluated,
        cycle_started_at=cycle_started_at,
        env=env,
    )
    cycle = pipeline.get("refresh_cycle") or {}
    if cycle.get("snapshot_source") != "current_refresh":
        raise WNBAStep11MultiBookShadowNotReadyError(
            "Step 11D shadow board accepts only a current-refresh snapshot."
        )
    snapshot = cycle.get("market_snapshot") or {}
    records = snapshot.get("records") or []
    audit = _same_line_audit(records)
    board = pipeline.get("board") or {}
    top_cards = board.get("top_cards") or {}
    primary = top_cards.get("primary") if isinstance(top_cards, Mapping) else []
    primary = primary if isinstance(primary, list) else []

    result = {
        "data_type": "wnba_step11d_multibook_live_shadow_board",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluated_at_utc": evaluated.isoformat(),
        "shadow_only": True,
        "sportsbooks": list(SPORTSBOOKS),
        "providers": provider_results,
        "provider_refreshes": provider_refreshes,
        "market_audit": audit,
        "shadow_summary": {
            "provider_count": len(provider_results),
            "successful_provider_count": len(succeeded),
            "eligible_market_record_count": len(records),
            "matched_prop_count": int((pipeline.get("pipeline") or {}).get("matched_prop_count") or 0),
            "qualified_prop_count": int((board.get("qualification_summary") or {}).get("qualified_prop_count") or 0),
            "top_card_count": len(primary),
            "requested_top_n": int((board.get("qualification_policy") or {}).get("top_n_requested") or policy.get("top_n", 5)),
            "exact_line_multibook_group_count": audit["exact_line_multibook_group_count"],
        },
        "pipeline_result": pipeline,
        "lineage": {
            "step11c_frozen_sha": STEP11C_FROZEN_HEAD_SHA,
            "step11b_frozen_sha": STEP11B_FROZEN_HEAD_SHA,
            "step11a_frozen_sha": STEP11A_FROZEN_HEAD_SHA,
            "step10_frozen_sha": STEP10_FROZEN_HEAD_SHA,
            "provider_bridge_hashes": bridge_hashes,
            "step10_pipeline_content_sha256": pipeline.get("pipeline_content_sha256"),
            "step10c_snapshot_content_sha256": (
                (pipeline.get("lineage") or {}).get("step10c_snapshot_content_sha256")
            ),
            "step9_ranking_content_sha256": board.get("ranking_content_sha256"),
        },
        "guardrails": {
            "shadow_only": True,
            "sportsbook_network_fetch_performed": True,
            "sportsbook_http_methods": ["GET"],
            "authentication_used": False,
            "cookies_used": False,
            "wager_action_performed": False,
            "paid_odds_vendor_used": False,
            "exact_line_consensus_required": True,
            "different_lines_blended": False,
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "vig_removed_in_frozen_step9": True,
            "edge_calculated_in_frozen_step9": True,
            "expected_value_calculated_in_frozen_step9": True,
            "cross_sportsbook_consensus_calculated_in_frozen_step9": True,
            "cross_prop_ranking_calculated_in_frozen_step9": True,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "public_fastapi_route_added": False,
        },
    }
    surface = {
        key: value for key, value in result.items()
        if key not in {"generated_at_utc", "shadow_board_content_sha256"}
    }
    result["shadow_board_content_sha256"] = _canonical_hash(surface)
    _assert_safe_environment(env)
    return result
