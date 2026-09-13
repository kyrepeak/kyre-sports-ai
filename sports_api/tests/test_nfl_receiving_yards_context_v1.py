from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json
import threading
import time
from urllib.error import HTTPError

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from sports_api.api import nfl_receiving_yards_context_v1 as route
from sports_api.collectors import nfl_receiving_yards_context_v1 as collector


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


def _receiving_block(
    team_id: str,
    athlete_id: str,
    name: str,
    receptions: str,
    yards: str,
    touchdowns: str,
    targets: str | None,
) -> dict:
    labels = ["REC", "YDS", "AVG", "TD", "LONG"]
    stats = [receptions, yards, "15.0", touchdowns, "32"]
    if targets is not None:
        labels.append("TGTS")
        stats.append(targets)
    return {
        "team": {"id": team_id},
        "statistics": [{
            "name": "receiving",
            "labels": labels,
            "athletes": [{
                "athlete": {"id": athlete_id, "displayName": name},
                "stats": stats,
            }],
        }],
    }


def _old_game(
    team_id: str,
    opponent_id: str,
    athlete_id: str,
    name: str,
    receptions: str,
    yards: str,
    targets: str | None,
    *,
    opponent_athlete_id: str,
    opponent_receptions: str,
    opponent_yards: str,
    opponent_targets: str | None,
) -> dict:
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
            "players": [
                _receiving_block(team_id, athlete_id, name, receptions, yards, "1", targets),
                _receiving_block(
                    opponent_id,
                    opponent_athlete_id,
                    "Opponent Receiver",
                    opponent_receptions,
                    opponent_yards,
                    "1",
                    opponent_targets,
                ),
            ]
        },
    }


def _schedule_event(
    event_id: str,
    *,
    year: int,
    season_type: int = 2,
    completed: bool = True,
    state: str = "post",
) -> dict:
    return {
        "id": event_id,
        "date": f"{year}-12-01T18:00Z",
        "season": {"year": year, "displayName": str(year)},
        "seasonType": {
            "id": str(season_type),
            "type": season_type,
            "name": "Regular Season" if season_type == 2 else "Other",
        },
        "competitions": [{"status": {"type": {"state": state, "completed": completed}}}],
    }


def _install_fake_espn(monkeypatch) -> None:
    # Team 27 offense: 5-80-1 on 7 explicit targets. Its opponent produced
    # 10-150-1 on 14 targets, which becomes Team 27 pass-defense context.
    old27 = _old_game(
        "27", "1", "100", "Receiver One", "5", "80", "7",
        opponent_athlete_id="901",
        opponent_receptions="10",
        opponent_yards="150",
        opponent_targets="14",
    )
    # Team 4 offense: 6-90-1 on 8 targets. Its opponent produced 8-120-1 on
    # 11 targets, which becomes Team 4 pass-defense context.
    old4 = _old_game(
        "4", "2", "200", "Receiver Two", "6", "90", "8",
        opponent_athlete_id="902",
        opponent_receptions="8",
        opponent_yards="120",
        opponent_targets="11",
    )

    def fake_get(url, params=None):
        params = params or {}
        if url.endswith("/summary"):
            event = str(params.get("event") or "")
            if event == "401900001":
                return _pregame()
            if event == "90027":
                return old27
            if event == "90004":
                return old4
        if url.endswith("/teams/27/roster"):
            return {"athletes": [{"items": [
                {"id": "100", "displayName": "Receiver One", "position": {"abbreviation": "WR"}},
                {"id": "999", "displayName": "Quarterback", "position": {"abbreviation": "QB"}},
            ]}]}
        if url.endswith("/teams/4/roster"):
            return {"athletes": [{"items": [
                {"id": "200", "displayName": "Receiver Two", "position": {"abbreviation": "TE"}},
            ]}]}
        if "/schedule" in url:
            assert int(params.get("seasontype") or 0) == 2
            team = url.split("/teams/", 1)[1].split("/", 1)[0]
            season = int(params.get("season") or 0)
            if season == 2026:
                return {"season": {"year": 2026}, "events": []}
            event_id = "90027" if team == "27" else "90004"
            return {
                "season": {"year": 2026, "type": 2},
                "requestedSeason": {"year": 2025},
                "events": [_schedule_event(event_id, year=2025)],
            }
        raise AssertionError(f"unexpected ESPN call: {url} {params}")

    monkeypatch.setattr(collector, "_get_json", fake_get)


