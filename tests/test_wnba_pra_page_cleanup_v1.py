from __future__ import annotations

from pathlib import Path

import wnba_pra_page_cleanup_v1 as cleanup
import wnba_pra_hub_v24 as v24
import wnba_pra_hub_v28 as v28
import wnba_pra_market_v29 as market
import wnba_pra_matchup_v30 as matchup
import wnba_sportsgameodds_v1 as legacy_market


ROOT = Path(__file__).resolve().parents[1]


def test_step2_cleanup_contract_is_presentation_only_and_protects_frozen_products():
    contract = cleanup.CLEANUP_CONTRACT
    assert contract["scope"] == "presentation_only"
    assert contract["hero_cleaned"] is True
    assert contract["off_day_zero_wall_removed"] is True
    assert contract["raw_diagnostics_collapsed"] is True
    assert contract["provider_secret_message_removed"] is True
    for key in (
        "api_ownership_changed",
        "projection_math_changed",
        "market_math_changed",
        "ranking_changed",
        "qualification_changed",
        "monte_carlo_changed",
        "nfl_changed",
        "mlb_changed",
    ):
        assert contract[key] is False


def test_step2_cleanup_patches_only_presentation_owners():
    result = cleanup.begin_render()
    hub = v28.v27.v25.v24.v23.hub

    assert result["installed"] is True
    assert hub._hero is cleanup._clean_hero
    assert hub._slate_tab is cleanup._clean_slate_tab
    assert legacy_market.render_market_panel is cleanup._clean_market_panel
    assert market.render_pra_market_grade is cleanup._clean_market_grade
    assert matchup.render_matchup_grade is cleanup._clean_matchup_grade

    # The schedule/data functions still come from their existing owners.
    assert v24.schedule_diagnostics is not cleanup._clean_hero
    assert market.grade_pra_markets is not cleanup._clean_market_grade
    assert matchup.grade_matchup_pra is not cleanup._clean_matchup_grade


def test_step2_active_compatibility_route_forwards_to_clean_wrapper():
    source = (ROOT / "wnba_pra_hub_v3612.py").read_text(encoding="utf-8")
    assert "import wnba_pra_hub_v3614 as active" in source

    wrapper = (ROOT / "wnba_pra_hub_v3614.py").read_text(encoding="utf-8")
    assert wrapper.index("previous.api_market.install()") < wrapper.index("cleanup.begin_render()")
    assert wrapper.index("cleanup.begin_render()") < wrapper.index("previous.frozen.base.render_wnba_pra_hub")
    assert "with cleanup.presentation_scope():" in wrapper


def test_step2_cleanup_has_no_direct_provider_secret_or_cross_sport_product_imports():
    source = (ROOT / "wnba_pra_page_cleanup_v1.py").read_text(encoding="utf-8")
    assert "SPORTSGAMEODDS_API_KEY" not in source
    assert "requests.get(" not in source
    assert "import mlb_" not in source
    assert "import nfl_" not in source


def test_step2_technical_caption_filter_keeps_user_caption(monkeypatch):
    seen = []

    def fake_caption(body, *args, **kwargs):
        seen.append(str(body))

    monkeypatch.setattr(cleanup.st, "caption", fake_caption)
    with cleanup.presentation_scope():
        cleanup.st.caption("PRA V3.0 • Step 7 technical wrapper")
        cleanup.st.caption("Lineups are still pending for this slate.")

    assert seen == ["Lineups are still pending for this slate."]


def test_step2_markdown_rewrites_legacy_step_labels_without_touching_values(monkeypatch):
    seen = []

    def fake_markdown(body, *args, **kwargs):
        seen.append(str(body))

    monkeypatch.setattr(cleanup.st, "markdown", fake_markdown)
    with cleanup.presentation_scope():
        cleanup.st.markdown("🏆 V2.8 Minutes + Role PRA — Top 5 • STEP-5 PRA")

    assert seen == ["🏆 Top PRA Projections • PRA"]
