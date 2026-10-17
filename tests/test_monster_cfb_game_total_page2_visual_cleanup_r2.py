from pathlib import Path


def _text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_r2_is_presentation_only_successor() -> None:
    text = _text("cfb_game_total_page2_visual_cleanup_r2.py")
    assert "import cfb_game_total_page2_complete_repair_r1 as prior" in text
    assert 'R1_PARENT = "cfb_game_total_page2_complete_repair_r1"' in text
    assert "MAY_MODIFY_MODEL = False" in text
    assert "MAY_MODIFY_PROJECTION = False" in text
    assert "MAY_MODIFY_PROBABILITY = False" in text
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in text


def test_team_evidence_css_is_loaded_and_logos_are_bounded() -> None:
    text = _text("cfb_game_total_page2_visual_cleanup_r2.py")
    assert "team_evidence_ui.STEP4_TEAM_EVIDENCE_CSS" in text
    assert "max-width:46px!important" in text
    assert "max-height:46px!important" in text
    assert ".gtp2r2-team-wrap .gt204-sectionhead{display:none!important}" in text


def test_stage6_uses_clean_renderer_without_raw_markup_artifact() -> None:
    import cfb_game_total_page2_visual_cleanup_r2 as cleanup

    html = cleanup.build_stage6_clean_html(
        {
            "away_offense_vs_home_defense": {
                "offense_team": "Mississippi St.",
                "read_title": "Slight defensive edge",
                "read_note": "The verified matchup profile tilts defense",
                "read_tone": "tough",
                "verified_tiles": 3,
            },
            "home_offense_vs_away_defense": {
                "offense_team": "LSU",
                "read_title": "Slight offensive edge",
                "read_note": "The verified matchup profile tilts offense",
                "read_tone": "fav",
                "verified_tiles": 3,
            },
        }
    )
    assert "Tough Matchup + Favorable Team" in html
    assert "Mississippi St." in html
    assert "LSU" in html
    assert "&lt;/div&gt;" not in html
    assert "<pre" not in html
    assert "```" not in html


def test_stage7_has_one_clean_header_and_reuses_verified_cards() -> None:
    text = _text("cfb_game_total_page2_visual_cleanup_r2.py")
    assert "Stage 7 • Team Evidence" in text
    assert "_team_evidence_html_v23" in text
    assert "gtp2r2-team-wrap" in text


def test_route_pointer_activates_cleanup_r2_and_restores_same_seam() -> None:
    route = _text("streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py")
    assert 'CFB_PAGE2_RUNTIME = "cfb_game_total_page2_visual_cleanup_r2"' in route
    assert "original_page2_runtime = prior.SAME_PAGE_RUNTIME" in route
    assert "prior.SAME_PAGE_RUNTIME = CFB_PAGE2_RUNTIME" in route
    assert "prior.SAME_PAGE_RUNTIME = original_page2_runtime" in route
    assert "MAY_MODIFY_PAGE1 = False" in route
    assert "MAY_MODIFY_OTHER_SPORTS = False" in route
