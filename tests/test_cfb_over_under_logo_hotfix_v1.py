"""Regression checks for CFB O/U ESPN logo resolver hotfix."""
from __future__ import annotations

import cfb_over_under_logo_resolver_v1 as logos


def _event():
    return {
        "id": "401858213",
        "competitions": [
            {
                "competitors": [
                    {
                        "homeAway": "away",
                        "records": [{"name": "overall", "summary": "1-1"}],
                        "team": {
                            "id": "50",
                            "location": "Florida A&M",
                            "displayName": "Florida A&M Rattlers",
                            "shortDisplayName": "Florida A&M",
                            "name": "Rattlers",
                            "abbreviation": "FAMU",
                            "slug": "florida-am-rattlers",
                        },
                    },
                    {
                        "homeAway": "home",
                        "records": [{"name": "overall", "summary": "1-0"}],
                        "team": {
                            "id": "2390",
                            "location": "Miami",
                            "displayName": "Miami Hurricanes",
                            "shortDisplayName": "Miami",
                            "name": "Hurricanes",
                            "abbreviation": "MIA",
                            "slug": "miami-hurricanes",
                        },
                    },
                ]
            }
        ],
    }


def _game():
    return {
        "game_date": "2026-09-10",
        "away_team": "Florida A&M",
        "away_team_slug": "florida-a-m",
        "home_team": "Miami (FL)",
        "home_team_slug": "miami-fl",
        "identity_key": "ncaa:999",
        "espn_event_id": "",
    }


def test_alias_match_handles_ncaa_vs_espn_team_names():
    assert logos._event_matches_game(_event(), _game()) is True


def test_exact_event_id_still_wins():
    game = _game()
    game["away_team"] = "Something Else"
    game["home_team"] = "Different Team"
    game["espn_event_id"] = "401858213"
    assert logos._event_matches_game(_event(), game) is True


def test_team_id_builds_stable_espn_logo_url_when_href_missing():
    url = logos._safe_logo_url({"id": "50"})
    assert url == "https://a.espncdn.com/i/teamlogos/ncaa/500/50.png"


def test_scoreboard_extracts_both_florida_am_and_miami_logos():
    payload = {"events": [_event()]}
    out = logos._extract_from_scoreboard(payload, _game())

    assert out["away"]["team_id"] == "50"
    assert out["away"]["logo"].endswith("/50.png")
    assert out["home"]["team_id"] == "2390"
    assert out["home"]["logo"].endswith("/2390.png")


def test_resolve_visuals_uses_scoreboard_before_summary(monkeypatch):
    monkeypatch.setattr(
        logos.schedule.frozen,
        "_fetch_espn_fbs_payload",
        lambda day: ({"events": [_event()]}, []),
    )

    called = {"summary": False}

    def fake_summary(event_id):
        called["summary"] = True
        return {}, []

    monkeypatch.setattr(logos, "_summary_payload", fake_summary)
    out = logos.resolve_visuals(_game())

    assert out["away"]["logo"].endswith("/50.png")
    assert out["home"]["logo"].endswith("/2390.png")
    assert called["summary"] is False


def test_resolve_visuals_uses_summary_if_scoreboard_is_incomplete(monkeypatch):
    game = _game()
    game["espn_event_id"] = "401858213"

    monkeypatch.setattr(
        logos.schedule.frozen,
        "_fetch_espn_fbs_payload",
        lambda day: ({}, []),
    )
    monkeypatch.setattr(
        logos,
        "_summary_payload",
        lambda event_id: (
            {
                "header": {
                    "competitions": _event()["competitions"],
                }
            },
            [],
        ),
    )

    out = logos.resolve_visuals(game)
    assert out["away"]["logo"].endswith("/50.png")
    assert out["home"]["logo"].endswith("/2390.png")


def test_no_event_match_returns_empty_instead_of_guessing():
    game = _game()
    game["away_team"] = "Alabama"
    game["away_team_slug"] = "alabama"
    game["home_team"] = "Auburn"
    game["home_team_slug"] = "auburn"
    out = logos._extract_from_scoreboard({"events": [_event()]}, game)
    assert out == {"away": {}, "home": {}}
