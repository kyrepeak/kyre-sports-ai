from copy import deepcopy
from datetime import datetime, timedelta, timezone

from sports_api.mlb_step9a_live_game_state_api_contract_v1 import (
    API_CONNECTED,
    CONTEXT_DATA_TYPE,
    DATA_TYPE,
    DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
    FALLBACK,
    LIVE,
    MATCH_METHOD,
    PREGAME,
    PROTECTED_FALSE_FLAGS,
    build_live_game_state_api_state,
    enforce_live_game_state_api_freshness,
    live_game_state_for_official_game_id,
)

NOW = datetime(2026, 9, 1, 5, 55, 0, tzinfo=timezone.utc)


def _live_game(game_id=823340):
    return {
        "official_game_id": game_id,
        "status": "In Progress",
        "state": "LIVE",
        "away_team": "Pittsburgh Pirates",
        "home_team": "San Francisco Giants",
        "away_runs": 2,
        "home_runs": 3,
        "away_hits": 6,
        "home_hits": 7,
        "away_errors": 0,
        "home_errors": 1,
        "inning": "Top 7th",
        "inning_state": "Top",
        "balls": 1,
        "strikes": 2,
        "outs": 1,
        "batter_id": 694973,
        "batter": "DISPLAY BATTER",
        "pitcher_id": 657277,
        "pitcher": "DISPLAY PITCHER",
        "on_deck": "ON DECK",
        "in_hole": "IN HOLE",
        "runner_first_id": 700001,
        "first": "RUNNER ONE",
        "runner_second_id": None,
        "second": "Empty",
        "runner_third_id": 700003,
        "third": "RUNNER THREE",
        "last_play": "Called Strike",
        "last_pitch_desc": "Called Strike",
        "last_pitch_type": "Four-Seam Fastball",
        "last_pitch_speed": 96.4,
        "recent_plays": [
            {"Inning": "Top 7", "Play": "Called Strike", "Score": "2-3"},
        ],
    }


def _pregame_game(game_id=823341):
    return {
        "official_game_id": game_id,
        "status": "Scheduled",
        "state": "PREGAME",
        "away_team": "Away Club",
        "home_team": "Home Club",
        "away_runs": 0,
        "home_runs": 0,
        "recent_plays": [],
    }


def _payload(*games, collected_at=NOW):
    return {
        "data_type": "mlb_live_game_state_api_response_v1",
        "schema_version": 1,
        "source": "MLB Stats API",
        "collected_at_utc": collected_at.isoformat(),
        "games": list(games),
    }


def _fresh(payload):
    return enforce_live_game_state_api_freshness(
        build_live_game_state_api_state(payload),
        as_of_utc=NOW,
        max_age_seconds=DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
    )


def test_valid_live_game_context_uses_exact_official_game_id_only():
    state = _fresh(_payload(_live_game()))
    assert state["data_type"] == DATA_TYPE
    assert state["integration_status"] == API_CONNECTED
    assert state["api_integration_active"] is True
    assert state["feed_fresh"] is True
    assert state["match_method"] == MATCH_METHOD
    context = live_game_state_for_official_game_id(state, official_game_id=823340)
    assert context is not None
    assert context["data_type"] == CONTEXT_DATA_TYPE
    assert context["official_game_id"] == 823340
    assert context["state"] == LIVE
    assert context["away_runs"] == 2
    assert context["home_runs"] == 3
    assert context["batter_id"] == 694973
    assert context["pitcher_id"] == 657277
    assert context["match_method"] == MATCH_METHOD


def test_team_and_player_display_names_do_not_participate_in_identity():
    row = _live_game()
    row["away_team"] = "TOTALLY DIFFERENT DISPLAY AWAY"
    row["home_team"] = "TOTALLY DIFFERENT DISPLAY HOME"
    row["batter"] = "NOT THE REAL BATTER NAME"
    row["pitcher"] = "NOT THE REAL PITCHER NAME"
    state = _fresh(_payload(row))
    context = live_game_state_for_official_game_id(state, official_game_id=823340)
    assert context is not None
    assert context["away_team"] == "TOTALLY DIFFERENT DISPLAY AWAY"
    assert context["team_name_matching_used"] is False
    assert context["player_name_matching_used"] is False


def test_wrong_official_game_id_returns_no_context():
    state = _fresh(_payload(_live_game()))
    assert live_game_state_for_official_game_id(state, official_game_id=999999) is None


def test_duplicate_exact_official_game_id_fails_closed_globally():
    first = _live_game()
    second = _live_game()
    second["away_team"] = "Different Metadata"
    state = build_live_game_state_api_state(_payload(first, second))
    assert state["integration_status"] == FALLBACK
    assert state["api_integration_active"] is False
    assert "duplicate_exact_official_game_id" in state["failures"]


def test_invalid_unrelated_row_is_isolated_when_exact_rows_remain_unambiguous():
    invalid = _live_game("823342.0")
    state = _fresh(_payload(_live_game(), invalid))
    assert state["integration_status"] == API_CONNECTED
    assert state["usable_live_game_count"] == 1
    assert state["unusable_live_game_count"] == 1
    assert live_game_state_for_official_game_id(state, official_game_id=823340) is not None


