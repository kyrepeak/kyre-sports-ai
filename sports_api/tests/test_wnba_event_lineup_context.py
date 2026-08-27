import unittest
from unittest.mock import patch

from sports_api import wnba_event_lineup_context as m


GAME_ID = "1022600284"
HOME_ID = 1611661323
AWAY_ID = 1611661329
HOME_KEY = "connecticut-sun"
AWAY_KEY = "chicago-sky"


def _stint(player_id, team_id, team_key, side, start, end):
    return {
        "side": side,
        "game_id": GAME_ID,
        "official_team_id": team_id,
        "team_key": team_key,
        "team_full_name": "Home Team" if side == "home" else "Away Team",
        "player_id": player_id,
        "player_name": f"Player {player_id}",
        "in_time_real": float(start),
        "out_time_real": float(end),
    }


def _side(side, team_id, team_key, specs):
    stints = [
        _stint(player_id, team_id, team_key, side, start, end)
        for player_id, start, end in specs
    ]
    grouped = {}
    for stint in stints:
        grouped.setdefault(stint["player_id"], []).append(stint)
    players = [
        {
            "player_id": player_id,
            "player_name": f"Player {player_id}",
            "official_team_id": team_id,
            "team_key": team_key,
            "team_full_name": "Home Team" if side == "home" else "Away Team",
            "stints": player_stints,
        }
        for player_id, player_stints in sorted(grouped.items())
    ]
    return {
        "side": side,
        "official_team_id": team_id,
        "team_key": team_key,
        "team_full_name": "Home Team" if side == "home" else "Away Team",
        "players": players,
        "stints": stints,
    }


def rotation(boundary=1000, end=2000):
    away_specs = [(player_id, 0, end) for player_id in range(11, 16)]
    home_specs = [(player_id, 0, end) for player_id in range(1, 5)]
    home_specs += [(5, 0, boundary), (6, boundary, end)]
    return {
        "source": "WNBA Stats API",
        "source_url": "https://stats.wnba.com/",
        "source_endpoint": "gamerotation",
        "retrieved_at_utc": "x",
        "cache_hit": False,
        "game_id": GAME_ID,
        "away": _side("away", AWAY_ID, AWAY_KEY, away_specs),
        "home": _side("home", HOME_ID, HOME_KEY, home_specs),
    }


def action(
    number,
    elapsed,
    category,
    *,
    side="home",
    person_id=None,
    sub_type=None,
    action_type=None,
    description=None,
    shot_result=None,
    scoring_side=None,
    points=0,
    period=1,
    clock=None,
):
    if side == "home":
        team_id, team_key = HOME_ID, HOME_KEY
    elif side == "away":
        team_id, team_key = AWAY_ID, AWAY_KEY
    else:
        team_id = team_key = None
    return {
        "action_number": number,
        "action_id": str(number),
        "period": period,
        "clock": clock,
        "clock_seconds_remaining": None,
        "elapsed_game_seconds": elapsed,
        "team_id": team_id,
        "team_key": team_key,
        "person_id": person_id,
        "assist_person_id": None,
        "block_person_id": None,
        "description": description,
        "action_type": action_type or category,
        "sub_type": sub_type,
        "event_category": category,
        "shot_result": shot_result,
        "score_home": None,
        "score_away": None,
        "points_scored_on_action": points,
        "scoring_side": scoring_side,
    }


def pbp(actions):
    return {
        "source": "WNBA Official Live Data",
        "source_url": "pbp",
        "data_type": "official_live_play_by_play",
        "retrieved_at_utc": "x",
        "cache_hit": False,
        "game_id": GAME_ID,
        "actions": actions,
    }


