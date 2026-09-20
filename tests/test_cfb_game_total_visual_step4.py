from __future__ import annotations

import cfb_game_total_clean_page_v27 as page
import streamlit_memory_lazy_router_v172 as router


def test_step4_team_evidence_contract() -> None:
    identity = {
        "away": {"team": "Purdue", "conference": "Big Ten", "logo": "https://example.com/purdue.png"},
        "home": {"team": "UCLA", "conference": "Big Ten", "logo": "https://example.com/ucla.png"},
    }
    away = {
        "team": "Purdue", "record": "1-1", "ppg": 40.0, "allowed_pg": 28.5,
        "point_diff_pg": 11.5, "recent_form": "WL", "sample_games": 2, "quality": "READY",
        "source": "Verified team evidence",
    }
    home = {
        "team": "UCLA", "record": "2-0", "ppg": 36.5, "allowed_pg": 17.0,
        "point_diff_pg": 19.5, "recent_form": "WW", "sample_games": 2, "quality": "READY",
        "source": "Verified team evidence",
    }

    html = page._team_evidence_html_v27(identity, away, home)

    assert 'data-testid="gt227-team-evidence"' in html
    assert page.STEP4_TEAM_EVIDENCE_MARKER in html
    for expected in (
        "TEAM EVIDENCE", "Purdue", "UCLA", "40.0", "28.5", "11.5",
        "36.5", "17.0", "19.5", "Recent Form", "PPG", "Allowed PPG",
        "Point Diff", "VS", "1-1", "2-0",
    ):
        assert expected in html
    assert html.count('class="gt227-formchip w"') == 3
    assert html.count('class="gt227-formchip l"') == 1
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_step4_missing_data_stays_pending() -> None:
    identity = {"away": {"team": "Away"}, "home": {"team": "Home"}}
    html = page._team_evidence_html_v27(identity, {}, {})
    assert "Pending" in html
    assert 'data-state="PENDING"' in html
    assert "Trending" not in html
    assert "Edge" not in html


def test_step4_router_activates_v27_only_for_game_total() -> None:
    assert router.ACTIVE_PAGE == "cfb_game_total_clean_page_v27"
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v171"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert router.MAY_MODIFY_PROJECTION is False
