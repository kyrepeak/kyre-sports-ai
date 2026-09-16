from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "devsystem" / "cfb_game_total_browser_qa_v2.py"
WORKFLOW = ROOT / ".github" / "workflows" / "cfb-game-total-v152-browser.yml"


def test_v152_browser_qa_exists_and_targets_real_game_total_page() -> None:
    source = QA.read_text(encoding="utf-8")
    assert 'TARGET_DAY = "2026-09-17"' in source
    assert 'TARGET_AWAY = "Syracuse"' in source
    assert 'TARGET_HOME = "Pittsburgh"' in source
    assert 'CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE' in source
    assert "College Football" in source
    assert "Game Total" in source


def test_v152_browser_qa_requires_visual_identity_records_and_compact_sections() -> None:
    source = QA.read_text(encoding="utf-8")
    for marker in (
        "gt152-monster-matchup-hero",
        "gt152-away-logo",
        "gt152-home-logo",
        "gt152-away-record",
        "gt152-home-record",
        "gt152-compact-game-strip",
        "gt152-scoring-defense",
    ):
        assert marker in source
    assert "0-0" in source
    assert "SPORTSBOOK" in source
    assert "0.0%" in source


def test_v152_browser_qa_opens_both_team_evidence_and_checks_deep_audit_collapsed() -> None:
    source = QA.read_text(encoding="utf-8")
    assert "Syracuse evidence" in source
    assert "Pittsburgh evidence" in source
    assert "Deep model evidence • Step 11 distribution" in source
    assert "aria-expanded" in source
    assert "Recent completed games" in source
    assert "DATA SOURCE" in source


def test_v152_browser_qa_writes_json_and_screenshot_evidence() -> None:
    source = QA.read_text(encoding="utf-8")
    assert "cfb_game_total_v152.png" in source
    assert "cfb_game_total_v152.json" in source
    assert "page.screenshot" in source
    assert "json.dumps" in source


def test_v152_browser_workflow_launches_real_app_and_uploads_evidence() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "python -m streamlit run app.py" in source
    assert "python -m devsystem.cfb_game_total_browser_qa_v2" in source
    assert "http://127.0.0.1:8501" in source
    assert "actions/upload-artifact@v4" in source
    assert "if: always()" in source
