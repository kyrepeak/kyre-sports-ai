from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

RUNTIME = "cfb_game_total_page2_market_completeness_r1"
ROUTER = "streamlit_memory_lazy_router_monster_cfb_market_completeness_r1"


def _quote():
    return {
        "book": "FanDuel",
        "raw_book": "FanDuel",
        "away_moneyline": 125.0,
        "home_moneyline": -145.0,
        "away_spread": 3.0,
        "home_spread": -3.0,
        "total": 47.5,
        "observed_at_utc": "2026-10-18T00:00:00+00:00",
        "transports": ["action_network"],
    }


def _load_runtime(monkeypatch, *, quote=None, quotes=None):
    rendered: list[str] = []
    fake_st = types.SimpleNamespace(markdown=lambda html, **kwargs: rendered.append(str(html)))

    fake_prior = types.ModuleType("cfb_game_total_page2_visual_cleanup_r4")
    fake_prior.MARKET = "Game Total"
    fake_prior.render_game_total_hub = lambda *args, **kwargs: "rendered"
    fake_prior.build_stage7_clean_html = lambda *args, **kwargs: "stage7"

    fake_market_truth = types.SimpleNamespace(
        select_featured_book_quote=lambda observations: (quote, quotes or {})
    )
    fake_base = types.ModuleType("cfb_game_total_page2_complete_repair_r1")
    fake_base.market_truth = fake_market_truth
    fake_base._apply_featured_market = lambda display_game, selected_game: dict(display_game)
    fake_base._render_source_strip = lambda display_game: rendered.append("base-source-strip")

    fake_router = types.ModuleType("streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1")
    fake_router.PAGE1_NATIVE_ROUTE = "old-route"
    fake_router._ROUTE_POINTER_LOCK = types.SimpleNamespace()
    fake_router._render_page1_in_shared_shell = lambda: "shared-shell"

    monkeypatch.setitem(sys.modules, "streamlit", fake_st)
    monkeypatch.setitem(sys.modules, "cfb_game_total_page2_visual_cleanup_r4", fake_prior)
    monkeypatch.setitem(sys.modules, "cfb_game_total_page2_complete_repair_r1", fake_base)
    monkeypatch.setitem(sys.modules, "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1", fake_router)
    sys.modules.pop(RUNTIME, None)
    module = importlib.import_module(RUNTIME)
    return module, fake_base, rendered


def test_same_book_complete_quote_populates_all_page2_market_fields(monkeypatch):
    quote = _quote()
    module, _, _ = _load_runtime(monkeypatch, quote=quote, quotes={"FanDuel": quote})
    out = module._apply_complete_market({"event_id": "401"}, {"market_observations": [{"x": 1}]})
    assert out["event_id"] == "401"
    assert out["market_sportsbook"] == "FanDuel"
    assert out["away_moneyline"] == 125.0
    assert out["home_moneyline"] == -145.0
    assert out["away_spread"] == 3.0
    assert out["home_spread"] == -3.0
    assert out["market_total"] == 47.5
    assert out["market_quote_count"] == 1
    assert out["market_projection_weight"] == 0.0
    assert out["market_may_modify_projection"] is False


def test_no_complete_same_book_quote_does_not_mix_partial_books(monkeypatch):
    module, _, _ = _load_runtime(monkeypatch, quote=None, quotes={})
    original = {"event_id": "402", "market_total": 51.5}
    out = module._apply_complete_market(original, {"market_observations": [{"sportsbook": "A"}, {"sportsbook": "B"}]})
    assert out == original
    assert "away_moneyline" not in out
    assert "home_spread" not in out


def test_incomplete_snapshot_masks_inherited_partial_market_values(monkeypatch):
    module, _, _ = _load_runtime(monkeypatch, quote=None, quotes={})
    html = module._market_snapshot_html(
        {
            "event_id": "402",
            "market_sportsbook": "PartialBook",
            "away_moneyline": 125.0,
            "home_moneyline": -145.0,
            "away_spread": 3.0,
            "home_spread": -3.0,
            "market_total": 51.5,
        }
    )
    assert "PartialBook" not in html
    assert "+125" not in html
    assert "-145" not in html
    assert "+3" not in html
    assert "-3" not in html
    assert "51.5" not in html
    assert html.count("Unavailable") == 5
    assert "No complete named book" in html


