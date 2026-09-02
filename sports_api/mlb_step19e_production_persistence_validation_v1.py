"""MLB Step 19E — durable live-data persistence and restart validation.

Step 19E persists one content-addressed snapshot of the certified Step 19A
official slate, Step 19B market feed, Step 19C event/player identity registry,
and Step 19D caller-owned provider reliability state.

The adapter is explicit and default-OFF. It defines separate Step-19 tables so
the frozen Step-14 scheduler/recovery checkpoint contract remains byte-identical.
It never calls providers, fabricates market data or identities, mutates models,
starts workers, schedules cycles, or emits actionable/wagering output.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sports_api.collectors import mlb_event_player_identity as step19c
from sports_api.collectors import mlb_live_market_feed as step19b
from sports_api.collectors import mlb_official_slate as step19a
from sports_api.collectors import mlb_provider_reliability as step19d
from sports_api.mlb_step11a_provider_contract_v1 import validate_market_provider_game_snapshot

DATA_TYPE = "mlb_step19e_production_persistence_validation_v1"
ENVELOPE_DATA_TYPE = "mlb_step19e_live_data_checkpoint_envelope_v1"
RESULT_DATA_TYPE = "mlb_step19e_live_data_checkpoint_result_v1"
SCHEMA_CHECK_DATA_TYPE = "mlb_step19e_persistence_schema_check_v1"
SCHEMA_VERSION = 1
STEP19E_BASE_MAIN_SHA = "4e9f5494f520b2c491b0820d3069baecd49124b3"
STEP19A_SOURCE_BLOB_SHA = "4dc01cee2bdd766d7ced0608ad53dfe378ec48b8"
STEP19B_SOURCE_BLOB_SHA = "8bc57ab1a0000fc902fc02f7f67a2e94eb20b3b2"
STEP19C_SOURCE_BLOB_SHA = "f7d231ec3b2327cc7e14d317a33ff4626d6a2145"
STEP19D_SOURCE_BLOB_SHA = "768aca6145e43179aec8c2c70e2ac4acaf221351"
CONTRACT_ID = "mlb_step19e_live_data_persistence_validation_2026_v1"
CONTRACT_VERSION = "mlb_step19e_postgresql_append_only_cas_2026_v1"
CONTRACT_STATUS = "STEP19E_PRODUCTION_PERSISTENCE_VALIDATION_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP19E_PRODUCTION_PERSISTENCE_VALIDATION_GREEN"

DATABASE_SCHEMA_NAME = "kyre_runtime"
CHECKPOINT_TABLE_NAME = "mlb_step19_live_data_checkpoints"
CHECKPOINT_HEAD_TABLE_NAME = "mlb_step19_live_data_checkpoint_heads"
SQL_SCHEMA_PATH = "sports_api/sql/mlb_step19e_live_data_persistence.sql"
SQL_SCHEMA_SHA256 = "154faefe8bc6e366f010339530fefcdea3a99db18b0a83be15d5b63ac5859a69"
DATABASE_URL_ENV = "KYRE_DATABASE_URL"

ADAPTER_ENABLED_ENV = "MLB_STEP19E_PERSISTENCE_ADAPTER_ENABLED"
DATABASE_READ_ENABLED_ENV = "MLB_STEP19E_DATABASE_READ_ENABLED"
DATABASE_WRITE_ENABLED_ENV = "MLB_STEP19E_DATABASE_WRITE_ENABLED"

DEFAULT_ENABLED = False
DEFAULT_MAX_CHECKPOINT_AGE_SECONDS = 300.0
DEFAULT_FUTURE_TOLERANCE_SECONDS = 5.0
POSTGRESQL_DATABASE_READ_ALLOWED = True
POSTGRESQL_DATABASE_WRITE_ALLOWED = True
APPEND_ONLY_HISTORY_REQUIRED = True
ATOMIC_HEAD_COMPARE_AND_SWAP_REQUIRED = True
CONTENT_ADDRESSING_REQUIRED = True
DURABLE_RESTART_RECOVERY_ALLOWED = True
RELIABILITY_STATE_RECOVERY_ALLOWED = True
SCHEMA_AUTO_APPLY_ALLOWED = False
PRODUCTION_RUNTIME_WIRING_ADDED = False
PRODUCTION_SCHEDULER_MUTATION_ADDED = False
PROVIDER_NETWORK_CALLS_ADDED = False
SPORTSBOOK_NETWORK_CALLS_ADDED = False
MODEL_PROBABILITY_MUTATION_ENABLED = False
PROJECTION_MUTATION_ENABLED = False
ACTIONABLE_OUTPUT_ENABLED = False
WAGERING_ENABLED = False

_PROVIDER_KEYS = (step19d.FANDUEL_PROVIDER_KEY, step19d.DRAFTKINGS_PROVIDER_KEY)
_PROVIDER_STATE_KEYS = {
    "cooldown_until_utc",
    "cooldown_reason",
    "last_failure_kind",
    "last_failure_at_utc",
    "last_success_at_utc",
}
_ENVELOPE_KEYS = {
    "data_type",
    "schema_version",
    "contract_id",
    "contract_version",
    "contract_status",
    "checkpoint_date",
    "checkpoint_key",
    "step19e_base_main_sha",
    "step19a_source_blob_sha",
    "step19b_source_blob_sha",
    "step19c_source_blob_sha",
    "step19d_source_blob_sha",
    "step19b_final_certification_marker",
    "step19c_final_certification_marker",
    "step19d_final_certification_marker",
    "official_slate",
    "official_slate_sha256",
    "reliable_market_collection",
    "reliable_market_collection_sha256",
    "market_feed_sha256",
    "identity_registry",
    "identity_registry_sha256",
    "reliability_state_sha256",
    "created_at_utc",
    "envelope_content_sha256",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA_EXISTENCE_SQL = "SELECT to_regclass(%s) IS NOT NULL, to_regclass(%s) IS NOT NULL"

_HEAD_SELECT_SQL = f"""
SELECT
    h.checkpoint_version,
    h.checkpoint_id::text,
    h.envelope_content_sha256::text,
    c.checkpoint_version,
    c.checkpoint_id::text,
    c.checkpoint_key,
    c.slate_date::text,
    c.contract_version,
    c.official_slate_sha256,
    c.market_feed_sha256,
    c.identity_registry_sha256,
    c.reliability_state_sha256,
    c.envelope_content_sha256,
    c.envelope_json
FROM {DATABASE_SCHEMA_NAME}.{CHECKPOINT_HEAD_TABLE_NAME} AS h
JOIN {DATABASE_SCHEMA_NAME}.{CHECKPOINT_TABLE_NAME} AS c
  ON c.checkpoint_id = h.checkpoint_id
WHERE h.checkpoint_key = %s
""".strip()
_HEAD_SELECT_FOR_UPDATE_SQL = _HEAD_SELECT_SQL + "\nFOR UPDATE OF h"

_INSERT_HISTORY_SQL = f"""
INSERT INTO {DATABASE_SCHEMA_NAME}.{CHECKPOINT_TABLE_NAME} (
    checkpoint_id,
    checkpoint_key,
    checkpoint_version,
    slate_date,
    contract_version,
    official_slate_sha256,
    market_feed_sha256,
    identity_registry_sha256,
    reliability_state_sha256,
    envelope_content_sha256,
    envelope_json,
    created_at
) VALUES (
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s::jsonb, %s
)
""".strip()

_INSERT_HEAD_SQL = f"""
INSERT INTO {DATABASE_SCHEMA_NAME}.{CHECKPOINT_HEAD_TABLE_NAME} (
    checkpoint_key,
    checkpoint_version,
    checkpoint_id,
    envelope_content_sha256,
    updated_at
) VALUES (%s, %s, %s, %s, %s)
""".strip()

_UPDATE_HEAD_SQL = f"""
UPDATE {DATABASE_SCHEMA_NAME}.{CHECKPOINT_HEAD_TABLE_NAME}
SET checkpoint_version = %s,
    checkpoint_id = %s,
    envelope_content_sha256 = %s,
    updated_at = %s