class _BytesResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _limit=None):
        return self._raw


def _http_error(url: str, code: int) -> HTTPError:
    return HTTPError(url, code, "transport failure", {}, io.BytesIO(b"{}"))


def _valid_payload(event_id: str = "401872925", *, ready: bool = True, marker: int = 1) -> dict:
    def team(team_id: str, opponent_id: str, athlete_id: str, name: str, position: str) -> dict:
        return {
            "official_team_id": team_id,
            "opponent_official_team_id": opponent_id,
            "team_name": name,
            "players": [{
                "official_team_id": team_id,
                "official_athlete_id": athlete_id,
                "player_name": f"Player {athlete_id}",
                "position": position,
                "sample_games": 1,
                "receptions": 5,
                "receiving_yards": 80,
                "yards_per_reception": 16.0,
                "receptions_per_game": 5.0,
                "receiving_yards_per_game": 80.0,
                "receiving_touchdowns": 1,
                "targets_data_available": True,
                "target_sample_games": 1,
                "targets": 7,
                "targets_per_game": 7.0,
                "baseline_season": 2025,
            }],
            "opponent_pass_defense": {
                "official_team_id": opponent_id,
                "baseline_season": 2025,
                "sample_games": 1,
                "receptions_allowed_per_game": 20.0,
                "receiving_yards_allowed_per_game": 220.0,
                "yards_per_reception_allowed": 11.0,
                "receiving_touchdowns_allowed_per_game": 1.0,
                "targets_data_available": True,
                "target_sample_games": 1,
                "targets_allowed_per_game": 28.0,
                "data_available": True,
            },
        }

    return {
        "schema_version": "nfl_receiving_yards_context_v1",
        "ready": ready,
        "official_event_id": event_id,
        "captured_at_utc": f"2026-09-13T16:00:{marker:02d}+00:00",
        "official_authority": "ESPN",
        "season": 2026,
        "teams": [
            team("27", "4", "100", "Tampa Bay Buccaneers", "WR"),
            team("4", "27", "200", "Cincinnati Bengals", "TE"),
        ],
        "identity": {
            "official_event_id_required": True,
            "official_athlete_id_required": True,
            "official_team_id_required": True,
            "player_name_display_only": True,
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "semantics": {
            "model_enabled": False,
            "projection_enabled": False,
            "market_enabled": False,
            "sportsbook_influence": 0.0,
            "stake_sizing_enabled": False,
            "wager_actions": False,
            "targets_inferred": False,
        },
    }


def test_receiving_rows_maps_labels_and_accepts_explicit_targets_only():
    summary = {
        "boxscore": {"players": [{
            "team": {"id": "27"},
            "statistics": [{
                "name": "receiving",
                "labels": ["YDS", "REC", "TGTS", "TD", "AVG"],
                "athletes": [{
                    "athlete": {"id": "100"},
                    "stats": ["84", "6", "9", "1", "14.0"],
                }],
            }],
        }]}
    }
    row = collector._receiving_rows(summary, "27")[0]
    assert row == {
        "official_athlete_id": "100",
        "receptions": 6.0,
        "yards": 84.0,
        "touchdowns": 1.0,
        "targets": 9.0,
        "targets_explicit": True,
    }


def test_receiving_rows_never_infers_targets_when_column_is_absent():
    summary = {
        "boxscore": {"players": [{
            "team": {"id": "27"},
            "statistics": [{
                "name": "receiving",
                "labels": ["REC", "YDS", "AVG", "TD"],
                "athletes": [{
                    "athlete": {"id": "100"},
                    "stats": ["6", "84", "14.0", "1"],
                }],
            }],
        }]}
    }
    row = collector._receiving_rows(summary, "27")[0]
    assert row["receptions"] == 6.0
    assert row["yards"] == 84.0
    assert row["targets"] is None
    assert row["targets_explicit"] is False


def test_get_json_primary_http_error_uses_same_path_and_query_on_alternate(monkeypatch):
    seen: list[str] = []
    event_id = "401872925"

    def fake_urlopen(request, timeout):
        assert timeout == collector.DEFAULT_TIMEOUT_SECONDS
        target = request.full_url
        seen.append(target)
        if len(seen) == 1:
            raise _http_error(target, 403)
        return _BytesResponse({"header": {"id": event_id}})

    monkeypatch.setattr(collector, "urlopen", fake_urlopen)
    payload = collector._get_json(
        f"{collector.ESPN_SITE_BASE}/summary",
        {"event": event_id},
    )
    assert payload["header"]["id"] == event_id
    assert seen == [
        f"{collector.ESPN_SITE_BASE}/summary?event={event_id}",
        f"{collector.ESPN_SITE_ALTERNATE_BASE}/summary?event={event_id}",
    ]


def test_get_json_both_certified_transports_fail_closed(monkeypatch):
    seen: list[str] = []

    def fake_urlopen(request, timeout):
        target = request.full_url
        seen.append(target)
        raise _http_error(target, 403 if len(seen) == 1 else 429)

    monkeypatch.setattr(collector, "urlopen", fake_urlopen)
    try:
        collector._get_json(f"{collector.ESPN_SITE_BASE}/summary", {"event": "401872925"})
    except collector.NFLReceivingYardsContextError as exc:
        message = str(exc)
        assert "both certified transports" in message
        assert "primary HTTP 403" in message
        assert "alternate HTTP 429" in message
    else:
        raise AssertionError("dual ESPN transport failure did not fail closed")


def test_completed_game_ids_uses_event_level_year_and_regular_season(monkeypatch):
    def fake_get(url, params=None):
        return {
            "season": {"year": 2026, "type": 2},
            "events": [
                _schedule_event("401772830", year=2025),
                _schedule_event("401900001", year=2026),
                _schedule_event("401888888", year=2025, season_type=3),
                _schedule_event("401777777", year=2025, completed=False, state="pre"),
            ],
        }

    monkeypatch.setattr(collector, "_get_json", fake_get)
    assert collector._completed_game_ids("27", 2025) == ["401772830"]


def test_collector_exact_id_prior_season_fallback_and_pass_defense(monkeypatch):
    _install_fake_espn(monkeypatch)
    payload = collector.collect_nfl_receiving_yards_context("401900001")

    assert payload["schema_version"] == "nfl_receiving_yards_context_v1"
    assert payload["official_event_id"] == "401900001"
    assert payload["ready"] is True
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
        "targets_inferred": False,
    }

    by_team = {team["official_team_id"]: team for team in payload["teams"]}
    player = by_team["27"]["players"][0]
    assert player["official_athlete_id"] == "100"
    assert player["position"] == "WR"
    assert player["receptions"] == 5
    assert player["receiving_yards"] == 80
    assert player["yards_per_reception"] == 16.0
    assert player["targets_data_available"] is True
    assert player["targets"] == 7
    assert player["targets_per_game"] == 7.0
    assert by_team["27"]["player_baseline_season"] == 2025
    assert by_team["27"]["player_sample_games"] == 1

    defense = by_team["27"]["opponent_pass_defense"]
    assert defense["official_team_id"] == "4"
    assert defense["baseline_season"] == 2025
    assert defense["sample_games"] == 1
    assert defense["receptions_allowed_per_game"] == 8.0
    assert defense["receiving_yards_allowed_per_game"] == 120.0
    assert defense["yards_per_reception_allowed"] == 15.0
    assert defense["targets_data_available"] is True
    assert defense["targets_allowed_per_game"] == 11.0


