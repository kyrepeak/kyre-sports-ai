from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from sports_api.api import mlb as mlb_api
from sports_api.collectors.mlb_fanduel_player_props import (
    HITS_RUNS_RBI,
    PITCHER_STRIKEOUTS,
    PLAYER_HITS,
    collect_live_mlb_player_props,
    market_family,
    normalize_two_way_player_market,
    reconcile_fanduel_player_to_mlbam,
)
from sports_api.mlb_step8a_player_prop_api_contract_v1 import (
    API_CONNECTED,
    build_player_prop_api_state,
    enforce_player_prop_api_freshness,
)

NOW = datetime(2026, 8, 31, 21, 0, tzinfo=timezone.utc)
EVENT_ID = "36004225"
GAME_ID = 824473
AWAY_TEAM_ID = 135
HOME_TEAM_ID = 113
PLAYER_ID = 650633
PLAYER_KEY = "provider-player-key"
HEADSHOT = "9e8adb3a-56df-44bd-b716-4a4b6c57175b"
OVER_SELECTION = "59649279"
UNDER_SELECTION = "59649280"


def _landing():
    return {
        "attachments": {
            "events": {
                EVENT_ID: {
                    "eventId": EVENT_ID,
                    "name": "San Diego Padres (M King) @ Cincinnati Reds (B Singer)",
                    "openDate": "2026-09-01T00:30:00Z",
                }
            }
        }
    }


def _schedule():
    return {
        "dates": [
            {
                "games": [
                    {
                        "gamePk": GAME_ID,
                        "gameDate": "2026-09-01T00:30:00Z",
                        "teams": {
                            "away": {"team": {"id": AWAY_TEAM_ID, "name": "San Diego Padres"}},
                            "home": {"team": {"id": HOME_TEAM_ID, "name": "Cincinnati Reds"}},
                        },
                    }
                ]
            }
        ]
    }


def _fdx_players(*, display_name="Completely Wrong Display Name"):
    return {
        "event": {
            "eventId": EVENT_ID,
            "awayTeam": {"abbrName": "SD"},
            "homeTeam": {"abbrName": "CIN"},
        },
        "playerMap": {
            PLAYER_KEY: {
                "name": display_name,
                "number": "34",
                "position": "SP",
                "team": "SD",
                "image": f"https://example.invalid/headshots/{HEADSHOT}.png",
                "selectionIds": [OVER_SELECTION, UNDER_SELECTION, "alt-1", "alt-2"],
            }
        },
    }


def _roster(team_id: int, _slate_date: str):
    if team_id == AWAY_TEAM_ID:
        return {
            "roster": [
                {
                    "person": {"id": PLAYER_ID, "fullName": "Official Name Is Not Read"},
                    "jerseyNumber": "34",
                    "position": {"abbreviation": "P"},
                },
                {
                    "person": {"id": 999001, "fullName": "Other Player"},
                    "jerseyNumber": "12",
                    "position": {"abbreviation": "OF"},
                },
            ]
        }
    return {
        "roster": [
            {
                "person": {"id": 663903, "fullName": "Home Pitcher"},
                "jerseyNumber": "51",
                "position": {"abbreviation": "P"},
            }
        ]
    }


def _odds(value: int):
    return {"americanDisplayOdds": {"americanOddsInt": value}}


def _runner(role: str, selection_id: str, odds: int, *, line=5.5, logo_uuid=HEADSHOT):
    return {
        "runnerName": f"ignored-{role}",
        "runnerStatus": "ACTIVE",
        "isPlayerSelection": True,
        "selectionId": selection_id,
        "logo": f"https://example.invalid/headshots/{logo_uuid}.png",
        "handicap": line,
        "result": {"type": role},
        "winRunnerOdds": _odds(odds),
    }


def _two_way_k_market(*, market_id="734.183697475", line=5.5):
    return {
        "marketId": market_id,
        "marketStatus": "OPEN",
        "inPlay": False,
        "marketType": "PITCHER_C_TOTAL_STRIKEOUTS",
        "marketName": "Display Name - Strikeouts",
        "runners": [
            _runner("OVER", OVER_SELECTION, -115, line=line),
            _runner("UNDER", UNDER_SELECTION, -105, line=line),
        ],
    }


