from __future__ import annotations

import inspect

import cfb_moneyline_clean_page_v1 as page
import cfb_over_under_logo_resolver_v3 as logo_v3


def _game() -> dict[str, object]:
    return {
        "game_date": "2026-09-17",
        "kickoff_iso": "2026-09-17T19:30:00-04:00",
        "kickoff_et": "7:30 PM ET",
        "away_team": "Syracuse",
        "home_team": "Pittsburgh",
        "away_rank": None,
        "home_rank": None,
        "away_espn_team_id": "183",
        "home_espn_team_id": "221",
        "identity_verified": True,
        "date_matches_query": True,
    }


def test_phoenix_time_comes_from_timezone_aware_kickoff_iso() -> None:
    assert page._kickoff_phoenix(_game()) == "4:30 PM Phoenix"


def test_matchup_label_uses_phoenix_and_not_eastern() -> None:
    label = page._matchup_label(_game())
    assert label == "Syracuse @ Pittsburgh • 4:30 PM Phoenix"
    assert " ET" not in label


def test_exact_espn_logo_resolver_is_reused_without_name_guessing() -> None:
    visuals = page._resolve_visuals(_game())
    assert visuals["away"]["team_id"] == "183"
    assert visuals["home"]["team_id"] == "221"
    assert visuals["away"]["logo"] == logo_v3.ESPN_LOGO_CDN_TEMPLATE.format(team_id="183")
    assert visuals["home"]["logo"] == logo_v3.ESPN_LOGO_CDN_TEMPLATE.format(team_id="221")
    assert logo_v3.NAME_BASED_LOGO_MATCHING is False
    assert logo_v3.FUZZY_LOGO_MATCHING is False


def test_page_declares_frozen_moneyline_math_and_zero_sportsbook_weight() -> None:
    assert page.FROZEN_MONEYLINE_OWNER == "cfb_moneyline_hub_v5"
    assert page.FROZEN_RAW_MODEL == "cfb_moneyline_model_v1"
    assert page.FROZEN_FINAL_MODEL == "cfb_moneyline_final_v1"
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_page_calls_frozen_slate_instead_of_recomputing_probability() -> None:
    source = inspect.getsource(page)
    assert "slate.analyze_game(game, selected_day)" in source
    assert "final_model.rank_slate(rows, limit=5)" in source
    assert "project_matchup(" not in source


def test_deep_evidence_is_collapsed_by_default() -> None:
    source = inspect.getsource(page.render_moneyline_hub)
    assert 'expanded=False' in source
    assert "Advanced model evidence" in source
    assert "Frozen team evidence" in source


def test_quick_read_and_why_sections_are_first_class() -> None:
    source = inspect.getsource(page)
    assert "QUICK READ" in source
    assert "WHY THE MODEL LEANS" in source
    assert "PHOENIX TIME" in source