WHERE checkpoint_key = %s
  AND checkpoint_version = %s
""".strip()


class MLBStep19EPersistenceDisabledError(RuntimeError):
    """Raised when an explicit Step 19E persistence gate is disabled."""


class MLBStep19EPersistenceInputError(ValueError):
    """Raised when caller input cannot form a valid Step 19E checkpoint."""


class MLBStep19EPersistenceIntegrityError(RuntimeError):
    """Raised when persisted or caller-owned live data fails closed."""


class MLBStep19EPersistenceSchemaError(RuntimeError):
    """Raised when the additive Step 19E PostgreSQL tables are absent."""


class MLBStep19EPersistenceConflictError(RuntimeError):
    """Raised when checkpoint-head compare-and-swap detects a stale writer."""


class MLBStep19EPersistenceDatabaseError(RuntimeError):
    """Raised for isolated PostgreSQL transport or transaction failures."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled",
    }


def persistence_adapter_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(ADAPTER_ENABLED_ENV))


def database_read_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(DATABASE_READ_ENABLED_ENV))


def database_write_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(DATABASE_WRITE_ENABLED_ENV))


def _hash(value: Any) -> str:
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MLBStep19EPersistenceInputError(
            "checkpoint content must be strict JSON-compatible"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _json_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MLBStep19EPersistenceInputError(f"{field} must be a mapping")
    try:
        raw = json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        normalized = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise MLBStep19EPersistenceInputError(
            f"{field} must be strict JSON-compatible"
        ) from exc
    if not isinstance(normalized, dict):
        raise MLBStep19EPersistenceInputError(f"{field} must normalize to an object")
    return normalized


def _rows(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise MLBStep19EPersistenceIntegrityError(f"{field} must be a list")
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise MLBStep19EPersistenceIntegrityError(
                f"{field}[{index}] must be a mapping"
            )
        rows.append(dict(row))
    return rows


def _utc(value: Any, field: str) -> tuple[str, datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(
                text[:-1] + "+00:00" if text.endswith("Z") else text
            )
        except ValueError as exc:
            raise MLBStep19EPersistenceIntegrityError(
                f"{field} must be valid ISO-8601"
            ) from exc
    else:
        raise MLBStep19EPersistenceIntegrityError(f"{field} is required")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MLBStep19EPersistenceIntegrityError(
            f"{field} must be timezone-aware"
        )
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _checkpoint_date(value: Any) -> str:
    text = value.isoformat() if isinstance(value, date) else str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise MLBStep19EPersistenceInputError(
            "checkpoint_date must use YYYY-MM-DD"
        ) from exc
    if parsed.isoformat() != text:
        raise MLBStep19EPersistenceInputError(
            "checkpoint_date must use canonical YYYY-MM-DD"
        )
    return text


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MLBStep19EPersistenceIntegrityError(
            f"{field} must be a non-negative integer"
        )
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise MLBStep19EPersistenceIntegrityError(
            f"{field} must be a positive integer"
        )
    return value


def _valid_sha(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if _SHA256_RE.fullmatch(text) is None:
        raise MLBStep19EPersistenceIntegrityError(
            f"{field} must be lowercase SHA-256 hex"
        )
    return text


def checkpoint_key_for_date(value: str | date) -> str:
    return f"mlb:step19e:live-data:{_checkpoint_date(value)}"


def _slate_date_mentions_checkpoint(slate_label: Any, checkpoint_date: str) -> bool:
    text = str(slate_label or "").strip()
    if not text:
        return False
    return checkpoint_date in {part.strip() for part in text.split(",") if part.strip()}


def _validate_official_slate(
    value: Any,
    *,
    checkpoint_date: str,
) -> tuple[dict[str, Any], set[int]]:
    slate = _json_object(value, "official_slate")
    if str(slate.get("sport") or "").strip().upper() != "MLB":
        raise MLBStep19EPersistenceIntegrityError("official_slate.sport must be MLB")
    if not _slate_date_mentions_checkpoint(slate.get("slate_date"), checkpoint_date):
        raise MLBStep19EPersistenceIntegrityError(
            "official_slate.slate_date must include checkpoint_date"
        )
    game_count = _nonnegative_int(slate.get("game_count"), "official_slate.game_count")
    games = _rows(slate.get("games"), "official_slate.games")
    if game_count != len(games):
        raise MLBStep19EPersistenceIntegrityError(
            "official_slate.game_count does not match games"
        )
    if str(slate.get("source") or "").strip() != step19a.SOURCE_NAME:
        raise MLBStep19EPersistenceIntegrityError(
            "official_slate.source must be the certified MLB Stats API source"
        )
    if slate.get("collected_at_utc") is not None:
        _utc(slate["collected_at_utc"], "official_slate.collected_at_utc")

    game_ids: set[int] = set()
    for index, game in enumerate(games):
        game_pk = _positive_int(
            game.get("game_pk"), f"official_slate.games[{index}].game_pk"
        )
        if game_pk in game_ids:
            raise MLBStep19EPersistenceIntegrityError(
                f"duplicate official game_pk {game_pk}"
            )
        game_ids.add(game_pk)
        away = game.get("away_team")
        home = game.get("home_team")
        if not isinstance(away, Mapping) or not isinstance(home, Mapping):
            raise MLBStep19EPersistenceIntegrityError(
                f"official_slate.games[{index}] requires away/home team mappings"
            )
        away_id = _positive_int(
            away.get("id"), f"official_slate.games[{index}].away_team.id"
        )
        home_id = _positive_int(
            home.get("id"), f"official_slate.games[{index}].home_team.id"
        )
        if away_id == home_id:
            raise MLBStep19EPersistenceIntegrityError(
                f"official_slate.games[{index}] has identical team IDs"
            )
        _utc(game.get("game_date"), f"official_slate.games[{index}].game_date")
        if not str(game.get("status") or "").strip():
            raise MLBStep19EPersistenceIntegrityError(
                f"official_slate.games[{index}].status is required"
            )
    return slate, game_ids


def _validate_reliability_state(value: Any) -> dict[str, Any]:
    state = _json_object(value, "reliability_state")
    if state.get("schema_version") != step19d.SCHEMA_VERSION:
        raise MLBStep19EPersistenceIntegrityError(
            "reliability_state schema_version mismatch"
        )
    providers = state.get("providers")
    if not isinstance(providers, Mapping):
        raise MLBStep19EPersistenceIntegrityError(
            "reliability_state.providers must be a mapping"
        )
    if set(providers) != set(_PROVIDER_KEYS):
        raise MLBStep19EPersistenceIntegrityError(
            "reliability_state provider keys must match certified Step19D providers"
        )
    for provider_key in _PROVIDER_KEYS:
        row = providers.get(provider_key)
        if not isinstance(row, Mapping) or set(row) != _PROVIDER_STATE_KEYS:
            raise MLBStep19EPersistenceIntegrityError(
                f"reliability_state.{provider_key} shape mismatch"
            )
        for field in _PROVIDER_STATE_KEYS:
            item = row.get(field)
            if item is not None and not isinstance(item, str):
                raise MLBStep19EPersistenceIntegrityError(
                    f"reliability_state.{provider_key}.{field} must be string or null"
                )
        for field in (
            "cooldown_until_utc",
            "last_failure_at_utc",
            "last_success_at_utc",
        ):
            if row.get(field) is not None:
                _utc(
                    row[field],
                    f"reliability_state.{provider_key}.{field}",
                )
        if (row.get("cooldown_until_utc") is None) != (
            row.get("cooldown_reason") is None
        ):
            raise MLBStep19EPersistenceIntegrityError(
                f"reliability_state.{provider_key} cooldown fields must be paired"
            )
    return state


def _validate_market_feed(
    value: Any,
    *,
    official_game_ids: set[int],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    feed = _json_object(value, "market_feed")
    if feed.get("data_type") != step19b.DATA_TYPE:
        raise MLBStep19EPersistenceIntegrityError("market_feed data_type mismatch")
    if feed.get("schema_version") != step19b.SCHEMA_VERSION:
        raise MLBStep19EPersistenceIntegrityError("market_feed schema_version mismatch")
    if feed.get("feed_status") != step19b.FEED_STATUS:
        raise MLBStep19EPersistenceIntegrityError("market_feed feed_status mismatch")
    _utc(feed.get("collected_at_utc"), "market_feed.collected_at_utc")

    game_rows = _rows(
        feed.get("game_market_snapshots"), "market_feed.game_market_snapshots"
    )
    prop_rows = _rows(feed.get("player_props"), "market_feed.player_props")
    if _nonnegative_int(
        feed.get("game_market_snapshot_count"),
        "market_feed.game_market_snapshot_count",
    ) != len(game_rows):
        raise MLBStep19EPersistenceIntegrityError(
            "market_feed game snapshot count mismatch"
        )
    if _nonnegative_int(
        feed.get("player_prop_count"), "market_feed.player_prop_count"
    ) != len(prop_rows):
        raise MLBStep19EPersistenceIntegrityError(
            "market_feed player prop count mismatch"
        )
    enabled = _nonnegative_int(
        feed.get("enabled_surface_count"), "market_feed.enabled_surface_count"
    )
    successful = _nonnegative_int(
        feed.get("successful_surface_count"), "market_feed.successful_surface_count"
    )
    not_ready = _nonnegative_int(
        feed.get("not_ready_surface_count"), "market_feed.not_ready_surface_count"
    )
    errors = _nonnegative_int(
        feed.get("error_surface_count"), "market_feed.error_surface_count"
    )
    if enabled <= 0 or successful != enabled or not_ready != 0 or errors != 0:
        raise MLBStep19EPersistenceIntegrityError(
            "market_feed is incomplete; every requested provider surface must succeed"
        )
    statuses = _rows(
        feed.get("provider_surface_statuses"), "market_feed.provider_surface_statuses"
    )
    if len(statuses) != enabled or any(row.get("status") != "success" for row in statuses):
        raise MLBStep19EPersistenceIntegrityError(
            "market_feed provider surface statuses are incomplete"
        )
    if any(int(row.get("upstream_rejected_count") or 0) != 0 for row in statuses):
        raise MLBStep19EPersistenceIntegrityError(
            "market_feed upstream rejected records prevent persistence"
        )
    if _nonnegative_int(
        feed.get("rejected_record_count"), "market_feed.rejected_record_count"
    ) != 0:
        raise MLBStep19EPersistenceIntegrityError(
            "market_feed rejected records prevent persistence"
        )
    if feed.get("rejected_records") != []:
        raise MLBStep19EPersistenceIntegrityError(
            "market_feed rejected_records must be empty"
        )
    if feed.get("live_market_data_present") is not bool(game_rows or prop_rows):
        raise MLBStep19EPersistenceIntegrityError(
            "market_feed live_market_data_present mismatch"
        )
    if official_game_ids and not game_rows:
        raise MLBStep19EPersistenceIntegrityError(
            "non-empty official slate requires verified game market data"
        )

    for flag in (
        "production_runtime_wiring",
        "production_database_writes",
        "model_probability_mutation",
        "projection_mutation",
        "actionable_output",
        "wagering",
        "price_fabrication_used",
        "new_step19b_identity_matching",
    ):
        if feed.get(flag) is not False:
            raise MLBStep19EPersistenceIntegrityError(
                f"market_feed.{flag} must be false"
            )
    if feed.get("network_reads_only") is not True or feed.get("http_methods") != ["GET"]:
        raise MLBStep19EPersistenceIntegrityError(
            "market_feed must preserve read-only GET boundary"
        )

    for index, row in enumerate(game_rows):
        snapshot_validation = validate_market_provider_game_snapshot(row)
        if snapshot_validation.get("snapshot_valid") is not True:
            raise MLBStep19EPersistenceIntegrityError(
                "market game failed frozen Step11A validation: "
                + repr(snapshot_validation.get("failures"))
            )
        game_id = _positive_int(
            row.get("official_game_id"),
            f"market_feed.game_market_snapshots[{index}].official_game_id",
        )
        if game_id not in official_game_ids:
            raise MLBStep19EPersistenceIntegrityError(
                f"market game {game_id} is absent from official slate"
            )
        if row.get("exact_official_game_id_verified") is not True:
            raise MLBStep19EPersistenceIntegrityError(
                "market game exact official ID must be verified"
            )
        if row.get("fuzzy_matching_used") is not False:
            raise MLBStep19EPersistenceIntegrityError(
                "market game fuzzy matching must be false"
            )
        if row.get("synthetic_game_id_used") is not False:
            raise MLBStep19EPersistenceIntegrityError(
                "market game synthetic ID must be false"
            )
        if row.get("price_fabrication_used") is not False:
            raise MLBStep19EPersistenceIntegrityError(
                "market game price fabrication must be false"
            )

    for index, row in enumerate(prop_rows):
        game_id = _positive_int(
            row.get("official_game_id"),
            f"market_feed.player_props[{index}].official_game_id",
        )
        if game_id not in official_game_ids:
            raise MLBStep19EPersistenceIntegrityError(
                f"player prop game {game_id} is absent from official slate"
            )
        _positive_int(
            row.get("official_player_id"),
            f"market_feed.player_props[{index}].official_player_id",
        )
        if row.get("exact_official_game_id_verified") is not True:
            raise MLBStep19EPersistenceIntegrityError(
                "player prop exact game ID must be verified"
            )
        if row.get("exact_official_player_id_verified") is not True:
            raise MLBStep19EPersistenceIntegrityError(
                "player prop exact player ID must be verified"
            )
        if row.get("player_name_matching_used") is not False:
            raise MLBStep19EPersistenceIntegrityError(
                "player prop name matching must be false"
            )
        if row.get("fuzzy_matching_used") is not False:
            raise MLBStep19EPersistenceIntegrityError(
                "player prop fuzzy matching must be false"
            )
        if row.get("price_fabrication_used") is not False:
            raise MLBStep19EPersistenceIntegrityError(
                "player prop price fabrication must be false"
            )
    return feed, game_rows, prop_rows


def _validate_reliable_collection(
    value: Any,
    *,
    official_game_ids: set[int],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    reliable = _json_object(value, "reliable_market_collection")
    if reliable.get("data_type") != step19d.DATA_TYPE:
        raise MLBStep19EPersistenceIntegrityError(
            "reliable_market_collection data_type mismatch"
        )
    if reliable.get("schema_version") != step19d.SCHEMA_VERSION:
        raise MLBStep19EPersistenceIntegrityError(
            "reliable_market_collection schema_version mismatch"
        )
    if reliable.get("reliability_status") != step19d.RELIABILITY_STATUS:
        raise MLBStep19EPersistenceIntegrityError(
            "reliable_market_collection reliability_status mismatch"
        )
    if reliable.get("collection_status") not in {"ok", "recovered"}:
        raise MLBStep19EPersistenceIntegrityError(
            "only complete healthy/recovered Step19D collections may be persisted"
        )
    _utc(reliable.get("collected_at_utc"), "reliable_market_collection.collected_at_utc")
    feed, game_rows, prop_rows = _validate_market_feed(
        reliable.get("market_feed"),
        official_game_ids=official_game_ids,
    )
    state = _validate_reliability_state(reliable.get("reliability_state"))

    for flag in (
        "price_fabrication_used",
        "synthetic_game_id_used",
        "synthetic_player_id_used",
        "fuzzy_matching_used",
        "reliability_state_persisted_by_step19d",
        "production_runtime_wiring",
        "production_database_writes",
        "model_probability_mutation",
        "projection_mutation",
        "actionable_output",
        "wagering",
    ):
        if reliable.get(flag) is not False:
            raise MLBStep19EPersistenceIntegrityError(
                f"reliable_market_collection.{flag} must be false"
            )
    if reliable.get("stale_data_fail_closed") is not True:
        raise MLBStep19EPersistenceIntegrityError(
            "Step19D stale-data fail-closed guard must be enabled"
        )
    if reliable.get("network_reads_only") is not True or reliable.get("http_methods") != ["GET"]:
        raise MLBStep19EPersistenceIntegrityError(
            "Step19D read-only GET boundary must be preserved"
        )
    return reliable, feed, state, game_rows, prop_rows


def _validate_identity_registry(
    value: Any,
    *,
    official_game_ids: set[int],
    game_rows: list[dict[str, Any]],
    prop_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    registry = _json_object(value, "identity_registry")
    if registry.get("data_type") != step19c.DATA_TYPE:
        raise MLBStep19EPersistenceIntegrityError("identity_registry data_type mismatch")
    if registry.get("schema_version") != step19c.SCHEMA_VERSION:
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry schema_version mismatch"
        )
    if registry.get("registry_status") != step19c.REGISTRY_STATUS:
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry registry_status mismatch"
        )
    if registry.get("final_certification_marker") != step19c.FINAL_CERTIFICATION_MARKER:
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry certification marker mismatch"
        )
    if _nonnegative_int(
        registry.get("official_game_count"), "identity_registry.official_game_count"
    ) != len(official_game_ids):
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry official game count mismatch"
        )
    if _nonnegative_int(
        registry.get("market_game_claim_count"),
        "identity_registry.market_game_claim_count",
    ) != len(game_rows):
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry market game claim count mismatch"
        )
    if _nonnegative_int(
        registry.get("player_prop_claim_count"),
        "identity_registry.player_prop_claim_count",
    ) != len(prop_rows):
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry player prop claim count mismatch"
        )
    if _nonnegative_int(
        registry.get("rejected_event_identity_count"),
        "identity_registry.rejected_event_identity_count",
    ) != 0:
        raise MLBStep19EPersistenceIntegrityError(
            "rejected event identities prevent persistence"
        )
    if _nonnegative_int(
        registry.get("rejected_player_identity_count"),
        "identity_registry.rejected_player_identity_count",
    ) != 0:
        raise MLBStep19EPersistenceIntegrityError(
            "rejected player identities prevent persistence"
        )
    if registry.get("rejected_event_identities") != []:
        raise MLBStep19EPersistenceIntegrityError(
            "rejected_event_identities must be empty"
        )
    if registry.get("rejected_player_identities") != []:
        raise MLBStep19EPersistenceIntegrityError(
            "rejected_player_identities must be empty"
        )
    if registry.get("identity_complete_for_all_market_games") is not True:
        raise MLBStep19EPersistenceIntegrityError(
            "identity registry is incomplete for market games"
        )

    event_identities = _rows(
        registry.get("event_identities"), "identity_registry.event_identities"
    )
    if _nonnegative_int(
        registry.get("event_identity_count"), "identity_registry.event_identity_count"
    ) != len(event_identities):
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry event identity count mismatch"
        )
    player_identities = _rows(
        registry.get("player_identities"), "identity_registry.player_identities"
    )
    if _nonnegative_int(
        registry.get("player_identity_count"), "identity_registry.player_identity_count"
    ) != len(player_identities):
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry player identity count mismatch"
        )

    market_events = {
        (
            str(row.get("provider_key") or ""),
            str(row.get("provider_event_id") or ""),
            _positive_int(row.get("official_game_id"), "market event official_game_id"),
        )
        for row in game_rows
    }
    registry_events = {
        (
            str(row.get("provider_key") or ""),
            str(row.get("provider_event_id") or ""),
            _positive_int(row.get("official_game_id"), "registry event official_game_id"),
        )
        for row in event_identities
    }
    if registry_events != market_events:
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry event identities do not exactly cover market events"
        )

    player_markets: set[tuple[str, str, str, int, int]] = set()
    for row in prop_rows:
        player_markets.add(
            (
                str(row.get("provider_key") or ""),
                str(row.get("source_event_id") or ""),
                str(row.get("source_market_id") or ""),
                _positive_int(row.get("official_game_id"), "prop official_game_id"),
                _positive_int(row.get("official_player_id"), "prop official_player_id"),
            )
        )
    registry_player_markets: set[tuple[str, str, str, int, int]] = set()
    for row in player_identities:
        game_id = _positive_int(
            row.get("official_game_id"), "registry player official_game_id"
        )
        player_id = _positive_int(
            row.get("official_player_id"), "registry player official_player_id"
        )
        market_ids = row.get("source_market_ids")
        if not isinstance(market_ids, list) or not market_ids:
            raise MLBStep19EPersistenceIntegrityError(
                "registry player source_market_ids must be non-empty"
            )
        for market_id in market_ids:
            registry_player_markets.add(
                (
                    str(row.get("provider_key") or ""),
                    str(row.get("source_event_id") or ""),
                    str(market_id),
                    game_id,
                    player_id,
                )
            )
    if registry_player_markets != player_markets:
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry player identities do not exactly cover prop markets"
        )

    for flag in (
        "fuzzy_matching_used",
        "player_name_matching_used",
        "synthetic_game_id_used",
        "synthetic_player_id_used",
        "price_fabrication_used",
        "network_reads_added_by_step19c",
        "production_runtime_wiring",
        "production_database_writes",
        "model_probability_mutation",
        "projection_mutation",
        "actionable_output",
        "wagering",
    ):
        if registry.get(flag) is not False:
            raise MLBStep19EPersistenceIntegrityError(
                f"identity_registry.{flag} must be false"
            )
    return registry


