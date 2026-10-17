from __future__ import annotations

from datetime import date

import requests

import cfb_game_total_page1_daily_slate_v1 as page
import sports_api.api.cfb_daily_slate_v1 as local_slate


def test_load_day_falls_back_to_certified_local_builder_when_hosted_api_is_unavailable(monkeypatch):
    selected = date(2026, 10, 17)
    calls: list[date] = []

    def hosted_api_down(_day_iso: str):
        raise requests.ConnectionError("hosted Daily Slate route unavailable")

    def local_builder(day: date, **_kwargs):
        calls.append(day)
        return {
            "requested_phoenix_date": day.isoformat(),
            "game_count": 1,
            "games": [
                {
                    "event_id": "fallback-game",
                    "phoenix_date": day.isoformat(),
                    "kickoff_phoenix": f"{day.isoformat()}T12:00:00-07:00",
                    "away": {"name": "Away"},
                    "home": {"name": "Home"},
                    "status": {"state": "Scheduled"},
                    "subdivisions": ["FBS"],
                }
            ],
        }

    monkeypatch.setattr(page, "_load_slate_cached_60", hosted_api_down)
    monkeypatch.setattr(local_slate, "build_daily_slate_payload", local_builder)

    payload = page._load_day(selected)

    assert payload["game_count"] == 1
    assert payload["games"][0]["event_id"] == "fallback-game"
    assert payload["transport"] == "local_certified_builder"
    assert payload["api_unavailable"] is True
    assert calls == [selected]
