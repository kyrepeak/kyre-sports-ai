from __future__ import annotations

import pytest

from sports_api.collectors.mlb_event_player_identity import (
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    MLBEventPlayerIdentityError,
    REGISTRY_STATUS,
    STEP19C_BASE_MAIN_SHA,
    build_mlb_event_player_identity_registry,
    identity_manifest,
)


def _game(
    game_pk: int,
    *,
    away_id: int = 10,
    away_name: str = "Away Club",
    home_id: int = 20,
    home_name: str = "Home Club",
    game_date: str = "2026-09-02T23:10:00Z",
    game_number: int = 1,
    doubleheader: bool = False,
    status: str = "scheduled",
) -> dict:
    return {
        "game_pk": game_pk,
        "game_date": game_date,
        "official_date": "2026-09-02",
        "game_type": "R",
        "status": status,
        "status_detail": "Scheduled" if status == "scheduled" else status.title(),
        "status_code": "S",
        "start_time_tbd": False,
        "away_team": {"id": away_id, "name": away_name},
        "home_team": {"id": home_id, "name": home_name},
        "away_probable_pitcher": None,
        "home_probable_pitcher": None,
        "doubleheader": doubleheader,
        "doubleheader_code": "Y" if doubleheader else "N",
        "game_number": game_number,
        "series_game_number": game_number,
        "scheduled_innings": 9,
        "reschedule_date": None,
        "is_postponed": status == "postponed",
        "is_cancelled": status == "cancelled",
    }


def _slate(games: list[dict] | None = None) -> dict:
    rows = [_game(1001)] if games is None else games
    return {
        "sport": "MLB",
        "slate_date": "2026-09-02",
        "game_count": len(rows),
        "games": rows,
        "collected_at_utc": "2026-09-02T03:30:00+00:00",
        "source": "MLB Stats API",
    }


def _game_snapshot(
    *,
    provider: str = "fanduel",
    event_id: str = "fd-event-1",
    game_id: int = 1001,
    exact: bool = True,
    fuzzy: bool = False,
    synthetic: bool = False,
) -> dict:
    return {
        "provider_key": provider,
        "provider_name": "FanDuel" if provider == "fanduel" else provider.title(),
        "provider_event_id": event_id,
        "official_game_id": game_id,
        "observed_at_utc": "2026-09-02T03:30:00Z",
        "source_collected_at_utc": "2026-09-02T03:29:00Z",
        "market_phase": "PREGAME",
        "transport": "anonymous_public_get_only",
        "source_payload_sha256": "a" * 64,
        "markets": {"moneyline": {"away_odds": -120, "home_odds": 110}},
        "source_complete": True,
        "exact_official_game_id_verified": exact,
        "fuzzy_matching_used": fuzzy,
        "synthetic_game_id_used": synthetic,
        "price_fabrication_used": False,
    }


def _prop(
    *,
    provider: str = "fanduel",
    event_id: str = "fd-event-1",
    market_id: str = "fd-market-1",
    game_id: int = 1001,
    player_id: int = 501,
    player_name: str = "Example Player",
    market_type: str = "player_hits",
    exact_game: bool = True,
    exact_player: bool = True,
    player_name_matching: bool = False,
    fuzzy: bool = False,
) -> dict:
    return {
        "provider_key": provider,
        "provider_name": "FanDuel" if provider == "fanduel" else provider.title(),
        "official_game_id": game_id,
        "official_player_id": player_id,
        "player_name": player_name,
        "market_type": market_type,
        "line": 0.5,
        "over_odds": -125,
        "under_odds": -105,
        "source_event_id": event_id,
        "source_market_id": market_id,
        "exact_official_game_id_verified": exact_game,
        "exact_official_player_id_verified": exact_player,
        "player_name_matching_used": player_name_matching,
        "fuzzy_matching_used": fuzzy,
        "price_fabrication_used": False,
    }


