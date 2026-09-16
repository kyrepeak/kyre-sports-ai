from pathlib import Path

import cfb_over_under_clean_page_v36 as page

ROOT = Path(__file__).resolve().parents[1]


def test_phoenix_time_conversion_during_dst():
    assert page.format_phoenix_from_iso("2026-09-19T23:30:00Z") == "4:30 PM Phoenix"


def test_phoenix_time_conversion_crosses_calendar_day():
    assert page.format_phoenix_from_iso("2026-11-07T02:00:00Z") == "7:00 PM Phoenix"
    assert page.phoenix_date_from_iso("2026-11-07T02:00:00Z") == "2026-11-06"


def test_invalid_time_fails_closed():
    assert page.format_phoenix_from_iso("") == "Time TBD"
    assert page.format_phoenix_from_iso("not-a-date") == "Time TBD"


def test_steps_five_through_ten_are_compact_targets():
    assert page.COMPACT_STEPS == {5, 6, 7, 8, 9, 10}
    assert page.compact_step_number("<div>STEP 8 • TURNOVER VOLATILITY</div>") == 8
    assert page.compact_step_number("<div>STEP 4 • PACE</div>") is None


def test_sportsbook_never_enters_projection():
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False
    source = (ROOT / "cfb_over_under_clean_page_v36.py").read_text(encoding="utf-8")
    assert 'FROZEN_PAGE = "cfb_over_under_clean_page_v35"' in source
    assert "runtime_slate.analyze_game" not in source
    assert "projected_total =" not in source


def test_router_v149_is_exact_over_under_only():
    source = (ROOT / "streamlit_memory_lazy_router_v149.py").read_text(encoding="utf-8")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v148"' in source
    assert 'OVER_UNDER_MARKET = "Over/Under"' in source
    assert 'ACTIVE_PAGE = "cfb_over_under_clean_page_v36"' in source
    assert "prior.render_app()" in source
    assert "Moneyline" not in source or "Moneyline remains owned by frozen V148" in source


def test_app_bootstraps_v149_additively():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'FROZEN_V148_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V148_CFB_MONEYLINE_MONSTER_DASHBOARD_2026-09-16"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V149_CFB_OVER_UNDER_MONSTER_COMPACT_2026-09-16"' in source
    assert "from streamlit_memory_lazy_router_v149 import record_bootstrap_import_ms, render_app" in source
