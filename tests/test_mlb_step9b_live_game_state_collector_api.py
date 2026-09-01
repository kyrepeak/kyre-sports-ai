from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from sports_api.api import mlb as mlb_api
from sports_api.collectors.mlb_live_game_state import (
    FINAL,
    LIVE,
    PREGAME,
    MLBLiveGameStateCollectorError,
    canonical_live_state,
    collect_live_mlb_game_state,
    normalize_live_feed,
    normalize_schedule_game,
)
from sports_api.mlb_step9a_live_game_state_api_contract_v1 import (
    API_CONNECTED,
    MATCH_METHOD,
    build_live_game_state_api_state,
    enforce_live_game_state_api_freshness,
    live_game_state_for_official_game_id,
)

NOW = datetime(2026, 9, 1, 6, 0, 0, tzinfo=timezone.utc)
GAME_LIVE = 823340
GAME_PRE = 823341
AWAY_ID = 110
HOME_ID = 111
BATTER_ID = 600001
PITCHER_ID = 600002
FIRST_ID = 600003


def _schedule_game(
    game_id: int,
    *,
    status: str,
    away_name: str = "Away Club",
    home_name: str = "Home Club",
    away_runs: int = 2,
    home_runs: int = 1,
):
    state = canonical_live_state(status)
    linescore = {
        "teams": {
            "away": {"runs": away_runs, "hits": 5, "errors": 0},
            "home": {"runs": home_runs, "hits": 4, "errors": 1},
        }
    }
    if state == LIVE:
        linescore.update(
            {
                "currentInningOrdinal": "5th",
                "currentInning": 5,
                "inningState": "Top",
                "balls": 1,
                "strikes": 2,
                "outs": 1,
            }
        )
    return {
        "gamePk": game_id,
        "gameDate": "2026-09-01T05:30:00Z",
        "status": {"detailedState": status},
        "teams": {
            "away": {
                "team": {"id": AWAY_ID, "name": away_name},
                "score": away_runs,
            },
            "home": {
                "team": {"id": HOME_ID, "name": home_name},
                "score": home_runs,
            },
        },
        "linescore": linescore,
    }


def _schedule_payload(*games):
    return {"dates": [{"date": "2026-09-01", "games": list(games)}]}


def _live_feed(
    game_id: int = GAME_LIVE,
    *,
    status: str = "In Progress",
    away_name: str = "Away Club",
    home_name: str = "Home Club",
):
    return {
        "gamePk": game_id,
        "gameData": {
            "status": {"detailedState": status},
            "teams": {
                "away": {"id": AWAY_ID, "name": away_name},
                "home": {"id": HOME_ID, "name": home_name},
            },
        },
        "liveData": {
            "linescore": {
                "currentInningOrdinal": "5th",
                "currentInning": 5,
                "inningState": "Top",
                "balls": 1,
                "strikes": 2,
                "outs": 1,
                "teams": {
                    "away": {"runs": 2, "hits": 5, "errors": 0},
                    "home": {"runs": 1, "hits": 4, "errors": 1},
                },
                "offense": {
                    "batter": {"id": BATTER_ID, "fullName": "Display Batter"},
                    "onDeck": {"id": 600004, "fullName": "On Deck"},
                    "inHole": {"id": 600005, "fullName": "In Hole"},
                    "first": {"id": FIRST_ID, "fullName": "Runner One"},
                },
                "defense": {
                    "pitcher": {"id": PITCHER_ID, "fullName": "Display Pitcher"},
                },
            },
            "plays": {
                "currentPlay": {
                    "matchup": {
                        "batter": {"id": BATTER_ID, "fullName": "Display Batter"},
                        "pitcher": {"id": PITCHER_ID, "fullName": "Display Pitcher"},
                    },
                    "count": {"balls": 1, "strikes": 2, "outs": 1},
                    "result": {"description": "Current live play"},
                    "playEvents": [
                        {
                            "isPitch": True,
                            "details": {
                                "description": "Called Strike",
                                "type": {"description": "Four-Seam Fastball"},
                            },
                            "pitchData": {"startSpeed": 96.4},
                        }
                    ],
                },
                "allPlays": [
                    {
                        "about": {"halfInning": "top", "inning": 4},
                        "result": {
                            "description": "Earlier play",
                            "awayScore": 1,
                            "homeScore": 1,
                        },
                    },
                    {
                        "about": {"halfInning": "top", "inning": 5},
                        "result": {
                            "description": "Latest play",
                            "awayScore": 2,
                            "homeScore": 1,
                        },
                    },
                ],
            },
        },
    }


