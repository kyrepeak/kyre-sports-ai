from __future__ import annotations

import cfb_game_total_step4_multisource_v1 as multi


DIRECTORY_HTML = """
<html><body>
<a href="/2026/team/415/index.html">Miami (FL)</a>
<a href="749/index.html">Wake Forest</a>
<a href="/2026/team/193/index.html">Miami (OH)</a>
</body></html>
"""

MIAMI_HTML = """
<table>
<tr><th></th><th>Miami (FL)</th><th>Opponents</th></tr>
<tr><td>Scoring: Games - Points</td><td>2 - 122</td><td>2 - 13</td></tr>
<tr><td>Rushing: Attempts - Yards - TD</td><td>76 - 551 - 6</td><td>44 - 115 - 0</td></tr>
<tr><td>Passing: Yards</td><td>854</td><td>291</td></tr>
<tr><td>Passing: Attempts - Completions - Interceptions - TD</td><td>64 - 57 - 1 - 11</td><td>68 - 33 - 0 - 0</td></tr>
<tr><td>Fumbles: Number - Lost</td><td>2 - 1</td><td>1 - 0</td></tr>
<tr><td>3rd Down Conversions: Conversion %</td><td>64.29%</td><td>20.69%</td></tr>
<tr><td>Red Zone: Success %</td><td>80%</td><td>100%</td></tr>
</table>
"""

MIAMI_SACK_HTML = """
<table>
<tr><th>Name</th><th>Yr</th><th>Pos</th><th>G</th><th>Sacks</th><th>Sack Yards</th><th>Sacks/G</th></tr>
<tr><td></td><td>Total</td><td></td><td></td><td>2</td><td>3.0</td><td>16</td><td>1.50</td></tr>
<tr><td></td><td>Opponents</td><td></td><td></td><td>2</td><td>0.0</td><td>0</td><td>0.00</td></tr>
</table>
"""

WAKE_HTML = """
<table>
<tr><th></th><th>Wake Forest</th><th>Opponents</th></tr>
<tr><td>Scoring: Games - Points</td><td>2 - 76</td><td>2 - 52</td></tr>
<tr><td>Rushing: Attempts - Yards - TD</td><td>74 - 389 - 4</td><td>76 - 275 - 3</td></tr>
<tr><td>Passing: Yards</td><td>581</td><td>485</td></tr>
<tr><td>Passing: Attempts - Completions - Interceptions - TD</td><td>62 - 38 - 0 - 4</td><td>75 - 60 - 0 - 3</td></tr>
<tr><td>Fumbles: Number - Lost</td><td>3 - 0</td><td>2 - 1</td></tr>
<tr><td>3rd Down Conversions: Conversion %</td><td>46.15%</td><td>48.15%</td></tr>
<tr><td>Red Zone: Success %</td><td>90%</td><td>100%</td></tr>
</table>
"""

WAKE_SACK_HTML = """
<table>
<tr><th>Name</th><th>Yr</th><th>Pos</th><th>G</th><th>Sacks</th><th>Sack Yards</th><th>Sacks/G</th></tr>
<tr><td></td><td>Total</td><td></td><td></td><td>2</td><td>5.0</td><td>36</td><td>2.50</td></tr>
<tr><td></td><td>Opponents</td><td></td><td></td><td>2</td><td>2.0</td><td>12</td><td>1.00</td></tr>
</table>
"""


def test_multisource_adapter_is_presentation_only():
    assert multi.MAY_MODIFY_PROJECTION is False
    assert multi.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert multi.SOURCE == "cfbstats.com"


def test_directory_parser_resolves_absolute_and_relative_team_links():
    directory = multi._parse_directory(DIRECTORY_HTML, 2026)
    assert directory["miamifl"]["team_id"] == "415"
    assert directory["wakeforest"]["team_id"] == "749"
    assert directory["miamioh"]["team_id"] == "193"

    assert multi._resolve_team(directory, {"team": "Miami (FL)"})["team_id"] == "415"
    assert multi._resolve_team(directory, {"team": "Wake Forest"})["team_id"] == "749"


