from pathlib import Path
import importlib.util
import math

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / f"{name}.py"
    assert path.exists(), f"missing production module: {path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_opening_day_uses_prior_season_baseline_without_inventing_current_sample():
    model = _load("nba_pra_page1_model_v1")
    prior = [
        {"points": 24, "rebounds": 8, "assists": 7, "minutes": 36},
        {"points": 21, "rebounds": 10, "assists": 8, "minutes": 35},
        {"points": 28, "rebounds": 6, "assists": 9, "minutes": 37},
    ]
    result = model.project_pra([], prior)
    assert result["current"]["sample"] == 0
    assert result["prior"]["sample"] == 3
    assert result["projection"] is not None
    assert result["basis"] == "PRIOR-SEASON BASELINE"


def test_projection_is_independent_of_sportsbook_line_and_grade_is_not():
    model = _load("nba_pra_page1_model_v1")
    prior = [{"points": 20, "rebounds": 10, "assists": 10, "minutes": 36}] * 5
    projection = model.project_pra([], prior)
    low = model.grade_market(projection["projection"], 34.5, projection["sigma"])
    high = model.grade_market(projection["projection"], 44.5, projection["sigma"])
    assert model.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert projection["projection"] == 40.0
    assert low["edge"] == 5.5
    assert high["edge"] == -4.5
    assert low["over_probability"] > high["over_probability"]


def test_model_fails_closed_without_history_or_market():
    model = _load("nba_pra_page1_model_v1")
    empty = model.project_pra([], [])
    assert empty["projection"] is None
    assert model.probability_over(None, 32.5, 6.0) is None
    assert model.grade_market(None, 32.5, 6.0)["confidence"] == "UNAVAILABLE"
    assert model.grade_market(35.0, None, 6.0)["lean"] == "PASS"


