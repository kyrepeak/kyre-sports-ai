from __future__ import annotations

import nfl_passing_yards_hub_v74 as v74
import streamlit_memory_lazy_router_v225 as v225


BODY = """
<section data-passing-yards-qb-detail="v59" data-passing-yards-live-market-ready="v73">
  <div class="kpass29-meta">QB • GB vs ATL • Green Bay Packers</div>
  <section class="ks-py73-market" data-passing-yards-live-market="v73"></section>
  <section class="kpy-personnel">
    <div class="kpy-imetric"><b>No listed injury</b><span>QB Status</span></div>
    <div class="kpy-imetric"><b>1</b><span>Skill Hard</span></div>
    <div class="kpy-imetric"><b>0</b><span>OL Hard</span></div>
    <div class="kpy-imetric"><b>2</b><span>Opp Secondary Hard</span></div>
  </section>
  <section class="kpy-env">
    <div class="kpy-envmetric"><b>Outdoor</b><span>Venue Type</span></div>
    <div class="kpy-envmetric"><b>Grass</b><span>Surface</span></div>
    <div class="kpy-envmetric"><b>WATCH</b><span>Weather</span></div>
    <div class="kpy-envmetric"><b>63°F</b><span>Temperature</span></div>
    <div class="kpy-envmetric"><b>12 mph</b><span>Wind</span></div>
  </section>
</section>
"""


def test_step5_contract_is_additive_and_math_frozen() -> None:
    assert v74.FROZEN_PRIOR == "nfl_passing_yards_hub_v73"
    assert v74.FROZEN_AVAILABILITY_PROVIDER == "nfl_game_day_availability_v1"
    assert v74.NEW_PHASE_STEP == 5
    assert v74.PRESENTATION_ONLY is True
    assert v74.MAY_MODIFY_PROJECTION is False
    assert v74.MAY_MODIFY_CONTEXT_MATH is False
    assert v74.MAY_MODIFY_PROBABILITY is False
    assert v74.MAY_MODIFY_MARKET_MATH is False
    assert v74.MAY_MODIFY_PERSONNEL_MATH is False
    assert v74.MAY_MODIFY_ENVIRONMENT_MATH is False
    assert v74.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v74.STAKE_SIZING_ENABLED is False
    assert v225.FROZEN_ROUTER == "streamlit_memory_lazy_router_v224"
    assert v225.PASSING_HUB == "nfl_passing_yards_hub_v74"


def test_exact_matchup_identity_from_frozen_selected_qb_card() -> None:
    out = v74._selected_matchup_identity(BODY)
    assert out["ready"] is True
    assert out["selected_abbr"] == "GB"
    assert out["opponent_abbr"] == "ATL"
    assert out["away_abbr"] == "ATL"
    assert out["home_abbr"] == "GB"
    assert out["selected_side"] == "home"


def test_game_day_pending_is_truthful_ready_provider_state() -> None:
    scoreboard = [{"game_id": "401772944", "state": "pre", "away_abbr": "ATL", "home_abbr": "GB"}]
    event_map = {"ATL": [], "GB": []}
    out = v74.resolve_game_day_snapshot(
        BODY,
        "2026-09-24",
        scoreboard_rows=scoreboard,
        scoreboard_diag={"ok": True, "http": 200},
        event_loader=lambda game_id: (event_map, {"ok": True, "http": 200}),
    )
    assert out["game_id"] == "401772944"
    assert out["provider_ok"] is True
    assert out["state"] == "PENDING"
    assert out["prop_gate_open"] is False
    assert out["selected_explicit_inactive"] == []
    assert out["opponent_explicit_inactive"] == []


def test_game_day_confirmed_preserves_exact_side_rows() -> None:
    scoreboard = [{"game_id": "401772944", "state": "pre", "away_abbr": "ATL", "home_abbr": "GB"}]
    event_map = {
        "ATL": [{"athlete_id": "1", "name": "Away WR", "status": "Inactive"}],
        "GB": [{"athlete_id": "2", "name": "Home OL", "status": "Inactive"}],
    }
    out = v74.resolve_game_day_snapshot(
        BODY,
        "2026-09-24",
        scoreboard_rows=scoreboard,
        scoreboard_diag={"ok": True, "http": 200},
        event_loader=lambda game_id: (event_map, {"ok": True, "http": 200}),
    )
    assert out["state"] == "CONFIRMED"
    assert out["prop_gate_open"] is True
    assert out["selected_explicit_inactive"][0]["name"] == "Home OL"
    assert out["opponent_explicit_inactive"][0]["name"] == "Away WR"


def test_provider_failure_fails_closed_without_fabrication() -> None:
    out = v74.resolve_game_day_snapshot(
        BODY,
        "2026-09-24",
        scoreboard_rows=[],
        scoreboard_diag={"ok": False, "http": 503},
    )
    assert out["state"] == "UNVERIFIED"
    assert out["provider_ok"] is False
    assert out["selected_explicit_inactive"] == []
    assert out["opponent_explicit_inactive"] == []


def test_panel_consolidates_personnel_environment_and_inactive_state() -> None:
    snapshot = {
        "state": "PENDING",
        "provider_ok": True,
        "game_id": "401772944",
        "selected_unavailable": [],
        "opponent_unavailable": [],
        "selected_explicit_inactive": [],
        "opponent_explicit_inactive": [],
    }
    panel = v74.build_availability_panel(BODY, snapshot)
    for token in (
        'data-passing-yards-availability-game-day="v74"',
        'data-passing-yards-availability-ready="true"',
        'data-game-day-state="PENDING"',
        'data-passing-yards-v225-runtime="availability-game-day-step5"',
        "Availability + game-day conditions",
        "QB Status",
        "Skill Hard",
        "OL Hard",
        "Opp Secondary Hard",
        "Venue Type",
        "Surface",
        "Weather",
        "Wind",
        "FINAL INACTIVES PENDING",
        "Sportsbook projection influence 0.0%",
        "stake sizing OFF",
    ):
        assert token in panel


def test_injection_is_once_only_and_preserves_step4() -> None:
    snapshot = {
        "state": "PENDING",
        "provider_ok": True,
        "game_id": "401772944",
        "selected_unavailable": [],
        "opponent_unavailable": [],
        "selected_explicit_inactive": [],
        "opponent_explicit_inactive": [],
    }
    original = v74._runtime_game_day_snapshot
    try:
        v74._runtime_game_day_snapshot = lambda body: snapshot
        once = v74._inject_availability_game_day(BODY, 2)
        twice = v74._inject_availability_game_day(once, 2)
    finally:
        v74._runtime_game_day_snapshot = original
    assert once.count('data-passing-yards-availability-game-day="v74"') == 1
    assert twice.count('data-passing-yards-availability-game-day="v74"') == 1
    assert 'data-passing-yards-live-market="v73"' in twice
    assert 'data-passing-yards-availability-game-day-ready="v74"' in twice
