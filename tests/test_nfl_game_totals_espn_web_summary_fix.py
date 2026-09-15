from __future__ import annotations

from sports_api.collectors import nfl_fanduel_game_totals_v1 as collector


def test_espn_identity_uses_cloud_reachable_web_summary(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get_json(url: str, params: dict | None = None):
        calls.append((url, params))
        return {
            "header": {
                "id": "401872933",
                "competitions": [
                    {
                        "id": "401872933",
                        "date": "2026-09-20T17:00:00Z",
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
                        "status": {"type": {"state": "pre"}},
                        "venue": {"fullName": "Mercedes-Benz Stadium"},
                        "broadcasts": [{"names": ["CBS"]}],
                    }
                ],
            }
        }

    monkeypatch.setattr(collector, "_get_json", fake_get_json)

    identity = collector._espn_identity("401872933")

    assert calls == [
        (
            "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary",
            {"event": "401872933"},
        )
    ]
    assert identity["event_id"] == "401872933"
    assert identity["away_team_id"] == "29"
    assert identity["home_team_id"] == "1"
    assert identity["away_values"] >= {"carolina panthers", "car"}
    assert identity["home_values"] >= {"atlanta falcons", "atl"}
    assert identity["status"] == "pre"
    assert identity["venue"] == "Mercedes-Benz Stadium"
    assert identity["broadcast"] == ["CBS"]
