from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_espn_stat_split_v1 as transport


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_athlete_stats_requests_explicit_all_splits_first(monkeypatch) -> None:
    calls = []

    def fake_get(url: str, timeout: int = 8):
        calls.append(url)
        return {"splits": {"categories": []}}, {"ok": True, "http": 200, "url": url, "error": ""}

    monkeypatch.setattr(transport.profile, "_json_get", fake_get)
    transport.athlete_stats_payload.clear()
    payload, diag = transport.athlete_stats_payload(2025, 2, "3915511")

    assert payload == {"splits": {"categories": []}}
    assert calls == [
        "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2025/types/2/athletes/3915511/statistics/0"
    ]
    assert diag["split_zero"] is True
    assert diag["selected_url"].endswith("/statistics/0")


def test_team_stats_requests_explicit_all_splits_first(monkeypatch) -> None:
    calls = []

    def fake_get(url: str, timeout: int = 8):
        calls.append(url)
        return {"splits": {"categories": []}}, {"ok": True, "http": 200, "url": url, "error": ""}

    monkeypatch.setattr(transport.defense, "_json_get", fake_get)
    transport.team_stats_payload.clear()
    payload, diag = transport.team_stats_payload(2025, 2, "27")

    assert payload == {"splits": {"categories": []}}
    assert calls == [
        "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2025/types/2/teams/27/statistics/0"
    ]
    assert diag["split_zero"] is True


def test_split_transport_falls_back_to_legacy_statistics_resource(monkeypatch) -> None:
    calls = []

    def fake_get(url: str, timeout: int = 8):
        calls.append(url)
        if url.endswith("/0"):
            return {}, {"ok": False, "http": 404, "url": url, "error": "not found"}
        return {"splits": {"categories": []}}, {"ok": True, "http": 200, "url": url, "error": ""}

    monkeypatch.setattr(transport.profile, "_json_get", fake_get)
    transport.athlete_stats_payload.clear()
    payload, diag = transport.athlete_stats_payload(2025, 2, "3052587")

    assert payload == {"splits": {"categories": []}}
    assert len(calls) == 2
    assert calls[0].endswith("/statistics/0")
    assert calls[1].endswith("/statistics")
    assert diag["split_zero"] is False
    assert len(diag["attempts"]) == 2


def test_invalid_ids_fail_closed_without_request(monkeypatch) -> None:
    monkeypatch.setattr(transport.profile, "_json_get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not request")))
    monkeypatch.setattr(transport.defense, "_json_get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not request")))
    transport.athlete_stats_payload.clear()
    transport.team_stats_payload.clear()

    athlete, athlete_diag = transport.athlete_stats_payload(2025, 2, "fake")
    team, team_diag = transport.team_stats_payload(2025, 2, "")

    assert athlete == {}
    assert athlete_diag["ok"] is False
    assert "verified ESPN athlete id" in athlete_diag["error"]
    assert team == {}
    assert team_diag["ok"] is False
    assert "verified ESPN team id" in team_diag["error"]


def test_active_v17_wires_split_zero_transport_without_model_math_change() -> None:
    hub = _read("nfl_passing_yards_hub_v17.py")
    transport_src = _read("nfl_passing_yards_espn_stat_split_v1.py")

    assert "statistics/0" in hub
    assert "step7_ui.profile._season_stats_payload = stat_split.athlete_stats_payload" in hub
    assert "defense_v1._team_stats_payload = stat_split.team_stats_payload" in hub
    assert "step7_ui.profile._season_stats_payload = original_profile_season_loader" in hub
    assert "defense_v1._team_stats_payload = original_team_stats_loader" in hub
    assert "No sportsbook data is used" in transport_src
    assert "exactly 0.0" not in transport_src  # transport does not touch projection/market math
