from __future__ import annotations

from pathlib import Path

import pytest

from sports_api import nfl_rushing_yards_data_truth_v1 as data_truth
from sports_api import nfl_rushing_yards_fastpath_v1 as fastpath
from sports_api.collectors import nfl_fanduel_rushing_yards_nflverse_v1 as market_adapter

ROOT = Path(__file__).resolve().parents[1]


def test_exact_identity_normalizers_bridge_provider_and_roster_serialization_only() -> None:
    assert market_adapter._normalize_team("WSH") == "WAS"
    assert market_adapter._normalize_team("JAC") == "JAX"
    assert market_adapter._normalize_team("LA") == "LAR"
    assert market_adapter._normalize_jersey("87.0") == "87"
    assert market_adapter._normalize_jersey(0.0) == "0"
    assert market_adapter._normalize_jersey(" 14 ") == "14"
    assert market_adapter._normalize_position("Running Back") == "RB"
    assert market_adapter._normalize_position("Halfback") == "RB"
    assert market_adapter._normalize_position("Fullback") == "FB"


def test_market_reconciliation_accepts_unique_exact_identity_after_canonical_normalization() -> None:
    observation = {"team_abbr": "WSH", "jersey_number": "24", "position": "Running Back"}
    roster = [{
        "team_abbr": "WAS",
        "jersey_number": "24.0",
        "position": "RB",
        "active": True,
        "canonical_player_id": "kyre:nfl:player:00-TEST",
    }]
    match = market_adapter.reconcile_observation_to_roster(observation, roster)
    assert match is not None
    assert match["canonical_player_id"] == "kyre:nfl:player:00-TEST"


def test_market_reconciliation_still_fails_closed_on_ambiguous_exact_identity() -> None:
    observation = {"team_abbr": "ARI", "jersey_number": "1", "position": "RB"}
    roster = [
        {"team_abbr": "ARI", "jersey_number": "1.0", "position": "RB", "active": True},
        {"team_abbr": "ARI", "jersey_number": "1", "position": "Running Back", "active": True},
    ]
    assert market_adapter.reconcile_observation_to_roster(observation, roster) is None


