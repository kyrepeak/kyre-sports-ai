from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "devsystem" / "guardian_source_of_truth_configuration_parity_v1.json"
MODULE_PATH = ROOT / "runless_v2" / "guardian_source_of_truth_configuration_parity_v1.py"

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

EXPECTED_STALE_PREVIEW_ENV_IDS = {
    "VLEtduzIHvXMjoLX", "r3bc0IxekmicERwc", "L7t5CRrjzfvCSGGL",
    "OHPkWOX397eJvAFh", "zFWGW9gf8AWVUfPP", "LdYdb6pTK3YqMEmZ",
    "TP2f7joGf5pidpfN", "BC16fRa5WnpIuBVG", "tnkMcmRm54v00wac",
}


def _manifest() -> dict:
    assert MANIFEST.exists(), "source-of-truth parity manifest must exist"
    return json.loads(MANIFEST.read_text())


def _guardian_module():
    spec = importlib.util.spec_from_file_location("guardian_source_parity_v1", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_supabase_migration_inventory_is_source_indexed() -> None:
    data = _manifest()
    migrations = data["supabase"]["migration_ledger"]
    assert len(migrations) == 38
    assert data["supabase"]["migration_count"] == 38
    assert len({m["version"] for m in migrations}) == 38
    assert all(len(m["content_md5"]) == 32 for m in migrations)
    assert data["supabase"]["migration_payload_archive_state"] in {"COMPLETE", "OPEN"}
    if data["supabase"]["migration_payload_archive_state"] != "COMPLETE":
        assert data["freeze"]["state"] == "OPEN"


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


def test_known_vercel_cleanup_debt_is_never_hidden() -> None:
    data = _manifest()
    vercel = data["vercel"]
    assert vercel["retired_preview_prs"] == [1527, 1528, 1529]
    stale = set(vercel["stale_preview_env_ids"])
    assert stale in (set(), EXPECTED_STALE_PREVIEW_ENV_IDS)
    assert vercel["stale_preview_env_count"] == len(stale)
    assert set(vercel["production_projects"]) == {
        "kyre-sports-api",
        "kyre-runless-proof",
        "kyre-sports-finalizer",
    }
    if stale:
        assert data["freeze"]["state"] == "OPEN"


def test_post_merge_convergence_contract_is_strict() -> None:
    evaluate_convergence = _guardian_module().evaluate_convergence
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


def test_freeze_requires_zero_stale_preview_configuration() -> None:
    freeze_eligible = _guardian_module().freeze_eligible
    assert freeze_eligible({"green": True, "failures": []}, stale_preview_env_count=0, migration_payload_archive_complete=True) is True
    assert freeze_eligible({"green": True, "failures": []}, stale_preview_env_count=9, migration_payload_archive_complete=True) is False
    assert freeze_eligible({"green": True, "failures": []}, stale_preview_env_count=0, migration_payload_archive_complete=False) is False
