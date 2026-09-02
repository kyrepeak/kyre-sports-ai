"""MLB Step 19B — live sportsbook market-feed aggregation.

This module reuses the already-certified read-only FanDuel and DraftKings
collectors and exposes one provider-neutral feed surface. It deliberately does
not add sportsbook credentials, browser automation, persistence writes, model
mutation, actionable output, or wagering. Step 19C remains the authority for
new event/player identity-matching logic; Step 19B only preserves identities
already established by the underlying certified collectors.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any

from sports_api.collectors.mlb_draftkings_provider import (
    MLBDraftKingsProviderNotReadyError,
    collect_draftkings_provider_snapshots,
)
from sports_api.collectors.mlb_fanduel_direct import collect_live_mlb_game_odds
from sports_api.collectors.mlb_fanduel_player_props import (
    SUPPORTED_MARKET_TYPES,
    collect_live_mlb_player_props,
)
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10_MARKER,
    FINAL_FREEZE_STATUS as STEP10_STATUS,
)
from sports_api.mlb_step11a_provider_contract_v1 import (
    build_market_provider_game_snapshot,
    validate_market_provider_game_snapshot,
)

DATA_TYPE = "mlb_step19b_live_market_feed_v1"
SCHEMA_VERSION = 1
STEP19B_BASE_MAIN_SHA = "9324b1e0daac20a948ccf8c452aa801adf36adf0"
FEED_STATUS = "STEP19B_LIVE_MARKET_FEED_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP19B_LIVE_MARKET_FEED_GREEN"

FANDUEL_PROVIDER_KEY = "fanduel"
FANDUEL_PROVIDER_NAME = "FanDuel"
DRAFTKINGS_PROVIDER_KEY = "draftkings"
DRAFTKINGS_PROVIDER_NAME = "DraftKings"
FANDUEL_TRANSPORT = "anonymous_public_get_only"


class MLBLiveMarketFeedError(RuntimeError):
    """The Step 19B aggregation boundary received malformed local input."""


def feed_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step19b_base_main_sha": STEP19B_BASE_MAIN_SHA,
        "feed_status": FEED_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "providers_supported": [FANDUEL_PROVIDER_KEY, DRAFTKINGS_PROVIDER_KEY],
        "real_sportsbook_network_reads_allowed": True,
        "http_methods_allowed": ["GET"],
        "fan_duel_game_odds_reused": True,
        "fan_duel_exact_mlbam_player_props_reused": True,
        "draftkings_step11a_snapshots_reused": True,
        "new_identity_matching_added_by_step19b": False,
        "fuzzy_matching_added_by_step19b": False,
        "price_fabrication_allowed": False,
        "sportsbook_credentials_added": False,
        "browser_automation_added": False,
        "production_runtime_wiring_added_by_step19b": False,
        "persistence_schema_changed_by_step19b": False,
        "production_database_writes_enabled": False,
        "model_probability_mutation_enabled": False,
        "projection_mutation_enabled": False,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
    }


def _utc_z(value: Any, field: str) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
        except ValueError as exc:
            raise MLBLiveMarketFeedError(f"{field} is not valid ISO-8601") from exc
    else:
        raise MLBLiveMarketFeedError(f"{field} is required")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MLBLiveMarketFeedError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MLBLiveMarketFeedError(f"{field} is required")
    return text


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise MLBLiveMarketFeedError(f"{field} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise MLBLiveMarketFeedError(f"{field} must be a positive integer") from exc
    if result <= 0:
        raise MLBLiveMarketFeedError(f"{field} must be a positive integer")
    return result


def _american_odds(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise MLBLiveMarketFeedError(f"{field} must be integer American odds")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise MLBLiveMarketFeedError(f"{field} must be integer American odds") from exc
    if abs(result) < 100 or abs(result) > 100_000:
        raise MLBLiveMarketFeedError(f"{field} is outside supported American-odds bounds")
    return result


def _positive_line(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise MLBLiveMarketFeedError(f"{field} must be positive numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise MLBLiveMarketFeedError(f"{field} must be positive numeric") from exc
    if not math.isfinite(result) or result <= 0 or result > 1000:
        raise MLBLiveMarketFeedError(f"{field} is outside supported bounds")
    return result


def _normalized_market_times(markets: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for market_name, raw_market in markets.items():
        if not isinstance(raw_market, Mapping):
            raise MLBLiveMarketFeedError(f"{market_name} must be a mapping")
        market = dict(raw_market)
        if market.get("market_time_utc") is not None:
            market["market_time_utc"] = _utc_z(market["market_time_utc"], f"{market_name}.market_time_utc")
        normalized[str(market_name)] = market
    return normalized


def _fanduel_game_snapshot(
    game: Mapping[str, Any],
    *,
    observed_at_utc: str,
    source_collected_at_utc: str,
) -> dict[str, Any]:
    if str(game.get("sportsbook") or "").strip() != FANDUEL_PROVIDER_NAME:
        raise MLBLiveMarketFeedError("FanDuel game record has unexpected sportsbook")
    match_method = _text(game.get("official_schedule_match"), "official_schedule_match")
    if match_method not in {"teams_exact", "teams_and_nearest_start"}:
        raise MLBLiveMarketFeedError("FanDuel game record lacks certified official schedule reconciliation")
    markets = game.get("markets")
    if not isinstance(markets, Mapping) or not markets:
        raise MLBLiveMarketFeedError("FanDuel game record has no priced core markets")
    snapshot = build_market_provider_game_snapshot(
        provider_key=FANDUEL_PROVIDER_KEY,
        provider_name=FANDUEL_PROVIDER_NAME,
        provider_event_id=_text(game.get("sportsbook_event_id"), "sportsbook_event_id"),
        official_game_id=_positive_int(game.get("official_game_id"), "official_game_id"),
        observed_at_utc=observed_at_utc,
        source_collected_at_utc=source_collected_at_utc,
        market_phase="PREGAME",
        transport=FANDUEL_TRANSPORT,
        source_payload_sha256=_hash(dict(game)),
        markets=_normalized_market_times(markets),
        source_complete=True,
        exact_official_game_id_verified=True,
        fuzzy_matching_used=False,
        synthetic_game_id_used=False,
        price_fabrication_used=False,
        step10_final_freeze_status=STEP10_STATUS,
        step10_final_certification_marker=STEP10_MARKER,
    )
    validation = validate_market_provider_game_snapshot(snapshot)
    if validation.get("snapshot_valid") is not True:
        raise MLBLiveMarketFeedError(f"FanDuel Step11A snapshot validation failed: {validation.get('failures')}")
    snapshot["identity_provenance"] = {
        "reused_existing_collector": "sports_api.collectors.mlb_fanduel_direct",
        "official_schedule_match": match_method,
        "new_step19b_identity_matching": False,
    }
    return snapshot


def _normalized_fanduel_prop(prop: Mapping[str, Any]) -> dict[str, Any]:
    if str(prop.get("sportsbook") or "").strip() != FANDUEL_PROVIDER_NAME:
        raise MLBLiveMarketFeedError("FanDuel prop record has unexpected sportsbook")
    market_type = _text(prop.get("market_type"), "market_type")
    if market_type not in SUPPORTED_MARKET_TYPES:
        raise MLBLiveMarketFeedError(f"unsupported FanDuel prop market_type: {market_type}")
    result = {
        "provider_key": FANDUEL_PROVIDER_KEY,
        "provider_name": FANDUEL_PROVIDER_NAME,
        "official_game_id": _positive_int(prop.get("official_game_id"), "official_game_id"),
        "official_player_id": _positive_int(prop.get("official_player_id"), "official_player_id"),
        "player_name": str(prop.get("player_name") or "").strip() or None,
        "market_type": market_type,
        "line": _positive_line(prop.get("line"), "line"),
        "over_odds": _american_odds(prop.get("over_odds"), "over_odds"),
        "under_odds": _american_odds(prop.get("under_odds"), "under_odds"),
        "source_event_id": _text(prop.get("source_event_id"), "source_event_id"),
        "source_market_id": _text(prop.get("source_market_id"), "source_market_id"),
        "exact_official_game_id_verified": True,
        "exact_official_player_id_verified": True,
        "player_name_matching_used": False,
        "fuzzy_matching_used": False,
        "price_fabrication_used": False,
        "identity_provenance": {
            "reused_existing_collector": "sports_api.collectors.mlb_fanduel_player_props",
            "new_step19b_identity_matching": False,
        },
    }
    result["record_key"] = (
        f"mlb:{result['official_game_id']}:player:{result['official_player_id']}:"
        f"provider:{FANDUEL_PROVIDER_KEY}:market:{market_type}:source:{result['source_market_id']}"
    )
    result["snapshot_sha256"] = _hash(result)
    return result


def _dedupe_game_snapshots(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[tuple[str, str, int, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row["provider_key"]),
            str(row["provider_event_id"]),
            int(row["official_game_id"]),
            str(row["market_phase"]),
        )
        groups.setdefault(key, []).append(row)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for key, matches in groups.items():
        if len(matches) == 1:
            accepted.append(matches[0])
        else:
            rejected.append({
                "kind": "duplicate_game_market_identity",
                "provider_key": key[0],
                "provider_event_id": key[1],
                "official_game_id": key[2],
                "market_phase": key[3],
                "count": len(matches),
            })
    accepted.sort(key=lambda row: (int(row["official_game_id"]), str(row["provider_key"]), str(row["provider_event_id"])))
    return accepted, rejected


def _dedupe_player_props(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[tuple[str, int, int, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row["provider_key"]),
            int(row["official_game_id"]),
            int(row["official_player_id"]),
            str(row["market_type"]),
        )
        groups.setdefault(key, []).append(row)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for key, matches in groups.items():
        if len(matches) == 1:
            accepted.append(matches[0])
        else:
            rejected.append({
                "kind": "duplicate_player_prop_identity",
                "provider_key": key[0],
                "official_game_id": key[1],
                "official_player_id": key[2],
                "market_type": key[3],
                "count": len(matches),
            })
    accepted.sort(key=lambda row: (int(row["official_game_id"]), int(row["official_player_id"]), str(row["market_type"])))
    return accepted, rejected


def collect_live_mlb_market_feed(
    *,
    now_utc: datetime | None = None,
    max_events: int = 30,
    include_fanduel_game_odds: bool = True,
    include_fanduel_player_props: bool = True,
    include_draftkings: bool = True,
    fanduel_game_collector: Callable[..., Mapping[str, Any]] | None = None,
    fanduel_prop_collector: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_collector: Callable[..., Mapping[str, Any]] | None = None,
    draftkings_kwargs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect one read-only Step 19B market-feed envelope.

    Provider surfaces are isolated: one upstream can be unavailable or fail
    without contaminating valid records from another provider. Malformed records
    are omitted and reported. No fallback prices or synthetic identities are
    created.
    """
    now = now_utc or datetime.now(timezone.utc)
    observed = _utc_z(now, "now_utc")
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events <= 0:
        raise MLBLiveMarketFeedError("max_events must be a positive integer")
    for value, name in (
        (include_fanduel_game_odds, "include_fanduel_game_odds"),
        (include_fanduel_player_props, "include_fanduel_player_props"),
        (include_draftkings, "include_draftkings"),
    ):
        if not isinstance(value, bool):
            raise MLBLiveMarketFeedError(f"{name} must be boolean")

    statuses: list[dict[str, Any]] = []
    game_candidates: list[dict[str, Any]] = []
    prop_candidates: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []

    if include_fanduel_game_odds:
        collector = fanduel_game_collector or collect_live_mlb_game_odds
        try:
            collection = dict(collector(now_utc=now, max_events=max_events))
            source_collected = _utc_z(collection.get("collected_at_utc") or observed, "FanDuel collected_at_utc")
            accepted = 0
            for game in collection.get("games") or []:
                if not isinstance(game, Mapping):
                    rejected_records.append({"surface": "fanduel_game_odds", "reason": "game_not_mapping"})
                    continue
                try:
                    game_candidates.append(_fanduel_game_snapshot(game, observed_at_utc=observed, source_collected_at_utc=source_collected))
                    accepted += 1
                except Exception as exc:
                    rejected_records.append({
                        "surface": "fanduel_game_odds",
                        "official_game_id": game.get("official_game_id"),
                        "provider_event_id": game.get("sportsbook_event_id"),
                        "reason": f"{type(exc).__name__}: {exc}",
                    })
            statuses.append({
                "surface": "fanduel_game_odds",
                "provider_key": FANDUEL_PROVIDER_KEY,
                "status": "success",
                "record_count": accepted,
                "upstream_rejected_count": len(collection.get("rejected_events") or []),
            })
        except Exception as exc:
            statuses.append({
                "surface": "fanduel_game_odds",
                "provider_key": FANDUEL_PROVIDER_KEY,
                "status": "error",
                "record_count": 0,
                "reason": f"{type(exc).__name__}: {exc}",
            })

    if include_fanduel_player_props:
        collector = fanduel_prop_collector or collect_live_mlb_player_props
        try:
            collection = dict(collector(now_utc=now, max_events=max_events))
            accepted = 0
            for prop in collection.get("props") or []:
                if not isinstance(prop, Mapping):
                    rejected_records.append({"surface": "fanduel_player_props", "reason": "prop_not_mapping"})
                    continue
                try:
                    prop_candidates.append(_normalized_fanduel_prop(prop))
                    accepted += 1
                except Exception as exc:
                    rejected_records.append({
                        "surface": "fanduel_player_props",
                        "official_game_id": prop.get("official_game_id"),
                        "official_player_id": prop.get("official_player_id"),
                        "market_type": prop.get("market_type"),
                        "reason": f"{type(exc).__name__}: {exc}",
                    })
            statuses.append({
                "surface": "fanduel_player_props",
                "provider_key": FANDUEL_PROVIDER_KEY,
                "status": "success",
                "record_count": accepted,
                "upstream_rejected_count": int(collection.get("rejected_prop_count") or 0) + int(collection.get("rejected_event_count") or 0),
            })
        except Exception as exc:
            statuses.append({
                "surface": "fanduel_player_props",
                "provider_key": FANDUEL_PROVIDER_KEY,
                "status": "error",
                "record_count": 0,
                "reason": f"{type(exc).__name__}: {exc}",
            })

    if include_draftkings:
        collector = draftkings_collector or collect_draftkings_provider_snapshots
        kwargs = dict(draftkings_kwargs or {})
        if "market_phase" in kwargs and kwargs["market_phase"] != "PREGAME":
            raise MLBLiveMarketFeedError("Step 19B DraftKings aggregation currently requires PREGAME")
        kwargs["market_phase"] = "PREGAME"
        kwargs.setdefault("now_utc", now)
        try:
            collection = dict(collector(**kwargs))
            accepted = 0
            for snapshot in collection.get("snapshots") or []:
                if not isinstance(snapshot, Mapping):
                    rejected_records.append({"surface": "draftkings_game_odds", "reason": "snapshot_not_mapping"})
                    continue
                validation = validate_market_provider_game_snapshot(snapshot)
                if validation.get("snapshot_valid") is not True:
                    rejected_records.append({
                        "surface": "draftkings_game_odds",
                        "official_game_id": snapshot.get("official_game_id"),
                        "provider_event_id": snapshot.get("provider_event_id"),
                        "reason": f"step11a_validation_failed:{validation.get('failures')}",
                    })
                    continue
                game_candidates.append(dict(snapshot))
                accepted += 1
            statuses.append({
                "surface": "draftkings_game_odds",
                "provider_key": DRAFTKINGS_PROVIDER_KEY,
                "status": "success",
                "record_count": accepted,
                "upstream_rejected_count": int(collection.get("rejected_snapshot_count") or 0),
            })
        except MLBDraftKingsProviderNotReadyError as exc:
            statuses.append({
                "surface": "draftkings_game_odds",
                "provider_key": DRAFTKINGS_PROVIDER_KEY,
                "status": "not_ready",
                "record_count": 0,
                "reason": f"{type(exc).__name__}: {exc}",
            })
        except Exception as exc:
            statuses.append({
                "surface": "draftkings_game_odds",
                "provider_key": DRAFTKINGS_PROVIDER_KEY,
                "status": "error",
                "record_count": 0,
                "reason": f"{type(exc).__name__}: {exc}",
            })

    games, duplicate_game_rejections = _dedupe_game_snapshots(game_candidates)
    props, duplicate_prop_rejections = _dedupe_player_props(prop_candidates)
    rejected_records.extend(duplicate_game_rejections)
    rejected_records.extend(duplicate_prop_rejections)

    successful_surfaces = [row for row in statuses if row["status"] == "success"]
    not_ready_surfaces = [row for row in statuses if row["status"] == "not_ready"]
    error_surfaces = [row for row in statuses if row["status"] == "error"]
    providers_with_data = sorted({str(row["provider_key"]) for row in games} | {str(row["provider_key"]) for row in props})

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "feed_status": FEED_STATUS,
        "collected_at_utc": observed,
        "enabled_surface_count": sum((include_fanduel_game_odds, include_fanduel_player_props, include_draftkings)),
        "successful_surface_count": len(successful_surfaces),
        "not_ready_surface_count": len(not_ready_surfaces),
        "error_surface_count": len(error_surfaces),
        "providers_with_data": providers_with_data,
        "provider_surface_statuses": statuses,
        "game_market_snapshot_count": len(games),
        "player_prop_count": len(props),
        "live_market_data_present": bool(games or props),
        "game_market_snapshots": games,
        "player_props": props,
        "rejected_record_count": len(rejected_records),
        "rejected_records": rejected_records,
        "network_reads_only": True,
        "http_methods": ["GET"],
        "new_step19b_identity_matching": False,
        "price_fabrication_used": False,
        "production_runtime_wiring": False,
        "production_database_writes": False,
        "model_probability_mutation": False,
        "projection_mutation": False,
        "actionable_output": False,
        "wagering": False,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP19B_BASE_MAIN_SHA",
    "FEED_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "MLBLiveMarketFeedError",
    "feed_manifest",
    "collect_live_mlb_market_feed",
]
