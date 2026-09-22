import unittest
from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import patch

from sports_api import wnba_projection_input_snapshot as m


GAME_ID = "1022600284"
PLAYER_ID = 101
HOME = "connecticut-sun"
AWAY = "chicago-sky"
DATE = "2026-08-26"


def opportunity(team_key=HOME, player_id=PLAYER_ID):
    return {
        "source": "4V",
        "data_type": "observed_player_opportunity_and_role_features",
        "season": 2026,
        "player_id": player_id,
        "latest_observed_team_key": team_key,
        "guardrails": {"no_projection_created": True},
    }


def rest(game_id=GAME_ID, away=AWAY, home=HOME):
    return {
        "source": "WNBA official schedule",
        "data_type": "wnba_game_rest_travel_context",
        "season": 2026,
        "game": {
            "game_id": game_id,
            "date": DATE,
            "game_datetime_utc": "2026-08-26T23:00:00+00:00",
            "game_datetime_eastern": "2026-08-26T19:00:00-04:00",
            "venue": {"name": "Example Arena"},
            "status": {"category": "scheduled"},
            "schedule_change": {},
        },
        "away_team_key": away,
        "home_team_key": home,
        "away_context": {"team": {"team_key": away}},
        "home_context": {"team": {"team_key": home}},
    }


def availability(include_focal=True, away=AWAY, home=HOME, game_id=GAME_ID):
    home_players = [
        {
            "player_id": PLAYER_ID,
            "player_name": "Focal Player",
            "injury_report_status": "Available",
            "availability_class": "available",
        }
    ] if include_focal else []
    return {
        "source": "game availability",
        "game_id": game_id,
        "date": DATE,
        "away": {"team_key": away, "players": []},
        "home": {"team_key": home, "players": home_players},
        "injury_report": {
            "report_timestamp_eastern": "2026-08-26T17:00:00-04:00",
            "retrieved_at_utc": "2026-08-26T21:00:01+00:00",
        },
        "starting_lineups": {"official_starters_confirmed": False},
        "verification": {"injury_report_submission_complete": True},
    }


def player_shot(player_id=PLAYER_ID):
    return {
        "source": "shot chart",
        "player_id": player_id,
        "retrieved_at_utc": "2026-08-26T21:00:02+00:00",
    }


def player_vs_opponent_shot(player_id=PLAYER_ID):
    return {
        "source": "shot chart",
        "player_id": player_id,
        "filters": {"opponent_team_key": AWAY},
    }


def zone_defense(team_key=AWAY):
    return {"source": "zone defense", "team_key": team_key}


def player_advanced(player_id=PLAYER_ID):
    return {"source": "advanced", "filters": {"player_id": player_id}}


def team_advanced(team_key):
    return {"source": "advanced", "filters": {"team_key": team_key}}


def whistle(game_id=GAME_ID):
    return {"source": "whistle", "game_id": game_id}


def matchup_status():
    return {
        "source": "4S",
        "official_player_defender_matchup_data_available": False,
        "shared_court_time_is_not_defender_time": True,
    }


