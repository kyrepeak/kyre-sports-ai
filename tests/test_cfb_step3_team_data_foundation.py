"""Regression checks for College Football Step 3 team data foundation."""
from __future__ import annotations

import copy
import inspect

import cfb_hub_v3 as hub
import cfb_team_data_v1 as team_data


def _team(name, slug, conference, score, is_home, winner=False, rank=None):
    return {
        "isHome": is_home,
        "isWinner": winner,
        "score": score,
        "nameShort": name,
        "seoname": slug,
        "conferenceSeo": conference,
        "teamRank": rank,
    }


def _contest(
    contest_id,
    date,
    away,
    home,
    away_score,
    home_score,
    neutral=False,
):
    return {
        "contestId": str(contest_id),
        "startDate": date,
        "startTime": "7:30 PM ET",
        "gameState": "F",
        "finalMessage": "Final",
        "neutralSite": neutral,
        "teams": [
            _team(
                away[0], away[1], away[2], away_score, False,
                away_score > home_score, away[3] if len(away) > 3 else None,
            ),
            _team(
                home[0], home[1], home[2], home_score, True,
                home_score > away_score, home[3] if len(home) > 3 else None,
            ),
        ],
    }


def _payload():
    texas = ("Texas", "texas", "sec", 5)
    ohio = ("Ohio State", "ohio-state", "big-ten", 1)
    mich = ("Michigan", "michigan", "big-ten", 16)
    ark = ("Arkansas", "arkansas", "sec", None)

    return {
        "data": {
            "schedule": {
                "contests": [
                    _contest("1", "09/01/2026", mich, texas, 20, 31),
                    _contest("2", "09/05/2026", texas, ark, 28, 14),
                    _contest("3", "09/06/2026", ohio, mich, 35, 17),
                    _contest("4", "09/09/2026", ark, ohio, 10, 42),
                    # Must be excluded by the as-of date guard.
                    _contest("5", "09/20/2026", texas, ohio, 24, 27),
                ]
            }
        }
    }


def _game_identity():
    return {
        "game_id": "900",
        "game_date": "2026-09-12",
        "away_team": "Ohio State",
        "away_team_slug": "ohio-state",
        "away_conference": "big-ten",
        "away_rank": 1,
        "home_team": "Texas",
        "home_team_slug": "texas",
        "home_conference": "sec",
        "home_rank": 5,
    }


def test_season_ledger_builds_records_scoring_splits_recent_and_future_guard():
    ledgers, meta, diag = team_data._season_games_from_payload(_payload(), "2026-09-12")

    texas_key = team_data._canonical_name("texas")
    ohio_key = team_data._canonical_name("ohio-state")

    assert len(ledgers[texas_key]) == 2
    assert len(ledgers[ohio_key]) == 2
    assert diag["completed_contests"] == 4
    assert diag["future_contests_ignored"] == 1

    texas = team_data._schedule_foundation(texas_key, ledgers)
    assert texas["record_text"] == "2-0"
    assert texas["ppg"] == 29.5
    assert texas["points_allowed_pg"] == 17.0
    assert texas["point_diff_pg"] == 12.5
    assert texas["home_record"]["wins"] == 1
    assert texas["away_record"]["wins"] == 1
    assert texas["recent_form"] == "WW"
    assert texas["sos_coverage"] == 1.0
    assert texas["sos_opponent_win_pct"] is not None
    assert meta[texas_key]["conference"] == "sec"


def test_ncaa_stat_categories_are_discovered_dynamically_not_hardcoded_ids():
    html = """
    <select id="team">
      <option value="/stats/football/fbs/current/team/28">Scoring Offense</option>
      <option value="/stats/football/fbs/current/team/21">Total Offense</option>
      <option value="/stats/football/fbs/current/team/29">Scoring Defense</option>
      <option value="/stats/football/fbs/current/team/22">Total Defense</option>
      <option value="/stats/football/fbs/current/team/113">Turnover Margin</option>
    </select>
    """
    categories = team_data._discover_stat_categories(html)

    assert set(categories) == {
        "scoring_offense",
        "total_offense",
        "scoring_defense",
        "total_defense",
        "turnover_margin",
    }
    assert categories["scoring_offense"]["url"].endswith("/current/team/28")