def test_canonical_live_state_matches_frozen_v19_semantics():
    assert canonical_live_state("Scheduled") == PREGAME
    assert canonical_live_state("Warmup") == LIVE
    assert canonical_live_state("In Progress") == LIVE
    assert canonical_live_state("Manager Challenge") == LIVE
    assert canonical_live_state("Delayed") == "DELAYED"
    assert canonical_live_state("Final") == FINAL
    assert canonical_live_state("Game Over") == FINAL


def test_schedule_normalization_uses_official_gamepk_not_team_names():
    a = normalize_schedule_game(
        _schedule_game(GAME_PRE, status="Scheduled", away_name="Name A", home_name="Name B")
    )
    b = normalize_schedule_game(
        _schedule_game(GAME_PRE, status="Scheduled", away_name="Totally Different", home_name="Also Different")
    )
    assert a["official_game_id"] == b["official_game_id"] == GAME_PRE
    assert a["state"] == b["state"] == PREGAME
    assert a["away_team"] != b["away_team"]


def test_live_feed_normalization_emits_v19_state_fields_and_exact_ids():
    row = normalize_live_feed(_live_feed(), official_game_id=GAME_LIVE)
    assert row["official_game_id"] == GAME_LIVE
    assert row["state"] == LIVE
    assert row["away_runs"] == 2
    assert row["home_runs"] == 1
    assert row["inning"] == "5th"
    assert row["inning_state"] == "Top"
    assert (row["balls"], row["strikes"], row["outs"]) == (1, 2, 1)
    assert row["batter_id"] == BATTER_ID
    assert row["pitcher_id"] == PITCHER_ID
    assert row["runner_first_id"] == FIRST_ID
    assert row["runner_second_id"] is None
    assert row["last_pitch_speed"] == 96.4
    assert row["last_pitch_type"] == "Four-Seam Fastball"
    assert len(row["recent_plays"]) == 2


def test_live_feed_gamepk_mismatch_fails_closed():
    with pytest.raises(MLBLiveGameStateCollectorError, match="does not match"):
        normalize_live_feed(_live_feed(GAME_LIVE + 99), official_game_id=GAME_LIVE)


@pytest.mark.parametrize("bad_id", [823340.0, True, "+823340", "８２３３４０", 0, -1])
def test_collector_rejects_coercible_or_nonpositive_requested_identity(bad_id):
    with pytest.raises(MLBLiveGameStateCollectorError):
        collect_live_mlb_game_state(
            slate_date="2026-09-01",
            official_game_id=bad_id,
            now_utc=NOW,
            schedule_fetcher=lambda _day: _schedule_payload(),
            feed_fetcher=lambda _game_id: _live_feed(),
        )


def test_collector_fetches_detail_only_for_live_game_on_full_slate():
    schedule = _schedule_payload(
        _schedule_game(GAME_PRE, status="Scheduled"),
        _schedule_game(GAME_LIVE, status="In Progress"),
    )
    feed_calls = []

    def fetch_feed(game_id):
        feed_calls.append(game_id)
        return _live_feed(game_id)

    snapshot = collect_live_mlb_game_state(
        slate_date="2026-09-01",
        now_utc=NOW,
        schedule_fetcher=lambda _day: schedule,
        feed_fetcher=fetch_feed,
    )
    assert snapshot["game_count"] == 2
    assert snapshot["detailed_feed_count"] == 1
    assert feed_calls == [GAME_LIVE]
    assert [g["official_game_id"] for g in snapshot["games"]] == [GAME_PRE, GAME_LIVE]
    assert snapshot["team_name_matching_used"] is False
    assert snapshot["player_name_matching_used"] is False
    assert snapshot["fuzzy_matching_used"] is False
    assert snapshot["synthetic_game_id_used"] is False


