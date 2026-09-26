from pathlib import Path

import nfl_prop_analytics_player_select_v1 as step7


def _row(
    player_id,
    name,
    team,
    position,
    availability="PENDING",
    depth_verified=True,
    verified=True,
    source_count=2,
    depth_rank=1,
):
    return {
        "espn_id": str(player_id),
        "name": name,
        "team": team,
        "position": position,
        "availability_state": availability,
        "availability_label": availability,
        "depth_verified": depth_verified,
        "verified": verified,
        "source_count": source_count,
        "depth_rank": depth_rank,
        "depth_role": f"{position}{depth_rank}",
    }


def _step6(players_car=None, players_cle=None):
    if players_car is None:
        players_car = [
        _row(101, "CAR QB", "CAR", "QB"),
        _row(102, "CAR RB", "CAR", "RB"),
        _row(103, "CAR WR", "CAR", "WR", depth_rank=2),
        _row(104, "CAR TE", "CAR", "TE"),
    ]
    if players_cle is None:
        players_cle = [
        _row(201, "CLE QB", "CLE", "QB"),
        _row(202, "CLE RB", "CLE", "RB"),
        _row(203, "CLE WR", "CLE", "WR", depth_rank=2),
        _row(204, "CLE TE", "CLE", "TE"),
    ]
    return {
        "state": "live",
        "selection_key": "CAR-CLE",
        "event_id": "401872949",
        "availability_state": "PENDING",
        "teams": {
            "CAR": {"team": "CAR", "players": players_car},
            "CLE": {"team": "CLE", "players": players_cle},
        },
    }


def _matchup():
    return {
        "state": "ready",
        "selection_key": "CAR-CLE",
        "away": "CAR",
        "home": "CLE",
        "target_date": "2026-09-27",
        "week": 3,
    }


def test_step7_contract_is_selection_handoff_only():
    source = Path("nfl_prop_analytics_player_select_v1.py").read_text()
    for token in (
        'MODEL_VERSION = "NFL PROP ANALYTICS V1 • STEP 7 ELIGIBLE PLAYER SELECTION + PROP PAGE HANDOFF"',
        "STEP = 7",
        "PAGE = 2",
        "SELECTION_HANDOFF_ONLY = True",
        "PLAYER_PROP_LOGIC = False",
        "SPORTSBOOK_ODDS_LOGIC = False",
        "PROJECTION_LOGIC = False",
        "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0",
        'data-nfl-prop-analytics-step7-player-selection="v1"',
        'data-prop-step7-prop-gate=',
        'data-prop-step7-prop-page-ready="true"',
        'QUERY_KEY = "ks_pa_player"',
    ):
        assert token in source, token


def test_pending_player_is_selectable_but_prop_gate_stays_closed():
    players = step7.eligible_players(_step6())
    qb = next(row for row in players if row["espn_id"] == "101")
    assert qb["selection_eligible"] is True
    assert qb["availability_state"] == "PENDING"
    assert qb["prop_analysis_gate_open"] is False

    handoff = step7.build_player_handoff(_matchup(), _step6(), qb)
    assert handoff["state"] == "ready"
    assert handoff["player_id"] == "101"
    assert handoff["availability_state"] == "PENDING"
    assert handoff["prop_page_ready"] is True
    assert handoff["prop_analysis_gate_open"] is False


def test_available_player_is_selectable_and_prop_gate_can_open():
    truth = _step6(
        players_car=[
            _row(101, "CAR QB", "CAR", "QB", availability="AVAILABLE"),
        ],
        players_cle=[
            _row(201, "CLE QB", "CLE", "QB", availability="AVAILABLE"),
        ],
    )
    players = step7.eligible_players(truth)
    assert len(players) == 2
    assert all(row["prop_analysis_gate_open"] is True for row in players)

    handoff = step7.build_player_handoff(_matchup(), truth, players[0])
    assert handoff["prop_analysis_gate_open"] is True
    assert handoff["availability_state"] == "AVAILABLE"


def test_blocked_availability_states_are_not_selectable():
    car = [
        _row(101, "Pending", "CAR", "QB", availability="PENDING"),
        _row(102, "Out", "CAR", "RB", availability="UNAVAILABLE"),
        _row(103, "Closed", "CAR", "WR", availability="CLOSED"),
        _row(104, "Unknown", "CAR", "TE", availability="UNVERIFIED"),
    ]
    players = step7.eligible_players(_step6(players_car=car, players_cle=[]))
    assert [row["espn_id"] for row in players] == ["101"]


def test_depth_unverified_and_single_source_players_are_excluded():
    car = [
        _row(101, "Good", "CAR", "QB"),
        _row(102, "No Depth", "CAR", "RB", depth_verified=False),
        _row(103, "One Source", "CAR", "WR", source_count=1),
        _row(104, "Not Verified", "CAR", "TE", verified=False),
    ]
    players = step7.eligible_players(_step6(players_car=car, players_cle=[]))
    assert [row["espn_id"] for row in players] == ["101"]


def test_handoff_preserves_exact_step6_identity_and_context():
    truth = _step6()
    player = next(row for row in step7.eligible_players(truth) if row["espn_id"] == "203")
    handoff = step7.build_player_handoff(_matchup(), truth, player)
    assert handoff == {
        "version": "v1",
        "state": "ready",
        "selection_key": "CAR-CLE",
        "event_id": "401872949",
        "player_id": "203",
        "player_name": "CLE WR",
        "team": "CLE",
        "position": "WR",
        "depth_rank": 2,
        "depth_role": "WR2",
        "availability_state": "PENDING",
        "roster_verified": True,
        "roster_source_count": 2,
        "depth_verified": True,
        "selection_eligible": True,
        "prop_analysis_gate_open": False,
        "prop_page_ready": True,
    }


def test_invalid_player_cannot_build_handoff():
    bad = _row(999, "Unavailable", "CAR", "QB", availability="UNAVAILABLE")
    try:
        step7.build_player_handoff(_matchup(), _step6(), bad)
    except ValueError as exc:
        assert "not Step 7 selection-eligible" in str(exc)
    else:
        raise AssertionError("Unavailable player built a Step 7 handoff")


def test_query_index_prefers_exact_requested_player_id():
    players = step7.eligible_players(_step6())
    idx = step7._resolve_initial_index(players, "203", "101")
    assert players[idx]["espn_id"] == "203"


def test_hub_renders_step7_only_after_step6_live():
    hub = Path("nfl_prop_analytics_hub_v1.py").read_text()
    assert "availability_truth = render_availability_depth_truth(handoff, roster_truth)" in hub
    assert 'availability_truth.get("state") == "live"' in hub
    assert "render_player_selection_handoff(handoff, availability_truth)" in hub
    assert hub.index("render_availability_depth_truth(handoff, roster_truth)") < hub.index(
        "render_player_selection_handoff(handoff, availability_truth)"
    )


def test_step7_keeps_prop_odds_projection_flags_off():
    assert step7.PLAYER_PROP_LOGIC is False
    assert step7.SPORTSBOOK_ODDS_LOGIC is False
    assert step7.PROJECTION_LOGIC is False
    assert step7.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step7.MAY_MODIFY_PASSING_YARDS is False
    assert step7.MAY_MODIFY_EXISTING_NFL_MARKETS is False
