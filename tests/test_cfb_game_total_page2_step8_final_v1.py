from __future__ import annotations

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "cfb_game_total_page2_step8_final_runtime_v1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
CERT = ROOT / "devsystem/cfb_game_total_page2_step8_live_cert_v1.py"
APP = ROOT / "app.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_runtime():
    assert RUNTIME.is_file(), "Step-8 final Page-2 runtime must exist before GREEN"
    spec = importlib.util.spec_from_file_location("cfb_gt_page2_step8", RUNTIME)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload() -> dict:
    return {
        "identity": {
            "away": {"team": "Arizona State", "conference": "Big 12"},
            "home": {"team": "Texas Tech", "conference": "Big 12"},
            "venue": "Jones AT&T Stadium",
            "kickoff_iso": "2026-10-10T23:00:00Z",
        },
        "away": {"team": "Arizona State", "record": "5-1"},
        "home": {"team": "Texas Tech", "record": "6-0"},
        "display_game": {
            "espn_event_id": "401999999",
            "game_date": "2026-10-10",
            "kickoff_iso": "2026-10-10T23:00:00Z",
            "venue": "Jones AT&T Stadium",
            "location": "Lubbock, TX",
            "market_total": 58.5,
        },
        "raw": {
            "projected_combined_total": 63.8,
            "over_probability": 0.61,
            "under_probability": 0.39,
            "analysis_line": 58.5,
            "projected_away_points": 30.1,
            "projected_home_points": 33.7,
            "recent_totals": [55, 62, 60, 66, 59],
            "line_scenarios": [
                {"line": 55.5, "over_probability": "67%", "under_probability": "33%"},
                {"line": 58.5, "over_probability": "61%", "under_probability": "39%"},
                {"line": 61.5, "over_probability": "54%", "under_probability": "46%"},
            ],
        },
        "final": {
            "ready": True,
            "projected_combined_total": 63.8,
            "forecast_strength": 0.61,
            "grade": "B",
            "recommendation": "OVER",
        },
        "statuses": {1: "READY"},
        "ready_count": 12,
        "away_logo_html": '<span class="logo">ASU</span>',
        "home_logo_html": '<span class="logo">TTU</span>',
    }


def test_step8_files_exist_before_green() -> None:
    assert RUNTIME.is_file()
    assert ROUTER.is_file()
    assert CERT.is_file()


def test_step8_runtime_composes_all_frozen_page2_surfaces() -> None:
    step8 = _load_runtime()
    html = step8.build_page2_final_html(_payload())
    for marker in (
        'data-testid="gtp2s2-matchup-hero"',
        'data-testid="gtp2s3-flow"',
        'data-testid="gtp2s4-outlook"',
        'data-testid="gtp2s5-team-snapshot"',
        'data-testid="gtp2s6-trends"',
        'data-testid="gtp2s7-line-lab"',
        'data-testid="gtp2s7-best-bet"',
        'data-testid="gtp2s8-back-to-slate"',
        'data-testid="gtp2s8-final"',
    ):
        assert marker in html
    assert "401999999" in html
    assert "America/Phoenix" in html


def test_step8_runtime_is_display_only_and_preserves_steps_2_to_7() -> None:
    step8 = _load_runtime()
    assert step8.FREEZE_TOKEN == "CFB_GAME_TOTAL_PAGE2_V1_STEP8_FINAL_RESPONSIVE_LIVE_DATA_FROZEN"
    assert step8.MAY_MODIFY_PAGE1 is False
    assert step8.MAY_MODIFY_PROJECTION is False
    assert step8.MAY_MODIFY_PROBABILITY is False
    assert step8.MAY_MODIFY_MODEL is False
    assert step8.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert step8.NETWORK_CALLS_ADDED == 0
    assert step8.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert len(step8.FROZEN_STEP_TOKENS) == 6
    source = _read(RUNTIME).lower()
    assert "requests." not in source
    assert "httpx." not in source
    assert "urllib.request" not in source


def test_step8_router_activates_only_selected_cfb_game_total() -> None:
    body = _read(ROUTER)
    assert 'EVENT_QUERY_KEY = "ks_cfb_game_total_event_id"' in body
    assert 'GAME_TOTAL_MARKET = "Game Total"' in body
    assert 'CFB_SPORT = "CFB"' in body
    assert "cfb_router.GAME_TOTAL_PAGE = PAGE2_RUNTIME" in body
    assert "finally:" in body
    assert "cfb_router.GAME_TOTAL_PAGE = original" in body
    assert "return frozen_parent.render_app()" in body
    assert "MAY_MODIFY_OTHER_SPORTS = False" in body


def test_step8_app_activates_final_router() -> None:
    app = _read(APP)
    assert (
        "from streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1 "
        "import record_bootstrap_import_ms, render_app"
    ) in app
    assert "CFB_GAME_TOTAL_PAGE2_STEP8_FINAL_RUNTIME" in app


def test_step8_live_cert_covers_required_viewports_and_live_contract() -> None:
    body = _read(CERT)
    for width in (390, 430, 768, 1440):
        assert f'"width": {width}' in body
    for marker in (
        "gtp2s2-matchup-hero",
        "gtp2s3-flow",
        "gtp2s4-outlook",
        "gtp2s5-team-snapshot",
        "gtp2s6-trends",
        "gtp2s7-line-lab",
        "gtp2s7-best-bet",
        "gtp2s8-back-to-slate",
        "gtp2s8-final",
    ):
        assert marker in body
    assert "horizontal_overflow" in body
    assert "data limited" in body.lower()
    assert "mock data" in body.lower()
    assert "pending" in body.lower()
    assert "ks_cfb_game_total_event_id" in body
    assert "sportsbook_projection_influence" in body
    assert "github_actions_fallback" in body


def test_step8_sample_has_no_limited_mock_or_pending_copy() -> None:
    step8 = _load_runtime()
    html = step8.build_page2_final_html(_payload()).lower()
    assert "data limited" not in html
    assert "mock data" not in html
    assert "pending" not in html
    assert "horizontal-scroll" not in html
    assert "@media(max-width:760px)" in html
    assert "@media(max-width:480px)" in html
