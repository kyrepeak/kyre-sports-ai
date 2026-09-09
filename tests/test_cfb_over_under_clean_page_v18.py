"""Regression tests for CFB O/U Clean Page V18 live odds integration."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v18 as page


def _game(identity, total=None, book="FanDuel"):
    row = {
        "identity_key": identity,
        "game_id": identity,
        "away_team": "Away",
        "home_team": "Home",
        "kickoff_et": "8:00 PM ET",
    }
    if total is not None:
        row.update(
            {
                "market_line_available": True,
                "market_identity_verified": True,
                "market_total": total,
                "market_sportsbook": book,
                "market_status": "active",
                "market_updated_at_utc": "2026-09-09T22:54:00+00:00",
                "market_projection_weight": 0.0,
            }
        )
    else:
        row["market_line_available"] = False
    return row


def test_full_slate_board_uses_each_games_own_live_total():
    games = [
        _game("g1", 62.5),
        _game("g2", 48.5),
        _game("g3", None),
    ]
    rows = page._line_board(games, "g1", 63.0)
    assert rows[0]["Live Total"] == 62.5
    assert rows[0]["Analysis Line"] == 63.0
    assert rows[1]["Live Total"] == 48.5
    assert rows[1]["Analysis Line"] == 48.5
    assert rows[2]["Live Total"] is None
    assert rows[2]["Analysis Line"] is None
    assert rows[2]["Market"] == "UNAVAILABLE"


def test_market_caption_discloses_zero_projection_weight():
    html = page._market_caption(
        _game("g1", 62.5),
        {"status": "GREEN"},
    )
    assert "LIVE FANDUEL GAME TOTAL" in html
    assert "<b>62.5</b>" in html
    assert "projection weight <b>0%</b>" in html


def test_v18_reuses_frozen_v17_render_and_model_helpers():
    source = inspect.getsource(page)
    assert "import cfb_over_under_clean_page_v17 as frozen_page" in source
    assert "frozen_page._step1" in source
    assert "frozen_page._step2" in source
    assert "frozen_page._step3_readable" in source
    assert "frozen_page._model_step" in source
    assert "frozen_page._cert_step" in source
    assert "frozen_page._final" in source
    assert "frozen_page.runtime_slate.analyze_game" in source


def test_v18_market_is_threshold_not_projection_formula():
    source = inspect.getsource(page)
    assert "0% projection weight" in source
    assert "market_adapter.market_line" in source
    assert "project_matchup(" not in source
    assert "apply_to_raw(" not in source


def test_v18_does_not_import_legacy_step1_or_step2_ui():
    source = inspect.getsource(page)
    assert "cfb_over_under_matchup_ui_v1" not in source
    assert "cfb_over_under_matchup_ui_v2" not in source
    assert "cfb_over_under_matchup_ui_v15" not in source
    assert "cfb_over_under_matchup_ui_v16" not in source
