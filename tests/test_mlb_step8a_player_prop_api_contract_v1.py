from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from sports_api.mlb_step8a_player_prop_api_contract_v1 import (
    API_CONNECTED,
    FALLBACK,
    HITS_RUNS_RBI,
    MATCH_METHOD,
    PITCHER_STRIKEOUTS,
    PLAYER_HITS,
    SUPPORTED_MARKET_TYPES,
    build_player_prop_api_state,
    enforce_player_prop_api_freshness,
    player_prop_context_for_identity,
)


def _payload(*props, collected_at="2026-08-31T20:00:00Z"):
    return {
        "data_type": "mlb_player_prop_api_response_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "collected_at_utc": collected_at,
        "props": list(props),
    }


def _prop(
    *,
    game_id=777001,
    player_id=660001,
    player_name="Exact Player",
    market_type=PITCHER_STRIKEOUTS,
    line=5.5,
    over_odds=-115,
    under_odds=-105,
):
    return {
        "official_game_id": game_id,
        "official_player_id": player_id,
        "player_name": player_name,
        "market_type": market_type,
        "line": line,
        "over_odds": over_odds,
        "under_odds": under_odds,
        "sportsbook": "FanDuel",
        "source_event_id": f"fd-event-{game_id}",
        "source_market_id": f"fd-market-{game_id}-{player_id}-{market_type}",
    }


def _fresh(state):
    return enforce_player_prop_api_freshness(
        state,
        as_of_utc="2026-08-31T20:00:20Z",
        max_age_seconds=60,
    )


def test_supported_market_contract_is_exact_and_intentionally_small():
    assert SUPPORTED_MARKET_TYPES == {
        PITCHER_STRIKEOUTS,
        PLAYER_HITS,
        HITS_RUNS_RBI,
    }
    assert PITCHER_STRIKEOUTS == "pitcher_strikeouts"
    assert PLAYER_HITS == "player_hits"
    assert HITS_RUNS_RBI == "hits_runs_rbi"


def test_raw_state_never_exposes_context_until_freshness_is_proven():
    state = build_player_prop_api_state(_payload(_prop()))

    assert state["integration_status"] == API_CONNECTED
    assert state["api_integration_active"] is True
    assert state["feed_fresh"] is None
    assert state["match_method"] == MATCH_METHOD
    assert state["fallback_matching_used"] is False
    assert state["player_name_matching_used"] is False
    assert state["fuzzy_matching_allowed"] is False
    assert player_prop_context_for_identity(
        state,
        official_game_id=777001,
        official_player_id=660001,
        market_type=PITCHER_STRIKEOUTS,
    ) is None


def test_fresh_exact_identity_unlocks_context_and_preserves_prices_exactly():
    payload = _payload(
        _prop(
            game_id=777101,
            player_id=660101,
            market_type=PITCHER_STRIKEOUTS,
            line=6.5,
            over_odds=104,
            under_odds=-128,
        )
    )
    original = deepcopy(payload)
    state = _fresh(build_player_prop_api_state(payload))
    context = player_prop_context_for_identity(
        state,
        official_game_id=777101,
        official_player_id=660101,
        market_type=PITCHER_STRIKEOUTS,
    )

    assert payload == original
    assert state["feed_fresh"] is True
    assert state["snapshot_age_seconds"] == 20.0
    assert context is not None
    assert context["official_game_id"] == 777101
    assert context["official_player_id"] == 660101
    assert context["market_type"] == PITCHER_STRIKEOUTS
    assert context["line"] == 6.5
    assert context["over_odds"] == 104
    assert context["under_odds"] == -128
    assert context["match_method"] == MATCH_METHOD
    assert context["fallback_matching_used"] is False
    assert context["player_name_matching_used"] is False
    assert context["display_only"] is True
    for key in (
        "model_math_impact",
        "simulation_impact",
        "probability_impact",
        "history_adjustment_impact",
        "ranking_impact",
        "selection_impact",
        "fair_odds_impact",
        "sportsbook_price_model_input",
        "production_exposure_impact",
        "wagering_impact",
        "durable_persistence",
        "wnba_impact",
    ):
        assert context[key] is False


def test_player_name_is_metadata_only_and_cannot_select_an_identity():
    state = _fresh(
        build_player_prop_api_state(
            _payload(
                _prop(game_id=777201, player_id=660201, player_name="Same Name", market_type=PLAYER_HITS),
                _prop(game_id=777201, player_id=660202, player_name="Same Name", market_type=PLAYER_HITS),
            )
        )
    )

    first = player_prop_context_for_identity(
        state,
        official_game_id=777201,
        official_player_id=660201,
        market_type=PLAYER_HITS,
    )
    second = player_prop_context_for_identity(
        state,
        official_game_id=777201,
        official_player_id=660202,
        market_type=PLAYER_HITS,
    )
    wrong_id = player_prop_context_for_identity(
        state,
        official_game_id=777201,
        official_player_id=999999,
        market_type=PLAYER_HITS,
    )

    assert first and first["official_player_id"] == 660201
    assert second and second["official_player_id"] == 660202
    assert first["player_name"] == second["player_name"] == "Same Name"
    assert wrong_id is None


