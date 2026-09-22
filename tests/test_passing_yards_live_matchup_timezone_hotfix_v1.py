from pathlib import Path
import importlib.util
import sys
import types

import nfl_passing_yards_defense_v3 as hardened

ROOT = Path(__file__).resolve().parents[1]
V62 = (ROOT / "nfl_passing_yards_hub_v62.py").read_text()
R213 = (ROOT / "streamlit_memory_lazy_router_v213.py").read_text()
APP = (ROOT / "app.py").read_text()


def _event(event_id: str, when: str, completed: bool = True) -> dict:
    return {
        "id": event_id,
        "date": when,
        "competitions": [
            {
                "status": {
                    "type": {
                        "completed": completed,
                        "state": "post" if completed else "pre",
                    }
                }
            }
        ],
    }


def test_certified_v3_parser_handles_aware_event_vs_date_only_cutoff():
    payload = {
        "events": [
            _event("401", "2026-09-20T17:00:00Z"),
            _event("402", "2026-09-21T20:25:00+00:00"),
        ]
    }
    rows = hardened._completed_event_rows_utc(payload, "2026-09-24", max_games=5)
    assert [row["event_id"] for row in rows] == ["402", "401"]


def test_certified_v3_parser_excludes_cutoff_day_and_future_events():
    payload = {
        "events": [
            _event("401", "2026-09-23T23:59:59Z"),
            _event("402", "2026-09-24T00:00:00Z"),
            _event("403", "2026-09-25T01:00:00Z"),
        ]
    }
    rows = hardened._completed_event_rows_utc(payload, "2026-09-24", max_games=5)
    assert [row["event_id"] for row in rows] == ["401"]


def test_v62_installs_utc_parser_only_during_frozen_v61_render(monkeypatch):
    defense_v1 = types.ModuleType("nfl_passing_yards_defense_v1")
    original_rows = lambda *args, **kwargs: ["legacy"]
    defense_v1._completed_event_rows = original_rows

    defense_v3 = types.ModuleType("nfl_passing_yards_defense_v3")
    utc_rows = lambda *args, **kwargs: ["utc"]
    defense_v3._completed_event_rows_utc = utc_rows

    prior = types.ModuleType("nfl_passing_yards_hub_v61")
    observed = {}

    def prior_render():
        observed["during"] = defense_v1._completed_event_rows
        return "ok"

    prior.render_nfl_passing_yards_hub = prior_render

    monkeypatch.setitem(sys.modules, "nfl_passing_yards_defense_v1", defense_v1)
    monkeypatch.setitem(sys.modules, "nfl_passing_yards_defense_v3", defense_v3)
    monkeypatch.setitem(sys.modules, "nfl_passing_yards_hub_v61", prior)

    spec = importlib.util.spec_from_file_location(
        "nfl_passing_yards_hub_v62_runtime_probe",
        ROOT / "nfl_passing_yards_hub_v62.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.render_nfl_passing_yards_hub() == "ok"
    assert observed["during"] is utc_rows
    assert defense_v1._completed_event_rows is original_rows


def test_v62_is_additive_runtime_only_over_frozen_v61():
    assert 'FROZEN_PRIOR = "nfl_passing_yards_hub_v61"' in V62
    assert "nfl_passing_yards_defense_v3 as defense_hardened" in V62
    assert "defense_hardened._completed_event_rows_utc" in V62
    assert "MAY_MODIFY_PROJECTION = False" in V62
    assert "MAY_MODIFY_PROBABILITY = False" in V62
    assert "MAY_MODIFY_MARKET_MATH = False" in V62
    assert "MAY_MODIFY_PRESENTATION = False" in V62
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in V62


def test_router_v213_advances_only_passing_yards_to_v62():
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v212"' in R213
    assert 'PASSING_HUB = "nfl_passing_yards_hub_v62"' in R213
    assert 'data-passing-yards-v213-runtime="live-matchup-utc-hotfix"' in R213
    assert "return prior.render_app()" in R213


def test_app_boots_v213_and_preserves_v212_compatibility():
    assert "from streamlit_memory_lazy_router_v213 import record_bootstrap_import_ms, render_app" in APP
    assert "Frozen Step 4 router compatibility" in APP
    assert 'PASSING_YARDS_LIVE_MATCHUP_UTC_HOTFIX_RUNTIME = "NFL_PASSING_YARDS_V62_UTC_2026_09_22"' in APP
