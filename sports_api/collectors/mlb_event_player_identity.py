"""MLB Step 19C — canonical sportsbook event/player identity registry.

Step 19C consumes the already-certified Step 19A official MLB slate and Step
19B provider-neutral market feed. It does not scrape providers, mutate prices,
run models, persist state, or emit actionable/wagering output.

The contract is deliberately strict:
* sportsbook event claims must carry a certified exact official MLB game ID;
* the game ID must exist on the supplied official slate;
* a provider event is one-to-one with one official game on that slate;
* player-prop claims must carry an exact MLBAM player ID and reference a
  verified provider event for the same official game;
* provider/player name fuzzy matching is never used;
* contradictions and ambiguity fail closed instead of being guessed through.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from sports_api.mlb_official_game_id_join_v1 import (
    MLBOfficialGameIDJoinError,
    canonical_official_game_id,
)


DATA_TYPE = "mlb_step19c_event_player_identity_registry_v1"
SCHEMA_VERSION = 1
STEP19C_BASE_MAIN_SHA = "62f3259f90975e6c636bae473c5feb70637165ed"
REGISTRY_STATUS = "STEP19C_EVENT_PLAYER_IDENTITY_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP19C_EVENT_PLAYER_IDENTITY_GREEN"


class MLBEventPlayerIdentityError(ValueError):
    """Raised when the Step 19C local identity envelope is malformed."""


def identity_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step19c_base_main_sha": STEP19C_BASE_MAIN_SHA,
        "registry_status": REGISTRY_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step19a_official_slate_required": True,
        "step19b_market_feed_required": True,
        "exact_official_game_id_required": True,
        "exact_official_player_id_required_for_props": True,
        "provider_event_one_to_one_required": True,
        "player_name_matching_allowed": False,
        "team_name_fuzzy_matching_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "synthetic_player_id_allowed": False,
        "price_fabrication_allowed": False,
        "network_reads_added_by_step19c": False,
        "production_runtime_wiring_added_by_step19c": False,
        "production_database_writes_enabled": False,
        "model_probability_mutation_enabled": False,
        "projection_mutation_enabled": False,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
    }


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MLBEventPlayerIdentityError(f"{field} must be a mapping")
    return value


def _rows(value: Any, field: str) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise MLBEventPlayerIdentityError(f"{field} must be a list")
    result: list[Mapping[str, Any]] = []
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise MLBEventPlayerIdentityError(f"{field}[{index}] must be a mapping")
        result.append(row)
    return result


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise MLBEventPlayerIdentityError(f"{field} is required")
    return text


def _positive_int(value: Any, field: str) -> int:
    try:
        return canonical_official_game_id(value)
    except MLBOfficialGameIDJoinError as exc:
        raise MLBEventPlayerIdentityError(f"{field}: {exc}") from exc


def _bool_true(row: Mapping[str, Any], field: str) -> bool:
    return row.get(field) is True


def _bool_false(row: Mapping[str, Any], field: str) -> bool:
    return row.get(field) is False


def _official_game_index(official_slate: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    sport = str(official_slate.get("sport") or "").strip().upper()
    if sport != "MLB":
        raise MLBEventPlayerIdentityError("official_slate.sport must be MLB")

    declared_count = official_slate.get("game_count")
    games = _rows(official_slate.get("games"), "official_slate.games")
    if isinstance(declared_count, bool) or not isinstance(declared_count, int) or declared_count < 0:
        raise MLBEventPlayerIdentityError("official_slate.game_count must be a non-negative integer")
    if declared_count != len(games):
        raise MLBEventPlayerIdentityError("official_slate.game_count does not match games")

    indexed: dict[int, dict[str, Any]] = {}
    for index, raw in enumerate(games):
        game_pk = _positive_int(raw.get("game_pk"), f"official_slate.games[{index}].game_pk")
        if game_pk in indexed:
            raise MLBEventPlayerIdentityError(f"duplicate official slate game_pk {game_pk}")

        away = _mapping(raw.get("away_team"), f"official_slate.games[{index}].away_team")
        home = _mapping(raw.get("home_team"), f"official_slate.games[{index}].home_team")
        away_id = _positive_int(away.get("id"), f"official_slate.games[{index}].away_team.id")
        home_id = _positive_int(home.get("id"), f"official_slate.games[{index}].home_team.id")
        if away_id == home_id:
            raise MLBEventPlayerIdentityError(f"official slate game {game_pk} has identical team IDs")

        indexed[game_pk] = {
            "game_pk": game_pk,
            "game_date": _text(raw.get("game_date"), f"official_slate.games[{index}].game_date"),
            "official_date": raw.get("official_date"),
            "status": _text(raw.get("status"), f"official_slate.games[{index}].status"),
            "status_detail": raw.get("status_detail"),
            "away_team": {"id": away_id, "name": _text(away.get("name"), "away_team.name")},
            "home_team": {"id": home_id, "name": _text(home.get("name"), "home_team.name")},
            "doubleheader": bool(raw.get("doubleheader")),
            "doubleheader_code": raw.get("doubleheader_code"),
            "game_number": raw.get("game_number"),
            "reschedule_date": raw.get("reschedule_date"),
            "is_postponed": raw.get("is_postponed") is True,
            "is_cancelled": raw.get("is_cancelled") is True,
        }
    return indexed


def _event_claim(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    provider_key = _text(row.get("provider_key"), f"game_market_snapshots[{index}].provider_key")
    provider_event_id = _text(
        row.get("provider_event_id"), f"game_market_snapshots[{index}].provider_event_id"
    )
    game_pk = _positive_int(
        row.get("official_game_id"), f"game_market_snapshots[{index}].official_game_id"
    )

    reasons: list[str] = []
    if not _bool_true(row, "exact_official_game_id_verified"):
        reasons.append("exact_official_game_id_not_verified")
    if not _bool_false(row, "fuzzy_matching_used"):
        reasons.append("fuzzy_matching_not_explicitly_false")
    if not _bool_false(row, "synthetic_game_id_used"):
        reasons.append("synthetic_game_id_not_explicitly_false")

    return {
        "provider_key": provider_key,
        "provider_name": str(row.get("provider_name") or "").strip() or None,
        "provider_event_id": provider_event_id,
        "official_game_id": game_pk,
        "source_index": index,
        "reasons": reasons,
    }


def _resolve_events(
    game_rows: list[Mapping[str, Any]],
    official_games: Mapping[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str], int]]:
    claims = [_event_claim(row, index) for index, row in enumerate(game_rows)]
    rejected: list[dict[str, Any]] = []

    by_event: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_game: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        by_event[(claim["provider_key"], claim["provider_event_id"])].append(claim)
        by_game[(claim["provider_key"], claim["official_game_id"])].append(claim)

    conflicted_indices: set[int] = set()
    for (provider_key, provider_event_id), matches in by_event.items():
        distinct_ids = sorted({int(match["official_game_id"]) for match in matches})
        if len(matches) > 1:
            conflicted_indices.update(int(match["source_index"]) for match in matches)
            rejected.append(
                {
                    "kind": "ambiguous_provider_event_claim",
                    "provider_key": provider_key,
                    "provider_event_id": provider_event_id,
                    "official_game_ids": distinct_ids,
                    "claim_count": len(matches),
                }
            )

    for (provider_key, game_pk), matches in by_game.items():
        event_ids = sorted({str(match["provider_event_id"]) for match in matches})
        if len(event_ids) > 1:
            conflicted_indices.update(int(match["source_index"]) for match in matches)
            rejected.append(
                {
                    "kind": "multiple_provider_events_for_official_game",
                    "provider_key": provider_key,
                    "official_game_id": game_pk,
                    "provider_event_ids": event_ids,
                }
            )

    resolved: list[dict[str, Any]] = []
    lookup: dict[tuple[str, str], int] = {}
    for claim in claims:
        index = int(claim["source_index"])
        if index in conflicted_indices:
            continue

        reasons = list(claim["reasons"])
        game_pk = int(claim["official_game_id"])
        game = official_games.get(game_pk)
        if game is None:
            reasons.append("official_game_not_in_slate")
        if reasons:
            rejected.append(
                {
                    "kind": "event_identity_rejected",
                    "provider_key": claim["provider_key"],
                    "provider_event_id": claim["provider_event_id"],
                    "official_game_id": game_pk,
                    "source_index": index,
                    "reasons": reasons,
                }
            )
            continue

        assert game is not None
        key = (str(claim["provider_key"]), str(claim["provider_event_id"]))
        lookup[key] = game_pk
        resolved.append(
            {
                "provider_key": claim["provider_key"],
                "provider_name": claim["provider_name"],
                "provider_event_id": claim["provider_event_id"],
                "official_game_id": game_pk,
                "match_method": "certified_exact_official_game_id_crosschecked_to_step19a_slate",
                "official_game": dict(game),
                "fuzzy_matching_used": False,
                "synthetic_game_id_used": False,
            }
        )

    resolved.sort(
        key=lambda row: (
            int(row["official_game_id"]),
            str(row["provider_key"]),
            str(row["provider_event_id"]),
        )
    )
    rejected.sort(
        key=lambda row: (
            str(row.get("provider_key") or ""),
            str(row.get("provider_event_id") or ""),
            str(row.get("kind") or ""),
        )
    )
    return resolved, rejected, lookup


def _player_claim(
    row: Mapping[str, Any],
    index: int,
    event_lookup: Mapping[tuple[str, str], int],
    official_games: Mapping[int, dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    provider_key = _text(row.get("provider_key"), f"player_props[{index}].provider_key")
    source_event_id = _text(row.get("source_event_id"), f"player_props[{index}].source_event_id")
    source_market_id = _text(row.get("source_market_id"), f"player_props[{index}].source_market_id")
    game_pk = _positive_int(row.get("official_game_id"), f"player_props[{index}].official_game_id")
    player_id = _positive_int(
        row.get("official_player_id"), f"player_props[{index}].official_player_id"
    )

    reasons: list[str] = []
    if not _bool_true(row, "exact_official_game_id_verified"):
        reasons.append("exact_official_game_id_not_verified")
    if not _bool_true(row, "exact_official_player_id_verified"):
        reasons.append("exact_official_player_id_not_verified")
    if not _bool_false(row, "player_name_matching_used"):
        reasons.append("player_name_matching_not_explicitly_false")
    if not _bool_false(row, "fuzzy_matching_used"):
        reasons.append("fuzzy_matching_not_explicitly_false")
    if game_pk not in official_games:
        reasons.append("official_game_not_in_slate")

    mapped_game = event_lookup.get((provider_key, source_event_id))
    if mapped_game is None:
        reasons.append("provider_event_not_verified")
    elif int(mapped_game) != game_pk:
        reasons.append("provider_event_game_conflict")

    if reasons:
        return None, {
            "kind": "player_identity_rejected",
            "provider_key": provider_key,
            "source_event_id": source_event_id,
            "source_market_id": source_market_id,
            "official_game_id": game_pk,
            "official_player_id": player_id,
            "source_index": index,
            "reasons": reasons,
        }

    return {
        "provider_key": provider_key,
        "provider_name": str(row.get("provider_name") or "").strip() or None,
        "source_event_id": source_event_id,
        "source_market_id": source_market_id,
        "official_game_id": game_pk,
        "official_player_id": player_id,
        "player_name": str(row.get("player_name") or "").strip() or None,
        "market_type": _text(row.get("market_type"), f"player_props[{index}].market_type"),
        "match_method": "certified_exact_mlbam_player_id_crosschecked_to_verified_provider_event",
        "player_name_matching_used": False,
        "fuzzy_matching_used": False,
        "synthetic_player_id_used": False,
    }, None


def _resolve_players(
    prop_rows: list[Mapping[str, Any]],
    event_lookup: Mapping[tuple[str, str], int],
    official_games: Mapping[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted_claims: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    market_claims: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(prop_rows):
        claim, failure = _player_claim(row, index, event_lookup, official_games)
        if failure is not None:
            rejected.append(failure)
            continue
        assert claim is not None
        market_key = (
            str(claim["provider_key"]),
            str(claim["source_event_id"]),
            str(claim["source_market_id"]),
        )
        market_claims[market_key].append(claim)

    for market_key, matches in market_claims.items():
        identities = {
            (int(match["official_game_id"]), int(match["official_player_id"]))
            for match in matches
        }
        if len(matches) != 1 or len(identities) != 1:
            rejected.append(
                {
                    "kind": "ambiguous_prop_market_player_claim",
                    "provider_key": market_key[0],
                    "source_event_id": market_key[1],
                    "source_market_id": market_key[2],
                    "official_identities": sorted(
                        [list(identity) for identity in identities]
                    ),
                    "claim_count": len(matches),
                }
            )
            continue
        accepted_claims.append(matches[0])

    grouped: dict[tuple[str, str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for claim in accepted_claims:
        grouped[
            (
                str(claim["provider_key"]),
                str(claim["source_event_id"]),
                int(claim["official_game_id"]),
                int(claim["official_player_id"]),
            )
        ].append(claim)

    resolved: list[dict[str, Any]] = []
    for key, matches in grouped.items():
        names = sorted({str(row["player_name"]) for row in matches if row.get("player_name")})
        if len(names) > 1:
            rejected.append(
                {
                    "kind": "conflicting_player_display_metadata",
                    "provider_key": key[0],
                    "source_event_id": key[1],
                    "official_game_id": key[2],
                    "official_player_id": key[3],
                    "player_names": names,
                }
            )
            continue

        resolved.append(
            {
                "provider_key": key[0],
                "provider_name": next(
                    (row["provider_name"] for row in matches if row.get("provider_name")), None
                ),
                "source_event_id": key[1],
                "official_game_id": key[2],
                "official_player_id": key[3],
                "player_name": names[0] if names else None,
                "source_market_ids": sorted({str(row["source_market_id"]) for row in matches}),
                "market_types": sorted({str(row["market_type"]) for row in matches}),
                "match_method": "certified_exact_mlbam_player_id_crosschecked_to_verified_provider_event",
                "player_name_matching_used": False,
                "fuzzy_matching_used": False,
                "synthetic_player_id_used": False,
            }
        )

    resolved.sort(
        key=lambda row: (
            int(row["official_game_id"]),
            int(row["official_player_id"]),
            str(row["provider_key"]),
            str(row["source_event_id"]),
        )
    )
    rejected.sort(
        key=lambda row: (
            str(row.get("provider_key") or ""),
            str(row.get("source_event_id") or ""),
            str(row.get("source_market_id") or ""),
            str(row.get("kind") or ""),
        )
    )
    return resolved, rejected


def build_mlb_event_player_identity_registry(
    *,
    official_slate: Mapping[str, Any],
    market_feed: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a fail-closed canonical identity registry from Step 19A + Step 19B.

    This function is pure: it performs no network reads and no writes. It trusts
    neither envelope blindly; every event game ID must be present on the supplied
    official slate, and every player prop must point through a verified provider
    event for the same official game.
    """
    slate = _mapping(official_slate, "official_slate")
    feed = _mapping(market_feed, "market_feed")
    official_games = _official_game_index(slate)

    game_rows = _rows(feed.get("game_market_snapshots"), "market_feed.game_market_snapshots")
    prop_rows = _rows(feed.get("player_props"), "market_feed.player_props")

    event_identities, rejected_events, event_lookup = _resolve_events(game_rows, official_games)
    player_identities, rejected_players = _resolve_players(prop_rows, event_lookup, official_games)

    providers = sorted(
        {
            str(row["provider_key"])
            for row in event_identities + player_identities
            if row.get("provider_key")
        }
    )
    unmatched_official_ids = sorted(
        set(official_games) - {int(row["official_game_id"]) for row in event_identities}
    )

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "registry_status": REGISTRY_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step19c_base_main_sha": STEP19C_BASE_MAIN_SHA,
        "official_slate_date": slate.get("slate_date"),
        "official_game_count": len(official_games),
        "market_game_claim_count": len(game_rows),
        "player_prop_claim_count": len(prop_rows),
        "event_identity_count": len(event_identities),
        "player_identity_count": len(player_identities),
        "rejected_event_identity_count": len(rejected_events),
        "rejected_player_identity_count": len(rejected_players),
        "providers_with_verified_identity": providers,
        "event_identities": event_identities,
        "player_identities": player_identities,
        "rejected_event_identities": rejected_events,
        "rejected_player_identities": rejected_players,
        "unmatched_official_game_ids": unmatched_official_ids,
        "identity_complete_for_all_market_games": len(event_identities) == len(game_rows)
        and not rejected_events,
        "fuzzy_matching_used": False,
        "player_name_matching_used": False,
        "synthetic_game_id_used": False,
        "synthetic_player_id_used": False,
        "price_fabrication_used": False,
        "network_reads_added_by_step19c": False,
        "production_runtime_wiring": False,
        "production_database_writes": False,
        "model_probability_mutation": False,
        "projection_mutation": False,
        "actionable_output": False,
        "wagering": False,
    }


__all__ = [
    "DATA_TYPE",
    "FINAL_CERTIFICATION_MARKER",
    "MLBEventPlayerIdentityError",
    "REGISTRY_STATUS",
    "SCHEMA_VERSION",
    "STEP19C_BASE_MAIN_SHA",
    "build_mlb_event_player_identity_registry",
    "identity_manifest",
]