def _alt_k_market():
    return {
        "marketId": "alt-k",
        "marketStatus": "OPEN",
        "inPlay": False,
        "marketType": "PITCHER_C_STRIKEOUTS",
        "marketName": "Display Name - Alt Strikeouts",
        "runners": [
            {
                "runnerStatus": "ACTIVE",
                "isPlayerSelection": True,
                "selectionId": "alt-1",
                "logo": f"https://example.invalid/headshots/{HEADSHOT}.png",
                "handicap": 0,
                "result": {"type": ""},
                "winRunnerOdds": _odds(-150),
            },
            {
                "runnerStatus": "ACTIVE",
                "isPlayerSelection": True,
                "selectionId": "alt-2",
                "logo": f"https://example.invalid/headshots/{HEADSHOT}.png",
                "handicap": 0,
                "result": {"type": ""},
                "winRunnerOdds": _odds(120),
            },
        ],
    }


def _hit_ladder_market():
    return {
        "marketId": "hit-ladder",
        "marketStatus": "OPEN",
        "inPlay": False,
        "marketType": "PLAYER_TO_RECORD_A_HIT",
        "marketName": "To Record A Hit",
        "runners": [
            {
                "runnerStatus": "ACTIVE",
                "isPlayerSelection": True,
                "selectionId": "hit-one-way",
                "logo": f"https://example.invalid/headshots/{HEADSHOT}.png",
                "handicap": 0,
                "result": {"type": ""},
                "winRunnerOdds": _odds(-550),
            }
        ],
    }


def _hrr_ladder_market():
    return {
        "marketId": "hrr-ladder",
        "marketStatus": "OPEN",
        "inPlay": False,
        "marketType": "PLAYER_TO_RECORD_2+_HITS+RUNS+RBIS",
        "marketName": "Player To Record 2+ Hits + Runs + RBIs",
        "runners": [
            {
                "runnerStatus": "ACTIVE",
                "isPlayerSelection": True,
                "selectionId": "hrr-one-way",
                "logo": f"https://example.invalid/headshots/{HEADSHOT}.png",
                "handicap": 0,
                "result": {"type": ""},
                "winRunnerOdds": _odds(-200),
            }
        ],
    }


def _tab_fetcher(_event_id: str, tab: str):
    markets = []
    if tab == "pitcher-props":
        markets = [_alt_k_market(), _two_way_k_market()]
    elif tab == "batter-props":
        markets = [_hit_ladder_market(), _hrr_ladder_market()]
    return {"attachments": {"markets": markets}}


def _collect(**overrides):
    kwargs = {
        "now_utc": NOW,
        "max_events": 5,
        "landing_fetcher": _landing,
        "tab_fetcher": _tab_fetcher,
        "players_fetcher": lambda _event_id: _fdx_players(),
        "schedule_fetcher": lambda _date: _schedule(),
        "roster_fetcher": _roster,
    }
    kwargs.update(overrides)
    return collect_live_mlb_player_props(**kwargs)


def test_market_family_recognizes_frozen_step8a_families_without_names():
    assert market_family("PITCHER_C_TOTAL_STRIKEOUTS") == PITCHER_STRIKEOUTS
    assert market_family("PITCHER_E_STRIKEOUTS") == PITCHER_STRIKEOUTS
    assert market_family("PLAYER_TO_RECORD_A_HIT") == PLAYER_HITS
    assert market_family("PLAYER_TO_RECORD_3+_HITS") == PLAYER_HITS
    assert market_family("PLAYER_TO_RECORD_2+_HITS+RUNS+RBIS") == HITS_RUNS_RBI
    assert market_family("TO_HIT_A_DOUBLE") is None
    assert market_family("TO_RECORD_2+_TOTAL_BASES") is None


