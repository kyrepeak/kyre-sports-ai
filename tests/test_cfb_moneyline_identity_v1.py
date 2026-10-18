from __future__ import annotations

from cfb_moneyline_identity_v1 import initials, resolve_game_identities


def _payload() -> dict:
    return {
        "events": [
            {
                "id": "401752999",
                "competitions": [
                    {
                        "competitors": [
                            {
                                "homeAway": "away",
                                "team": {
                                    "id": "183",
                                    "displayName": "Syracuse Orange",
                                    "shortDisplayName": "Syracuse",
                                    "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/183.png",
                                },
                            },
                            {
                                "homeAway": "home",
                                "team": {
                                    "id": "221",
                                    "displayName": "Pittsburgh Panthers",
                                    "shortDisplayName": "Pittsburgh",
                                    "logos": [
                                        {"href": "https://a.espncdn.com/i/teamlogos/ncaa/500/221.png"}
                                    ],
                                },
                            },
                        ]
                    }
                ],
            }
        ]
    }


def test_exact_verified_event_resolves_current_provider_logos() -> None:
    game = {
        "espn_event_id": "401752999",
        "away_team": "Syracuse",
        "home_team": "Pittsburgh",
    }
    identity = resolve_game_identities(game, _payload())

    assert identity["away"]["team_id"] == "183"
    assert identity["away"]["logo_url"].endswith("/183.png")
    assert identity["home"]["team_id"] == "221"
    assert identity["home"]["logo_url"].endswith("/221.png")
    assert identity["source"] == "ESPN College Football scoreboard"


def test_unsafe_or_missing_logo_falls_back_without_inventing_url() -> None:
    payload = _payload()
    payload["events"][0]["competitions"][0]["competitors"][0]["team"]["logo"] = "javascript:alert(1)"
    game = {
        "espn_event_id": "401752999",
        "away_team": "Syracuse",
        "home_team": "Pittsburgh",
    }
    identity = resolve_game_identities(game, payload)

    assert identity["away"]["logo_url"] == ""
    assert identity["away"]["fallback"] == "SY"


def test_unmatched_event_fails_closed_to_team_initials() -> None:
    identity = resolve_game_identities(
        {"espn_event_id": "no-match", "away_team": "New Mexico", "home_team": "Arizona State"},
        _payload(),
    )

    assert identity["away"]["logo_url"] == ""
    assert identity["away"]["fallback"] == "NM"
    assert identity["home"]["fallback"] == "AS"
    assert identity["source"] == "fallback initials"


def test_initials_are_stable_and_compact() -> None:
    assert initials("Arizona State") == "AS"
    assert initials("UCF") == "UC"
    assert initials("") == "CF"
