"""Regression tests for CFB O/U Clean Page V19 freshness activation."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v19 as page


def _game(identity="401858213", total=62.5):
    return {
        "identity_key": f"espn:{identity}",
        "game_id": identity,
        "away_team": "Florida A&M",
        "home_team": "Miami",
        "kickoff_et": "7:30 PM ET",
        "market_line_available": True,
        "market_identity_verified": True,
        "market_total": total,
        "market_sportsbook": "FanDuel",
        "market_status": "active",
        "market_updated_at_utc": "2026-09-10T04:50:00+00:00",
        "market_projection_weight": 0.0,
    }


def test_v19_is_additive_over_permanently_frozen_v18():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v18"
    assert page.ACTIVE_MARKET_ADAPTER == "cfb_over_under_market_adapter_v2"
    assert page.frozen_page.MODEL_VERSION.startswith("CFB O/U CLEAN PAGE V18")
    assert page.frozen_page.market_adapter.MODEL_VERSION.startswith(
        "CFB O/U MARKET ADAPTER V1"
    )


def test_v19_execution_context_uses_certified_v2_without_mutating_v18():
    assert page._RENDER_V19.__globals__["market_adapter"] is page.market_adapter
    assert page._market_caption.__globals__["market_adapter"] is page.market_adapter
    assert page._line_board.__globals__["market_adapter"] is page.market_adapter
    assert page.frozen_page.market_adapter is not page.market_adapter


def test_v19_market_caption_still_discloses_zero_projection_weight():
    html = page._market_caption(_game(), {"status": "GREEN"})
    assert "LIVE FANDUEL GAME TOTAL" in html
    assert "<b>62.5</b>" in html
    assert "projection weight <b>0%</b>" in html


def test_v19_replaces_only_active_page_marker(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    proxy = page._StreamlitV19Proxy()

    proxy.caption(
        "🟢 CFB O/U • CLEAN PAGE V18 ACTIVE • LIVE ODDS CONNECTED • "
        "FROZEN PROJECTION MATH PRESERVED"
    )
    proxy.caption("ordinary downstream caption")

    assert "CLEAN PAGE V19 ACTIVE" in seen[0]
    assert "FRESHNESS FIREWALL ACTIVE" in seen[0]
    assert "FROZEN PROJECTION MATH PRESERVED" in seen[0]
    assert seen[1] == "ordinary downstream caption"


def test_v19_adds_no_projection_formula():
    source = inspect.getsource(page)
    assert "cfb_over_under_market_adapter_v2 as market_adapter" in source
    assert "projection weight remains 0%" in source
    assert "project_matchup(" not in source
    assert "apply_to_raw(" not in source
    assert "analyze_game(" not in source


def test_v19_reuses_frozen_v18_render_contract():
    assert page._RENDER_V19.__code__ is page.frozen_page.render_over_under_hub.__code__
    assert page._market_caption.__code__ is page.frozen_page._market_caption.__code__
    assert page._line_board.__code__ is page.frozen_page._line_board.__code__