def test_pass_defense_withholds_targets_when_any_receiving_row_lacks_explicit_target():
    summary = {
        "header": {"competitions": [{"competitors": [
            {"team": {"id": "4"}}, {"team": {"id": "2"}},
        ]}]},
        "boxscore": {"players": [{
            "team": {"id": "2"},
            "statistics": [{
                "name": "receiving",
                "labels": ["REC", "YDS", "TD", "TGTS"],
                "athletes": [
                    {"athlete": {"id": "901"}, "stats": ["5", "70", "1", "8"]},
                    {"athlete": {"id": "902"}, "stats": ["3", "40", "0"]},
                ],
            }],
        }]},
    }
    memo = {"90004": summary}
    defense = collector._pass_defense_from_games("4", 2025, ["90004"], memo)
    assert defense["data_available"] is True
    assert defense["receptions_allowed_per_game"] == 8.0
    assert defense["receiving_yards_allowed_per_game"] == 110.0
    assert defense["targets_data_available"] is False
    assert defense["target_sample_games"] == 0
    assert defense["targets_allowed_per_game"] is None


def test_summary_prefetch_uses_bounded_parallel_workers(monkeypatch):
    active = 0
    peak = 0
    lock = threading.Lock()

    def fake_get(url, params=None):
        nonlocal active, peak
        event_id = str((params or {}).get("event") or "")
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.04)
        with lock:
            active -= 1
        return {"header": {"id": event_id}}

    monkeypatch.setattr(collector, "_get_json", fake_get)
    memo: dict[str, dict] = {}
    event_ids = ["90001", "90002", "90003", "90004"]
    collector._prefetch_summaries(event_ids, memo)
    assert set(memo) == set(event_ids)
    assert 2 <= peak <= collector.MAX_PARALLEL_ESPN_REQUESTS