def _feed(
    games: list[dict] | None = None,
    props: list[dict] | None = None,
) -> dict:
    game_rows = [_game_snapshot()] if games is None else games
    prop_rows = [_prop()] if props is None else props
    return {
        "data_type": "mlb_step19b_live_market_feed_v1",
        "schema_version": 1,
        "game_market_snapshots": game_rows,
        "player_props": prop_rows,
    }


def _build(*, slate: dict | None = None, feed: dict | None = None) -> dict:
    return build_mlb_event_player_identity_registry(
        official_slate=_slate() if slate is None else slate,
        market_feed=_feed() if feed is None else feed,
    )


def test_manifest_freezes_step19c_boundary():
    manifest = identity_manifest()
    assert manifest["data_type"] == DATA_TYPE
    assert manifest["step19c_base_main_sha"] == STEP19C_BASE_MAIN_SHA
    assert manifest["registry_status"] == REGISTRY_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert manifest["exact_official_game_id_required"] is True
    assert manifest["exact_official_player_id_required_for_props"] is True
    assert manifest["player_name_matching_allowed"] is False
    assert manifest["fuzzy_matching_allowed"] is False
    assert manifest["synthetic_game_id_allowed"] is False
    assert manifest["synthetic_player_id_allowed"] is False
    assert manifest["network_reads_added_by_step19c"] is False
    assert manifest["production_database_writes_enabled"] is False
    assert manifest["actionable_output_enabled"] is False
    assert manifest["wagering_enabled"] is False


def test_builds_verified_event_and_player_identity_registry():
    registry = _build()
    assert registry["event_identity_count"] == 1
    assert registry["player_identity_count"] == 1
    assert registry["rejected_event_identity_count"] == 0
    assert registry["rejected_player_identity_count"] == 0
    assert registry["providers_with_verified_identity"] == ["fanduel"]
    assert registry["identity_complete_for_all_market_games"] is True

    event = registry["event_identities"][0]
    assert event["provider_event_id"] == "fd-event-1"
    assert event["official_game_id"] == 1001
    assert event["official_game"]["away_team"]["id"] == 10
    assert event["official_game"]["home_team"]["id"] == 20
    assert event["fuzzy_matching_used"] is False

    player = registry["player_identities"][0]
    assert player["source_event_id"] == "fd-event-1"
    assert player["official_game_id"] == 1001
    assert player["official_player_id"] == 501
    assert player["source_market_ids"] == ["fd-market-1"]
    assert player["player_name_matching_used"] is False


def test_cross_provider_events_can_map_to_same_official_game():
    feed = _feed(
        games=[
            _game_snapshot(provider="fanduel", event_id="fd-1", game_id=1001),
            _game_snapshot(provider="draftkings", event_id="dk-1", game_id=1001),
        ],
        props=[],
    )
    registry = _build(feed=feed)
    assert registry["event_identity_count"] == 2
    assert registry["providers_with_verified_identity"] == ["draftkings", "fanduel"]
    assert {row["provider_event_id"] for row in registry["event_identities"]} == {"fd-1", "dk-1"}


def test_doubleheader_exact_game_ids_remain_distinct():
    slate = _slate(
        [
            _game(1001, game_number=1, doubleheader=True, game_date="2026-09-02T18:10:00Z"),
            _game(1002, game_number=2, doubleheader=True, game_date="2026-09-02T23:10:00Z"),
        ]
    )
    feed = _feed(
        games=[
            _game_snapshot(event_id="fd-game-1", game_id=1001),
            _game_snapshot(event_id="fd-game-2", game_id=1002),
        ],
        props=[],
    )
    registry = _build(slate=slate, feed=feed)
    assert registry["event_identity_count"] == 2
    by_event = {row["provider_event_id"]: row for row in registry["event_identities"]}
    assert by_event["fd-game-1"]["official_game"]["game_number"] == 1
    assert by_event["fd-game-2"]["official_game"]["game_number"] == 2


def test_postponed_official_game_is_preserved_not_remapped():
    slate = _slate([_game(1001, status="postponed")])
    registry = _build(slate=slate, feed=_feed(props=[]))
    event = registry["event_identities"][0]
    assert event["official_game_id"] == 1001
    assert event["official_game"]["status"] == "postponed"
    assert event["official_game"]["is_postponed"] is True


