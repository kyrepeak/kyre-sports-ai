from __future__ import annotations

import sys
import time
from sports_api.api import nfl_passing_yards_slate_v1 as slate


def _impl():
    return slate


def test_market_prefetch_has_aggregate_deadline_and_preserves_completed_games(monkeypatch):
    impl = _impl()
    games = [{"game_id": "fast"}, {"game_id": "slow"}]

    def collect(game):
        if game["game_id"] == "slow":
            time.sleep(0.60)
        return [{"sportsbook": "FanDuel", "game_id": game["game_id"]}]

    monkeypatch.setattr(impl._legacy, "_collect_market_observations", collect)
    started = time.perf_counter()
    out = impl._bounded_market_prefetch(games, max_workers=2, deadline_seconds=0.20)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.45
    assert out["fast"][0]["game_id"] == "fast"
    assert out["slow"] == []


def test_context_and_market_prefetch_start_concurrently(monkeypatch):
    impl = _impl()
    games = [{"game_id": "g1", "season": 2026, "date": "2026-10-25", "away": "NE", "home": "CHI"}]
    started = {"context": False, "market": False}

    def contexts(_games):
        started["context"] = True
        deadline = time.perf_counter() + 0.20
        while not started["market"] and time.perf_counter() < deadline:
            time.sleep(0.002)
        assert started["market"], "market prefetch did not start concurrently"
        return {(2026, "2026-10-25"): {"frame": object(), "current_rows": [], "defenses": {}, "history": []}}

    def markets(_games):
        started["market"] = True
        deadline = time.perf_counter() + 0.20
        while not started["context"] and time.perf_counter() < deadline:
            time.sleep(0.002)
        assert started["context"], "context prefetch did not start concurrently"
        return {"g1": []}

    monkeypatch.setattr(impl._legacy, "_schedule_games", lambda target_date=None: ("2026-10-25", games))
    monkeypatch.setattr(impl._legacy, "_prefetch_season_contexts", contexts)
    monkeypatch.setattr(impl, "_bounded_market_prefetch", markets, raising=False)
    monkeypatch.setattr(impl._legacy.base._legacy, "_player_bundle", lambda **kwargs: None)

    resolved, bundles, _ = slate.build_game_bundles("2026-10-25")
    assert resolved == "2026-10-25"
    assert len(bundles) == 1
