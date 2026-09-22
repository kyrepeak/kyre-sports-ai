from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

from sports_api.collectors.mlb_event_player_identity import (
    build_mlb_event_player_identity_registry,
)
from sports_api.collectors.mlb_provider_reliability import (
    collect_reliable_mlb_market_feed,
)
from sports_api import mlb_step19e_production_persistence_validation_v1 as s19e

NOW = datetime(2026, 9, 2, 4, 15, tzinfo=timezone.utc)
DATE = "2026-09-02"


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _official_slate(*, collected_at: datetime = NOW) -> dict:
    return {
        "sport": "MLB",
        "slate_date": DATE,
        "game_count": 1,
        "games": [
            {
                "game_pk": 1001,
                "game_date": "2026-09-02T23:10:00Z",
                "official_date": DATE,
                "game_type": "R",
                "status": "scheduled",
                "status_detail": "Scheduled",
                "status_code": "S",
                "start_time_tbd": False,
                "away_team": {"id": 10, "name": "Away Club"},
                "home_team": {"id": 20, "name": "Home Club"},
                "away_probable_pitcher": None,
                "home_probable_pitcher": None,
                "doubleheader": False,
                "doubleheader_code": "N",
                "game_number": 1,
                "series_game_number": 1,
                "scheduled_innings": 9,
                "reschedule_date": None,
                "is_postponed": False,
                "is_cancelled": False,
            }
        ],
        "collected_at_utc": _iso(collected_at),
        "source": "MLB Stats API",
    }


def _fanduel_game() -> dict:
    return {
        "official_game_id": 1001,
        "sportsbook_event_id": "fd-event-1",
        "sportsbook_event_name": "Away Club @ Home Club",
        "official_schedule_match": "teams_exact",
        "scheduled_start_utc": "2026-09-02T23:10:00Z",
        "sportsbook_start_utc": "2026-09-02T23:10:00Z",
        "game_status": "Scheduled",
        "away_team": {"id": 10, "name": "Away Club"},
        "home_team": {"id": 20, "name": "Home Club"},
        "sportsbook": "FanDuel",
        "sportsbook_region": "NJ",
        "markets": {
            "moneyline": {
                "market_id": "fd-event-1-ml",
                "market_time_utc": "2026-09-02T23:10:00Z",
                "away_odds": -120,
                "home_odds": 110,
                "away_selection_id": "a-ml",
                "home_selection_id": "h-ml",
            },
            "run_line": {
                "market_id": "fd-event-1-rl",
                "market_time_utc": "2026-09-02T23:10:00Z",
                "away_line": 1.5,
                "away_odds": -105,
                "home_line": -1.5,
                "home_odds": -115,
                "away_selection_id": "a-rl",
                "home_selection_id": "h-rl",
            },
            "total": {
                "market_id": "fd-event-1-tot",
                "market_time_utc": "2026-09-02T23:10:00Z",
                "line": 8.5,
                "over_odds": -110,
                "under_odds": -110,
                "over_selection_id": "o-tot",
                "under_selection_id": "u-tot",
            },
        },
        "market_availability": {
            "moneyline": True,
            "run_line": True,
            "total": True,
        },
        "fully_priced": True,
    }


def _fd_collection(*, collected_at: datetime = NOW, rejected: bool = False) -> dict:
    return {
        "data_type": "mlb_live_game_odds_snapshot_v1",
        "schema_version": 1,
        "collected_at_utc": _iso(collected_at),
        "provider": "FanDuel",
        "games": [_fanduel_game()],
        "rejected_events": [{"reason": "bad"}] if rejected else [],
    }


def _blank_provider_state() -> dict:
    return {
        "cooldown_until_utc": None,
        "cooldown_reason": None,
        "last_failure_kind": None,
        "last_failure_at_utc": None,
        "last_success_at_utc": None,
    }