def test_game_id_not_present_on_official_slate_fails_closed():
    feed = _feed(games=[_game_snapshot(game_id=9999)], props=[])
    registry = _build(feed=feed)
    assert registry["event_identity_count"] == 0
    assert registry["rejected_event_identity_count"] == 1
    assert "official_game_not_in_slate" in registry["rejected_event_identities"][0]["reasons"]
    assert registry["synthetic_game_id_used"] is False


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("exact_official_game_id_verified", False, "exact_official_game_id_not_verified"),
        ("fuzzy_matching_used", True, "fuzzy_matching_not_explicitly_false"),
        ("synthetic_game_id_used", True, "synthetic_game_id_not_explicitly_false"),
    ],
)
def test_event_identity_requires_exact_nonfuzzy_nonsynthetic_claim(field, value, reason):
    row = _game_snapshot()
    row[field] = value
    registry = _build(feed=_feed(games=[row], props=[]))
    assert registry["event_identity_count"] == 0
    assert reason in registry["rejected_event_identities"][0]["reasons"]


def test_same_provider_event_claimed_twice_fails_closed():
    feed = _feed(
        games=[
            _game_snapshot(event_id="fd-dup", game_id=1001),
            _game_snapshot(event_id="fd-dup", game_id=1001),
        ],
        props=[],
    )
    registry = _build(feed=feed)
    assert registry["event_identity_count"] == 0
    assert registry["rejected_event_identities"][0]["kind"] == "ambiguous_provider_event_claim"


def test_same_provider_event_cannot_claim_two_official_games():
    slate = _slate(
        [
            _game(1001),
            _game(
                1002,
                away_id=30,
                away_name="Other Away",
                home_id=40,
                home_name="Other Home",
            ),
        ]
    )
    feed = _feed(
        games=[
            _game_snapshot(event_id="fd-conflict", game_id=1001),
            _game_snapshot(event_id="fd-conflict", game_id=1002),
        ],
        props=[],
    )
    registry = _build(slate=slate, feed=feed)
    assert registry["event_identity_count"] == 0
    rejected = registry["rejected_event_identities"][0]
    assert rejected["kind"] == "ambiguous_provider_event_claim"
    assert rejected["official_game_ids"] == [1001, 1002]


def test_one_provider_cannot_publish_two_event_ids_for_same_official_game():
    feed = _feed(
        games=[
            _game_snapshot(event_id="fd-a", game_id=1001),
            _game_snapshot(event_id="fd-b", game_id=1001),
        ],
        props=[],
    )
    registry = _build(feed=feed)
    assert registry["event_identity_count"] == 0
    assert any(
        row["kind"] == "multiple_provider_events_for_official_game"
        for row in registry["rejected_event_identities"]
    )


def test_player_prop_requires_verified_provider_event_for_same_game():
    registry = _build(
        feed=_feed(
            games=[_game_snapshot(event_id="fd-event-1", game_id=1001)],
            props=[_prop(event_id="different-event", game_id=1001)],
        )
    )
    assert registry["player_identity_count"] == 0
    assert "provider_event_not_verified" in registry["rejected_player_identities"][0]["reasons"]


def test_player_prop_event_game_conflict_fails_closed():
    slate = _slate(
        [
            _game(1001),
            _game(
                1002,
                away_id=30,
                away_name="Other Away",
                home_id=40,
                home_name="Other Home",
            ),
        ]
    )
    registry = _build(
        slate=slate,
        feed=_feed(
            games=[_game_snapshot(event_id="fd-event-1", game_id=1001)],
            props=[_prop(event_id="fd-event-1", game_id=1002)],
        ),
    )
    assert registry["player_identity_count"] == 0
    assert "provider_event_game_conflict" in registry["rejected_player_identities"][0]["reasons"]


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("exact_official_game_id_verified", False, "exact_official_game_id_not_verified"),
        ("exact_official_player_id_verified", False, "exact_official_player_id_not_verified"),
        ("player_name_matching_used", True, "player_name_matching_not_explicitly_false"),
        ("fuzzy_matching_used", True, "fuzzy_matching_not_explicitly_false"),
    ],
)
def test_player_identity_requires_exact_name_free_nonfuzzy_claim(field, value, reason):
    prop = _prop()
    prop[field] = value
    registry = _build(feed=_feed(props=[prop]))
    assert registry["player_identity_count"] == 0
    assert reason in registry["rejected_player_identities"][0]["reasons"]


