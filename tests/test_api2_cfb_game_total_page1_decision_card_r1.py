from __future__ import annotations

from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[1]


def _game():
    return {
        "game_id": "g1",
        "identity_key": "g1",
        "away_team": "Iowa St.",
        "home_team": "Arizona",
        "away_team_slug": "iowa-st",
        "home_team_slug": "arizona",
        "kickoff_iso": "2026-10-25T00:30:00+00:00",
        "market_quotes": [{"sportsbook": "FanDuel", "total_line": 51.5, "over_price": -105, "under_price": -115}],
        "team_identity": {
            "away": {"logo_url": "https://assets.invalid/isu.svg", "fallback_monogram": "IS"},
            "home": {"logo_url": "https://assets.invalid/ari.svg", "fallback_monogram": "A"},
        },
        "market_consensus": {"status": "SINGLE_BOOK_ONLY", "consensus_line": 51.5, "books_reporting": 1},
        "line_movement": {"status": "OPENING_LINE_NOT_VERIFIED", "current_total": 51.5},
    }


def test_decision_payload_uses_frozen_model_distribution_not_market_probability(monkeypatch):
    api = importlib.import_module("sports_api.api.cfb_game_total_page1_decision_v1")
    monkeypatch.setattr(api.page1, "build_page1_payload", lambda **_: {"service": "Kyre Sports API", "selected_date": "2026-10-24", "games": [_game()]})
    raw = {
        "ready": True,
        "distribution_ready": True,
        "projected_combined_total": 54.0,
        "distribution": [
            {"total": 50, "probability": .20},
            {"total": 51, "probability": .18},
            {"total": 52, "probability": .22},
            {"total": 53, "probability": .18},
            {"total": 54, "probability": .22},
        ],
        "sportsbook_input_used": False,
        "market_probability_used": False,
    }
    final = {"ready": True, "forecast_ready": True, "projected_combined_total": 54.0, "grade": "B", "confidence": "MEDIUM"}
    monkeypatch.setattr(api.slate, "analyze_game", lambda game, day: {"raw": raw, "final": final})
    payload = api.build_decision_payload(game_date="2026-10-24", game_id="g1")
    assert payload["service"] == "Kyre Sports API"
    assert payload["projected_total"] == 54.0
    assert payload["market_total"] == 51.5
    assert payload["over_probability"] == .62
    assert payload["under_probability"] == .38
    assert payload["push_probability"] == 0.0
    assert payload["model_edge"] == 2.5
    assert payload["model_tilt"] == "OVER"
    assert payload["sportsbook_projection_weight"] == 0.0
    assert payload["probability_owner"] == "frozen_cfb_game_total_distribution"


def test_decision_payload_fails_soft_when_model_unavailable(monkeypatch):
    api = importlib.import_module("sports_api.api.cfb_game_total_page1_decision_v1")
    monkeypatch.setattr(api.page1, "build_page1_payload", lambda **_: {"service": "Kyre Sports API", "selected_date": "2026-10-24", "games": [_game()]})
    monkeypatch.setattr(api.slate, "analyze_game", lambda game, day: {"raw": {"ready": False}, "final": {"ready": False}})
    payload = api.build_decision_payload(game_date="2026-10-24", game_id="g1")
    assert payload["status"] == "MODEL_PENDING"
    assert payload["projected_total"] is None
    assert payload["over_probability"] is None
    assert payload["under_probability"] is None
    assert payload["model_tilt"] == "MODEL_PENDING"


def test_v6_decision_card_is_simple_logo_rich_and_model_first():
    page = ROOT / "cfb_game_total_page1_atier_v6.py"
    assert page.exists(), "V6 decision card successor is missing"
    source = page.read_text(encoding="utf-8")
    folded = "".join(source.split()).casefold()
    assert "kyreprojectedtotal" in folded
    assert "kyreo/uprobability" in folded
    assert "modeltilt" in folded
    assert "cfbgt6-team-logo" in source
    assert "@media(max-width:430px){.cfbgt6-team-logo{display:none" not in folded
    assert "openanalysis" in folded
    assert "team snapshot" not in source.casefold()
    assert "trends" not in source.casefold()
    assert "line lab" not in source.casefold()


def test_bootstrap_activates_v6_and_frozen_boundaries_remain():
    source = (ROOT / "cfb_game_total_page1_api_bootstrap_repair_r1.py").read_text(encoding="utf-8")
    assert "cfb_game_total_page1_atier_v6" in source
    assert "MAY_MODIFY_MODEL = False" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_PROBABILITY = False" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_api_entry_registers_additive_decision_router():
    source = (ROOT / "kyre_sports_api_vercel_v1.py").read_text(encoding="utf-8")
    assert "cfb_game_total_page1_decision_v1" in source
    assert "app.include_router(cfb_game_total_decision_router)" in source
