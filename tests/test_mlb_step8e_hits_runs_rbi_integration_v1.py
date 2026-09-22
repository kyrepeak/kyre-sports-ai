from copy import deepcopy

from sports_api.mlb_step8a_player_prop_api_contract_v1 import (
    API_CONNECTED,
    HITS_RUNS_RBI,
    PLAYER_HITS,
    build_player_prop_api_state,
    enforce_player_prop_api_freshness,
)
from sports_api.mlb_step8e_hits_runs_rbi_integration_v1 import (
    ATTACHMENT_KEY,
    FALLBACK,
    INTEGRATED,
    build_hits_runs_rbi_integration,
    enrich_hits_runs_rbi_results,
)


def _prop(game=1001, player=2001, market=HITS_RUNS_RBI, name="FanDuel Display"):
    return {
        "official_game_id": game,
        "official_player_id": player,
        "player_name": name,
        "market_type": market,
        "line": 2.5,
        "over_odds": -115,
        "under_odds": -105,
        "sportsbook": "FanDuel",
        "source_event_id": "fd-event-1",
        "source_market_id": "fd-market-1",
    }


def _fresh_state(*props):
    payload = {
        "data_type": "mlb_player_prop_api_response_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "collected_at_utc": "2026-08-31T22:00:00Z",
        "props": list(props or [_prop()]),
    }
    raw = build_player_prop_api_state(payload)
    assert raw["integration_status"] == API_CONNECTED
    return enforce_player_prop_api_freshness(
        raw,
        as_of_utc="2026-08-31T22:00:20Z",
        max_age_seconds=60,
    )


def _result(game=1001, player=2001, name="Model Display"):
    return {
        "game_pk": game,
        "player_id": player,
        "player_name": name,
        "team": "AAA",
        "opponent": "BBB",
        "rank_sentinel": 7,
        "projection_sentinel": 2.91,
        "probability_sentinel": 0.641,
        "confidence": "HIGH",
        "model_payload": {
            "hits": 1.21,
            "runs": 0.84,
            "rbi": 0.86,
            "combined": 2.91,
            "distribution": {"0": 0.09, "1": 0.17, "2": 0.24, "3+": 0.50},
            "sentinel": 17,
        },
    }


def test_exact_id_attachment_ignores_player_name_completely():
    state = _fresh_state(_prop(name="Completely Different FanDuel Name"))
    results = [_result(name="Unrelated Model Display Name")]
    integration = build_hits_runs_rbi_integration(results, state)

    assert integration["integration_status"] == INTEGRATED
    assert integration["attached_count"] == 1
    context = integration["attachments_by_result_index"][0]
    assert context["official_game_id"] == 1001
    assert context["official_player_id"] == 2001
    assert context["player_name"] == "Completely Different FanDuel Name"
    assert context["market_type"] == HITS_RUNS_RBI
    assert integration["player_name_matching_used"] is False


def test_enrichment_preserves_every_preexisting_model_field_and_value():
    state = _fresh_state(_prop())
    original = _result()
    integration = build_hits_runs_rbi_integration([original], state)
    enriched = enrich_hits_runs_rbi_results([original], integration)

    assert ATTACHMENT_KEY in enriched[0]
    stripped = dict(enriched[0])
    stripped.pop(ATTACHMENT_KEY)
    assert stripped == original
    assert enriched[0]["model_payload"] == original["model_payload"]
    assert enriched[0]["projection_sentinel"] == original["projection_sentinel"]
    assert enriched[0]["probability_sentinel"] == original["probability_sentinel"]
    assert enriched[0]["rank_sentinel"] == original["rank_sentinel"]


def test_stale_step8a_state_fails_closed_to_preexisting_model():
    payload = {
        "data_type": "mlb_player_prop_api_response_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "collected_at_utc": "2026-08-31T20:00:00Z",
        "props": [_prop()],
    }
    raw = build_player_prop_api_state(payload)
    stale = enforce_player_prop_api_freshness(
        raw,
        as_of_utc="2026-08-31T22:00:00Z",
        max_age_seconds=60,
    )
    original = [_result()]
    integration = build_hits_runs_rbi_integration(original, stale)

    assert integration["integration_status"] == FALLBACK
    assert integration["attached_count"] == 0
    assert "player_prop_feed_freshness_not_proven" in integration["failures"]
    assert enrich_hits_runs_rbi_results(original, integration) == original


