import unittest
from unittest.mock import patch

from sports_api import wnba_player_opportunity_context as m


PLAYER_ID = 100
TEAM_KEY = "indiana-fever"
OPPONENT_KEY = "new-york-liberty"


def rotation_context(*, player_id=PLAYER_ID, team_key=TEAM_KEY):
    games = []
    for index, minutes in enumerate((30.0, 36.0, 33.0), start=1):
        games.append({
            "game_id": f"10226002{index:02d}",
            "game_date": f"2026-08-{20 + index:02d}",
            "player_rotation": {
                "player_id": player_id,
                "player_name": "Test Player",
                "team_key": team_key,
                "tracked_minutes": minutes,
                "stint_count": index + 1,
                "started_game": index != 2,
            },
        })
    return {
        "source": "WNBA Stats API",
        "data_type": "official_recent_player_rotation_context",
        "player_id": player_id,
        "team_keys_observed": [team_key],
        "rotation_game_count": 3,
        "missing_rotation_game_ids": [],
        "aggregate": {
            "stint_count": 9,
            "tracked_seconds": 5940.0,
            "tracked_minutes": 99.0,
            "tracked_minutes_per_rotation_game": 33.0,
            "average_stint_seconds": 660.0,
            "starts_in_rotation_games": 2,
            "start_share": 2 / 3,
            "player_points_during_stints": 55.0,
            "team_point_differential_during_stints": 10.0,
            "time_weighted_usage_percentage": .25,
        },
        "games": games,
    }


def counts(multiplier=1):
    return {
        "field_goals_attempted": 30 * multiplier,
        "field_goals_made": 15 * multiplier,
        "three_pointers_attempted": 12 * multiplier,
        "three_pointers_made": 5 * multiplier,
        "free_throws_attempted": 10 * multiplier,
        "free_throws_made": 8 * multiplier,
        "offensive_rebounds": 3 * multiplier,
        "defensive_rebounds": 12 * multiplier,
        "rebounds": 15 * multiplier,
        "assists": 18 * multiplier,
        "turnovers": 6 * multiplier,
        "blocks": 2 * multiplier,
        "personal_fouls": 7 * multiplier,
        "points": 50 * multiplier,
    }


def event_context(*, player_id=PLAYER_ID, team_key=TEAM_KEY):
    own = counts()
    team = counts(2)
    opponent = counts(2)
    games = [{
        "game_id": "1022600203",
        "features": {
            "team": {"team_key": team_key},
            "opponent": {"team_key": OPPONENT_KEY},
        },
    }]
    return {
        "source": "WNBA Step 4T Event-Lineup + Derived Possession Context",
        "data_type": "official_recent_player_event_floor_context_features",
        "player_id": player_id,
        "feature_game_count": 3,
        "missing_feature_game_ids": [],
        "team_keys_observed": [team_key],
        "games": games,
        "aggregate": {
            "data_quality": {
                "selected_lineup_event_count": 150,
                "feature_eligible_event_count": 120,
                "feature_eligible_share_of_selected_lineup_events": .8,
            },
            "own_event_counts": own,
            "own_shot_profile": {"field_goal_percentage": .5},
            "on_court_event_environment": {
                "team": team,
                "opponent": opponent,
                "action_shares_of_team_events": {
                    "field_goal_attempt_share": .5,
                    "assist_event_share": .5,
                },
            },
            "co_presence": {
                "teammates": [{"player_id": 101, "shared_feature_eligible_event_count": 100}],
                "opponents": [{"player_id": 201, "shared_feature_eligible_event_count": 90}],
            },
            "derived_possession_exposure": {
                "stable_complete_segment_count": 60,
                "stable_incomplete_segment_count": 2,
                "stable_complete_offensive_segment_count": 30,
                "stable_complete_defensive_segment_count": 30,
                "unstable_player_presence_segment_count": 1,
                "player_present_but_lineup_ineligible_segment_count": 1,
                "offensive_points_in_stable_complete_segments": 32,
                "defensive_points_allowed_in_stable_complete_segments": 28,
                "offensive_points_per_100_stable_complete_segments": 106.6667,
                "defensive_points_allowed_per_100_stable_complete_segments": 93.3333,
            },
        },
    }


