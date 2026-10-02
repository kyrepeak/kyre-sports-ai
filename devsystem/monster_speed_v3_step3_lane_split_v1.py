"""Monster Speed V3 Step 3 — targeted-required PR / full merged-main lane guard.

API2 Proof Architecture V1 Step 2 forward-ports the original speed contract:
PRs stay targeted, but any integration lane relevant to the classified change
must run before merge. Irrelevant lanes may still skip.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/devsystem-targeted-ci.yml"


class LaneSplitFailure(RuntimeError):
    pass


def _job_block(text: str, name: str) -> str:
    marker = f"  {name}:\n"
    if marker not in text:
        raise LaneSplitFailure(f"missing job: {name}")
    tail = text.split(marker, 1)[1]
    lines = tail.splitlines()
    out: list[str] = []
    for line in lines:
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            break
        out.append(line)
    return "\n".join(out)


def check_repository() -> dict[str, object]:
    text = WORKFLOW.read_text(encoding="utf-8")
    failures: list[str] = []

    push_block = text.split("  push:", 1)[1].split("  workflow_dispatch:", 1)[0]
    if "- main" not in push_block:
        failures.append("targeted CI does not run on merged main")

    fast = _job_block(text, "pr-fast")
    if "always() && github.event_name == 'pull_request'" not in fast:
        failures.append("fast PR lane is not PR-only")
    if "MONSTER_SPEED_V3_STEP3_FAST_PR_GREEN" not in fast:
        failures.append("fast PR token missing")

    full = _job_block(text, "full-merge-certification")
    if "always() && github.event_name == 'push'" not in full or "refs/heads/main" not in full:
        failures.append("full merge lane is not main-push-only")
    if "MONSTER_SPEED_V3_STEP3_FULL_MERGE_GREEN" not in full:
        failures.append("full merge token missing")

    browser = _job_block(text, "browser-qa")
    if "github.event_name != 'pull_request'" in browser:
        failures.append("browser QA is still PR-deferred")
    for marker in (
        "needs.classify.outputs.ui == 'true'",
        "needs.classify.outputs.core == 'true'",
    ):
        if marker not in browser:
            failures.append(f"browser QA missing targeted requirement: {marker}")

    for domain in ("cfb", "mlb", "wnba", "nfl"):
        name = f"{domain}-critical"
        block = _job_block(text, name)
        if "github.event_name != 'pull_request'" in block:
            failures.append(f"{name} is still deferred from PR")
        if "needs.classify.outputs.model == 'true'" in block:
            failures.append(f"{name} still depends on model-only PR escape hatch")
        for marker in (
            f"needs.classify.outputs.{domain} == 'true'",
            "needs.classify.outputs.core == 'true'",
        ):
            if marker not in block:
                failures.append(f"{name} missing targeted requirement: {marker}")

    final = _job_block(text, "devsystem-final-gate")
    for required in (
        "- pr-fast",
        "- full-merge-certification",
        "PR_FAST_RESULT",
        "FULL_MERGE_RESULT",
        "MONSTER_SPEED_V3_STEP3_FAST_PR_REQUIRED",
        "MONSTER_SPEED_V3_STEP3_FULL_MERGE_REQUIRED",
        "require_success_if()",
        "DEVSYSTEM_REQUIRED_LANE_BLOCKED",
        "DEVSYSTEM_REQUIRED_LANE_POLICY_GREEN",
    ):
        if required not in final:
            failures.append(f"final gate missing {required}")

    for lane in (
        "browser-qa",
        "cfb-critical",
        "mlb-critical",
        "wnba-critical",
        "nfl-critical",
        "core-smoke",
    ):
        if f'require_success_if "{lane}"' not in final:
            failures.append(f"final gate does not require success for in-scope {lane}")

    if failures:
        raise LaneSplitFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "pr_mode": "TARGETED_REQUIRED",
        "merged_main_mode": "FULL",
        "relevant_pr_browser_qa": True,
        "relevant_pr_sport_proof": True,
        "optional_pr_lanes_skippable": True,
        "required_pr_lanes_must_succeed": True,
        "full_merge_required_on_main": True,
    }


def main() -> int:
    result = check_repository()
    print("MONSTER_SPEED_V3_STEP3_TARGETED_REQUIRED_PR_FULL_MERGE_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
