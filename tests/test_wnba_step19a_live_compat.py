from __future__ import annotations

from sports_api import wnba_step11_draftkings_provider as dk
from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step19a_live_compat as compat


def test_draftkings_pho_mercury_alias_is_explicit_and_canonical() -> None:
    assert compat.draftkings_team_identity_key("PHO Mercury") == dk._name_key("Phoenix Mercury")
    assert compat.draftkings_team_identity_key("PHX Mercury") == dk._name_key("Phoenix Mercury")


def test_fanduel_event_date_uses_eastern_slate_day() -> None:
    event = {"openDate": "2026-08-30T02:00:00.000Z"}
    assert compat.fanduel_event_date_eastern(event) == "2026-08-29"


def test_fanduel_player_tabs_use_current_public_slugs() -> None:
    document = {
        "layout": {
            "tabs": [
                {"id": 168, "title": "Player Points"},
                {"id": 169, "title": "Player Assists"},
                {"id": 170, "title": "Player Rebounds"},
                {"id": 171, "title": "Player Combos"},
                {"id": 26, "title": "1st Quarter"},
            ]
        }
    }
    assert compat.fanduel_relevant_tab_slugs(document) == [
        "player-points",
        "player-assists",
        "player-rebounds",
        "player-combos",
    ]


def test_fanduel_nested_result_type_and_handicap_form_two_way_line() -> None:
    over = {
        "runnerName": "Kiki Rice Over",
        "result": {"type": "OVER"},
        "handicap": 15.5,
    }
    under = {
        "runnerName": "Kiki Rice Under",
        "result": {"type": "UNDER"},
        "handicap": 15.5,
    }
    assert compat.fanduel_runner_side_line_current(over) == ("over", 15.5)
    assert compat.fanduel_runner_side_line_current(under) == ("under", 15.5)


def test_installation_patches_only_compatibility_helpers() -> None:
    status = compat.install_step19a_live_provider_compat()
    assert status["installed"] is True
    assert dk._team_identity_key("PHO Mercury") == dk._name_key("Phoenix Mercury")
    assert fd._event_date({"openDate": "2026-08-30T02:00:00.000Z"}) == "2026-08-29"
    assert fd._relevant_tab_ids({"layout": {"tabs": [{"id": 168, "title": "Player Points"}]}}) == ["player-points"]
    assert fd._runner_side_line({"runnerName": "Alyssa Thomas Over", "result": {"type": "OVER"}, "handicap": 20.5}) == ("over", 20.5)
    assert status["frozen_step11a_source_modified"] is False
    assert status["frozen_step11c_source_modified"] is False
    assert status["frozen_step11d_source_modified"] is False
