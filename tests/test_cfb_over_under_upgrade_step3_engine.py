"""Regression checks for CFB O/U Upgrade Step 3 offense-vs-defense engine."""
from __future__ import annotations

import copy

import cfb_over_under_matchup_engine_v1 as engine


def _profile(team, division="FBS"):
    return {
        "team": team,
        "team_slug": team.lower().replace(" ", "-"),
        "division_context": division if division == "FCS" else "",
        "data_source": (
            "NCAA official FCS schedule + NCAA.com FCS team stats"
            if division == "FCS"
            else "NCAA official FBS schedule + NCAA.com team stats/AP rankings"
        ),
        "official_stats": {},
    }


def _item(team, rank, value="100.0", field_size=136):
    return {
        "team": team,
        "rank": rank,
        "value": value,
        "field_size": field_size,
        "headers": ["Rank", "Team", "Value"],
        "row": [str(rank), team, value],
    }


def _complete_tables():
    tables = {}
    offense_keys = {row[1] for row in engine._DIMENSIONS}
    defense_keys = {row[2] for row in engine._DIMENSIONS}
    for metric in offense_keys:
        tables[metric] = {
            engine.frozen_team._canonical_name("Oklahoma"): _item("Oklahoma", 10),
            engine.frozen_team._canonical_name("Michigan"): _item("Michigan", 100),
        }
    for metric in defense_keys:
        tables[metric] = {
            engine.frozen_team._canonical_name("Oklahoma"): _item("Oklahoma", 10),
            engine.frozen_team._canonical_name("Michigan"): _item("Michigan", 100),
        }
    return tables


def _base_raw(line=50.5):
    return {
        "version": "CFB OVER/UNDER MODEL V1 • STEP 8 RAW TOTAL MODEL",
        "ready": True,
        "analysis_line": float(line),
        "projected_away_points": 27.0,
        "projected_home_points": 27.0,
        "projected_total": 54.0,
        "over_probability": 0.60,
        "under_probability": 0.40,
        "push_probability": 0.0,
        "model_lean": "OVER",
        "reliability": 0.84,
        "feature_coverage": {"score": 0.85},
        "confidence": "MEDIUM",
        "structural_total_sigma": 13.5,
        "total_uncertainty_90": {"low": 31.8, "high": 76.2},
        "components": {},
        "sportsbook_input_used": False,
        "market_price_used": False,
        "monte_carlo_used": False,
    }


def test_category_discovery_finds_all_eight_pair_families():
    html = """
    <select>
      <option value="/stats/football/fbs/scoring/team/28">Scoring Offense</option>
      <option value="/stats/football/fbs/scoring-defense/team/28">Scoring Defense</option>
      <option value="/stats/football/fbs/total-offense/team/21">Total Offense</option>
      <option value="/stats/football/fbs/total-defense/team/22">Total Defense</option>
      <option value="/stats/football/fbs/passing-offense/team/25">Passing Offense</option>
      <option value="/stats/football/fbs/passing-defense/team/26">Passing Yards Allowed</option>
      <option value="/stats/football/fbs/rushing-offense/team/23">Rushing Offense</option>
      <option value="/stats/football/fbs/rushing-defense/team/24">Rushing Defense</option>
      <option value="/stats/football/fbs/third-down/team/701">3rd Down Conversion Pct</option>
      <option value="/stats/football/fbs/third-down-defense/team/702">3rd Down Conversion Pct Defense</option>
      <option value="/stats/football/fbs/red-zone/team/703">Red Zone Offense</option>
      <option value="/stats/football/fbs/red-zone-defense/team/704">Red Zone Defense</option>
      <option value="/stats/football/fbs/sacks-allowed/team/705">Sacks Allowed</option>
      <option value="/stats/football/fbs/team-sacks/team/706">Team Sacks</option>
      <option value="/stats/football/fbs/turnovers-lost/team/707">Turnovers Lost</option>
      <option value="/stats/football/fbs/turnovers-gained/team/708">Turnovers Gained</option>
    </select>
    """
    found = engine._discover_categories(html)
    required = {row[1] for row in engine._DIMENSIONS} | {row[2] for row in engine._DIMENSIONS}
    assert required.issubset(set(found))