def test_exact_selected_game_fetches_detailed_feed_even_when_pregame():
    schedule = _schedule_payload(_schedule_game(GAME_PRE, status="Scheduled"))
    pregame_feed = _live_feed(GAME_PRE, status="Scheduled")
    pregame_feed["liveData"]["linescore"].pop("currentInningOrdinal", None)
    pregame_feed["liveData"]["linescore"].pop("currentInning", None)
    pregame_feed["liveData"]["linescore"].pop("inningState", None)
    pregame_feed["liveData"]["plays"]["currentPlay"]["count"] = {}

    calls = []
    snapshot = collect_live_mlb_game_state(
        slate_date="2026-09-01",
        official_game_id=str(GAME_PRE),
        now_utc=NOW,
        schedule_fetcher=lambda _day: schedule,
        feed_fetcher=lambda game_id: calls.append(game_id) or pregame_feed,
    )
    assert calls == [GAME_PRE]
    assert snapshot["requested_official_game_id"] == GAME_PRE
    assert snapshot["game_count"] == 1
    assert snapshot["games"][0]["state"] == PREGAME


def test_wrong_selected_game_id_returns_empty_exact_candidate_set_without_name_fallback():
    schedule = _schedule_payload(
        _schedule_game(GAME_PRE, status="Scheduled", away_name="Same Team", home_name="Same Home")
    )
    snapshot = collect_live_mlb_game_state(
        slate_date="2026-09-01",
        official_game_id=999999,
        now_utc=NOW,
        schedule_fetcher=lambda _day: schedule,
        feed_fetcher=lambda _game_id: pytest.fail("feed should not be called"),
    )
    assert snapshot["candidate_game_count"] == 0
    assert snapshot["game_count"] == 0
    assert snapshot["games"] == []


def test_duplicate_official_schedule_gamepk_fails_closed_globally():
    duplicate = _schedule_game(GAME_PRE, status="Scheduled")
    with pytest.raises(MLBLiveGameStateCollectorError, match="duplicate official MLB gamePk"):
        collect_live_mlb_game_state(
            slate_date="2026-09-01",
            now_utc=NOW,
            schedule_fetcher=lambda _day: _schedule_payload(duplicate, deepcopy(duplicate)),
            feed_fetcher=lambda _game_id: _live_feed(),
        )


def test_live_feed_failure_is_isolated_and_invalid_live_row_is_not_emitted():
    schedule = _schedule_payload(
        _schedule_game(GAME_PRE, status="Scheduled"),
        _schedule_game(GAME_LIVE, status="In Progress"),
    )

    def fail_feed(_game_id):
        raise RuntimeError("upstream unavailable")

    snapshot = collect_live_mlb_game_state(
        slate_date="2026-09-01",
        now_utc=NOW,
        schedule_fetcher=lambda _day: schedule,
        feed_fetcher=fail_feed,
    )
    assert snapshot["game_count"] == 1
    assert snapshot["games"][0]["official_game_id"] == GAME_PRE
    assert snapshot["rejected_game_count"] == 1
    assert snapshot["rejected_games"][0]["official_game_id"] == GAME_LIVE


def test_collector_payload_passes_step9a_contract_and_exact_context_lookup():
    schedule = _schedule_payload(
        _schedule_game(GAME_PRE, status="Scheduled"),
        _schedule_game(GAME_LIVE, status="In Progress"),
    )
    snapshot = collect_live_mlb_game_state(
        slate_date="2026-09-01",
        now_utc=NOW,
        schedule_fetcher=lambda _day: schedule,
        feed_fetcher=lambda game_id: _live_feed(game_id),
    )
    payload = {
        "data_type": "mlb_live_game_state_api_response_v1",
        "schema_version": 1,
        "source": snapshot["provider"],
        "collected_at_utc": snapshot["collected_at_utc"],
        "games": snapshot["games"],
    }
    state = enforce_live_game_state_api_freshness(
        build_live_game_state_api_state(payload),
        as_of_utc=NOW,
    )
    assert state["integration_status"] == API_CONNECTED
    assert state["feed_fresh"] is True
    assert state["match_method"] == MATCH_METHOD
    context = live_game_state_for_official_game_id(
        state, official_game_id=GAME_LIVE
    )
    assert context is not None
    assert context["official_game_id"] == GAME_LIVE
    assert context["batter_id"] == BATTER_ID
    assert live_game_state_for_official_game_id(
        state, official_game_id=GAME_LIVE + 1
    ) is None


