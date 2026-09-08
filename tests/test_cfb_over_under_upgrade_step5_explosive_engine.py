"""Regression checks for CFB O/U Upgrade Step 5 explosive engine."""
from __future__ import annotations

import cfb_over_under_explosive_engine_v1 as exp


def _pass_off(team: str, games: int, att: int, comp: int, yds: int):
    return {
        "team": team,
        "headers": ["Rank", "Team", "G", "Pass Att", "Pass Com", "Int", "Pass Yds", "Pass TD", "Pass Eff"],
        "row": ["1", team, str(games), str(att), str(comp), "0", str(yds), "3", "180.0"],
    }


def _pass_ypc(team: str, games: int, comp: int, att: int, yds: int):
    return {
        "team": team,
        "headers": ["Rank", "Team", "G", "Pass Com", "Pass Att", "Pass Yds", "Avg"],
        "row": ["1", team, str(games), str(comp), str(att), str(yds), f"{yds/comp:.2f}"],
    }


def _pass_def(team: str, games: int, att: int, comp: int, yds: int):
    return {
        "team": team,
        "headers": ["Rank", "Team", "G", "Opp Pass", "Opp Cpl", "Opp Int", "Opp Pass <br/>Yds", "Opp Pass <br/>TDs", "Pass Eff"],
        "row": ["1", team, str(games), str(att), str(comp), "1", str(yds), "1", "120.0"],
    }


def _rush_off(team: str, games: int, rush: int, yds: int):
    return {
        "team": team,
        "headers": ["Rank", "Team", "G", "Rush", "Rush Yds", "Yds/Rush", "Rush TD", "YPG"],
        "row": ["1", team, str(games), str(rush), str(yds), f"{yds/rush:.2f}", "2", f"{yds/games:.1f}"],
    }


def _rush_def(team: str, games: int, rush: int, yds: int):
    return {
        "team": team,
        "headers": ["Rank", "Team", "G", "Opp Rush", "Opp Rush Yds", "Yds/Rush", "Opp Rush TDs", "YPG"],
        "row": ["1", team, str(games), str(rush), str(yds), f"{yds/rush:.2f}", "2", f"{yds/games:.1f}"],
    }


def _key(name: str) -> str:
    return exp.frozen_team._canonical_name(name)


def _bundle(division: str, team: str, *, pass_att=30, pass_comp=20, pass_yds=240,
            def_att=30, def_comp=18, def_yds=210, rush=30, rush_yds=150,
            def_rush=30, def_rush_yds=120, include_rush=True):
    key = _key(team)
    tables = {
        "pass_offense": {key: _pass_off(team, 2, pass_att, pass_comp, pass_yds)},
        "pass_yards_per_completion": {key: _pass_ypc(team, 2, pass_comp, pass_att, pass_yds)},
        "pass_defense": {key: _pass_def(team, 2, def_att, def_comp, def_yds)},
        "rush_offense": {key: _rush_off(team, 2, rush, rush_yds)} if include_rush else {},
        "rush_defense": {key: _rush_def(team, 2, def_rush, def_rush_yds)},
    }
    return {
        "division": division,
        "tables": tables,
        "baselines": {
            "pass_ypa": 7.2,
            "pass_ypc": 11.8,
            "pass_ypa_allowed": 7.2,
            "pass_ypc_allowed": 11.8,
            "rush_ypr": 4.5,
            "rush_ypr_allowed": 4.5,
        },
    }


def _pace_bundle(team: str):
    return {"total_offense": {_key(team): {"team": team}}}


def test_pass_metrics_parse_ncaa_headers():
    off = exp._pass_offense_metrics(
        _pass_off("Miami (FL)", 1, 35, 30, 428),
        _pass_ypc("Miami (FL)", 1, 30, 35, 428),
    )
    defense = exp._pass_defense_metrics(
        _pass_def("Miami (FL)", 1, 42, 22, 221)
    )

    assert round(off["yards_per_attempt"], 3) == round(428 / 35, 3)
    assert abs(off["yards_per_completion"] - (428 / 30)) < 0.01
    assert round(defense["yards_per_attempt_allowed"], 3) == round(221 / 42, 3)
    assert round(defense["yards_per_completion_allowed"], 3) == round(221 / 22, 3)


def test_rush_metrics_parse_offense_and_defense():
    off = exp._rush_metrics(_rush_off("Miami (FL)", 1, 32, 121), False)
    defense = exp._rush_metrics(_rush_def("Miami (FL)", 1, 23, 78), True)
    assert round(off["yards_per_rush"], 2) == 3.78
    assert round(defense["yards_per_rush_allowed"], 2) == 3.39


def test_discover_categories_prefers_team_selector_paths():
    html = """
    <select>
      <option value="/stats/football/fbs/current/individual/8">Passing Efficiency</option>
      <option value="/stats/football/fbs/current/team/465">Team Passing Efficiency</option>
      <option value="/stats/football/fbs/current/team/40">Team Passing Efficiency Defense</option>
      <option value="/stats/football/fbs/current/team/741">Passing Yards per Completion</option>
      <option value="/stats/football/fbs/current/team/23">Rushing Offense</option>
      <option value="/stats/football/fbs/current/team/24">Rushing Defense</option>
    </select>
    """
    found = exp._discover_categories(html)
    assert set(found) == {
        "pass_offense",
        "pass_defense",
        "pass_yards_per_completion",
        "rush_offense",
        "rush_defense",
    }
    assert "/team/465" in found["pass_offense"]


