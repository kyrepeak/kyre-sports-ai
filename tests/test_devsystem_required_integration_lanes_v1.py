from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "devsystem-targeted-ci.yml"


def _job(name: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = f"  {name}:\n"
    start = text.index(marker) + len(marker)
    match = re.search(r"(?m)^  [a-z0-9][a-z0-9-]*:\n", text[start:])
    end = start + match.start() if match else len(text)
    return text[start:end]


def test_each_active_sport_lane_runs_when_its_domain_or_core_changes():
    for domain in ("cfb", "mlb", "wnba", "nfl"):
        block = _job(f"{domain}-critical")
        assert f"needs.classify.outputs.{domain} == 'true'" in block
        assert "needs.classify.outputs.core == 'true'" in block
        assert "needs.classify.outputs.model == 'true'" not in block
        assert "github.event_name != 'pull_request'" not in block


def test_browser_qa_is_premerge_for_ui_and_core_changes():
    block = _job("browser-qa")
    assert "needs.classify.outputs.ui == 'true'" in block
    assert "needs.classify.outputs.core == 'true'" in block
    assert "github.event_name != 'pull_request'" not in block


def test_required_lane_skip_can_never_certify_final_gate():
    block = _job("devsystem-final-gate")
    assert 'allowed="success skipped"' in block
    assert "require_success_if()" in block
    assert "DEVSYSTEM_REQUIRED_LANE_BLOCKED" in block
    assert "DEVSYSTEM_REQUIRED_LANE_POLICY_GREEN" in block
    assert 'require_success_if "browser-qa" "$BROWSER_QA_RESULT" "$UI_TOUCHED" "$CORE_TOUCHED"' in block
    assert 'require_success_if "wnba-critical" "$WNBA_CRITICAL_RESULT" "$WNBA_TOUCHED" "$CORE_TOUCHED"' in block
    assert 'require_success_if "nfl-critical" "$NFL_CRITICAL_RESULT" "$NFL_TOUCHED" "$CORE_TOUCHED"' in block
    assert 'require_success_if "cfb-critical" "$CFB_CRITICAL_RESULT" "$CFB_TOUCHED" "$CORE_TOUCHED"' in block
    assert 'require_success_if "mlb-critical" "$MLB_CRITICAL_RESULT" "$MLB_TOUCHED" "$CORE_TOUCHED"' in block