def test_exact_roster_reconciliation_ignores_player_name_and_maps_sp_to_p():
    fdx_player = _fdx_players()["playerMap"][PLAYER_KEY]
    player_id = reconcile_fanduel_player_to_mlbam(
        fdx_player,
        official_team_by_fanduel_abbr={"SD": AWAY_TEAM_ID, "CIN": HOME_TEAM_ID},
        official_rosters_by_team={
            AWAY_TEAM_ID: _roster(AWAY_TEAM_ID, "2026-08-31")["roster"],
            HOME_TEAM_ID: _roster(HOME_TEAM_ID, "2026-08-31")["roster"],
        },
    )
    assert player_id == PLAYER_ID


def test_ambiguous_same_team_jersey_position_fails_closed():
    roster = deepcopy(_roster(AWAY_TEAM_ID, "2026-08-31")["roster"])
    roster.append(
        {
            "person": {"id": 777777, "fullName": "Another Name That Must Not Be Compared"},
            "jerseyNumber": "34",
            "position": {"abbreviation": "P"},
        }
    )
    player_id = reconcile_fanduel_player_to_mlbam(
        _fdx_players()["playerMap"][PLAYER_KEY],
        official_team_by_fanduel_abbr={"SD": AWAY_TEAM_ID},
        official_rosters_by_team={AWAY_TEAM_ID: roster},
    )
    assert player_id is None


def test_normalize_true_two_way_k_market_emits_frozen_contract_fields():
    fdx = _fdx_players()
    players = {key: dict(value) for key, value in fdx["playerMap"].items()}
    selection_map = {
        selection: [PLAYER_KEY]
        for selection in fdx["playerMap"][PLAYER_KEY]["selectionIds"]
    }
    prop = normalize_two_way_player_market(
        _two_way_k_market(),
        official_game_id=GAME_ID,
        source_event_id=EVENT_ID,
        players=players,
        selection_to_players=selection_map,
        official_team_by_fanduel_abbr={"SD": AWAY_TEAM_ID, "CIN": HOME_TEAM_ID},
        official_rosters_by_team={
            AWAY_TEAM_ID: _roster(AWAY_TEAM_ID, "2026-08-31")["roster"],
            HOME_TEAM_ID: _roster(HOME_TEAM_ID, "2026-08-31")["roster"],
        },
    )
    assert prop == {
        "official_game_id": GAME_ID,
        "official_player_id": PLAYER_ID,
        "player_name": "Completely Wrong Display Name",
        "market_type": PITCHER_STRIKEOUTS,
        "line": 5.5,
        "over_odds": -115,
        "under_odds": -105,
        "sportsbook": "FanDuel",
        "source_event_id": EVENT_ID,
        "source_market_id": "734.183697475",
    }


def test_alt_ladder_and_one_way_batter_boards_are_not_fabricated_into_props():
    snapshot = _collect()
    assert snapshot["prop_count"] == 1
    assert [prop["market_type"] for prop in snapshot["props"]] == [PITCHER_STRIKEOUTS]
    assert snapshot["contract_unavailable_market_counts"][PITCHER_STRIKEOUTS] == 1
    assert snapshot["contract_unavailable_market_counts"][PLAYER_HITS] == 1
    assert snapshot["contract_unavailable_market_counts"][HITS_RUNS_RBI] == 1
    assert snapshot["player_name_matching_used"] is False
    assert snapshot["fuzzy_matching_used"] is False


def test_wrong_fdx_display_name_does_not_change_official_identity():
    snapshot_a = _collect(players_fetcher=lambda _event_id: _fdx_players(display_name="Wrong A"))
    snapshot_b = _collect(players_fetcher=lambda _event_id: _fdx_players(display_name="Totally Different B"))
    assert snapshot_a["props"][0]["official_player_id"] == PLAYER_ID
    assert snapshot_b["props"][0]["official_player_id"] == PLAYER_ID
    assert snapshot_a["props"][0]["player_name"] == "Wrong A"
    assert snapshot_b["props"][0]["player_name"] == "Totally Different B"


def test_selection_not_owned_by_exact_fdx_player_fails_closed():
    fdx = _fdx_players()
    fdx["playerMap"][PLAYER_KEY]["selectionIds"] = [UNDER_SELECTION]
    snapshot = _collect(players_fetcher=lambda _event_id: fdx)
    assert snapshot["props"] == []
    assert snapshot["rejected_prop_count"] == 1
    assert "selection does not map to one FDX player" in snapshot["rejected_props"][0]["reason"]


