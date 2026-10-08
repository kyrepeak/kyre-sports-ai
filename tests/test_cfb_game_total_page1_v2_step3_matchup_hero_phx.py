from __future__ import annotations

import importlib.util
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PRESENTATION = ROOT / "cfb_game_total_page1_step3_presentation_v1.py"
PAGE = ROOT / "cfb_game_total_clean_page_v36.py"
ACTIVATION = ROOT / "cfb_game_total_page1_v2_step3_activation.py"
SHELL = ROOT / "kyre_universal_shell_runtime_v1.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_presentation():
    spec = importlib.util.spec_from_file_location("step3_presentation", PRESENTATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_step3_successor_files_exist() -> None:
    assert PRESENTATION.exists(), "Step-3 Phoenix presentation helper must exist"
    assert PAGE.exists(), "Step-3 Page V36 wrapper must exist"
    assert ACTIVATION.exists(), "Step-3 CFB-only activation hook must exist"


def test_step3_phoenix_time_and_future_only_contract() -> None:
    presentation = _load_presentation()
    assert presentation.PHOENIX_TZ == "America/Phoenix"
    assert presentation.phoenix_kickoff_text(
        {"game_date": "2026-10-08", "kickoff": "7:00 PM ET"}
    ) == "4:00 PM AZ"

    now = datetime(2026, 10, 7, 21, 12, tzinfo=ZoneInfo("America/Phoenix"))
    days = presentation.future_day_window(date(2026, 10, 7), now=now, count=7)
    assert days[0] == date(2026, 10, 8)
    assert all(day > now.date() for day in days)
    assert days == sorted(days)


def test_step3_matchup_hero_visual_contract() -> None:
    page = _read(PAGE)
    visual = page + "\n" + _read(PRESENTATION)
    assert "import cfb_game_total_clean_page_v35 as prior" in page
    assert "import cfb_game_total_clean_page_v11 as day_owner" in page
    assert "import cfb_game_total_clean_page_v14 as selector_owner" in page
    assert "import cfb_game_total_clean_page_v25 as hero_owner" in page
    assert "PAGE1 V2 STEP3 MATCHUP HERO PHOENIX" in page
    assert "Overview" in visual
    assert "Full Analysis" in visual
    assert "data-testid=\"gt236-matchup-hero\"" in visual
    assert "data-testid=\"gt236-view-tabs\"" in visual
    assert "PHX" in visual or "AZ" in visual
    assert "MAY_MODIFY_PROJECTION = False" in page
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page


def test_step3_presentation_seams_are_scoped_and_restored() -> None:
    page = _read(PAGE)
    for token in (
        "day_owner._render_day_strip",
        "selector_owner._kickoff_text",
        "hero_owner._matchup_header_html_v25",
    ):
        assert token in page
    assert "finally:" in page
    assert "prior.render_game_total_hub" in page
    assert "cfb_game_total_clean_page_v35" in page


def test_step3_activation_is_cfb_game_total_only() -> None:
    activation = _read(ACTIVATION)
    shell = _read(SHELL)
    assert "import streamlit_memory_lazy_router_v190 as cfb_router" in activation
    assert 'BASE_PAGE = "cfb_game_total_clean_page_v35"' in activation
    assert 'STEP3_PAGE = "cfb_game_total_clean_page_v36"' in activation
    assert "cfb_router.GAME_TOTAL_PAGE = STEP3_PAGE" in activation
    assert "from cfb_game_total_page1_v2_step3_activation import activate_step3_page" in shell
    assert "activate_step3_page()" in shell


def test_step3_does_not_reopen_frozen_steps() -> None:
    page = _read(PAGE)
    activation = _read(ACTIVATION)
    assert "cfb_game_total_clean_page_v35.py" not in activation
    assert "streamlit_memory_lazy_router_v190.py" not in activation
    assert "MAY_MODIFY_PROJECTION = False" in page
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in page
