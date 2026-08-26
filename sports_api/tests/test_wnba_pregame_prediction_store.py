import copy
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import sports_api.wnba_historical_backtest_calibration as h
import sports_api.database.wnba_pregame_prediction_store as s
import sports_api.api.wnba_pregame_prediction_store as api

SECRET = "s" * 32
TIP = datetime(2026, 8, 26, 23, 0, tzinfo=timezone.utc)


def snap(*, side="away", role="mostly_starter", rest=1, b2b=False):
    team, opp = "SEA", "PHX"
    value = {
        "schema_version": "wnba_step_4w_v1",
        "season": 2026,
        "season_type": "Regular Season",
        "game_id": "1022600001",
        "player_id": 123,
        "recent_window_games": 5,
        "game_identity": {
            "game_id": "1022600001",
            "date": "2026-08-26",
            "away_team_key": team if side == "away" else opp,
            "home_team_key": team if side == "home" else opp,
            "game_datetime_utc": TIP.isoformat(),
            "game_datetime_eastern": None,
            "venue": None,
            "status": None,
            "schedule_change": None,
        },
        "focal_identity": {
            "player_id": 123,
            "team_key": team,
            "side": side,
            "opponent_team_key": opp,
        },
        "component_status": {},
        "inputs": {
            "player_opportunity_context": {
                "observed_role_context": {"observed_role_band": role}
            },
            "game_rest_travel_context": {
                f"{side}_context": {
                    "rest": {
                        "full_rest_days_before_date": rest,
                        "is_second_night_of_back_to_back": b2b,
                        "back_to_back_position": "second" if b2b else "none",
                    },
                    "road_trip": {"road_trip_game_number": 2},
                }
            },
        },
        "captured_at_utc": (TIP - timedelta(hours=2)).isoformat(),
        "finalized_at_utc": (TIP - timedelta(hours=1, minutes=59)).isoformat(),
        "snapshot_id": "snap-1",
    }
    content = {k: value[k] for k in (
        "schema_version", "season", "season_type", "game_id", "player_id",
        "recent_window_games", "game_identity", "focal_identity",
        "component_status", "inputs",
    )}
    value["content_sha256"] = h._canonical_hash(content)
    return value


def scenario(name, stat, line, mean, probability):
    return {
        "conditional_scenario": name,
        "stat": stat,
        "line": line,
        "raw_probabilities": {
            "over": {"probability": probability},
            "under": {"probability": 1 - probability},
            "push": {"probability": 0.0},
        },
        "fair_odds": {
            "over": {"available": True, "fair_probability": probability},
            "under": {"available": True, "fair_probability": 1 - probability},
        },
        "source_distribution_summary": {"mean": mean},
    }


def threshold(snapshot=None, *, stat="points", line=19.5, probability=.60):
    snapshot = snapshot or snap()
    means = {
        "points": (16., 20., 24.),
        "rebounds": (5., 7., 9.),
        "assists": (3., 5., 7.),
        "pra": (25., 32., 39.),
    }[stat]
    probabilities = (max(.01, probability - .20), probability, min(.99, probability + .18))
    results = {
        name: scenario(name, stat, line, means[index], probabilities[index])
        for index, name in enumerate(("low", "base", "high"))
    }
    value = {
        "model_version": h.THRESHOLD_MODEL_VERSION,
        "player_id": 123,
        "game_id": "1022600001",
        "team_key": "SEA",
        "opponent_team_key": "PHX",
        "season": 2026,
        "season_type": "Regular Season",
        "generated_at_utc": (TIP - timedelta(hours=1, minutes=30)).isoformat(),
        "prop": {"stat": stat, "line": line},
        "conditional_scenario_results": results,
        "primary_result": copy.deepcopy(results["base"]),
        "scenario_sensitivity": {"fixture": True},
        "model_config": {"fixture": True},
        "step_5e_reference": {"simulation_fingerprint_sha256": "a" * 64},
        "snapshot_reference": {
            k: snapshot[k] for k in (
                "snapshot_id", "content_sha256", "captured_at_utc",
                "finalized_at_utc", "season", "season_type", "game_id",
                "player_id", "recent_window_games",
            )
        },
        "probability_id": "prob-1",
    }
    value["probability_fingerprint_sha256"] = h._canonical_hash({
        "step_5e_simulation_fingerprint_sha256": "a" * 64,
        "model_config": value["model_config"],
        "conditional_threshold_results": results,
        "scenario_sensitivity": value["scenario_sensitivity"],
    })
    return value


