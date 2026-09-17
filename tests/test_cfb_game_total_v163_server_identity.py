from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_cfb_router_exposes_full_slate_selector_identity() -> None:
    source = (ROOT / "sports_api" / "api" / "cfb_odds_v1.py").read_text(encoding="utf-8")
    assert '@router.get("/selector/verified-games")' in source
    assert "def selector_verified_games(" in source
    assert '"synthetic_ids": False' in source
    assert '"projection_weight": 0.0' in source
    assert "load_verified_games()" in source
    assert "_fetch_github_verified_games()" in source
    assert "_fetch_espn_verified_games(requested_day)" in source


def test_v163_consumes_full_slate_identity_not_market_lines() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v14.py").read_text(encoding="utf-8")
    assert 'SELECTOR_IDENTITY_ENDPOINT = "/api/v1/cfb/selector/verified-games"' in source
    assert 'params={"game_date": selected_day.isoformat()}' in source
    enrich_start = source.index("def _enrich_selector_ids_from_api(")
    enrich_end = source.index("\ndef _load_games(", enrich_start)
    enrich_body = source[enrich_start:enrich_end]
    assert 'payload.get("games")' in enrich_body
    assert 'row.get("event_id")' in enrich_body
    assert 'row.get("away_team")' in enrich_body
    assert 'row.get("home_team")' in enrich_body
    assert 'payload.get("lines")' not in enrich_body
