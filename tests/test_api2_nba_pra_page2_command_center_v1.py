from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "nba_pra_page2_command_center_v1.py"


def _load_module():
    assert MODULE.exists(), "NBA PRA Page 2 command-center module is missing"
    spec = importlib.util.spec_from_file_location("nba_pra_page2_command_center_v1_test", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _context() -> dict:
    return {
        "state": "ready",
        "line_moved": True,
        "line_moved_label": "FanDuel line moved from 25.5 to 26.0",
        "player_name": "Andrew Nembhard",
        "team": "IND",
        "opponent": "NOP",
        "availability": "AVAILABLE",
        "team_logo": "https://cdn.nba.com/ind.svg",
        "opponent_logo": "https://cdn.nba.com/nop.svg",
        "game": {"away_tricode": "IND", "home_tricode": "NOP", "tip_utc": "2026-10-25T23:00:00Z"},
        "player": {
            "player_name": "Andrew Nembhard",
            "team": "IND",
            "position": "PG",
            "headshot": "https://example.com/nembhard.png",
            "usage_pct": 24.8,
            "usage_rank": 2,
            "usage_team_size": 15,
            "usage_games": 68,
            "usage_period": "2025-26 REGULAR SEASON",
            "usage_source": "NBA Stats",
            "current_games": [
                {"game_date": "2026-10-23", "opponent": "NOP", "minutes": 36, "points": 15, "rebounds": 3, "assists": 10},
                {"game_date": "2026-10-21", "opponent": "BOS", "minutes": 32, "points": 13, "rebounds": 1, "assists": 10},
                {"game_date": "2026-10-19", "opponent": "MIA", "minutes": 34, "points": 14, "rebounds": 2, "assists": 9},
            ],
            "prior_games": [],
        },
        "selected_quote": {
            "sportsbook": "FanDuel",
            "line": 25.5,
            "over_price": -108,
            "under_price": -112,
            "observed_at_utc": "2026-10-25T18:00:00Z",
        },
        "current_quote": {
            "sportsbook": "FanDuel",
            "line": 26.0,
            "over_price": -113,
            "under_price": -107,
            "observed_at_utc": "2026-10-25T22:30:00Z",
        },
        "quotes": [
            {"sportsbook": "FanDuel", "line": 26.0, "over_price": -113, "under_price": -107, "observed_at_utc": "2026-10-25T22:30:00Z"},
            {"sportsbook": "DraftKings", "line": 26.5, "over_price": -110, "under_price": -110, "observed_at_utc": "2026-10-25T22:28:00Z"},
        ],
    }


def _model() -> dict:
    return {
        "projection": 27.9,
        "sigma": 6.0,
        "basis": "CURRENT SEASON",
        "current": {"sample": 3, "l5": 25.7, "l10": 25.7, "minutes": 34.0},
        "prior": {"sample": 0},
    }


def _result() -> dict:
    return {
        "line": 26.0,
        "edge": 1.9,
        "over_probability": 0.624,
        "under_probability": 0.376,
        "lean": "OVER",
        "confidence": "MEDIUM",
        "score": 7.4,
        "tier": "STRONG",
    }


def _matchup() -> dict:
    return {
        "points": {"rank": 26, "value": 124.5, "grade": "FAVORABLE"},
        "rebounds": {"rank": 21, "value": 47.0, "grade": "MEDIUM"},
        "assists": {"rank": 28, "value": 29.5, "grade": "FAVORABLE"},
        "pra_rank": 25,
        "matchup_grade": "FAVORABLE",
        "rank_semantics": "NBA opponent rank: 1 = toughest/stingiest, 30 = most permissive",
        "evidence_period": "2026-27 REGULAR SEASON",
        "source": "Kyre Sports API",
    }


def test_command_center_uses_visual_analytics_hierarchy_without_legacy_duplicate_panels() -> None:
    page = _load_module()
    html = page.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=26.0)
    order = [
        "PLAYER COMMAND CENTER",
        "PROJECTION DISTRIBUTION",
        "KYRE INSIGHTS",
        "RECENT PERFORMANCE",
        "VERIFIED PRA COMPOSITION",
        "MATCHUP INTELLIGENCE",
        "MARKET INTELLIGENCE",
        "RISK & EVIDENCE QUALITY",
        "FULL GAME LOG",
    ]
    positions = [html.index(label) for label in order]
    assert positions == sorted(positions)
    assert "KYRE AI VERDICT" not in html
    assert "FAST LINE LAB" not in html


def test_distribution_and_recent_chart_use_verified_projection_sigma_games_and_threshold() -> None:
    page = _load_module()
    html = page.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=26.0)
    assert 'class="p2cc-distribution-svg"' in html
    assert "KYRE 27.9" in html
    assert "BOOK LINE 26.0" in html
    assert "MODEL SIGMA 6.0" in html
    assert 'class="p2cc-recent-svg"' in html
    assert "28.0" in html and "24.0" in html and "25.0" in html
    assert "ACTIVE LINE 26.0" in html


def test_verified_pra_composition_is_history_based_not_fake_component_projection() -> None:
    page = _load_module()
    html = page.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=26.0)
    assert "VERIFIED PRA COMPOSITION" in html
    assert "14.0 PTS" in html
    assert "2.0 REB" in html
    assert "9.7 AST" in html
    assert "PROJECTED PTS" not in html
    assert "PROJECTED REB" not in html
    assert "PROJECTED AST" not in html


def test_matchup_and_market_are_visual_but_quotes_remain_independent() -> None:
    page = _load_module()
    html = page.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=26.0)
    assert html.count('class="p2cc-rank-bar"') == 4
    assert "#26" in html and "#21" in html and "#28" in html and "#25" in html
    assert "FanDuel" in html and "DraftKings" in html
    assert "25.5 → 26.0" in html
    assert "CONSENSUS LINE" not in html


def test_hero_evidence_coverage_counts_verified_matchup() -> None:
    page = _load_module()
    html = page.build_page2_html(_context(), _model(), _result(), _matchup(), active_line=26.0)
    assert "6/6 VERIFIED DATA AREAS" in html


def test_sparse_data_fails_closed_into_compact_data_gaps() -> None:
    page = _load_module()
    context = {
        "player_name": "Sparse Player",
        "team": "MEM",
        "opponent": "SAC",
        "availability": "UNVERIFIED",
        "player": {"player_name": "Sparse Player", "current_games": [], "prior_games": []},
        "quotes": [],
    }
    html = page.build_page2_html(
        context,
        {"projection": 20.5, "sigma": None, "current": {"sample": 0}, "prior": {"sample": 0}},
        {"lean": "OVER", "edge": 5.0, "over_probability": None, "score": None, "tier": ""},
        {},
        active_line=15.5,
    )
    assert "DATA GAPS" in html
    assert "Projection distribution unavailable" in html
    assert "Verified PRA composition unavailable" in html
    assert 'class="p2cc-distribution-svg"' not in html
    assert "0.0 PTS" not in html
    assert "AVAILABLE" not in html.replace("UNAVAILABLE", "")


def test_command_center_css_has_mobile_single_column_and_no_network_code() -> None:
    page = _load_module()
    css = page._css().replace(" ", "")
    source = MODULE.read_text(encoding="utf-8").lower()
    assert "@media(max-width:760px)" in css
    assert "grid-template-columns:1fr" in css
    for forbidden in ("import requests", "import httpx", "requests.get", "httpx.get", "espn", "sgo"):
        assert forbidden not in source