def test_collector_fetches_each_team_baseline_once(monkeypatch):
    baseline_calls: list[tuple[str, int]] = []
    roster_calls: list[str] = []
    summary_calls: list[str] = []
    lock = threading.Lock()

    rosters = {
        "27": {"100": {"official_athlete_id": "100", "player_name": "Receiver One", "position": "WR"}},
        "4": {"200": {"official_athlete_id": "200", "player_name": "Receiver Two", "position": "TE"}},
    }
    games = {
        "90027": _old_game(
            "27", "1", "100", "Receiver One", "5", "80", "7",
            opponent_athlete_id="901", opponent_receptions="10", opponent_yards="150", opponent_targets="14",
        ),
        "90004": _old_game(
            "4", "2", "200", "Receiver Two", "6", "90", "8",
            opponent_athlete_id="902", opponent_receptions="8", opponent_yards="120", opponent_targets="11",
        ),
    }

    def fake_roster(team_id: str):
        with lock:
            roster_calls.append(team_id)
        return rosters[team_id]

    def fake_baseline(team_id: str, season: int):
        with lock:
            baseline_calls.append((team_id, season))
        return 2025, ["90027" if team_id == "27" else "90004"]

    def fake_get(url, params=None):
        event_id = str((params or {}).get("event") or "")
        with lock:
            summary_calls.append(event_id)
        return _pregame() if event_id == "401900001" else games[event_id]

    monkeypatch.setattr(collector, "_roster", fake_roster)
    monkeypatch.setattr(collector, "_baseline_game_ids", fake_baseline)
    monkeypatch.setattr(collector, "_get_json", fake_get)

    payload = collector.collect_nfl_receiving_yards_context("401900001")
    assert sorted(roster_calls) == ["27", "4"]
    assert sorted(baseline_calls) == [("27", 2026), ("4", 2026)]
    assert summary_calls.count("401900001") == 1
    assert summary_calls.count("90027") == 1
    assert summary_calls.count("90004") == 1
    assert [team["official_team_id"] for team in payload["teams"]] == ["27", "4"]


