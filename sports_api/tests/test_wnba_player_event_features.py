import unittest
from copy import deepcopy
from unittest.mock import patch

from sports_api import wnba_player_event_features as m


GAME_ID = "1022600300"
HOME_ID = 1611661325
AWAY_ID = 1611661313
HOME_KEY = "indiana-fever"
AWAY_KEY = "new-york-liberty"


def _teams():
    return {
        "away": {
            "side": "away",
            "official_team_id": AWAY_ID,
            "team_key": AWAY_KEY,
            "team_full_name": "New York Liberty",
        },
        "home": {
            "side": "home",
            "official_team_id": HOME_ID,
            "team_key": HOME_KEY,
            "team_full_name": "Indiana Fever",
        },
    }


def _side(side, ids):
    team = _teams()[side]
    return {
        **team,
        "player_ids": list(ids),
        "players": [
            {
                "player_id": player_id,
                "player_name": f"Player {player_id}",
                "official_team_id": team["official_team_id"],
                "team_key": team["team_key"],
                "team_full_name": team["team_full_name"],
            }
            for player_id in ids
        ],
    }


def _selected(home_ids=(1, 2, 3, 4, 5), away_ids=(11, 12, 13, 14, 15)):
    return {
        "away": _side("away", away_ids),
        "home": _side("home", home_ids),
        "all_player_ids": list(away_ids) + list(home_ids),
        "exact_5v5": len(away_ids) == 5 and len(home_ids) == 5,
        "exact_ten_players": len(set(away_ids + home_ids)) == 10,
    }


def _event(
    index,
    category,
    *,
    side=None,
    actor=None,
    assist=None,
    block=None,
    sub_type=None,
    action_type=None,
    description=None,
    shot_result=None,
    points=0,
    scoring_side=None,
    selected=None,
    eligible=True,
):
    selected = selected or _selected()
    return {
        "source_index": index,
        "event_side": side,
        "event": {
            "action_number": index + 1,
            "action_id": str(index + 1),
            "event_category": category,
            "person_id": actor,
            "assist_person_id": assist,
            "block_person_id": block,
            "sub_type": sub_type,
            "action_type": action_type or category,
            "description": description,
            "shot_result": shot_result,
            "points_scored_on_action": points,
            "scoring_side": scoring_side,
        },
        "lineup_context": {
            "available": selected is not None,
            "selected": selected,
            "exact_5v5": bool(selected and selected.get("exact_5v5")),
            "eligible_for_player_event_features": eligible,
            "lineup_phase": "stable" if eligible else "ambiguous_boundary",
        },
    }


def _possession(number, indices, offense, points=0, complete=True):
    return {
        "possession_number": number,
        "classification": "derived_play_by_play_possession_segment",
        "offense_side": offense,
        "defense_side": "away" if offense == "home" else "home",
        "complete": complete,
        "points_scored_by_offense": points,
        "event_refs": [{"source_index": index} for index in indices],
    }


def _datasets(extra_events=None, extra_possessions=None):
    events = [
        _event(0, "shot", side="home", actor=1, assist=2, action_type="3pt", shot_result="Made", points=3, scoring_side="home"),
        _event(1, "shot", side="away", actor=11, block=1, shot_result="Missed"),
        _event(2, "rebound", side="away", actor=11, sub_type="Offensive"),
        _event(3, "turnover", side="home", actor=1),
        _event(4, "shot", side="home", actor=3, assist=1, action_type="2pt", shot_result="Made", points=2, scoring_side="home"),
        _event(5, "shot", side="away", actor=12, shot_result="Missed"),
        _event(6, "rebound", side="home", actor=4, sub_type="Defensive"),
    ]
    if extra_events:
        events.extend(extra_events)
    possessions = [
        _possession(1, [0], "home", 3),
        _possession(2, [1, 2], "away", 0),
        _possession(3, [3], "home", 0),
        _possession(4, [4], "home", 2),
        _possession(5, [5, 6], "away", 0),
    ]
    if extra_possessions:
        possessions.extend(extra_possessions)
    event_dataset = {
        "source": "step4t",
        "data_type": "official_pbp_with_observed_rotation_event_lineups",
        "game_id": GAME_ID,
        "source_action_count": len(events),
        "feature_eligible_event_count": sum(
            bool(row["lineup_context"]["eligible_for_player_event_features"])
            for row in events
        ),
        "teams": _teams(),
        "events": events,
    }
    possession_dataset = {
        "source": "step4t",
        "data_type": "derived_possession_segments_with_observed_event_lineups",
        "game_id": GAME_ID,
        "possession_count": len(possessions),
        "complete_possession_count": sum(bool(item["complete"]) for item in possessions),
        "teams": _teams(),
        "possessions": possessions,
    }
    return event_dataset, possession_dataset


