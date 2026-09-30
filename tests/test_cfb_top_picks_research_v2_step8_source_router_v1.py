from __future__ import annotations

from pathlib import Path

import cfb_top_picks_source_router_v1 as router
from devsystem.cfb_top_picks_research_v2_step8_source_router_v1 import check_repository


def _m(value, source="verified source", status="VERIFIED", note=""):
    return {"value": value, "status": status, "source": source, "observed_at": "2026-09-30T06:00:00+00:00", "note": note}


def _detail():
    return {
        "offense_research": {"away": {"metrics": {"points_per_game": _m(31)}}, "home": {"metrics": {"points_per_game": _m(28)}}},
        "defense_pace_research": {"away": {"metrics": {"plays_per_game": _m(72, "NCAA pace")}}, "home": {"metrics": {"plays_per_game": _m(68, "ESPN Core", "VERIFIED_FALLBACK")}}},
        "market_reasoning": {"required_signals": ["edge"], "signals": {"edge": {"status": "VERIFIED", "text": "edge", "sources": ["verified source"], "observed_at": "2026-09-30T06:00:00+00:00"}}},
        "benefits_risks": {"benefits": [{"status": "VERIFIED", "text": "benefit", "sources": ["verified source"], "observed_at": "2026-09-30T06:00:00+00:00"}], "risks": [{"status": "VERIFIED", "text": "risk", "sources": ["verified source"], "observed_at": "2026-09-30T06:00:00+00:00"}]},
        "history_status": "VERIFIED_HISTORY", "history_source": "Winsipedia", "sources_verified": ["Winsipedia"], "history_observed_at": "2026-09-30T06:00:00+00:00",
    }


def test_step8_permanent_contract_green():
    assert check_repository()["status"] == "GREEN"


def test_step8_data_field_provenance_ready():
    result = router.build_source_freshness_audit({}, _detail())
    assert result["status"] == "READY"
    assert result["unit_of_work"] == "DATA_FIELD"
    assert result["no_source_loyalty"] is True
    assert result["violation_count"] == 0
    assert result["sources"]


def test_step8_fails_closed_on_material_fact_without_source():
    detail = _detail()
    detail["offense_research"]["away"]["metrics"]["points_per_game"]["source"] = ""
    result = router.build_source_freshness_audit({}, detail)
    assert result["status"] == "BLOCKED"
    assert result["violation_count"] >= 1


def test_step8_wraps_frozen_step7():
    assert "import cfb_top_picks_details_v3 as prior" in Path("cfb_top_picks_details_v4.py").read_text(encoding="utf-8")
    assert "import cfb_top_picks_page_v7 as prior" in Path("cfb_top_picks_page_v8.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step7 as prior" in Path("streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8.py").read_text(encoding="utf-8")
