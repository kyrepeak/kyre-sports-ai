from __future__ import annotations

import cfb_game_total_step4_matchup_v1 as step4


def _identity(away="Coastal Carolina", home="Delaware"):
    return {
        "away": {"team": away, "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/324.png"},
        "home": {"team": home, "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/48.png"},
    }


def _away_full():
    return {
        "team": "Coastal Carolina",
        "ppg": 27.4,
        "points_allowed_pg": 24.1,
        "pass_yards_pg": 245.0,
        "pass_yards_allowed_pg": 218.0,
        "rush_yards_pg": 168.0,
        "rush_yards_allowed_pg": 142.0,
        "epa_per_play": 0.18,
        "epa_allowed_per_play": 0.05,
    }


def _home_full():
    return {
        "team": "Delaware",
        "ppg": 31.2,
        "points_allowed_pg": 19.3,
        "pass_yards_pg": 226.0,
        "pass_yards_allowed_pg": 201.0,
        "rush_yards_pg": 151.0,
        "rush_yards_allowed_pg": 128.0,
        "epa_per_play": 0.14,
        "epa_allowed_per_play": 0.02,
    }


def test_step4_is_presentation_only():
    assert step4.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step4.MAY_MODIFY_PROJECTION is False
    assert step4.STEP4_PRESENTATION_MARKER == "CFB_GAME_TOTAL_STEP4_MATCHUP_OFF_DEF_PASS_RUSH_EPA_ACTIVE"


def test_step4_full_matchup_contract_is_ready():
    contract = step4.build_step4_contract(_identity(), _away_full(), _home_full())
    assert contract["state"] == "READY"
    assert contract["coverage"] == 1.0
    assert contract["epa_ready"] is True
    away_battle = contract["away_offense_vs_home_defense"]
    home_battle = contract["home_offense_vs_away_defense"]
    assert away_battle["offense_team"] == "Coastal Carolina"
    assert away_battle["defense_team"] == "Delaware"
    assert home_battle["offense_team"] == "Delaware"
    assert [row["label"] for row in away_battle["rows"]] == [
        "Off vs Def",
        "Passing",
        "Rushing",
        "EPA / Play",
    ]


def test_step4_partial_verified_matchup_is_check_not_fake_ready():
    away = {
        "team": "Coastal Carolina",
        "ppg": 24.0,
        "points_allowed_pg": 31.0,
    }
    home = {
        "team": "Delaware",
        "ppg": 42.0,
        "points_allowed_pg": 7.0,
    }
    contract = step4.build_step4_contract(_identity(), away, home)
    assert contract["state"] == "CHECK"
    assert contract["coverage"] == 0.25
    assert contract["epa_ready"] is False
    assert "does not fabricate" in contract["epa_note"] or "leaves EPA blank" in contract["epa_note"]


def test_step4_no_matchup_values_is_data_limited():
    contract = step4.build_step4_contract(
        _identity(),
        {"team": "Coastal Carolina"},
        {"team": "Delaware"},
    )
    assert contract["state"] == "DATA LIMITED"


def test_step4_reads_official_pass_and_rush_rows():
    away = {
        "team": "Coastal Carolina",
        "ppg": 24,
        "points_allowed_pg": 31,
        "official_stats": {
            "passing_offense": {
                "label": "Passing Offense",
                "value_numeric": 233.5,
                "rank": 41,
            },
            "rushing_offense": {
                "label": "Rushing Offense",
                "value_numeric": 177.2,
                "rank": 35,
            },
            "passing_defense": {
                "label": "Passing Yards Allowed",
                "value_numeric": 205.0,
                "rank": 29,
            },
            "rushing_defense": {
                "label": "Rushing Defense",
                "value_numeric": 139.0,
                "rank": 44,
            },
        },
    }
    home = {
        "team": "Delaware",
        "ppg": 42,
        "points_allowed_pg": 7,
        "official_stats": {
            "passing_offense": {
                "label": "Passing Offense",
                "value_numeric": 210.0,
                "rank": 55,
            },
            "rushing_offense": {
                "label": "Rushing Offense",
                "value_numeric": 166.0,
                "rank": 39,
            },
            "passing_defense": {
                "label": "Passing Yards Allowed",
                "value_numeric": 188.0,
                "rank": 18,
            },
            "rushing_defense": {
                "label": "Rushing Defense",
                "value_numeric": 121.0,
                "rank": 24,
            },
        },
    }
    contract = step4.build_step4_contract(_identity(), away, home)
    battle = contract["away_offense_vs_home_defense"]
    rows = {row["label"]: row for row in battle["rows"]}
    assert rows["Passing"]["offense_value"] == 233.5
    assert rows["Passing"]["defense_value"] == 188.0
    assert rows["Rushing"]["offense_value"] == 177.2
    assert rows["Rushing"]["defense_value"] == 121.0
    assert contract["state"] == "CHECK"


def test_step4_render_matches_wide_matchup_layout():
    html = step4.render_step4_html("CHECK", _identity(), _away_full(), _home_full())
    assert 'data-testid="gt157-step-4"' in html
    assert 'data-testid="gt170-step4-away-off-home-def"' in html
    assert 'data-testid="gt170-step4-home-off-away-def"' in html
    assert 'data-testid="gt170-step4-matchup-read"' in html
    assert 'data-testid="gt170-step4-epa-integrity"' in html
    assert ">Matchup<" in html
    assert "Off vs Def · Pass · Rush · EPA" in html
    assert "Passing" in html
    assert "Rushing" in html
    assert "EPA / Play" in html
    details_tag = html.split(">", 1)[0]
    assert " open" not in details_tag


def test_step4_is_universal_not_cert_matchup_hardcoded():
    identity = _identity("Oregon", "Penn State")
    away = dict(_away_full(), team="Oregon")
    home = dict(_home_full(), team="Penn State")
    html = step4.render_step4_html("CHECK", identity, away, home)
    assert "Oregon Offense" in html
    assert "Penn State Defense" in html
    assert "Coastal Carolina Offense" not in html
    assert "Delaware Defense" not in html


def test_step4_css_is_wide_and_mobile_safe():
    assert ".gt170-step4" in step4.STEP4_CSS
    assert ".gt170-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in step4.STEP4_CSS
    assert "@media(max-width:760px)" in step4.STEP4_CSS
