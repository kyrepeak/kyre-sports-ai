from copy import deepcopy

import pytest

from sports_api.mlb_step7b_spread_api_integration_v1 import (
    API_CONNECTED,
    FALLBACK,
    MATCH_METHOD,
    build_spread_api_state,
    spread_api_context_for_result,
)


def api_game(game_id=880001, *, sportsbook="FanDuel"):
    return {
        "official_game_id": game_id,
        "sportsbook": sportsbook,
        "scheduled_start_utc": "2026-08-31T23:10:00+00:00",
        "source_event_id": f"fd-{game_id}",
        "away_team": {"name": "Away Club"},
        "home_team": {"name": "Home Club"},
        "fully_priced": True,
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


def payload(*games):
    return {
        "data_type": "mlb_live_odds_api_response_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "collected_at_utc": "2026-08-31T18:40:00+00:00",
        "games": list(games or [api_game()]),
    }


def spread_result(game_id=880001, *, side="away", line=None):
    away_id, home_id = 111, 222
    if line is None:
        line = 1.5 if side == "away" else -1.5
    return {
        "game_pk": game_id,
        "team_id": away_id if side == "away" else home_id,
        "away_team_id": away_id,
        "home_team_id": home_id,
        "team": "Selected Team",
        "line": line,
        "cover": 0.631,
        "fair_odds": "-171",
    }


def test_healthy_payload_exposes_exact_run_line_context_only():
    state = build_spread_api_state(payload(api_game()))
    assert state["integration_status"] == API_CONNECTED
    assert state["api_integration_active"] is True
    assert state["match_method"] == MATCH_METHOD
    assert state["fallback_matching_used"] is False
    assert state["usable_run_line_game_count"] == 1
    assert state["contexts_by_game_id"][880001]["away_line"] == 1.5
    assert state["contexts_by_game_id"][880001]["away_odds"] == -175
    assert state["contexts_by_game_id"][880001]["home_line"] == -1.5
    assert state["contexts_by_game_id"][880001]["home_odds"] == 145


def test_contexts_are_keyed_by_official_id_not_api_order():
    state = build_spread_api_state(payload(api_game(880002), api_game(880001)))
    assert sorted(state["contexts_by_game_id"]) == [880001, 880002]
    assert spread_api_context_for_result(spread_result(880001), state)["official_game_id"] == 880001


def test_away_result_selects_away_fanduel_side():
    state = build_spread_api_state(payload(api_game()))
    context = spread_api_context_for_result(spread_result(side="away"), state)
    assert context["selected_side"] == "away"
    assert context["live_fanduel_line"] == 1.5
    assert context["live_fanduel_odds"] == -175
    assert context["line_match"] is True


def test_home_result_selects_home_fanduel_side():
    state = build_spread_api_state(payload(api_game()))
    context = spread_api_context_for_result(spread_result(side="home"), state)
    assert context["selected_side"] == "home"
    assert context["live_fanduel_line"] == -1.5
    assert context["live_fanduel_odds"] == 145
    assert context["line_match"] is True


def test_live_line_move_is_reported_but_never_substituted():
    state = build_spread_api_state(payload(api_game()))
    result = spread_result(side="away", line=2.5)
    before = deepcopy(result)
    context = spread_api_context_for_result(result, state)
    assert context["model_selected_line"] == 2.5
    assert context["live_fanduel_line"] == 1.5
    assert context["line_match"] is False
    assert result == before


def test_wrong_official_game_id_never_attaches_even_if_names_would_match():
    state = build_spread_api_state(payload(api_game(880001)))
    result = spread_result(880099)
    result["team"] = "Away Club"
    assert spread_api_context_for_result(result, state) is None


def test_selected_team_must_resolve_to_model_away_or_home_identity():
    state = build_spread_api_state(payload(api_game()))
    result = spread_result()
    result["team_id"] = 999
    assert spread_api_context_for_result(result, state) is None


def test_duplicate_official_game_id_fails_closed():
    state = build_spread_api_state(payload(api_game(), api_game()))
    assert state["integration_status"] == FALLBACK
    assert state["api_integration_active"] is False
    assert "duplicate_official_game_id" in state["failures"]
    assert spread_api_context_for_result(spread_result(), state) is None


@pytest.mark.parametrize(
    ("field", "value", "failure"),
    [
        ("data_type", "wrong", "unexpected_api_data_type"),
        ("schema_version", 99, "unexpected_api_schema_version"),
        ("source", "OtherBook", "unexpected_api_source"),
    ],
)
def test_bad_top_level_api_contract_falls_back(field, value, failure):
    body = payload(api_game())
    body[field] = value
    state = build_spread_api_state(body)
    assert state["integration_status"] == FALLBACK
    assert failure in state["failures"]


def test_empty_slate_falls_back_without_fabricating_market_context():
    body = payload(api_game())
    body["games"] = []
    state = build_spread_api_state(body)
    assert state["integration_status"] == FALLBACK
    assert state["contexts_by_game_id"] == {}
    assert "empty_api_slate" in state["failures"]
    assert "no_usable_run_line_contexts" in state["failures"]


def test_non_list_games_falls_back():
    body = payload(api_game())
    body["games"] = {"not": "a list"}
    state = build_spread_api_state(body)
    assert state["integration_status"] == FALLBACK
    assert "games_not_list" in state["failures"]


@pytest.mark.parametrize("field", ["away_line", "away_odds", "home_line", "home_odds"])
def test_missing_required_run_line_value_is_never_fabricated(field):
    game = api_game()
    game["markets"]["run_line"][field] = None
    state = build_spread_api_state(payload(game))
    assert state["integration_status"] == FALLBACK
    assert state["contexts_by_game_id"] == {}
    assert state["unusable_game_ids"] == [880001]
    assert spread_api_context_for_result(spread_result(), state) is None


def test_one_unusable_book_row_does_not_poison_a_distinct_valid_exact_id():
    state = build_spread_api_state(
        payload(api_game(880001), api_game(880002, sportsbook="OtherBook"))
    )
    assert state["integration_status"] == API_CONNECTED
    assert sorted(state["contexts_by_game_id"]) == [880001]
    assert state["unusable_game_ids"] == [880002]
    assert spread_api_context_for_result(spread_result(880001), state) is not None
    assert spread_api_context_for_result(spread_result(880002), state) is None


def test_invalid_official_id_fails_page_claim_closed():
    bad = api_game()
    bad["official_game_id"] = None
    state = build_spread_api_state(payload(api_game(880001), bad))
    assert state["integration_status"] == FALLBACK
    assert "invalid_official_game_id" in state["failures"]


def test_boolean_and_nonfinite_market_values_are_rejected():
    for field, bad in (("away_line", True), ("away_odds", float("nan"))):
        game = api_game()
        game["markets"]["run_line"][field] = bad
        state = build_spread_api_state(payload(game))
        assert state["integration_status"] == FALLBACK
        assert state["contexts_by_game_id"] == {}


def test_inputs_are_not_mutated():
    body = payload(api_game())
    result = spread_result()
    body_before = deepcopy(body)
    result_before = deepcopy(result)
    state = build_spread_api_state(body)
    context = spread_api_context_for_result(result, state)
    assert context is not None
    assert body == body_before
    assert result == result_before


def test_result_context_declares_display_only_and_protected_flags_clear():
    state = build_spread_api_state(payload(api_game()))
    context = spread_api_context_for_result(spread_result(), state)
    assert context["display_only"] is True
    for key in (
        "model_math_impact",
        "simulation_impact",
        "probability_impact",
        "history_adjustment_impact",
        "ranking_impact",
        "selection_impact",
        "fair_odds_impact",
        "wagering_impact",
        "durable_persistence",
        "wnba_impact",
    ):
        assert context[key] is False


def test_page_state_declares_frozen_spread_fallback_and_no_protected_impact():
    state = build_spread_api_state(payload(api_game()))
    assert state["frozen_spread_fallback_preserved"] is True
    for key in (
        "model_math_impact",
        "simulation_impact",
        "probability_impact",
        "history_adjustment_impact",
        "ranking_impact",
        "selection_impact",
        "fair_odds_impact",
        "wagering_impact",
        "durable_persistence",
        "wnba_impact",
    ):
        assert state[key] is False
