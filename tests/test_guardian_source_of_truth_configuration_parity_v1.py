from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "devsystem" / "guardian_source_of_truth_configuration_parity_v1.json"
LEDGER = ROOT / "supabase" / "source_parity_ledger"
FUNCTIONS = ROOT / "supabase" / "functions"

EXPECTED_FUNCTIONS = {
    "noop-do-not-deploy",
    "api2-registry-payload-builder-temp",
    "api2-github-credential-presence-temp",
    "api2-runless-step4-repair-relay-temp",
    "api2-registry-step4-rebind-payload-temp",
    "api2-pickvault-step4-public-ws-proof-temp",
    "api2-registry-step7-thaw-r1",
    "api2-registry-payload-gzip-temp",
    "guardian-finalizer-authority-bridge-v1",
}

EXPECTED_RLS_DENY_BY_DEFAULT = {
    "public.wnba_durable_locks",
    "public.wnba_durable_objects",
    "public.wnba_step7g_board_publications",
    "public.wnba_step7g_board_scheduler_runs",
    "public.wnba_step7g_prop_feed_attempts",
    "public.wnba_step7g_prop_feed_snapshots",
    "public.wnba_step7g_scheduler_lock_history",
    "public.wnba_step7g_scheduler_locks",
}


def _manifest() -> dict:
    assert MANIFEST.exists(), "source-of-truth parity manifest must exist"
    return json.loads(MANIFEST.read_text())


def test_live_supabase_migration_ledger_is_fully_source_controlled() -> None:
    data = _manifest()
    migrations = data["supabase"]["migration_ledger"]
    assert len(migrations) == 38
    assert data["supabase"]["migration_count"] == 38
    ledger_files = sorted(LEDGER.glob("*.sql"))
    assert len(ledger_files) == 38
    expected_files = {entry["file"] for entry in migrations}
    assert {p.relative_to(ROOT).as_posix() for p in ledger_files} == expected_files


def test_every_live_edge_function_has_source_or_existing_authoritative_source() -> None:
    data = _manifest()
    functions = data["supabase"]["edge_functions"]
    assert set(functions) == EXPECTED_FUNCTIONS
    for slug, entry in functions.items():
        path = ROOT / entry["source_file"]
        assert path.exists(), f"missing source for live Edge Function {slug}"
        assert entry["status"] == "ACTIVE"
        assert isinstance(entry["verify_jwt"], bool)


def test_intentional_rls_no_policy_tables_are_explicitly_allowlisted() -> None:
    data = _manifest()
    assert set(data["supabase"]["intentional_rls_no_policy_tables"]) == EXPECTED_RLS_DENY_BY_DEFAULT
    assert data["supabase"]["security_actionable_findings"] == 0


def test_retired_vercel_preview_config_is_declared_clean() -> None:
    data = _manifest()
    vercel = data["vercel"]
    assert vercel["retired_preview_prs"] == [1527, 1528, 1529]
    assert vercel["stale_preview_env_ids"] == []
    assert set(vercel["production_projects"]) == {
        "kyre-sports-api",
        "kyre-runless-proof",
        "kyre-sports-finalizer",
    }


def test_post_merge_convergence_contract_is_strict() -> None:
    from runless_v2.guardian_source_of_truth_configuration_parity_v1 import evaluate_convergence

    main = "a" * 40
    snapshot = {
        "main_sha": main,
        "supabase": {"status": "ACTIVE_HEALTHY", "security_errors": 0, "security_warnings": 0},
        "vercel": {
            "stale_preview_env_count": 0,
            "projects": {
                name: {"ready_state": "READY", "git_sha": main, "runtime_error_count": 0, "runtime_fatal_count": 0}
                for name in ("kyre-sports-api", "kyre-runless-proof", "kyre-sports-finalizer")
            },
        },
    }
    assert evaluate_convergence(snapshot)["green"] is True

    snapshot["vercel"]["projects"]["kyre-sports-api"]["git_sha"] = "b" * 40
    report = evaluate_convergence(snapshot)
    assert report["green"] is False
    assert any("kyre-sports-api" in item for item in report["failures"])
