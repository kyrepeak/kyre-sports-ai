from pathlib import Path

from sports_api.mlb_step7d_total_api_integration_v1 import (
    API_CONNECTED,
    build_total_api_state,
    enforce_total_api_freshness,
    total_api_context_for_result,
)


def _payload(collected_at="2026-08-31T19:00:00+00:00"):
    return {
        "data_type": "mlb_live_odds_api_response_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "collected_at_utc": collected_at,
        "games": [
            {
                "official_game_id": 880001,
                "sportsbook": "FanDuel",
                "scheduled_start_utc": "2026-08-31T23:10:00+00:00",
                "source_event_id": "fd-880001",
                "away_team": {"name": "Away Club"},
                "home_team": {"name": "Home Club"},
                "markets": {
                    "moneyline": {"away_odds": 120, "home_odds": -140},
                    "run_line": {
                        "away_line": 1.5,
                        "away_odds": -175,
                        "home_line": -1.5,
                        "home_odds": 145,
                    },
                    "total": {"line": 8.5, "over_odds": -105, "under_odds": -115},
                },
            }
        ],
    }


def test_total_context_requires_explicitly_proven_fresh_state():
    raw = build_total_api_state(_payload(collected_at="2020-01-01T00:00:00+00:00"))
    assert raw["integration_status"] == API_CONNECTED
    assert raw["api_integration_active"] is True
    assert raw["feed_fresh"] is None
    assert total_api_context_for_result({"game_pk": 880001}, raw) is None


def test_freshness_enforcement_unlocks_only_fresh_exact_id_context():
    raw = build_total_api_state(_payload())
    fresh = enforce_total_api_freshness(
        raw,
        as_of_utc="2026-08-31T19:00:30+00:00",
        max_age_seconds=60,
    )
    context = total_api_context_for_result({"game_pk": 880001}, fresh)
    assert fresh["feed_fresh"] is True
    assert context is not None
    assert context["official_game_id"] == 880001
    assert context["live_fanduel_total_line"] == 8.5
    assert context["live_fanduel_over_odds"] == -105
    assert context["live_fanduel_under_odds"] == -115
    assert context["display_only"] is True
    assert context["sportsbook_price_model_input"] is False


def test_v174_wrapper_is_presentation_only_over_frozen_v173():
    text = Path("mlb_totals_hub_v174.py").read_text()
    required = (
        "import mlb_totals_hub_v173 as prior",
        "enforce_total_api_freshness(build_total_api_state(response.json()))",
        "total_api_context_for_result(result, state)",
        "v171 = prior.base.base",
        "frozen_cards = v171._render_ou_cards",
        "v171._render_ou_cards = cards_with_api_context",
        "v171._render_ou_cards = frozen_cards",
        "return prior.render_totals_hub",
        '"sportsbook_price_model_input": False',
    )
    for token in required:
        assert token in text

    forbidden = (
        "_scan_ou_game =",
        "_default_market_lines =",
        "simulate_total(",
        "projected_total =",
        "fair_lean =",
        '"sportsbook_price_model_input": True',
    )
    for token in forbidden:
        assert token not in text


def test_app_installs_step7e_totals_alias_before_frozen_replay():
    text = Path("app.py").read_text()
    assert "def _install_mlb_totals_step7e_route()" in text
    assert 'import mlb_totals_hub_v174 as totals_v174' in text
    assert 'sys.modules["mlb_totals_hub_v173"] = totals_v174' in text
    assert 'import mlb_totals_hub_v173 as frozen_v173' in text
    assert 'sys.modules["mlb_totals_hub_v173"] = frozen_v173' in text
    call = "_STEP7E_MLB_TOTALS_ROUTE = _install_mlb_totals_step7e_route()"
    replay = "source = _load_frozen_pre_live_app()"
    assert call in text and replay in text
    assert text.index(call) < text.index(replay)


def test_step7e_does_not_rewire_frozen_totals_math_or_line_sync_modules():
    app_text = Path("app.py").read_text()
    wrapper_text = Path("mlb_totals_hub_v174.py").read_text()
    assert "totals_hub_v171" not in app_text
    assert "totals_hub_v172" not in app_text
    assert "_default_market_lines" not in wrapper_text
    assert "_scan_ou_game" not in wrapper_text
    assert "sportsbook totals do not drive" not in wrapper_text.lower() or "never substituted" in wrapper_text.lower()
