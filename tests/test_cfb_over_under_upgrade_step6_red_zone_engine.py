"""Regression checks for CFB O/U Upgrade Step 6 red-zone engine."""
from __future__ import annotations

import cfb_over_under_red_zone_engine_v1 as rz


def _row(team: str, games: int, attempts: int, rush_td: int, pass_td: int, fg: int, *, defense=False, rank="-"):
    if defense:
        headers = ["Rank", "Team", "G", "Opp RZAtt", "Opp RZ Rush TD", "Opp RZ Pass TD", "Opp RZ FG Made", "Opp RZScores", "Pct"]
    else:
        headers = ["Rank", "Team", "G", "RZAtt", "RZ Rush TD", "RZ Pass TD", "RZ FG Made", "RZScores", "Pct"]
    scores = rush_td + pass_td + fg
    pct = scores / attempts if attempts else 0.0
    return {
        "team": team,
        "headers": headers,
        "row": [rank, team, str(games), str(attempts), str(rush_td), str(pass_td), str(fg), str(scores), f"{pct:.3f}"],
    }


def _key(name: str) -> str:
    return rz.frozen_team._canonical_name(name)


def _bundle(division: str, team: str, off_row, def_row):
    return {
        "division": division,
        "tables": {
            "red_zone_offense": {_key(team): off_row} if off_row else {},
            "red_zone_defense": {_key(team): def_row} if def_row else {},
        },
        "baselines": {
            "offense_touchdown_rate": 0.60,
            "offense_points_per_trip": 4.80,
            "defense_touchdown_rate_allowed": 0.60,
            "defense_points_per_trip_allowed": 4.80,
        },
    }


def _pace_bundle(team: str):
    return {"total_offense": {_key(team): {"team": team}}}


def test_rankless_parser_keeps_blank_rank_ties():
    html = """
    <table>
      <tr><th>Rank</th><th>Team</th><th>G</th><th>RZAtt</th><th>RZ Rush TD</th><th>RZ Pass TD</th><th>RZ FG Made</th><th>RZScores</th><th>Pct</th></tr>
      <tr><td>1</td><td>Air Force</td><td>1</td><td>4</td><td>2</td><td>1</td><td>1</td><td>4</td><td>1.000</td></tr>
      <tr><td>-</td><td>Miami (FL)</td><td>1</td><td>3</td><td>1</td><td>2</td><td>0</td><td>3</td><td>1.000</td></tr>
    </table>
    """
    rows = rz._red_zone_rows(html)
    assert _key("Air Force") in rows
    assert _key("Miami (FL)") in rows
    assert rows[_key("Miami (FL)")]["row"][0] == "-"


def test_red_zone_metrics_parse_offense():
    metrics = rz._metrics(_row("Miami (FL)", 1, 3, 1, 2, 0), False)
    assert metrics["ready"] is True
    assert metrics["attempts"] == 3.0
    assert metrics["touchdowns"] == 3.0
    assert metrics["touchdown_rate"] == 1.0
    assert metrics["scoring_rate"] == 1.0
    assert metrics["points_per_trip"] == 7.0
    assert metrics["attempts_per_game"] == 3.0


def test_red_zone_metrics_parse_defense():
    metrics = rz._metrics(_row("Florida A&M", 2, 5, 2, 1, 0, defense=True), True)
    assert metrics["ready"] is True
    assert metrics["attempts"] == 5.0
    assert metrics["touchdowns"] == 3.0
    assert metrics["touchdown_rate"] == 0.6
    assert metrics["points_per_trip"] == 4.2
    assert metrics["attempts_per_game"] == 2.5


def test_discover_red_zone_categories_uses_team_paths_only():
    html = """
    <select>
      <option value="/stats/football/fbs/current/individual/703">Red Zone Offense</option>
      <option value="/stats/football/fbs/current/team/703">Red Zone Offense</option>
      <option value="/stats/football/fbs/current/team/704">Red Zone Defense</option>
    </select>
    """
    found = rz._discover_categories(html)
    assert set(found) == {"red_zone_offense", "red_zone_defense"}
    assert found["red_zone_offense"].endswith("/team/703")
    assert found["red_zone_defense"].endswith("/team/704")


def test_sample_factor_uses_verified_red_zone_attempts():
    offense = {"attempts": 3}
    defense = {"attempts": 6}
    assert rz._sample_factor(offense, defense) == 0.25
    assert rz._sample_factor({"attempts": 20}, {"attempts": 18}) == 1.0


