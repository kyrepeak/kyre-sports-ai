from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from sports_api.collectors.mlb_fanduel_inplay import (
    collect_inplay_mlb_game_odds,
    normalize_inplay_core_markets,
)


GAME_ID = 824472
START = "2026-09-01T22:41:00.000Z"
NOW = datetime(2026, 9, 1, 23, 15, tzinfo=timezone.utc)


def _runner(role, odds, handicap=None):
    row = {
        "runnerStatus": "ACTIVE",
        "result": {"type": role},
        "runnerName": role.title(),
        "selectionId": f"sel-{role.lower()}",
        "winRunnerOdds": {
            "americanDisplayOdds": {"americanOddsInt": odds},
        },
    }
    if handicap is not None:
        row["handicap"] = handicap
    return row


def _market(name, roles, *, in_play=True, status="OPEN", market_id="m1"):
    return {
        "marketName": name,
        "marketStatus": status,
        "inPlay": in_play,
        "sortPriority": 1,
        "marketId": market_id,
        "marketTime": START,
        "runners": roles,
    }


def _core_markets(*, in_play=True):
    return [
        _market(
            "Moneyline",
            [_runner("AWAY", +125), _runner("HOME", -145)],
            in_play=in_play,
            market_id="ml",
        ),
        _market(
            "Run Line",
            [_runner("AWAY", -105, +1.5), _runner("HOME", -115, -1.5)],
            in_play=in_play,
            market_id="rl",
        ),
        _market(
            "Total Runs",
            [_runner("OVER", -110, 7.5), _runner("UNDER", -110, 7.5)],
            in_play=in_play,
            market_id="tot",
        ),
    ]


def _event(*, start=START):
    return {
        "eventId": "36014929",
        "name": "San Francisco Giants (L Webb) @ Pittsburgh Pirates (P Skenes)",
        "openDate": start,
    }


def _landing(events=None):
    rows = events if events is not None else [_event()]
    return {"attachments": {"events": rows}}


def _event_page(markets=None):
    return {"attachments": {"markets": markets if markets is not None else _core_markets()}}


def _schedule(game_id=GAME_ID):
    return {
        "dates": [
            {
                "games": [
                    {
                        "gamePk": game_id,
                        "gameDate": START,
                        "status": {
                            "detailedState": "In Progress",
                            "abstractGameState": "Live",
                        },
                        "teams": {
                            "away": {"team": {"id": 137, "name": "San Francisco Giants"}},
                            "home": {"team": {"id": 134, "name": "Pittsburgh Pirates"}},
                        },
                    }
                ]
            }
        ]
    }


def test_normalize_inplay_core_markets_requires_explicit_inplay_true():
    live = normalize_inplay_core_markets(_core_markets(in_play=True))
    assert set(live) == {"moneyline", "run_line", "total"}
    assert live["moneyline"]["away_odds"] == 125
    assert live["run_line"]["home_line"] == -1.5
    assert live["total"]["line"] == 7.5

    assert normalize_inplay_core_markets(_core_markets(in_play=False)) == {}


def test_suspended_market_is_not_treated_as_open_inplay():
    markets = _core_markets()
    markets[0]["marketStatus"] = "SUSPENDED"
    result = normalize_inplay_core_markets(markets)
    assert "moneyline" not in result
    assert set(result) == {"run_line", "total"}


def test_collector_returns_only_started_inplay_game_and_does_not_mutate_inputs():
    landing = _landing()
    page = _event_page()
    schedule = _schedule()
    originals = deepcopy((landing, page, schedule))

    result = collect_inplay_mlb_game_odds(
        now_utc=NOW,
        landing_fetcher=lambda: landing,
        event_fetcher=lambda event_id: page,
        schedule_fetcher=lambda slate_date: schedule,
    )

    assert result["data_type"] == "mlb_inplay_game_odds_snapshot_v1"
    assert result["market_phase"] == "IN_PLAY"
    assert result["candidate_started_event_count"] == 1
    assert result["matched_inplay_game_count"] == 1
    assert result["fuzzy_matching_used"] is False
    assert result["synthetic_game_id_used"] is False
    game = result["games"][0]
    assert game["official_game_id"] == GAME_ID
    assert game["in_play"] is True
    assert game["market_phase"] == "IN_PLAY"
    assert game["fully_priced"] is True
    assert game["official_schedule_match"] == "teams_exact"
    assert (landing, page, schedule) == originals