def test_parallel_input_failure_still_fails_closed(monkeypatch):
    def fake_roster(team_id: str):
        if team_id == "4":
            raise collector.NFLReceivingYardsContextError("current ESPN receiving roster unavailable for team 4")
        return {"100": {"official_athlete_id": "100", "player_name": "Receiver One", "position": "WR"}}

    monkeypatch.setattr(collector, "_roster", fake_roster)
    monkeypatch.setattr(collector, "_baseline_game_ids", lambda team_id, season: (season, []))
    try:
        collector._parallel_team_inputs(["27", "4"], 2026)
    except collector.NFLReceivingYardsContextError as exc:
        assert "roster unavailable for team 4" in str(exc)
    else:
        raise AssertionError("parallel roster failure did not fail closed")


def test_route_status_contract_is_exact_id_target_explicit_and_market_blind():
    app = FastAPI()
    app.include_router(route.router)
    response = TestClient(app).get("/api/v1/nfl/receiving-yards/status")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "nfl_receiving_yards_context_v1"
    assert body["official_event_id_required"] is True
    assert body["official_athlete_id_required"] is True
    assert body["official_team_id_required"] is True
    assert body["eligible_positions"] == ["FB", "RB", "TE", "WR"]
    assert body["targets_explicit_only"] is True
    assert body["targets_inferred"] is False
    assert body["player_name_matching"] is False
    assert body["fuzzy_matching"] is False
    assert body["model_enabled"] is False
    assert body["projection_enabled"] is False
    assert body["market_enabled"] is False
    assert body["sportsbook_influence"] == 0.0
    assert body["stake_sizing_enabled"] is False
    assert body["wager_actions"] is False


def test_route_returns_exact_id_context(monkeypatch):
    route._clear_context_snapshot_cache()
    _install_fake_espn(monkeypatch)
    app = FastAPI()
    app.include_router(route.router)
    response = TestClient(app).get(
        "/api/v1/nfl/receiving-yards",
        params={"event_id": "401900001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["official_event_id"] == "401900001"
    athlete_ids = [p["official_athlete_id"] for team in body["teams"] for p in team["players"]]
    assert athlete_ids == ["100", "200"]
    assert len(set(athlete_ids)) == len(athlete_ids)


def test_route_rejects_inferred_target_payload(monkeypatch):
    route._clear_context_snapshot_cache()
    payload = _valid_payload()
    payload["teams"][0]["players"][0]["targets_data_available"] = False
    # Leaving numeric targets behind must fail closed instead of silently
    # presenting an inferred target value.
    monkeypatch.setattr(route, "collect_nfl_receiving_yards_context", lambda event_id: deepcopy(payload))
    try:
        route._collect_or_reuse_context("401872925")
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "inferred-target contract failed closed" in str(exc.detail)
    else:
        raise AssertionError("inferred target payload did not fail closed")


def test_route_rejects_weakened_semantics(monkeypatch):
    route._clear_context_snapshot_cache()
    payload = _valid_payload()
    payload["semantics"]["market_enabled"] = True
    monkeypatch.setattr(route, "collect_nfl_receiving_yards_context", lambda event_id: deepcopy(payload))
    try:
        route._collect_or_reuse_context("401872925")
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "safety contract failed closed" in str(exc.detail)
    else:
        raise AssertionError("weakened semantics did not fail closed")


def test_exact_event_cache_reuses_payload_and_returns_deep_copies(monkeypatch):
    route._clear_context_snapshot_cache()
    calls = 0

    def fake_collect(event_id: str):
        nonlocal calls
        calls += 1
        return _valid_payload(event_id, marker=calls)

    monkeypatch.setattr(route, "collect_nfl_receiving_yards_context", fake_collect)
    first = route._collect_or_reuse_context("401872925")
    first["teams"][0]["team_name"] = "MUTATED"
    second = route._collect_or_reuse_context("401872925")
    assert calls == 1
    assert second["teams"][0]["team_name"] == "Tampa Bay Buccaneers"
    assert second["captured_at_utc"] == "2026-09-13T16:00:01+00:00"


def test_snapshot_expiry_and_non_ready_payload_behavior(monkeypatch):
    route._clear_context_snapshot_cache()
    clock = [100.0]
    calls = 0
    monkeypatch.setattr(route, "monotonic", lambda: clock[0])

    def fake_collect(event_id: str):
        nonlocal calls
        calls += 1
        return _valid_payload(event_id, marker=calls)

    monkeypatch.setattr(route, "collect_nfl_receiving_yards_context", fake_collect)
    route._collect_or_reuse_context("401872925")
    clock[0] = 159.9
    route._collect_or_reuse_context("401872925")
    assert calls == 1
    clock[0] = 160.01
    route._collect_or_reuse_context("401872925")
    assert calls == 2

    route._clear_context_snapshot_cache()
    calls = 0

    def fake_not_ready(event_id: str):
        nonlocal calls
        calls += 1
        return _valid_payload(event_id, ready=False, marker=calls)

    monkeypatch.setattr(route, "collect_nfl_receiving_yards_context", fake_not_ready)
    route._collect_or_reuse_context("401872925")
    route._collect_or_reuse_context("401872925")
    assert calls == 2


def test_cached_payload_is_revalidated_and_fails_closed(monkeypatch):
    route._clear_context_snapshot_cache()
    monkeypatch.setattr(route, "collect_nfl_receiving_yards_context", lambda event_id: _valid_payload(event_id))
    route._collect_or_reuse_context("401872925")

    with route._CACHE_LOCK:
        expires_at, collector_id, cached = route._CONTEXT_SNAPSHOT_CACHE["401872925"]
        weakened = deepcopy(cached)
        weakened["semantics"]["targets_inferred"] = True
        route._CONTEXT_SNAPSHOT_CACHE["401872925"] = (expires_at, collector_id, weakened)

    try:
        route._collect_or_reuse_context("401872925")
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "safety contract failed closed" in str(exc.detail)
    else:
        raise AssertionError("weakened cached payload did not fail closed")


def test_same_event_concurrent_requests_single_flight(monkeypatch):
    route._clear_context_snapshot_cache()
    calls = 0
    lock = threading.Lock()

    def fake_collect(event_id: str):
        nonlocal calls
        with lock:
            calls += 1
            marker = calls
        time.sleep(0.08)
        return _valid_payload(event_id, marker=marker)

    monkeypatch.setattr(route, "collect_nfl_receiving_yards_context", fake_collect)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: route._collect_or_reuse_context("401872925"), range(6)))
    assert calls == 1
    assert all(row["captured_at_utc"] == "2026-09-13T16:00:01+00:00" for row in results)


