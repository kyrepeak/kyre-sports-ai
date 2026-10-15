from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "nba_spread_schedule_v1.py"


def _load_schedule():
    spec = importlib.util.spec_from_file_location("nba_spread_schedule_v1", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, *, status: int = 200, payload=None, text: str = ""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FallbackSession:
    def get(self, url, *, params=None, headers=None, timeout=None):
        if "cdn.nba.com" in url:
            return _Response(status=403)
        if "site.api.espn.com" in url:
            return _Response(
                payload={
                    "events": [
                        {
                            "id": "401999001",
                            "date": "2026-10-16T02:00:00Z",
                            "status": {"type": {"state": "pre", "description": "Scheduled"}},
                            "competitions": [
                                {
                                    "date": "2026-10-16T02:00:00Z",
                                    "venue": {"fullName": "Madison Square Garden"},
                                    "competitors": [
                                        {
                                            "homeAway": "away",
                                            "team": {"abbreviation": "TOR", "displayName": "Toronto Raptors"},
                                        },
                                        {
                                            "homeAway": "home",
                                            "team": {"abbreviation": "NYK", "displayName": "New York Knicks"},
                                        },
                                    ],
                                }
                            ],
                        }
                    ]
                }
            )
        if "cbssports.com/nba/scoreboard/20261015" in url:
            return _Response(
                text="""
                <html><body><main>
                  <section><span>Raptors</span><span>3-2</span><span>Knicks</span><span>2-1</span></section>
                  <h2>Our Latest NBA Stories</h2>
                  <article>Warriors Lakers trade rumor</article>
                </main></body></html>
                """
            )
        raise AssertionError(f"unexpected URL: {url}")


def test_step1_cbs_parser_builds_only_scoreboard_matchup_identities():
    schedule = _load_schedule()
    html = """
    <html><body><main>
      <div>Raptors3-2</div><div>Knicks2-1</div>
      <div>Thunder</div><div>Rockets</div>
      <h2>Our Latest NBA Stories</h2>
      <p>Warriors Lakers trade rumor</p>
    </main></body></html>
    """
    games = schedule.parse_cbs_scoreboard_html(html, "2026-10-15")
    assert [game["game_key"] for game in games] == [
        "TOR@NYK:2026-10-15",
        "OKC@HOU:2026-10-15",
    ]
    assert all(game["source"] == "CBS Sports" for game in games)


def test_step1_nba_official_403_falls_back_to_cbs_plus_espn_quorum():
    schedule = _load_schedule()
    result = schedule.load_verified_nba_schedule(
        now_utc=datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
        days=1,
        session=_FallbackSession(),
    )

    assert result["verification"] == "VERIFIED"
    assert result["diagnostic_state"] == "SOURCE_CONSENSUS_FALLBACK"
    assert result["source_agreement"] == 2
    assert result["provider_errors"] == {"NBA Official": "HTTPError"}
    assert len(result["games"]) == 1
    game = result["games"][0]
    assert game["game_key"] == "TOR@NYK:2026-10-15"
    assert game["confirming_sources"] == ["CBS Sports", "ESPN NBA"]
    assert game["tip_phoenix"] == "7:00 PM MST"


def test_step1_fallback_still_fails_closed_when_cbs_and_espn_disagree():
    schedule = _load_schedule()
    cbs = schedule.parse_cbs_scoreboard_html(
        "<main><div>Raptors</div><div>Knicks</div></main>",
        "2026-10-15",
    )
    espn = [
        {
            "game_key": "TOR@BOS:2026-10-15",
            "source": "ESPN NBA",
            "source_game_id": "x",
            "away_tricode": "TOR",
            "away_name": "Toronto Raptors",
            "home_tricode": "BOS",
            "home_name": "Boston Celtics",
            "tip_utc": "2026-10-16T02:00:00Z",
            "tip_iso_phoenix": "2026-10-15T19:00:00-07:00",
            "tip_phoenix": "7:00 PM MST",
            "game_date_phoenix": "2026-10-15",
            "status": "UPCOMING",
            "venue": "TD Garden",
        }
    ]
    result = schedule.reconcile_identity_fallback(cbs, espn, ("2026-10-15",), provider_name="CBS Sports")
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "PROVIDER_CONFLICT"
    assert result["games"] == []
