from __future__ import annotations

import sports_api.collectors.nfl_fanduel_game_totals_v1 as collector


def test_fanduel_landing_uses_american_football_event_type(monkeypatch) -> None:
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
