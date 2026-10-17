from __future__ import annotations

from datetime import date
from pathlib import Path

import requests

import cfb_game_total_page1_daily_slate_runtime_fallback_r1 as fallback
import cfb_game_total_page1_daily_slate_v1 as page
import streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1 as router


def _event(*, event_id: str = "401-test", kickoff_utc: str = "2026-10-17T19:00:00Z", state: str = "in") -> dict:
    detail = "2nd Quarter" if state == "in" else "Scheduled"
    return {
        "id": event_id,
        "date": kickoff_utc,
        "competitions": [
            {
                "date": kickoff_utc,
                "competitors": [
                    {
                        "homeAway": "away",
                        "team": {"id": "1", "displayName": "Away University"},
                        "score": "14",
                        "records": [{"summary": "4-2"}],
                    },
                    {
                        "homeAway": "home",
                        "team": {"id": "2", "displayName": "Home University"},
                        "score": "10",
                        "records": [{"summary": "5-1"}],
                    },
                ],
                "status": {
                    "type": {"state": state, "description": detail, "completed": False},
                    "period": 2 if state == "in" else 0,
                    "displayClock": "08:22" if state == "in" else "",
                },
                "odds": [
                    {
                        "provider": {"id": "58", "name": "ESPN BET"},
                        "overUnder": 52.5,
                        "spread": -3.5,
                    }
                ],
            }
        ],
    }


def test_hosted_api_outage_uses_requests_fallback(monkeypatch):
    selected = date(2026, 10, 17)
    calls: list[date] = []

    def hosted_down(_day_iso: str):
        raise requests.ConnectionError("hosted Daily Slate route unavailable")

    def requests_builder(day: date, **_kwargs):
        calls.append(day)
        return {
            "requested_phoenix_date": day.isoformat(),
            "game_count": 1,
            "games": [{"event_id": "fallback-game"}],
        }

    monkeypatch.setattr(page, "_load_slate_cached_60", hosted_down)
    monkeypatch.setattr(fallback, "build_requests_fallback_payload", requests_builder)

    payload = fallback._load_day_with_fallback(selected)

    assert payload["game_count"] == 1
    assert payload["games"][0]["event_id"] == "fallback-game"
    assert payload["transport"] == "requests_espn_fallback"
    assert payload["api_unavailable"] is True
    assert calls == [selected]


def test_empty_hosted_payload_is_crosschecked_with_fallback(monkeypatch):
    selected = date(2026, 10, 16)
    calls: list[date] = []

    monkeypatch.setattr(
        page,
        "_load_slate_cached_60",
        lambda _day_iso: {
            "requested_phoenix_date": selected.isoformat(),
            "game_count": 0,
            "games": [],
        },
    )

    def requests_builder(day: date, **_kwargs):
        calls.append(day)
        return {
            "requested_phoenix_date": day.isoformat(),
            "game_count": 4,
            "games": [{"event_id": f"live-{index}"} for index in range(4)],
        }

    monkeypatch.setattr(fallback, "build_requests_fallback_payload", requests_builder)

    payload = fallback._load_day_with_fallback(selected)

    assert payload["game_count"] == 4
    assert payload["transport"] == "requests_espn_fallback"
    assert payload["primary_empty"] is True
    assert calls == [selected]


def test_total_transport_failure_is_not_reported_as_a_normal_empty_slate(monkeypatch):
    selected = date(2026, 10, 17)

    monkeypatch.setattr(
        page,
        "_load_slate_cached_60",
        lambda _day_iso: (_ for _ in ()).throw(requests.ConnectionError("hosted down")),
    )
    monkeypatch.setattr(
        fallback,
        "build_requests_fallback_payload",
        lambda _day: (_ for _ in ()).throw(RuntimeError("fallback down")),
    )

    payload = fallback._load_day_with_fallback(selected)

    assert payload["game_count"] == 0
    assert payload["api_unavailable"] is True
    assert payload["local_fallback_unavailable"] is True
    assert payload["transport"] == "unavailable"


def test_requests_fallback_preserves_phoenix_date_live_state_and_exact_event_dedupe():
    selected = date(2026, 10, 17)
    days = fallback.upstream_scoreboard_dates_for_phoenix_day(selected)
    assert days == ("2026-10-17", "2026-10-18")

    event = _event()
    payloads = {
        ("2026-10-17", 80): {"events": [event]},
        ("2026-10-17", 81): {"events": [event]},
        ("2026-10-18", 80): {"events": []},
        ("2026-10-18", 81): {"events": []},
    }
    payload = fallback.build_requests_fallback_payload(selected, scoreboard_payloads=payloads)

    assert payload["game_count"] == 1
    game = payload["games"][0]
    assert game["event_id"] == "401-test"
    assert game["phoenix_date"] == "2026-10-17"
    assert game["status"]["state"] == "Live"
    assert game["subdivisions"] == ["FBS", "FCS"]
    assert any(row["market_type"] == "game_total" and row["value"] == 52.5 for row in game["market_observations"])
    assert payload["fabrication"] is False
    assert payload["page_wide_source_authority"] is False


def test_router_preserves_canonical_page1_identity_and_installs_fallback_context():
    source = Path(router.__file__).read_text(encoding="utf-8")
    assert router.PAGE1_DAILY_SLATE_ROUTE == "cfb_game_total_page1_daily_slate_v1"
    assert "import cfb_game_total_page1_daily_slate_runtime_fallback_r1 as daily_fallback" in source
    assert "with daily_fallback._install_runtime_fallback():" in source
    assert router.MAY_MODIFY_SELECTED_GAME_RUNTIME is False
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_fallback_has_no_fastapi_or_httpx_runtime_dependency():
    source = Path(fallback.__file__).read_text(encoding="utf-8")
    assert "import requests" in source
    assert "import fastapi" not in source
    assert "from fastapi" not in source
    assert "import httpx" not in source