def _initial_state(*, draftkings_cooldown: bool = False) -> dict:
    state = {
        "schema_version": 1,
        "providers": {
            "fanduel": _blank_provider_state(),
            "draftkings": _blank_provider_state(),
        },
    }
    if draftkings_cooldown:
        state["providers"]["draftkings"].update(
            {
                "cooldown_until_utc": _iso(NOW + timedelta(seconds=90)),
                "cooldown_reason": "rate_limited",
                "last_failure_kind": "rate_limited",
                "last_failure_at_utc": _iso(NOW),
            }
        )
    return state


def _reliable(
    *,
    now: datetime = NOW,
    collection_time: datetime | None = None,
    draftkings_cooldown: bool = False,
    rejected_upstream: bool = False,
) -> dict:
    collected = now if collection_time is None else collection_time
    return collect_reliable_mlb_market_feed(
        now_utc=now,
        reliability_state=_initial_state(
            draftkings_cooldown=draftkings_cooldown
        ),
        include_fanduel_game_odds=True,
        include_fanduel_player_props=False,
        include_draftkings=False,
        fanduel_game_collector=lambda **_: _fd_collection(
            collected_at=collected,
            rejected=rejected_upstream,
        ),
        sleeper=lambda _: None,
    )


def _inputs(
    *,
    now: datetime = NOW,
    draftkings_cooldown: bool = False,
) -> tuple[dict, dict, dict]:
    slate = _official_slate(collected_at=now)
    reliable = _reliable(
        now=now,
        draftkings_cooldown=draftkings_cooldown,
    )
    registry = build_mlb_event_player_identity_registry(
        official_slate=slate,
        market_feed=reliable["market_feed"],
    )
    return slate, reliable, registry


def _envelope(
    *,
    now: datetime = NOW,
    created_at: datetime | None = None,
    draftkings_cooldown: bool = False,
) -> dict:
    slate, reliable, registry = _inputs(
        now=now,
        draftkings_cooldown=draftkings_cooldown,
    )
    return s19e.build_step19e_checkpoint_envelope(
        checkpoint_date=DATE,
        official_slate=slate,
        reliable_market_collection=reliable,
        identity_registry=registry,
        created_at_utc=created_at or now,
    )


def _safe_env(*, read: bool = True, write: bool = True) -> dict[str, str]:
    return {
        s19e.ADAPTER_ENABLED_ENV: "true",
        s19e.DATABASE_READ_ENABLED_ENV: "true" if read else "false",
        s19e.DATABASE_WRITE_ENABLED_ENV: "true" if write else "false",
        "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
        "MLB_WAGERING_ENABLED": "false",
    }


def _rehash(envelope: dict) -> None:
    def digest(value):
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    envelope["official_slate_sha256"] = digest(envelope["official_slate"])
    reliable = envelope["reliable_market_collection"]
    envelope["reliable_market_collection_sha256"] = digest(reliable)
    envelope["market_feed_sha256"] = digest(reliable["market_feed"])
    envelope["identity_registry_sha256"] = digest(envelope["identity_registry"])
    envelope["reliability_state_sha256"] = digest(reliable["reliability_state"])
    envelope["envelope_content_sha256"] = digest(
        {
            key: deepcopy(value)
            for key, value in envelope.items()
            if key != "envelope_content_sha256"
        }
    )


def _row(envelope: dict, version: int = 1):
    checkpoint_id = s19e.checkpoint_id_for_envelope(envelope)
    return (
        version,
        checkpoint_id,
        envelope["envelope_content_sha256"],
        version,
        checkpoint_id,
        envelope["checkpoint_key"],
        envelope["checkpoint_date"],
        envelope["contract_version"],
        envelope["official_slate_sha256"],
        envelope["market_feed_sha256"],
        envelope["identity_registry_sha256"],
        envelope["reliability_state_sha256"],
        envelope["envelope_content_sha256"],
        deepcopy(envelope),
    )


