"""Monster Speed V3 Step 3 — fast PR / full merged-main lane guard."""
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
    if "github.event_name != 'pull_request'" not in browser:
        failures.append("browser QA still runs on routine PRs")

    for name in ("cfb-critical", "mlb-critical", "wnba-critical", "nfl-critical"):
        block = _job_block(text, name)
        if "github.event_name != 'pull_request'" not in block:
            failures.append(f"{name} not deferred from routine PR")
        if "needs.classify.outputs.model == 'true'" not in block:
            failures.append(f"{name} lost high-risk model PR escape hatch")

    final = _job_block(text, "devsystem-final-gate")
    for required in ("- pr-fast", "- full-merge-certification", "PR_FAST_RESULT", "FULL_MERGE_RESULT", "MONSTER_SPEED_V3_STEP3_FAST_PR_REQUIRED", "MONSTER_SPEED_V3_STEP3_FULL_MERGE_REQUIRED"):
        if required not in final:
            failures.append(f"final gate missing {required}")

    if failures:
        raise LaneSplitFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "pr_mode": "FAST",
        "merged_main_mode": "FULL",
        "routine_pr_browser_qa": False,
        "high_risk_model_pr_full_sport_proof": True,
        "full_merge_required_on_main": True,
    }

def main() -> int:
    result = check_repository()
    print("MONSTER_SPEED_V3_STEP3_FAST_PR_FULL_MERGE_GREEN")
    print(result)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
