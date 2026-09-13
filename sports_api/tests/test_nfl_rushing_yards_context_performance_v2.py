from __future__ import annotations

import threading
import time

from sports_api.collectors import nfl_rushing_yards_context_v1 as collector


def _pregame() -> dict:
    return {
        "header": {
            "id": "401900001",
            "season": {"year": 2026, "type": 2},
            "competitions": [{
                "competitors": [
                    {"homeAway": "away", "team": {"id": "27", "displayName": "Tampa Bay Buccaneers", "abbreviation": "TB"}},
                    {"homeAway": "home", "team": {"id": "4", "displayName": "Cincinnati Bengals", "abbreviation": "CIN"}},
                ]
            }],
        }
    }


def _game(team_id: str, opponent_id: str, athlete_id: str, attempts: str, yards: str) -> dict:
    return {
        "header": {
            "competitions": [{
                "competitors": [
                    {"team": {"id": team_id}},
                    {"team": {"id": opponent_id}},
                ]
            }]
        },
        "boxscore": {
            "players": [{
                "team": {"id": team_id},
                "statistics": [{
                    "name": "rushing",
                    "labels": ["CAR", "YDS", "AVG", "TD", "LONG"],
                    "athletes": [{
                        "athlete": {"id": athlete_id},
                        "stats": [attempts, yards, "4.5", "1", "18"],
                    }],
                }],
            }],
            "teams": [
                {"team": {"id": team_id}, "statistics": [
                    {"name": "rushingAttempts", "displayValue": attempts},
                    {"name": "rushingYards", "displayValue": yards},
                    {"name": "rushingTouchdowns", "displayValue": "1"},
                ]},
                {"team": {"id": opponent_id}, "statistics": [
                    {"name": "rushingAttempts", "displayValue": "24"},
                    {"name": "rushingYards", "displayValue": "108"},
                    {"name": "rushingTouchdowns", "displayValue": "1"},
                ]},
            ],
        },
    }


def test_summary_prefetch_uses_bounded_parallel_workers(monkeypatch):
    active = 0
    peak = 0
    lock = threading.Lock()

    def fake_get(url, params=None):
        nonlocal active, peak
        assert url.endswith("/summary")
        event_id = str((params or {}).get("event") or "")
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return {"header": {"id": event_id}}

    monkeypatch.setattr(collector, "_get_json", fake_get)
    memo: dict[str, dict] = {}
    event_ids = ["90001", "90002", "90003", "90004"]
    collector._prefetch_summaries(event_ids, memo)

    assert set(memo) == set(event_ids)
    assert peak >= 2
    assert peak <= collector.MAX_PARALLEL_ESPN_REQUESTS


def test_collector_fetches_each_team_baseline_once_and_preserves_order(monkeypatch):
    baseline_calls: list[tuple[str, int]] = []
    roster_calls: list[str] = []
    summary_calls: list[str] = []
    call_lock = threading.Lock()

    rosters = {
        "27": {"100": {"official_athlete_id": "100", "player_name": "Runner One", "position": "RB"}},
        "4": {"200": {"official_athlete_id": "200", "player_name": "Runner Two", "position": "RB"}},
    }
    game_payloads = {
        "90027": _game("27", "1", "100", "20", "100"),
        "90004": _game("4", "2", "200", "18", "81"),
    }

    def fake_roster(team_id: str):
        with call_lock:
            roster_calls.append(team_id)
        return rosters[team_id]

    def fake_baseline(team_id: str, season: int):
        with call_lock:
            baseline_calls.append((team_id, season))
        return 2025, ["90027" if team_id == "27" else "90004"]

    def fake_get(url, params=None):
        assert url.endswith("/summary")
        event_id = str((params or {}).get("event") or "")
        with call_lock:
            summary_calls.append(event_id)
        if event_id == "401900001":
            return _pregame()
        return game_payloads[event_id]

    monkeypatch.setattr(collector, "_roster", fake_roster)
    monkeypatch.setattr(collector, "_baseline_game_ids", fake_baseline)
    monkeypatch.setattr(collector, "_get_json", fake_get)

    payload = collector.collect_nfl_rushing_yards_context("401900001")

    assert sorted(roster_calls) == ["27", "4"]
    assert sorted(baseline_calls) == [("27", 2026), ("4", 2026)]
    assert summary_calls.count("401900001") == 1
    assert summary_calls.count("90027") == 1
    assert summary_calls.count("90004") == 1

    # Parallel acquisition must not alter the authoritative event/team order.
    assert [team["official_team_id"] for team in payload["teams"]] == ["27", "4"]
    by_team = {team["official_team_id"]: team for team in payload["teams"]}
    assert by_team["27"]["players"][0]["official_athlete_id"] == "100"
    assert by_team["27"]["players"][0]["carries"] == 20
    assert by_team["27"]["opponent_run_front"]["official_team_id"] == "4"
    assert by_team["4"]["players"][0]["official_athlete_id"] == "200"
    assert by_team["4"]["players"][0]["carries"] == 18
    assert by_team["4"]["opponent_run_front"]["official_team_id"] == "27"

    assert payload["identity"]["player_name_matching"] is False
    assert payload["identity"]["fuzzy_matching"] is False
    assert payload["identity"]["synthetic_event_ids"] is False
    assert payload["identity"]["synthetic_player_ids"] is False
    assert payload["semantics"] == {
        "model_enabled": False,
        "projection_enabled": False,
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


def test_parallel_input_failure_still_fails_closed(monkeypatch):
    def fake_roster(team_id: str):
        if team_id == "4":
            raise collector.NFLRushingYardsContextError("current ESPN roster unavailable for team 4")
        return {"100": {"official_athlete_id": "100", "player_name": "Runner One", "position": "RB"}}

    monkeypatch.setattr(collector, "_roster", fake_roster)
    monkeypatch.setattr(collector, "_baseline_game_ids", lambda team_id, season: (season, []))

    try:
        collector._parallel_team_inputs(["27", "4"], 2026)
    except collector.NFLRushingYardsContextError as exc:
        assert "roster unavailable for team 4" in str(exc)
    else:
        raise AssertionError("parallel roster failure did not fail closed")