class FakeCursor:
    def __init__(self, script):
        self.script = list(script)
        self.current = None
        self.rowcount = -1
        self.calls = []
        self.closed = False

    def execute(self, sql, params=None):
        if not self.script:
            raise AssertionError(f"unexpected SQL: {sql}")
        step = self.script.pop(0)
        contains = step.get("contains")
        if contains and contains not in sql:
            raise AssertionError(f"expected {contains!r} in SQL: {sql}")
        self.calls.append((sql, params))
        if step.get("raise") is not None:
            raise step["raise"]
        self.current = step
        self.rowcount = step.get("rowcount", -1)

    def fetchone(self):
        return None if self.current is None else self.current.get("fetchone")

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, script):
        self.cursor_obj = FakeCursor(script)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _factory(script):
    box = {}

    def factory():
        box["connection"] = FakeConnection(script)
        return box["connection"]

    return factory, box


def _schema_step(*, present: bool = True):
    return {"contains": "to_regclass", "fetchone": (present, present)}


def _load_script(row):
    return [
        _schema_step(),
        {
            "contains": f"JOIN {s19e.DATABASE_SCHEMA_NAME}.{s19e.CHECKPOINT_TABLE_NAME}",
            "fetchone": row,
        },
    ]


def _save_initial_script():
    return [
        _schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": None},
        {
            "contains": f"INSERT INTO {s19e.DATABASE_SCHEMA_NAME}.{s19e.CHECKPOINT_TABLE_NAME}",
            "rowcount": 1,
        },
        {
            "contains": f"INSERT INTO {s19e.DATABASE_SCHEMA_NAME}.{s19e.CHECKPOINT_HEAD_TABLE_NAME}",
            "rowcount": 1,
        },
    ]


def test_manifest_pins_step19_lineage_and_separate_tables():
    manifest = s19e.persistence_manifest()
    assert manifest["step19e_base_main_sha"] == "4e9f5494f520b2c491b0820d3069baecd49124b3"
    assert manifest["separate_from_frozen_step14_tables"] is True
    assert manifest["append_only_history_required"] is True
    assert manifest["atomic_head_compare_and_swap_required"] is True
    assert manifest["content_addressing_required"] is True
    assert manifest["production_runtime_wiring_added_by_step19e"] is False
    assert manifest["actionable_output_enabled"] is False
    assert manifest["wagering_enabled"] is False


def test_sql_source_hash_is_pinned():
    observed = hashlib.sha256(Path(s19e.SQL_SCHEMA_PATH).read_bytes()).hexdigest()
    assert observed == s19e.SQL_SCHEMA_SHA256


def test_adapter_gates_default_off():
    assert s19e.persistence_adapter_enabled({}) is False
    assert s19e.database_read_enabled({}) is False
    assert s19e.database_write_enabled({}) is False


def test_checkpoint_key_is_deterministic():
    assert s19e.checkpoint_key_for_date(DATE) == "mlb:step19e:live-data:2026-09-02"


def test_build_checkpoint_is_valid_and_content_addressed():
    envelope = _envelope()
    validation = s19e.validate_step19e_checkpoint_envelope(
        envelope,
        expected_checkpoint_date=DATE,
        now_utc=NOW,
        max_checkpoint_age_seconds=300,
    )
    assert validation["envelope_valid"] is True
    assert len(envelope["envelope_content_sha256"]) == 64
    assert len(envelope["official_slate_sha256"]) == 64
    assert len(envelope["market_feed_sha256"]) == 64
    assert len(envelope["identity_registry_sha256"]) == 64
    assert len(envelope["reliability_state_sha256"]) == 64


def test_build_checkpoint_deep_copies_inputs():
    slate, reliable, registry = _inputs()
    original = deepcopy((slate, reliable, registry))
    envelope = s19e.build_step19e_checkpoint_envelope(
        checkpoint_date=DATE,
        official_slate=slate,
        reliable_market_collection=reliable,
        identity_registry=registry,
        created_at_utc=NOW,
    )
    envelope["official_slate"]["games"][0]["status"] = "changed"
    envelope["reliable_market_collection"]["reliability_state"]["providers"]["fanduel"][
        "last_success_at_utc"
    ] = None
    assert (slate, reliable, registry) == original


