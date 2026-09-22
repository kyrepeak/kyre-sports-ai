"""Targeted Step 7 source/runtime-owner verifier."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    app = _read("app.py")
    router = _read("streamlit_memory_lazy_router_v187.py")
    passing = _read("nfl_passing_yards_hub_v42.py")
    rushing = _read("nfl_rushing_yards_hub_v16.py")
    receiving = _read("nfl_receiving_yards_hub_v17.py")
    guard = _read("nfl_prop_app_eligibility_v1.py")

    assert "from streamlit_memory_lazy_router_v187 import record_bootstrap_import_ms, render_app" in app
    assert '"Passing Yards": "nfl_passing_yards_hub_v42"' in router
    assert '"Rushing Yards": "nfl_rushing_yards_hub_v16"' in router
    assert '"Receiving Yards": "nfl_receiving_yards_hub_v17"' in router
    assert 'RECEPTIONS_MARKET = "Receptions"' in router
    assert "fail-closed at the Step 7 app identity gate" in router
    assert "guard_passing_identity" in passing
    assert "guard_context_payload" in rushing
    assert "guard_context_payload" in receiving
    assert "athlete_id not in current_ids" in guard
    assert 'state in {"in", "post"}' in guard
    assert "player names never participate" in guard.lower()
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in guard

    print("NFL_STEP7_APP_IDENTITY_FAIL_CLOSED_V1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
