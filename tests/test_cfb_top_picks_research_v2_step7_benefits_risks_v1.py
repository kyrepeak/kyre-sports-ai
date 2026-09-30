from __future__ import annotations

from pathlib import Path

import cfb_top_picks_benefits_risks_v1 as br
from devsystem.cfb_top_picks_research_v2_step7_benefits_risks_v1 import check_repository


def _metric(value):
    return {"value": value, "status": "VERIFIED", "source": "verified source", "observed_at": "2026-09-30T05:00:00+00:00"}


def _detail():
    return {
        "ready": True,
        "market_reasoning": {"observed_at": "2026-09-30T05:00:00+00:00"},
        "offense_research": {
            "away": {"observed_at": "2026-09-30T05:00:00+00:00", "metrics": {"points_per_game": _metric(34), "recent_scoring_avg": _metric(28)}, "recent_games": [{"points_for": 31, "points_against": 28}], "source_router": {"recent_scoring": {"provider": "verified recent"}}},
            "home": {"observed_at": "2026-09-30T05:00:00+00:00", "metrics": {"points_per_game": _metric(29), "recent_scoring_avg": _metric(30)}, "recent_games": [{"points_for": 35, "points_against": 27}], "source_router": {"recent_scoring": {"provider": "verified recent"}}},
        },
        "defense_pace_research": {
            "away": {"metrics": {"recent_points_allowed_avg": _metric(24)}},
            "home": {"metrics": {"recent_points_allowed_avg": _metric(27)}},
        },
        "history_ready": True, "history_source": "verified history",
        "sources_verified": ["verified history"], "history_observed_at": "2026-09-30T05:00:00+00:00",
        "meetings": 4, "away_wins": 1, "home_wins": 3, "avg_combined_total": 65.0,
    }


def _row(market, pick):
    return {"market": market, "pick": pick, "away": "Away State", "home": "Home Tech", "probability": 66, "probability_value": .66, "source": "frozen model"}


def test_step7_permanent_contract_green():
    assert check_repository()["status"] == "GREEN"


def test_step7_three_markets_have_benefits_and_risks_with_sources():
    for market, pick in (("OVER/UNDER", "Over 60.5"), ("SPREAD", "Away State +3.5"), ("MONEYLINE", "Away State")):
        result = br.build_benefits_risks(_row(market, pick), _detail())
        assert result["benefits"]
        assert result["risks"]
        assert result["projection_weight"] == 0.0
        for item in result["benefits"] + result["risks"]:
            assert item["sources"]
            assert item["observed_at"]


def test_step7_is_additive_over_frozen_step6():
    details = Path("cfb_top_picks_details_v3.py").read_text(encoding="utf-8")
    page = Path("cfb_top_picks_page_v7.py").read_text(encoding="utf-8")
    router = Path("streamlit_memory_lazy_router_cfb_top_picks_research_v2_step7.py").read_text(encoding="utf-8")
    assert "import cfb_top_picks_details_v2 as prior" in details
    assert "import cfb_top_picks_page_v6 as prior" in page
    assert "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step6 as prior" in router
    assert "<h4>Benefits</h4>" in page
    assert "<h4>Risks</h4>" in page