def _targeted_game_feature(game_id=GAME_ID, team_key=HOME_KEY, opponent_key=AWAY_KEY, fga=2, eligible=10):
    counts = m._empty_counts()
    counts["field_goals_attempted"] = fga
    counts["field_goals_made"] = 1
    counts["points"] = 3
    team = m._empty_counts()
    team["field_goals_attempted"] = 5
    team["field_goals_made"] = 2
    team["points"] = 7
    opponent = m._empty_counts()
    opponent["field_goals_attempted"] = 4
    opponent["field_goals_made"] = 2
    opponent["points"] = 5
    feature = {
        "player": {"player_id": 1, "player_name": "Player 1", "side": "home"},
        "team": {"team_key": team_key},
        "opponent": {"team_key": opponent_key},
        "data_quality": {
            "selected_lineup_event_count": eligible + 2,
            "feature_eligible_event_count": eligible,
        },
        "own_event_counts": counts,
        "on_court_event_environment": {"team": team, "opponent": opponent},
        "co_presence": {
            "teammates": [{
                "player_id": 2,
                "player_name": "Player 2",
                "team_key": team_key,
                "shared_feature_eligible_event_count": eligible,
            }],
            "opponents": [{
                "player_id": 11,
                "player_name": "Player 11",
                "team_key": opponent_key,
                "shared_feature_eligible_event_count": eligible,
            }],
        },
        "derived_possession_exposure": {
            "stable_complete_segment_count": 4,
            "stable_incomplete_segment_count": 1,
            "stable_complete_offensive_segment_count": 2,
            "stable_complete_defensive_segment_count": 2,
            "unstable_player_presence_segment_count": 0,
            "player_present_but_lineup_ineligible_segment_count": 0,
            "offensive_points_in_stable_complete_segments": 3,
            "defensive_points_allowed_in_stable_complete_segments": 2,
        },
    }
    return {"game_id": game_id, "players": [feature]}


