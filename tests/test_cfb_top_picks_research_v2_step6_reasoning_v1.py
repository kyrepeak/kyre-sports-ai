from __future__ import annotations

from pathlib import Path

import cfb_top_picks_market_reasoning_v1 as reasoning
import cfb_top_picks_page_v6 as page
from devsystem.cfb_top_picks_research_v2_step6_market_reasoning_v1 import check_repository


def _metric(value, source="verified source"):
    return {"value": value, "status": "VERIFIED", "source": source, "observed_at": "2026-09-30T04:00:00+00:00"}


def _research():
    offense = {
        "observed_at": "2026-09-30T04:00:00+00:00",
        "away": {"team": "Away State", "observed_at": "2026-09-30T04:00:00+00:00", "metrics": {
            "points_per_game": _metric(34.0), "recent_scoring_avg": _metric(31.0), "yards_per_play": _metric(6.4),
        }, "recent_games": [{"points_for": 35, "points_against": 24}], "source_router": {"recent_scoring": {"provider": "ESPN recent"}}},
        "home": {"team": "Home Tech", "observed_at": "2026-09-30T04:00:00+00:00", "metrics": {
            "points_per_game": _metric(29.0), "recent_scoring_avg": _metric(27.0), "yards_per_play": _metric(5.8),
        }, "recent_games": [{"points_for": 27, "points_against": 30}], "source_router": {"recent_scoring": {"provider": "ESPN recent"}}},
    }
    defense = {
        "observed_at": "2026-09-30T04:00:00+00:00",
        "away": {"team": "Away State", "metrics": {
            "points_allowed_per_game": _metric(20.0), "recent_points_allowed_avg": _metric(23.0),
            "yards_per_play_allowed": _metric(5.0), "plays_per_game": _metric(72.0),
        }},
        "home": {"team": "Home Tech", "metrics": {
            "points_allowed_per_game": _metric(27.0), "recent_points_allowed_avg": _metric(29.0),
            "yards_per_play_allowed": _metric(5.9), "plays_per_game": _metric(68.0),
        }},
    }
    series = {"history_ready": True, "status": "VERIFIED_HISTORY", "source": "history", "sources_verified": ["history"], "observed_at": "2026-09-30T04:00:00+00:00", "meetings": 4, "away_wins": 3, "home_wins": 1, "avg_combined_total": 58.5}
    return offense, defense, series


def _row(market, pick):
    return {"rank": 1, "event_id": "401234567", "away": "Away State", "away_abbr": "AWY", "home": "Home Tech", "home_abbr": "HME", "time": "Sat, 12:00 PM", "network": "ESPN", "market": market, "pick": pick, "odds": "-110", "probability": 66, "probability_value": .66, "toughness": 3, "toughness_label": "Medium", "reliability": .88, "source": "frozen model"}


def test_step6_permanent_contract():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["step"] == "6/9"
    assert result["steps1_5_wrapped_not_modified"] is True


def test_step6_all_three_market_contracts_have_exact_required_signals():
    offense, defense, series = _research()
    for market, pick in (("OVER/UNDER", "Over 51.5"), ("SPREAD", "Away State +3.5"), ("MONEYLINE", "Away State")):
        result = reasoning.build_market_reasoning(_row(market, pick), {"espn_event_id": "401234567"}, offense, defense, series)
        assert set(result["signals"]) == set(reasoning.REQUIRED_SIGNALS[market])
        assert result["projection_weight"] == 0.0
        assert result["sportsbook_projection_weight"] == 0.0
        assert result["may_modify_probability"] is False
        assert result["may_modify_ranking"] is False
        assert result["may_modify_selection"] is False


def test_step6_ui_is_additive_over_frozen_v5_and_no_raw_audit_markup_leaks():
    row = _row("MONEYLINE", "Away State")
    offense, defense, series = _research()
    market = reasoning.build_market_reasoning(row, {"espn_event_id": "401234567"}, offense, defense, series)
    detail = {
        "why": "Why", "benefit": "Benefit", "event_id": "401234567",
        "meetings": 0, "history_rows": [], "market_reasoning": market,
    }
    html = page._page_html([row], {"games_analyzed": 1}, "2026-10-03", "401234567", detail)
    assert "Market-Aware Football Reasoning" in html
    assert page.PAGE_MARKER in html
    assert 'data-market="MONEYLINE"' in html
    assert "<div class=&quot;tp4-audit&quot;>" not in html


def test_step6_does_not_modify_frozen_owner_files():
    guard = Path("devsystem/cfb_top_picks_research_v2_step6_market_reasoning_v1.py").read_text(encoding="utf-8")
    assert "cfb_top_picks_details_v1 as prior" in Path("cfb_top_picks_details_v2.py").read_text(encoding="utf-8")
    assert "cfb_top_picks_page_v5 as prior" in Path("cfb_top_picks_page_v6.py").read_text(encoding="utf-8")
    assert "steps1_5_wrapped_not_modified" in guard