def role_context(starter_share=.8):
    starter_games = int(round(starter_share * 10))
    bench_games = 10 - starter_games
    return {
        "role_summary": {
            "starter_games": starter_games,
            "bench_games": bench_games,
            "starter_game_share": starter_share,
            "primary_observed_role": "starter" if starter_share > .5 else "bench",
        },
        "starter": {"role": "Starters", "games_played": starter_games},
        "bench": {"role": "Bench", "games_played": bench_games},
    }


def lineup_context(*, include_player=True):
    ids = [PLAYER_ID, 101, 102, 103, 104] if include_player else [999, 101, 102, 103, 104]
    return {
        "lineups": [{
            "group_id": "-".join(str(value) for value in ids),
            "group_name": "Lineup",
            "player_ids": ids,
            "members": [{"player_id": value} for value in ids],
            "games_played": 3,
            "stats": {
                "minutes": 12.5,
                "points": 20.0,
                "rebounds": 10.0,
                "assists": 7.0,
                "plus_minus": 4.0,
            },
        }],
    }


def availability_context(*, team_key=TEAM_KEY, include_focal=True):
    players = []
    if include_focal:
        players.append({
            "player_id": PLAYER_ID,
            "player_name": "Test Player",
            "position": "G",
            "injury_report_status": None,
            "injury_reason": None,
            "listed_on_injury_report": False,
            "availability_class": "not_listed",
            "availability_blocking": False,
            "availability_uncertain": False,
            "recent_minutes_per_game": 33.0,
            "observed_rotation_rank_by_recent_minutes": 1,
            "member_of_most_used_five_player_lineup": True,
        })
    players.append({
        "player_id": 101,
        "player_name": "Teammate",
        "position": "F",
        "injury_report_status": "Out",
        "injury_reason": "Ankle",
        "listed_on_injury_report": True,
        "availability_class": "unavailable",
        "availability_blocking": True,
        "availability_uncertain": False,
        "recent_minutes_per_game": 30.0,
        "observed_rotation_rank_by_recent_minutes": 2,
        "member_of_most_used_five_player_lineup": True,
    })
    return {
        "team_key": team_key,
        "injury_report": {"report_timestamp_eastern": "2026-08-26T12:00:00-04:00"},
        "team": {
            "players": players,
            "team_report_not_yet_submitted": False,
            "starter_verification": {
                "official_starters_confirmed": False,
                "status": "pregame_not_confirmed_from_central_official_sources",
            },
        },
    }


