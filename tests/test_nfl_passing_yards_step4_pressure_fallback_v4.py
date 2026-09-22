from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_hub_v19 as v19
import nfl_passing_yards_hub_v25 as v25
import nfl_passing_yards_pressure_v4 as pressure_v4


ROOT = Path(__file__).resolve().parents[1]


def _recent(prefix: str, count: int, side: str) -> list[dict]:
    rows = []
    for index in range(count):
        if side == "offense":
            rows.append({
                "event_id": f"{prefix}o{index}",
                "sacks_taken": 2.0,
                "sack_rate": 5.0,
            })
        else:
            rows.append({
                "event_id": f"{prefix}d{index}",
                "sacks_made": 3.0,
                "sack_rate_generated": 7.0,
            })
    return rows


def _profile(
    *,
    ready: bool,
    count: int,
    offense_team_id: str = "27",
    defense_team_id: str = "4",
    season_type=None,
    basis: str = "verified current",
) -> dict:
    row = {
        "ready": ready,
        "reason": "" if ready else "verified season pass-protection or defensive sack evidence is incomplete",
        "offense_team_id": offense_team_id,
        "defense_team_id": defense_team_id,
        "offense": {"sack_rate_allowed": 5.0 if ready else None},
        "defense": {"sack_rate_generated": 7.0 if ready else None},
        "pressure_label": "MODERATE" if ready else "CHECK",
        "pressure_basis": basis,
        "blitz_state": "UNAVAILABLE — not synthesized",
        "recent_offense": _recent("x", count, "offense"),
        "recent_defense": _recent("x", count, "defense"),
        "projection_adjustment": 0.0,
    }
    if season_type is not None:
        row["season_type"] = season_type
    return row


def test_complete_current_profile_is_untouched_and_prior_is_not_called(monkeypatch) -> None:
    current = _profile(ready=True, count=5, basis="CURRENT SENTINEL")
    calls = []

    def fake_build(*args):
        calls.append((int(args[4]), int(args[5])))
        return dict(current)

    monkeypatch.setattr(pressure_v4, "_build_utc_base", fake_build)
    out = pressure_v4.build_pressure_matchup("27", "Bucs", "4", "Bengals", 2026, 2, "2026-10-20")

    assert calls == [(2026, 2)]
    assert out["ready"] is True
    assert out["pressure_basis"] == "CURRENT SENTINEL"
    assert out["baseline_source_year"] == 2026
    assert out["early_season_fallback"] is False
    assert out["projection_adjustment"] == 0.0
    assert out["sportsbook_influence"] == 0.0


def test_incomplete_current_inside_existing_window_can_use_exact_prior_regular(monkeypatch) -> None:
    current = _profile(ready=False, count=1)
    prior = _profile(ready=True, count=5, season_type=2, basis="PRIOR REGULAR SENTINEL")
    calls = []

    def fake_build(*args):
        year, season_type = int(args[4]), int(args[5])
        calls.append((year, season_type))
        return dict(current if year == 2026 else prior)

    monkeypatch.setattr(pressure_v4, "_build_utc_base", fake_build)
    out = pressure_v4.build_pressure_matchup("27", "Bucs", "4", "Bengals", 2026, 2, "2026-09-13")

    assert calls == [(2026, 2), (2025, 2)]
    assert out["ready"] is True
    assert out["early_season_fallback"] is True
    assert out["baseline_source_year"] == 2025
    assert "PRIOR REGULAR SENTINEL" in out["pressure_basis"]
    assert out["offense_team_id"] == "27"
    assert out["defense_team_id"] == "4"


def test_outside_existing_five_game_window_never_uses_prior_rescue(monkeypatch) -> None:
    current = _profile(ready=False, count=5)
    calls = []

    def fake_build(*args):
        calls.append((int(args[4]), int(args[5])))
        if int(args[4]) == 2026:
            return dict(current)
        raise AssertionError("prior season must not be requested outside existing recent-five window")

    monkeypatch.setattr(pressure_v4, "_build_utc_base", fake_build)
    out = pressure_v4.build_pressure_matchup("27", "Bucs", "4", "Bengals", 2026, 2, "2026-11-01")

    assert calls == [(2026, 2)]
    assert out["ready"] is False
    assert out["early_season_fallback"] is False
    assert out["baseline_source_year"] == 2026


