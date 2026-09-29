from __future__ import annotations

from devsystem.cfb_top_picks_research_v2_step2_logos_v1 import check_repository


def test_step2_lightweight_permanent_contract():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["required_real_logo_images"] == 20
    assert result["exact_identity_primary"] is True
    assert result["multi_source_fallback"] is True
    assert result["enrichment_after_ranking"] is True
    assert result["api2_protected"] is True
    assert result["ranking_math_changed"] is False
    assert result["probability_math_changed"] is False