class WNBAProjectionInputSnapshotTests(unittest.TestCase):
    DEFAULTS = {
        "get_player_opportunity_context": opportunity(),
        "get_game_rest_travel_context": rest(),
        "get_game_availability_context_dataset": availability(),
        "get_player_shot_chart_dataset": [player_shot(), player_vs_opponent_shot()],
        "get_opponent_defense_by_shot_zone_dataset": zone_defense(),
        "get_player_advanced_stats_dataset": player_advanced(),
        "get_team_advanced_stats_dataset": [team_advanced(HOME), team_advanced(AWAY)],
        "get_game_whistle_context": whistle(),
        "get_matchup_source_status": matchup_status(),
    }

    def _call(self, *, overrides=None, call_kwargs=None, timestamps=None):
        overrides = overrides or {}
        call_kwargs = call_kwargs or {}
        mocks = {}
        with ExitStack() as stack:
            for name, default in self.DEFAULTS.items():
                mock = stack.enter_context(
                    patch(f"sports_api.wnba_projection_input_snapshot.{name}")
                )
                value = overrides.get(name, default)
                if isinstance(value, BaseException):
                    mock.side_effect = value
                elif isinstance(value, list):
                    mock.side_effect = deepcopy(value)
                else:
                    mock.return_value = deepcopy(value)
                mocks[name] = mock
            if timestamps is not None:
                clock = stack.enter_context(
                    patch("sports_api.wnba_projection_input_snapshot._utc_now_iso")
                )
                if isinstance(timestamps, list):
                    clock.side_effect = timestamps
                else:
                    clock.return_value = timestamps
            result = m.get_player_game_projection_input_snapshot(
                PLAYER_ID,
                GAME_ID,
                2026,
                **call_kwargs,
            )
            return result, mocks

    def test_builds_home_player_game_identity_and_opponent(self):
        result, _ = self._call()
        self.assertEqual(result["game_id"], GAME_ID)
        self.assertEqual(result["player_id"], PLAYER_ID)
        self.assertEqual(result["focal_identity"]["team_key"], HOME)
        self.assertEqual(result["focal_identity"]["side"], "home")
        self.assertEqual(result["focal_identity"]["opponent_team_key"], AWAY)
        self.assertEqual(result["game_identity"]["date"], DATE)

    def test_builds_away_player_identity(self):
        result, _ = self._call(
            overrides={"get_player_opportunity_context": opportunity(AWAY)}
        )
        self.assertEqual(result["focal_identity"]["side"], "away")
        self.assertEqual(result["focal_identity"]["opponent_team_key"], HOME)

    def test_player_latest_team_must_be_in_requested_game(self):
        with self.assertRaisesRegex(
            m.WNBAProjectionInputSnapshotNotFoundError,
            "is not in WNBA game",
        ):
            self._call(
                overrides={
                    "get_player_opportunity_context": opportunity("seattle-storm")
                }
            )

    def test_wrong_player_from_step_4v_fails_closed(self):
        with self.assertRaisesRegex(
            m.WNBAProjectionInputSnapshotUpstreamError,
            "wrong player ID",
        ):
            self._call(
                overrides={"get_player_opportunity_context": opportunity(player_id=999)}
            )

    def test_wrong_game_from_step_4n_fails_closed(self):
        with self.assertRaisesRegex(
            m.WNBAProjectionInputSnapshotUpstreamError,
            "wrong game ID",
        ):
            self._call(
                overrides={"get_game_rest_travel_context": rest(game_id="1022600999")}
            )

    def test_availability_must_match_schedule_teams(self):
        bad = availability(away="seattle-storm")
        with self.assertRaisesRegex(
            m.WNBAProjectionInputSnapshotUpstreamError,
            "teams disagree",
        ):
            self._call(overrides={"get_game_availability_context_dataset": bad})

    def test_availability_summary_identifies_focal_current_roster_row(self):
        result, _ = self._call()
        summary = result["availability_summary"]
        self.assertTrue(summary["focal_player_current_roster_match"])
        self.assertEqual(summary["focal_player_availability"]["player_id"], PLAYER_ID)
        self.assertTrue(summary["verification"]["injury_report_submission_complete"])

    def test_missing_focal_current_roster_row_is_exposed_not_fabricated(self):
        result, _ = self._call(
            overrides={"get_game_availability_context_dataset": availability(False)}
        )
        self.assertFalse(result["availability_summary"]["focal_player_current_roster_match"])
        self.assertIsNone(result["availability_summary"]["focal_player_availability"])

    def test_availability_not_found_fails_soft(self):
        result, _ = self._call(
            overrides={
                "get_game_availability_context_dataset": m.WNBAAvailabilityNotFoundError(
                    "report unavailable"
                )
            }
        )
        status = result["component_status"]["game_availability"]
        self.assertFalse(status["available"])
        self.assertIn("report unavailable", status["error"])
        self.assertNotIn("game_availability", result["inputs"])
        self.assertIsNone(result["availability_summary"])

    def test_shot_source_failure_fails_soft_without_fake_value(self):
        result, _ = self._call(
            overrides={
                "get_player_shot_chart_dataset": [
                    m.WNBAShotContextNotFoundError("no recent chart"),
                    player_vs_opponent_shot(),
                ]
            }
        )
        self.assertFalse(result["component_status"]["player_recent_shot_chart"]["available"])
        self.assertNotIn("player_recent_shot_chart", result["inputs"])
        self.assertIn("player_vs_opponent_shot_chart", result["inputs"])

    def test_advanced_source_failure_fails_soft(self):
        result, _ = self._call(
            overrides={
                "get_player_advanced_stats_dataset": m.WNBAAdvancedStatsUpstreamError(
                    "advanced down"
                )
            }
        )
        self.assertFalse(result["component_status"]["player_advanced"]["available"])
        self.assertNotIn("player_advanced", result["inputs"])

    def test_returned_optional_player_identity_is_checked(self):
        with self.assertRaisesRegex(
            m.WNBAProjectionInputSnapshotUpstreamError,
            "wrong player ID",
        ):
            self._call(
                overrides={
                    "get_player_shot_chart_dataset": [
                        player_shot(999),
                        player_vs_opponent_shot(),
                    ]
                }
            )

    def test_returned_optional_team_identity_is_checked(self):
        with self.assertRaisesRegex(
            m.WNBAProjectionInputSnapshotUpstreamError,
            "conflicting team identity",
        ):
            self._call(
                overrides={
                    "get_opponent_defense_by_shot_zone_dataset": zone_defense(HOME)
                }
            )

    def test_step_4v_is_called_without_its_own_availability_fetch(self):
        _, mocks = self._call()
        mocks["get_player_opportunity_context"].assert_called_once_with(
            PLAYER_ID,
            2026,
            season_type="Regular Season",
            last_n_games=5,
            include_current_availability=False,
        )

    def test_shot_context_uses_current_opponent_from_official_game(self):
        _, mocks = self._call()
        calls = mocks["get_player_shot_chart_dataset"].call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].kwargs["last_n_games"], 5)
        self.assertNotIn("opponent_team_key", calls[0].kwargs)
        self.assertEqual(calls[1].kwargs["last_n_games"], 0)
        self.assertEqual(calls[1].kwargs["opponent_team_key"], AWAY)
        mocks["get_opponent_defense_by_shot_zone_dataset"].assert_called_once_with(
            AWAY,
            2026,
            season_type="Regular Season",
            last_n_games=5,
        )

    def test_optional_flags_prevent_optional_network_calls(self):
        result, mocks = self._call(
            call_kwargs={
                "include_current_availability": False,
                "include_shot_context": False,
                "include_advanced_context": False,
                "include_officiating_context": False,
            }
        )
        mocks["get_game_availability_context_dataset"].assert_not_called()
        mocks["get_player_shot_chart_dataset"].assert_not_called()
        mocks["get_opponent_defense_by_shot_zone_dataset"].assert_not_called()
        mocks["get_player_advanced_stats_dataset"].assert_not_called()
        mocks["get_team_advanced_stats_dataset"].assert_not_called()
        mocks["get_game_whistle_context"].assert_not_called()
        self.assertFalse(result["component_status"]["game_availability"]["requested"])
        self.assertFalse(result["component_status"]["player_advanced"]["requested"])

    def test_content_hash_is_independent_of_capture_clock(self):
        first, _ = self._call(
            timestamps=[
                "2026-08-26T16:00:00+00:00",
                "2026-08-26T16:00:01+00:00",
            ]
        )
        second, _ = self._call(
            timestamps=[
                "2026-08-26T17:00:00+00:00",
                "2026-08-26T17:00:01+00:00",
            ]
        )
        self.assertEqual(first["content_sha256"], second["content_sha256"])
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertNotEqual(first["captured_at_utc"], second["captured_at_utc"])

    def test_content_hash_changes_when_captured_input_changes(self):
        first, _ = self._call()
        changed = player_advanced()
        changed["players"] = [{"player_id": PLAYER_ID, "usage": 0.25}]
        second, _ = self._call(
            overrides={"get_player_advanced_stats_dataset": changed}
        )
        self.assertNotEqual(first["content_sha256"], second["content_sha256"])
        self.assertNotEqual(first["snapshot_id"], second["snapshot_id"])

    def test_matchup_source_guardrail_is_carried_into_snapshot(self):
        result, _ = self._call()
        self.assertFalse(
            result["inputs"]["matchup_source_status"][
                "official_player_defender_matchup_data_available"
            ]
        )
        self.assertTrue(
            result["guardrails"][
                "official_wnba_player_defender_assignment_remains_unavailable"
            ]
        )

    def test_required_opportunity_not_found_is_translated(self):
        with self.assertRaises(m.WNBAProjectionInputSnapshotNotFoundError):
            self._call(
                overrides={
                    "get_player_opportunity_context": m.WNBAPlayerOpportunityNotFoundError(
                        "no opportunity"
                    )
                }
            )

    def test_required_schedule_not_found_is_translated(self):
        with self.assertRaises(m.WNBAProjectionInputSnapshotNotFoundError):
            self._call(
                overrides={
                    "get_game_rest_travel_context": m.WNBARestTravelNotFoundError(
                        "no game"
                    )
                }
            )

    def test_invalid_inputs_fail_before_network(self):
        with patch(
            "sports_api.wnba_projection_input_snapshot.get_player_opportunity_context"
        ) as opportunity_mock:
            with self.assertRaisesRegex(ValueError, "positive integer"):
                m.get_player_game_projection_input_snapshot(0, GAME_ID, 2026)
            with self.assertRaisesRegex(ValueError, "10 numeric digits"):
                m.get_player_game_projection_input_snapshot(PLAYER_ID, "123", 2026)
            with self.assertRaisesRegex(ValueError, "1 through 20"):
                m.get_player_game_projection_input_snapshot(
                    PLAYER_ID, GAME_ID, 2026, last_n_games=21
                )
            with self.assertRaisesRegex(ValueError, "must be boolean"):
                m.get_player_game_projection_input_snapshot(
                    PLAYER_ID,
                    GAME_ID,
                    2026,
                    include_shot_context=1,
                )
            opportunity_mock.assert_not_called()

    def test_component_summary_reports_requested_availability(self):
        result, _ = self._call(
            overrides={
                "get_game_whistle_context": m.WNBAOfficiatingNotFoundError(
                    "officials not assigned"
                )
            }
        )
        summary = result["component_status_summary"]
        self.assertEqual(summary["requested_component_count"], 8)
        self.assertEqual(summary["unavailable_component_count"], 1)
        self.assertIn("game_whistle_context", summary["unavailable_components"])
        self.assertFalse(summary["all_requested_optional_components_available"])

    def test_snapshot_has_no_projection_monte_carlo_or_betting_outputs(self):
        result, _ = self._call()
        guardrails = result["guardrails"]
        self.assertTrue(guardrails["snapshot_is_pre_model_input_not_projection"])
        self.assertTrue(guardrails["no_projected_minutes_created"])
        self.assertTrue(guardrails["no_projected_starters_created"])
        self.assertTrue(guardrails["no_monte_carlo_created"])
        self.assertTrue(guardrails["no_sportsbook_data_created"])
        self.assertTrue(guardrails["no_betting_probability_created"])
        self.assertFalse(result["snapshot_semantics"]["persisted_to_database"])


if __name__ == "__main__":
    unittest.main()