def test_wrong_prior_espn_team_id_is_rejected(monkeypatch) -> None:
    current = _profile(ready=False, count=0)
    wrong_prior = _profile(
        ready=True,
        count=5,
        offense_team_id="999",
        defense_team_id="4",
        season_type=2,
        basis="WRONG ID MUST NOT ENTER",
    )

    monkeypatch.setattr(
        pressure_v4,
        "_build_utc_base",
        lambda *args: dict(current if int(args[4]) == 2026 else wrong_prior),
    )
    out = pressure_v4.build_pressure_matchup("27", "Bucs", "4", "Bengals", 2026, 2, "2026-09-13")

    assert out["ready"] is False
    assert out["early_season_fallback"] is False
    assert out["baseline_source_year"] == 2026
    assert "WRONG ID MUST NOT ENTER" not in str(out)


def test_both_current_and_exact_prior_incomplete_stays_fail_closed(monkeypatch) -> None:
    current = _profile(ready=False, count=0)
    prior = _profile(ready=False, count=3, season_type=2)

    monkeypatch.setattr(
        pressure_v4,
        "_build_utc_base",
        lambda *args: dict(current if int(args[4]) == 2026 else prior),
    )
    out = pressure_v4.build_pressure_matchup("27", "Bucs", "4", "Bengals", 2026, 2, "2026-09-13")

    assert out["ready"] is False
    assert out["early_season_fallback"] is False
    assert out["baseline_source_year"] == 2026
    assert out["sportsbook_influence"] == 0.0


def test_explicit_prior_preseason_or_postseason_metadata_is_rejected(monkeypatch) -> None:
    current = _profile(ready=False, count=0)

    for invalid_type in (1, 3, "preseason", "postseason"):
        prior = _profile(ready=True, count=5, season_type=invalid_type, basis="NONREGULAR MUST NOT ENTER")
        monkeypatch.setattr(
            pressure_v4,
            "_build_utc_base",
            lambda *args, current=current, prior=prior: dict(
                current if int(args[4]) == 2026 else prior
            ),
        )
        out = pressure_v4.build_pressure_matchup(
            "27", "Bucs", "4", "Bengals", 2026, 2, "2026-09-13"
        )
        assert out["ready"] is False
        assert out["early_season_fallback"] is False
        assert "NONREGULAR MUST NOT ENTER" not in str(out)


def test_non_regular_current_request_never_loads_prior(monkeypatch) -> None:
    current = _profile(ready=False, count=0)
    calls = []

    def fake_build(*args):
        calls.append((int(args[4]), int(args[5])))
        return dict(current)

    monkeypatch.setattr(pressure_v4, "_build_utc_base", fake_build)
    out = pressure_v4.build_pressure_matchup("27", "Bucs", "4", "Bengals", 2026, 1, "2026-08-15")

    assert calls == [(2026, 1)]
    assert out["ready"] is False
    assert out["early_season_fallback"] is False


def test_v25_patches_only_v19_pressure_builder_and_restores_it(monkeypatch) -> None:
    original = v19.pressure_v3
    observed = {}

    def fake_prior_render():
        observed["builder"] = v19.pressure_v3.build_pressure_matchup
        return "rendered"

    monkeypatch.setattr(v25.prior, "render_nfl_passing_yards_hub", fake_prior_render)
    result = v25.render_nfl_passing_yards_hub()

    assert result == "rendered"
    assert observed["builder"] is pressure_v4.build_pressure_matchup
    assert v19.pressure_v3 is original


def test_router_advances_only_passing_yards_to_v25_and_keeps_v24_contract() -> None:
    source = (ROOT / "nfl_hub_v35.py").read_text(encoding="utf-8")
    assert "from nfl_passing_yards_hub_v24 import render_nfl_passing_yards_hub as render_v24" in source
    assert "return render_v24()" in source
    assert "from nfl_passing_yards_hub_v25 import render_nfl_passing_yards_hub as render_v25" in source
    assert "return render_v25()" in source
    assert 'if market == "Passing Yards"' in source
    assert "return base.render_nfl_hub(market)" in source
