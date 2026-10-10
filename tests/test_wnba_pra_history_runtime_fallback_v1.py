from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType


def _load_module():
    history = ModuleType("sports_api.wnba_game_history")
    history.WNBA_CURRENT_STATS_BASE_URL = "https://stats.nba.com/stats"
    history.get_player_game_log_dataset = lambda *args, **kwargs: None
    sys.modules["sports_api.wnba_game_history"] = history

    primary = ModuleType("sports_api.wnba_pra_history_multisource_v1")
    primary.get_multisource_player_game_log_dataset = lambda *args, **kwargs: None
    sys.modules["sports_api.wnba_pra_history_multisource_v1"] = primary

    sys.modules.pop("sports_api.wnba_pra_history_runtime_fallback_v1", None)
    return importlib.import_module("sports_api.wnba_pra_history_runtime_fallback_v1")


def test_primary_multisource_remains_authoritative(monkeypatch):
    module = _load_module()
    expected = {"source": "ESPN + WNBA.com", "games": [{"points": 19}]}
    monkeypatch.setattr(module, "get_multisource_player_game_log_dataset", lambda player_id, season: expected)
    called = {"official": 0}

    def official(*args, **kwargs):
        called["official"] += 1
        raise AssertionError("fallback should stay asleep")

    monkeypatch.setattr(module, "get_player_game_log_dataset", official)
    assert module.get_runtime_player_game_log_dataset(1627668, 2026) is expected
    assert called["official"] == 0


def test_official_stats_fallback_recovers_when_primary_sources_are_unavailable(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "get_multisource_player_game_log_dataset",
        lambda player_id, season: (_ for _ in ()).throw(RuntimeError("primary down")),
    )
    official = {
        "source": "WNBA Stats API",
        "games": [
            {
                "game_date": "2026-10-04",
                "points": 19,
                "rebounds": 2,
                "assists": 3,
                "minutes": 40.0,
                "matchup": {"opponent_team_key": "atlanta-dream"},
            }
        ],
        "verification": {"returned_player_ids_match_request": True},
    }
    seen = {}

    def official_read(player_id, season, *, stats_base_url=None):
        seen.update(player_id=player_id, season=season, stats_base_url=stats_base_url)
        return official

    monkeypatch.setattr(module, "get_player_game_log_dataset", official_read)
    result = module.get_runtime_player_game_log_dataset(1627668, 2026)

    assert result["games"][0]["points"] + result["games"][0]["rebounds"] + result["games"][0]["assists"] == 24
    assert result["verification"]["provider_policy"] == "multi_source"
    assert result["verification"]["runtime_fallback"] == "official_wnba_stats_api"
    assert result["verification"]["official_wnba_stats_available"] is True
    assert result["verification"]["primary_multisource_error"] == "RuntimeError"
    assert seen["stats_base_url"] == "https://stats.nba.com/stats"


def test_all_provider_failure_is_explicit(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "get_multisource_player_game_log_dataset",
        lambda player_id, season: (_ for _ in ()).throw(RuntimeError("primary down")),
    )
    monkeypatch.setattr(
        module,
        "get_player_game_log_dataset",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("official down")),
    )
    try:
        module.get_runtime_player_game_log_dataset(1627668, 2026)
    except RuntimeError as exc:
        detail = str(exc)
    else:
        raise AssertionError("expected fail-closed provider error")
    assert "WNBA_HISTORY_ALL_CREDIBLE_PROVIDERS_UNAVAILABLE" in detail
    assert "primary=RuntimeError" in detail
    assert "official_stats=TimeoutError" in detail


def test_detail_bundle_declares_three_source_runtime_policy():
    text = (Path(__file__).resolve().parents[1] / "sports_api/api/wnba_pra_detail_bundle.py").read_text()
    assert "wnba_pra_history_runtime_fallback_v1" in text
    assert "official_wnba_profile_plus_espn_plus_official_stats_fallback" in text
    assert '"official_wnba_stats_fallback": True' in text
