from __future__ import annotations

from pathlib import Path

import pytest

from sports_api.collectors import nfl_fanduel_receiving_yards_nflverse_v2 as market_adapter

ROOT = Path(__file__).resolve().parents[1]


def test_exact_identity_normalizers_bridge_provider_and_roster_serialization_only() -> None:
    assert market_adapter._normalize_team("WSH") == "WAS"
    assert market_adapter._normalize_team("JAC") == "JAX"
    assert market_adapter._normalize_team("LA") == "LAR"
    assert market_adapter._normalize_jersey("87.0") == "87"
    assert market_adapter._normalize_jersey(0.0) == "0"
    assert market_adapter._normalize_jersey(" 14 ") == "14"
    assert market_adapter._normalize_position("Wide Receiver") == "WR"
    assert market_adapter._normalize_position("Tight End") == "TE"
    assert market_adapter._normalize_position("Halfback") == "RB"
    assert market_adapter._normalize_position("Fullback") == "FB"


def test_market_reconciliation_accepts_unique_exact_identity_after_canonical_normalization() -> None:
    observation = {
        "team_abbr": "WSH",
        "jersey_number": "17",
        "position": "Wide Receiver",
    }
    roster = [
        {
            "team_abbr": "WAS",
            "jersey_number": "17.0",
            "position": "WR",
            "active": True,
            "canonical_player_id": "kyre:nfl:player:00-TEST",
        }
    ]
    match = market_adapter.reconcile_observation_to_roster(observation, roster)
    assert match is not None
    assert match["canonical_player_id"] == "kyre:nfl:player:00-TEST"


def test_market_reconciliation_still_fails_closed_on_ambiguous_exact_identity() -> None:
    observation = {"team_abbr": "KC", "jersey_number": "1", "position": "WR"}
    roster = [
        {"team_abbr": "KC", "jersey_number": "1.0", "position": "WR", "active": True},
        {"team_abbr": "KC", "jersey_number": "1", "position": "Wide Receiver", "active": True},
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


def test_direct_book_transport_has_bounded_retry_constants() -> None:
    assert market_adapter.MARKET_READ_TIMEOUT_SECONDS == 8
    assert market_adapter.MAX_MARKET_READ_ATTEMPTS == 2


def test_api_keeps_provider_failures_semantic_not_verified_absence() -> None:
    source = (ROOT / "sports_api/api/nfl_receiving_yards_slate_v2.py").read_text(encoding="utf-8")
    assert '"state": "DATA_UNAVAILABLE"' in source
    assert '"verified_absence": False' in source
    assert '"state": "VERIFIED_NO_STANDARD_MARKET"' in source
    assert '"verified_absence": True' in source


def test_live_source_policy_and_projection_isolation_remain_unchanged() -> None:
    adapter_source = (ROOT / "sports_api/collectors/nfl_fanduel_receiving_yards_nflverse_v2.py").read_text(encoding="utf-8").lower()
    api_source = (ROOT / "sports_api/api/nfl_receiving_yards_slate_v2.py").read_text(encoding="utf-8").lower()
    for source in (adapter_source, api_source):
        assert "espn" not in source
        assert "sgo" not in source
        assert "espn bet" not in source
    assert market_adapter.PLAYER_NAME_MATCHING is False
    assert market_adapter.FUZZY_MATCHING is False
    assert market_adapter.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
