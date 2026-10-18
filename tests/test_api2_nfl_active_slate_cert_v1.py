from __future__ import annotations

from pathlib import Path
import importlib

EXPECTED = (
    "API2_NFL_ACTIVE_SLATE_RESOLVER_OK",
    "API2_NFL_ACTIVE_SLATE_ALL_FINAL_ROLLOVER_OK",
    "API2_NFL_ACTIVE_SLATE_CROSS_MARKET_DATE_OK",
    "API2_NFL_ACTIVE_SLATE_MANUAL_OVERRIDE_OK",
    "API2_NFL_ACTIVE_SLATE_LEGACY_AUTO_GUARDS_OK",
    "API2_NFL_ACTIVE_SLATE_NON_NFL_DELEGATION_OK",
    "API2_NFL_ACTIVE_SLATE_MODEL_FIREWALL_OK",
    "API2_NFL_ACTIVE_SLATE_UNIVERSAL_NAV_OK",
    "API2_NFL_ACTIVE_SLATE_V1_PASS",
)


def test_cert_emits_every_required_token(capsys):
    cert = importlib.import_module("devsystem.api2_nfl_active_slate_cert_v1")
    assert cert.main() == 0
    out = capsys.readouterr().out
    for token in EXPECTED:
        assert token in out


def test_runless_plan_is_single_authority_and_no_actions_fallback():
    import json
    plan = json.loads(Path("devsystem/runless_proof_plans/api2-universal-nfl-active-slate-v1.json").read_text())
    assert plan["mode"] == "runless"
    assert plan["workstream"] == "api2-universal-nfl-active-slate-v1"
    assert plan["task_id"] == "api2-universal-nfl-active-slate-v1"
    assert plan["github_actions_fallback"] == 0
    assert plan["required_check"] == "runless-final-gate"
    assert plan["required_check_app_id"] == 5204253
    assert plan["freeze_token"] == "API2_NFL_ACTIVE_SLATE_V1_FROZEN"
