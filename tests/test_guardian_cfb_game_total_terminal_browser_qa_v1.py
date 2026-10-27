from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "devsystem" / "guardian_cfb_game_total_terminal_browser_qa_v1.py"
V150 = ROOT / ".github" / "workflows" / "cfb-game-total-v150-browser.yml"
V152 = ROOT / ".github" / "workflows" / "cfb-game-total-v152-activation.yml"
CONFTEST = ROOT / "tests" / "conftest.py"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing Guardian terminal-cert asset: {path}"
    return path.read_text(encoding="utf-8")


def test_guardian_terminal_browser_contract_is_current_and_date_agnostic() -> None:
    source = _read(QA)
    for token in (
        'ROUTE_SPORT_KEY = "sport"',
        'ROUTE_MARKET_KEY = "market"',
        'ROUTE_SPORT = "cfb"',
        'ROUTE_MARKET = "game-total"',
        'SELECTION_QUERY_KEY = "cfbgt_game"',
        '"KYRE SPORTS AI • CFB GAME TOTALS"',
        '"Game Total Intelligence"',
        '"UPCOMING MATCHUPS"',
        '"No upcoming CFB games remain on this slate. "',
        '".cfbgt4-rail"',
        '"a.cfbgt4-chip"',
        '".cfbgt6-card"',
        "page.reload",
        "GUARDIAN_CFB_GAME_TOTAL_TERMINAL_BROWSER_GREEN",
        "terminal_state = EMPTY_SLATE_MARKER in body or all(",
    ):
        assert token in source, token
    for stale in (
        "CERT_DATE",
        "2026-09-19",
        "gt163-game-strip",
        "gt157-step-6",
        "GAMES ON THIS DAY",
        "CFB_GAME_TOTAL_V163_PRODUCTION_ACTIVE",
        "CFB_GAME_TOTAL_STEP6_V184_DEPLOYMENT_ACTIVE",
    ):
        assert stale not in source, stale


def test_unavoidable_legacy_wrappers_delegate_to_one_guardian_terminal_proof() -> None:
    command = "python -m devsystem.guardian_cfb_game_total_terminal_browser_qa_v1"
    for path in (V150, V152):
        workflow = _read(path)
        assert command in workflow
        assert "python -m devsystem.cfb_game_total_browser_qa_v4" not in workflow
        assert "python devsystem/cfb_game_total_v152_activation_qa.py" not in workflow
        assert "devsystem/guardian_cfb_game_total_terminal_browser_qa_v1.py" in workflow
        assert "tests/test_guardian_cfb_game_total_terminal_browser_qa_v1.py" in workflow


def test_global_pytest_collector_is_runtime_neutral_without_mutating_frozen_browser_contract() -> None:
    source = _read(CONFTEST)
    assert "record_bootstrap_import_ms," in source
    assert "render_app," in source
    assert "from devsystem.shared_runtime_lifecycle_v1 import run_shared_runtime_lifecycle" in source
    assert "run_shared_runtime_lifecycle(" in source
    assert "render=render_app" in source
    assert "from streamlit_memory_lazy_router_v157 import record_bootstrap_import_ms, render_app" not in source
    assert 'ROUTE_QUERY_MARKET = "ks_cfb_market"' in source
    assert 'FULL_RENDER_MARKER = "VIEW TOP 5 →"' in source