def _validate_cross_layer_inputs(
    *,
    checkpoint_date: str,
    official_slate: Any,
    reliable_market_collection: Any,
    identity_registry: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    slate, official_game_ids = _validate_official_slate(
        official_slate,
        checkpoint_date=checkpoint_date,
    )
    reliable, feed, state, game_rows, prop_rows = _validate_reliable_collection(
        reliable_market_collection,
        official_game_ids=official_game_ids,
    )
    registry = _validate_identity_registry(
        identity_registry,
        official_game_ids=official_game_ids,
        game_rows=game_rows,
        prop_rows=prop_rows,
    )
    if registry.get("official_slate_date") != slate.get("slate_date"):
        raise MLBStep19EPersistenceIntegrityError(
            "identity_registry official_slate_date mismatch"
        )
    return slate, reliable, registry, state


def build_step19e_checkpoint_envelope(
    *,
    checkpoint_date: str | date,
    official_slate: Mapping[str, Any],
    reliable_market_collection: Mapping[str, Any],
    identity_registry: Mapping[str, Any],
    created_at_utc: str | datetime | None = None,
    future_tolerance_seconds: float = DEFAULT_FUTURE_TOLERANCE_SECONDS,
) -> dict[str, Any]:
    """Build one strict content-addressed live-data checkpoint candidate."""
    checkpoint = _checkpoint_date(checkpoint_date)
    slate, reliable, registry, state = _validate_cross_layer_inputs(
        checkpoint_date=checkpoint,
        official_slate=official_slate,
        reliable_market_collection=reliable_market_collection,
        identity_registry=identity_registry,
    )
    created_text, created = _utc(
        created_at_utc or datetime.now(timezone.utc),
        "created_at_utc",
    )
    tolerance = float(future_tolerance_seconds)
    if tolerance < 0 or tolerance > 60:
        raise MLBStep19EPersistenceInputError(
            "future_tolerance_seconds must be between 0 and 60"
        )
    source_times = [
        _utc(reliable.get("collected_at_utc"), "reliable_market_collection.collected_at_utc")[1],
        _utc(reliable["market_feed"].get("collected_at_utc"), "market_feed.collected_at_utc")[1],
    ]
    if slate.get("collected_at_utc") is not None:
        source_times.append(
            _utc(slate.get("collected_at_utc"), "official_slate.collected_at_utc")[1]
        )
    if any(source_time > created and (source_time - created).total_seconds() > tolerance for source_time in source_times):
        raise MLBStep19EPersistenceIntegrityError(
            "source data timestamp is too far in the future relative to checkpoint"
        )

    envelope: dict[str, Any] = {
        "data_type": ENVELOPE_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "contract_status": CONTRACT_STATUS,
        "checkpoint_date": checkpoint,
        "checkpoint_key": checkpoint_key_for_date(checkpoint),
        "step19e_base_main_sha": STEP19E_BASE_MAIN_SHA,
        "step19a_source_blob_sha": STEP19A_SOURCE_BLOB_SHA,
        "step19b_source_blob_sha": STEP19B_SOURCE_BLOB_SHA,
        "step19c_source_blob_sha": STEP19C_SOURCE_BLOB_SHA,
        "step19d_source_blob_sha": STEP19D_SOURCE_BLOB_SHA,
        "step19b_final_certification_marker": step19b.FINAL_CERTIFICATION_MARKER,
        "step19c_final_certification_marker": step19c.FINAL_CERTIFICATION_MARKER,
        "step19d_final_certification_marker": step19d.FINAL_CERTIFICATION_MARKER,
        "official_slate": deepcopy(slate),
        "official_slate_sha256": _hash(slate),
        "reliable_market_collection": deepcopy(reliable),
        "reliable_market_collection_sha256": _hash(reliable),
        "market_feed_sha256": _hash(reliable["market_feed"]),
        "identity_registry": deepcopy(registry),
        "identity_registry_sha256": _hash(registry),
        "reliability_state_sha256": _hash(state),
        "created_at_utc": created_text,
    }
    envelope["envelope_content_sha256"] = _hash(
        {key: deepcopy(value) for key, value in envelope.items() if key != "envelope_content_sha256"}
    )
    return envelope


def validate_step19e_checkpoint_envelope(
    envelope: Mapping[str, Any] | None,
    *,
    expected_checkpoint_date: str | date | None = None,
    now_utc: str | datetime | None = None,
    max_checkpoint_age_seconds: float | None = None,
    future_tolerance_seconds: float = DEFAULT_FUTURE_TOLERANCE_SECONDS,
) -> dict[str, Any]:
    failures: list[str] = []
    if not isinstance(envelope, Mapping):
        return {
            "data_type": ENVELOPE_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "envelope_valid": False,
            "failures": ["STEP19E_ENVELOPE_NOT_MAPPING"],
        }
    value = dict(envelope)
    missing = sorted(_ENVELOPE_KEYS - set(value))
    unknown = sorted(set(value) - _ENVELOPE_KEYS)
    if missing:
        failures.append("STEP19E_ENVELOPE_MISSING_KEYS:" + ",".join(missing))
    if unknown:
        failures.append("STEP19E_ENVELOPE_UNKNOWN_KEYS:" + ",".join(unknown))
    if failures:
        return {
            "data_type": ENVELOPE_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "envelope_valid": False,
            "failures": failures,
        }

    try:
        checkpoint = _checkpoint_date(value["checkpoint_date"])
        if expected_checkpoint_date is not None:
            expected = _checkpoint_date(expected_checkpoint_date)
            if checkpoint != expected:
                raise MLBStep19EPersistenceIntegrityError(
                    "checkpoint_date does not match expected checkpoint date"
                )
        exact = {
            "data_type": value["data_type"] == ENVELOPE_DATA_TYPE,
            "schema_version": value["schema_version"] == SCHEMA_VERSION,
            "contract_id": value["contract_id"] == CONTRACT_ID,
            "contract_version": value["contract_version"] == CONTRACT_VERSION,
            "contract_status": value["contract_status"] == CONTRACT_STATUS,
            "checkpoint_key": value["checkpoint_key"] == checkpoint_key_for_date(checkpoint),
            "step19e_base_main_sha": value["step19e_base_main_sha"] == STEP19E_BASE_MAIN_SHA,
            "step19a_blob": value["step19a_source_blob_sha"] == STEP19A_SOURCE_BLOB_SHA,
            "step19b_blob": value["step19b_source_blob_sha"] == STEP19B_SOURCE_BLOB_SHA,
            "step19c_blob": value["step19c_source_blob_sha"] == STEP19C_SOURCE_BLOB_SHA,
            "step19d_blob": value["step19d_source_blob_sha"] == STEP19D_SOURCE_BLOB_SHA,
            "step19b_marker": value["step19b_final_certification_marker"] == step19b.FINAL_CERTIFICATION_MARKER,
            "step19c_marker": value["step19c_final_certification_marker"] == step19c.FINAL_CERTIFICATION_MARKER,
            "step19d_marker": value["step19d_final_certification_marker"] == step19d.FINAL_CERTIFICATION_MARKER,
        }
        bad = [name for name, ok in exact.items() if not ok]
        if bad:
            raise MLBStep19EPersistenceIntegrityError(
                "checkpoint lineage/contract mismatch: " + ", ".join(bad)
            )
        slate, reliable, registry, state = _validate_cross_layer_inputs(
            checkpoint_date=checkpoint,
            official_slate=value["official_slate"],
            reliable_market_collection=value["reliable_market_collection"],
            identity_registry=value["identity_registry"],
        )
        hashes = {
            "official_slate_sha256": _hash(slate),
            "reliable_market_collection_sha256": _hash(reliable),
            "market_feed_sha256": _hash(reliable["market_feed"]),
            "identity_registry_sha256": _hash(registry),
            "reliability_state_sha256": _hash(state),
        }
        for field, expected_hash in hashes.items():
            if _valid_sha(value[field], field) != expected_hash:
                raise MLBStep19EPersistenceIntegrityError(
                    f"{field} content hash mismatch"
                )
        expected_envelope_hash = _hash(
            {
                key: deepcopy(item)
                for key, item in value.items()
                if key != "envelope_content_sha256"
            }
        )
        if _valid_sha(
            value["envelope_content_sha256"], "envelope_content_sha256"
        ) != expected_envelope_hash:
            raise MLBStep19EPersistenceIntegrityError(
                "envelope_content_sha256 mismatch"
            )

        created_text, created = _utc(value["created_at_utc"], "created_at_utc")
        if created_text != value["created_at_utc"]:
            raise MLBStep19EPersistenceIntegrityError(
                "created_at_utc must use canonical UTC Z format"
            )
        tolerance = float(future_tolerance_seconds)
        if tolerance < 0 or tolerance > 60:
            raise MLBStep19EPersistenceInputError(
                "future_tolerance_seconds must be between 0 and 60"
            )
        if now_utc is not None:
            _, now = _utc(now_utc, "now_utc")
            if created > now and (created - now).total_seconds() > tolerance:
                raise MLBStep19EPersistenceIntegrityError(
                    "checkpoint timestamp is too far in the future"
                )
            if max_checkpoint_age_seconds is not None:
                max_age = float(max_checkpoint_age_seconds)
                if max_age <= 0 or max_age > 86400:
                    raise MLBStep19EPersistenceInputError(
                        "max_checkpoint_age_seconds must be between 0 and 86400"
                    )
                age = (now - created).total_seconds()
                if age > max_age:
                    raise MLBStep19EPersistenceIntegrityError(
                        "checkpoint is stale"
                    )
    except Exception as exc:
        failures.append(
            f"STEP19E_ENVELOPE_INVALID:{type(exc).__name__}:{exc}"
        )

    return {
        "data_type": ENVELOPE_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "envelope_valid": not failures,
        "failures": failures,
    }


def checkpoint_id_for_envelope(envelope: Mapping[str, Any]) -> str:
    if not isinstance(envelope, Mapping):
        raise MLBStep19EPersistenceInputError("checkpoint_envelope must be a mapping")
    key = str(envelope.get("checkpoint_key") or "").strip()
    digest = str(envelope.get("envelope_content_sha256") or "").strip()
    if not key or _SHA256_RE.fullmatch(digest) is None:
        raise MLBStep19EPersistenceInputError(
            "checkpoint identity requires checkpoint_key and valid envelope hash"
        )
    return str(uuid5(NAMESPACE_URL, f"kyre-sports-ai:mlb:step19e:{key}:{digest}"))


def persistence_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step19e_base_main_sha": STEP19E_BASE_MAIN_SHA,
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "contract_status": CONTRACT_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "database_schema": DATABASE_SCHEMA_NAME,
        "checkpoint_table": CHECKPOINT_TABLE_NAME,
        "checkpoint_head_table": CHECKPOINT_HEAD_TABLE_NAME,
        "sql_schema_path": SQL_SCHEMA_PATH,
        "sql_schema_sha256": SQL_SCHEMA_SHA256,
        "separate_from_frozen_step14_tables": True,
        "explicit_adapter_gate_required": True,
        "explicit_read_gate_required": True,
        "explicit_write_gate_required": True,
        "postgresql_database_read_allowed": POSTGRESQL_DATABASE_READ_ALLOWED,
        "postgresql_database_write_allowed": POSTGRESQL_DATABASE_WRITE_ALLOWED,
        "append_only_history_required": APPEND_ONLY_HISTORY_REQUIRED,
        "atomic_head_compare_and_swap_required": ATOMIC_HEAD_COMPARE_AND_SWAP_REQUIRED,
        "content_addressing_required": CONTENT_ADDRESSING_REQUIRED,
        "durable_restart_recovery_allowed": DURABLE_RESTART_RECOVERY_ALLOWED,
        "reliability_state_recovery_allowed": RELIABILITY_STATE_RECOVERY_ALLOWED,
        "schema_auto_apply_allowed": SCHEMA_AUTO_APPLY_ALLOWED,
        "production_runtime_wiring_added_by_step19e": PRODUCTION_RUNTIME_WIRING_ADDED,
        "production_scheduler_mutation_added_by_step19e": PRODUCTION_SCHEDULER_MUTATION_ADDED,
        "provider_network_calls_added_by_step19e": PROVIDER_NETWORK_CALLS_ADDED,
        "sportsbook_network_calls_added_by_step19e": SPORTSBOOK_NETWORK_CALLS_ADDED,
        "model_probability_mutation_enabled": MODEL_PROBABILITY_MUTATION_ENABLED,
        "projection_mutation_enabled": PROJECTION_MUTATION_ENABLED,
        "actionable_output_enabled": ACTIONABLE_OUTPUT_ENABLED,
        "wagering_enabled": WAGERING_ENABLED,
        "source_lineage": {
            "step19a_source_blob_sha": STEP19A_SOURCE_BLOB_SHA,
            "step19b_source_blob_sha": STEP19B_SOURCE_BLOB_SHA,
            "step19c_source_blob_sha": STEP19C_SOURCE_BLOB_SHA,
            "step19d_source_blob_sha": STEP19D_SOURCE_BLOB_SHA,
            "step19b_final_certification_marker": step19b.FINAL_CERTIFICATION_MARKER,
            "step19c_final_certification_marker": step19c.FINAL_CERTIFICATION_MARKER,
            "step19d_final_certification_marker": step19d.FINAL_CERTIFICATION_MARKER,
        },
    }