def test_transient_read_retries_once_and_timeout_is_floored(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_get_json(_url, _params=None, *, timeout):
        calls.append(int(timeout))
        if len(calls) == 1:
            raise market_adapter.base.FanDuelPassingYardsError("FanDuel read failed: TimeoutError")
        return {"ok": True}

    monkeypatch.setattr(market_adapter.base, "_get_json", fake_get_json)
    assert market_adapter._get_json_reliable("https://provider.test", timeout=4) == {"ok": True}
    assert calls == [8, 8]


def test_deterministic_provider_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_get_json(_url, _params=None, *, timeout):
        nonlocal calls
        calls += 1
        raise market_adapter.base.FanDuelPassingYardsError("FanDuel GET returned HTTP 403")

    monkeypatch.setattr(market_adapter.base, "_get_json", fake_get_json)
    with pytest.raises(market_adapter.base.FanDuelPassingYardsError, match="HTTP 403"):
        market_adapter._get_json_reliable("https://provider.test", timeout=4)
    assert calls == 1


def test_direct_book_and_runtime_transport_have_bounded_reliability_budget() -> None:
    assert market_adapter.MARKET_READ_TIMEOUT_SECONDS == 8
    assert market_adapter.MAX_MARKET_READ_ATTEMPTS == 2
    assert data_truth.DEFAULT_CALL_TIMEOUT_SECONDS == 8
    assert data_truth.DEFAULT_MARKET_BUDGET_SECONDS == 18.0
    # The compatibility fastpath stays independently latency-bounded. The data-truth
    # overlay installs after it and owns the production sportsbook read semantics.
    assert fastpath.MARKET_CALL_TIMEOUT_SECONDS <= 3
    assert fastpath.MARKET_BUDGET_SECONDS <= 5.0
    assert market_adapter.PLAYER_NAME_MATCHING is False
    assert market_adapter.FUZZY_MATCHING is False
    assert data_truth.PLAYER_NAME_MATCHING is False
    assert data_truth.FUZZY_MATCHING is False
    assert market_adapter.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert data_truth.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_data_truth_keeps_provider_mapping_and_verified_absence_distinct() -> None:
    player = {"team_abbr": "WAS", "jersey_number": "24.0", "position": "RB", "active": True}

    failure = data_truth.market_state_from_bundle(
        {"provider": "FanDuel", "state": "PROVIDER_FETCH_FAILURE", "observations": [], "reason": "TimeoutError"},
        player=player,
    )
    assert failure["status"] == "DATA_UNAVAILABLE"
    assert failure["state"] == "DATA_UNAVAILABLE"
    assert failure["verified_absence"] is False

    mapping = data_truth.market_state_from_bundle(
        {"provider": "FanDuel", "state": "AVAILABLE", "observations": [{"team_abbr": "WAS", "jersey_number": "99", "position": "RB"}]},
        player=player,
    )
    assert mapping["status"] == "DATA_UNAVAILABLE"
    assert mapping["state"] == "PLAYER_MAPPING_UNAVAILABLE"
    assert mapping["verified_absence"] is False

    absent = data_truth.market_state_from_bundle(
        {"provider": "FanDuel", "state": "VERIFIED_NOT_POSTED", "observations": [], "reason": "standard market absent"},
        player=player,
    )
    assert absent["status"] == "MARKET_NOT_POSTED"
    assert absent["state"] == "VERIFIED_NO_STANDARD_MARKET"
    assert absent["verified_absence"] is True


def test_data_truth_uses_exact_identity_not_player_name() -> None:
    player = {"team_abbr": "WAS", "jersey_number": "24.0", "position": "RB", "active": True, "player_name": "Canonical Back"}
    bundle = {
        "provider": "FanDuel",
        "state": "AVAILABLE",
        "observations": [{
            "team_abbr": "WSH",
            "jersey_number": "24",
            "position": "Running Back",
            "player_name": "Different Provider Display Name",
            "sportsbook": "FanDuel",
            "market": "Rushing Yards",
            "line": 51.5,
            "over_odds": -110,
            "under_odds": -110,
        }],
    }
    state = data_truth.market_state_from_bundle(bundle, player=player)
    assert state["status"] == "VERIFIED"
    assert state["line"] == 51.5
    assert state["identity_verified"] is True


def test_identity_present_but_not_offered_is_verified_player_market_absence() -> None:
    player = {"team_abbr": "ARI", "jersey_number": "4.0", "position": "RB", "active": True, "player_name": "Canonical RB"}
    bundle = {
        "provider": "FanDuel",
        "state": "AVAILABLE",
        "observations": [{
            "provider_player_id": "fd-22",
            "team_abbr": "ARI",
            "jersey_number": "22",
            "position": "RB",
            "sportsbook": "FanDuel",
            "market": "Rushing Yards",
            "line": 32.5,
            "over_odds": -113,
            "under_odds": -113,
        }],
        "evidence": {
            "identity_catalog": [
                {"provider_player_id": "fd-4", "team_abbr": "ARI", "jersey_number": "4", "position": "RB", "active": True},
                {"provider_player_id": "fd-22", "team_abbr": "ARI", "jersey_number": "22", "position": "RB", "active": True},
            ],
            "offered_provider_player_ids": ["fd-22"],
        },
    }
    state = data_truth.market_state_from_bundle(bundle, player=player)
    assert state["status"] == "MARKET_NOT_POSTED"
    assert state["state"] == "VERIFIED_NO_STANDARD_MARKET"
    assert state["diagnostic_state"] == "VERIFIED_NO_STANDARD_MARKET"
    assert state["verified_absence"] is True
    assert state["identity_verified"] is True
    assert state["line"] is None


def test_identity_offered_but_quote_not_normalized_stays_data_unavailable() -> None:
    player = {"team_abbr": "ARI", "jersey_number": "4.0", "position": "RB", "active": True}
    bundle = {
        "provider": "FanDuel",
        "state": "AVAILABLE",
        "observations": [{
            "provider_player_id": "fd-22",
            "team_abbr": "ARI",
            "jersey_number": "22",
            "position": "RB",
            "sportsbook": "FanDuel",
            "market": "Rushing Yards",
            "line": 32.5,
            "over_odds": -113,
            "under_odds": -113,
        }],
        "evidence": {
            "identity_catalog": [
                {"provider_player_id": "fd-4", "team_abbr": "ARI", "jersey_number": "4", "position": "RB", "active": True},
                {"provider_player_id": "fd-22", "team_abbr": "ARI", "jersey_number": "22", "position": "RB", "active": True},
            ],
            "offered_provider_player_ids": ["fd-4", "fd-22"],
        },
    }
    state = data_truth.market_state_from_bundle(bundle, player=player)
    assert state["status"] == "DATA_UNAVAILABLE"
    assert state["diagnostic_state"] == "MARKET_MAPPING_FAILURE"
    assert state["verified_absence"] is False
    assert state["line"] is None


def test_duplicate_provider_identity_rows_with_no_offered_market_are_verified_absence() -> None:
    player = {"team_abbr": "GB", "jersey_number": "2.0", "position": "RB", "active": True}
    bundle = {
        "provider": "FanDuel",
        "state": "AVAILABLE",
        "observations": [{
            "provider_player_id": "other-rb",
            "team_abbr": "GB",
            "jersey_number": "32",
            "position": "RB",
            "sportsbook": "FanDuel",
            "market": "Rushing Yards",
            "line": 10.5,
            "over_odds": -113,
            "under_odds": -113,
        }],
        "evidence": {
            "identity_catalog": [
                {"provider_player_id": "dup-a", "team_abbr": "GB", "jersey_number": "2", "position": "RB", "active": True},
                {"provider_player_id": "dup-b", "team_abbr": "GB", "jersey_number": "2.0", "position": "Running Back", "active": True},
                {"provider_player_id": "other-rb", "team_abbr": "GB", "jersey_number": "32", "position": "RB", "active": True},
            ],
            "offered_provider_player_ids": ["other-rb"],
        },
    }
    state = data_truth.market_state_from_bundle(bundle, player=player)
    assert state["status"] == "MARKET_NOT_POSTED"
    assert state["state"] == "VERIFIED_NO_STANDARD_MARKET"
    assert state["verified_absence"] is True
    assert state["identity_verified"] is True
    assert state["line"] is None


def test_live_source_policy_and_projection_isolation_remain_clean() -> None:
    paths = [
        ROOT / "sports_api/collectors/nfl_fanduel_rushing_yards_nflverse_v1.py",
        ROOT / "sports_api/nfl_rushing_yards_data_truth_v1.py",
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8").lower()
        assert "espn" not in source
        assert "sgo" not in source
        assert "espn bet" not in source
    data_truth_source = (ROOT / "sports_api/nfl_rushing_yards_data_truth_v1.py").read_text(encoding="utf-8")
    assert "collect_fanduel_game_market_bundle" in data_truth_source
    wrapper = (ROOT / "sports_api/api/nfl_rushing_yards_slate_v1/__init__.py").read_text(encoding="utf-8")
    assert '"market_budget_seconds": _data_truth.DEFAULT_MARKET_BUDGET_SECONDS' in wrapper
    assert '"market_call_timeout_seconds": _data_truth.DEFAULT_CALL_TIMEOUT_SECONDS' in wrapper
