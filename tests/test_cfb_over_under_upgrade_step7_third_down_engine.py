"""Regression checks for CFB O/U Upgrade Step 7 third-down engine."""
from __future__ import annotations

import cfb_over_under_third_down_engine_v1 as td


def _row(team: str, games: int, attempts: int, conversions: int, *, defense=False, rank="-"):
    if defense:
        headers = ["Rank", "Team", "G", "Opp 3rd Conv", "Opp 3rd Att", "Pct"]
        row = [rank, team, str(games), str(conversions), str(attempts), f"{conversions/attempts:.3f}"]
    else:
        headers = ["Rank", "Team", "G", "3rd Att", "3rd Conv", "Pct"]
        row = [rank, team, str(games), str(attempts), str(conversions), f"{conversions/attempts:.3f}"]
    return {"team": team, "headers": headers, "row": row}


def _key(name: str) -> str:
    return td.frozen_team._canonical_name(name)


def _bundle(division: str, team: str, off_row, def_row):
    return {
        "division": division,
        "tables": {
            "third_down_offense": {_key(team): off_row} if off_row else {},
            "third_down_defense": {_key(team): def_row} if def_row else {},
        },
        "baselines": {
            "offense_conversion_rate": 0.40,
            "defense_conversion_rate_allowed": 0.40,
            "offense_attempts_per_game": 13.0,
            "defense_attempts_per_game": 13.0,
        },
    }


def _pace_bundle(team: str):
    return {"total_offense": {_key(team): {"team": team}}}


def test_rankless_parser_keeps_blank_rank_ties():
    html = """
    <table>
      <tr><th>Rank</th><th>Team</th><th>G</th><th>3rd Att</th><th>3rd Conv</th><th>Pct</th></tr>
      <tr><td>5</td><td>Air Force</td><td>1</td><td>10</td><td>7</td><td>.700</td></tr>
      <tr><td>-</td><td>Miami (FL)</td><td>1</td><td>11</td><td>8</td><td>.727</td></tr>
    </table>
    """
    rows = td._third_down_rows(html)
    assert _key("Air Force") in rows
    assert _key("Miami (FL)") in rows
    assert rows[_key("Miami (FL)")]["row"][0] == "-"


def test_metrics_parse_offense_from_counts():
    metrics = td._metrics(_row("Miami (FL)", 1, 11, 8), False)
    assert metrics["ready"] is True
    assert metrics["attempts"] == 11.0
    assert metrics["conversions"] == 8.0
    assert round(metrics["conversion_rate"], 6) == round(8/11, 6)
    assert metrics["attempts_per_game"] == 11.0
    assert metrics["conversions_per_game"] == 8.0


def test_metrics_parse_defense_from_counts():
    metrics = td._metrics(_row("Florida A&M", 2, 19, 3, defense=True), True)
    assert metrics["ready"] is True
    assert metrics["attempts"] == 19.0
    assert metrics["conversions"] == 3.0
    assert round(metrics["conversion_rate"], 6) == round(3/19, 6)
    assert metrics["attempts_per_game"] == 9.5
    assert metrics["conversions_per_game"] == 1.5


def test_discover_third_down_categories_uses_team_paths_only():
    html = """
    <select>
      <option value="/stats/football/fbs/current/individual/699">3rd Down Conversion Pct</option>
      <option value="/stats/football/fbs/current/team/699">3rd Down Conversion Pct</option>
      <option value="/stats/football/fbs/current/team/701">3rd Down Conversion Pct Defense</option>
    </select>
    """
    found = td._discover_categories(html)
    assert set(found) == {"third_down_offense", "third_down_defense"}
    assert found["third_down_offense"].endswith("/team/699")
    assert found["third_down_defense"].endswith("/team/701")


def test_sample_factor_uses_verified_attempts():
    assert td._sample_factor({"attempts": 11}, {"attempts": 15}) == 11/30
    assert td._sample_factor({"attempts": 40}, {"attempts": 35}) == 1.0