def _assert_schema_source_integrity() -> None:
    try:
        observed = hashlib.sha256(Path(SQL_SCHEMA_PATH).read_bytes()).hexdigest()
    except OSError as exc:
        raise MLBStep19EPersistenceIntegrityError(
            "Step19E cannot read SQL schema source"
        ) from exc
    if observed != SQL_SCHEMA_SHA256:
        raise MLBStep19EPersistenceIntegrityError(
            "Step19E SQL schema hash drift"
        )


def _assert_adapter_enabled(
    env: Mapping[str, str] | None,
    *,
    read: bool,
    write: bool,
) -> None:
    source = os.environ if env is None else env
    if not persistence_adapter_enabled(source):
        raise MLBStep19EPersistenceDisabledError(
            f"Step19E requires {ADAPTER_ENABLED_ENV}=true"
        )
    if read and not database_read_enabled(source):
        raise MLBStep19EPersistenceDisabledError(
            f"Step19E reads require {DATABASE_READ_ENABLED_ENV}=true"
        )
    if write and not database_write_enabled(source):
        raise MLBStep19EPersistenceDisabledError(
            f"Step19E writes require {DATABASE_WRITE_ENABLED_ENV}=true"
        )
    _assert_schema_source_integrity()


def _open_connection(
    env: Mapping[str, str] | None,
    connection_factory: Callable[[], Any] | None,
) -> Any:
    if connection_factory is not None:
        try:
            connection = connection_factory()
        except Exception as exc:
            raise MLBStep19EPersistenceDatabaseError(
                "injected database connection factory failed"
            ) from exc
        if connection is None:
            raise MLBStep19EPersistenceDatabaseError(
                "database connection factory returned no connection"
            )
        return connection
    source = os.environ if env is None else env
    dsn = str(source.get(DATABASE_URL_ENV) or "").strip()
    if not dsn:
        raise MLBStep19EPersistenceDisabledError(
            f"live PostgreSQL access requires {DATABASE_URL_ENV}"
        )
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise MLBStep19EPersistenceDatabaseError(
            "live PostgreSQL access requires psycopg 3"
        ) from exc
    try:
        return psycopg.connect(
            dsn,
            connect_timeout=10,
            application_name="kyre-sports-ai-mlb-step19e",
        )
    except Exception as exc:
        raise MLBStep19EPersistenceDatabaseError(
            "could not open Step19E PostgreSQL connection"
        ) from exc


