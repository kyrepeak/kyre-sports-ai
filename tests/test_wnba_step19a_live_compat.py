from __future__ import annotations

from sports_api import wnba_step11_draftkings_provider as dk
from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step19a_live_compat as compat


def _ou(line: float):
    return [
        {"isPlayerSelection": True, "runnerName": "Player Over", "result": {"type": "OVER"}, "handicap": line},
        {"isPlayerSelection": True, "runnerName": "Player Under", "result": {"type": "UNDER"}, "handicap": line},
    ]


def test_draftkings_pho_mercury_alias_is_explicit_and_canonical() -> None:
    assert compat.draftkings_team_identity_key("PHO Mercury") == dk._name_key("Phoenix Mercury")
    assert compat.draftkings_team_identity_key("PHX Mercury") == dk._name_key("Phoenix Mercury")


def test_fanduel_event_date_uses_eastern_slate_day() -> None:
    assert compat.fanduel_event_date_eastern({"openDate": "2026-08-30T02:00:00.000Z"}) == "2026-08-29"


def test_fanduel_player_tabs_use_current_public_slugs() -> None:
    document = {"layout": {"tabs": [
        {"id": 168, "title": "Player Points"}, {"id": 169, "title": "Player Assists"},
        {"id": 170, "title": "Player Rebounds"}, {"id": 171, "title": "Player Combos"},
        {"id": 26, "title": "1st Quarter"},
    ]}}
    assert compat.fanduel_relevant_tab_slugs(document) == ["player-points", "player-assists", "player-rebounds", "player-combos"]


def test_fanduel_player_stat_scope_accepts_only_p_r_a_or_pra() -> None:
    assert compat.fanduel_market_stat_current({"marketType": "PLAYER_D_TOTAL_POINTS_WNBA"}) == "points"
    assert compat.fanduel_market_stat_current({"marketType": "PLAYER_D_TOTAL_REBOUNDS_WNBA"}) == "rebounds"
    assert compat.fanduel_market_stat_current({"marketType": "PLAYER_D_TOTAL_ASSISTS_WNBA"}) == "assists"
    assert compat.fanduel_market_stat_current({"marketType": "PLAYER_D_TOTAL_POINTS_+_REBOUNDS_+_ASSISTS_WNBA"}) == "pra"
    assert compat.fanduel_market_stat_current({"marketType": "PLAYER_D_TOTAL_POINTS_+_ASSISTS_WNBA"}) is None
    assert compat.fanduel_market_stat_current({"marketType": "PLAYER_D_TOTAL_POINTS_+_REBOUNDS_WNBA"}) is None
    assert compat.fanduel_market_stat_current({"marketType": "PLAYER_D_TOTAL_REBOUNDS_+_ASSISTS_WNBA"}) is None


def test_fanduel_current_player_title_parser_is_exact() -> None:
    assert compat.fanduel_market_player_name_current(
        {"marketType": "PLAYER_B_TOTAL_POINTS_+_REBOUNDS_+_ASSISTS_WNBA", "marketName": "Alyssa Thomas - Pts + Reb + Ast"},
        _ou(31.5), "pra",
    ) == "Alyssa Thomas"
    assert compat.fanduel_market_player_name_current(
        {"marketType": "PLAYER_D_TOTAL_POINTS_WNBA", "marketName": "Kiki Rice - Points"},
        _ou(15.5), "points",
    ) == "Kiki Rice"


def test_fanduel_nested_result_type_and_handicap_form_two_way_line() -> None:
    over, under = _ou(15.5)
    assert compat.fanduel_runner_side_line_current(over) == ("over", 15.5)
    assert compat.fanduel_runner_side_line_current(under) == ("under", 15.5)


def test_fanduel_current_player_evidence_requires_exact_two_way_market() -> None:
    assert compat.fanduel_declares_player_market_current(
        {"marketType": "PLAYER_D_TOTAL_POINTS_WNBA", "marketName": "Kiki Rice - Points"}, _ou(15.5)
    ) is True
    assert compat.fanduel_declares_player_market_current(
        {"marketType": "PLAYER_TO_SCORE_35_POINTS_WNBA", "marketName": "To Score 35+"},
        [{"result": {"type": "YES"}, "handicap": 0}, {"result": {"type": "NO"}, "handicap": 0}],
    ) is False
    assert compat.fanduel_declares_player_market_current(
        {"marketType": "TOTAL_POINTS_(OVER/UNDER)", "marketName": "Total Points"}, _ou(179.5)
    ) is False


def test_installation_patches_only_compatibility_helpers() -> None:
    status = compat.install_step19a_live_provider_compat()
    assert status["installed"] is True
    assert dk._team_identity_key("PHO Mercury") == dk._name_key("Phoenix Mercury")
    assert fd._event_date({"openDate": "2026-08-30T02:00:00.000Z"}) == "2026-08-29"
    assert fd._relevant_tab_ids({"layout": {"tabs": [{"id": 168, "title": "Player Points"}]}}) == ["player-points"]
    assert fd._market_stat({"marketType": "PLAYER_B_TOTAL_POINTS_+_ASSISTS_WNBA"}) is None
    assert fd._market_player_name(
        {"marketType": "PLAYER_B_TOTAL_POINTS_+_REBOUNDS_+_ASSISTS_WNBA", "marketName": "Alyssa Thomas - Pts + Reb + Ast"},
        _ou(31.5), "pra",
    ) == "Alyssa Thomas"
    assert fd._runner_side_line({"runnerName": "Alyssa Thomas Over", "result": {"type": "OVER"}, "handicap": 20.5}) == ("over", 20.5)
    assert fd._declares_player_market({"marketType": "PLAYER_B_TOTAL_REBOUNDS_WNBA", "marketName": "Alyssa Thomas - Rebounds"}, _ou(10.5)) is True
    assert status["frozen_step11a_source_modified"] is False
    assert status["frozen_step11c_source_modified"] is False
    assert status["frozen_step11d_source_modified"] is False
