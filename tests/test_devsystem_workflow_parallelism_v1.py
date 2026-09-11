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
    expected = (
        "needs: [classify, workflow-hygiene, permanent-contract, regression-shield]"
    )
    for job in (
        "browser-qa",
        "cfb-critical",
        "mlb-critical",
        "wnba-critical",
        "core-smoke",
    ):
        assert expected in _job_block(job), job


def test_final_gate_still_aggregates_both_safety_gates() -> None:
    final_gate = _job_block("devsystem-final-gate")
    assert "- permanent-contract" in final_gate
    assert "- regression-shield" in final_gate
