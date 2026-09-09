"""Regression checks for CFB O/U Upgrade Step 8 turnover volatility engine."""
from __future__ import annotations

import cfb_over_under_turnover_engine_v1 as to


def _row(team: str, games: int, gained: int, lost: int, *, rank="-"):
    fum_rec = max(0, gained // 2)
    opp_int = gained - fum_rec
    fum_lost = max(0, lost // 2)
    interceptions = lost - fum_lost
    margin = gained - lost
    return {
        "team": team,
        "headers": ["Rank","Team","G","Fum Rec","Opp Int","Turn Gain","Fum Lost","Int","Turn Lost","Margin","Avg"],
        "row": [rank,team,str(games),str(fum_rec),str(opp_int),str(gained),str(fum_lost),str(interceptions),str(lost),str(margin),f"{margin/games:.2f}"],
    }


def _key(name: str) -> str:
    return to.frozen_team._canonical_name(name)


def _bundle(division: str, team: str, row):
    return {
        "division": division,
        "table": {_key(team): row} if row else {},
        "baselines": {
            "giveaways_per_game": 1.0,
            "takeaways_per_game": 1.0,
        },
    }


def _pace_bundle(team: str):
    return {"total_offense": {_key(team): {"team": team}}}


def test_rankless_parser_keeps_blank_rank_rows():
    html = """
    <table>
      <tr><th>Rank</th><th>Team</th><th>G</th><th>Fum Rec</th><th>Opp Int</th><th>Turn Gain</th><th>Fum Lost</th><th>Int</th><th>Turn Lost</th><th>Margin</th><th>Avg</th></tr>
      <tr><td>-</td><td>Miami (FL)</td><td>1</td><td>0</td><td>0</td><td>0</td><td>0</td><td>1</td><td>1</td><td>-1</td><td>-1.00</td></tr>
    </table>
    """
    rows = to._turnover_rows(html)
    assert _key("Miami (FL)") in rows
    assert rows[_key("Miami (FL)")]["row"][0] == "-"


def test_metrics_parse_direct_turnover_counts():
    metrics = to._metrics(_row("Florida A&M", 2, 4, 1))
    assert metrics["ready"] is True
    assert metrics["games"] == 2
    assert metrics["turnovers_gained"] == 4.0
    assert metrics["turnovers_lost"] == 1.0
    assert metrics["takeaways_per_game"] == 2.0
    assert metrics["giveaways_per_game"] == 0.5
    assert metrics["margin_per_game"] == 1.5


def test_zero_turnovers_are_valid_evidence():
    metrics = to._metrics(_row("Miami (FL)", 1, 0, 0))
    assert metrics["ready"] is True
    assert metrics["takeaways_per_game"] == 0.0
    assert metrics["giveaways_per_game"] == 0.0


def test_discover_turnover_margin_team_category():
    html = """
    <select>
      <option value="/stats/football/fbs/current/individual/29">Turnover Margin</option>
      <option value="/stats/football/fbs/current/team/29">Turnover Margin</option>
    </select>
    """
    found = to._discover_category(html)
    assert found.endswith("/team/29")


def test_sample_factor_uses_minimum_verified_games():
    assert to._sample_factor({"games": 2}, {"games": 1}) == 1/6
    assert to._sample_factor({"games": 8}, {"games": 7}) == 1.0


def test_side_blends_giveaways_and_opponent_takeaways():
    off_team = "Miami (FL)"
    def_team = "Florida A&M"
    offense_bundle = _bundle("FBS", off_team, _row(off_team, 2, 1, 4))
    defense_bundle = _bundle("FCS", def_team, _row(def_team, 2, 4, 1))
    side = to._side(
        {"team": off_team, "team_slug": "miami-fl"},
        {"team": def_team, "team_slug": "florida-a-m"},
        offense_bundle,
        defense_bundle,
        "FBS",
        "FCS",
    )
    assert side["model_ready"] is True
    assert side["coverage"] == 1.0
    assert side["expected_giveaways_per_game"] == 2.0
    assert side["baseline_expected_giveaways_per_game"] == 1.0
    assert side["sample_factor"] == 2/6
    assert side["signal"] == 1.0
    assert round(side["shrunk_signal"], 6) == round(1/3, 6)


def test_side_fails_closed_when_opponent_row_missing():
    offense_bundle = _bundle("FBS", "Miami (FL)", _row("Miami (FL)", 1, 0, 1))
    defense_bundle = _bundle("FCS", "Florida A&M", None)
    side = to._side(
        {"team": "Miami (FL)", "team_slug": "miami-fl"},
        {"team": "Florida A&M", "team_slug": "florida-a-m"},
        offense_bundle,
        defense_bundle,
        "FBS",
        "FCS",
    )
    assert side["model_ready"] is False
    assert side["coverage"] == 0.5
    assert "opponent defense" in side["reason"]


def test_build_engine_mixed_division_and_sigma_cap(monkeypatch):
    fbs = _bundle("FBS","Miami (FL)",_row("Miami (FL)",1,0,1))
    fcs = _bundle("FCS","Florida A&M",_row("Florida A&M",2,4,1))
    fbs_pace = _pace_bundle("Miami (FL)")
    fcs_pace = _pace_bundle("Florida A&M")

    monkeypatch.setattr(
        to.step4,
        "_load_pace_division",
        lambda division: ((fcs_pace,{}) if division == "FCS" else (fbs_pace,{})),
    )
    monkeypatch.setattr(
        to,
        "_load_turnover_division",
        lambda division: ((fcs,{}) if division == "FCS" else (fbs,{})),
    )

    out = to.build_turnover_engine(
        {},
        {"team":"Florida A&M","team_slug":"florida-a-m","division_context":"FBS"},
        {"team":"Miami (FL)","team_slug":"miami-fl","division_context":"FBS"},
    )
    assert out["model_ready"] is True, out
    assert out["away_division"] == "FCS"
    assert out["home_division"] == "FBS"
    assert out["mixed_division"] is True
    assert out["cross_division_rank_comparison_used"] is False
    assert out["field_position_data_available"] is False
    assert out["field_position_points_adjustment_used"] is False
    assert abs(out["sigma_adjustment"]) <= to.MAX_TOTAL_SIGMA_ADJUSTMENT


def test_apply_to_raw_changes_sigma_not_projection():
    base = {
        "version":"STEP7",
        "ready":True,
        "projected_away_points":24.0,
        "projected_home_points":28.0,
        "projected_total":52.0,
        "structural_total_sigma":13.5,
        "reliability":0.72,
        "analysis_line":50.5,
        "components":{},
    }
    engine = {
        "model_ready":True,
        "coverage":1.0,
        "total_volatility_signal":0.5,
        "sigma_adjustment":0.625,
    }
    out = to.apply_to_raw(base, engine)
    assert out["upgrade_step8_applied"] is True
    assert out["projected_away_points"] == 24.0
    assert out["projected_home_points"] == 28.0
    assert out["projected_total"] == 52.0
    assert out["structural_total_sigma"] == 14.125
    assert out["reliability"] == 0.72
    assert out["components"]["step8_projected_total_adjustment"] == 0.0
    assert out["analysis_line_turnover_weight"] == 0.0
    assert out["projected_total_turnover_weight"] == 0.0
    assert out["field_position_points_adjustment_used"] is False


def test_apply_to_raw_fails_closed_when_engine_not_ready():
    base={"version":"STEP7","ready":True,"projected_total":50.0}
    out=to.apply_to_raw(base,{"model_ready":False,"coverage":0.5,"reason":"missing turnover row"})
    assert out["upgrade_step8_applied"] is False
    assert out["projected_total"] == 50.0
    assert out["turnover_engine_reason"] == "missing turnover row"