def test_market_type_is_part_of_exact_identity_not_a_fuzzy_fallback():
    state = _fresh(
        build_player_prop_api_state(
            _payload(
                _prop(game_id=777301, player_id=660301, market_type=PLAYER_HITS, line=1.5),
                _prop(game_id=777301, player_id=660301, market_type=HITS_RUNS_RBI, line=2.5),
            )
        )
    )

    hits = player_prop_context_for_identity(
        state,
        official_game_id=777301,
        official_player_id=660301,
        market_type=PLAYER_HITS,
    )
    hrrbi = player_prop_context_for_identity(
        state,
        official_game_id=777301,
        official_player_id=660301,
        market_type=HITS_RUNS_RBI,
    )
    unsupported = player_prop_context_for_identity(
        state,
        official_game_id=777301,
        official_player_id=660301,
        market_type="home_runs",
    )

    assert hits and hits["line"] == 1.5
    assert hrrbi and hrrbi["line"] == 2.5
    assert unsupported is None


def test_duplicate_exact_identity_fails_closed_globally():
    duplicate = _prop(game_id=777401, player_id=660401, market_type=PITCHER_STRIKEOUTS)
    state = build_player_prop_api_state(_payload(duplicate, deepcopy(duplicate)))

    assert state["integration_status"] == FALLBACK
    assert state["api_integration_active"] is False
    assert "duplicate_exact_prop_identity" in state["failures"]
    state = _fresh(state)
    assert state["feed_fresh"] is False
    assert player_prop_context_for_identity(
        state,
        official_game_id=777401,
        official_player_id=660401,
        market_type=PITCHER_STRIKEOUTS,
    ) is None


def test_incomplete_prop_row_is_isolated_without_poisoning_other_exact_contexts():
    good_a = _prop(game_id=777501, player_id=660501, market_type=PITCHER_STRIKEOUTS)
    bad = _prop(game_id=777502, player_id=660502, market_type=PLAYER_HITS, over_odds=None)
    good_b = _prop(game_id=777503, player_id=660503, market_type=HITS_RUNS_RBI, line=2.5)
    state = _fresh(build_player_prop_api_state(_payload(good_a, bad, good_b)))

    assert state["integration_status"] == API_CONNECTED
    assert state["feed_fresh"] is True
    assert state["api_prop_count"] == 3
    assert state["usable_player_prop_count"] == 2
    assert state["unusable_player_prop_count"] == 1
    assert state["failures"] == []
    assert player_prop_context_for_identity(
        state,
        official_game_id=777502,
        official_player_id=660502,
        market_type=PLAYER_HITS,
    ) is None
    assert player_prop_context_for_identity(
        state,
        official_game_id=777501,
        official_player_id=660501,
        market_type=PITCHER_STRIKEOUTS,
    ) is not None
    assert player_prop_context_for_identity(
        state,
        official_game_id=777503,
        official_player_id=660503,
        market_type=HITS_RUNS_RBI,
    ) is not None


def test_missing_exact_identity_is_isolated_and_never_recovered_by_name():
    nameless_identity = _prop(game_id=777601, player_id=None, player_name="Famous Name", market_type=PLAYER_HITS)
    good = _prop(game_id=777602, player_id=660602, player_name="Famous Name", market_type=PLAYER_HITS)
    state = _fresh(build_player_prop_api_state(_payload(nameless_identity, good)))

    assert state["usable_player_prop_count"] == 1
    assert state["unusable_player_prop_count"] == 1
    assert state["player_name_matching_used"] is False
    assert player_prop_context_for_identity(
        state,
        official_game_id=777601,
        official_player_id=660602,
        market_type=PLAYER_HITS,
    ) is None


def test_stale_snapshot_fails_closed_and_does_not_guess_prices():
    state = build_player_prop_api_state(
        _payload(_prop(), collected_at="2026-08-31T19:00:00Z")
    )
    stale = enforce_player_prop_api_freshness(
        state,
        as_of_utc="2026-08-31T20:00:00Z",
        max_age_seconds=60,
    )

    assert stale["integration_status"] == FALLBACK
    assert stale["api_integration_active"] is False
    assert stale["feed_fresh"] is False
    assert stale["snapshot_age_seconds"] == 3600.0
    assert "api_snapshot_stale" in stale["failures"]
    assert player_prop_context_for_identity(
        stale,
        official_game_id=777001,
        official_player_id=660001,
        market_type=PITCHER_STRIKEOUTS,
    ) is None


def test_bad_freshness_arguments_fail_explicitly():
    state = build_player_prop_api_state(_payload(_prop()))
    with pytest.raises(ValueError):
        enforce_player_prop_api_freshness(state, max_age_seconds=-1)
    with pytest.raises(ValueError):
        enforce_player_prop_api_freshness(state, as_of_utc="not-a-date")
