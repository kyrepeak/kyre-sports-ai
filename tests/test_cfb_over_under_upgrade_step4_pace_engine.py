"""Regression checks for CFB O/U Upgrade Step 4 pace engine."""
from __future__ import annotations

import cfb_over_under_pace_engine_v1 as pace


def _row(team: str, games: int, plays: int):
    return {
        "team": team,
        "headers": ["Rank", "Team", "G", "Plays", "YDS", "Yds/Play", "Off TDs", "YPG"],
        "row": ["1", team, str(games), str(plays), "1000", "6.5", "10", "500.0"],
    }


def _top_row(team: str, games: int, avg_top: str):
    return {
        "team": team,
        "headers": ["Rank", "Team", "G", "TOP", "AvgTOP"],
        "row": ["1", team, str(games), "60:00", avg_top],
    }


def _bundle(division: str, rows: dict, tops: dict, baseline_plays: float = 70.0, baseline_spp: float = 25.7):
    return {
        "division": division,
        "total_offense": rows,
        "time_of_possession": tops,
        "baseline_plays_per_game": baseline_plays,
        "baseline_seconds_per_play": baseline_spp,
        "field_size": len(rows),
    }


def test_clock_seconds_parses_ncaa_time_formats():
    assert pace._clock_seconds("30:15") == 1815.0
    assert pace._clock_seconds("30") == 1800.0
    assert pace._clock_seconds("") is None
    assert pace._clock_seconds("30:99") is None


def test_games_and_plays_uses_total_offense_columns():
    games, plays = pace._games_and_plays(_row("Miami (FL)", 2, 146))
    assert games == 2
    assert plays == 146.0


def test_avg_top_seconds_uses_avg_top_column():
    item = _top_row("Miami (FL)", 2, "31:20")
    assert pace._avg_top_seconds(item, 2) == 1880.0


def test_discover_time_of_possession_category():
    html = """
    <select>
      <option value="/stats/football/fbs/current/team/705">Time of Possession</option>
      <option value="/stats/football/fbs/current/team/21">Total Offense</option>
    </select>
    """
    url = pace._discover_time_of_possession(html)
    assert "team/705" in url


def test_build_pace_engine_resolves_mixed_fbs_fcs_by_actual_table(monkeypatch):
    fbs = _bundle(
        "FBS",
        {pace.frozen_team._canonical_name("Miami (FL)"): _row("Miami (FL)", 2, 150)},
        {pace.frozen_team._canonical_name("Miami (FL)"): _top_row("Miami (FL)", 2, "29:30")},
        baseline_plays=70.0,
        baseline_spp=25.7,
    )
    fcs = _bundle(
        "FCS",
        {pace.frozen_team._canonical_name("Florida A&M"): _row("Florida A&M", 2, 142)},
        {pace.frozen_team._canonical_name("Florida A&M"): _top_row("Florida A&M", 2, "30:30")},
        baseline_plays=68.0,
        baseline_spp=26.5,
    )

    monkeypatch.setattr(
        pace,
        "_load_pace_division",
        lambda division: ((fcs, {}) if division == "FCS" else (fbs, {})),
    )

    away = {
        "team": "Florida A&M",
        "team_slug": "florida-a-m",
        # Recreate the legacy profile mislabel. Table identity must win.
        "division_context": "FBS",
    }
    home = {
        "team": "Miami (FL)",
        "team_slug": "miami-fl",
        "division_context": "FBS",
    }

    out = pace.build_pace_engine({}, away, home)

    assert out["model_ready"] is True
    assert out["away_division"] == "FCS"
    assert out["home_division"] == "FBS"
    assert out["mixed_division"] is True
    assert out["away"]["plays_per_game"] == 71.0
    assert out["home"]["plays_per_game"] == 75.0
    assert out["expected_combined_plays"] > 0
    assert abs(out["total_points_adjustment"]) <= pace.MAX_TOTAL_PACE_ADJUSTMENT
    assert out["direct_possessions_available"] is False
    assert out["expected_combined_possessions"] is None


def test_small_sample_shrinks_expected_plays_toward_baseline(monkeypatch):
    fbs = _bundle(
        "FBS",
        {
            "fasta": _row("Fast A", 1, 90),
            "fastb": _row("Fast B", 1, 90),
        },
        {
            "fasta": _top_row("Fast A", 1, "30:00"),
            "fastb": _top_row("Fast B", 1, "30:00"),
        },
        baseline_plays=70.0,
        baseline_spp=25.7,
    )
    fcs = _bundle("FCS", {}, {}, baseline_plays=68.0, baseline_spp=26.0)

    monkeypatch.setattr(
        pace,
        "_load_pace_division",
        lambda division: ((fcs, {}) if division == "FCS" else (fbs, {})),
    )

    out = pace.build_pace_engine(
        {},
        {"team": "Fast A", "team_slug": "fast-a"},
        {"team": "Fast B", "team_slug": "fast-b"},
    )

    baseline = out["division_baseline_combined_plays"]
    historical = out["historical_combined_plays_per_game"]
    expected = out["expected_combined_plays"]

    assert out["sample_factor"] == 0.2
    assert abs(expected - baseline) < abs(historical - baseline)


def test_apply_to_raw_preserves_frozen_sigma_and_reliability():
    base = {
        "version": "STEP3",
        "ready": True,
        "projected_away_points": 24.0,
        "projected_home_points": 28.0,
        "projected_total": 52.0,
        "structural_total_sigma": 9.5,
        "reliability": 0.72,
        "analysis_line": 50.5,
        "components": {"step3_total_matchup_adjustment": 1.0},
    }
    engine = {
        "model_ready": True,
        "coverage": 1.0,
        "expected_combined_plays": 150.0,
        "expected_combined_possessions": None,
        "division_baseline_combined_plays": 138.0,
        "pace_ratio": 150.0 / 138.0,
        "sample_factor": 0.8,
        "total_points_adjustment": 2.0,
    }

    out = pace.apply_to_raw(base, engine)

    assert out["upgrade_step4_applied"] is True
    assert out["projected_total"] > base["projected_total"]
    assert out["structural_total_sigma"] == 9.5
    assert out["reliability"] == 0.72
    assert out["analysis_line_pace_weight"] == 0.0
    assert out["components"]["step4_total_pace_adjustment"] > 0
    assert out["sportsbook_input_used"] is False
    assert out["monte_carlo_used"] is False


def test_apply_to_raw_fails_closed_when_pace_not_ready():
    base = {
        "version": "STEP3",
        "ready": True,
        "projected_total": 50.0,
    }
    engine = {
        "model_ready": False,
        "coverage": 0.0,
        "reason": "missing pace rows",
    }
    out = pace.apply_to_raw(base, engine)
    assert out["upgrade_step4_applied"] is False
    assert out["projected_total"] == 50.0
    assert out["pace_engine_reason"] == "missing pace rows"


def test_identity_safe_lookup_does_not_match_florida_am_to_florida():
    table = {
        pace.frozen_team._canonical_name("Florida"): _row("Florida", 1, 67),
        pace.frozen_team._canonical_name("Florida State"): _row("Florida State", 1, 70),
    }
    profile = {"team": "Florida A&M", "team_slug": "florida-am"}
    assert pace._lookup(table, profile) == {}


def test_identity_safe_lookup_still_allows_close_unique_alias():
    table = {
        "miamifl": _row("Miami (FL)", 2, 150),
    }
    profile = {"team": "Miami (FL)", "team_slug": "miami-fl"}
    assert pace._lookup(table, profile)["team"] == "Miami (FL)"
