from __future__ import annotations

import importlib.util
from pathlib import Path

import nfl_passing_yards_projection_v1 as frozen_projection

ROOT = Path(__file__).resolve().parents[1]


def _path(path: str) -> Path:
    target = ROOT / path
    assert target.exists(), f"required successor artifact missing: {path}"
    return target


def _read(path: str) -> str:
    return _path(path).read_text(encoding="utf-8")


def _load(path: str, name: str):
    target = _path(path)
    spec = importlib.util.spec_from_file_location(name, target)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_passing_yards_route_uses_professional_gateway_only() -> None:
    loader = _read("universal_runtime_v5_loader.py")
    assert "def _nfl_passing_yards_adapter" in loader
    block = loader.split("def _nfl_passing_yards_adapter", 1)[1].split("def _nfl_adapter", 1)[0].lower()
    assert '_import("nfl_passing_yards_professional_v1")' in block
    assert "nfl_hub_v1" not in block
    assert "nfl_active_slate_runtime_v1" not in block
    assert "espn" not in block
    resolve = loader.split("def resolve_destination", 1)[1]
    assert 'route.market_id == "passing-yards"' in resolve
    assert "_nfl_passing_yards_adapter(route)" in resolve


def test_application_page_is_kyre_gateway_only_and_has_no_banned_provider() -> None:
    page = _read("nfl_passing_yards_professional_v1.py").lower()
    gateway = _read("nfl_passing_yards_gateway_v1.py").lower()
    for banned in ("espn", "sgo", "sgodata"):
        assert banned not in page
        assert banned not in gateway
    assert "nfl_passing_yards_gateway_v1" in page
    assert "/api/v1/nfl/passing-yards/page" in gateway
    assert "requests.get" in gateway
    assert "nflverse" not in gateway
    assert "fanduel" not in gateway


def test_api_registration_replaces_legacy_passing_yards_market_route() -> None:
    source = _read("sports_api/api/health.py")
    assert "nfl_passing_yards_page_v1" in source
    assert "nfl_passing_yards_page_router.routes" in source
    assert "nfl_passing_yards_market_v1" not in source
    assert "nfl_passing_yards_market_router.routes" not in source


def test_server_bundle_uses_approved_sources_and_never_guesses_missing_data() -> None:
    source = _read("sports_api/api/nfl_passing_yards_page_v1.py").lower()
    for banned in ("espn", "sgo", "sgodata"):
        assert banned not in source
    assert "nflverse" in source
    assert "fanduel" in source
    assert "canonical" in source
    assert "source_timestamp" in source
    assert "return none" in source
    assert '"sportsbook_line_averaging":false' in source.replace(" ", "")
    assert '"missing_to_zero":false' in source.replace(" ", "")


def test_rank_grade_contract() -> None:
    page_api = _load("sports_api/api/nfl_passing_yards_page_v1.py", "py_page_api_rank")
    grade = page_api.pass_defense_grade
    assert grade(1) == "TOUGH"
    assert grade(8) == "TOUGH"
    assert grade(9) == "MEDIUM"
    assert grade(20) == "MEDIUM"
    assert grade(21) == "FAVORABLE"
    assert grade(32) == "FAVORABLE"
    assert grade(None) == "CHECK"


def test_qb_vs_opponent_history_is_explicitly_fail_closed() -> None:
    page_api = _load("sports_api/api/nfl_passing_yards_page_v1.py", "py_page_api_history")
    summarize = page_api.summarize_qb_vs_opponent
    empty = summarize([], qb_name="Test QB", opponent="CHI")
    assert empty["games"] == 0
    assert empty["available"] is False
    assert empty["avg_passing_yards"] is None
    assert "No verified prior matchup history" in empty["message"]
    rows = [
        {"qb_name": "Test QB", "opponent": "CHI", "passing_yards": 240, "attempts": 31, "completions": 20, "pass_tds": 2, "interceptions": 1},
        {"qb_name": "Test QB", "opponent": "CHI", "passing_yards": 280, "attempts": 35, "completions": 24, "pass_tds": 1, "interceptions": 0},
    ]
    out = summarize(rows, qb_name="Test QB", opponent="CHI")
    assert out["available"] is True
    assert out["games"] == 2
    assert out["avg_passing_yards"] == 260.0
    assert round(out["completion_pct"], 6) == round(44 / 66 * 100, 6)


def test_projection_v2_preserves_frozen_numeric_formula() -> None:
    v2 = _load("nfl_passing_yards_projection_v2.py", "py_projection_v2")
    attempt_values = {
        "qb_season_attempts_per_game": 35.0,
        "qb_recent3_attempts": 33.0,
        "opponent_attempts_allowed_per_game": 38.0,
        "team_pass_attempts_per_game": 36.0,
    }
    ypa_values = {
        "qb_season_ypa": 7.8,
        "qb_recent3_ypa": 7.4,
        "opponent_season_ypa_allowed": 7.1,
        "opponent_recent3_ypa_allowed": 7.3,
    }
    old_a = frozen_projection.weighted_blend(attempt_values, frozen_projection.ATTEMPT_WEIGHTS)
    old_y = frozen_projection.weighted_blend(ypa_values, frozen_projection.YPA_WEIGHTS)
    new = v2.project_from_canonical_inputs(attempt_values, ypa_values)
    assert new["expected_attempts"] == old_a["value"]
    assert new["expected_ypa"] == old_y["value"]
    assert new["projection_yards"] == old_a["value"] * old_y["value"]
    assert new["sportsbook_influence"] == 0.0


def test_professional_page_is_decision_first_and_hides_internal_step_chrome() -> None:
    page = _read("nfl_passing_yards_professional_v1.py")
    for token in (
        "KYRE AI PASSING YARDS",
        "QB VS TEAM HISTORY",
        "PASS DEFENSE RANK",
        "WHY THIS PROJECTION",
        "PROBABILITY LADDER",
        "MODEL DETAILS & METHODOLOGY",
    ):
        assert token in page
    assert "Step 7 methodology" not in page
    assert "Step 8 methodology" not in page
    assert "Step 9 methodology" not in page
    assert "Step 10 methodology" not in page
    assert "st.date_input" not in page