def test_checkpoint_id_is_deterministic():
    envelope = _envelope()
    assert s19e.checkpoint_id_for_envelope(envelope) == s19e.checkpoint_id_for_envelope(
        deepcopy(envelope)
    )


def test_missing_envelope_key_fails_closed():
    envelope = _envelope()
    envelope.pop("market_feed_sha256")
    result = s19e.validate_step19e_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is False


def test_unknown_envelope_key_fails_closed():
    envelope = _envelope()
    envelope["surprise"] = True
    result = s19e.validate_step19e_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is False


def test_corrupt_envelope_hash_fails_closed():
    envelope = _envelope()
    envelope["envelope_content_sha256"] = "0" * 64
    result = s19e.validate_step19e_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is False


def test_corrupt_section_hash_fails_closed():
    envelope = _envelope()
    envelope["market_feed_sha256"] = "0" * 64
    envelope["envelope_content_sha256"] = hashlib.sha256(
        json.dumps(
            {k: v for k, v in envelope.items() if k != "envelope_content_sha256"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    result = s19e.validate_step19e_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is False


def test_cross_layer_game_id_mismatch_fails_even_when_rehashed():
    envelope = _envelope()
    envelope["official_slate"]["games"][0]["game_pk"] = 9999
    _rehash(envelope)
    result = s19e.validate_step19e_checkpoint_envelope(envelope)
    assert result["envelope_valid"] is False


def test_incomplete_surface_fails_before_checkpoint_build():
    slate, reliable, registry = _inputs()
    reliable["market_feed"]["successful_surface_count"] = 0
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.build_step19e_checkpoint_envelope(
            checkpoint_date=DATE,
            official_slate=slate,
            reliable_market_collection=reliable,
            identity_registry=registry,
            created_at_utc=NOW,
        )


def test_upstream_rejected_record_fails_before_checkpoint_build():
    slate = _official_slate()
    reliable = _reliable(rejected_upstream=True)
    registry = build_mlb_event_player_identity_registry(
        official_slate=slate,
        market_feed=reliable["market_feed"],
    )
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.build_step19e_checkpoint_envelope(
            checkpoint_date=DATE,
            official_slate=slate,
            reliable_market_collection=reliable,
            identity_registry=registry,
            created_at_utc=NOW,
        )


def test_price_fabrication_flag_fails_closed():
    slate, reliable, registry = _inputs()
    reliable["price_fabrication_used"] = True
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.build_step19e_checkpoint_envelope(
            checkpoint_date=DATE,
            official_slate=slate,
            reliable_market_collection=reliable,
            identity_registry=registry,
            created_at_utc=NOW,
        )


def test_synthetic_market_game_id_fails_closed():
    slate, reliable, registry = _inputs()
    reliable["market_feed"]["game_market_snapshots"][0]["synthetic_game_id_used"] = True
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.build_step19e_checkpoint_envelope(
            checkpoint_date=DATE,
            official_slate=slate,
            reliable_market_collection=reliable,
            identity_registry=registry,
            created_at_utc=NOW,
        )


def test_rejected_identity_fails_closed():
    slate, reliable, registry = _inputs()
    registry["rejected_event_identity_count"] = 1
    registry["identity_complete_for_all_market_games"] = False
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.build_step19e_checkpoint_envelope(
            checkpoint_date=DATE,
            official_slate=slate,
            reliable_market_collection=reliable,
            identity_registry=registry,
            created_at_utc=NOW,
        )


def test_identity_market_event_mismatch_fails_closed():
    slate, reliable, registry = _inputs()
    registry["event_identities"][0]["provider_event_id"] = "wrong"
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.build_step19e_checkpoint_envelope(
            checkpoint_date=DATE,
            official_slate=slate,
            reliable_market_collection=reliable,
            identity_registry=registry,
            created_at_utc=NOW,
        )


def test_malformed_reliability_state_fails_closed():
    slate, reliable, registry = _inputs()
    reliable["reliability_state"]["providers"]["extra"] = _blank_provider_state()
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.build_step19e_checkpoint_envelope(
            checkpoint_date=DATE,
            official_slate=slate,
            reliable_market_collection=reliable,
            identity_registry=registry,
            created_at_utc=NOW,
        )


def test_future_source_beyond_tolerance_fails_closed():
    slate = _official_slate(collected_at=NOW + timedelta(seconds=10))
    reliable = _reliable(now=NOW)
    registry = build_mlb_event_player_identity_registry(
        official_slate=slate,
        market_feed=reliable["market_feed"],
    )
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.build_step19e_checkpoint_envelope(
            checkpoint_date=DATE,
            official_slate=slate,
            reliable_market_collection=reliable,
            identity_registry=registry,
            created_at_utc=NOW,
            future_tolerance_seconds=5,
        )


def test_stale_checkpoint_validation_fails_closed():
    envelope = _envelope()
    result = s19e.validate_step19e_checkpoint_envelope(
        envelope,
        now_utc=NOW + timedelta(seconds=301),
        max_checkpoint_age_seconds=300,
    )
    assert result["envelope_valid"] is False
    assert "stale" in result["failures"][0]


def test_future_checkpoint_validation_fails_closed():
    envelope = _envelope(created_at=NOW + timedelta(seconds=10), now=NOW)
    result = s19e.validate_step19e_checkpoint_envelope(
        envelope,
        now_utc=NOW,
        max_checkpoint_age_seconds=300,
        future_tolerance_seconds=5,
    )
    assert result["envelope_valid"] is False
    assert "future" in result["failures"][0]


def test_schema_verification_requires_read_gate():
    factory, _ = _factory([_schema_step()])
    with pytest.raises(s19e.MLBStep19EPersistenceDisabledError):
        s19e.verify_step19e_database_schema(
            env=_safe_env(read=False),
            connection_factory=factory,
        )


def test_schema_verification_fails_if_table_missing():
    factory, _ = _factory([_schema_step(present=False)])
    with pytest.raises(s19e.MLBStep19EPersistenceSchemaError):
        s19e.verify_step19e_database_schema(
            env=_safe_env(),
            connection_factory=factory,
        )


def test_schema_verification_is_read_only():
    factory, box = _factory([_schema_step()])
    result = s19e.verify_step19e_database_schema(
        env=_safe_env(),
        connection_factory=factory,
    )
    assert result["tables_present"] is True
    assert result["database_write_performed"] is False
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks == 1


def test_initial_save_appends_and_advances_head():
    envelope = _envelope()
    factory, box = _factory(_save_initial_script())
    result = s19e.save_step19e_checkpoint(
        checkpoint_envelope=envelope,
        expected_head_version=0,
        env=_safe_env(),
        connection_factory=factory,
        generated_at_utc=NOW,
    )
    assert result["status"] == "saved"
    assert result["checkpoint_version"] == 1
    assert result["reliability_state_for_restart"] == envelope[
        "reliable_market_collection"
    ]["reliability_state"]
    assert box["connection"].commits == 1


def test_save_refuses_disabled_write_gate():
    envelope = _envelope()
    factory, _ = _factory(_save_initial_script())
    with pytest.raises(s19e.MLBStep19EPersistenceDisabledError):
        s19e.save_step19e_checkpoint(
            checkpoint_envelope=envelope,
            expected_head_version=0,
            env=_safe_env(write=False),
            connection_factory=factory,
        )


def test_save_rejects_invalid_candidate_before_database_open():
    envelope = _envelope()
    envelope["envelope_content_sha256"] = "0" * 64
    called = {"value": False}

    def factory():
        called["value"] = True
        raise AssertionError("must not open")

    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.save_step19e_checkpoint(
            checkpoint_envelope=envelope,
            expected_head_version=0,
            env=_safe_env(),
            connection_factory=factory,
        )
    assert called["value"] is False


def test_load_not_found_returns_empty_restart_context():
    factory, _ = _factory(_load_script(None))
    result = s19e.load_step19e_checkpoint(
        checkpoint_date=DATE,
        env=_safe_env(),
        connection_factory=factory,
        now_utc=NOW,
    )
    assert result["status"] == "not_found"
    assert result["found"] is False
    assert result["reliability_state_for_restart"] is None


def test_load_valid_checkpoint_returns_restart_bundle():
    envelope = _envelope(draftkings_cooldown=True)
    factory, _ = _factory(_load_script(_row(envelope)))
    result = s19e.load_step19e_checkpoint(
        checkpoint_date=DATE,
        env=_safe_env(),
        connection_factory=factory,
        now_utc=NOW + timedelta(seconds=10),
    )
    assert result["status"] == "loaded"
    assert result["found"] is True
    assert result["market_feed_for_restart"] == envelope[
        "reliable_market_collection"
    ]["market_feed"]
    assert result["identity_registry_for_restart"] == envelope["identity_registry"]
    assert (
        result["reliability_state_for_restart"]["providers"]["draftkings"][
            "cooldown_reason"
        ]
        == "rate_limited"
    )


def test_recover_preserves_provider_cooldown_across_restart():
    envelope = _envelope(draftkings_cooldown=True)
    factory, _ = _factory(_load_script(_row(envelope)))
    result = s19e.recover_step19e_live_data(
        checkpoint_date=DATE,
        env=_safe_env(),
        connection_factory=factory,
        now_utc=NOW + timedelta(seconds=10),
    )
    assert result["status"] == "recovered"
    state = result["reliability_state_for_restart"]
    assert state["providers"]["draftkings"]["cooldown_until_utc"] == _iso(
        NOW + timedelta(seconds=90)
    )


def test_recover_refuses_stale_checkpoint():
    envelope = _envelope()
    factory, _ = _factory(_load_script(_row(envelope)))
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.recover_step19e_live_data(
            checkpoint_date=DATE,
            env=_safe_env(),
            connection_factory=factory,
            now_utc=NOW + timedelta(seconds=301),
            max_checkpoint_age_seconds=300,
        )


def test_load_detects_row_hash_mismatch():
    envelope = _envelope()
    row = list(_row(envelope))
    row[9] = "0" * 64
    factory, _ = _factory(_load_script(tuple(row)))
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.load_step19e_checkpoint(
            checkpoint_date=DATE,
            env=_safe_env(),
            connection_factory=factory,
            now_utc=NOW,
        )


def test_load_detects_corrupt_persisted_envelope():
    envelope = _envelope()
    corrupt = deepcopy(envelope)
    corrupt["official_slate"]["games"][0]["status"] = "tampered"
    row = list(_row(envelope))
    row[13] = corrupt
    factory, _ = _factory(_load_script(tuple(row)))
    with pytest.raises(s19e.MLBStep19EPersistenceIntegrityError):
        s19e.load_step19e_checkpoint(
            checkpoint_date=DATE,
            env=_safe_env(),
            connection_factory=factory,
            now_utc=NOW,
        )


def test_idempotent_save_does_not_commit():
    envelope = _envelope()
    script = [_schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": _row(envelope)}]
    factory, box = _factory(script)
    result = s19e.save_step19e_checkpoint(
        checkpoint_envelope=envelope,
        expected_head_version=99,
        env=_safe_env(),
        connection_factory=factory,
        generated_at_utc=NOW,
    )
    assert result["status"] == "idempotent"
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks == 1


def test_cas_conflict_fails_closed():
    current = _envelope()
    newer = _envelope(created_at=NOW + timedelta(seconds=1))
    script = [_schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": _row(current)}]
    factory, box = _factory(script)
    with pytest.raises(s19e.MLBStep19EPersistenceConflictError):
        s19e.save_step19e_checkpoint(
            checkpoint_envelope=newer,
            expected_head_version=0,
            env=_safe_env(),
            connection_factory=factory,
            generated_at_utc=NOW + timedelta(seconds=1),
        )
    assert box["connection"].commits == 0
    assert box["connection"].rollbacks >= 1


def test_cas_update_appends_version_two():
    current = _envelope()
    newer = _envelope(created_at=NOW + timedelta(seconds=1))
    script = [
        _schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": _row(current)},
        {
            "contains": f"INSERT INTO {s19e.DATABASE_SCHEMA_NAME}.{s19e.CHECKPOINT_TABLE_NAME}",
            "rowcount": 1,
        },
        {
            "contains": f"UPDATE {s19e.DATABASE_SCHEMA_NAME}.{s19e.CHECKPOINT_HEAD_TABLE_NAME}",
            "rowcount": 1,
        },
    ]
    factory, box = _factory(script)
    result = s19e.save_step19e_checkpoint(
        checkpoint_envelope=newer,
        expected_head_version=1,
        env=_safe_env(),
        connection_factory=factory,
        generated_at_utc=NOW + timedelta(seconds=1),
    )
    assert result["status"] == "saved"
    assert result["checkpoint_version"] == 2
    assert box["connection"].commits == 1


def test_cas_update_zero_row_fails_closed():
    current = _envelope()
    newer = _envelope(created_at=NOW + timedelta(seconds=1))
    script = [
        _schema_step(),
        {"contains": "FOR UPDATE OF h", "fetchone": _row(current)},
        {
            "contains": f"INSERT INTO {s19e.DATABASE_SCHEMA_NAME}.{s19e.CHECKPOINT_TABLE_NAME}",
            "rowcount": 1,
        },
        {
            "contains": f"UPDATE {s19e.DATABASE_SCHEMA_NAME}.{s19e.CHECKPOINT_HEAD_TABLE_NAME}",
            "rowcount": 0,
        },
    ]
    factory, box = _factory(script)
    with pytest.raises(s19e.MLBStep19EPersistenceConflictError):
        s19e.save_step19e_checkpoint(
            checkpoint_envelope=newer,
            expected_head_version=1,
            env=_safe_env(),
            connection_factory=factory,
            generated_at_utc=NOW + timedelta(seconds=1),
        )
    assert box["connection"].commits == 0


def test_database_transport_failure_is_wrapped_and_rolled_back():
    envelope = _envelope()
    script = [_schema_step(), {"contains": "FOR UPDATE OF h", "raise": OSError("db down")}]
    factory, box = _factory(script)
    with pytest.raises(s19e.MLBStep19EPersistenceDatabaseError):
        s19e.save_step19e_checkpoint(
            checkpoint_envelope=envelope,
            expected_head_version=0,
            env=_safe_env(),
            connection_factory=factory,
            generated_at_utc=NOW,
        )
    assert box["connection"].rollbacks >= 1


def test_recovered_objects_are_independent_copies():
    envelope = _envelope()
    factory, _ = _factory(_load_script(_row(envelope)))
    result = s19e.load_step19e_checkpoint(
        checkpoint_date=DATE,
        env=_safe_env(),
        connection_factory=factory,
        now_utc=NOW,
    )
    result["official_slate_for_restart"]["games"][0]["status"] = "changed"
    result["reliability_state_for_restart"]["providers"]["fanduel"][
        "last_success_at_utc"
    ] = None
    assert envelope["official_slate"]["games"][0]["status"] == "scheduled"
    assert envelope["reliable_market_collection"]["reliability_state"]["providers"][
        "fanduel"
    ]["last_success_at_utc"] is not None


def test_result_boundary_never_activates_models_or_wagering():
    envelope = _envelope()
    factory, _ = _factory(_load_script(_row(envelope)))
    result = s19e.load_step19e_checkpoint(
        checkpoint_date=DATE,
        env=_safe_env(),
        connection_factory=factory,
        now_utc=NOW,
    )
    assert result["production_runtime_wiring"] is False
    assert result["model_probability_mutation"] is False
    assert result["projection_mutation"] is False
    assert result["actionable_output"] is False
    assert result["wagering"] is False