def test_future_event_is_never_candidate_for_inplay_collection():
    future = _event(start="2026-09-02T01:00:00.000Z")
    calls = []
    result = collect_inplay_mlb_game_odds(
        now_utc=NOW,
        landing_fetcher=lambda: _landing([future]),
        event_fetcher=lambda event_id: calls.append(event_id) or _event_page(),
        schedule_fetcher=lambda slate_date: _schedule(),
    )
    assert result["candidate_started_event_count"] == 0
    assert result["games"] == []
    assert calls == []


def test_pregame_only_event_page_fails_closed_per_event():
    result = collect_inplay_mlb_game_odds(
        now_utc=NOW,
        landing_fetcher=lambda: _landing(),
        event_fetcher=lambda event_id: _event_page(_core_markets(in_play=False)),
        schedule_fetcher=lambda slate_date: _schedule(),
    )
    assert result["games"] == []
    assert len(result["rejected_events"]) == 1
    assert "no OPEN in-play core markets" in result["rejected_events"][0]["reason"]


def test_exact_requested_official_game_id_filters_without_name_fallback():
    result = collect_inplay_mlb_game_odds(
        now_utc=NOW,
        official_game_id=GAME_ID + 1,
        landing_fetcher=lambda: _landing(),
        event_fetcher=lambda event_id: _event_page(),
        schedule_fetcher=lambda slate_date: _schedule(),
    )
    assert result["requested_official_game_id"] == GAME_ID + 1
    assert result["games"] == []
    assert result["matched_inplay_game_count"] == 0


def test_bool_official_game_id_is_rejected():
    with pytest.raises(ValueError, match="positive integer"):
        collect_inplay_mlb_game_odds(
            now_utc=NOW,
            official_game_id=True,
            landing_fetcher=lambda: _landing(),
        )


def test_collector_is_get_only_and_preserves_frozen_pregame_module_contract():
    import sports_api.collectors.mlb_fanduel_direct as pregame
    import sports_api.collectors.mlb_fanduel_inplay as inplay

    assert pregame.collect_live_mlb_game_odds.__doc__
    assert inplay.fetch_fanduel_mlb_landing is pregame.fetch_fanduel_mlb_landing
    assert inplay.fetch_fanduel_event_page is pregame.fetch_fanduel_event_page


def test_router_live_odds_response_and_exact_id_404(monkeypatch):
    import sports_api.api.mlb as mlb_api

    snapshot = collect_inplay_mlb_game_odds(
        now_utc=NOW,
        landing_fetcher=lambda: _landing(),
        event_fetcher=lambda event_id: _event_page(),
        schedule_fetcher=lambda slate_date: _schedule(),
    )
    monkeypatch.setattr(mlb_api, "collect_inplay_mlb_game_odds", lambda **kwargs: deepcopy(snapshot))

    payload = mlb_api.get_mlb_live_odds(
        official_game_id=GAME_ID,
        max_events=30,
        fully_priced_only=True,
    )
    assert payload["data_type"] == "mlb_inplay_odds_api_response_v1"
    assert payload["market_phase"] == "IN_PLAY"
    assert payload["requested_official_game_id"] == GAME_ID
    assert payload["game_count"] == 1
    assert payload["games"][0]["official_game_id"] == GAME_ID
    assert payload["fuzzy_matching_used"] is False
    assert payload["synthetic_game_id_used"] is False

    empty = deepcopy(snapshot)
    empty["games"] = []
    empty["matched_inplay_game_count"] = 0
    monkeypatch.setattr(mlb_api, "collect_inplay_mlb_game_odds", lambda **kwargs: deepcopy(empty))
    with pytest.raises(HTTPException) as excinfo:
        mlb_api.get_mlb_live_odds(
            official_game_id=GAME_ID,
            max_events=30,
            fully_priced_only=True,
        )
    assert excinfo.value.status_code == 404
