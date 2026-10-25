from __future__ import annotations

from pathlib import Path

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


def test_direct_book_transport_has_bounded_transient_retry_and_production_timeout() -> None:
    source = (ROOT / "sports_api/collectors/nfl_fanduel_receiving_yards_nflverse_v2.py").read_text(encoding="utf-8")
    assert "MARKET_READ_TIMEOUT_SECONDS = 8" in source
    assert "MAX_MARKET_READ_ATTEMPTS = 2" in source
    assert "def _get_json_reliable(" in source
    assert "for attempt in range(1, MAX_MARKET_READ_ATTEMPTS + 1):" in source
    assert '"read failed" not in message.lower()' in source
    assert "base._get_json(" in source


def test_api_market_failure_preserves_provider_reason_and_uses_adapter_timeout() -> None:
    source = (ROOT / "sports_api/api/nfl_receiving_yards_slate_v2.py").read_text(encoding="utf-8")
    assert "timeout=direct_book.MARKET_READ_TIMEOUT_SECONDS" in source
    assert 'detail = str(exc).strip()' in source
    assert 'f"direct market read failed: {detail or type(exc).__name__}"' in source


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
