from __future__ import annotations

import importlib


def test_live_espn_total_rebounds_alias_is_preserved(monkeypatch):
    module = importlib.import_module("sports_api.wnba_pra_speed_v3_step3_espn_history")
    monkeypatch.setattr(module, "get_wnba_teams", lambda season: [])
    payload = {
        "labels": ["MIN", "PTS", "REB", "AST"],
        "names": ["minutes", "points", "totalRebounds", "assists"],
        "events": [
            {
                "id": "401857213",
                "date": "2026-09-01T00:00Z",
                "stats": ["22", "6", "5", "2"],
            }
        ],
    }

    result = module.normalize_espn_wnba_gamelog(
        payload,
        player_id=3102133,
        season=2026,
        retrieved_at_utc="2026-10-07T00:00:00+00:00",
    )

    assert result["game_count"] == 1
    assert result["games"][0]["rebounds"] == 5