def game_log(*, pts=22, reb=7, ast=5, minutes=32.5):
    return {
        "player_id": 123,
        "season": 2026,
        "season_type": "Regular Season",
        "games": [{
            "game_id": "1022600001",
            "game_date": "2026-08-26",
            "minutes": minutes,
            "points": pts,
            "rebounds": reb,
            "assists": ast,
            "result": "W",
            "matchup": {"team_key": "SEA", "opponent_team_key": "PHX"},
        }],
    }


def archive(*, stat="points", line=19.5, probability=.60,
            archived_at=TIP - timedelta(hours=1), snapshot=None):
    snapshot = snapshot or snap()
    return h.build_pregame_archive_envelope(
        threshold(snapshot, stat=stat, line=line, probability=probability),
        snapshot,
        archived_at_utc=archived_at,
        signing_secret=SECRET,
    )


def observation(*, stat="points", line=19.5, probability=.60,
                pts=22, reb=7, ast=5, source_archive=None):
    source_archive = source_archive or archive(stat=stat, line=line, probability=probability)
    return h.grade_archived_prediction(
        source_archive,
        game_log(pts=pts, reb=reb, ast=ast),
        signing_secret=SECRET,
    )


class Step5JDurableStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "step5j.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def persist_archive(self, value=None):
        value = value or archive()
        return s.persist_pregame_archive(value, db_path=self.db, signing_secret=SECRET)

    def persist_observation(self, source_archive=None, **kwargs):
        source_archive = source_archive or archive(**{k:v for k,v in kwargs.items() if k in {"stat","line","probability"}})
        self.persist_archive(source_archive)
        value = observation(source_archive=source_archive, **kwargs)
        return s.persist_graded_observation(value, db_path=self.db), value

    def test_01_initialize_store(self):
        result = s.initialize_store(self.db)
        self.assertTrue(self.db.exists())
        self.assertEqual(result["schema_version"], s.STORE_SCHEMA_VERSION)

    def test_02_explicit_store_path_reported(self):
        result = s.initialize_store(self.db)
        self.assertTrue(result["persistent_path_explicitly_configured"])

    def test_03_directory_path_rejected(self):
        with self.assertRaises(s.WNBAPregameStoreError):
            s.resolve_store_path(self.temp.name)

    def test_04_signed_archive_persists(self):
        result = self.persist_archive()
        self.assertTrue(result["stored"])
        self.assertTrue(result["signature_verified"])

    def test_05_exact_archive_replay_is_idempotent(self):
        value = archive()
        self.persist_archive(value)
        replay = self.persist_archive(value)
        self.assertFalse(replay["stored"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertFalse(replay["logical_idempotent_replay"])

    def test_06_logical_retry_first_write_wins(self):
        first = archive(archived_at=TIP - timedelta(hours=1, minutes=10))
        second = archive(archived_at=TIP - timedelta(hours=1))
        stored = self.persist_archive(first)
        replay = self.persist_archive(second)
        self.assertFalse(replay["stored"])
        self.assertTrue(replay["logical_idempotent_replay"])
        self.assertEqual(replay["archive_id"], stored["archive_id"])
        self.assertNotEqual(replay["request_archive_id"], stored["archive_id"])

    def test_07_archive_and_persist_returns_durable_first_record(self):
        snapshot = snap()
        prediction = threshold(snapshot)
        first = s.archive_and_persist_prediction(
            prediction, snapshot, db_path=self.db,
            archived_at_utc=TIP - timedelta(hours=1, minutes=10), signing_secret=SECRET,
        )
        second = s.archive_and_persist_prediction(
            prediction, snapshot, db_path=self.db,
            archived_at_utc=TIP - timedelta(hours=1), signing_secret=SECRET,
        )
        self.assertEqual(first["archive"]["archive_id"], second["archive"]["archive_id"])

    def test_08_wrong_signature_secret_rejected(self):
        with self.assertRaises(h.WNBAHistoricalBacktestUpstreamError):
            s.persist_pregame_archive(archive(), db_path=self.db, signing_secret="z" * 32)

    def test_09_unsigned_archive_rejected(self):
        snapshot = snap()
        with patch.dict(os.environ, {}, clear=True):
            unsigned = h.build_pregame_archive_envelope(
                threshold(snapshot), snapshot,
                archived_at_utc=TIP - timedelta(hours=1), signing_secret=None,
            )
            with self.assertRaises(h.WNBAHistoricalBacktestNotReadyError):
                s.persist_pregame_archive(unsigned, db_path=self.db, signing_secret=None)

    def test_10_archive_rows_are_update_immutable(self):
        self.persist_archive()
        conn = sqlite3.connect(self.db)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE wnba_pregame_archives SET team_key='X'")
        conn.close()

    def test_11_archive_rows_are_delete_immutable(self):
        self.persist_archive()
        conn = sqlite3.connect(self.db)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM wnba_pregame_archives")
        conn.close()

    def test_12_get_stored_archive(self):
        value = archive()
        self.persist_archive(value)
        loaded = s.get_stored_archive(value["archive_id"], db_path=self.db)
        self.assertEqual(loaded["content_sha256"], value["content_sha256"])

    def test_13_unknown_stored_archive(self):
        with self.assertRaises(s.WNBAPregameStoreError):
            s.get_stored_archive("missing", db_path=self.db)

    def test_14_observation_requires_archive(self):
        with self.assertRaises(s.WNBAPregameStoreConflictError):
            s.persist_graded_observation(observation(), db_path=self.db)

    def test_15_observation_persists(self):
        result, _ = self.persist_observation()
        self.assertTrue(result["stored"])

    def test_16_observation_replay_is_idempotent(self):
        source = archive()
        self.persist_archive(source)
        value = observation(source_archive=source)
        s.persist_graded_observation(value, db_path=self.db)
        replay = s.persist_graded_observation(value, db_path=self.db)
        self.assertFalse(replay["stored"])
        self.assertTrue(replay["idempotent_replay"])

    def test_17_conflicting_second_observation_rejected(self):
        source = archive()
        self.persist_archive(source)
        first = observation(source_archive=source, pts=22)
        second = observation(source_archive=source, pts=24)
        s.persist_graded_observation(first, db_path=self.db)
        with self.assertRaises(s.WNBAPregameStoreConflictError):
            s.persist_graded_observation(second, db_path=self.db)

    def test_18_observation_rows_are_update_immutable(self):
        self.persist_observation()
        conn = sqlite3.connect(self.db)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE wnba_backtest_observations SET settlement='under'")
        conn.close()

    def test_19_observation_rows_are_delete_immutable(self):
        self.persist_observation()
        conn = sqlite3.connect(self.db)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM wnba_backtest_observations")
        conn.close()

    def test_20_pending_only_after_official_tip(self):
        self.persist_archive()
        before = s.list_pending_archives(db_path=self.db, now_utc=TIP - timedelta(minutes=1))
        after = s.list_pending_archives(db_path=self.db, now_utc=TIP + timedelta(minutes=1))
        self.assertEqual(before, [])
        self.assertEqual(len(after), 1)

    def test_21_pending_limit_validation(self):
        with self.assertRaises(ValueError):
            s.list_pending_archives(db_path=self.db, limit=0)
        with self.assertRaises(ValueError):
            s.list_pending_archives(db_path=self.db, limit=s.MAX_SWEEP_LIMIT + 1)

    def test_22_grading_sweep_success(self):
        source = archive()
        self.persist_archive(source)
        def grader(value, **_):
            return observation(source_archive=value)
        result = s.grade_pending_archives(
            db_path=self.db, signing_secret=SECRET,
            now_utc=TIP + timedelta(hours=1), grader=grader,
        )
        self.assertEqual(result["counts"]["graded"], 1)
        self.assertEqual(s.get_store_status(db_path=self.db)["counts"]["graded_observations"], 1)

    def test_23_not_found_remains_pending(self):
        self.persist_archive()
        def grader(*_, **__):
            raise h.WNBAHistoricalBacktestNotFoundError("official result not available")
        result = s.grade_pending_archives(db_path=self.db, now_utc=TIP + timedelta(hours=1), grader=grader)
        self.assertEqual(result["counts"]["not_found"], 1)
        self.assertEqual(len(s.list_pending_archives(db_path=self.db, now_utc=TIP + timedelta(hours=1))), 1)

    def test_24_not_ready_remains_pending(self):
        self.persist_archive()
        def grader(*_, **__):
            raise h.WNBAHistoricalBacktestNotReadyError("not final")
        result = s.grade_pending_archives(db_path=self.db, now_utc=TIP + timedelta(hours=1), grader=grader)
        self.assertEqual(result["counts"]["not_ready"], 1)

    def test_25_upstream_failure_isolated(self):
        self.persist_archive()
        def grader(*_, **__):
            raise h.WNBAHistoricalBacktestUpstreamError("temporary upstream")
        result = s.grade_pending_archives(db_path=self.db, now_utc=TIP + timedelta(hours=1), grader=grader)
        self.assertEqual(result["counts"]["upstream_error"], 1)

    def test_26_model_input_failure_isolated(self):
        self.persist_archive()
        def grader(*_, **__):
            raise h.WNBAHistoricalBacktestModelInputError("bad model input")
        result = s.grade_pending_archives(db_path=self.db, now_utc=TIP + timedelta(hours=1), grader=grader)
        self.assertEqual(result["counts"]["model_input_error"], 1)

    def test_27_unexpected_grader_failure_isolated(self):
        self.persist_archive()
        def grader(*_, **__):
            raise RuntimeError("boom")
        result = s.grade_pending_archives(db_path=self.db, now_utc=TIP + timedelta(hours=1), grader=grader)
        self.assertEqual(result["counts"]["store_error"], 1)

    def test_28_grading_attempts_are_append_only_history(self):
        self.persist_archive()
        def grader(*_, **__):
            raise h.WNBAHistoricalBacktestNotFoundError("wait")
        for _ in range(2):
            s.grade_pending_archives(db_path=self.db, now_utc=TIP + timedelta(hours=1), grader=grader)
        self.assertEqual(s.get_store_status(db_path=self.db)["counts"]["grading_attempts"], 2)

    def test_29_stored_observations_filter_by_stat(self):
        source = archive(stat="points", line=19.5)
        self.persist_archive(source)
        s.persist_graded_observation(observation(source_archive=source, stat="points", line=19.5), db_path=self.db)
        self.assertEqual(len(s.get_stored_observations(db_path=self.db, stat="points")), 1)
        self.assertEqual(len(s.get_stored_observations(db_path=self.db, stat="rebounds")), 0)

    def test_30_observation_limit_validation(self):
        with self.assertRaises(ValueError):
            s.get_stored_observations(db_path=self.db, limit=0)

    def test_31_empty_store_calibration_not_ready(self):
        with self.assertRaises(s.WNBAPregameStoreNotReadyError):
            s.evaluate_stored_calibration(db_path=self.db)

    def test_32_calibration_reuses_step5i_engine(self):
        self.persist_observation()
        result = s.evaluate_stored_calibration(db_path=self.db)
        self.assertEqual(result["observation_count"], 1)
        self.assertFalse(result["pooled_report"]["probability"]["calibration_claim_ready"])

    def test_33_push_survives_store_and_is_excluded_from_binary_scoring(self):
        source = archive(stat="points", line=20.0)
        self.persist_archive(source)
        push = observation(source_archive=source, stat="points", line=20.0, pts=20)
        s.persist_graded_observation(push, db_path=self.db)
        result = s.evaluate_stored_calibration(db_path=self.db)
        probability = result["pooled_report"]["probability"]
        self.assertEqual(probability["resolved_observation_count"], 0)
        self.assertEqual(probability["push_count_excluded_from_binary_scoring"], 1)

    def test_34_status_has_zero_settlement_buckets(self):
        status = s.get_store_status(db_path=self.db)
        self.assertEqual(status["counts"]["settlements"], {"over":0,"under":0,"push":0})

    def test_35_api_routes_registered(self):
        paths = {route.path for route in api.router.routes}
        self.assertIn("/api/v1/wnba/backtests/player-props/archive-and-store", paths)
        self.assertIn("/api/v1/wnba/backtests/player-props/store/grade-pending", paths)
        self.assertIn("/api/v1/wnba/backtests/player-props/store/status", paths)
        self.assertIn("/api/v1/wnba/backtests/player-props/store/observations", paths)
        self.assertIn("/api/v1/wnba/backtests/player-props/store/calibration", paths)

    def test_36_autograder_requires_secret_and_persistent_path(self):
        with patch.dict(os.environ, {}, clear=True):
            config = api._autograde_config()
        self.assertFalse(config["enabled"])

    def test_37_autograder_enabled_when_deployment_requirements_exist(self):
        with patch.dict(os.environ, {
            h.ARCHIVE_SIGNING_ENV: SECRET,
            s.STORE_PATH_ENV: str(self.db),
            api.AUTOGRADE_ENABLED_ENV: "true",
        }, clear=True):
            config = api._autograde_config()
        self.assertTrue(config["enabled"])

    def test_38_store_conflict_maps_to_http_409(self):
        with self.assertRaises(HTTPException) as caught:
            api._raise_api_error(s.WNBAPregameStoreConflictError("conflict"))
        self.assertEqual(caught.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
