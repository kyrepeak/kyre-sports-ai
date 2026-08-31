from copy import deepcopy
from datetime import datetime, timezone

import pytest

from sports_api.mlb_step7d_total_api_integration_v1 import (
    API_CONNECTED,
    FALLBACK,
    MATCH_METHOD,
    build_total_api_state,
    enforce_total_api_freshness,
    total_api_context_for_result,
)


NOW = datetime(2026, 8, 31, 19, 0, 30, tzinfo=timezone.utc)


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


def payload(*games, collected_at="2026-08-31T19:00:00+00:00"):
    return {
        "data_type": "mlb_live_odds_api_response_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "collected_at_utc": collected_at,
        "games": list(games or [api_game()]),
    }


def game_result(game_id=880001):
    return {
        "game_pk": game_id,
        "away_team_id": 111,
        "home_team_id": 222,
        "away_team": "Away Club",
        "home_team": "Home Club",
        "projection": {"away_runs": 4.2, "home_runs": 3.9},
    }


def fresh_state(*games):
    state = build_total_api_state(payload(*(games or (api_game(),))))
    return enforce_total_api_freshness(state, as_of_utc=NOW)


def test_healthy_payload_exposes_exact_game_total_context_only():
    state = fresh_state(api_game())
    assert state["integration_status"] == API_CONNECTED
    assert state["api_integration_active"] is True
    assert state["match_method"] == MATCH_METHOD
    assert state["fallback_matching_used"] is False
    assert state["feed_fresh"] is True
    assert state["snapshot_age_seconds"] == 30.0
    assert state["usable_game_total_game_count"] == 1
    context = state["contexts_by_game_id"][880001]
    assert context["line"] == 8.5
    assert context["over_odds"] == -105
    assert context["under_odds"] == -115


def test_contexts_are_keyed_by_official_id_not_api_order():
    state = fresh_state(api_game(880002), api_game(880001))
    assert sorted(state["contexts_by_game_id"]) == [880001, 880002]
    assert total_api_context_for_result(game_result(880001), state)["official_game_id"] == 880001


def test_result_receives_complete_fanduel_total_market():
    context = total_api_context_for_result(game_result(), fresh_state())
    assert context["live_fanduel_total_line"] == 8.5
    assert context["live_fanduel_over_odds"] == -105
    assert context["live_fanduel_under_odds"] == -115


def test_result_is_never_mutated_by_live_total_context():
    state = fresh_state()
    result = game_result()
    before = deepcopy(result)
    context = total_api_context_for_result(result, state)
    assert context["live_fanduel_total_line"] == 8.5
    assert result == before


def test_wrong_official_game_id_never_attaches_even_if_names_would_match():
    state = fresh_state(api_game(880001))
    result = game_result(880099)
    result["away_team"] = "Away Club"
    result["home_team"] = "Home Club"
    assert total_api_context_for_result(result, state) is None


def test_missing_result_game_id_never_attaches():
    result = game_result()
    result["game_pk"] = None
    assert total_api_context_for_result(result, fresh_state()) is None


def test_duplicate_official_game_id_fails_closed():
    state = enforce_total_api_freshness(
        build_total_api_state(payload(api_game(), api_game())),
        as_of_utc=NOW,
    )
    assert state["integration_status"] == FALLBACK
    assert state["api_integration_active"] is False
    assert "duplicate_official_game_id" in state["failures"]
    assert total_api_context_for_result(game_result(), state) is None


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
    state = enforce_total_api_freshness(build_total_api_state(body), as_of_utc=NOW)
    assert state["integration_status"] == FALLBACK
    assert failure in state["failures"]


def test_empty_slate_falls_back_without_fabricating_total_context():
    body = payload(api_game())
    body["games"] = []
    state = enforce_total_api_freshness(build_total_api_state(body), as_of_utc=NOW)
    assert state["integration_status"] == FALLBACK
    assert state["contexts_by_game_id"] == {}
    assert "empty_api_slate" in state["failures"]
    assert "no_usable_game_total_contexts" in state["failures"]


def test_non_list_games_falls_back():
    body = payload(api_game())
    body["games"] = {"not": "a list"}
    state = enforce_total_api_freshness(build_total_api_state(body), as_of_utc=NOW)
    assert state["integration_status"] == FALLBACK
    assert "games_not_list" in state["failures"]


@pytest.mark.parametrize("field", ["line", "over_odds", "under_odds"])
def test_missing_required_total_field_is_never_fabricated(field):
    game = api_game()
    game["markets"]["total"][field] = None
    state = enforce_total_api_freshness(build_total_api_state(payload(game)), as_of_utc=NOW)
    assert state["integration_status"] == FALLBACK
    assert state["contexts_by_game_id"] == {}
    assert state["unusable_game_ids"] == [880001]
    assert total_api_context_for_result(game_result(), state) is None


