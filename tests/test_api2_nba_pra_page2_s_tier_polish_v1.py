from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "nba_pra_page2_command_center_v2.py"
SYNC = ROOT / "nba_pra_page2_sync_v1.py"
V1 = ROOT / "nba_pra_page2_command_center_v1.py"


def _context() -> dict:
    return {
        "state": "ready",
        "player_name": "Jaylen Wells",
        "team": "MEM",
        "opponent": "SAC",
        "availability": "UNVERIFIED",
        "team_logo": "https://example.com/mem.png",
        "opponent_logo": "https://example.com/sac.png",
        "player": {
            "player_name": "Jaylen Wells",
            "team": "MEM",
            "position": "SG",
            "headshot": "https://example.com/wells.png",
            "current_games": [
                {"game_date": "2026-10-23", "opponent": "UTA", "minutes": 25, "points": 17, "rebounds": 4, "assists": 3},
                {"game_date": "2026-10-21", "opponent": "POR", "minutes": 28, "points": 12, "rebounds": 5, "assists": 0},
            ],
            "prior_games": [],
        },
        "game": {"away_tricode": "MEM", "home_tricode": "SAC"},
        "selected_quote": {"sportsbook": "FanDuel", "line": 15.5, "over_price": -104, "under_price": -122, "observed_at_utc": "2026-10-26T00:12:59Z"},
        "current_quote": {"sportsbook": "FanDuel", "line": 15.5, "over_price": -104, "under_price": -122, "observed_at_utc": "2026-10-26T00:12:59Z"},
        "quotes": [
            {"sportsbook": "FanDuel", "line": 15.5, "over_price": -104, "under_price": -122, "observed_at_utc": "2026-10-26T00:12:59Z"},
            {"sportsbook": "DraftKings", "line": 15.5, "over_price": -110, "under_price": -110, "observed_at_utc": "2026-10-26T00:11:00Z"},
        ],
    }


def _model() -> dict:
    return {
        "projection": 20.5,
        "sigma": 4.0,
        "current": {"sample": 2, "l5": 20.5, "l10": 20.5, "minutes": 26.5},
        "prior": {"sample": 0},
    }


def _result() -> dict:
    return {"line": 15.5, "edge": 5.0, "over_probability": 0.89, "under_probability": 0.11, "lean": "OVER", "score": 10.0, "tier": "ELITE"}


def _matchup() -> dict:
    return {
        "points": {"rank": 26, "value": 124.5, "grade": "FAVORABLE"},
        "rebounds": {"rank": 21, "value": 47.0, "grade": "MEDIUM"},
        "assists": {"rank": 28, "value": 29.5, "grade": "FAVORABLE"},
        "pra_rank": 25,
        "matchup_grade": "FAVORABLE",
        "rank_semantics": "NBA opponent rank: 1 = toughest/stingiest, 30 = most permissive",
        "evidence_period": "2026-27 REGULAR SEASON",
    }


def _load_v2():
    assert V2.exists(), "Page 2 S-tier polish V2 module is missing"
    import importlib.util
    spec = importlib.util.spec_from_file_location("nba_pra_page2_command_center_v2", V2)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_v2_adds_scan_first_decision_support_without_changing_model() -> None:
    page = _load_v2()
    html = page.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=15.5)
    assert "LIMITED VERIFIED CONTEXT" in html
    assert "WHY THIS PICK WORKS" in html
    assert "WHAT COULD BREAK IT" in html
    assert "+5.0 PRA EDGE" in html
    assert "2/2 OVER" in html
    assert "FAVORABLE PRA MATCHUP" in html
    assert "SMALL SAMPLE: 2 GAMES" in html
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_v2_insights_are_scan_first_and_final_insight_has_edge_and_caution() -> None:
    page = _load_v2()
    html = page.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=15.5)
    assert "QUICK READ" in html
    assert "20.5 PRA AVG" in html
    assert "89% OVER" in html
    assert "ANALYST SUMMARY" in html
    assert "PRIMARY EDGE" in html
    assert "PRIMARY CAUTION" in html
    assert "Sportsbook projection influence" not in html


def test_v2_recent_performance_has_compact_summary_metrics() -> None:
    page = _load_v2()
    html = page.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=15.5)
    assert "RECENT PERFORMANCE" in html
    assert "L5 PRA" in html
    assert "20.5" in html
    assert "HIT RATE" in html
    assert "2/2" in html
    assert "RECENT MIN" in html
    assert "26.5" in html
    assert "SAMPLE" in html
    assert "2 GAMES" in html


def test_v2_market_intelligence_surfaces_best_prices_without_averaging_lines() -> None:
    page = _load_v2()
    html = page.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=15.5)
    assert "2 VERIFIED BOOKS" in html
    assert "BEST OVER PRICE" in html
    assert "FanDuel" in html and "-104" in html
    assert "BEST UNDER PRICE" in html
    assert "DraftKings" in html and "-110" in html
    assert "Conflicting lines are never averaged" in html
    assert "CONSENSUS LINE" not in html


def test_v2_css_tightens_top_space_and_visually_integrates_slider() -> None:
    page = _load_v2()
    css = page._css()
    assert "p2cc-line-lab-polish" in css
    assert 'data-testid="stSlider"' in css
    assert "padding-top" in css
    assert "@media(max-width:760px)" in css.replace(" ", "")


def test_live_sync_activates_v2_but_v1_stays_untouched() -> None:
    sync = SYNC.read_text(encoding="utf-8")
    assert "from nba_pra_page2_command_center_v2 import _css, build_page2_html" in sync
    assert "nba_pra_page2_command_center_v1" not in sync
    v1 = V1.read_text(encoding="utf-8")
    assert 'VERSION = "API2_NBA_PRA_PAGE2_S_TIER_COMMAND_CENTER_V1"' in v1
    assert "WHY THIS PICK WORKS" not in v1
