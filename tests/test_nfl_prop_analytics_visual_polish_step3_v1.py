from datetime import datetime, timezone
from pathlib import Path

import nfl_prop_analytics_schedule_v1 as schedule
import nfl_prop_analytics_game_select_v1 as selection


def test_all_nfl_teams_have_stable_logo_urls():
    urls = {team: schedule.team_logo_url(team) for team in schedule.TEAM_NAMES}
    assert len(urls) == 32
    assert all(url.startswith("https://a.espncdn.com/i/teamlogos/nfl/500/") for url in urls.values())
    assert urls["WAS"].endswith("/wsh.png")
    assert urls["CAR"].endswith("/car.png")
    assert urls["CLE"].endswith("/cle.png")


def test_schedule_cards_render_away_and_home_logo_markers():
    source = Path("nfl_prop_analytics_schedule_v1.py").read_text()
    assert 'data-prop-team-logo="{html_lib.escape(game[\'away\'])}"' in source
    assert 'data-prop-team-logo="{html_lib.escape(game[\'home\'])}"' in source
    assert 'data-prop-logo-side="away"' in source
    assert 'data-prop-logo-side="home"' in source
    assert ".ks-pa2-logo" in source


def test_selected_matchup_renders_logos_and_explicit_kickoff_marker():
    source = Path("nfl_prop_analytics_game_select_v1.py").read_text()
    assert source.count("data-prop-selected-team-logo=") == 2
    assert "data-prop-selected-kickoff=" in source
    assert ".ks-pa3-logo" in source
    assert ".ks-pa3-kickoff" in source


def test_selected_kickoff_label_is_et():
    handoff = {"kickoff_utc": datetime(2026, 9, 27, 17, 0, tzinfo=timezone.utc).isoformat()}
    assert selection._handoff_kickoff_label(handoff) == "1:00 PM ET"


def test_polish_does_not_enable_prop_or_market_logic():
    assert schedule.PLAYER_PROP_LOGIC is False
    assert schedule.MAY_MODIFY_PASSING_YARDS is False
    assert selection.PLAYER_PROP_LOGIC is False
    assert selection.ROSTER_LOGIC is False
    assert selection.MAY_MODIFY_PASSING_YARDS is False