def test_ratio_signal_is_bounded():
    assert exp._ratio_signal(20, 10, 0.1) == 1.0
    assert exp._ratio_signal(1, 10, 0.1) == -1.0
    assert exp._ratio_signal(None, 10, 0.1) is None


def test_build_engine_handles_mixed_fcs_fbs_and_partial_away_rush(monkeypatch):
    fbs = _bundle(
        "FBS",
        "Miami (FL)",
        pass_att=35,
        pass_comp=30,
        pass_yds=428,
        def_att=42,
        def_comp=22,
        def_yds=221,
        rush=32,
        rush_yds=121,
        def_rush=23,
        def_rush_yds=78,
    )
    fcs = _bundle(
        "FCS",
        "Florida A&M",
        pass_att=55,
        pass_comp=27,
        pass_yds=352,
        def_att=42,
        def_comp=26,
        def_yds=347,
        def_rush=75,
        def_rush_yds=295,
        include_rush=False,
    )

    fbs_pace = _pace_bundle("Miami (FL)")
    fcs_pace = _pace_bundle("Florida A&M")

    monkeypatch.setattr(
        exp.step4,
        "_load_pace_division",
        lambda division: ((fcs_pace, {}) if division == "FCS" else (fbs_pace, {})),
    )
    monkeypatch.setattr(
        exp,
        "_load_explosive_division",
        lambda division: ((fcs, {}) if division == "FCS" else (fbs, {})),
    )

    out = exp.build_explosive_engine(
        {},
        {"team": "Florida A&M", "team_slug": "florida-a-m", "division_context": "FBS"},
        {"team": "Miami (FL)", "team_slug": "miami-fl", "division_context": "FBS"},
    )

    assert out["model_ready"] is True
    assert out["away_division"] == "FCS"
    assert out["home_division"] == "FBS"
    assert out["mixed_division"] is True
    assert out["away_offense"]["coverage"] == exp.PASS_WEIGHT
    assert out["home_offense"]["coverage"] == 1.0
    assert abs(out["away_offense"]["points_adjustment"]) <= exp.MAX_TEAM_EXPLOSIVE_ADJUSTMENT
    assert abs(out["home_offense"]["points_adjustment"]) <= exp.MAX_TEAM_EXPLOSIVE_ADJUSTMENT
    assert out["true_explosive_pass_rate_available"] is False
    assert out["true_explosive_run_rate_available"] is False


def test_side_fails_closed_below_minimum_coverage():
    fbs = _bundle("FBS", "Miami (FL)")
    empty = {"division": "FBS", "tables": {}, "baselines": fbs["baselines"]}
    side = exp._side(
        {"team": "Miami (FL)", "team_slug": "miami-fl"},
        {"team": "Opponent", "team_slug": "opponent"},
        fbs,
        empty,
        "FBS",
        "FBS",
    )
    assert side["model_ready"] is False
    assert side["coverage"] == 0.0
    assert side["points_adjustment"] == 0.0


def test_early_sample_shrinks_explosive_adjustment():
    offense = {
        "games": 1,
        "yards_per_attempt": 10.0,
        "yards_per_completion": 15.0,
    }
    defense = {
        "games": 1,
        "yards_per_attempt_allowed": 9.0,
        "yards_per_completion_allowed": 14.0,
    }
    rush_off = {"games": 1, "yards_per_rush": 6.5}
    rush_def = {"games": 1, "yards_per_rush_allowed": 6.0}
    factor = exp._sample_factor(offense, defense, rush_off, rush_def)
    assert factor == 0.2


def test_apply_to_raw_preserves_frozen_sigma_and_reliability():
    base = {
        "version": "STEP4",
        "ready": True,
        "projected_away_points": 24.0,
        "projected_home_points": 28.0,
        "projected_total": 52.0,
        "structural_total_sigma": 9.5,
        "reliability": 0.72,
        "analysis_line": 50.5,
        "components": {"step4_total_pace_adjustment": 0.5},
    }
    engine = {
        "model_ready": True,
        "coverage": 0.8,
        "away_offense": {"points_adjustment": 0.4},
        "home_offense": {"points_adjustment": -0.1},
    }

    out = exp.apply_to_raw(base, engine)

    assert out["upgrade_step5_applied"] is True
    assert round(out["projected_total"], 3) == 52.3
    assert out["structural_total_sigma"] == 9.5
    assert out["reliability"] == 0.72
    assert out["analysis_line_explosive_weight"] == 0.0
    assert out["sportsbook_input_used"] is False
    assert out["monte_carlo_used"] is False


def test_apply_to_raw_fails_closed_when_engine_not_ready():
    base = {"version": "STEP4", "ready": True, "projected_total": 50.0}
    out = exp.apply_to_raw(
        base,
        {"model_ready": False, "coverage": 0.0, "reason": "missing evidence"},
    )
    assert out["upgrade_step5_applied"] is False
    assert out["projected_total"] == 50.0
    assert out["explosive_engine_reason"] == "missing evidence"