def test_dimension_edge_points_toward_offense_when_offense_rank_is_better():
    out = engine._dimension(
        "passing",
        _item("Oklahoma", 1),
        _item("Michigan", 136),
        0.20,
    )
    assert out["ready"] is True
    assert out["edge"] == 1.0
    assert out["weighted_edge"] == 0.20
    assert out["edge_label"] == "STRONG OFFENSE EDGE"


def test_build_engine_creates_opposite_team_adjustments(monkeypatch):
    monkeypatch.setattr(
        engine,
        "_load_division_tables",
        lambda *a, **k: (_complete_tables(), {"attempts": [], "tables_loaded": 16}),
    )
    result = engine.build_matchup_engine(
        {"game_date": "2026-09-12"},
        _profile("Oklahoma"),
        _profile("Michigan"),
    )

    assert result["model_ready"] is True
    assert result["same_division"] is True
    assert result["away_offense"]["points_adjustment"] > 0
    assert result["home_offense"]["points_adjustment"] < 0
    assert result["coverage"] == 1.0
    assert abs(result["away_offense"]["points_adjustment"]) <= engine.MAX_TEAM_MATCHUP_ADJUSTMENT
    assert abs(result["home_offense"]["points_adjustment"]) <= engine.MAX_TEAM_MATCHUP_ADJUSTMENT


def test_cross_division_rank_pools_fail_closed(monkeypatch):
    called = {"tables": False}

    def should_not_call(*a, **k):
        called["tables"] = True
        return {}, {}

    monkeypatch.setattr(engine, "_load_division_tables", should_not_call)
    result = engine.build_matchup_engine(
        {},
        _profile("Oklahoma", "FBS"),
        _profile("Howard", "FCS"),
    )

    assert result["ready"] is True
    assert result["model_ready"] is False
    assert result["same_division"] is False
    assert "not directly comparable" in result["reason"]
    assert called["tables"] is False


def test_apply_to_raw_changes_mean_but_preserves_frozen_reliability_and_sigma():
    matchup = {
        "model_ready": True,
        "coverage": 0.90,
        "away_offense": {"points_adjustment": 2.0},
        "home_offense": {"points_adjustment": -0.5},
    }
    raw = engine.apply_to_raw(_base_raw(), matchup)

    assert raw["upgrade_step3_applied"] is True
    assert raw["base_projected_total"] == 54.0
    assert raw["projected_total"] == 55.5
    assert raw["projected_away_points"] == 29.0
    assert raw["projected_home_points"] == 26.5
    assert raw["reliability"] == 0.84
    assert raw["structural_total_sigma"] == 13.5
    assert raw["analysis_line_matchup_weight"] == 0.0
    assert raw["sportsbook_input_used"] is False
    assert raw["monte_carlo_used"] is False


def test_analysis_line_cannot_change_step3_projection():
    matchup = {
        "model_ready": True,
        "coverage": 1.0,
        "away_offense": {"points_adjustment": 1.25},
        "home_offense": {"points_adjustment": 0.75},
    }
    low_line = engine.apply_to_raw(_base_raw(45.5), copy.deepcopy(matchup))
    high_line = engine.apply_to_raw(_base_raw(65.5), copy.deepcopy(matchup))

    assert low_line["projected_total"] == high_line["projected_total"] == 56.0
    assert low_line["projected_away_points"] == high_line["projected_away_points"]
    assert low_line["projected_home_points"] == high_line["projected_home_points"]
    assert low_line["over_probability"] != high_line["over_probability"]


def test_engine_below_coverage_threshold_leaves_frozen_projection_unchanged():
    raw = _base_raw()
    out = engine.apply_to_raw(
        raw,
        {
            "model_ready": False,
            "coverage": 0.25,
            "reason": "matchup evidence below minimum",
        },
    )
    assert out["upgrade_step3_applied"] is False
    assert out["projected_total"] == 54.0
    assert out["projected_away_points"] == 27.0
    assert out["projected_home_points"] == 27.0