def test_market_snapshot_renders_ml_spread_total_from_one_verified_book(monkeypatch):
    quote = _quote()
    module, _, rendered = _load_runtime(monkeypatch, quote=quote, quotes={"FanDuel": quote})
    game = module._apply_complete_market({"event_id": "403"}, {"market_observations": [{"x": 1}]})
    module._render_source_strip_with_market_snapshot(game)
    html = "\n".join(rendered)
    assert "base-source-strip" in html
    assert 'data-testid="gtp2-market-complete-r1"' in html
    assert "FanDuel" in html
    assert "+125" in html
    assert "-145" in html
    assert "+3" in html
    assert "-3" in html
    assert "47.5" in html


def test_runtime_restores_frozen_base_hooks_after_render(monkeypatch):
    quote = _quote()
    module, base, _ = _load_runtime(monkeypatch, quote=quote, quotes={"FanDuel": quote})
    original_apply = base._apply_featured_market
    original_strip = base._render_source_strip
    assert module.render_game_total_hub() == "rendered"
    assert base._apply_featured_market is original_apply
    assert base._render_source_strip is original_strip


def _load_router(monkeypatch, *, is_cfb=True):
    calls: list[str] = []
    seen_runtime: list[str] = []
    fast_switch = types.SimpleNamespace(CFB_PAGE2_RUNTIME="cfb_game_total_page2_visual_cleanup_r4")

    fake_cfb = types.ModuleType("streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1")
    fake_cfb.prior = fast_switch

    fake_prior = types.ModuleType("streamlit_memory_lazy_router_monster_cfb_v4_route_ownership_r1")
    fake_prior._is_cfb_game_total_route = lambda: is_cfb
    fake_prior.record_bootstrap_import_ms = lambda value: calls.append(f"bootstrap:{value}")

    def _render():
        seen_runtime.append(fast_switch.CFB_PAGE2_RUNTIME)
        calls.append("prior")
        return "prior"

    fake_prior.render_app = _render

    monkeypatch.setitem(sys.modules, "streamlit_memory_lazy_router_monster_cfb_v4_route_ownership_r1", fake_prior)
    monkeypatch.setitem(sys.modules, "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1", fake_cfb)
    sys.modules.pop(ROUTER, None)
    module = importlib.import_module(ROUTER)
    return module, fake_cfb, calls, seen_runtime


def test_monster_router_activates_successor_only_for_cfb_and_restores(monkeypatch):
    module, cfb, calls, seen_runtime = _load_router(monkeypatch, is_cfb=True)
    old = cfb.prior.CFB_PAGE2_RUNTIME
    assert module.render_app() == "prior"
    assert calls == ["prior"]
    assert seen_runtime == [module.CFB_PAGE2_RUNTIME]
    assert cfb.prior.CFB_PAGE2_RUNTIME == old


def test_non_cfb_route_does_not_touch_page2_runtime(monkeypatch):
    module, cfb, calls, seen_runtime = _load_router(monkeypatch, is_cfb=False)
    old = cfb.prior.CFB_PAGE2_RUNTIME
    assert module.render_app() == "prior"
    assert calls == ["prior"]
    assert seen_runtime == [old]
    assert cfb.prior.CFB_PAGE2_RUNTIME == old


def test_app_activates_market_completeness_successor():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "streamlit_memory_lazy_router_monster_cfb_market_completeness_r1" in source
    active = source.split("_LEGACY_ROUTER_IMPORT_V4 =", 1)[1].split("_legacy_router_import_count", 1)[0]
    assert "streamlit_memory_lazy_router_monster_cfb_v4_route_ownership_r1" not in active
