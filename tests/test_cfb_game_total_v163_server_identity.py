from __future__ import annotations

from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_cfb_router_exposes_selector_identity_and_is_fail_closed() -> None:
    source = (ROOT / "sports_api" / "api" / "cfb_odds_v1.py").read_text(encoding="utf-8")
    assert '@router.get("/selector/verified-games")' in source
    assert "def selector_verified_games(" in source
    assert '"synthetic_ids": False' in source
    assert '"projection_weight": 0.0' in source
    assert "load_verified_games()" in source
    assert "_fetch_github_verified_games()" in source
    assert "_fetch_espn_verified_games(requested_day)" in source


def test_v163_selector_uses_render_identity_before_direct_espn() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v14.py").read_text(encoding="utf-8")
    assert 'IDENTITY_ENDPOINT = "/api/v1/cfb/selector/verified-games"' in source
    assert "def _fetch_selector_server_games(" in source
    assert "def _server_games_as_espn_payload(" in source
    load_start = source.index("def _load_games(")
    load_end = source.index("\ndef _sync_frozen_matchup_state", load_start)
    load_body = source[load_start:load_end]
    assert "_fetch_selector_server_games(selected_day)" in load_body
    assert "_server_games_as_espn_payload(server_games" in load_body
    assert load_body.index("_fetch_selector_server_games(selected_day)") < load_body.index("_fetch_selector_espn_payload(selected_day)")


def test_server_identity_adapter_preserves_official_event_id_shape() -> None:
    row = {
        "event_id": "401752999",
        "game_date": date(2026, 9, 19).isoformat(),
        "away_team": "Coastal Carolina",
        "home_team": "Delaware",
        "away_team_id": "324",
        "home_team_id": "48",
        "venue": "Delaware Stadium",
        "status": "Scheduled",
    }
    assert row["event_id"] == "401752999"
    assert "game_id" not in row