def test_live_state_requires_inning_and_count_fields():
    row = _live_game()
    row.pop("outs")
    state = build_live_game_state_api_state(_payload(row))
    assert state["integration_status"] == FALLBACK
    assert state["usable_live_game_count"] == 0
    assert state["unusable_game_rows"][0]["reason"] == "live_state_missing_inning_or_count"


def test_pregame_state_does_not_fabricate_live_count_fields():
    state = _fresh(_payload(_pregame_game()))
    context = live_game_state_for_official_game_id(state, official_game_id=823341)
    assert context is not None
    assert context["state"] == PREGAME
    assert context["balls"] is None
    assert context["strikes"] is None
    assert context["outs"] is None
    assert context["inning"] is None


def test_stale_snapshot_fails_closed_and_exposes_no_context():
    payload = _payload(_live_game(), collected_at=NOW - timedelta(seconds=21))
    state = enforce_live_game_state_api_freshness(
        build_live_game_state_api_state(payload),
        as_of_utc=NOW,
        max_age_seconds=20,
    )
    assert state["integration_status"] == FALLBACK
    assert state["feed_fresh"] is False
    assert "api_snapshot_stale" in state["failures"]
    assert live_game_state_for_official_game_id(state, official_game_id=823340) is None


def test_unproven_freshness_never_exposes_context():
    state = build_live_game_state_api_state(_payload(_live_game()))
    assert state["integration_status"] == API_CONNECTED
    assert state["feed_fresh"] is None
    assert live_game_state_for_official_game_id(state, official_game_id=823340) is None


def test_snapshot_too_far_in_future_fails_closed():
    payload = _payload(_live_game(), collected_at=NOW + timedelta(seconds=6))
    state = enforce_live_game_state_api_freshness(
        build_live_game_state_api_state(payload),
        as_of_utc=NOW,
    )
    assert state["integration_status"] == FALLBACK
    assert state["feed_fresh"] is False
    assert "api_snapshot_from_future" in state["failures"]


def test_ascii_serialized_integer_ids_are_allowed():
    row = _live_game("823340")
    row["batter_id"] = "694973"
    row["pitcher_id"] = "657277"
    state = _fresh(_payload(row))
    context = live_game_state_for_official_game_id(state, official_game_id="823340")
    assert context is not None
    assert context["official_game_id"] == 823340
    assert context["batter_id"] == 694973


def test_fractional_bool_and_unicode_game_ids_are_rejected():
    bad_ids = (823340.0, True, "823340.0", "８２３３４０")
    for bad in bad_ids:
        state = build_live_game_state_api_state(_payload(_live_game(bad)))
        assert state["integration_status"] == FALLBACK
        assert state["usable_live_game_count"] == 0


def test_invalid_supplied_optional_player_id_rejects_only_that_row():
    bad = _live_game(823342)
    bad["pitcher_id"] = 657277.0
    state = _fresh(_payload(_live_game(), bad))
    assert state["integration_status"] == API_CONNECTED
    assert state["usable_live_game_count"] == 1
    assert state["unusable_live_game_count"] == 1


def test_builder_and_context_do_not_mutate_input_or_share_nested_recent_plays():
    payload = _payload(_live_game())
    before = deepcopy(payload)
    state = _fresh(payload)
    context = live_game_state_for_official_game_id(state, official_game_id=823340)
    assert payload == before
    assert context is not None
    context["recent_plays"][0]["Play"] = "MUTATED"
    context2 = live_game_state_for_official_game_id(state, official_game_id=823340)
    assert context2["recent_plays"][0]["Play"] == "Called Strike"


def test_tampered_identity_and_matching_flags_fail_closed():
    base = _fresh(_payload(_live_game()))
    for key, value in (
        ("match_method", "team_name_guess"),
        ("fallback_matching_used", True),
        ("team_name_matching_used", True),
        ("player_name_matching_used", True),
        ("fuzzy_matching_allowed", True),
        ("synthetic_game_id_allowed", True),
        ("unverified_game_id_allowed", True),
        ("sportsbook_price_model_input", True),
    ):
        state = deepcopy(base)
        state[key] = value
        assert live_game_state_for_official_game_id(state, official_game_id=823340) is None


def test_step9a_is_contract_only_and_preserves_all_protected_boundaries():
    state = build_live_game_state_api_state(_payload(_live_game()))
    assert state["production_endpoint_added"] is False
    assert state["live_state_collection_added"] is False
    assert state["preexisting_v19_live_model_preserved"] is True
    assert state["preexisting_direct_transport_preserved"] is True
    assert state["synthetic_game_id_allowed"] is False
    assert state["unverified_game_id_allowed"] is False
    assert state["team_name_matching_used"] is False
    assert state["player_name_matching_used"] is False
    assert state["fuzzy_matching_allowed"] is False
    for key in PROTECTED_FALSE_FLAGS:
        assert state[key] is False, key
