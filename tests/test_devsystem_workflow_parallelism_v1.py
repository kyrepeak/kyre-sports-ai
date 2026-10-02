from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "devsystem-targeted-ci.yml"


def _job_block(name: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = f"  {name}:\n"
    start = text.index(marker) + len(marker)
    match = re.search(r"(?m)^  [a-z0-9][a-z0-9-]*:\n", text[start:])
    end = start + match.start() if match else len(text)
    return text[start:end]


def test_cheap_safety_gates_run_in_parallel() -> None:
    permanent = _job_block("permanent-contract")
    regression = _job_block("regression-shield")

    assert "needs: [classify, workflow-hygiene]" in permanent
    assert "needs: [classify, workflow-hygiene]" in regression
    assert "permanent-contract" not in regression


def test_expensive_lanes_still_wait_for_both_safety_gates() -> None:
    expected = "needs: [classify, workflow-hygiene, permanent-contract, regression-shield]"
    for job in (
        "browser-qa",
        "cfb-critical",
        "mlb-critical",
        "wnba-critical",
        "nfl-critical",
        "core-smoke",
    ):
        assert expected in _job_block(job), job


def test_step3_fast_pr_and_full_merge_jobs_exist() -> None:
    fast = _job_block("pr-fast")
    full = _job_block("full-merge-certification")
    assert "if: always() && github.event_name == 'pull_request'" in fast
    assert "MONSTER_SPEED_V3_STEP3_FAST_PR_GREEN" in fast
    assert "always() && github.event_name == 'push'" in full
    assert "refs/heads/main" in full
    assert "MONSTER_SPEED_V3_STEP3_FULL_MERGE_GREEN" in full


def test_relevant_sport_critical_lanes_are_not_deferred_on_pr() -> None:
    for domain in ("cfb", "mlb", "wnba", "nfl"):
        block = _job_block(f"{domain}-critical")
        assert "github.event_name != 'pull_request'" not in block
        assert "needs.classify.outputs.model == 'true'" not in block
        assert f"needs.classify.outputs.{domain} == 'true'" in block
        assert "needs.classify.outputs.core == 'true'" in block


def test_browser_qa_runs_for_ui_or_core_on_pr() -> None:
    browser = _job_block("browser-qa")
    assert "github.event_name != 'pull_request'" not in browser
    assert "needs.classify.outputs.ui == 'true'" in browser
    assert "needs.classify.outputs.core == 'true'" in browser


def test_final_gate_still_aggregates_both_safety_gates() -> None:
    final_gate = _job_block("devsystem-final-gate")
    assert "- permanent-contract" in final_gate
    assert "- regression-shield" in final_gate
    assert "- pr-fast" in final_gate
    assert "- full-merge-certification" in final_gate
    assert "MONSTER_SPEED_V3_STEP3_FAST_PR_REQUIRED" in final_gate
    assert "MONSTER_SPEED_V3_STEP3_FULL_MERGE_REQUIRED" in final_gate


def test_final_gate_allows_optional_skip_but_blocks_required_skip() -> None:
    final_gate = _job_block("devsystem-final-gate")

    assert "actions/checkout" not in final_gate
    assert "actions/setup-python" not in final_gate
    assert "python devsystem/final_gate_v1.py" not in final_gate
    assert 'allowed="success skipped"' in final_gate
    assert 'if ! grep -qw -- "$result" <<< "$allowed"; then' in final_gate
    assert "require_success_if()" in final_gate
    assert "DEVSYSTEM_REQUIRED_LANE_BLOCKED" in final_gate
    assert "DEVSYSTEM_REQUIRED_LANE_POLICY_GREEN" in final_gate
    for marker in (
        "CFB_TOUCHED",
        "MLB_TOUCHED",
        "WNBA_TOUCHED",
        "NFL_TOUCHED",
        "CORE_TOUCHED",
        "UI_TOUCHED",
    ):
        assert marker in final_gate
    for lane in (
        "browser-qa",
        "cfb-critical",
        "mlb-critical",
        "wnba-critical",
        "nfl-critical",
        "core-smoke",
    ):
        assert f'require_success_if "{lane}"' in final_gate
    assert "DEVSYSTEM_FINAL_GATE_GREEN" in final_gate