def test_same_player_name_with_wrong_official_id_never_matches():
    state = _fresh_state(_prop(game=1001, player=2001, name="Same Name"))
    integration = build_hits_runs_rbi_integration(
        [_result(game=1001, player=9999, name="Same Name")],
        state,
    )
    assert integration["attached_count"] == 0
    assert integration["unmatched_count"] == 1
    assert integration["player_name_matching_used"] is False


def test_player_hits_context_never_attaches_to_hits_runs_rbi():
    state = _fresh_state(_prop(market=PLAYER_HITS))
    integration = build_hits_runs_rbi_integration([_result()], state)
    assert integration["attached_count"] == 0
    assert integration["unmatched_count"] == 1
    assert integration["market_type"] == HITS_RUNS_RBI


def test_invalid_result_identity_is_isolated_when_unrelated_exact_row_is_usable():
    state = _fresh_state(_prop())
    integration = build_hits_runs_rbi_integration(
        [{"player_id": None, "player_name": "Bad"}, _result()],
        state,
    )
    assert integration["integration_status"] == INTEGRATED
    assert integration["invalid_result_count"] == 1
    assert integration["attached_count"] == 1
    assert 1 in integration["attachments_by_result_index"]


def test_duplicate_exact_hits_runs_rbi_result_identity_globally_fails_closed():
    state = _fresh_state(_prop())
    results = [_result(name="First"), _result(name="Second")]
    integration = build_hits_runs_rbi_integration(results, state)

    assert integration["integration_status"] == FALLBACK
    assert integration["api_integration_active"] is False
    assert integration["attached_count"] == 0
    assert "duplicate_exact_hits_runs_rbi_result_identity" in integration["failures"]
    assert enrich_hits_runs_rbi_results(results, integration) == results


def test_tampered_step8a_matching_flags_block_all_attachments():
    state = _fresh_state(_prop())
    state["player_name_matching_used"] = True
    integration = build_hits_runs_rbi_integration([_result()], state)
    assert integration["attached_count"] == 0
    assert "player_name_matching_detected" in integration["failures"]


def test_sportsbook_price_model_input_drift_blocks_all_attachments():
    state = _fresh_state(_prop())
    state["sportsbook_price_model_input"] = True
    integration = build_hits_runs_rbi_integration([_result()], state)
    assert integration["attached_count"] == 0
    assert "sportsbook_price_model_input_drift" in integration["failures"]


def test_inactive_integration_returns_deep_copied_results_without_attachment():
    original = [_result()]
    fallback = {
        "api_integration_active": False,
        "integration_status": FALLBACK,
    }
    enriched = enrich_hits_runs_rbi_results(original, fallback)
    assert enriched == original
    assert enriched is not original
    assert enriched[0] is not original[0]
    assert ATTACHMENT_KEY not in enriched[0]


def test_tampered_attachment_identity_is_rejected_during_enrichment():
    state = _fresh_state(_prop())
    integration = build_hits_runs_rbi_integration([_result()], state)
    integration["attachments_by_result_index"][0]["official_player_id"] = 9999
    enriched = enrich_hits_runs_rbi_results([_result()], integration)
    assert ATTACHMENT_KEY not in enriched[0]


def test_tampered_attachment_market_is_rejected_during_enrichment():
    state = _fresh_state(_prop())
    integration = build_hits_runs_rbi_integration([_result()], state)
    integration["attachments_by_result_index"][0]["market_type"] = PLAYER_HITS
    enriched = enrich_hits_runs_rbi_results([_result()], integration)
    assert ATTACHMENT_KEY not in enriched[0]