def test_side_uses_direct_rates_and_caps_adjustment():
    off_team = "Miami (FL)"
    def_team = "Florida A&M"
    offense_bundle = _bundle(
        "FBS",
        off_team,
        _row(off_team, 1, 3, 1, 2, 0),
        _row(off_team, 1, 2, 0, 0, 2, defense=True),
    )
    defense_bundle = _bundle(
        "FCS",
        def_team,
        _row(def_team, 2, 7, 1, 1, 4),
        _row(def_team, 2, 5, 2, 1, 0, defense=True),
    )

    side = rz._side(
        {"team": off_team, "team_slug": "miami-fl"},
        {"team": def_team, "team_slug": "florida-a-m"},
        offense_bundle,
        defense_bundle,
        "FBS",
        "FCS",
    )

    assert side["model_ready"] is True
    assert side["coverage"] == 1.0
    assert side["sample_factor"] == 0.25
    assert abs(side["points_adjustment"]) <= rz.MAX_TEAM_RED_ZONE_ADJUSTMENT


def test_side_fails_closed_when_direct_offense_row_missing():
    offense_bundle = _bundle(
        "FBS",
        "Miami (FL)",
        None,
        _row("Miami (FL)", 1, 2, 0, 0, 2, defense=True),
    )
    defense_bundle = _bundle(
        "FCS",
        "Florida A&M",
        _row("Florida A&M", 2, 7, 1, 1, 4),
        _row("Florida A&M", 2, 5, 2, 1, 0, defense=True),
    )

    side = rz._side(
        {"team": "Miami (FL)", "team_slug": "miami-fl"},
        {"team": "Florida A&M", "team_slug": "florida-a-m"},
        offense_bundle,
        defense_bundle,
        "FBS",
        "FCS",
    )

    assert side["model_ready"] is False
    assert side["coverage"] == 0.5
    assert side["points_adjustment"] == 0.0
    assert "offense row" in side["reason"]


def test_build_engine_handles_mixed_fcs_fbs(monkeypatch):
    fbs = _bundle(
        "FBS",
        "Miami (FL)",
        _row("Miami (FL)", 1, 3, 1, 2, 0),
        _row("Miami (FL)", 1, 2, 0, 0, 2, defense=True),
    )
    fcs = _bundle(
        "FCS",
        "Florida A&M",
        _row("Florida A&M", 2, 7, 1, 1, 4),
        _row("Florida A&M", 2, 5, 2, 1, 0, defense=True),
    )
    fbs_pace = _pace_bundle("Miami (FL)")
    fcs_pace = _pace_bundle("Florida A&M")

    monkeypatch.setattr(
        rz.step4,
        "_load_pace_division",
        lambda division: ((fcs_pace, {}) if division == "FCS" else (fbs_pace, {})),
    )
    monkeypatch.setattr(
        rz,
        "_load_red_zone_division",
        lambda division: ((fcs, {}) if division == "FCS" else (fbs, {})),
    )

    out = rz.build_red_zone_engine(
        {},
        {"team": "Florida A&M", "team_slug": "florida-a-m", "division_context": "FBS"},
        {"team": "Miami (FL)", "team_slug": "miami-fl", "division_context": "FBS"},
    )

    assert out["model_ready"] is True
    assert out["away_division"] == "FCS"
    assert out["home_division"] == "FBS"
    assert out["mixed_division"] is True
    assert out["rankless_tie_safe_parser_active"] is True
    assert out["cross_division_rank_comparison_used"] is False
    assert out["away_offense"]["coverage"] == 1.0
    assert out["home_offense"]["coverage"] == 1.0


def test_ratio_signal_is_bounded():
    assert rz._ratio_signal(2.0, 1.0, 0.1) == 1.0
    assert rz._ratio_signal(0.1, 1.0, 0.1) == -1.0
    assert rz._ratio_signal(None, 1.0, 0.1) is None


def test_apply_to_raw_preserves_sigma_and_reliability():
    base = {
        "version": "STEP5",
        "ready": True,
        "projected_away_points": 24.0,
        "projected_home_points": 28.0,
        "projected_total": 52.0,
        "structural_total_sigma": 9.5,
        "reliability": 0.72,
        "analysis_line": 50.5,
        "components": {"step5_total_explosive_adjustment": 0.1},
    }
    engine = {
        "model_ready": True,
        "coverage": 1.0,
        "away_offense": {"points_adjustment": 0.3},
        "home_offense": {"points_adjustment": -0.2},
    }

    out = rz.apply_to_raw(base, engine)

    assert out["upgrade_step6_applied"] is True
    assert round(out["projected_total"], 3) == 52.1
    assert out["structural_total_sigma"] == 9.5
    assert out["reliability"] == 0.72
    assert out["analysis_line_red_zone_weight"] == 0.0
    assert out["sportsbook_input_used"] is False
    assert out["monte_carlo_used"] is False


def test_apply_to_raw_fails_closed_when_engine_not_ready():
    base = {"version": "STEP5", "ready": True, "projected_total": 50.0}
    out = rz.apply_to_raw(
        base,
        {"model_ready": False, "coverage": 0.5, "reason": "missing direct row"},
    )
    assert out["upgrade_step6_applied"] is False
    assert out["projected_total"] == 50.0
    assert out["red_zone_engine_reason"] == "missing direct row"
