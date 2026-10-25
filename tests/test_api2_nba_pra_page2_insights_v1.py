from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSIGHTS_MODULE = ROOT / "nba_pra_page2_insights_v1.py"
PAGE_MODULE = ROOT / "nba_pra_page2_v1.py"


def _insights_module():
    assert INSIGHTS_MODULE.exists(), "NBA PRA Page 2 Insights V1 module is missing"
    return importlib.import_module("nba_pra_page2_insights_v1")


def _context() -> dict:
    return {
        "state": "ready",
        "player_name": "Test Guard",
        "team": "IND",
        "opponent": "NOP",
        "availability": "QUESTIONABLE",
        "line_moved": True,
        "line_moved_label": "LINE MOVED SINCE SELECTION",
        "game": {
            "away_tricode": "IND",
            "home_tricode": "NOP",
            "tip_utc": "2026-10-25T23:00:00Z",
        },
        "player": {
            "player_name": "Test Guard",
            "team": "IND",
            "position": "PG",
            "usage_pct": 27.4,
            "usage_rank": 1,
            "usage_team_size": 15,
            "usage_games": 4,
            "usage_period": "2026-27 REGULAR SEASON",
            "usage_source": "NBA Stats",
            "current_games": [
                {"game_date": "2026-10-24", "opponent": "NOP", "minutes": 36, "points": 22, "rebounds": 5, "assists": 8},
                {"game_date": "2026-10-22", "opponent": "BOS", "minutes": 35, "points": 18, "rebounds": 4, "assists": 7},
                {"game_date": "2026-10-20", "opponent": "MIA", "minutes": 34, "points": 16, "rebounds": 3, "assists": 9},
                {"game_date": "2026-10-18", "opponent": "NYK", "minutes": 33, "points": 14, "rebounds": 4, "assists": 6},
                {"game_date": "2026-10-16", "opponent": "ORL", "minutes": 33, "points": 20, "rebounds": 5, "assists": 7},
            ],
            "prior_games": [
                {"game_date": "2026-03-12", "opponent": "NOP", "minutes": 35, "points": 18, "rebounds": 5, "assists": 8},
                {"game_date": "2026-03-10", "opponent": "CHI", "minutes": 32, "points": 12, "rebounds": 3, "assists": 6},
            ],
        },
        "selected_quote": {
            "sportsbook": "FanDuel",
            "line": 25.5,
            "over_price": -110,
            "under_price": -110,
            "observed_at_utc": "2026-10-25T18:00:00Z",
        },
        "current_quote": {
            "sportsbook": "FanDuel",
            "line": 26.5,
            "over_price": -105,
            "under_price": -115,
            "observed_at_utc": "2026-10-25T21:00:00Z",
        },
        "quotes": [],
    }


def _model() -> dict:
    return {
        "projection": 30.8,
        "sigma": 6.2,
        "current": {
            "sample": 5,
            "l5": 29.6,
            "l10": 28.9,
            "minutes": 34.2,
        },
        "prior": {"sample": 0},
    }


def _result() -> dict:
    return {
        "line": 26.5,
        "edge": 4.3,
        "over_probability": 0.67,
        "under_probability": 0.33,
        "lean": "OVER",
        "confidence": "STRONG",
        "score": 8.1,
        "tier": "STRONG",
    }


def _matchup() -> dict:
    return {
        "points": {"rank": 24, "value": 118.0, "grade": "FAVORABLE"},
        "rebounds": {"rank": 20, "value": 45.2, "grade": "FAVORABLE"},
        "assists": {"rank": 26, "value": 29.1, "grade": "FAVORABLE"},
        "pra_rank": 23,
        "matchup_grade": "FAVORABLE",
        "rank_semantics": "1 = toughest, 30 = most permissive",
        "evidence_period": "2026-27 REGULAR SEASON",
        "source": "Kyre Sports API",
    }


def _section_map(report: dict) -> dict[str, str]:
    return {str(row["title"]): str(row["body"]) for row in report["sections"]}


