from __future__ import annotations

import pytest

from sports_api import wnba_step11_draftkings_provider as draftkings
from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step19f_draftkings_identity as step19f


def _game(game_id: str, game_date: str, away: str, home: str) -> dict[str, object]:
    return {
        "game_id": game_id,
        "game_date": game_date,
        "away_team_name": away,
        "home_team_name": home,
    }


def test_pho_mercury_alias_resolves_to_official_phoenix() -> None:
    assert step19f.team_identity_key_step19f("PHO Mercury") == draftkings._name_key("Phoenix Mercury")
    assert step19f.team_identity_key_step19f("TOR Tempo") == draftkings._name_key("Toronto Tempo")


def test_live_dk_tor_pho_event_maps_to_official_aug29_game() -> None:
    step19f.install_step19f_draftkings_identity()
    events = [{
        "source_event_id": "34579785",
        "event_date": "2026-08-30",
        "participants": ["PHO Mercury", "TOR Tempo"],
    }]
    games = [
        _game("1022600296", "2026-08-29", "Toronto Tempo", "Phoenix Mercury"),
        _game("1022600999", "2026-08-30", "Minnesota Lynx", "Atlanta Dream"),
    ]
    mapped = draftkings._event_game_map(events, games, slate_date="2026-08-29")
    assert mapped["34579785"]["game_id"] == "1022600296"


def test_live_dk_con_dal_event_maps_with_next_day_feed_date() -> None:
    step19f.install_step19f_draftkings_identity()
    events = [{
        "source_event_id": "34584574",
        "event_date": "2026-08-31",
        "participants": ["DAL Wings", "CON Sun"],
    }]
    games = [_game("1022600300", "2026-08-30", "Connecticut Sun", "Dallas Wings")]
    mapped = draftkings._event_game_map(events, games, slate_date="2026-08-30")
    assert mapped["34584574"]["game_id"] == "1022600300"


def test_fanduel_late_evening_utc_instant_uses_eastern_slate_date() -> None:
    event = {"openDate": "2026-08-30T01:00:00Z"}
    assert fanduel._event_date(event) == "2026-08-30"  # frozen pre-Step19F behavior
    step19f.install_step19f_draftkings_identity()
    assert fanduel._event_date(event) == "2026-08-29"
    assert step19f.fanduel_event_date_step19f(event) == "2026-08-29"


def test_fanduel_daytime_utc_instant_keeps_same_eastern_date() -> None:
    step19f.install_step19f_draftkings_identity()
    assert fanduel._event_date({"startTime": "2026-08-29T18:00:00Z"}) == "2026-08-29"


def test_unrelated_event_still_fails_closed() -> None:
    step19f.install_step19f_draftkings_identity()
    events = [{
        "source_event_id": "bad",
        "event_date": "2026-08-30",
        "participants": ["PHO Mercury", "TOR Tempo"],
    }]
    games = [_game("1022600295", "2026-08-29", "Chicago Sky", "New York Liberty")]
    with pytest.raises(draftkings.WNBAStep11DraftKingsProviderIdentityError):
        draftkings._event_game_map(events, games, slate_date="2026-08-29")
