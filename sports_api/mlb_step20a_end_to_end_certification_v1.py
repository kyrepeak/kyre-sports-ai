"""MLB Step 20A — end-to-end certification of the frozen Step19 live-data chain.

Step20A is certification-only.  It proves that a Step19E restart-recovered bundle
can cross the already-existing MLB live-odds API/Streamlit consumer seam without
recollecting providers, changing identity, changing prices, or enabling any
production/actionable/wagering behavior.  Production wiring remains Step20B.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from sports_api.collectors import mlb_event_player_identity as step19c
from sports_api.collectors import mlb_live_market_feed as step19b
from sports_api.mlb_step11a_provider_contract_v1 import (
    validate_market_provider_game_snapshot,
)
from sports_api.mlb_step19e_production_persistence_validation_v1 import (
    RESULT_DATA_TYPE as STEP19E_RESULT_DATA_TYPE,
)

DATA_TYPE = "mlb_step20a_end_to_end_certification_v1"
SCHEMA_VERSION = 1
STEP20A_BASE_MAIN_SHA = "52e497ff9a3282918cbee8aca8926e9168443325"
CERTIFICATION_STATUS = "STEP20A_END_TO_END_CERTIFICATION_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP20A_END_TO_END_CERTIFICATION_GREEN"
EXISTING_API_DATA_TYPE = "mlb_live_odds_api_response_v1"
EXISTING_API_SCHEMA_VERSION = 1
EXISTING_CONSUMER_PATH = "/api/v1/mlb/odds"


class MLBStep20AEndToEndCertificationError(ValueError):
    """A recovered Step19 bundle cannot safely cross the frozen consumer seam."""


def certification_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step20a_base_main_sha": STEP20A_BASE_MAIN_SHA,
        "certification_status": CERTIFICATION_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step19e_recovery_required": True,
        "step19a_official_identity_rechecked": True,
        "step19b_market_contract_rechecked": True,
        "step19c_identity_registry_rechecked": True,
        "step19d_reliability_state_preserved": True,
        "step19e_restart_copy_integrity_rechecked": True,
        "existing_api_data_type": EXISTING_API_DATA_TYPE,
        "existing_api_schema_version": EXISTING_API_SCHEMA_VERSION,
        "existing_consumer_path": EXISTING_CONSUMER_PATH,
        "existing_streamlit_consumer_reused": True,
        "new_provider_calls_added_by_step20a": False,
        "production_runtime_wiring_added_by_step20a": False,
        "production_scheduler_mutation_added_by_step20a": False,
        "production_database_writes_enabled": False,
        "model_probability_mutation_enabled": False,
        "projection_mutation_enabled": False,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "synthetic_player_id_allowed": False,
        "price_fabrication_allowed": False,
    }


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MLBStep20AEndToEndCertificationError(f"{field} must be a mapping")
    return value


def _rows(value: Any, field: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise MLBStep20AEndToEndCertificationError(f"{field} must be a list")
    rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise MLBStep20AEndToEndCertificationError(
                f"{field}[{index}] must be a mapping"
            )
        rows.append(row)
    return rows


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MLBStep20AEndToEndCertificationError(
            f"{field} must be a non-negative integer"
        )
    return value


def _positive_int(value: Any, field: str) -> int:
    result = _nonnegative_int(value, field)
    if result <= 0:
        raise MLBStep20AEndToEndCertificationError(
            f"{field} must be a positive integer"
        )
    return result


def _assert_restart_safety(recovered: Mapping[str, Any]) -> None:
    if recovered.get("data_type") != STEP19E_RESULT_DATA_TYPE:
        raise MLBStep20AEndToEndCertificationError(
            "recovered bundle is not a Step19E result"
        )
    if recovered.get("schema_version") != 1:
        raise MLBStep20AEndToEndCertificationError(
            "recovered Step19E schema version is unsupported"
        )
    if recovered.get("found") is not True or recovered.get("status") != "recovered":
        raise MLBStep20AEndToEndCertificationError(
            "Step19E restart recovery must be complete"
        )
    for field in (
        "production_runtime_wiring",
        "model_probability_mutation",
        "projection_mutation",
        "actionable_output",
        "wagering",
    ):
        if recovered.get(field) is not False:
            raise MLBStep20AEndToEndCertificationError(
                f"recovered Step19E safety flag {field} must be false"
            )


def _restart_sections(recovered: Mapping[str, Any]) -> tuple[
    Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]
]:
    envelope = _mapping(recovered.get("checkpoint_envelope"), "checkpoint_envelope")
    official = _mapping(recovered.get("official_slate_for_restart"), "official_slate_for_restart")
    feed = _mapping(recovered.get("market_feed_for_restart"), "market_feed_for_restart")
    registry = _mapping(
        recovered.get("identity_registry_for_restart"),
        "identity_registry_for_restart",
    )
    reliability = _mapping(
        recovered.get("reliability_state_for_restart"),
        "reliability_state_for_restart",
    )
    reliable = _mapping(
        envelope.get("reliable_market_collection"),
        "checkpoint_envelope.reliable_market_collection",
    )

    if dict(official) != envelope.get("official_slate"):
        raise MLBStep20AEndToEndCertificationError(
            "restart official slate differs from persisted checkpoint envelope"
        )
    if dict(feed) != reliable.get("market_feed"):
        raise MLBStep20AEndToEndCertificationError(
            "restart market feed differs from persisted checkpoint envelope"
        )
    if dict(registry) != envelope.get("identity_registry"):
        raise MLBStep20AEndToEndCertificationError(
            "restart identity registry differs from persisted checkpoint envelope"
        )
    if dict(reliability) != reliable.get("reliability_state"):
        raise MLBStep20AEndToEndCertificationError(
            "restart reliability state differs from persisted checkpoint envelope"
        )
    return official, feed, registry, reliability


def _official_game_index(official: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    if str(official.get("sport") or "").upper() != "MLB":
        raise MLBStep20AEndToEndCertificationError("official slate sport must be MLB")
    games = _rows(official.get("games"), "official_slate.games")
    declared = _nonnegative_int(official.get("game_count"), "official_slate.game_count")
    if declared != len(games):
        raise MLBStep20AEndToEndCertificationError(
            "official slate game_count does not match games"
        )
    result: dict[int, Mapping[str, Any]] = {}
    for index, game in enumerate(games):
        game_id = _positive_int(game.get("game_pk"), f"official_slate.games[{index}].game_pk")
        if game_id in result:
            raise MLBStep20AEndToEndCertificationError(
                f"duplicate official game ID {game_id}"
            )
        for side in ("away_team", "home_team"):
            team = _mapping(game.get(side), f"official_slate.games[{index}].{side}")
            _positive_int(team.get("id"), f"official_slate.games[{index}].{side}.id")
            if not str(team.get("name") or "").strip():
                raise MLBStep20AEndToEndCertificationError(
                    f"official_slate.games[{index}].{side}.name is required"
                )
        if not str(game.get("game_date") or "").strip():
            raise MLBStep20AEndToEndCertificationError(
                f"official_slate.games[{index}].game_date is required"
            )
        result[game_id] = game
    return result


def _identity_index(registry: Mapping[str, Any]) -> dict[tuple[str, str], int]:
    if registry.get("data_type") != step19c.DATA_TYPE:
        raise MLBStep20AEndToEndCertificationError("identity registry data_type mismatch")
    if registry.get("schema_version") != step19c.SCHEMA_VERSION:
        raise MLBStep20AEndToEndCertificationError("identity registry schema mismatch")
    if registry.get("final_certification_marker") != step19c.FINAL_CERTIFICATION_MARKER:
        raise MLBStep20AEndToEndCertificationError("identity registry marker mismatch")
    if registry.get("identity_complete_for_all_market_games") is not True:
        raise MLBStep20AEndToEndCertificationError(
            "identity registry is incomplete for market games"
        )
    if _nonnegative_int(
        registry.get("rejected_event_identity_count"),
        "rejected_event_identity_count",
    ) != 0:
        raise MLBStep20AEndToEndCertificationError("identity registry rejected events")
    if _nonnegative_int(
        registry.get("rejected_player_identity_count"),
        "rejected_player_identity_count",
    ) != 0:
        raise MLBStep20AEndToEndCertificationError("identity registry rejected players")
    for field in (
        "fuzzy_matching_used",
        "player_name_matching_used",
        "synthetic_game_id_used",
        "synthetic_player_id_used",
        "price_fabrication_used",
        "production_runtime_wiring",
        "production_database_writes",
        "model_probability_mutation",
        "projection_mutation",
        "actionable_output",
        "wagering",
    ):
        if registry.get(field) is not False:
            raise MLBStep20AEndToEndCertificationError(
                f"identity registry safety flag {field} must be false"
            )

    rows = _rows(registry.get("event_identities"), "identity_registry.event_identities")
    declared = _nonnegative_int(registry.get("event_identity_count"), "event_identity_count")
    if declared != len(rows):
        raise MLBStep20AEndToEndCertificationError(
            "event_identity_count does not match event_identities"
        )
    result: dict[tuple[str, str], int] = {}
    for index, row in enumerate(rows):
        provider = str(row.get("provider_key") or "").strip()
        event_id = str(row.get("provider_event_id") or "").strip()
        game_id = _positive_int(
            row.get("official_game_id"),
            f"identity_registry.event_identities[{index}].official_game_id",
        )
        if not provider or not event_id:
            raise MLBStep20AEndToEndCertificationError(
                "event identity provider/event ID is required"
            )
        if row.get("fuzzy_matching_used") is not False or row.get("synthetic_game_id_used") is not False:
            raise MLBStep20AEndToEndCertificationError(
                "event identity contains forbidden fuzzy/synthetic identity"
            )
        key = (provider, event_id)
        if key in result:
            raise MLBStep20AEndToEndCertificationError(
                f"duplicate event identity {key!r}"
            )
        result[key] = game_id
    return result


def _validate_feed(
    feed: Mapping[str, Any],
    official_games: Mapping[int, Mapping[str, Any]],
    identities: Mapping[tuple[str, str], int],
) -> list[Mapping[str, Any]]:
    if feed.get("data_type") != step19b.DATA_TYPE:
        raise MLBStep20AEndToEndCertificationError("market feed data_type mismatch")
    if feed.get("schema_version") != step19b.SCHEMA_VERSION:
        raise MLBStep20AEndToEndCertificationError("market feed schema mismatch")
    if _nonnegative_int(feed.get("rejected_record_count"), "rejected_record_count") != 0:
        raise MLBStep20AEndToEndCertificationError("market feed contains rejected records")
    rows = _rows(feed.get("game_market_snapshots"), "market_feed.game_market_snapshots")
    declared = _nonnegative_int(
        feed.get("game_market_snapshot_count"), "game_market_snapshot_count"
    )
    if declared != len(rows):
        raise MLBStep20AEndToEndCertificationError(
            "game_market_snapshot_count does not match snapshots"
        )
    if _nonnegative_int(feed.get("error_surface_count"), "error_surface_count") != 0:
        raise MLBStep20AEndToEndCertificationError("market feed contains provider errors")
    if _nonnegative_int(feed.get("not_ready_surface_count"), "not_ready_surface_count") != 0:
        raise MLBStep20AEndToEndCertificationError("market feed contains not-ready surfaces")

    for index, row in enumerate(rows):
        validation = validate_market_provider_game_snapshot(row)
        if validation.get("snapshot_valid") is not True:
            raise MLBStep20AEndToEndCertificationError(
                f"market snapshot {index} fails frozen Step11A validation: "
                f"{validation.get('failures')!r}"
            )
        game_id = _positive_int(
            row.get("official_game_id"),
            f"market_feed.game_market_snapshots[{index}].official_game_id",
        )
        if game_id not in official_games:
            raise MLBStep20AEndToEndCertificationError(
                f"market snapshot game {game_id} is absent from official slate"
            )
        identity_game = identities.get(
            (str(row.get("provider_key") or ""), str(row.get("provider_event_id") or ""))
        )
        if identity_game != game_id:
            raise MLBStep20AEndToEndCertificationError(
                f"market snapshot {index} does not match certified event identity"
            )
    if len(identities) != len(rows):
        raise MLBStep20AEndToEndCertificationError(
            "certified event identities and market snapshots are not one-to-one"
        )
    return rows


def _existing_api_payload(
    *,
    feed: Mapping[str, Any],
    official_games: Mapping[int, Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    games: list[dict[str, Any]] = []
    transports: set[str] = set()
    for row in rows:
        if row.get("provider_key") != "fanduel":
            continue
        if row.get("market_phase") != "PREGAME" or row.get("fully_priced") is not True:
            continue
        game_id = int(row["official_game_id"])
        official = official_games[game_id]
        transports.add(str(row.get("transport") or ""))
        games.append(
            {
                "official_game_id": game_id,
                "scheduled_start_utc": official.get("game_date"),
                "away_team": deepcopy(dict(_mapping(official.get("away_team"), "away_team"))),
                "home_team": deepcopy(dict(_mapping(official.get("home_team"), "home_team"))),
                "sportsbook": "FanDuel",
                "fully_priced": True,
                "markets": deepcopy(dict(_mapping(row.get("markets"), "markets"))),
            }
        )
    games.sort(key=lambda game: (str(game.get("scheduled_start_utc") or ""), int(game["official_game_id"])))
    if not games:
        raise MLBStep20AEndToEndCertificationError(
            "no fully priced certified FanDuel game can cross the existing MLB odds consumer seam"
        )
    if len(transports) != 1 or "" in transports:
        raise MLBStep20AEndToEndCertificationError(
            "FanDuel consumer games do not share one explicit transport"
        )
    collected_at = feed.get("observed_at_utc") or feed.get("collected_at_utc")
    return {
        "data_type": EXISTING_API_DATA_TYPE,
        "schema_version": EXISTING_API_SCHEMA_VERSION,
        "source": "FanDuel",
        "transport": next(iter(transports)),
        "http_methods": ["GET"],
        "collected_at_utc": collected_at,
        "fully_priced_only": True,
        "game_count": len(games),
        "rejected_event_count": 0,
        "games": games,
    }


class _ConsumerResponse:
    def __init__(self, payload: Mapping[str, Any]):
        self._payload = deepcopy(dict(payload))
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return deepcopy(self._payload)


def certify_recovered_step19_to_existing_mlb_consumer(
    recovered_step19e: Mapping[str, Any],
) -> dict[str, Any]:
    """Certify the recovered Step19 chain through the existing MLB UI contract.

    No provider, database, model, scheduler, API-server, or wagering action is
    performed here.  The existing Streamlit fetch/parser and card builder are
    reused with an in-process response carrying only already-recovered data.
    """
    recovered = _mapping(recovered_step19e, "recovered_step19e")
    _assert_restart_safety(recovered)
    official, feed, registry, reliability = _restart_sections(recovered)
    official_games = _official_game_index(official)
    identities = _identity_index(registry)
    rows = _validate_feed(feed, official_games, identities)
    payload = _existing_api_payload(feed=feed, official_games=official_games, rows=rows)

    # Lazy import keeps Step20A itself independent of Streamlit startup state.
    import mlb_live_odds_streamlit_v1 as consumer

    request_metadata: dict[str, Any] = {}

    def _request_get(url: str, **kwargs: Any) -> _ConsumerResponse:
        request_metadata["url"] = url
        request_metadata.update(deepcopy(kwargs))
        return _ConsumerResponse(payload)

    consumed = consumer.fetch_live_mlb_odds(
        base_url="https://step20a-certification.invalid",
        max_events=30,
        request_get=_request_get,
    )
    cards = consumer.build_game_cards(consumed)
    if request_metadata.get("url") != (
        "https://step20a-certification.invalid" + EXISTING_CONSUMER_PATH
    ):
        raise MLBStep20AEndToEndCertificationError(
            "existing Streamlit consumer requested an unexpected API path"
        )
    if request_metadata.get("params") != {
        "max_events": 30,
        "fully_priced_only": "true",
    }:
        raise MLBStep20AEndToEndCertificationError(
            "existing Streamlit consumer request parameters changed"
        )
    if len(cards) != len(payload["games"]):
        raise MLBStep20AEndToEndCertificationError(
            "existing Streamlit consumer dropped certified fully priced games"
        )
    expected_ids = [int(game["official_game_id"]) for game in payload["games"]]
    consumed_ids = [int(card["official_game_id"]) for card in cards]
    if consumed_ids != expected_ids:
        raise MLBStep20AEndToEndCertificationError(
            "existing Streamlit consumer changed official MLB game identity"
        )

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "certification_status": "certified",
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "checkpoint_version": recovered.get("checkpoint_version"),
        "checkpoint_id": recovered.get("checkpoint_id"),
        "checkpoint_envelope_sha256": recovered.get("envelope_content_sha256"),
        "official_game_count": len(official_games),
        "market_game_snapshot_count": len(rows),
        "verified_event_identity_count": len(identities),
        "reliability_provider_state_count": len(reliability),
        "consumer_api_path": EXISTING_CONSUMER_PATH,
        "consumer_api_data_type": EXISTING_API_DATA_TYPE,
        "consumer_game_count": len(payload["games"]),
        "consumer_card_count": len(cards),
        "consumer_official_game_ids": consumed_ids,
        "consumer_payload": deepcopy(payload),
        "consumer_cards": deepcopy(cards),
        "provider_network_calls_added_by_step20a": 0,
        "database_reads_added_by_step20a": 0,
        "database_writes_added_by_step20a": 0,
        "production_runtime_wiring": False,
        "production_scheduler_mutation": False,
        "model_probability_mutation": False,
        "projection_mutation": False,
        "actionable_output": False,
        "wagering": False,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "synthetic_player_id_used": False,
        "price_fabrication_used": False,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP20A_BASE_MAIN_SHA",
    "CERTIFICATION_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "EXISTING_API_DATA_TYPE",
    "EXISTING_API_SCHEMA_VERSION",
    "EXISTING_CONSUMER_PATH",
    "MLBStep20AEndToEndCertificationError",
    "certification_manifest",
    "certify_recovered_step19_to_existing_mlb_consumer",
]