def test_headshot_identity_mismatch_fails_closed():
    bad_uuid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def tabs(_event_id: str, tab: str):
        if tab != "pitcher-props":
            return {"attachments": {"markets": []}}
        market = _two_way_k_market()
        market["runners"][0]["logo"] = f"https://example.invalid/{bad_uuid}.png"
        market["runners"][1]["logo"] = f"https://example.invalid/{bad_uuid}.png"
        return {"attachments": {"markets": [market]}}

    snapshot = _collect(tab_fetcher=tabs)
    assert snapshot["props"] == []
    assert "headshot identity does not match FDX player" in snapshot["rejected_props"][0]["reason"]


def test_mismatched_over_under_lines_fail_closed():
    def tabs(_event_id: str, tab: str):
        if tab != "pitcher-props":
            return {"attachments": {"markets": []}}
        market = _two_way_k_market()
        market["runners"][1]["handicap"] = 6.5
        return {"attachments": {"markets": [market]}}

    snapshot = _collect(tab_fetcher=tabs)
    assert snapshot["props"] == []
    assert "mismatched lines" in snapshot["rejected_props"][0]["reason"]


def test_zero_or_missing_price_fails_closed():
    def tabs(_event_id: str, tab: str):
        if tab != "pitcher-props":
            return {"attachments": {"markets": []}}
        market = _two_way_k_market()
        market["runners"][1]["winRunnerOdds"] = _odds(0)
        return {"attachments": {"markets": [market]}}

    snapshot = _collect(tab_fetcher=tabs)
    assert snapshot["props"] == []
    assert "nonzero integer" in snapshot["rejected_props"][0]["reason"]


def test_ambiguous_multiple_two_way_markets_for_same_exact_identity_are_omitted():
    def tabs(_event_id: str, tab: str):
        if tab != "pitcher-props":
            return {"attachments": {"markets": []}}
        return {
            "attachments": {
                "markets": [
                    _two_way_k_market(market_id="market-a", line=5.5),
                    _two_way_k_market(market_id="market-b", line=6.5),
                ]
            }
        }

    snapshot = _collect(tab_fetcher=tabs)
    assert snapshot["props"] == []
    assert any(
        row["reason"] == "ambiguous_multiple_contract_markets_for_exact_identity"
        for row in snapshot["rejected_props"]
    )


def test_collector_output_is_accepted_by_frozen_step8a_contract_after_freshness():
    snapshot = _collect()
    payload = {
        "data_type": "mlb_player_prop_api_response_v1",
        "schema_version": 1,
        "source": snapshot["provider"],
        "collected_at_utc": snapshot["collected_at_utc"],
        "props": snapshot["props"],
    }
    state = build_player_prop_api_state(payload)
    assert state["integration_status"] == API_CONNECTED
    assert state["player_name_matching_used"] is False
    assert state["fuzzy_matching_allowed"] is False
    fresh = enforce_player_prop_api_freshness(state, as_of_utc=NOW)
    assert fresh["integration_status"] == API_CONNECTED
    assert fresh["feed_fresh"] is True
    assert fresh["usable_player_prop_count"] == 1


def test_api_endpoint_returns_exact_step8a_payload_shape(monkeypatch):
    snapshot = _collect()

    def fake_collect(**_kwargs):
        return snapshot

    monkeypatch.setattr(mlb_api, "collect_live_mlb_player_props", fake_collect)
    response = mlb_api.get_mlb_player_props(max_events=5)
    assert response["data_type"] == "mlb_player_prop_api_response_v1"
    assert response["schema_version"] == 1
    assert response["source"] == "FanDuel"
    assert response["prop_count"] == 1
    assert response["player_name_matching_used"] is False
    assert response["fuzzy_matching_used"] is False
    state = build_player_prop_api_state(response)
    assert state["integration_status"] == API_CONNECTED


def test_collector_requires_timezone_aware_now():
    with pytest.raises(ValueError, match="timezone-aware"):
        _collect(now_utc=datetime(2026, 8, 31, 21, 0))