def _endpoint_snapshot(*, games=None, requested_id=None):
    rows = games if games is not None else [normalize_live_feed(_live_feed(), official_game_id=GAME_LIVE)]
    return {
        "provider": "MLB Stats API",
        "transport": "HTTPS GET",
        "http_methods": ["GET"],
        "collected_at_utc": NOW.isoformat().replace("+00:00", "Z"),
        "slate_date": "2026-09-01",
        "requested_official_game_id": requested_id,
        "schedule_game_count": 2,
        "candidate_game_count": len(rows),
        "detailed_feed_count": len(rows),
        "game_count": len(rows),
        "rejected_game_count": 0,
        "games": rows,
    }


def test_fastapi_endpoint_emits_exact_step9a_response_envelope(monkeypatch):
    calls = {}

    def fake_collect(**kwargs):
        calls.update(kwargs)
        return _endpoint_snapshot(requested_id=GAME_LIVE)

    monkeypatch.setattr(mlb_api, "collect_live_mlb_game_state", fake_collect)
    response = mlb_api.get_mlb_live_game_state(
        date="2026-09-01",
        official_game_id=GAME_LIVE,
        max_games=30,
    )
    assert response["data_type"] == "mlb_live_game_state_api_response_v1"
    assert response["schema_version"] == 1
    assert response["source"] == "MLB Stats API"
    assert response["requested_official_game_id"] == GAME_LIVE
    assert response["game_count"] == 1
    assert response["games"][0]["official_game_id"] == GAME_LIVE
    assert response["team_name_matching_used"] is False
    assert response["player_name_matching_used"] is False
    assert response["fuzzy_matching_used"] is False
    assert response["synthetic_game_id_used"] is False
    assert calls["official_game_id"] == GAME_LIVE
    assert calls["slate_date"] == "2026-09-01"

    state = enforce_live_game_state_api_freshness(
        build_live_game_state_api_state(response),
        as_of_utc=NOW,
    )
    assert state["integration_status"] == API_CONNECTED
    assert live_game_state_for_official_game_id(
        state, official_game_id=GAME_LIVE
    ) is not None


def test_endpoint_returns_404_for_missing_requested_exact_game(monkeypatch):
    monkeypatch.setattr(
        mlb_api,
        "collect_live_mlb_game_state",
        lambda **_kwargs: _endpoint_snapshot(games=[], requested_id=999999),
    )
    with pytest.raises(HTTPException) as exc:
        mlb_api.get_mlb_live_game_state(
            date="2026-09-01",
            official_game_id=999999,
            max_games=30,
        )
    assert exc.value.status_code == 404


def test_endpoint_returns_502_on_collector_failure(monkeypatch):
    def fail(**_kwargs):
        raise MLBLiveGameStateCollectorError("boom")

    monkeypatch.setattr(mlb_api, "collect_live_mlb_game_state", fail)
    with pytest.raises(HTTPException) as exc:
        mlb_api.get_mlb_live_game_state(
            date="2026-09-01",
            official_game_id=GAME_LIVE,
            max_games=30,
        )
    assert exc.value.status_code == 502
    assert exc.value.detail == "MLB live game state collection failed."


def test_router_contains_only_get_for_step9b_endpoint():
    matches = [
        route
        for route in mlb_api.router.routes
        if getattr(route, "path", None) == "/api/v1/mlb/live-game-state"
    ]
    assert len(matches) == 1
    assert matches[0].methods == {"GET"}
