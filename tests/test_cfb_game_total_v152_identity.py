from __future__ import annotations


def _game() -> dict:
    return {
        "away_team": "Syracuse",
        "home_team": "Pittsburgh",
        "away_espn_team_id": "183",
        "home_espn_team_id": "221",
        "kickoff_display": "7:30 PM ET",
        "venue": "Acrisure Stadium",
        "broadcast": "ESPN",
        "status": "Scheduled",
    }


def _profiles() -> tuple[dict, dict]:
    return (
        {"team": "Syracuse", "conference": "ACC", "ap_rank": None},
        {"team": "Pittsburgh", "conference": "ACC", "ap_rank": None},
    )


def _visuals() -> dict:
    return {
        "away": {
            "team_id": "183",
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/183.png",
            "exact_identity": True,
        },
        "home": {
            "team_id": "221",
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/221.png",
            "exact_identity": True,
        },
    }


def test_identity_verified_requires_both_exact_ids_and_logos() -> None:
    from cfb_game_total_clean_page_v3 import _identity_state

    away, home = _profiles()
    state = _identity_state(_game(), away, home, _visuals())

    assert state["verified"] is True
    assert state["status_label"] == "IDENTITY VERIFIED"
    assert state["away"]["team_id"] == "183"
    assert state["home"]["team_id"] == "221"
    assert state["away"]["logo"].endswith("/183.png")
    assert state["home"]["logo"].endswith("/221.png")
    assert state["away"]["team"] == "Syracuse"
    assert state["home"]["team"] == "Pittsburgh"


def test_missing_one_exact_team_id_forces_identity_check() -> None:
    from cfb_game_total_clean_page_v3 import _identity_state

    away, home = _profiles()
    visuals = _visuals()
    visuals["home"] = {
        "team_id": "",
        "logo": "",
        "exact_identity": False,
    }
    game = _game()
    game.pop("home_espn_team_id")

    state = _identity_state(game, away, home, visuals)

    assert state["verified"] is False
    assert state["status_label"] == "IDENTITY CHECK"
    assert state["home"]["team_id"] == ""
    assert state["home"]["logo"] == ""


def test_optional_game_metadata_does_not_fake_team_identity() -> None:
    from cfb_game_total_clean_page_v3 import _identity_state

    away, home = _profiles()
    game = _game()
    game.pop("venue")
    game.pop("broadcast")

    state = _identity_state(game, away, home, _visuals())

    assert state["verified"] is True
    assert state["venue"] == "Venue unavailable"
    assert state["broadcast"] == "Broadcast unavailable"
    assert state["kickoff"] == "7:30 PM ET"
    assert state["game_status"] == "Scheduled"


def test_identity_state_exposes_conference_and_rank_context() -> None:
    from cfb_game_total_clean_page_v3 import _identity_state

    away, home = _profiles()
    away["ap_rank"] = 18
    state = _identity_state(_game(), away, home, _visuals())

    assert state["away"]["conference"] == "ACC"
    assert state["home"]["conference"] == "ACC"
    assert state["away"]["rank"] == "#18"
    assert state["home"]["rank"] == "UNRANKED"
