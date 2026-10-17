from __future__ import annotations

import threading
import time

import cfb_game_total_page1_daily_slate_runtime_fallback_r1 as fallback
import cfb_game_total_page1_daily_slate_v1 as slate


class _Response:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {"requested_phoenix_date": "2026-10-17", "game_count": 0, "games": []}


def test_same_day_daily_slate_loaders_share_one_transport(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_get(url, *, params, timeout, **_kwargs):
        calls.append((str(url), str(params.get("game_date"))))
        return _Response()

    monkeypatch.setattr(slate.requests, "get", fake_get)
    slate._load_slate_cached_60.clear()
    slate._load_slate_cached_20.clear()

    first = slate._load_slate_cached_60("2026-10-17")
    second = slate._load_slate_cached_20("2026-10-17")

    assert first["requested_phoenix_date"] == "2026-10-17"
    assert second["requested_phoenix_date"] == "2026-10-17"
    assert len(calls) == 1


def test_espn_fallback_fetches_independent_scoreboards_concurrently(monkeypatch) -> None:
    lock = threading.Lock()
    active = 0
    max_active = 0
    seen: list[tuple[str, int]] = []

    def fake_fetch(day: str, group_id: int):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
            seen.append((day, group_id))
        time.sleep(0.05)
        with lock:
            active -= 1
        return {"events": []}

    monkeypatch.setattr(fallback, "_fetch_scoreboard_payload", fake_fetch)
    payload = fallback.build_requests_fallback_payload(fallback.date(2026, 10, 17))

    assert payload["requested_phoenix_date"] == "2026-10-17"
    assert len(seen) == 4
    assert max_active >= 2
    attempts = payload["diagnostics"]["scoreboard_attempts"]
    assert [(row["date"], row["group_id"]) for row in attempts] == [
        ("2026-10-17", 80),
        ("2026-10-17", 81),
        ("2026-10-18", 80),
        ("2026-10-18", 81),
    ]