@pytest.mark.parametrize("bad", [True, float("nan"), 0, -1, "bad"])
def test_invalid_total_line_is_rejected(bad):
    game = api_game()
    game["markets"]["total"]["line"] = bad
    state = enforce_total_api_freshness(build_total_api_state(payload(game)), as_of_utc=NOW)
    assert state["integration_status"] == FALLBACK
    assert state["contexts_by_game_id"] == {}


@pytest.mark.parametrize("field", ["over_odds", "under_odds"])
@pytest.mark.parametrize("bad", [True, float("nan"), 0, 101.5])
def test_invalid_total_odds_are_rejected(field, bad):
    game = api_game()
    game["markets"]["total"][field] = bad
    state = enforce_total_api_freshness(build_total_api_state(payload(game)), as_of_utc=NOW)
    assert state["integration_status"] == FALLBACK
    assert state["contexts_by_game_id"] == {}


def test_one_unusable_book_row_does_not_poison_a_distinct_valid_exact_id():
    state = fresh_state(api_game(880001), api_game(880002, sportsbook="OtherBook"))
    assert state["integration_status"] == API_CONNECTED
    assert sorted(state["contexts_by_game_id"]) == [880001]
    assert state["unusable_game_ids"] == [880002]
    assert total_api_context_for_result(game_result(880001), state) is not None
    assert total_api_context_for_result(game_result(880002), state) is None


def test_invalid_official_id_fails_page_claim_closed():
    bad = api_game()
    bad["official_game_id"] = None
    state = fresh_state(api_game(880001), bad)
    assert state["integration_status"] == FALLBACK
    assert "invalid_official_game_id" in state["failures"]


def test_stale_snapshot_falls_back_at_runtime_boundary():
    state = build_total_api_state(payload(api_game(), collected_at="2026-08-31T18:58:00+00:00"))
    state = enforce_total_api_freshness(state, as_of_utc=NOW)
    assert state["integration_status"] == FALLBACK
    assert state["api_integration_active"] is False
    assert state["feed_fresh"] is False
    assert state["snapshot_age_seconds"] == 150.0
    assert "api_snapshot_stale" in state["failures"]
    assert total_api_context_for_result(game_result(), state) is None


@pytest.mark.parametrize("collected", [None, "", "not-a-time"])
def test_missing_or_unparseable_timestamp_falls_back(collected):
    state = build_total_api_state(payload(api_game(), collected_at=collected))
    state = enforce_total_api_freshness(state, as_of_utc=NOW)
    assert state["integration_status"] == FALLBACK
    assert state["feed_fresh"] is False
    assert "invalid_or_missing_collected_at_utc" in state["failures"]


def test_exactly_60_seconds_old_is_still_fresh():
    state = build_total_api_state(payload(api_game(), collected_at="2026-08-31T18:59:30+00:00"))
    state = enforce_total_api_freshness(state, as_of_utc=NOW)
    assert state["integration_status"] == API_CONNECTED
    assert state["feed_fresh"] is True
    assert state["snapshot_age_seconds"] == 60.0


def test_future_timestamp_clock_skew_never_creates_negative_age():
    state = build_total_api_state(payload(api_game(), collected_at="2026-08-31T19:01:00+00:00"))
    state = enforce_total_api_freshness(state, as_of_utc=NOW)
    assert state["integration_status"] == API_CONNECTED
    assert state["snapshot_age_seconds"] == 0.0


def test_invalid_freshness_parameters_raise_instead_of_silently_weakening_gate():
    state = build_total_api_state(payload(api_game()))
    with pytest.raises(ValueError):
        enforce_total_api_freshness(state, as_of_utc=NOW, max_age_seconds=-1)
    with pytest.raises(ValueError):
        enforce_total_api_freshness(state, as_of_utc="not-a-time")


def test_inputs_are_not_mutated():
    body = payload(api_game())
    result = game_result()
    body_before = deepcopy(body)
    result_before = deepcopy(result)
    state = enforce_total_api_freshness(build_total_api_state(body), as_of_utc=NOW)
    context = total_api_context_for_result(result, state)
    assert context is not None
    assert body == body_before
    assert result == result_before


def test_result_context_declares_display_only_and_protected_flags_clear():
    context = total_api_context_for_result(game_result(), fresh_state())
    assert context["display_only"] is True
    assert context["sportsbook_price_model_input"] is False
    for key in (
        "model_math_impact",
        "simulation_impact",
        "probability_impact",
        "history_adjustment_impact",
        "ranking_impact",
        "selection_impact",
        "fair_odds_impact",
        "production_exposure_impact",
        "wagering_impact",
        "durable_persistence",
        "wnba_impact",
    ):
        assert context[key] is False


def test_page_state_preserves_existing_presentation_and_no_protected_impact():
    state = fresh_state()
    assert state["preexisting_presentation_preserved"] is True
    assert state["sportsbook_price_model_input"] is False
    for key in (
        "model_math_impact",
        "simulation_impact",
        "probability_impact",
        "history_adjustment_impact",
        "ranking_impact",
        "selection_impact",
        "fair_odds_impact",
        "production_exposure_impact",
        "wagering_impact",
        "durable_persistence",
        "wnba_impact",
    ):
        assert state[key] is False
