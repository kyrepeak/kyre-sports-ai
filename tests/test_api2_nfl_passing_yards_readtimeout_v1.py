from __future__ import annotations

import importlib
import threading
import time


def test_market_prefetch_is_bounded_parallel_and_preserves_game_results(monkeypatch):
    slate = importlib.import_module("sports_api.api.nfl_passing_yards_slate_v1")
    games = [
        {"game_id": f"kyre:nfl:game:test-{idx}", "away": f"A{idx}", "home": f"H{idx}"}
        for idx in range(4)
    ]
    lock = threading.Lock()
    active = 0
    max_active = 0

    def fake_collect(game):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return [{"game_id": game["game_id"], "line": 200.5}]

    monkeypatch.setattr(slate, "_collect_market_observations", fake_collect)
    out = slate._prefetch_market_observations(games, max_workers=4)

    assert max_active >= 2
    assert list(out) == [game["game_id"] for game in games]
    assert [out[game["game_id"]][0]["game_id"] for game in games] == [game["game_id"] for game in games]