def _safe_close(value: Any) -> None:
    try:
        closer = getattr(value, "close", None)
        if callable(closer):
            closer()
    except Exception:
        pass


def _safe_rollback(connection: Any) -> None:
    try:
        rollback = getattr(connection, "rollback", None)
        if callable(rollback):
            rollback()
    except Exception:
        pass


def _verify_schema(cursor: Any) -> None:
    cursor.execute(
        _SCHEMA_EXISTENCE_SQL,
        (
            f"{DATABASE_SCHEMA_NAME}.{CHECKPOINT_TABLE_NAME}",
            f"{DATABASE_SCHEMA_NAME}.{CHECKPOINT_HEAD_TABLE_NAME}",
        ),
    )
    row = cursor.fetchone()
    if not isinstance(row, (tuple, list)) or len(row) != 2:
        raise MLBStep19EPersistenceSchemaError(
            "schema probe returned invalid shape"
        )
    if row[0] is not True or row[1] is not True:
        raise MLBStep19EPersistenceSchemaError(
            "both Step19E checkpoint tables are required"
        )


def verify_step19e_database_schema(
    *,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    _assert_adapter_enabled(env, read=True, write=False)
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_schema(cursor)
        _safe_rollback(connection)
    except (MLBStep19EPersistenceDisabledError, MLBStep19EPersistenceIntegrityError, MLBStep19EPersistenceSchemaError):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise MLBStep19EPersistenceDatabaseError(
            "Step19E schema verification failed"
        ) from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)
    return {
        "data_type": SCHEMA_CHECK_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "database_schema": DATABASE_SCHEMA_NAME,
        "checkpoint_table": CHECKPOINT_TABLE_NAME,
        "checkpoint_head_table": CHECKPOINT_HEAD_TABLE_NAME,
        "tables_present": True,
        "database_write_performed": False,
        "schema_auto_apply_performed": False,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
    }


