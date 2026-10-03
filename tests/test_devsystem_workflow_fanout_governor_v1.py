import json

from devsystem.workflow_fanout_governor_v1 import ROOT, VERSION, audit_repository


def test_repository_fanout_governor_is_green():
    result = audit_repository(ROOT)
    assert result["status"] == "GREEN"
    assert result["version"] == VERSION
    assert result["proof_lanes"]["step7"] == "PATH_SCOPED_AND_STALE_CANCELLED"
    assert result["proof_lanes"]["failure_packet"] == "SOURCE_FAILURE_ONLY"
    assert result["proof_lanes"]["targeted_ci"] == "CENTRAL_BROAD_DISPATCHER_PRESERVED"
    assert result["proof_lanes"]["wnba_nav_fast_cert"] == "WNBA_PATH_SCOPED"
    assert result["proof_lanes"]["wnba_nav_responsive_cert"] == "WNBA_PATH_SCOPED"
    assert result["proof_lanes"]["workflow_quarantine"] == "WORKFLOW_CHANGE_SAFETY_PRESERVED"
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["may_modify_product_runtime"] is False


def test_step7_is_not_a_universal_pr_push_fanout_source():
    text = (
        ROOT
        / ".github"
        / "workflows"
        / "api2-proof-architecture-v1-step7-end-to-end-convergence.yml"
    ).read_text(encoding="utf-8")
    assert "pull_request:\n    branches: [main]\n    paths:" in text
    assert "push:\n    branches: [main]\n    paths:" in text
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


def test_policy_keeps_product_and_model_domains_out_of_scope():
    policy = json.loads(
        (ROOT / "devsystem" / "workflow_fanout_policy_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert policy["safety"]["product_runtime_mutation_allowed"] is False
    assert policy["safety"]["model_projection_mutation_allowed"] is False
    assert policy["safety"]["blind_reruns_allowed"] is False
    assert policy["safety"]["step_2a_required"] is True


def test_wnba_navigation_certs_are_path_scoped_to_wnba_dependencies():
    for workflow in (
        "wnba-nav-step6-fast-cert.yml",
        "wnba-nav-step6-responsive-cert.yml",
    ):
        text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
        assert "pull_request:\n    branches: [main]\n    paths:" in text
        assert "wnba_pra_responsive_v2_step6.py" in text
        assert "wnba_pra_navigation_v2_step1.py" in text
        assert "app.py" in text


def test_workflow_change_quarantine_safety_lane_is_preserved():
    text = (
        ROOT / ".github" / "workflows" / "monster-speed-v3-step1-quarantine-v1.yml"
    ).read_text(encoding="utf-8")
    assert '".github/workflows/**"' in text
    assert "cancel-in-progress: true" in text
