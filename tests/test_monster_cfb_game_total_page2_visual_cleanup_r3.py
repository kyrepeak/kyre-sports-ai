from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R3 = ROOT / "cfb_game_total_page2_visual_cleanup_r3.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_fast_switch_step9_v1.py"


def test_r3_successor_exists_and_owns_page2_runtime() -> None:
    assert R3.exists(), "R3 presentation successor must exist before activation"
    router = ROUTER.read_text(encoding="utf-8")
    assert 'CFB_PAGE2_RUNTIME = "cfb_game_total_page2_visual_cleanup_r3"' in router


def test_r3_removes_nested_legacy_team_evidence_header_and_sizes_logos_inline() -> None:
    assert R3.exists(), "R3 presentation successor must exist before import"
    import cfb_game_total_page2_visual_cleanup_r3 as r3

    identity = {
        "away": {"team": "Mississippi St.", "conference": "SEC", "logo": "https://example.com/ms.png"},
        "home": {"team": "LSU", "conference": "SEC", "logo": "https://example.com/lsu.png"},
    }
    away = {
        "team": "Mississippi St.", "record": "4-1", "ppg": 39.0,
        "allowed_pg": 28.0, "point_diff_pg": 11.0, "recent_form": "WWWWL",
        "sample_games": 5, "quality": "GREEN", "source": "verified source",
    }
    home = {
        "team": "LSU", "record": "4-2", "ppg": 42.0,
        "allowed_pg": 18.5, "point_diff_pg": 23.5, "recent_form": "WLWWL",
        "sample_games": 6, "quality": "GREEN", "source": "verified source",
    }

    html = r3.build_stage7_clean_html(identity, away, home)
    assert 'gt204-sectionhead' not in html
    assert '🏈 TEAM EVIDENCE' not in html
    assert html.count('<h3>Team Evidence</h3>') == 1
    assert 'data-testid="gtp2r3-team-evidence"' in html
    assert 'max-width:46px' in html
    assert 'max-height:46px' in html


def test_r3_is_presentation_only_and_preserves_frozen_logic_contract() -> None:
    assert R3.exists(), "R3 presentation successor must exist before import"
    import cfb_game_total_page2_visual_cleanup_r3 as r3

    assert r3.MAY_MODIFY_PAGE1 is False
    assert r3.MAY_MODIFY_MODEL is False
    assert r3.MAY_MODIFY_PROJECTION is False
    assert r3.MAY_MODIFY_PROBABILITY is False
    assert r3.MAY_MODIFY_RANKING is False
    assert r3.MAY_MODIFY_SELECTION is False
    assert r3.MAY_MODIFY_MARKET_OWNERSHIP is False
    assert r3.MAY_MODIFY_OTHER_SPORTS is False
    assert r3.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
