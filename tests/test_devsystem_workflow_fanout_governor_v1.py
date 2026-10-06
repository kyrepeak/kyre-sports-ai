import json

from devsystem.runless_actions_fallback_policy_v1 import AUTO_RE, manifest_paths
from devsystem.workflow_fanout_governor_v1 import ROOT, VERSION, audit_repository


def _manual_only(text: str) -> bool:
    return "workflow_dispatch:" in text and AUTO_RE.search(text) is None


def test_repository_fanout_governor_is_green():
    result = audit_repository(ROOT)
    assert result["status"] == "GREEN"
    assert result["version"] == VERSION
    assert result["normal_proof_plane"] == "runless-proof-plane"
    assert result["legacy_actions_mode"] == "manual_only"
    assert result["legacy_actions_manifest_count"] == len(manifest_paths(ROOT))
    assert result["proof_lanes"]["step7"] == "RUNLESS_MANUAL_FALLBACK"
    assert result["proof_lanes"]["failure_packet"] == "SOURCE_FAILURE_ONLY"
    assert result["proof_lanes"]["targeted_ci"] == "RUNLESS_MANUAL_FALLBACK"
    assert result["proof_lanes"]["permanent_contract"] == "EXACT_PR_HEAD_IDENTITY"
    assert result["proof_lanes"]["wnba_nav_fast_cert"] == "RUNLESS_MANUAL_FALLBACK"
    assert result["proof_lanes"]["wnba_nav_responsive_cert"] == "RUNLESS_MANUAL_FALLBACK"
    assert result["proof_lanes"]["workflow_quarantine"] == "RUNLESS_MANUAL_FALLBACK"
    assert result["proof_lanes"]["legacy_actions"] == "MANIFEST_MANUAL_ONLY"
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False


def test_step7_is_manual_only_fallback():
    text = (
        ROOT
        / ".github"
        / "workflows"
        / "api2-proof-architecture-v1-step7-end-to-end-convergence.yml"
    ).read_text(encoding="utf-8")
    assert _manual_only(text)
    assert "github.event.pull_request.number" in text
    assert "cancel-in-progress: true" in text


def test_failure_packet_does_not_allocate_runner_for_successful_source_run():
    text = (
        ROOT / ".github" / "workflows" / "devsystem-failure-packet-v1.yml"
    ).read_text(encoding="utf-8")
    assert (
        "if: github.event_name != 'workflow_run' || "
        "github.event.workflow_run.conclusion == 'failure'"
    ) in text


def test_policy_keeps_runless_normal_and_product_domains_out_of_scope():
    policy = json.loads(
        (ROOT / "devsystem" / "workflow_fanout_policy_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert policy["normal_proof_plane"] == "runless-proof-plane"
    assert policy["legacy_actions_mode"] == "manual_only"
    assert policy["legacy_actions_manifest"] == "devsystem/runless_legacy_proof_workflows_v1.txt"
    assert policy["safety"]["product_runtime_mutation_allowed"] is False
    assert policy["safety"]["model_projection_mutation_allowed"] is False
    assert policy["safety"]["blind_reruns_allowed"] is False
    assert policy["safety"]["step_2a_required"] is True


def test_wnba_navigation_certs_are_manual_only_fallback():
    for workflow in (
        "wnba-nav-step6-fast-cert.yml",
        "wnba-nav-step6-responsive-cert.yml",
    ):
        text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
        assert _manual_only(text)


def test_workflow_change_quarantine_is_manual_only_fallback():
    text = (
        ROOT / ".github" / "workflows" / "monster-speed-v3-step1-quarantine-v1.yml"
    ).read_text(encoding="utf-8")
    assert _manual_only(text)
    assert "cancel-in-progress: true" in text


def test_devsystem_permanent_contract_preserves_exact_head_identity_for_manual_fallback():
    text = (
        ROOT / ".github" / "workflows" / "devsystem-targeted-ci.yml"
    ).read_text(encoding="utf-8")
    assert _manual_only(text)
    assert "permanent-contract:" in text
    assert (
        "ref: ${{ github.event_name == 'pull_request' && "
        "github.event.pull_request.head.sha || github.sha }}"
    ) in text


def test_current_governed_proof_lanes_are_in_runless_fallback_manifest():
    manifest = set(manifest_paths(ROOT))
    assert ".github/workflows/api2-proof-architecture-v1-step7-end-to-end-convergence.yml" in manifest
    assert ".github/workflows/wnba-nav-step6-fast-cert.yml" in manifest
    assert ".github/workflows/wnba-nav-step6-responsive-cert.yml" in manifest
