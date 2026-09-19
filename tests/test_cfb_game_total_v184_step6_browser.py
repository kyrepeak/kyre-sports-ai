from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "devsystem" / "cfb_game_total_step6_browser_qa_v184.py"
WORKFLOW = ROOT / ".github" / "workflows" / "cfb-game-total-v184-step6-browser.yml"


def _read(path: Path) -> str:
    assert path.exists(), f"missing required V184 browser-cert file: {path}"
    return path.read_text(encoding="utf-8")


def test_v184_browser_qa_locks_exact_step6_dom_and_metric_contract():
    source = _read(QA)
    required = (
        'STEP6_TESTID = "gt157-step-6"',
        'STEP6_TILE_TESTID = "gt184-step6-stat-tile"',
        'STEP6_DEPLOYMENT_MARKER = "CFB_GAME_TOTAL_STEP6_V184_DEPLOYMENT_ACTIVE"',
        '"EXPLOSIVE PASS RATE"',
        '"EXPLOSIVE RUSH RATE"',
        '"OVERALL EXPLOSIVE RATE"',
        '"SCORING-OPPORTUNITY CONVERSION"',
        '"Big-play susceptibility"',
        '"Red-zone TD rate allowed"',
        '"SPORTSBOOK INFLUENCE 0.0%"',
        '"PROJECTION MUTATION OFF"',
        'tile_count != 12',
        'state == "READY"',
        'coverage != 100 or ready_tiles != 12',
        'def _find_v184_frame',
        'selector_qa._wait_for_event_query',
        'selector_qa._selected_link_event',
        'page.reload',
        'CFB_GAME_TOTAL_V184_STEP6_BROWSER_GREEN',
    )
    for token in required:
        assert token in source, token
    assert '"POINTS / OPPORTUNITY"' in source
    assert '"TD DRIVES"' in source
    assert "selector_qa._find_v163_frame" not in source


def test_v184_browser_workflow_runs_real_app_and_uploads_proof():
    source = _read(WORKFLOW)
    required = (
        "CFB Game Total V184 Step 6 browser certification",
        "cfb_game_total_step6_scoring_v1.py",
        "cfb_game_total_clean_page_v18.py",
        "streamlit_memory_lazy_router_v163.py",
        "app.py",
        "devsystem/cfb_game_total_step6_browser_qa_v184.py",
        "tests/test_cfb_game_total_v184_step6_browser.py",
        "python -m playwright install --with-deps chromium",
        "python -m streamlit run app.py",
        "python -m devsystem.cfb_game_total_step6_browser_qa_v184",
        "actions/upload-artifact@v4",
    )
    for token in required:
        assert token in source, token
