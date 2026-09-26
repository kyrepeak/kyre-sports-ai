from pathlib import Path
import inspect

import nfl_prop_analytics_matchup_shell_v1 as shell


def test_cleanup_step2_stops_rendering_obsolete_shell():
    render_source = inspect.getsource(shell.render_matchup_shell)
    assert "Position shell ready" not in render_source
    assert "Roster data is intentionally deferred to the next step." not in render_source
    assert "_team_position_shell(away" not in render_source
    assert "_team_position_shell(home" not in render_source


def test_cleanup_step2_preserves_header_and_page2_contract():
    source = Path("nfl_prop_analytics_matchup_shell_v1.py").read_text()
    assert 'data-nfl-prop-analytics-step4-page2="v1"' in source
    assert 'data-prop-page2-premium-header="v1"' in source
    assert "_premium_matchup_header(handoff)" in source
    assert "resolve_matchup_handoff()" in source
    assert "return handoff" in source


def test_cleanup_step2_keeps_legacy_helper_compatible_but_unrendered():
    html = shell._team_position_shell("CAR", "Panthers", "away")
    assert 'data-prop-page2-team-shell="CAR"' in html
    assert html.count('data-prop-page2-roster-state="pending"') == 4
