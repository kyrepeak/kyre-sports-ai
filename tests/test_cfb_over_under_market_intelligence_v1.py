from __future__ import annotations

import copy

import pytest

import cfb_over_under_market_intelligence_v1 as market_intel


def _row(
    *,
    game_id="401858213",
    sportsbook="FanDuel",
    total=62.5,
    line_status="active",
    identity_verified=True,
):
    return {
        "game_id": game_id,
        "game_date": "2026-09-10",
        "away_team": "Florida A&M",
        "home_team": "Miami",
        "sportsbook": sportsbook,
        "market_type": "game_total",
        "total": total,
        "line_status": line_status,
        "line_updated_at_utc": "2026-09-10T14:10:00+00:00",
        "identity_verified": identity_verified,
    }


def _payload(rows):
    return {
        "games": rows,
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


def test_single_fanduel_row_is_truthfully_single_book_not_consensus():
    result = market_intel.build_market_intelligence(_payload([_row()]))
    game = result["games"]["401858213"]

    assert game["market_state"] == "SINGLE_BOOK"
    assert game["provider_count"] == 1
    assert game["consensus_available"] is False
    assert game["reference_source"] == "single_book"
    assert game["reference_total"] == 62.5
    assert game["total_range"] == 0.0
    assert result["diagnostics"]["single_book_is_consensus"] is False
    assert result["diagnostics"]["projection_weight"] == 0.0


def test_three_books_build_real_median_consensus_without_projection_influence():
    result = market_intel.build_market_intelligence(
        _payload(
            [
                _row(sportsbook="FanDuel", total=62.5),
                _row(sportsbook="DraftKings", total=63.0),
                _row(sportsbook="BetMGM", total=63.5),
            ]
        ),
        model_projections={"401858213": 65.0},
    )
    game = result["games"]["401858213"]

    assert game["provider_count"] == 3
    assert game["market_state"] == "CONSENSUS"
    assert game["consensus_available"] is True
    assert game["reference_source"] == "multibook_median"
    assert game["reference_total"] == 63.0
    assert game["minimum_total"] == 62.5
    assert game["maximum_total"] == 63.5
    assert game["total_range"] == 1.0
    assert game["model_projection"] == 65.0
    assert game["model_market_edge"] == 2.0
    assert game["projection_weight"] == 0.0
    assert game["may_modify_projection"] is False


def test_multibook_dispersion_is_classified_mixed_then_disagreement():
    mixed = market_intel.build_market_intelligence(
        _payload(
            [
                _row(sportsbook="FanDuel", total=62.5),
                _row(sportsbook="DraftKings", total=64.0),
            ]
        )
    )["games"]["401858213"]
    assert mixed["market_state"] == "MIXED"
    assert mixed["reference_total"] == 63.25

    disagreement = market_intel.build_market_intelligence(
        _payload(
            [
                _row(sportsbook="FanDuel", total=61.5),
                _row(sportsbook="DraftKings", total=64.5),
            ]
        )
    )["games"]["401858213"]
    assert disagreement["market_state"] == "DISAGREEMENT"
    assert disagreement["total_range"] == 3.0


def test_duplicate_sportsbook_for_same_event_fails_closed():
    with pytest.raises(
        market_intel.MarketIntelligenceError,
        match=r"unsafe_duplicate_sportsbook:401858213:FanDuel",
    ):
        market_intel.build_market_intelligence(
            _payload([_row(total=62.5), _row(total=63.0)])
        )


def test_non_numeric_official_event_id_fails_closed():
    with pytest.raises(
        market_intel.MarketIntelligenceError,
        match="unsafe_non_official_event_id",
    ):
        market_intel.build_market_intelligence(
            _payload([_row(game_id="synthetic-401858213")])
        )


def test_unverified_identity_fails_closed():
    with pytest.raises(
        market_intel.MarketIntelligenceError,
        match="unsafe_unverified_event_identity:401858213",
    ):
        market_intel.build_market_intelligence(
            _payload([_row(identity_verified=False)])
        )


def test_nonfinite_total_fails_closed():
    with pytest.raises(
        market_intel.MarketIntelligenceError,
        match="unsafe_nonfinite:total:401858213",
    ):
        market_intel.build_market_intelligence(_payload([_row(total=float("nan"))]))


def test_nonzero_market_projection_weight_fails_closed():
    payload = _payload([_row()])
    payload["market_semantics"]["projection_weight"] = 0.01
    with pytest.raises(
        market_intel.MarketIntelligenceError,
        match="unsafe_nonzero_projection_weight",
    ):
        market_intel.build_market_intelligence(payload)


def test_separate_official_event_ids_are_never_combined():
    result = market_intel.build_market_intelligence(
        _payload(
            [
                _row(game_id="401858213", sportsbook="FanDuel", total=62.5),
                _row(game_id="401858214", sportsbook="FanDuel", total=48.5),
            ]
        )
    )

    assert result["game_count"] == 2
    assert result["games"]["401858213"]["provider_count"] == 1
    assert result["games"]["401858214"]["provider_count"] == 1
    assert result["games"]["401858213"]["reference_total"] == 62.5
    assert result["games"]["401858214"]["reference_total"] == 48.5


def test_model_projection_is_display_only_and_input_payload_is_not_mutated():
    payload = _payload([_row(total=62.5)])
    before = copy.deepcopy(payload)
    projections = {"401858213": 64.75}

    result = market_intel.build_market_intelligence(
        payload,
        model_projections=projections,
    )
    game = result["games"]["401858213"]

    assert payload == before
    assert projections == {"401858213": 64.75}
    assert game["model_projection"] == 64.75
    assert game["model_market_edge"] == 2.25
    assert game["projection_weight"] == 0.0
    assert result["diagnostics"]["market_context_only"] is True
    assert result["diagnostics"]["may_modify_projection"] is False