def test_team_parser_extracts_complete_display_metrics():
    miami = multi._parse_team_metrics(MIAMI_HTML, MIAMI_SACK_HTML)
    wake = multi._parse_team_metrics(WAKE_HTML, WAKE_SACK_HTML)

    assert miami["pass_yards_pg"] == 427.0
    assert miami["pass_yards_allowed_pg"] == 145.5
    assert miami["rush_yards_pg"] == 275.5
    assert miami["rush_yards_allowed_pg"] == 57.5
    assert miami["third_down_offense_pct"] == 64.29
    assert miami["third_down_defense_pct"] == 20.69
    assert miami["red_zone_offense_pct"] == 80.0
    assert miami["red_zone_defense_pct"] == 100.0
    assert miami["team_sacks_pg"] == 1.5
    assert miami["sacks_allowed_pg"] == 0.0
    assert miami["turnovers_lost_pg"] == 1.0
    assert miami["turnovers_gained_pg"] == 0.0

    assert wake["pass_yards_pg"] == 290.5
    assert wake["pass_yards_allowed_pg"] == 242.5
    assert wake["rush_yards_pg"] == 194.5
    assert wake["rush_yards_allowed_pg"] == 137.5
    assert wake["third_down_offense_pct"] == 46.15
    assert wake["third_down_defense_pct"] == 48.15
    assert wake["red_zone_offense_pct"] == 90.0
    assert wake["red_zone_defense_pct"] == 100.0
    assert wake["team_sacks_pg"] == 2.5
    assert wake["sacks_allowed_pg"] == 1.0
    assert wake["turnovers_lost_pg"] == 0.0
    assert wake["turnovers_gained_pg"] == 0.5


def test_fallback_dimensions_are_display_only_and_complete():
    miami = multi._parse_team_metrics(MIAMI_HTML, MIAMI_SACK_HTML)
    wake = multi._parse_team_metrics(WAKE_HTML, WAKE_SACK_HTML)
    dims = multi._fallback_dimensions(miami, wake)

    assert set(dims) == {
        "passing",
        "rushing",
        "third_down",
        "red_zone",
        "sack_pressure",
        "turnovers",
    }
    assert all(row["ready"] for row in dims.values())
    assert all(row["edge"] is None for row in dims.values())
    assert dims["rushing"]["offense_value"] == "275.5"
    assert dims["rushing"]["defense_value"] == "137.5"
    assert dims["third_down"]["offense_value"] == "64.3%"
    assert dims["red_zone"]["defense_value"] == "100.0%"
    assert dims["sack_pressure"]["offense_value"] == "0.00/g"
    assert dims["sack_pressure"]["defense_value"] == "2.50/g"


def test_merge_missing_dimensions_never_overwrites_certified_ncaa_edge():
    fallback = {
        "ready": True,
        "source": "cfbstats.com",
        "away_offense": {
            "dimensions": {
                key: row
                for key, row in multi._fallback_dimensions(
                    multi._parse_team_metrics(MIAMI_HTML, MIAMI_SACK_HTML),
                    multi._parse_team_metrics(WAKE_HTML, WAKE_SACK_HTML),
                ).items()
            }
        },
        "home_offense": {
            "dimensions": {
                key: row
                for key, row in multi._fallback_dimensions(
                    multi._parse_team_metrics(WAKE_HTML, WAKE_SACK_HTML),
                    multi._parse_team_metrics(MIAMI_HTML, MIAMI_SACK_HTML),
                ).items()
            }
        },
    }
    engine = {
        "ready": True,
        "away_offense": {
            "dimensions": {
                "passing": {
                    "ready": True,
                    "edge": 0.24,
                    "offense_value": "427.0",
                    "defense_value": "242.5",
                }
            }
        },
        "home_offense": {"dimensions": {}},
    }

    merged, filled = multi.merge_missing_dimensions(engine, fallback)

    assert merged["away_offense"]["dimensions"]["passing"]["edge"] == 0.24
    assert merged["away_offense"]["dimensions"]["rushing"]["edge"] is None
    assert merged["home_offense"]["dimensions"]["red_zone"]["ready"] is True
    assert merged["display_fallback_source"] == "cfbstats.com"
    assert filled == 11


def test_official_audit_snapshot_wins_when_secondary_source_disagrees():
    official = multi._official_metrics(2026, {"team": "Wake Forest"})
    assert official["third_down_defense_pct"] == 44.828
    assert official["official_snapshot"] is True

    merged, disagreements = multi._merge_official_metrics(
        {"third_down_defense_pct": 48.15, "rush_yards_pg": 194.5},
        official,
    )
    assert merged["third_down_defense_pct"] == 44.828
    assert merged["rush_yards_pg"] == 194.5
    assert any(
        row["field"] == "third_down_defense_pct"
        and row["secondary"] == 48.15
        and row["official"] == 44.828
        and row["winner"] == "official"
        for row in disagreements
    )


def test_complete_official_snapshot_skips_secondary_network(monkeypatch):
    def fail_directory(_season):
        raise AssertionError("secondary directory must not be called")

    monkeypatch.setattr(multi, "_load_directory", fail_directory)

    result = multi.build_display_fallback(
        None,
        {"team": "Miami (FL)"},
        {"team": "Wake Forest"},
    )

    assert result["ready"] is True
    assert result["season"] == 2026
    assert result["diagnostics"]["directory"]["skipped"] is True
    assert "official team athletics audit" in result["source"]
    assert "cfbstats fallback available" in result["source"]
    assert all(
        row["ready"]
        for side in ("away_offense", "home_offense")
        for row in result[side]["dimensions"].values()
    )
