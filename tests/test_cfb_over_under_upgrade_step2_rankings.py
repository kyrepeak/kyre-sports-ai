"""Regression checks for CFB O/U Intelligence V2 Upgrade Step 2 rankings."""
from __future__ import annotations

import cfb_over_under_rankings_v1 as rankings


def _profile(team="Michigan", conference="Big Ten"):
    return {
        "team": team,
        "team_slug": team.lower().replace(" ", "-"),
        "conference": conference,
        "record_text": "2-0",
        "record": {"wins": 2, "losses": 0, "ties": 0, "games": 2},
        "home_record": {"wins": 2, "losses": 0, "ties": 0, "games": 2},
        "away_record": {"wins": 0, "losses": 0, "ties": 0, "games": 0},
        "recent_form": "W-W",
        "ap_rank": 16,
        "rank_source": "NCAA AP rankings",
        "official_stats": {
            "total_offense": {
                "headers": ["Rank", "Team", "G", "YPG"],
                "row": ["24", team, "2", "411.5"],
                "value": "411.5",
            },
            "scoring_offense": {
                "headers": ["Rank", "Team", "G", "PPG"],
                "row": ["31", team, "2", "32.0"],
                "value": "32.0",
            },
            "total_defense": {
                "headers": ["Rank", "Team", "G", "YPG"],
                "row": ["8", team, "2", "251.0"],
                "value": "251.0",
            },
            "scoring_defense": {
                "headers": ["Rank", "Team", "G", "PPG"],
                "row": ["6", team, "2", "12.0"],
                "value": "12.0",
            },
        },
        "data_source": "NCAA official FBS schedule + NCAA.com team stats/AP rankings",
    }


def test_supplemental_category_discovery_finds_pass_rush_both_sides():
    html = """
    <select>
      <option value="/stats/football/fbs/passing-offense">Passing Offense</option>
      <option value="/stats/football/fbs/rushing-offense">Rushing Offense</option>
      <option value="/stats/football/fbs/passing-yards-allowed">Passing Yards Allowed</option>
      <option value="/stats/football/fbs/rushing-defense">Rushing Defense</option>
    </select>
    """
    found = rankings._discover_supplemental_categories(html)
    assert set(found) == {
        "passing_offense",
        "rushing_offense",
        "passing_defense",
        "rushing_defense",
    }


def test_rank_from_stat_item_uses_named_rank_column():
    item = {
        "headers": ["Team", "Rank", "G", "YPG"],
        "row": ["Michigan", "7", "2", "300.0"],
    }
    assert rankings._rank_from_stat_item(item) == 7


def test_metric_entry_prefers_frozen_certified_core_stat():
    profile = _profile()
    supplemental = {
        "total_offense": {
            "headers": ["Rank", "Team", "YPG"],
            "row": ["99", "Michigan", "1.0"],
            "value": "1.0",
        }
    }
    out = rankings._metric_entry(profile, supplemental, "total_offense")
    assert out["rank"] == 24
    assert out["value"] == "411.5"


def test_metric_entry_uses_supplemental_pass_rush_stat():
    profile = _profile()
    supplemental = {
        "passing_offense": {
            "headers": ["Rank", "Team", "YPG"],
            "row": ["7", "Michigan", "301.5"],
            "value": "301.5",
        }
    }
    out = rankings._metric_entry(profile, supplemental, "passing_offense")
    assert out["rank"] == 7
    assert out["available"] is True


def test_poll_state_distinguishes_ranked_unranked_and_unavailable():
    profile = _profile()
    mapping = {
        rankings.frozen_team._canonical_name("Michigan"): {
            "rank": 14,
            "team_text": "Michigan",
        }
    }
    ranked = rankings._poll_state(profile, mapping, 25)
    unranked = rankings._poll_state(
        _profile("Arizona State", "Big 12"),
        mapping,
        25,
    )
    unavailable = rankings._poll_state(profile, {}, 0)

    assert ranked == {"rank": 14, "state": "ranked"}
    assert unranked == {"rank": None, "state": "unranked"}
    assert unavailable == {"rank": None, "state": "unavailable"}


def test_cfp_is_not_released_before_november(monkeypatch):
    monkeypatch.setattr(
        rankings,
        "_load_supplemental_stat_ranks",
        lambda *a, **k: ({"away": {}, "home": {}}, {"attempts": [], "metrics_found": 0}),
    )
    monkeypatch.setattr(
        rankings,
        "_load_poll_rankings",
        lambda url, provider: ({}, {"rows": 0, "attempts": [], "provider": provider}),
    )

    game = {"game_date": "2026-09-12"}
    out = rankings.build_ranking_context(game, _profile("Oklahoma", "SEC"), _profile())

    assert out["cfp_released_for_date"] is False
    assert out["away"]["cfp"]["state"] == "not_released"
    assert out["home"]["cfp"]["state"] == "not_released"
    assert out["projection_weight"] == 0.0
    assert out["selection_weight"] == 0.0
    assert out["ranking_selection_weight"] == 0.0


def test_fcs_profile_does_not_receive_fbs_poll_rank():
    profile = _profile("Howard", "MEAC")
    profile["division_context"] = "FCS"
    profile["ap_rank"] = None
    profile["rank_source"] = "FCS ranking not used"
    side = rankings._side_context(
        profile,
        {},
        {},
        25,
        {},
        25,
        True,
    )

    assert side["division"] == "FCS"
    assert side["coaches"]["state"] == "not_applicable"
    assert side["cfp"]["state"] == "not_applicable"