def test_side_blends_direct_offense_and_defense_rates():
    off_team = "Miami (FL)"
    def_team = "Florida A&M"
    offense_bundle = _bundle(
        "FBS",
        off_team,
        _row(off_team, 1, 11, 8),
        _row(off_team, 1, 15, 5, defense=True),
    )
    defense_bundle = _bundle(
        "FCS",
        def_team,
        _row(def_team, 2, 30, 7),
        _row(def_team, 2, 19, 3, defense=True),
    )

    side = td._side(
        {"team": off_team, "team_slug": "miami-fl"},
        {"team": def_team, "team_slug": "florida-a-m"},
        offense_bundle,
        defense_bundle,
        "FBS",
        "FCS",
    )

    assert side["model_ready"] is True
    assert side["coverage"] == 1.0
    assert side["sample_factor"] == 11/30
    assert round(side["matchup_conversion_rate"], 6) == round(((8/11)+(3/19))/2, 6)
    assert abs(side["points_adjustment"]) <= td.MAX_TEAM_THIRD_DOWN_ADJUSTMENT


def test_side_fails_closed_when_direct_defense_row_missing():
    offense_bundle = _bundle(
        "FBS",
        "Miami (FL)",
        _row("Miami (FL)", 1, 11, 8),
        _row("Miami (FL)", 1, 15, 5, defense=True),
    )
    defense_bundle = _bundle(
        "FCS",
        "Florida A&M",
        _row("Florida A&M", 2, 30, 7),
        None,
    )
    side = td._side(
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
    assert "defense row" in side["reason"]


def test_build_engine_handles_mixed_fcs_fbs(monkeypatch):
    fbs = _bundle(
        "FBS",
        "Miami (FL)",
        _row("Miami (FL)", 1, 11, 8),
        _row("Miami (FL)", 1, 15, 5, defense=True),
    )
    fcs = _bundle(
        "FCS",
        "Florida A&M",
        _row("Florida A&M", 2, 30, 7),
        _row("Florida A&M", 2, 19, 3, defense=True),
    )
    fbs_pace = _pace_bundle("Miami (FL)")
    fcs_pace = _pace_bundle("Florida A&M")

    monkeypatch.setattr(
        td.step4,
        "_load_pace_division",
        lambda division: ((fcs_pace, {}) if division == "FCS" else (fbs_pace, {})),
    )
    monkeypatch.setattr(
        td,
        "_load_third_down_division",
        lambda division: ((fcs, {}) if division == "FCS" else (fbs, {})),
    )

    out = td.build_third_down_engine(
        {},
        {"team": "Florida A&M", "team_slug": "florida-a-m", "division_context": "FBS"},
        {"team": "Miami (FL)", "team_slug": "miami-fl", "division_context": "FBS"},
    )

    assert out["model_ready"] is True, out
    assert out["away_division"] == "FCS"
    assert out["home_division"] == "FBS"
    assert out["mixed_division"] is True
    assert out["rankless_tie_safe_parser_active"] is True
    assert out["cross_division_rank_comparison_used"] is False
    assert out["away_offense"]["coverage"] == 1.0
    assert out["home_offense"]["coverage"] == 1.0


def test_ratio_signal_is_bounded():
    assert td._ratio_signal(0.80, 0.40, 0.20) == 1.0
    assert td._ratio_signal(0.10, 0.40, 0.20) == -1.0
    assert td._ratio_signal(None, 0.40, 0.20) is None


def test_apply_to_raw_preserves_sigma_and_reliability():
    base = {
        "version": "STEP6",
        "ready": True,
        "projected_away_points": 24.0,
        "projected_home_points": 28.0,
        "projected_total": 52.0,
        "structural_total_sigma": 9.5,
        "reliability": 0.72,
        "analysis_line": 50.5,
        "components": {"step6_total_red_zone_adjustment": -0.2},
    }
    engine = {
        "model_ready": True,
        "coverage": 1.0,
        "away_offense": {"points_adjustment": -0.3},
        "home_offense": {"points_adjustment": 0.2},
    }

    out = td.apply_to_raw(base, engine)

    assert out["upgrade_step7_applied"] is True
    assert round(out["projected_total"], 3) == 51.9
    assert out["structural_total_sigma"] == 9.5
    assert out["reliability"] == 0.72
    assert out["analysis_line_third_down_weight"] == 0.0
    assert out["sportsbook_input_used"] is False
    assert out["monte_carlo_used"] is False


def test_apply_to_raw_fails_closed_when_engine_not_ready():
    base = {"version": "STEP6", "ready": True, "projected_total": 50.0}
    out = td.apply_to_raw(
        base,
        {"model_ready": False, "coverage": 0.5, "reason": "missing direct row"},
    )
    assert out["upgrade_step7_applied"] is False
    assert out["projected_total"] == 50.0
    assert out["third_down_engine_reason"] == "missing direct row"