class WNBAPlayerOpportunityContextTests(unittest.TestCase):
    def _run(self, **kwargs):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()), \
             patch.object(m, "get_player_role_context_dataset", return_value=role_context()), \
             patch.object(m, "get_lineups_dataset", return_value=lineup_context()), \
             patch.object(m, "get_team_availability_context_dataset", return_value=availability_context()):
            return m.get_player_opportunity_context(PLAYER_ID, 2026, **kwargs)

    def test_rotation_stability_math(self):
        result = self._run()
        stability = result["observed_minutes_opportunity"]["tracked_minutes"]["stability"]
        self.assertEqual(stability["tracked_minutes_mean"], 33.0)
        self.assertEqual(stability["tracked_minutes_median"], 33.0)
        self.assertEqual(stability["tracked_minutes_range"], 6.0)
        self.assertEqual(stability["starts_in_rotation_games"], 2)
        self.assertAlmostEqual(stability["start_share"], 2 / 3, places=6)

    def test_event_counts_are_converted_to_per_feature_game_rates(self):
        result = self._run()
        event = result["observed_event_opportunity"]
        self.assertEqual(event["own_event_counts_per_feature_game"]["field_goals_attempted"], 10.0)
        self.assertEqual(event["own_event_counts_per_feature_game"]["assists"], 6.0)
        self.assertEqual(event["derived_offensive_segments_per_feature_game"], 10.0)

    def test_role_band_mostly_starter(self):
        result = self._run()
        self.assertEqual(result["observed_role_context"]["observed_role_band"], "mostly_starter")

    def test_role_band_mostly_bench(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()), \
             patch.object(m, "get_player_role_context_dataset", return_value=role_context(.1)), \
             patch.object(m, "get_lineups_dataset", return_value=lineup_context()), \
             patch.object(m, "get_team_availability_context_dataset", return_value=availability_context()):
            result = m.get_player_opportunity_context(PLAYER_ID, 2026)
        self.assertEqual(result["observed_role_context"]["observed_role_band"], "mostly_bench")

    def test_role_band_mixed(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()), \
             patch.object(m, "get_player_role_context_dataset", return_value=role_context(.5)), \
             patch.object(m, "get_lineups_dataset", return_value=lineup_context()), \
             patch.object(m, "get_team_availability_context_dataset", return_value=availability_context()):
            result = m.get_player_opportunity_context(PLAYER_ID, 2026)
        self.assertEqual(result["observed_role_context"]["observed_role_band"], "mixed_starter_bench_history")

    def test_role_not_found_fails_soft(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()), \
             patch.object(m, "get_player_role_context_dataset", side_effect=m.WNBALineupContextNotFoundError("missing")), \
             patch.object(m, "get_lineups_dataset", return_value=lineup_context()), \
             patch.object(m, "get_team_availability_context_dataset", return_value=availability_context()):
            result = m.get_player_opportunity_context(PLAYER_ID, 2026)
        self.assertFalse(result["observed_role_context"]["available"])
        self.assertEqual(result["observed_role_context"]["error"], "missing")

    def test_lineup_upstream_failure_fails_soft(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()), \
             patch.object(m, "get_player_role_context_dataset", return_value=role_context()), \
             patch.object(m, "get_lineups_dataset", side_effect=m.WNBALineupContextUpstreamError("blocked")), \
             patch.object(m, "get_team_availability_context_dataset", return_value=availability_context()):
            result = m.get_player_opportunity_context(PLAYER_ID, 2026)
        self.assertFalse(result["observed_five_player_lineup_context"]["available"])
        self.assertEqual(result["observed_five_player_lineup_context"]["error"], "blocked")

    def test_targeted_lineup_without_focal_player_fails_closed(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()), \
             patch.object(m, "get_player_role_context_dataset", return_value=role_context()), \
             patch.object(m, "get_lineups_dataset", return_value=lineup_context(include_player=False)), \
             patch.object(m, "get_team_availability_context_dataset", return_value=availability_context()):
            with self.assertRaisesRegex(m.WNBAPlayerOpportunityUpstreamError, "without focal player"):
                m.get_player_opportunity_context(PLAYER_ID, 2026)

    def test_availability_can_be_skipped_before_network(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()), \
             patch.object(m, "get_player_role_context_dataset", return_value=role_context()), \
             patch.object(m, "get_lineups_dataset", return_value=lineup_context()), \
             patch.object(m, "get_team_availability_context_dataset") as availability:
            result = m.get_player_opportunity_context(
                PLAYER_ID, 2026, include_current_availability=False
            )
        availability.assert_not_called()
        self.assertFalse(result["current_availability_context"]["requested"])

    def test_current_roster_match_verifies_team_and_preserves_out_teammate(self):
        result = self._run()
        availability = result["current_availability_context"]
        self.assertTrue(availability["current_roster_team_verified"])
        teammate = next(row for row in availability["same_team_statuses"] if row["player_id"] == 101)
        self.assertEqual(teammate["injury_report_status"], "Out")
        self.assertTrue(teammate["availability_blocking"])

    def test_missing_focal_from_current_roster_does_not_verify_current_team(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()), \
             patch.object(m, "get_player_role_context_dataset", return_value=role_context()), \
             patch.object(m, "get_lineups_dataset", return_value=lineup_context()), \
             patch.object(m, "get_team_availability_context_dataset", return_value=availability_context(include_focal=False)):
            result = m.get_player_opportunity_context(PLAYER_ID, 2026)
        self.assertFalse(result["current_availability_context"]["current_roster_team_verified"])
        self.assertIsNone(result["current_availability_context"]["focal_player"])

    def test_availability_team_mismatch_fails_closed(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()), \
             patch.object(m, "get_player_role_context_dataset", return_value=role_context()), \
             patch.object(m, "get_lineups_dataset", return_value=lineup_context()), \
             patch.object(m, "get_team_availability_context_dataset", return_value=availability_context(team_key="seattle-storm")):
            with self.assertRaisesRegex(m.WNBAPlayerOpportunityUpstreamError, "unexpected team key"):
                m.get_player_opportunity_context(PLAYER_ID, 2026)

    def test_availability_not_found_fails_soft(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()), \
             patch.object(m, "get_player_role_context_dataset", return_value=role_context()), \
             patch.object(m, "get_lineups_dataset", return_value=lineup_context()), \
             patch.object(m, "get_team_availability_context_dataset", side_effect=m.WNBAAvailabilityNotFoundError("no report")):
            result = m.get_player_opportunity_context(PLAYER_ID, 2026)
        self.assertFalse(result["current_availability_context"]["available"])
        self.assertEqual(result["current_availability_context"]["error"], "no report")

    def test_core_latest_team_disagreement_fails_closed(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context(team_key="seattle-storm")):
            with self.assertRaisesRegex(m.WNBAPlayerOpportunityUpstreamError, "disagree"):
                m.get_player_opportunity_context(PLAYER_ID, 2026)

    def test_rotation_wrong_player_fails_closed(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context(player_id=999)), \
             patch.object(m, "get_player_recent_event_feature_context", return_value=event_context()):
            with self.assertRaisesRegex(m.WNBAPlayerOpportunityUpstreamError, "rotation player ID"):
                m.get_player_opportunity_context(PLAYER_ID, 2026)

    def test_rotation_not_found_is_translated(self):
        with patch.object(m, "get_player_recent_rotation_context", side_effect=m.WNBARotationNotFoundError("missing")):
            with self.assertRaises(m.WNBAPlayerOpportunityNotFoundError):
                m.get_player_opportunity_context(PLAYER_ID, 2026)

    def test_event_feature_not_found_is_translated(self):
        with patch.object(m, "get_player_recent_rotation_context", return_value=rotation_context()), \
             patch.object(m, "get_player_recent_event_feature_context", side_effect=m.WNBAPlayerEventFeatureNotFoundError("missing")):
            with self.assertRaises(m.WNBAPlayerOpportunityNotFoundError):
                m.get_player_opportunity_context(PLAYER_ID, 2026)

    def test_bad_inputs_fail_before_core_network_calls(self):
        with patch.object(m, "get_player_recent_rotation_context") as rotation:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                m.get_player_opportunity_context(0, 2026)
            with self.assertRaisesRegex(ValueError, "1 through 20"):
                m.get_player_opportunity_context(PLAYER_ID, 2026, last_n_games=21)
            with self.assertRaisesRegex(ValueError, "include_current_availability"):
                m.get_player_opportunity_context(PLAYER_ID, 2026, include_current_availability=1)
            rotation.assert_not_called()

    def test_guardrails_block_projection_and_opportunity_redistribution(self):
        result = self._run()
        guardrails = result["guardrails"]
        self.assertTrue(guardrails["no_projection_created"])
        self.assertTrue(guardrails["no_monte_carlo_created"])
        self.assertTrue(guardrails["no_missing_teammate_minutes_redistributed"])
        self.assertTrue(guardrails["injury_status_does_not_trigger_automatic_opportunity_redistribution"])
        self.assertTrue(guardrails["court_context_is_not_defender_assignment"])


if __name__ == "__main__":
    unittest.main()