def test_build_and_enrich_do_not_mutate_inputs():
    api_state = _fresh_state(_prop())
    results = [_result()]
    api_before = deepcopy(api_state)
    results_before = deepcopy(results)

    integration = build_hits_runs_rbi_integration(results, api_state)
    integration_before = deepcopy(integration)
    _ = enrich_hits_runs_rbi_results(results, integration)

    assert api_state == api_before
    assert results == results_before
    assert integration == integration_before


def test_attachment_is_display_only_and_has_zero_math_or_ranking_impact_flags():
    integration = build_hits_runs_rbi_integration([_result()], _fresh_state(_prop()))
    context = integration["attachments_by_result_index"][0]

    assert context["display_only"] is True
    for key in (
        "model_math_impact",
        "projection_impact",
        "simulation_impact",
        "probability_impact",
        "line_grading_impact",
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
        assert integration[key] is False


def test_multiple_exact_players_attach_independently_by_ids_only():
    state = _fresh_state(
        _prop(game=1001, player=2001, name="FD A"),
        {
            **_prop(game=1002, player=2002, name="FD B"),
            "source_event_id": "fd-event-2",
            "source_market_id": "fd-market-2",
            "line": 3.5,
            "over_odds": 125,
            "under_odds": -150,
        },
    )
    results = [
        _result(game=1001, player=2001, name="Model X"),
        _result(game=1002, player=2002, name="Model Y"),
    ]
    integration = build_hits_runs_rbi_integration(results, state)
    enriched = enrich_hits_runs_rbi_results(results, integration)

    assert integration["attached_count"] == 2
    assert integration["unmatched_count"] == 0
    assert enriched[0][ATTACHMENT_KEY]["line"] == 2.5
    assert enriched[1][ATTACHMENT_KEY]["line"] == 3.5
    assert enriched[1][ATTACHMENT_KEY]["over_odds"] == 125
    assert enriched[1][ATTACHMENT_KEY]["under_odds"] == -150


def test_fractional_ids_fail_closed_without_truncation_but_digit_strings_work():
    state = _fresh_state(_prop())
    rows = [
        _result(game=1001.9, player=2001),
        _result(game=1001, player=2001.8),
        _result(game="1001", player="2001", name="Serialized exact IDs"),
    ]
    integration = build_hits_runs_rbi_integration(rows, state)

    assert integration["invalid_result_count"] == 2
    assert integration["valid_exact_identity_count"] == 1
    assert integration["attached_count"] == 1
    assert set(integration["attachments_by_result_index"]) == {2}


def test_boolean_ids_are_not_accepted_as_integer_identity():
    state = _fresh_state(_prop())
    integration = build_hits_runs_rbi_integration([_result(game=True, player=2001)], state)
    assert integration["invalid_result_count"] == 1
    assert integration["attached_count"] == 0


def test_fractional_attachment_index_cannot_redirect_context_to_another_row():
    state = _fresh_state(_prop())
    integration = build_hits_runs_rbi_integration([_result()], state)
    context = integration["attachments_by_result_index"].pop(0)
    integration["attachments_by_result_index"][0.9] = context

    enriched = enrich_hits_runs_rbi_results([_result()], integration)
    assert ATTACHMENT_KEY not in enriched[0]


def test_unicode_digit_ids_are_isolated_instead_of_raising():
    state = _fresh_state(_prop())
    rows = [
        _result(game="²", player=2001, name="Bad game id"),
        _result(game=1001, player="²", name="Bad player id"),
        _result(game="1001", player="2001", name="Good ASCII ids"),
    ]

    integration = build_hits_runs_rbi_integration(rows, state)

    assert integration["invalid_result_count"] == 2
    assert integration["valid_exact_identity_count"] == 1
    assert integration["attached_count"] == 1
    assert set(integration["attachments_by_result_index"]) == {2}


def test_unicode_digit_attachment_index_is_ignored_instead_of_raising():
    state = _fresh_state(_prop())
    integration = build_hits_runs_rbi_integration([_result()], state)
    context = integration["attachments_by_result_index"].pop(0)
    integration["attachments_by_result_index"]["²"] = context

    enriched = enrich_hits_runs_rbi_results([_result()], integration)
    assert ATTACHMENT_KEY not in enriched[0]