def test_stat_table_matches_ohio_state_abbreviation_and_extracts_metric_value():
    html = """
    <table>
      <thead><tr><th>Rank</th><th>Team</th><th>G</th><th>PPG</th></tr></thead>
      <tbody>
        <tr><td>1</td><td>Ohio St.</td><td>2</td><td>49.0</td></tr>
        <tr><td>7</td><td>Texas</td><td>2</td><td>29.5</td></tr>
      </tbody>
    </table>
    """
    targets = {
        "away": team_data._team_keys("Ohio State", "ohio-state"),
        "home": team_data._team_keys("Texas", "texas"),
    }
    values = team_data._stat_page_values(html, targets)

    assert values["away"]["value"] == "49.0"
    assert values["away"]["value_numeric"] == 49.0
    assert values["home"]["value"] == "29.5"


def test_profiles_preserve_team_identity_rank_stats_and_quality_without_model_math():
    ledgers, meta, _ = team_data._season_games_from_payload(_payload(), "2026-09-12")
    game = _game_identity()
    stats = {
        "away": {
            "scoring_offense": {"label": "NCAA Scoring Offense", "value": "49.0"},
            "scoring_defense": {"label": "NCAA Scoring Defense", "value": "13.5"},
            "total_offense": {"label": "NCAA Total Offense", "value": "510.0"},
        },
        "home": {
            "scoring_offense": {"label": "NCAA Scoring Offense", "value": "29.5"},
            "scoring_defense": {"label": "NCAA Scoring Defense", "value": "17.0"},
            "total_offense": {"label": "NCAA Total Offense", "value": "430.0"},
        },
    }
    rankings = {
        team_data._canonical_name("Ohio St."): {"rank": 1},
        team_data._canonical_name("Texas"): {"rank": 5},
    }

    away = team_data._build_profile("away", game, ledgers, meta, stats, rankings)
    home = team_data._build_profile("home", game, ledgers, meta, stats, rankings)

    assert away["team"] == "Ohio State"
    assert away["record_text"] == "2-0"
    assert away["ap_rank"] == 1
    assert away["rank_source"] == "NCAA AP rankings"
    assert len(away["official_stats"]) == 3
    assert away["data_quality"]["grade"] == "READY"

    assert home["team"] == "Texas"
    assert home["record_text"] == "2-0"
    assert home["ap_rank"] == 5
    assert home["data_quality"]["grade"] == "READY"


def test_unranked_team_is_not_marked_missing_when_ap_table_loaded():
    profile = {
        "record": {"wins": 2, "losses": 0, "ties": 0, "games": 2},
        "ppg": 31.0,
        "points_allowed_pg": 17.0,
        "recent_form": "WW",
        "sos_coverage": 1.0,
        "official_stats": {
            "scoring_offense": {"value": "31.0"},
            "scoring_defense": {"value": "17.0"},
        },
        "ap_rank": None,
        "rank_source": "NCAA AP rankings — unranked",
    }
    quality = team_data._quality(profile)
    assert quality["components"]["ranking"] is True
    assert quality["grade"] == "READY"


def test_hub_team_card_shows_step3_evidence_and_no_projection():
    ledgers, meta, _ = team_data._season_games_from_payload(_payload(), "2026-09-12")
    game = _game_identity()
    profile = team_data._build_profile(
        "home",
        game,
        ledgers,
        meta,
        {
            "home": {
                "scoring_offense": {
                    "label": "NCAA Scoring Offense",
                    "value": "29.5",
                },
                "scoring_defense": {
                    "label": "NCAA Scoring Defense",
                    "value": "17.0",
                },
            }
        },
        {team_data._canonical_name("Texas"): {"rank": 5}},
    )

    html = hub._team_card(profile)

    assert "Texas" in html
    assert "2-0" in html
    assert "29.5" in html
    assert "17.0" in html
    assert "Opp win % (SOS)" in html
    assert "Home split" in html and "Away split" in html
    assert "NCAA Scoring Offense" in html
    assert "evidence only" in html


def test_step3_is_additive_data_foundation_only():
    source = inspect.getsource(team_data) + "\n" + inspect.getsource(hub)

    assert hub.FROZEN_CFB_HUB == "cfb_hub_v2"
    assert hub.CFB_MARKETS == ["Moneyline", "Over/Under", "Game Total"]

    required = (
        "recent_form",
        "home_record",
        "away_record",
        "sos_opponent_win_pct",
        "official_stats",
        "data_quality",
        "NCAA_AP_RANKINGS",
        "NCAA_STATS_INDEX",
    )
    for token in required:
        assert token in source

    forbidden = (
        "import numpy",
        "np.random",
        "def simulate",
        "def win_probability",
        "fair_odds =",
        "projected_score =",
        "projected_total =",
        "sportsbook_line =",
    )
    for token in forbidden:
        assert token not in source