class WNBAEventLineupContextTests(unittest.TestCase):
    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_stable_event_maps_exact_five_v_five(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([action(1, 50.0, "shot", person_id=5)])
        game_rotation.return_value = rotation()
        result = m.get_game_event_lineups(GAME_ID, 2026)
        row = result["events"][0]
        self.assertTrue(row["lineup_context"]["exact_5v5"])
        self.assertEqual(row["lineup_context"]["selected"]["home"]["player_ids"], [1, 2, 3, 4, 5])
        self.assertEqual(row["lineup_context"]["selected"]["away"]["player_ids"], [11, 12, 13, 14, 15])
        self.assertTrue(row["lineup_context"]["eligible_for_player_event_features"])

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_same_clock_events_use_source_order_around_substitution(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([
            action(1, 100.0, "shot", person_id=5),
            action(2, 100.0, "substitution", person_id=6),
            action(3, 100.0, "shot", person_id=6),
        ])
        game_rotation.return_value = rotation()
        result = m.get_game_event_lineups(GAME_ID, 2026)
        before, substitution, after = result["events"]
        self.assertEqual(before["lineup_context"]["selected"]["home"]["player_ids"], [1, 2, 3, 4, 5])
        self.assertEqual(before["lineup_context"]["lineup_phase"], "pre_boundary")
        self.assertEqual(substitution["lineup_context"]["lineup_phase"], "transition")
        self.assertEqual(substitution["lineup_context"]["selected"]["home"]["player_ids"], [1, 2, 3, 4, 6])
        self.assertEqual(after["lineup_context"]["selected"]["home"]["player_ids"], [1, 2, 3, 4, 6])
        self.assertEqual(after["lineup_context"]["lineup_phase"], "post_boundary")

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_event_filter_is_applied_after_substitution_reconstruction(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([
            action(1, 100.0, "shot", person_id=5),
            action(2, 100.0, "substitution", person_id=6),
            action(3, 100.0, "shot", person_id=6),
        ])
        game_rotation.return_value = rotation()
        result = m.get_game_event_lineups(GAME_ID, 2026, event_category="shot")
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(result["events"][0]["lineup_context"]["lineup_phase"], "pre_boundary")
        self.assertEqual(result["events"][1]["lineup_context"]["lineup_phase"], "post_boundary")
        play_by_play.assert_called_once_with(GAME_ID, 2026, event_category="All", limit=0)

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_period_end_uses_pre_boundary_and_period_start_uses_post(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([
            action(1, 600.0, "period", side=None, action_type="period", sub_type="end", period=1, clock="PT00M00.00S"),
            action(2, 600.0, "period", side=None, action_type="period", sub_type="start", period=2, clock="PT10M00.00S"),
        ])
        game_rotation.return_value = rotation(boundary=6000, end=12000)
        result = m.get_game_event_lineups(GAME_ID, 2026)
        end_event, start_event = result["events"]
        self.assertEqual(end_event["lineup_context"]["selected"]["home"]["player_ids"], [1, 2, 3, 4, 5])
        self.assertEqual(start_event["lineup_context"]["selected"]["home"]["player_ids"], [1, 2, 3, 4, 6])

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_known_participant_can_resolve_unordered_rotation_boundary(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([action(1, 100.0, "shot", person_id=5)])
        game_rotation.return_value = rotation()
        result = m.get_game_event_lineups(GAME_ID, 2026)
        context = result["events"][0]["lineup_context"]
        self.assertEqual(context["lineup_phase"], "pre_boundary")
        self.assertIn("participants_resolve_pre", context["selection_basis"])

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_unordered_boundary_without_evidence_fails_closed(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([action(1, 100.0, "timeout", person_id=None)])
        game_rotation.return_value = rotation()
        result = m.get_game_event_lineups(GAME_ID, 2026)
        context = result["events"][0]["lineup_context"]
        self.assertFalse(context["available"])
        self.assertEqual(context["lineup_phase"], "ambiguous_boundary")
        self.assertFalse(context["eligible_for_player_event_features"])

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_missing_known_participant_is_flagged_not_fabricated(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([action(1, 50.0, "shot", person_id=999)])
        game_rotation.return_value = rotation()
        result = m.get_game_event_lineups(GAME_ID, 2026)
        context = result["events"][0]["lineup_context"]
        self.assertFalse(context["known_participants_on_selected_court"])
        self.assertEqual(context["missing_known_participant_ids"], [999])
        self.assertFalse(context["eligible_for_player_event_features"])

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_bad_cardinality_is_exposed_instead_of_filled(self, play_by_play, game_rotation):
        bad = rotation()
        bad["away"]["players"] = [p for p in bad["away"]["players"] if p["player_id"] != 15]
        bad["away"]["stints"] = [s for s in bad["away"]["stints"] if s["player_id"] != 15]
        play_by_play.return_value = pbp([action(1, 50.0, "shot", person_id=5)])
        game_rotation.return_value = bad
        result = m.get_game_event_lineups(GAME_ID, 2026)
        context = result["events"][0]["lineup_context"]
        self.assertFalse(context["exact_5v5"])
        self.assertEqual(context["selected"]["away"]["player_count"], 4)
        self.assertFalse(context["eligible_for_player_event_features"])

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_zero_team_id_on_non_team_event_is_treated_as_no_team(self, play_by_play, game_rotation):
        period = action(1, 0.0, "period", side=None, action_type="period", sub_type="start", period=1, clock="PT10M00.00S")
        period["team_id"] = 0
        play_by_play.return_value = pbp([period])
        game_rotation.return_value = rotation()
        result = m.get_game_event_lineups(GAME_ID, 2026)
        self.assertIsNone(result["events"][0]["event_side"])
        self.assertTrue(result["events"][0]["lineup_context"]["exact_5v5"])

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_team_event_outside_rotation_matchup_fails_closed(self, play_by_play, game_rotation):
        bad_action = action(1, 50.0, "shot", person_id=5)
        bad_action["team_id"] = 999999
        bad_action["team_key"] = "not-this-game"
        play_by_play.return_value = pbp([bad_action])
        game_rotation.return_value = rotation()
        with self.assertRaisesRegex(m.WNBAEventLineupUpstreamError, "outside the rotation matchup"):
            m.get_game_event_lineups(GAME_ID, 2026)

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_possessions_close_on_defensive_rebound_turnover_and_made_shot(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([
            action(1, 10.0, "shot", side="home", person_id=1, shot_result="Missed"),
            action(2, 12.0, "rebound", side="away", person_id=11, sub_type="Defensive"),
            action(3, 20.0, "turnover", side="away", person_id=12),
            action(4, 30.0, "shot", side="home", person_id=2, shot_result="Made", scoring_side="home", points=2),
        ])
        game_rotation.return_value = rotation(boundary=1000, end=2000)
        result = m.get_game_possession_event_context(GAME_ID, 2026)
        self.assertEqual(result["possession_count"], 3)
        self.assertEqual([p["offense_side"] for p in result["possessions"]], ["home", "away", "home"])
        self.assertEqual([p["end_reason"] for p in result["possessions"]], ["defensive_rebound", "turnover", "made_field_goal"])
        self.assertEqual(result["possessions"][2]["points_scored_by_offense"], 2)

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_and_one_field_goal_and_free_throw_remain_one_segment(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([
            action(1, 10.0, "shot", side="home", person_id=1, shot_result="Made", scoring_side="home", points=2),
            action(2, 10.0, "free_throw", side="home", person_id=1, sub_type="1 of 1", shot_result="Made", scoring_side="home", points=1),
        ])
        game_rotation.return_value = rotation(boundary=1000, end=2000)
        result = m.get_game_possession_event_context(GAME_ID, 2026)
        self.assertEqual(result["possession_count"], 1)
        possession = result["possessions"][0]
        self.assertEqual(possession["end_reason"], "made_final_free_throw")
        self.assertEqual(possession["event_count"], 2)
        self.assertEqual(possession["points_scored_by_offense"], 3)
        self.assertEqual(possession["boundary_confidence"], "medium")

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_live_open_segment_is_marked_incomplete(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([action(1, 10.0, "shot", side="home", person_id=1, shot_result="Missed")])
        game_rotation.return_value = rotation(boundary=1000, end=2000)
        result = m.get_game_possession_event_context(GAME_ID, 2026)
        possession = result["possessions"][0]
        self.assertFalse(possession["complete"])
        self.assertEqual(possession["end_reason"], "open_at_feed_end")
        self.assertEqual(possession["boundary_confidence"], "low")

    def test_bad_game_id_and_limit_fail_before_network(self):
        with patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset") as play_by_play:
            with self.assertRaisesRegex(ValueError, "10 numeric digits"):
                m.get_game_event_lineups("123", 2026)
            with self.assertRaisesRegex(ValueError, "0 through 1000"):
                m.get_game_event_lineups(GAME_ID, 2026, limit=1001)
            play_by_play.assert_not_called()

    @patch("sports_api.wnba_event_lineup_context.get_game_rotation")
    @patch("sports_api.wnba_event_lineup_context.get_play_by_play_dataset")
    def test_rotation_not_found_is_translated(self, play_by_play, game_rotation):
        play_by_play.return_value = pbp([])
        game_rotation.side_effect = m.WNBARotationNotFoundError("missing")
        with self.assertRaises(m.WNBAEventLineupNotFoundError):
            m.get_game_event_lineups(GAME_ID, 2026)

    def test_guardrail_constants_are_present_in_outputs(self):
        rows, teams = m._reconstruct_all_events(
            pbp([action(1, 50.0, "shot", person_id=5)]),
            rotation(),
        )
        possessions = m._reconstruct_possessions(rows, teams)
        self.assertTrue(rows[0]["lineup_context"]["guardrails"]["event_lineup_is_court_context_not_defender_assignment"])
        self.assertTrue(possessions[0]["guardrails"]["no_player_vs_defender_possession_inferred"])


if __name__ == "__main__":
    unittest.main()
