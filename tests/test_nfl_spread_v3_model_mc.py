from __future__ import annotations

import inspect

import nfl_spread_hub_v3 as page
import streamlit_memory_lazy_router_v134 as router


def _game(state: str = "pre") -> dict:
    return {
        "game_id": "401872931",
        "state": state,
        "season_type": "Regular Season",
        "tip_et": "8:15 PM ET",
        "venue": "Arrowhead Stadium",
        "broadcast": "ESPN / ABC",
        "away_team": "Denver Broncos",
        "away_abbr": "DEN",
        "away_record": "0-0",
        "away_logo": "https://example.com/den.png",
        "home_team": "Kansas City Chiefs",
        "home_abbr": "KC",
        "home_record": "0-0",
        "home_logo": "https://example.com/kc.png",
    }


def _market(ready: bool = True) -> dict:
    if not ready:
        return {
            "ready": False,
            "reason": "Market unavailable",
            "books": [],
            "projection_weight": 0.0,
        }
    return {
        "ready": True,
        "market_available": True,
        "official_event_id": "401872931",
        "projection_weight": 0.0,
        "books": [
            {
                "sportsbook": "FanDuel",
                "away_spread": 2.5,
                "away_price": -115,
                "home_spread": -2.5,
                "home_price": -105,
                "age_seconds": 4,
            }
        ],
    }


def _analytics() -> dict:
    return {
        "ready": True,
        "simulator_version": "NFL SPREAD MC V1 • DETERMINISTIC 5M",
        "model_version": "NFL SPREAD MODEL V1",
        "model_quality": "HIGH",
        "game_id": "401872931",
        "simulations": 5_000_000,
        "seed": 20260914,
        "projected_away_margin": -4.2,
        "projected_home_margin": 4.2,
        "parameter_se": 0.6,
        "residual_sd": 13.0,
        "predictive_sd": 13.0138,
        "simulated_away_margin_mean": -4.18,
        "simulated_away_margin_median": -4.0,
        "margin_quantiles": {
            "p05": -26.0,
            "p25": -13.0,
            "p50": -4.0,
            "p75": 5.0,
            "p95": 17.0,
        },
        "away_win_probability": 0.359,
        "home_win_probability": 0.611,
        "tie_probability": 0.030,
        "away_cover_probability": 0.472,
        "home_cover_probability": 0.498,
        "push_probability": 0.030,
        "away_win_mc_se": 0.00021,
        "away_cover_mc_se": 0.000223,
        "push_mc_se": 0.000076,
        "converged": True,
        "certified_run": True,
        "sportsbook_projection_influence": 0.0,
        "sportsbook_inputs_to_projection": [],
        "market_line_role": "settlement_only",
    }


def test_v3_contract_is_additive_over_frozen_v2_and_v1() -> None:
    assert page.FROZEN_PRESENTATION == "nfl_spread_hub_v2"
    assert page.FROZEN_TRANSPORT == "nfl_spread_hub_v1"
    assert page.PROJECTION_MODEL_ENABLED is True
    assert page.MONTE_CARLO_ENABLED is True
    assert page.CERTIFIED_SIMULATIONS == 5_000_000
    assert page.MARKET_LINE_ROLE == "settlement_only"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.RANKINGS_ENABLED is False
    assert page.STAKE_SIZING_ENABLED is False
    assert page.WAGER_ACTIONS_ENABLED is False


def test_v3_analytics_card_renders_fair_line_and_certified_mc() -> None:
    html = page._analytics_card(_game(), _market(), _analytics())

    assert "Denver Broncos @ Kansas City Chiefs" in html
    assert "5M CERTIFIED" in html
    assert "MODEL HIGH" in html
    assert "5,000,000 SIMS" in html
    assert "+4.2" in html
    assert "-4.2" in html
    assert "47.2%" in html
    assert "49.8%" in html
    assert "3.0%" in html
    assert "35.9%" in html
    assert "0.000223" in html
    assert "settlement only" in html
    assert "0.0% MARKET → MODEL" in html
    assert "no rankings, stake sizing, or wager actions" in html