def test_collector_swap_invalidates_existing_snapshot(monkeypatch):
    route._clear_context_snapshot_cache()
    calls = {"a": 0, "b": 0}

    def collector_a(event_id: str):
        calls["a"] += 1
        return _valid_payload(event_id, marker=1)

    def collector_b(event_id: str):
        calls["b"] += 1
        return _valid_payload(event_id, marker=2)

    monkeypatch.setattr(route, "collect_nfl_receiving_yards_context", collector_a)
    first = route._collect_or_reuse_context("401872925")
    monkeypatch.setattr(route, "collect_nfl_receiving_yards_context", collector_b)
    second = route._collect_or_reuse_context("401872925")
    assert calls == {"a": 1, "b": 1}
    assert first["captured_at_utc"] != second["captured_at_utc"]


def test_cache_contract_is_short_exact_event_and_market_blind():
    assert route.CONTEXT_SNAPSHOT_TTL_SECONDS == 60.0
    assert route.CONTRACT["official_event_id_required"] is True
    assert route.CONTRACT["player_name_matching"] is False
    assert route.CONTRACT["fuzzy_matching"] is False
    assert route.CONTRACT["synthetic_event_ids"] is False
    assert route.CONTRACT["synthetic_player_ids"] is False
    assert route.CONTRACT["targets_explicit_only"] is True
    assert route.CONTRACT["targets_inferred"] is False
    assert route.CONTRACT["projection_enabled"] is False
    assert route.CONTRACT["market_enabled"] is False
    assert route.CONTRACT["sportsbook_influence"] == 0.0
