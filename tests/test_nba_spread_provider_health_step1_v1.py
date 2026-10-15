from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTION = ROOT / "devsystem" / "execution_plans" / "nba-spread-provider-health-step1-v1.json"
RUNLESS = ROOT / "devsystem" / "runless_proof_plans" / "nba-spread-provider-health-step1-v1.json"
LEDGER = ROOT / "devsystem" / "task_ledgers" / "nba-spread-provider-health-step1-v1.json"
REGISTRY = ROOT / "devsystem" / "contracts" / "universal-sports-provider-registry-v1.json"
SCHEDULE = ROOT / "nba_spread_schedule_v1.py"
PAGE = ROOT / "nba_spread_page_v1.py"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_step1_diagnosis_is_exact_and_fail_closed_threshold_is_preserved():
    execution = _json(EXECUTION)
    ledger = _json(LEDGER)

    assert execution["workstream"] == "nba-spread-provider-resilience-v1"
    assert execution["step"] == "1/3"
    diagnostic = execution["diagnostic_scope"]
    assert diagnostic["failed_capability"] == "schedule"
    assert diagnostic["failed_provider_id"] == "nba_official"
    assert diagnostic["failure_class"] == "PROVIDER_ACCESS_BLOCKED"
    assert diagnostic["observed_http_status"] == 403
    assert diagnostic["healthy_provider_id"] == "espn"
    assert diagnostic["independent_fallback_provider_id"] == "cbs_sports"
    assert diagnostic["minimum_independent_sources"] == 2
    assert diagnostic["verification_threshold_lowered"] is False

    assert ledger["diagnostic"]["nba_official_endpoint_1_status"] == 403
    assert ledger["diagnostic"]["nba_official_endpoint_2_status"] == 403
    assert ledger["diagnostic"]["independent_fetch_methods_agree"] is True
    assert ledger["diagnostic"]["espn_single_day_reachability"] == "REACHABLE"
    assert ledger["approved_step2_route"]["single_provider_publish_allowed"] is False
    assert ledger["approved_step2_route"]["fail_closed_on_conflict"] is True


def test_step1_fallback_is_already_approved_for_nba_schedule_capability():
    registry = _json(REGISTRY)
    providers = {item["provider_id"]: item for item in registry["providers"]}

    for provider_id in ("nba_official", "espn", "cbs_sports"):
        assert provider_id in providers
        provider = providers[provider_id]
        assert "nba" in provider["sports"]
        assert "schedule" in provider["capabilities"]
        assert provider["page_wide_authority"] is False


def test_step1_is_control_plane_only_and_preserves_frozen_product_files():
    execution = _json(EXECUTION)
    runless = _json(RUNLESS)
    ledger = _json(LEDGER)

    assert "nba_spread_schedule_v1.py" not in execution["write_paths"]
    assert "nba_spread_page_v1.py" not in execution["write_paths"]
    assert "nba_spread_schedule_v1.py" in execution["protected_dependencies"]
    assert "nba_spread_page_v1.py" in execution["protected_dependencies"]
    assert ledger["scope"]["product_runtime_mutation"] is False
    assert ledger["scope"]["sports_model_mutation"] is False
    assert ledger["scope"]["legacy_registry_mutation"] is False
    assert runless["github_actions_fallback"] == 0
    assert runless["required_check"] == "runless-final-gate"
    assert runless["freeze_token"] == "NBA_SPREAD_PROVIDER_HEALTH_STEP1_V1_FROZEN"


def test_step1_records_the_exact_current_schedule_failure_surface():
    schedule_source = SCHEDULE.read_text(encoding="utf-8")
    page_source = PAGE.read_text(encoding="utf-8")

    assert "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json" in schedule_source
    assert "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json" in schedule_source
    assert "NBA_OFFICIAL_UNAVAILABLE" in schedule_source
    assert "load_verified_nba_schedule" in page_source
    assert "NBA Official + ESPN NBA" in page_source