def test_multiple_market_types_for_same_player_aggregate_without_fabricated_player_key():
    registry = _build(
        feed=_feed(
            props=[
                _prop(market_id="hits-1", market_type="player_hits"),
                _prop(market_id="ks-1", market_type="pitcher_strikeouts"),
            ]
        )
    )
    assert registry["player_identity_count"] == 1
    player = registry["player_identities"][0]
    assert player["official_player_id"] == 501
    assert player["source_market_ids"] == ["hits-1", "ks-1"]
    assert player["market_types"] == ["pitcher_strikeouts", "player_hits"]
    assert "provider_player_id" not in player
    assert player["synthetic_player_id_used"] is False


def test_duplicate_prop_market_reference_fails_closed():
    registry = _build(
        feed=_feed(
            props=[
                _prop(market_id="dup-market"),
                _prop(market_id="dup-market"),
            ]
        )
    )
    assert registry["player_identity_count"] == 0
    assert registry["rejected_player_identities"][0]["kind"] == "ambiguous_prop_market_player_claim"


def test_conflicting_player_display_names_fail_closed_even_though_names_are_not_matching_keys():
    registry = _build(
        feed=_feed(
            props=[
                _prop(market_id="m1", player_name="Example Player"),
                _prop(market_id="m2", player_name="Different Display Name"),
            ]
        )
    )
    assert registry["player_identity_count"] == 0
    assert registry["rejected_player_identities"][0]["kind"] == "conflicting_player_display_metadata"


def test_empty_official_slate_and_empty_feed_are_valid():
    registry = _build(slate=_slate([]), feed=_feed(games=[], props=[]))
    assert registry["official_game_count"] == 0
    assert registry["event_identity_count"] == 0
    assert registry["player_identity_count"] == 0
    assert registry["unmatched_official_game_ids"] == []
    assert registry["identity_complete_for_all_market_games"] is True


def test_unmatched_official_games_are_reported_without_synthetic_market_identity():
    slate = _slate(
        [
            _game(1001),
            _game(
                1002,
                away_id=30,
                away_name="Other Away",
                home_id=40,
                home_name="Other Home",
            ),
        ]
    )
    registry = _build(slate=slate, feed=_feed(props=[]))
    assert registry["unmatched_official_game_ids"] == [1002]
    assert registry["synthetic_game_id_used"] is False


def test_malformed_local_envelopes_raise_instead_of_guessing():
    with pytest.raises(MLBEventPlayerIdentityError):
        build_mlb_event_player_identity_registry(
            official_slate={"sport": "NBA", "game_count": 0, "games": []},
            market_feed=_feed(games=[], props=[]),
        )

    bad_slate = _slate()
    bad_slate["game_count"] = 2
    with pytest.raises(MLBEventPlayerIdentityError):
        _build(slate=bad_slate)


def test_registry_is_pure_and_keeps_all_mutation_flags_off():
    registry = _build()
    assert registry["fuzzy_matching_used"] is False
    assert registry["player_name_matching_used"] is False
    assert registry["synthetic_game_id_used"] is False
    assert registry["synthetic_player_id_used"] is False
    assert registry["price_fabrication_used"] is False
    assert registry["network_reads_added_by_step19c"] is False
    assert registry["production_runtime_wiring"] is False
    assert registry["production_database_writes"] is False
    assert registry["model_probability_mutation"] is False
    assert registry["projection_mutation"] is False
    assert registry["actionable_output"] is False
    assert registry["wagering"] is False
