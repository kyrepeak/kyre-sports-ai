"""WNBA Step 6G DraftKings compatibility and shadow-ingestion gate.

Step 6F live-verified the four public DraftKings WNBA player-prop endpoints
needed by the model. Step 6G freezes those exact endpoint identities and runs a
read-only shadow collection through the existing Step 6D normalizer and the
Step 6C owned-feed validator. It does not write the production feed and it does
not enable direct sync or the WNBA production runtime.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sports_api.collectors.wnba_draftkings_direct import fetch_draftkings_canonical_feed
from sports_api.collectors.wnba_kyre_market_feed import validate_kyre_market_feed
from sports_api.wnba_draftkings_prop_market_discovery import WNBA_LEAGUE_ID

MODEL_SOURCE = "Kyre Sports API WNBA Step 6G DraftKings compatibility + shadow ingestion"
MODEL_VERSION = "wnba_step_6g_draftkings_shadow_ingestion_v1"
SCHEMA_VERSION = MODEL_VERSION

REQUIRED_STATS = ("points", "rebounds", "assists", "pra")
FROZEN_ENDPOINTS = {
    "points": {
        "category_id": "1215",
        "subcategory_id": "12488",
        "url": "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusva/v1/leagues/94682/categories/1215/subcategories/12488",
    },
    "rebounds": {
        "category_id": "1216",
        "subcategory_id": "12492",
        "url": "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusva/v1/leagues/94682/categories/1216/subcategories/12492",
    },
    "assists": {
        "category_id": "1217",
        "subcategory_id": "12495",
        "url": "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusva/v1/leagues/94682/categories/1217/subcategories/12495",
    },
    "pra": {
        "category_id": "583",
        "subcategory_id": "5001",
        "url": "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusva/v1/leagues/94682/categories/583/subcategories/5001",
    },
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def frozen_draftkings_urls() -> list[str]:
    return [FROZEN_ENDPOINTS[stat]["url"] for stat in REQUIRED_STATS]


def get_shadow_readiness() -> dict[str, Any]:
    """Network-free readiness contract for the Step 6G shadow gate."""
    endpoint_rows = []
    for stat in REQUIRED_STATS:
        row = FROZEN_ENDPOINTS[stat]
        endpoint_rows.append(
            {
                "stat": stat,
                "league_id": WNBA_LEAGUE_ID,
                "category_id": row["category_id"],
                "subcategory_id": row["subcategory_id"],
                "host": "sportsbook-nash.draftkings.com",
            }
        )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6g_shadow_readiness",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "frozen_endpoint_count": len(endpoint_rows),
        "required_stats": list(REQUIRED_STATS),
        "frozen_endpoints": endpoint_rows,
        "shadow_probe_available": True,
        "automatic_sync_enabled_by_step6g": False,
        "production_runtime_enabled_by_step6g": False,
        "safety": {
            "sportsbook_http_methods": ["GET"],
            "authentication_used": False,
            "cookies_used": False,
            "wager_action_performed": False,
            "paid_odds_vendor_used": False,
            "production_feed_written": False,
            "monte_carlo_run": False,
        },
    }


def _offer_key(row: Mapping[str, Any]) -> tuple[str, str, float, str]:
    return (
        str(row.get("source_event_id") or ""),
        str(row.get("player_name") or "").strip().casefold(),
        float(row.get("line")),
        str(row.get("stat") or "").strip().casefold(),
    )


def validate_shadow_feed(feed: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a Step 6D feed without persisting it to the Step 6C live path."""
    validated = validate_kyre_market_feed(dict(feed))
    offers = validated["offers"]
    stat_sides: dict[str, int] = Counter()
    player_lines: dict[str, set[tuple[str, str, float]]] = defaultdict(set)
    pair_sides: dict[tuple[str, str, float, str], set[str]] = defaultdict(set)
    market_events: dict[str, set[str]] = defaultdict(set)
    source_offer_ids: set[str] = set()
    duplicate_source_offer_ids = 0
    blockers: list[str] = []

    for index, row in enumerate(offers):
        stat = str(row.get("stat") or "").strip().casefold()
        side = str(row.get("side") or "").strip().casefold()
        player = str(row.get("player_name") or "").strip()
        event_id = str(row.get("source_event_id") or "").strip()
        market_id = str(row.get("source_market_id") or "").strip()
        offer_id = str(row.get("source_offer_id") or "").strip()
        sportsbook = str(row.get("sportsbook") or "").strip().casefold()
        line = row.get("line")

        if stat not in REQUIRED_STATS:
            blockers.append(f"offer_{index}_unsupported_stat")
            continue
        if side not in {"over", "under"}:
            blockers.append(f"offer_{index}_invalid_side")
        if not player or len(player) > 100:
            blockers.append(f"offer_{index}_invalid_player_identity")
        if not event_id:
            blockers.append(f"offer_{index}_missing_game_identity")
        if not market_id:
            blockers.append(f"offer_{index}_missing_market_identity")
        if not offer_id:
            blockers.append(f"offer_{index}_missing_offer_identity")
        elif offer_id in source_offer_ids:
            duplicate_source_offer_ids += 1
        else:
            source_offer_ids.add(offer_id)
        if sportsbook != "draftkings":
            blockers.append(f"offer_{index}_wrong_sportsbook")
        if not isinstance(line, (int, float)) or isinstance(line, bool) or not 0 <= float(line) <= 500:
            blockers.append(f"offer_{index}_invalid_line")
            continue
        if not (row.get("american_odds") is not None or row.get("decimal_odds") is not None):
            blockers.append(f"offer_{index}_missing_odds")

        stat_sides[stat] += 1
        player_lines[stat].add((event_id, player.casefold(), float(line)))
        pair_sides[_offer_key(row)].add(side)
        if market_id and event_id:
            market_events[market_id].add(event_id)

    missing_stats = [stat for stat in REQUIRED_STATS if stat_sides[stat] <= 0]
    for stat in missing_stats:
        blockers.append(f"missing_stat_{stat}")

    incomplete_pairs = [key for key, sides in pair_sides.items() if sides != {"over", "under"}]
    cross_game_markets = [market_id for market_id, events in market_events.items() if len(events) > 1]
    if incomplete_pairs:
        blockers.append("incomplete_over_under_pairs")
    if cross_game_markets:
        blockers.append("cross_game_market_drift")
    if duplicate_source_offer_ids:
        blockers.append("duplicate_source_offer_ids")

    stat_summary = {
        stat: {
            "offer_side_count": int(stat_sides[stat]),
            "two_sided_player_line_count": len(player_lines[stat]),
        }
        for stat in REQUIRED_STATS
    }
    expected_side_total = sum(row["two_sided_player_line_count"] * 2 for row in stat_summary.values())
    two_sided_pair_count = sum(1 for sides in pair_sides.values() if sides == {"over", "under"})
    downstream_contract = {
        "step6c_feed_schema_valid": True,
        "feed_format": validated["feed_format"],
        "odds_format": validated["odds_format"],
        "offer_count": len(offers),
        "all_four_stats_present": not missing_stats,
        "all_player_lines_two_sided": len(incomplete_pairs) == 0 and len(pair_sides) > 0,
        "game_identity_present": not any(item.endswith("missing_game_identity") for item in blockers),
        "player_identity_present": not any(item.endswith("invalid_player_identity") for item in blockers),
        "market_identity_present": not any(item.endswith("missing_market_identity") for item in blockers),
        "no_cross_game_market_drift": len(cross_game_markets) == 0,
        "no_duplicate_source_offer_ids": duplicate_source_offer_ids == 0,
    }
    ready = bool(offers) and not blockers and expected_side_total == len(offers) and two_sided_pair_count == sum(
        row["two_sided_player_line_count"] for row in stat_summary.values()
    )
    identity = {
        "date": validated["date"],
        "season": validated["season"],
        "captured_at_utc": validated["captured_at_utc"],
        "offer_count": len(offers),
        "stat_summary": stat_summary,
        "ready_for_auto_sync": ready,
    }
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6g_shadow_validation",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "date": validated["date"],
        "season": validated["season"],
        "offer_side_count": len(offers),
        "two_sided_player_line_count": len(pair_sides),
        "verified_event_count": len({key[0] for key in pair_sides if key[0]}),
        "stat_summary": stat_summary,
        "downstream_contract": downstream_contract,
        "blockers": sorted(set(blockers)),
        "incomplete_pair_count": len(incomplete_pairs),
        "cross_game_market_count": len(cross_game_markets),
        "duplicate_source_offer_id_count": duplicate_source_offer_ids,
        "ready_for_auto_sync": ready,
        "validation_fingerprint_sha256": _hash(identity),
        "safety": {
            "production_feed_written": False,
            "direct_sync_enablement_changed": False,
            "production_runtime_enablement_changed": False,
            "monte_carlo_run": False,
        },
    }


def run_shadow_ingestion(
    *,
    date: str,
    season: int,
    requester: Callable[..., Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """GET the frozen endpoints, normalize via Step 6D, validate in memory only."""
    feed = fetch_draftkings_canonical_feed(
        date=date,
        season=season,
        urls=frozen_draftkings_urls(),
        requester=requester,
        env=env,
    )
    report = validate_shadow_feed(feed)
    report["source_summary"] = [dict(row) for row in (feed.get("source_summary") or [])]
    report["frozen_endpoint_count"] = len(FROZEN_ENDPOINTS)
    report["wnba_league_id"] = WNBA_LEAGUE_ID
    report["safety"].update(
        {
            "sportsbook_http_methods": ["GET"],
            "authentication_used": False,
            "cookies_used": False,
            "wager_action_performed": False,
            "paid_odds_vendor_used": False,
        }
    )
    return report
