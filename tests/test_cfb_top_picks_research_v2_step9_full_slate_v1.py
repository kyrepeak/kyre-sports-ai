from __future__ import annotations

from pathlib import Path

import cfb_top_picks_page_v9 as page
import cfb_top_picks_source_router_v2 as router
from devsystem.cfb_top_picks_research_v2_step9_full_slate_v1 import check_repository


def _row():
    return {
        "rank": 1, "event_id": "401234567",
        "away": "Away State", "away_abbr": "AWY", "away_team_id": "1",
        "away_logo_url": "https://example.com/away.png", "away_logo_provider": "test",
        "home": "Home Tech", "home_abbr": "HME", "home_team_id": "2",
        "home_logo_url": "https://example.com/home.png", "home_logo_provider": "test",
        "time": "Sat, 12:00 PM", "network": "ESPN",
        "market": "MONEYLINE", "pick": "Away State", "odds": "-140",
        "probability": 65, "probability_value": .65, "reliability": .9,
        "toughness": 3, "toughness_label": "Medium", "source": "ESPN odds market • Kyre Moneyline model",
        "logo_identity_ready": True,
    }


def test_step9_permanent_contract_green():
    assert check_repository()["status"] == "GREEN"


def test_step9_final_page_removes_obsolete_audit_footer():
    row = _row()
    detail = page._loading_detail(row)
    html = page._detail_card(row, detail)
    assert '<div class="tp4-audit">' not in html
    assert "&lt;div class=&quot;tp4-audit" not in html


def test_step9_history_attempt_alias_closes_nonhistory_provenance_gap():
    detail = {
        "history_status": "SOURCE_CONFLICT_REVIEW",
        "history_observed_at": "2026-09-30T06:00:00+00:00",
        "sources_attempted": [
            {"source": "ESPN", "observed_at": "2026-09-30T06:00:00+00:00"},
            {"source": "Winsipedia", "observed_at": "2026-09-30T06:00:00+00:00"},
        ],
    }
    result = router.build_source_freshness_audit({}, detail)
    assert result["history_terminal"] is True
    assert result["violation_count"] == 0
    assert result["status"] == "READY"


def test_step9_wraps_frozen_step8():
    assert "import cfb_top_picks_details_v4 as prior" in Path("cfb_top_picks_details_v5.py").read_text(encoding="utf-8")
    assert "import cfb_top_picks_page_v8 as prior" in Path("cfb_top_picks_page_v9.py").read_text(encoding="utf-8")
    router_text = Path("streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_wnba_pra_speed_v3_step4 as current_parent" in router_text
    assert "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8 as cfb_step8_parent" in router_text
    assert "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step7 as cfb_step7_parent" in router_text
    assert "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step6 as cfb_step6_parent" in router_text
    assert "def _page_owner_chain()" in router_text
    assert "cfb_step8_parent, cfb_step7_parent, cfb_step6_parent" in router_text
    assert "owner.TOP_PICKS_PAGE = TOP_PICKS_PAGE" in router_text
    assert "zip(reversed(owners), reversed(original_pages))" in router_text

def test_step9_fair_model_price_has_truthful_sportsbook_unavailable_state():
    from devsystem.cfb_top_picks_research_v2_step9_full_slate_cert_v1 import (
        FAIR_PRICE_NO_SPORTSBOOK,
        _sportsbook,
    )

    row = {
        "source": "Kyre Moneyline model • fair price",
        "odds": "Fair +125",
    }
    assert _sportsbook(row) == FAIR_PRICE_NO_SPORTSBOOK
    assert "FanDuel" not in _sportsbook(row)
    assert "ESPN" not in _sportsbook(row)