class WNBAPlayerEventFeatureTests(unittest.TestCase):
    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_game_player_features_build_own_stats_and_environment(self, event_lineups, possession_context):
        event_lineups.return_value, possession_context.return_value = _datasets()
        result = m.get_game_player_event_features(GAME_ID, 2026, player_id=1)
        self.assertEqual(result["player_count"], 1)
        player = result["players"][0]
        own = player["own_event_counts"]
        self.assertEqual(own["field_goals_attempted"], 1)
        self.assertEqual(own["field_goals_made"], 1)
        self.assertEqual(own["three_pointers_attempted"], 1)
        self.assertEqual(own["three_pointers_made"], 1)
        self.assertEqual(own["assists"], 1)
        self.assertEqual(own["turnovers"], 1)
        self.assertEqual(own["blocks"], 1)
        self.assertEqual(own["points"], 3)
        team = player["on_court_event_environment"]["team"]
        opponent = player["on_court_event_environment"]["opponent"]
        self.assertEqual(team["field_goals_attempted"], 2)
        self.assertEqual(team["field_goals_made"], 2)
        self.assertEqual(team["assists"], 2)
        self.assertEqual(team["turnovers"], 1)
        self.assertEqual(team["defensive_rebounds"], 1)
        self.assertEqual(team["points"], 5)
        self.assertEqual(opponent["field_goals_attempted"], 2)
        self.assertEqual(opponent["offensive_rebounds"], 1)
        self.assertAlmostEqual(
            player["on_court_event_environment"]["action_shares_of_team_events"]["field_goal_attempt_share"],
            .5,
        )

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_co_presence_is_event_count_not_minutes(self, event_lineups, possession_context):
        event_lineups.return_value, possession_context.return_value = _datasets()
        player = m.get_game_player_event_features(GAME_ID, 2026, player_id=1)["players"][0]
        teammate = next(row for row in player["co_presence"]["teammates"] if row["player_id"] == 2)
        opponent = next(row for row in player["co_presence"]["opponents"] if row["player_id"] == 11)
        self.assertEqual(teammate["shared_feature_eligible_event_count"], 7)
        self.assertEqual(opponent["shared_feature_eligible_event_count"], 7)
        self.assertEqual(teammate["share_of_focal_player_feature_eligible_events"], 1.0)
        self.assertIn("not shared minutes", player["co_presence"]["semantics"])

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_lineup_signature_counts_eligible_events(self, event_lineups, possession_context):
        event_lineups.return_value, possession_context.return_value = _datasets()
        player = m.get_game_player_event_features(GAME_ID, 2026, player_id=1)["players"][0]
        lineups = player["lineup_event_context"]["lineups"]
        self.assertEqual(len(lineups), 1)
        self.assertEqual(lineups[0]["feature_eligible_event_count"], 7)
        self.assertEqual(lineups[0]["own_team_player_ids"], [1, 2, 3, 4, 5])

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_possession_exposure_is_conservative_and_labeled_derived(self, event_lineups, possession_context):
        event_lineups.return_value, possession_context.return_value = _datasets()
        exposure = m.get_game_player_event_features(GAME_ID, 2026, player_id=1)["players"][0]["derived_possession_exposure"]
        self.assertEqual(exposure["stable_complete_segment_count"], 5)
        self.assertEqual(exposure["stable_complete_offensive_segment_count"], 3)
        self.assertEqual(exposure["stable_complete_defensive_segment_count"], 2)
        self.assertEqual(exposure["offensive_points_in_stable_complete_segments"], 5)
        self.assertAlmostEqual(exposure["offensive_points_per_100_stable_complete_segments"], 166.6667)
        self.assertTrue(exposure["guardrails"]["segments_are_derived_not_official_possessions"])

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_off_court_events_are_not_counted_for_player(self, event_lineups, possession_context):
        bench_lineup = _selected(home_ids=(2, 3, 4, 5, 6))
        extra = _event(7, "shot", side="home", actor=6, shot_result="Made", points=2, scoring_side="home", selected=bench_lineup)
        event_lineups.return_value, possession_context.return_value = _datasets(extra_events=[extra], extra_possessions=[_possession(6, [7], "home", 2)])
        player = m.get_game_player_event_features(GAME_ID, 2026, player_id=1)["players"][0]
        self.assertEqual(player["data_quality"]["selected_lineup_event_count"], 7)
        self.assertEqual(player["on_court_event_environment"]["team"]["field_goals_attempted"], 2)

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_ineligible_event_is_excluded_from_player_feature_counts(self, event_lineups, possession_context):
        bad = _event(7, "shot", side="home", actor=1, shot_result="Made", points=2, scoring_side="home", eligible=False)
        event_lineups.return_value, possession_context.return_value = _datasets(extra_events=[bad], extra_possessions=[_possession(6, [7], "home", 2)])
        player = m.get_game_player_event_features(GAME_ID, 2026, player_id=1)["players"][0]
        self.assertEqual(player["data_quality"]["selected_lineup_event_count"], 8)
        self.assertEqual(player["data_quality"]["feature_eligible_event_count"], 7)
        self.assertEqual(player["own_event_counts"]["field_goals_attempted"], 1)
        self.assertEqual(player["derived_possession_exposure"]["player_present_but_lineup_ineligible_segment_count"], 1)

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_mid_segment_substitution_is_not_counted_as_stable_possession(self, event_lineups, possession_context):
        bench_lineup = _selected(home_ids=(2, 3, 4, 5, 6))
        extra = _event(7, "shot", side="away", actor=13, shot_result="Missed", selected=bench_lineup)
        event_lineups.return_value, possession_context.return_value = _datasets(
            extra_events=[extra],
            extra_possessions=[_possession(6, [6, 7], "away", 0)],
        )
        exposure = m.get_game_player_event_features(GAME_ID, 2026, player_id=1)["players"][0]["derived_possession_exposure"]
        self.assertEqual(exposure["unstable_player_presence_segment_count"], 1)
        self.assertEqual(exposure["stable_complete_segment_count"], 5)

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_incomplete_segment_is_separated_from_complete_rates(self, event_lineups, possession_context):
        event_lineups.return_value, possession_context.return_value = _datasets(
            extra_possessions=[_possession(6, [6], "home", 0, complete=False)]
        )
        exposure = m.get_game_player_event_features(GAME_ID, 2026, player_id=1)["players"][0]["derived_possession_exposure"]
        self.assertEqual(exposure["stable_incomplete_segment_count"], 1)
        self.assertEqual(exposure["stable_complete_segment_count"], 5)

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_all_player_mode_returns_both_teams(self, event_lineups, possession_context):
        event_lineups.return_value, possession_context.return_value = _datasets()
        result = m.get_game_player_event_features(GAME_ID, 2026)
        self.assertEqual(result["player_count"], 10)
        self.assertEqual({row["player"]["side"] for row in result["players"]}, {"away", "home"})

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_missing_target_player_is_not_found(self, event_lineups, possession_context):
        event_lineups.return_value, possession_context.return_value = _datasets()
        with self.assertRaises(m.WNBAPlayerEventFeatureNotFoundError):
            m.get_game_player_event_features(GAME_ID, 2026, player_id=999)

    def test_invalid_game_and_player_ids_fail_before_step4t_calls(self):
        with patch("sports_api.wnba_player_event_features.get_game_event_lineups") as event_lineups:
            with self.assertRaisesRegex(ValueError, "10 numeric digits"):
                m.get_game_player_event_features("123", 2026, player_id=1)
            with self.assertRaisesRegex(ValueError, "positive integer"):
                m.get_game_player_event_features(GAME_ID, 2026, player_id=0)
            event_lineups.assert_not_called()

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_step4t_team_disagreement_fails_closed(self, event_lineups, possession_context):
        events, possessions = _datasets()
        possessions = deepcopy(possessions)
        possessions["teams"]["home"]["team_key"] = "wrong-team"
        event_lineups.return_value = events
        possession_context.return_value = possessions
        with self.assertRaisesRegex(m.WNBAPlayerEventFeatureUpstreamError, "team identities"):
            m.get_game_player_event_features(GAME_ID, 2026, player_id=1)

    @patch("sports_api.wnba_player_event_features.get_game_player_event_features")
    @patch("sports_api.wnba_player_event_features.get_player_game_log_dataset")
    def test_recent_context_aggregates_games_and_co_presence(self, history, game_features):
        history.return_value = {
            "games": [
                {"game_id": GAME_ID, "game_date": "2026-08-26", "matchup": {"team_key": HOME_KEY, "opponent_team_key": AWAY_KEY}},
                {"game_id": "1022600299", "game_date": "2026-08-24", "matchup": {"team_key": HOME_KEY, "opponent_team_key": AWAY_KEY}},
            ]
        }
        game_features.side_effect = [
            _targeted_game_feature(GAME_ID, fga=2, eligible=10),
            _targeted_game_feature("1022600299", fga=3, eligible=8),
        ]
        result = m.get_player_recent_event_feature_context(1, 2026, last_n_games=2)
        self.assertEqual(result["feature_game_count"], 2)
        self.assertEqual(result["aggregate"]["own_event_counts"]["field_goals_attempted"], 5)
        self.assertEqual(result["aggregate"]["data_quality"]["feature_eligible_event_count"], 18)
        teammate = result["aggregate"]["co_presence"]["teammates"][0]
        self.assertEqual(teammate["player_id"], 2)
        self.assertEqual(teammate["shared_feature_eligible_event_count"], 18)
        self.assertEqual(teammate["games_observed_together"], 2)
        exposure = result["aggregate"]["derived_possession_exposure"]
        self.assertEqual(exposure["stable_complete_offensive_segment_count"], 4)
        self.assertEqual(exposure["offensive_points_in_stable_complete_segments"], 6)
        self.assertEqual(exposure["offensive_points_per_100_stable_complete_segments"], 150.0)

    @patch("sports_api.wnba_player_event_features.get_game_player_event_features")
    @patch("sports_api.wnba_player_event_features.get_player_game_log_dataset")
    def test_recent_missing_feature_game_is_reported(self, history, game_features):
        history.return_value = {
            "games": [
                {"game_id": GAME_ID, "game_date": "2026-08-26", "matchup": {"team_key": HOME_KEY, "opponent_team_key": AWAY_KEY}},
                {"game_id": "1022600299", "game_date": "2026-08-24", "matchup": {"team_key": HOME_KEY, "opponent_team_key": AWAY_KEY}},
            ]
        }
        game_features.side_effect = [
            _targeted_game_feature(GAME_ID),
            m.WNBAPlayerEventFeatureNotFoundError("missing"),
        ]
        result = m.get_player_recent_event_feature_context(1, 2026, last_n_games=2)
        self.assertEqual(result["feature_game_count"], 1)
        self.assertEqual(result["missing_feature_game_ids"], ["1022600299"])

    @patch("sports_api.wnba_player_event_features.get_game_player_event_features")
    @patch("sports_api.wnba_player_event_features.get_player_game_log_dataset")
    def test_recent_team_identity_mismatch_fails_closed(self, history, game_features):
        history.return_value = {
            "games": [{
                "game_id": GAME_ID,
                "game_date": "2026-08-26",
                "matchup": {"team_key": HOME_KEY, "opponent_team_key": AWAY_KEY},
            }]
        }
        game_features.return_value = _targeted_game_feature(GAME_ID, team_key="wrong-team")
        with self.assertRaisesRegex(m.WNBAPlayerEventFeatureUpstreamError, "team identity"):
            m.get_player_recent_event_feature_context(1, 2026)

    def test_recent_validation_fails_before_history_network(self):
        with patch("sports_api.wnba_player_event_features.get_player_game_log_dataset") as history:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                m.get_player_recent_event_feature_context(0, 2026)
            with self.assertRaisesRegex(ValueError, "1 through 20"):
                m.get_player_recent_event_feature_context(1, 2026, last_n_games=21)
            with self.assertRaisesRegex(ValueError, "season_type"):
                m.get_player_recent_event_feature_context(1, 2026, season_type="BAD")
            history.assert_not_called()

    @patch("sports_api.wnba_player_event_features.get_game_possession_event_context")
    @patch("sports_api.wnba_player_event_features.get_game_event_lineups")
    def test_guardrails_forbid_projection_usage_and_defender_claims(self, event_lineups, possession_context):
        event_lineups.return_value, possession_context.return_value = _datasets()
        player = m.get_game_player_event_features(GAME_ID, 2026, player_id=1)["players"][0]
        self.assertTrue(player["guardrails"]["features_are_observed_descriptive_inputs_not_projections"])
        self.assertTrue(player["guardrails"]["action_shares_are_not_official_usage_percentage"])
        self.assertTrue(player["guardrails"]["court_context_is_not_defender_assignment"])
        self.assertTrue(player["guardrails"]["no_projection_created"])
        self.assertTrue(player["guardrails"]["no_betting_probability_created"])


if __name__ == "__main__":
    unittest.main()
