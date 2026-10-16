from __future__ import annotations

import cfb_game_total_page2_step7_line_lab_best_bet_v1 as step7
import cfb_game_total_page2_step8_final_runtime_v1 as runtime


def _raw(*, projected: float = 58.0, distribution_ready: bool = True):
    return {
        "projected_combined_total": projected,
        "distribution_ready": distribution_ready,
        "distribution": [
            {"total": 50, "probability": 0.20},
            {"total": 55, "probability": 0.30},
            {"total": 60, "probability": 0.50},
        ],
    }


def _final(*, forecast_ready: bool = True, projected: float = 58.0):
    return {
        "ready": True,
        "forecast_ready": forecast_ready,
        "betting_pick_active": False,
        "projected_combined_total": projected,
        "grade": "A",
        "confidence": "HIGH",
        "forecast_strength": 0.84,
    }


def _game(line=54.5):
    return {
        "market_total": line,
        "verified_market_total": line,
        "market_identity_verified": True,
        "market_projection_weight": 0.0,
    }


def test_step6_qualified_forecast_uses_stronger_frozen_distribution_side():
    rec = runtime._recommendation(_raw(), _final(), _game())
    assert rec["side"] == "OVER"
    assert rec["line"] == 54.5
    assert rec["probability"] == "80.0%"
    assert rec["expected_total"] == 58.0
    assert rec["edge"] == 3.5
    assert rec["confidence"] == "A"
    assert "distribution" in rec["rationale"].lower()


def test_step6_projection_direction_disagreement_fails_closed():
    rec = runtime._recommendation(
        _raw(projected=52.0),
        _final(projected=52.0),
        _game(),
    )
    assert rec["side"] == "NO BET"
    assert rec["probability"] is None


def test_step6_unqualified_or_missing_evidence_fails_closed():
    assert runtime._recommendation(_raw(), _final(forecast_ready=False), _game())["side"] == "NO BET"
    assert runtime._recommendation(_raw(distribution_ready=False), _final(), _game())["side"] == "NO BET"
    assert runtime._recommendation(_raw(), _final(), _game(line=None))["side"] == "NO BET"


def test_step6_stage4_line_lab_can_render_without_best_bet():
    assert hasattr(step7, "build_line_lab_html")
    html = step7.build_line_lab_html(
        line_scenarios=[
            {"line": 51.5, "over_probability": "82.0%", "under_probability": "18.0%"},
            {"line": 54.5, "over_probability": "80.0%", "under_probability": "20.0%"},
            {"line": 57.5, "over_probability": "50.0%", "under_probability": "50.0%"},
        ],
        selected_line=54.5,
    )
    assert "Stage 4 • Line Lab" in html
    assert 'id="gtp2-best-bet"' not in html
    # Backward-compatible combined renderer remains available for frozen callers.
    combined = step7.build_line_lab_best_bet_html(
        line_scenarios=[], selected_line=54.5, recommendation={"side": "NO BET"}
    )
    assert 'id="gtp2-best-bet"' in combined


def test_step6_page2_body_has_separate_stage5_best_bet_after_line_lab():
    payload = {
        "identity": {"away": {"team": "Away"}, "home": {"team": "Home"}},
        "away": {},
        "home": {},
        "display_game": _game(),
        "raw": _raw(),
        "final": _final(),
    }
    html = runtime.build_page2_body_html(payload)
    assert 'data-testid="gtp2s9-best-bet"' in html
    assert "Stage 5 • Best Bet" in html
    assert html.index('data-testid="gtp2s7-line-lab"') < html.index('data-testid="gtp2s9-best-bet"')
    assert "OVER" in html


def test_step6_keeps_frozen_safety_boundaries():
    assert runtime.MAY_MODIFY_MODEL is False
    assert runtime.MAY_MODIFY_PROJECTION is False
    assert runtime.MAY_MODIFY_PROBABILITY is False
    assert runtime.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert runtime.NETWORK_CALLS_ADDED == 0
    assert runtime.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