def test_market_unavailable_keeps_independent_model_but_hides_cover_numbers() -> None:
    html = page._analytics_card(_game(), _market(False), _analytics())

    assert "5M CERTIFIED" in html
    assert "+4.2" in html
    assert "-4.2" in html
    assert "AWAY COVER" in html
    assert "HOME COVER" in html
    assert "PUSH" in html
    assert html.count("—") >= 3


def test_market_line_is_passed_only_as_post_projection_settlement_context(monkeypatch) -> None:
    captured: dict = {}

    def fake_cached(game: dict, day_str: str, market_away_spread: float | None) -> dict:
        captured["game_id"] = game["game_id"]
        captured["day_str"] = day_str
        captured["market_away_spread"] = market_away_spread
        result = _analytics()
        result["sportsbook_projection_influence"] = 0.0
        return result

    monkeypatch.setattr(page, "_cached_game_mc", fake_cached)
    result = page._analytics_for_game(_game(), _market(), "2026-09-14")

    assert result["ready"] is True
    assert captured == {
        "game_id": "401872931",
        "day_str": "2026-09-14",
        "market_away_spread": 2.5,
    }
    assert result["sportsbook_projection_influence"] == 0.0


def test_v3_firewall_fails_closed_on_contaminated_mc_result(monkeypatch) -> None:
    contaminated = _analytics()
    contaminated["sportsbook_projection_influence"] = 0.01

    monkeypatch.setattr(page, "_cached_game_mc", lambda *args, **kwargs: contaminated)
    result = page._analytics_for_game(_game(), _market(), "2026-09-14")

    assert result["ready"] is False
    assert result["runtime_stage"] == "sportsbook firewall"
    assert "firewall" in result["error"].lower()


def test_post_kickoff_game_never_runs_model_or_mc(monkeypatch) -> None:
    called = {"value": False}

    def should_not_run(*args, **kwargs):
        called["value"] = True
        raise AssertionError("Monte Carlo should not run after kickoff")

    monkeypatch.setattr(page, "_cached_game_mc", should_not_run)
    result = page._analytics_for_game(_game("in"), _market(), "2026-09-14")

    assert result["ready"] is False
    assert result["runtime_stage"] == "pregame gate"
    assert called["value"] is False


def test_render_flow_preserves_frozen_transport_and_v2_matchup_card() -> None:
    source = inspect.getsource(page.render_nfl_hub)

    assert "frozen.base.load_nfl_slate(day_str)" in source
    assert "frozen._fetch_markets(games)" in source
    assert "prior._matchup_card(game, market_state)" in source
    assert "_analytics_for_game(" in source
    assert "_analytics_card(game, market_state, analytics)" in source
    assert "fetch_event_market" not in source


def test_summary_reports_market_model_mc_and_firewall() -> None:
    html = page._summary_html(
        games=4,
        upcoming=4,
        market_ready=3,
        model_ready=4,
        mc_certified=4,
    )
    assert "3/4" in html
    assert html.count("4/4") == 2
    assert "0.0%" in html
    assert "sportsbook → projection" in html


def test_router_v134_is_additive_over_v133() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v133"
    assert router.ACTIVE_SPREAD_HUB == "nfl_spread_hub_v3"
    assert router.SPREAD_MARKET == "Spread"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.PROJECTION_MODEL_ENABLED is True
    assert router.MONTE_CARLO_ENABLED is True
    assert router.STAKE_SIZING_ENABLED is False
    assert router.WAGER_ACTIONS_ENABLED is False

    source = inspect.getsource(router.render_app)
    assert "prior.ACTIVE_SPREAD_HUB = ACTIVE_SPREAD_HUB" in source
    assert "return prior.render_app()" in source
    assert "prior.ACTIVE_SPREAD_HUB = original_active_hub" in source
