from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_hub_v19 as v19
import nfl_passing_yards_hub_v26 as v26
import nfl_passing_yards_pressure_v5 as pressure_v5


ROOT = Path(__file__).resolve().parents[1]


def _current_incomplete(offense_id="27", defense_id="4") -> dict:
    return {
        "ready": False,
        "reason": "verified season pass-protection or defensive sack evidence is incomplete",
        "offense_team_id": offense_id,
        "defense_team_id": defense_id,
        "offense": {"ready": False, "games": 0.0, "sacks_allowed": 0.0},
        "defense": {"ready": False, "games": 0.0, "sacks_made": 0.0},
        "pressure_label": "CHECK",
        "pressure_basis": "season sack-rate evidence incomplete",
        "recent_offense": [],
        "recent_defense": [],
        "projection_adjustment": 0.0,
        "sportsbook_influence": 0.0,
        "season_type": 2,
    }


def _prior_ready(offense_id="27", defense_id="4") -> dict:
    recent_offense = [
        {"event_id": f"o{i}", "sacks_taken": 2.0, "sack_rate": 6.0}
        for i in range(5)
    ]
    recent_defense = [
        {"event_id": f"d{i}", "sacks_made": 3.0, "sack_rate_generated": 7.0}
        for i in range(5)
    ]
    return {
        "ready": True,
        "reason": "",
        "offense_team_id": offense_id,
        "defense_team_id": defense_id,
        "offense": {
            "ready": True,
            "games": 17.0,
            "passing_attempts": 558.0,
            "sacks_allowed": 38.0,
            "sacks_allowed_per_game": 38.0 / 17.0,
            "sack_yards_lost": 255.0,
            "sack_rate_allowed": 100.0 * 38.0 / 596.0,
        },
        "defense": {
            "ready": True,
            "games": 17.0,
            "sacks_made": 34.0,
            "sacks_per_game": 2.0,
            "opponent_pass_attempts": 534.0,
            "sack_rate_generated": 100.0 * 34.0 / 568.0,
        },
        "pressure_label": "MODERATE",
        "pressure_basis": "mean sack-rate context 6.2%",
        "recent_offense": recent_offense,
        "recent_defense": recent_defense,
        "pressure_source_recovery": "verified ESPN opponent attempts from exact regular-season event box scores",
        "boxscore_value_fallback": "ESPN DISPLAY VALUE FOR PLACEHOLDER PRIMARY VALUES",
        "projection_adjustment": 0.0,
        "sportsbook_influence": 0.0,
        "season_type": 2,
    }


def test_live_defense_proxy_uses_only_certified_source_shape_overrides() -> None:
    wrapped = object()
    proxy = pressure_v5._LiveDefenseProxy(wrapped)
    assert proxy._completed_event_rows is pressure_v5.defense_v3._completed_event_rows_utc
    assert proxy._box_stat is pressure_v5.defense_v3._box_stat_v3


def test_recover_defensive_pressure_uses_verified_aggregate_attempts(monkeypatch) -> None:
    row = {
        "ready": False,
        "offense": {"ready": True, "sack_rate_allowed": 6.0},
        "defense": {"ready": False, "games": 17.0, "sacks_made": 34.0, "opponent_pass_attempts": float("nan")},
    }

    def fake_aggregate(team_id, year, season_type, cutoff_date, partial_season=None):
        assert team_id == "4"
        assert year == 2025
        assert season_type == 2
        assert partial_season == {"sacks": 34.0}
        return (
            {"ready": True, "games": 17.0, "passing_attempts_allowed": 534.0},
            [],
            {"ready": True, "expected_games": 17, "parsed_games": 17},
        )

    monkeypatch.setattr(pressure_v5.defense_v3, "_verified_boxscore_season", fake_aggregate)
    out = pressure_v5._recover_defensive_pressure(row, "4", 2025, 2, "2026-09-13")

    assert out["defense"]["ready"] is True
    assert out["defense"]["opponent_pass_attempts"] == 534.0
    assert out["defense"]["sacks_made"] == 34.0
    assert round(out["defense"]["sack_rate_generated"], 6) == round(100.0 * 34.0 / 568.0, 6)
    assert out["pressure_label"] != "CHECK"
    assert out["ready"] is True


