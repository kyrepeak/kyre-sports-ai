from __future__ import annotations

import sports_api.collectors.nfl_fanduel_game_totals_v1 as collector


def test_step2_provider_constants_match_verified_production() -> None:
    assert collector.ESPN_SUMMARY_URL == (
        "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary"
    )
    assert collector.FANDUEL_NFL_EVENT_TYPE_ID == "6423"


def test_fanduel_landing_uses_verified_american_football_event_type(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get_json(url: str, params=None):
        captured["url"] = url
        captured["params"] = dict(params or {})
        return {"attachments": {"events": {}}}

    monkeypatch.setattr(collector, "_get_json", fake_get_json)
    collector._fanduel_landing()

    assert captured["url"] == f"{collector.FANDUEL_HOST}/api/content-managed-page"
    assert captured["params"]["page"] == "SPORT"
    assert captured["params"]["eventTypeId"] == "6423"
    assert captured["params"]["timezone"] == "America/Phoenix"
