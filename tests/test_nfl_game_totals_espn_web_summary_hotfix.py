from __future__ import annotations

import io
import json

import sports_api.collectors.nfl_fanduel_game_totals_v1 as collector


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def test_espn_identity_uses_web_summary_host(monkeypatch) -> None:
    event_id = "401872933"
    captured_urls: list[str] = []
    payload = {
        "header": {
            "id": event_id,
            "date": "2026-09-20T17:00:00Z",
            "competitions": [
                {
                    "id": event_id,
                    "date": "2026-09-20T17:00:00Z",
                    "status": {"type": {"state": "pre"}},
                    "competitors": [
                        {
                            "homeAway": "away",
                            "team": {
                                "id": "29",
                                "displayName": "Carolina Panthers",
                                "shortDisplayName": "Panthers",
                                "name": "Panthers",
                                "abbreviation": "CAR",
                            },
                        },
                        {
                            "homeAway": "home",
                            "team": {
                                "id": "1",
                                "displayName": "Atlanta Falcons",
                                "shortDisplayName": "Falcons",
                                "name": "Falcons",
                                "abbreviation": "ATL",
                            },
                        },
                    ],
                    "venue": {"fullName": "Mercedes-Benz Stadium"},
                    "broadcasts": [{"names": ["FOX"]}],
                }
            ],
        }
    }

    def fake_urlopen(request, timeout):
        captured_urls.append(request.full_url)
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(collector, "urlopen", fake_urlopen)

    identity = collector._espn_identity(event_id)

    assert captured_urls == [
        "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=401872933"
    ]
    assert identity["home_team_id"] == "1"
    assert identity["away_team_id"] == "29"
    assert identity["status"] == "pre"