def test_recovery_does_not_run_without_real_completed_season_sample(monkeypatch) -> None:
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("aggregate must not run")

    monkeypatch.setattr(pressure_v5.defense_v3, "_verified_boxscore_season", forbidden)
    row = {
        "ready": False,
        "offense": {"ready": False},
        "defense": {"ready": False, "games": 0.0, "sacks_made": 0.0},
    }
    out = pressure_v5._recover_defensive_pressure(row, "4", 2026, 2, "2026-09-13")
    assert called is False
    assert out["defense"]["ready"] is False


def test_v5_preserves_v4_exact_id_bounded_prior_gate(monkeypatch) -> None:
    current = _current_incomplete()
    prior = _prior_ready()
    calls = []

    def fake_build(*args):
        year = int(args[4])
        calls.append(year)
        return dict(current if year == 2026 else prior)

    monkeypatch.setattr(pressure_v5, "_build_live_base", fake_build)
    out = pressure_v5.build_pressure_matchup("27", "Bucs", "4", "Bengals", 2026, 2, "2026-09-13")

    assert calls == [2026, 2025]
    assert out["ready"] is True
    assert out["early_season_fallback"] is True
    assert out["baseline_source_year"] == 2025
    assert out["offense_team_id"] == "27"
    assert out["defense_team_id"] == "4"
    assert out["pressure_label"] == "MODERATE"
    assert len(out["recent_offense"]) == 5
    assert len(out["recent_defense"]) == 5
    assert out["sportsbook_influence"] == 0.0
    assert out["projection_adjustment"] == 0.0


def test_v5_rejects_wrong_prior_exact_team_identity(monkeypatch) -> None:
    current = _current_incomplete()
    wrong = _prior_ready(offense_id="999", defense_id="4")
    monkeypatch.setattr(
        pressure_v5,
        "_build_live_base",
        lambda *args: dict(current if int(args[4]) == 2026 else wrong),
    )
    out = pressure_v5.build_pressure_matchup("27", "Bucs", "4", "Bengals", 2026, 2, "2026-09-13")
    assert out["ready"] is False
    assert out["early_season_fallback"] is False
    assert out["baseline_source_year"] == 2026


def test_v26_patches_only_v19_pressure_builder_and_restores(monkeypatch) -> None:
    original = v19.pressure_v3
    observed = {}

    def fake_prior_render():
        observed["builder"] = v19.pressure_v3.build_pressure_matchup
        return "rendered"

    monkeypatch.setattr(v26.prior, "render_nfl_passing_yards_hub", fake_prior_render)
    assert v26.render_nfl_passing_yards_hub() == "rendered"
    assert observed["builder"] is pressure_v5.build_pressure_matchup
    assert v19.pressure_v3 is original


def test_router_advances_only_passing_yards_to_v26_and_preserves_v25_contract() -> None:
    source = (ROOT / "nfl_hub_v35.py").read_text(encoding="utf-8")
    assert "from nfl_passing_yards_hub_v25 import render_nfl_passing_yards_hub as render_v25" in source
    assert "return render_v25()" in source
    assert "from nfl_passing_yards_hub_v26 import render_nfl_passing_yards_hub as render_v26" in source
    assert "return render_v26()" in source
    assert 'if market == "Passing Yards"' in source
    assert "return base.render_nfl_hub(market)" in source
    assert "0.0% sportsbook projection influence" in source


def test_v5_is_source_recovery_only_and_never_adds_market_math() -> None:
    source = (ROOT / "nfl_passing_yards_pressure_v5.py").read_text(encoding="utf-8")
    assert "no fuzzy/name identity authority" in source.lower()
    assert 'current["projection_adjustment"] = 0.0' in source
    assert 'current["sportsbook_influence"] = 0.0' in source
    for forbidden in ("evaluate_market", "over_ev", "under_ev", "fair_odds", "monte_carlo"):
        assert forbidden not in source
