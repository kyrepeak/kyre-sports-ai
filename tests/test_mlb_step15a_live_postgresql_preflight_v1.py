from __future__ import annotations

import pytest

from sports_api import mlb_step15a_live_postgresql_preflight_v1 as step15a


def _ready_snapshot() -> dict:
    tables = {}
    for name in step15a.REQUIRED_TABLES:
        tables[name] = {
            "columns": list(step15a.EXPECTED_COLUMNS[name]),
            "constraints": sorted(step15a.REQUIRED_CONSTRAINTS[name]),
            "indexes": sorted(step15a.REQUIRED_INDEXES[name]),
            "privileges_ok": True,
            "row_count": 0,
        }
    return {
        "database_name": "postgres",
        "database_user": "postgres",
        "server_version_num": 170006,
        "in_recovery": False,
        "schema_exists": True,
        "can_connect": True,
        "can_use_schema": True,
        "tables": tables,
    }


def test_manifest_keeps_step15a_read_only_and_production_off():
    manifest = step15a.live_postgresql_preflight_manifest()
    assert manifest["runtime_mode"] == "SHADOW_ONLY"
    assert manifest["live_database_connection_allowed"] is True
    assert manifest["live_database_metadata_reads_allowed"] is True
    assert manifest["live_database_writes_allowed"] is False
    assert manifest["schema_auto_apply_allowed"] is False
    assert manifest["checkpoint_smoke_write_allowed"] is False
    assert manifest["lease_smoke_write_allowed"] is False
    assert manifest["runtime_cycle_execution_allowed"] is False
    assert manifest["production_runtime_activation_allowed"] is False
    assert manifest["production_scheduler_activation_allowed"] is False
    assert manifest["actionable_output_allowed"] is False
    assert manifest["provider_network_calls_allowed"] is False
    assert manifest["sportsbook_network_calls_allowed"] is False
    assert manifest["future_step15b_live_persistence_smoke_required"] is True
    assert manifest["final_certification_marker"] == (
        "MLB_STEP15A_LIVE_POSTGRESQL_PREFLIGHT_GREEN"
    )


def test_preflight_gate_requires_explicit_enable_and_database_url():
    with pytest.raises(step15a.MLBStep15ALivePostgreSQLPreflightDisabledError):
        step15a._assert_preflight_gate({})

    with pytest.raises(step15a.MLBStep15ALivePostgreSQLPreflightDisabledError):
        step15a._assert_preflight_gate({step15a.PREFLIGHT_ENABLED_ENV: "true"})

    step15a._assert_preflight_gate(
        {
            step15a.PREFLIGHT_ENABLED_ENV: "true",
            step15a.DATABASE_URL_ENV: "postgresql://example.invalid/db",
        }
    )


def test_preflight_gate_refuses_production_switches():
    env = {
        step15a.PREFLIGHT_ENABLED_ENV: "true",
        step15a.DATABASE_URL_ENV: "postgresql://example.invalid/db",
        "MLB_PRODUCTION_RUNTIME_ENABLED": "true",
    }
    with pytest.raises(step15a.MLBStep15ALivePostgreSQLPreflightDisabledError):
        step15a._assert_preflight_gate(env)


def test_ready_snapshot_is_step15b_ready_without_writes():
    result = step15a.evaluate_live_postgresql_preflight(_ready_snapshot())
    assert result["ready_for_step15b"] is True
    assert result["failures"] == []
    assert result["live_database_connection_executed"] is True
    assert result["live_database_write_executed"] is False
    assert result["checkpoint_write_executed"] is False
    assert result["lease_operation_executed"] is False
    assert result["runtime_cycle_executed"] is False
    assert result["provider_calls"] == 0
    assert result["sportsbook_calls"] == 0
    assert result["production_activation"] == 0


def test_missing_table_fails_closed():
    snapshot = _ready_snapshot()
    del snapshot["tables"][step15a.LEASE_TABLE_NAME]
    result = step15a.evaluate_live_postgresql_preflight(snapshot)
    assert result["ready_for_step15b"] is False
    assert any(
        failure.startswith(step15a.LEASE_TABLE_NAME.upper())
        for failure in result["failures"]
    )


def test_column_drift_fails_closed():
    snapshot = _ready_snapshot()
    table = snapshot["tables"][step15a.CHECKPOINT_TABLE_NAME]
    table["columns"] = list(table["columns"][:-1])
    result = step15a.evaluate_live_postgresql_preflight(snapshot)
    assert result["ready_for_step15b"] is False
    assert (
        f"{step15a.CHECKPOINT_TABLE_NAME.upper()}_COLUMN_CONTRACT_MISMATCH"
        in result["failures"]
    )


def test_nonempty_table_blocks_pre_smoke_certification():
    snapshot = _ready_snapshot()
    snapshot["tables"][step15a.CHECKPOINT_TABLE_NAME]["row_count"] = 1
    result = step15a.evaluate_live_postgresql_preflight(snapshot)
    assert result["ready_for_step15b"] is False
    assert (
        f"{step15a.CHECKPOINT_TABLE_NAME.upper()}_NOT_EMPTY_BEFORE_SMOKE"
        in result["failures"]
    )


class _FakeCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.executed = []
        self._current = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split()).upper()
        self.executed.append((normalized, params))
        self._current = self.responses.pop(0)

    def fetchone(self):
        if isinstance(self._current, tuple):
            return self._current
        raise AssertionError("expected tuple response")

    def fetchall(self):
        if isinstance(self._current, list):
            return self._current
        raise AssertionError("expected list response")


class _FakeConnection:
    def __init__(self, responses):
        self.cursor_obj = _FakeCursor(responses)
        self.rollback_calls = 0
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.closed = True


def _fake_live_responses():
    snapshot = _ready_snapshot()
    metadata = (
        snapshot["database_name"],
        snapshot["database_user"],
        snapshot["server_version_num"],
        snapshot["in_recovery"],
        snapshot["schema_exists"],
        snapshot["can_connect"],
        snapshot["can_use_schema"],
    )

    column_rows = []
    constraint_rows = []
    index_rows = []
    for table_name in step15a.REQUIRED_TABLES:
        for column in step15a.EXPECTED_COLUMNS[table_name]:
            column_rows.append((table_name, *column))
        for name in sorted(step15a.REQUIRED_CONSTRAINTS[table_name]):
            constraint_rows.append((table_name, name))
        for name in sorted(step15a.REQUIRED_INDEXES[table_name]):
            index_rows.append((table_name, name))

    return [
        None,
        metadata,
        column_rows,
        constraint_rows,
        index_rows,
        (True, True, True),
        (0, 0, 0),
    ]


def test_live_collector_is_read_only_and_closes_connection():
    connection = _FakeConnection(_fake_live_responses())

    result = step15a.run_live_postgresql_preflight(
        env={
            step15a.PREFLIGHT_ENABLED_ENV: "true",
            step15a.DATABASE_URL_ENV: "postgresql://unit-test.invalid/db",
        },
        connection_factory=lambda _: connection,
    )

    assert result["ready_for_step15b"] is True
    assert connection.rollback_calls == 1
    assert connection.closed is True

    statements = [sql for sql, _ in connection.cursor_obj.executed]
    assert statements[0] == "SET TRANSACTION READ ONLY"
    forbidden = (
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "CREATE ",
        "ALTER ",
        "DROP ",
        "TRUNCATE ",
    )
    assert all(not any(token in sql for token in forbidden) for sql in statements)
