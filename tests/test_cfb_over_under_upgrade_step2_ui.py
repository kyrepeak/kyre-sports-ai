"""Regression checks for CFB O/U Intelligence V2 Upgrade Step 2 UI."""
from __future__ import annotations

import inspect

import cfb_over_under_matchup_ui_v2 as ui


def _context():
    metrics = {}
    for idx, key in enumerate(ui.rankings._METRIC_ORDER, start=1):
        metrics[key] = {
            "key": key,
            "label": key.replace("_", " ").title(),
            "rank": idx,
            "value": str(100 + idx),
            "available": True,
        }
    side = {
        "team": "Michigan",
        "conference": "Big Ten",
        "division": "FBS",
        "record": "2-0",
        "home_record": "2-0",
        "away_record": "0-0",
        "recent_form": "W-W",
        "ap": {"rank": 16, "state": "ranked"},
        "coaches": {"rank": 15, "state": "ranked"},
        "cfp": {"rank": None, "state": "not_released"},
        "metrics": metrics,
        "metric_coverage": 1.0,
        "metric_ready": 8,
        "metric_total": 8,
    }
    away = dict(side)
    away["team"] = "Oklahoma"
    away["conference"] = "SEC"
    away["record"] = "2-0"
    away["ap"] = {"rank": 10, "state": "ranked"}
    away["coaches"] = {"rank": 11, "state": "ranked"}
    return {
        "ready": True,
        "away": away,
        "home": side,
        "metric_coverage": 1.0,
        "presentation_only": True,
        "projection_weight": 0.0,
        "selection_weight": 0.0,
        "ranking_selection_weight": 0.0,
    }


def test_rank_display_states():
    assert ui._rank_display({"rank": 7, "state": "ranked"}) == "#7"
    assert ui._rank_display({"rank": None, "state": "unranked"}) == "NR"
    assert ui._rank_display({"rank": None, "state": "not_released"}) == "NOT YET"
    assert ui._rank_display({"rank": None, "state": "not_applicable"}) == "N/A"
    assert ui._rank_display({"rank": None, "state": "unavailable"}) == "—"


def test_rankings_panel_shows_polls_records_conference_and_category_ranks(monkeypatch):
    monkeypatch.setattr(ui.rankings, "build_ranking_context", lambda *a, **k: _context())

    html = ui._rankings_panel(
        {"game_date": "2026-09-12"},
        {"team": "Oklahoma"},
        {"team": "Michigan"},
    )

    assert "RANKINGS + CONFERENCE + RECORDS" in html
    assert "Oklahoma" in html
    assert "Michigan" in html
    assert "SEC" in html
    assert "Big Ten" in html
    assert "#10" in html
    assert "#16" in html
    assert "NOT YET" in html
    assert "KYRE matchup ranking profile" in html
    assert "DISPLAY EVIDENCE" in html
    assert "MODEL WEIGHT 0%" in html


def test_rankings_panel_fails_closed_when_provider_not_ready(monkeypatch):
    monkeypatch.setattr(
        ui.rankings,
        "build_ranking_context",
        lambda *a, **k: {"ready": False},
    )
    html = ui._rankings_panel({}, {}, {})
    assert "Supplemental ranking tables are unavailable" in html
    assert "no ranking value is invented" in html


def test_enhanced_v2_keeps_step1_hero_and_appends_step2(monkeypatch):
    monkeypatch.setattr(ui, "_FROZEN_STEP1_HERO", lambda *a, **k: "<STEP1>logos</STEP1>")
    monkeypatch.setattr(ui, "_rankings_panel", lambda *a, **k: "<STEP2>ranks</STEP2>")

    html = ui._enhanced_hero_v2({}, {}, {})
    assert html == "<STEP1>logos</STEP1><STEP2>ranks</STEP2>"


def test_wrapper_temporarily_replaces_step1_hero_and_restores(monkeypatch):
    original = ui.frozen_v1._enhanced_hero
    seen = {}

    monkeypatch.setattr(ui.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(ui.st, "markdown", lambda *a, **k: None)

    def fake_render(*args, **kwargs):
        seen["during"] = ui.frozen_v1._enhanced_hero
        return "ok"

    monkeypatch.setattr(ui.frozen_v1, "render_over_under_hub", fake_render)
    result = ui.render_over_under_hub()

    assert result == "ok"
    assert seen["during"] is ui._enhanced_hero_v2
    assert ui.frozen_v1._enhanced_hero is original


def test_step2_is_display_only_and_preserves_step1_freeze():
    source = inspect.getsource(ui).lower()

    assert ui.FROZEN_UPGRADE == "cfb_over_under_matchup_ui_v1"
    assert ui.MARKET == "Over/Under"
    assert "model weight 0%" in source
    assert "not a new power-rating formula" in source

    forbidden = (
        "projected_total =",
        "over_probability =",
        "under_probability =",
        "selection_probability =",
        "rank_slate(",
        "analyze_game(",
        "expected_value",
        "np.random",
    )
    for token in forbidden:
        assert token not in source
