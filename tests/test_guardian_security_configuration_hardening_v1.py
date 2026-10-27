import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MAIN_SHA = "31f94eae6e007a61d01397e6d868df3a6a3bd1e2"


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_hardening_plan_is_guardian_only_and_exact_source_main():
    plan = _json("devsystem/runless_proof_plans/guardian-security-configuration-hardening-v1.json")
    assert plan["task_id"] == "guardian-security-configuration-hardening-v1"
    assert plan["workstream"] == "guardian-security-configuration-hardening-v1"
    assert plan["source_main_sha"] == SOURCE_MAIN_SHA
    assert plan["required_check"] == "runless-final-gate"
    assert plan["required_check_app_id"] == 5204253
    assert plan["freeze_token"] == "GUARDIAN_SECURITY_CONFIGURATION_HARDENING_V1_FROZEN"


def test_neutral_finalizer_baseline_has_no_api2_or_monster_identity():
    path = "devsystem/runless_proof_plans/guardian-finalizer-baseline-v1.json"
    plan = _json(path)
    text = _text(path).lower()
    assert plan["task_id"] == "guardian-finalizer-baseline-v1"
    assert plan["workstream"] == "guardian-finalizer-baseline-v1"
    assert plan["source_main_sha"] == SOURCE_MAIN_SHA
    assert "vercel_finalizer/test_health_truthfulness.py" in str(plan["commands"])
    assert "vercel_finalizer/test_publish_gate_build.py" in str(plan["commands"])
    assert "api2-" not in text
    assert "monster" not in text


def test_previous_guardian_cleanup_freeze_remains_untouched():
    previous = _json("devsystem/runless_proof_plans/guardian-infrastructure-automation-cleanup-v1.json")
    assert previous["freeze_token"] == "GUARDIAN_INFRASTRUCTURE_AUTOMATION_CLEANUP_V1_FROZEN"


def test_spec_preserves_hard_isolation_and_truthful_secret_handling():
    spec = _text("docs/superpowers/specs/2026-10-27-guardian-security-configuration-hardening-v1.md")
    assert "Do not alter sports models" in spec
    assert "API 2 or MONSTER" in spec
    assert "Do not create a Supabase service-role credential" not in spec
    assert "required secrets are not exposed or invented" in spec
