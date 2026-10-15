from __future__ import annotations

import importlib
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import httpx

try:
    import requests  # type: ignore
except ModuleNotFoundError:
    requests = types.ModuleType("requests")

    class _HTTPError(Exception):
        pass

    class _Session:
        def get(self, *args, **kwargs):
            raise RuntimeError("requests.Session is unavailable in the Runless proof sandbox")

    requests.HTTPError = _HTTPError
    requests.Session = _Session
    sys.modules["requests"] = requests


ROOT = Path(__file__).resolve().parents[1]
TRANSPORT = ROOT / "nba_spread_schedule_provider_resilience_step1_r1.py"
PAGE_WRAPPER = ROOT / "nba_spread_page_provider_resilience_step1_r1.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py"


def _official_payload():
    return {
        "leagueSchedule": {
            "gameDates": [{
                "gameDate": "10/15/2026 00:00:00",
                "games": [{
                    "gameId": "0012600101",
                    "gameDateTimeUTC": "2026-10-16T02:00:00Z",
                    "gameStatus": 1,
                    "gameStatusText": "Scheduled",
                    "arenaName": "Madison Square Garden",
                    "awayTeam": {"teamTricode": "TOR", "teamCity": "Toronto", "teamName": "Raptors"},
                    "homeTeam": {"teamTricode": "NYK", "teamCity": "New York", "teamName": "Knicks"},
                }],
            }]
        }
    }


def _espn_payload():
    return {
        "events": [{
            "id": "401999001",
            "date": "2026-10-16T02:00:00Z",
            "status": {"type": {"state": "pre", "description": "Scheduled"}},
            "competitions": [{
                "date": "2026-10-16T02:00:00Z",
                "venue": {"fullName": "Madison Square Garden"},
                "competitors": [
                    {"homeAway": "away", "team": {"abbreviation": "TOR", "displayName": "Toronto Raptors"}},
                    {"homeAway": "home", "team": {"abbreviation": "NYK", "displayName": "New York Knicks"}},
                ],
            }],
        }]
    }


class _Response:
    def __init__(self, status: int, payload=None):
        self.status_code = status
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _WafSession:
    required = {
        "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform", "User-Agent",
        "Accept", "Accept-Encoding", "Origin", "Sec-Fetch-Site", "Sec-Fetch-Mode",
        "Sec-Fetch-Dest", "Referer", "Accept-Language",
    }

    def __init__(self, *, always_block_official: bool = False):
        self.always_block_official = always_block_official
        self.official_headers: list[dict] = []
        self.espn_dates: list[str] = []

    def get(self, url, *, params=None, headers=None, timeout=None):
        supplied = dict(headers or {})
        if "cdn.nba.com" in url:
            self.official_headers.append(supplied)
            if self.always_block_official or not self.required.issubset(supplied):
                return _Response(403, {})
            return _Response(200, _official_payload())
        if "site.api.espn.com" in url:
            date_value = str((params or {}).get("dates") or "")
            self.espn_dates.append(date_value)
            if "-" in date_value:
                return _Response(400, {})
            if date_value == "20261015":
                return _Response(200, _espn_payload())
            return _Response(200, {"events": []})
        raise AssertionError(f"unexpected URL: {url}")


class _HttpxSession:
    """requests-compatible live adapter using Runless's guaranteed httpx package."""

    def __init__(self):
        self._client = httpx.Client(follow_redirects=True)

    def get(self, url, *args, params=None, headers=None, timeout=None):
        wire_headers = dict(headers or {})
        if "Accept-Encoding" in wire_headers:
            wire_headers["Accept-Encoding"] = "gzip, deflate"
        return self._client.get(url, params=params, headers=wire_headers, timeout=timeout)


def test_step1_transport_injects_current_nba_cdn_browser_header_contract():
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    headers = transport.NBA_CDN_HEADERS
    assert _WafSession.required.issubset(headers)
    assert headers["Origin"] == "https://www.nba.com"
    assert headers["Referer"] == "https://www.nba.com/"
    assert headers["Sec-Fetch-Site"] == "same-site"
    assert "Chrome/140" in headers["User-Agent"]
    assert "gzip" in headers["Accept-Encoding"]


def test_step1_espn_range_transport_fans_out_to_supported_single_day_calls():
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    assert transport._espn_range_days("20261015-20261017") == ("20261015", "20261016", "20261017")
    assert transport._espn_range_days("20261017-20261015") is None
    assert transport._espn_range_days("20261001-20261020") is None


def test_step1_same_provider_repair_restores_nba_official_plus_espn_consensus():
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    session = _WafSession()
    result = transport.load_verified_nba_schedule(
        now_utc=datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
        days=1,
        session=session,
    )
    assert result["verification"] == "VERIFIED"
    assert result["diagnostic_state"] == "SOURCE_CONSENSUS"
    assert result["source_agreement"] == 2
    assert result["provider_errors"] == {}
    assert len(result["games"]) == 1
    assert result["games"][0]["game_key"] == "TOR@NYK:2026-10-15"
    assert result["games"][0]["confirming_sources"] == ["NBA Official", "ESPN NBA"]
    assert session.official_headers
    assert _WafSession.required.issubset(session.official_headers[0])
    assert session.espn_dates == ["20261015"]


def test_step1_repair_does_not_weaken_fail_closed_semantics():
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    result = transport.load_verified_nba_schedule(
        now_utc=datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
        days=1,
        session=_WafSession(always_block_official=True),
    )
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "NBA_OFFICIAL_UNAVAILABLE"
    assert result["games"] == []
    assert result["source_agreement"] == 0


def test_step1_is_additive_and_leaves_frozen_router_for_step2_activation():
    assert TRANSPORT.exists()
    assert PAGE_WRAPPER.exists()
    transport_source = TRANSPORT.read_text(encoding="utf-8")
    page_source = PAGE_WRAPPER.read_text(encoding="utf-8")
    router_source = ROUTER.read_text(encoding="utf-8")

    assert "import nba_spread_schedule_v1 as frozen_schedule" in transport_source
    assert "import nba_spread_page_v1 as frozen_page" in page_source
    assert 'ACTIVE_PAGE = "nba_spread_page_v1"' in router_source
    assert "nba_spread_page_provider_resilience_step1_r1" not in router_source
    assert "cbssports" not in transport_source.lower()
    assert "tinyfish" not in transport_source.lower()
    assert "MAY_MODIFY_MODEL = False" in transport_source
    assert "MAY_MODIFY_PROJECTION = False" in transport_source
    assert "MAY_MODIFY_PROBABILITY = False" in transport_source
    assert "MAY_MODIFY_SOURCE_OWNERSHIP = False" in transport_source


def test_step1_live_runless_provider_consensus():
    """Authoritative live smoke: exact repaired loader must reach both providers."""
    transport = importlib.import_module("nba_spread_schedule_provider_resilience_step1_r1")
    result = transport.load_verified_nba_schedule(
        days=7,
        timeout=12.0,
        session=_HttpxSession(),
    )
    assert result.get("verification") == "VERIFIED", result
    assert result.get("diagnostic_state") == "SOURCE_CONSENSUS", result
    assert result.get("source_agreement") == 2, result
    assert len(result.get("games") or []) >= 1, result
    assert not result.get("provider_errors"), result
    assert all(
        set(game.get("confirming_sources") or []) == {"NBA Official", "ESPN NBA"}
        for game in result.get("games") or []
    ), result