def _decode_envelope(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        decoded = dict(value)
    elif isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise MLBStep19EPersistenceIntegrityError(
                "persisted envelope JSON is malformed"
            ) from exc
    else:
        raise MLBStep19EPersistenceIntegrityError(
            "persisted envelope must be a JSON object"
        )
    if not isinstance(decoded, dict):
        raise MLBStep19EPersistenceIntegrityError(
            "persisted envelope did not decode to object"
        )
    return decoded


def _normalize_head_row(
    row: Any,
    *,
    expected_checkpoint_date: str,
    now_utc: str | datetime | None,
    max_checkpoint_age_seconds: float | None,
    future_tolerance_seconds: float,
) -> dict[str, Any] | None:
    if row is None:
        return None
    if not isinstance(row, (tuple, list)) or len(row) != 14:
        raise MLBStep19EPersistenceIntegrityError(
            "checkpoint-head query returned invalid row shape"
        )
    (
        head_version,
        head_id,
        head_hash,
        history_version,
        history_id,
        history_key,
        history_date,
        history_contract_version,
        history_slate_hash,
        history_market_hash,
        history_identity_hash,
        history_reliability_hash,
        history_envelope_hash,
        envelope_json,
    ) = row
    if (
        isinstance(head_version, bool)
        or not isinstance(head_version, int)
        or head_version < 1
        or history_version != head_version
    ):
        raise MLBStep19EPersistenceIntegrityError(
            "persisted checkpoint version mismatch"
        )
    try:
        head_uuid = str(UUID(str(head_id)))
        history_uuid = str(UUID(str(history_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MLBStep19EPersistenceIntegrityError(
            "persisted checkpoint UUID is invalid"
        ) from exc
    if head_uuid != history_uuid:
        raise MLBStep19EPersistenceIntegrityError(
            "head/history checkpoint UUID mismatch"
        )
    if str(head_hash) != str(history_envelope_hash):
        raise MLBStep19EPersistenceIntegrityError(
            "head/history envelope hash mismatch"
        )
    envelope = _decode_envelope(envelope_json)
    validation = validate_step19e_checkpoint_envelope(
        envelope,
        expected_checkpoint_date=expected_checkpoint_date,
        now_utc=now_utc,
        max_checkpoint_age_seconds=max_checkpoint_age_seconds,
        future_tolerance_seconds=future_tolerance_seconds,
    )
    if validation.get("envelope_valid") is not True:
        raise MLBStep19EPersistenceIntegrityError(
            "persisted Step19E envelope failed validation: "
            + repr(validation.get("failures"))
        )
    expected_key = checkpoint_key_for_date(expected_checkpoint_date)
    checks = {
        "checkpoint_key": str(history_key) == expected_key == envelope["checkpoint_key"],
        "checkpoint_date": str(history_date) == envelope["checkpoint_date"],
        "contract_version": str(history_contract_version) == CONTRACT_VERSION,
        "official_slate_sha256": str(history_slate_hash) == envelope["official_slate_sha256"],
        "market_feed_sha256": str(history_market_hash) == envelope["market_feed_sha256"],
        "identity_registry_sha256": str(history_identity_hash) == envelope["identity_registry_sha256"],
        "reliability_state_sha256": str(history_reliability_hash) == envelope["reliability_state_sha256"],
        "envelope_content_sha256": str(history_envelope_hash) == envelope["envelope_content_sha256"],
        "checkpoint_id": head_uuid == checkpoint_id_for_envelope(envelope),
    }
    bad = [name for name, ok in checks.items() if not ok]
    if bad:
        raise MLBStep19EPersistenceIntegrityError(
            "persisted row/envelope mismatch: " + ", ".join(bad)
        )
    return {
        "checkpoint_version": head_version,
        "checkpoint_id": head_uuid,
        "envelope": deepcopy(envelope),
    }


def _result(
    *,
    operation: str,
    status: str,
    checkpoint_date: str,
    normalized: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if normalized is None:
        return {
            "data_type": RESULT_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "operation": operation,
            "status": status,
            "found": False,
            "checkpoint_date": checkpoint_date,
            "checkpoint_key": checkpoint_key_for_date(checkpoint_date),
            "checkpoint_version": None,
            "checkpoint_id": None,
            "envelope_content_sha256": None,
            "checkpoint_envelope": None,
            "official_slate_for_restart": None,
            "market_feed_for_restart": None,
            "identity_registry_for_restart": None,
            "reliability_state_for_restart": None,
            "production_runtime_wiring": False,
            "model_probability_mutation": False,
            "projection_mutation": False,
            "actionable_output": False,
            "wagering": False,
        }
    envelope = deepcopy(dict(normalized["envelope"]))
    reliable = envelope["reliable_market_collection"]
    return {
        "data_type": RESULT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "operation": operation,
        "status": status,
        "found": True,
        "checkpoint_date": checkpoint_date,
        "checkpoint_key": envelope["checkpoint_key"],
        "checkpoint_version": int(normalized["checkpoint_version"]),
        "checkpoint_id": str(normalized["checkpoint_id"]),
        "envelope_content_sha256": envelope["envelope_content_sha256"],
        "checkpoint_envelope": envelope,
        "official_slate_for_restart": deepcopy(envelope["official_slate"]),
        "market_feed_for_restart": deepcopy(reliable["market_feed"]),
        "identity_registry_for_restart": deepcopy(envelope["identity_registry"]),
        "reliability_state_for_restart": deepcopy(reliable["reliability_state"]),
        "production_runtime_wiring": False,
        "model_probability_mutation": False,
        "projection_mutation": False,
        "actionable_output": False,
        "wagering": False,
    }


def load_step19e_checkpoint(
    *,
    checkpoint_date: str | date,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
    now_utc: str | datetime | None = None,
    max_checkpoint_age_seconds: float | None = DEFAULT_MAX_CHECKPOINT_AGE_SECONDS,
    future_tolerance_seconds: float = DEFAULT_FUTURE_TOLERANCE_SECONDS,
) -> dict[str, Any]:
    """Load, hash-check, cross-validate, and freshness-check the durable head."""
    _assert_adapter_enabled(env, read=True, write=False)
    checkpoint = _checkpoint_date(checkpoint_date)
    key = checkpoint_key_for_date(checkpoint)
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_schema(cursor)
        cursor.execute(_HEAD_SELECT_SQL, (key,))
        normalized = _normalize_head_row(
            cursor.fetchone(),
            expected_checkpoint_date=checkpoint,
            now_utc=now_utc,
            max_checkpoint_age_seconds=max_checkpoint_age_seconds,
            future_tolerance_seconds=future_tolerance_seconds,
        )
        _safe_rollback(connection)
    except (
        MLBStep19EPersistenceDisabledError,
        MLBStep19EPersistenceIntegrityError,
        MLBStep19EPersistenceSchemaError,
        MLBStep19EPersistenceInputError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise MLBStep19EPersistenceDatabaseError(
            "Step19E checkpoint load failed"
        ) from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)
    return _result(
        operation="load",
        status="not_found" if normalized is None else "loaded",
        checkpoint_date=checkpoint,
        normalized=normalized,
    )


def save_step19e_checkpoint(
    *,
    checkpoint_envelope: Mapping[str, Any],
    expected_head_version: int,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
    generated_at_utc: str | datetime | None = None,
) -> dict[str, Any]:
    """Append one valid checkpoint and CAS-advance its per-date head."""
    _assert_adapter_enabled(env, read=True, write=True)
    if (
        isinstance(expected_head_version, bool)
        or not isinstance(expected_head_version, int)
        or expected_head_version < 0
    ):
        raise MLBStep19EPersistenceInputError(
            "expected_head_version must be an integer >= 0"
        )
    validation = validate_step19e_checkpoint_envelope(checkpoint_envelope)
    if validation.get("envelope_valid") is not True:
        raise MLBStep19EPersistenceIntegrityError(
            "checkpoint candidate failed validation: "
            + repr(validation.get("failures"))
        )
    envelope = deepcopy(dict(checkpoint_envelope))
    checkpoint = envelope["checkpoint_date"]
    key = envelope["checkpoint_key"]
    checkpoint_id = checkpoint_id_for_envelope(envelope)
    _, created = _utc(envelope["created_at_utc"], "created_at_utc")
    _, write_time = _utc(
        generated_at_utc or datetime.now(timezone.utc),
        "generated_at_utc",
    )

    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_schema(cursor)
        cursor.execute(_HEAD_SELECT_FOR_UPDATE_SQL, (key,))
        current = _normalize_head_row(
            cursor.fetchone(),
            expected_checkpoint_date=checkpoint,
            now_utc=None,
            max_checkpoint_age_seconds=None,
            future_tolerance_seconds=DEFAULT_FUTURE_TOLERANCE_SECONDS,
        )
        current_version = 0 if current is None else int(current["checkpoint_version"])
        if (
            current is not None
            and current["envelope"]["envelope_content_sha256"]
            == envelope["envelope_content_sha256"]
        ):
            _safe_rollback(connection)
            return _result(
                operation="save",
                status="idempotent",
                checkpoint_date=checkpoint,
                normalized=current,
            )
        if current_version != expected_head_version:
            raise MLBStep19EPersistenceConflictError(
                "checkpoint head CAS conflict: "
                f"expected version {expected_head_version}, current version {current_version}"
            )
        new_version = current_version + 1
        cursor.execute(
            _INSERT_HISTORY_SQL,
            (
                checkpoint_id,
                key,
                new_version,
                checkpoint,
                CONTRACT_VERSION,
                envelope["official_slate_sha256"],
                envelope["market_feed_sha256"],
                envelope["identity_registry_sha256"],
                envelope["reliability_state_sha256"],
                envelope["envelope_content_sha256"],
                json.dumps(
                    envelope,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ),
                created,
            ),
        )
        if current is None:
            cursor.execute(
                _INSERT_HEAD_SQL,
                (
                    key,
                    new_version,
                    checkpoint_id,
                    envelope["envelope_content_sha256"],
                    write_time,
                ),
            )
        else:
            cursor.execute(
                _UPDATE_HEAD_SQL,
                (
                    new_version,
                    checkpoint_id,
                    envelope["envelope_content_sha256"],
                    write_time,
                    key,
                    current_version,
                ),
            )
            if getattr(cursor, "rowcount", 1) != 1:
                raise MLBStep19EPersistenceConflictError(
                    "checkpoint head CAS update affected no row"
                )
        connection.commit()
    except (
        MLBStep19EPersistenceDisabledError,
        MLBStep19EPersistenceIntegrityError,
        MLBStep19EPersistenceSchemaError,
        MLBStep19EPersistenceInputError,
        MLBStep19EPersistenceConflictError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise MLBStep19EPersistenceDatabaseError(
            "Step19E checkpoint save failed"
        ) from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)

    normalized = {
        "checkpoint_version": new_version,
        "checkpoint_id": checkpoint_id,
        "envelope": envelope,
    }
    return _result(
        operation="save",
        status="saved",
        checkpoint_date=checkpoint,
        normalized=normalized,
    )


def recover_step19e_live_data(
    *,
    checkpoint_date: str | date,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
    now_utc: str | datetime | None = None,
    max_checkpoint_age_seconds: float = DEFAULT_MAX_CHECKPOINT_AGE_SECONDS,
    future_tolerance_seconds: float = DEFAULT_FUTURE_TOLERANCE_SECONDS,
) -> dict[str, Any]:
    """Recover only a still-fresh, fully verified Step19 live-data bundle."""
    result = load_step19e_checkpoint(
        checkpoint_date=checkpoint_date,
        env=env,
        connection_factory=connection_factory,
        now_utc=now_utc or datetime.now(timezone.utc),
        max_checkpoint_age_seconds=max_checkpoint_age_seconds,
        future_tolerance_seconds=future_tolerance_seconds,
    )
    if result["found"] is not True:
        raise MLBStep19EPersistenceIntegrityError(
            "no Step19E checkpoint is available for restart"
        )
    recovered = deepcopy(result)
    recovered["operation"] = "recover"
    recovered["status"] = "recovered"
    return recovered


__all__ = [
    "DATA_TYPE",
    "ENVELOPE_DATA_TYPE",
    "RESULT_DATA_TYPE",
    "SCHEMA_CHECK_DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP19E_BASE_MAIN_SHA",
    "CONTRACT_ID",
    "CONTRACT_VERSION",
    "CONTRACT_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "DATABASE_SCHEMA_NAME",
    "CHECKPOINT_TABLE_NAME",
    "CHECKPOINT_HEAD_TABLE_NAME",
    "SQL_SCHEMA_PATH",
    "SQL_SCHEMA_SHA256",
    "ADAPTER_ENABLED_ENV",
    "DATABASE_READ_ENABLED_ENV",
    "DATABASE_WRITE_ENABLED_ENV",
    "DEFAULT_MAX_CHECKPOINT_AGE_SECONDS",
    "DEFAULT_FUTURE_TOLERANCE_SECONDS",
    "MLBStep19EPersistenceDisabledError",
    "MLBStep19EPersistenceInputError",
    "MLBStep19EPersistenceIntegrityError",
    "MLBStep19EPersistenceSchemaError",
    "MLBStep19EPersistenceConflictError",
    "MLBStep19EPersistenceDatabaseError",
    "persistence_manifest",
    "persistence_adapter_enabled",
    "database_read_enabled",
    "database_write_enabled",
    "checkpoint_key_for_date",
    "checkpoint_id_for_envelope",
    "build_step19e_checkpoint_envelope",
    "validate_step19e_checkpoint_envelope",
    "verify_step19e_database_schema",
    "load_step19e_checkpoint",
    "save_step19e_checkpoint",
    "recover_step19e_live_data",
]
