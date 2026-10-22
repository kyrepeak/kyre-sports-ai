from pathlib import Path

from universal_runtime_v5_state import RuntimeRoute


def test_runtime_routes_only_cfb_top_picks_to_v16():
    import streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v1 as runtime
    adapter = runtime.resolve_destination(RuntimeRoute("cfb", "top-picks", {}, 1, "tap"))
    assert adapter.route_key == ("cfb", "top-picks")
    assert adapter.source_version == runtime.MODEL_VERSION
    assert adapter.loader().MODEL_VERSION.startswith("CFB TOP PICKS V16")


def test_page1_handoff_carries_exact_candidate_identity():
    import cfb_top_picks_page_v16 as page
    href = page._page1_handoff({"candidate_id": "g1", "selected_date": "2026-10-22"}, "game-pick")
    assert "top_pick_id=g1" in href
    assert "top_pick_kind=game-pick" in href
    assert "top_pick_date=2026-10-22" in href


def test_api_resolves_exact_frozen_page1_candidate(monkeypatch):
    import sports_api.api.cfb_top_picks_page2_v1 as api
    monkeypatch.setattr(api.page1_v4, "build_page1_payload", lambda game_date=None, limit=10: {
        "schema_version": "v4", "selected_date": "2026-10-22",
        "game_picks": [{"candidate_id": "g1", "event_id": "e1", "probability": .71}],
        "player_props": []})
    out = api.resolve_candidate("g1", "game-pick", "2026-10-22")
    assert out["status"] == "READY"
    assert out["selection_snapshot"]["candidate_id"] == "g1"
    assert out["selection_snapshot"]["selected_date"] == "2026-10-22"


def test_candidate_tamper_fails_closed(monkeypatch):
    import sports_api.api.cfb_top_picks_page2_v1 as api
    monkeypatch.setattr(api.page1_v4, "build_page1_payload", lambda game_date=None, limit=10: {
        "schema_version": "v4", "selected_date": "2026-10-22", "game_picks": [], "player_props": []})
    assert api.resolve_candidate("made-up", "game-pick", "2026-10-22")["status"] == "IDENTITY_UNAVAILABLE"


def test_model_market_separation_and_zero_preservation():
    import sports_api.api.cfb_top_picks_page2_v1 as api
    assert api.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert api._n(0) == 0.0
    assert set(api.FORBIDDEN_PROVIDERS) == {"SGO", "ESPN", "ESPN BET"}
    out = api._decision({"market_type": "MONEYLINE", "probability": .70, "american_odds": -200}, {})
    rows = out["line_lab"]["scenarios"]
    assert len({row["model_probability"] for row in rows}) == 1
    assert len({row["implied_probability"] for row in rows}) > 1


def test_ui_contains_deep_page2_modules_without_raw_none():
    import cfb_top_picks_page_v16 as page
    payload = {
        "selection_snapshot": {"kind": "game-pick", "candidate_id": "g1", "selected_date": "2026-10-22", "away_team": "East Carolina", "home_team": "Memphis", "market_type": "MONEYLINE", "selection": "Memphis ML", "sportsbook": "FanDuel", "american_odds": -200, "probability": .70},
        "kyre_verdict": {"status": "READY", "outcome_confidence": .70, "market_implied_probability": .667, "market_value_edge": .033, "model_fair_price": -233, "selected_price": -200, "verdict": "BETTABLE EDGE"},
        "line_lab": {"status": "READY", "lab_type": "PRICE", "scenarios": [{"american_odds": -200, "implied_probability": .667, "model_probability": .70, "market_value_edge": .033}]},
        "projection": {"status": "PARTIAL", "selected_probability": .70},
        "drivers": {"status": "DATA_UNAVAILABLE", "reason": "Verified data unavailable."},
        "market_board": {"status": "READY", "quotes": [{"sportsbook": "FanDuel", "side": "HOME", "american_odds": -200}]},
        "risks": {"status": "READY", "items": []}, "flip_conditions": {"status": "READY", "items": []},
        "sources": {"status": "READY", "modules": {"projection": "PARTIAL", "market_board": "READY"}},
    }
    html = page.render_page2_html(payload)
    for text in ("KYRE VERDICT", "WHY THIS PICK", "LIVE MARKET BOARD", "SOURCE + FRESHNESS AUDIT", "Back to Top Picks"):
        assert text in html
    assert ">None<" not in html


def test_production_registration_preserves_frozen_lineage_and_nfl_routes():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text()
    gateway = (root / "kyre_sports_api_vercel_v1.py").read_text()
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v2" in app
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v3" in app
    assert "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v1" in app
    assert "app.include_router(cfb_top_picks_page2_router)" in gateway
    assert '"nfl_passing_yards_slate": True' in gateway