def test_rich_verified_evidence_builds_detailed_structured_insights() -> None:
    module = _insights_module()
    report = module.build_nba_pra_insights(_context(), _model(), _result(), _matchup(), active_line=26.5)
    sections = _section_map(report)

    assert set(
        (
            "RECENT FORM",
            "ROLE & USAGE",
            "MATCHUP",
            "PLAYER VS OPPONENT",
            "MARKET & MODEL EDGE",
            "AVAILABILITY & RISK",
            "GAME SITUATION",
        )
    ).issubset(sections)
    assert "4 of 5" in sections["RECENT FORM"]
    assert "34.2" in sections["RECENT FORM"]
    assert "27.4%" in sections["ROLE & USAGE"]
    assert "#1" in sections["ROLE & USAGE"]
    assert "#23" in sections["MATCHUP"]
    assert "2 verified" in sections["PLAYER VS OPPONENT"]
    assert "33.0" in sections["PLAYER VS OPPONENT"]
    assert "FanDuel" in sections["MARKET & MODEL EDGE"]
    assert "30.8" in sections["MARKET & MODEL EDGE"]
    assert "+4.3" in sections["MARKET & MODEL EDGE"]
    assert "67%" in sections["MARKET & MODEL EDGE"]
    assert "QUESTIONABLE" in sections["AVAILABILITY & RISK"]
    assert "road" in sections["GAME SITUATION"].casefold()
    assert report["final_title"].startswith("KYRE FINAL INSIGHT")
    assert "OVER 26.5 PRA" in report["final_title"]
    assert report["evidence_count"] >= 7
    assert len([part for part in report["final_body"].split(".") if part.strip()]) >= 3


def test_exact_opponent_history_does_not_mix_other_opponents() -> None:
    module = _insights_module()
    report = module.build_nba_pra_insights(_context(), _model(), _result(), _matchup(), active_line=26.5)
    body = _section_map(report)["PLAYER VS OPPONENT"]

    assert "2 verified" in body
    assert "33.0" in body
    assert "BOS" not in body
    assert "CHI" not in body


def test_under_pick_uses_under_probability_direction_in_final_insight() -> None:
    module = _insights_module()
    result = {
        "line": 25.5,
        "edge": -4.5,
        "over_probability": 0.30,
        "under_probability": 0.70,
        "lean": "UNDER",
        "confidence": "STRONG",
        "score": 8.0,
        "tier": "STRONG",
    }
    model = {**_model(), "projection": 21.0}
    report = module.build_nba_pra_insights(_context(), model, result, _matchup(), active_line=25.5)

    assert "UNDER 25.5 PRA" in report["final_title"]
    assert "70%" in report["final_body"]
    assert "30%" not in report["final_body"]


def test_sparse_evidence_omits_unsupported_claims_instead_of_filling_space() -> None:
    module = _insights_module()
    context = {
        "player_name": "Sparse Player",
        "team": "IND",
        "opponent": "NOP",
        "availability": "UNVERIFIED",
        "game": {"away_tricode": "IND", "home_tricode": "NOP"},
        "player": {"player_name": "Sparse Player", "team": "IND", "current_games": [], "prior_games": []},
        "current_quote": {"sportsbook": "FanDuel", "line": 25.5},
    }
    model = {"projection": 25.0, "sigma": None, "current": {"sample": 0}, "prior": {"sample": 0}}
    result = {"line": 25.5, "edge": -0.5, "over_probability": None, "lean": "PASS", "tier": "PASS"}
    report = module.build_nba_pra_insights(context, model, result, {}, active_line=25.5)
    sections = _section_map(report)
    combined = " ".join(sections.values()).casefold() + " " + report["final_body"].casefold()

    assert "ROLE & USAGE" not in sections
    assert "PLAYER VS OPPONENT" not in sections
    assert "MATCHUP" not in sections
    assert "% probability" not in combined
    assert "pace" not in combined
    assert "home performance" not in combined
    assert "road performance" not in combined
    assert "PASS" in report["final_title"]


def test_page2_renders_insights_between_verdict_and_line_lab() -> None:
    _insights_module()
    from nba_pra_page2_v1 import build_page2_html

    html = build_page2_html(_context(), _model(), _result(), _matchup(), active_line=26.5)
    assert "INSIGHTS" in html
    assert "KYRE FINAL INSIGHT" in html
    assert "RECENT FORM" in html
    assert "MARKET &amp; MODEL EDGE" in html or "MARKET & MODEL EDGE" in html
    assert html.index("KYRE AI VERDICT") < html.index("INSIGHTS") < html.index("FAST LINE LAB")


def test_insights_module_is_pure_and_has_no_provider_client_or_banned_source() -> None:
    assert INSIGHTS_MODULE.exists(), "NBA PRA Page 2 Insights V1 module is missing"
    source = INSIGHTS_MODULE.read_text(encoding="utf-8").casefold()
    for banned in (
        "import requests",
        "requests.get",
        "requests.post",
        "http://",
        "https://",
        "sportsgameodds",
        "espn bet",
        "stats.nba.com",
        "load_kyre_sports_api",
    ):
        assert banned not in source
