import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import sports_api.api.wnba_pregame_board_scheduler as api
import sports_api.database.wnba_current_board_store as store
import sports_api.wnba_pregame_board_scheduler as s
from sports_api.main import app
from sports_api.wnba_historical_backtest_calibration import ARCHIVE_SIGNING_ENV

NOW = datetime(2026, 8, 26, 20, 0, 0, tzinfo=timezone.utc)
TIP = datetime(2026, 8, 26, 23, 0, 0, tzinfo=timezone.utc)
DATE = "2026-08-26"
SEASON = 2026
GAME_ID = "1022600201"


def official_slate(*, state="playable", tip=TIP, integrity=True):
    games = []
    if state != "empty":
        playable = state == "playable"
        games = [{
            "game_id": GAME_ID,
            "game_datetime_utc": tip.isoformat(),
            "verification": {"playable_pregame": playable},
        }]
    return {
        "date": DATE,
        "season": SEASON,
        "source_retrieved_at_utc": NOW.isoformat(),
        "verified_at_utc": NOW.isoformat(),
        "slate": {
            "slate_integrity_pass": integrity,
            "blocking_reasons": [] if integrity else ["bad_slate"],
        },
        "games": games,
    }


def failover_payload(fingerprint="a" * 64, *, with_lines=True):
    lines = [{
        "player_id": 1,
        "stat": "points",
        "line": 22.5,
        "sportsbook_quotes": None,
    }] if with_lines else []
    return {
        "failover_id": "failover-1",
        "failover_fingerprint_sha256": "b" * 64,
        "selected_provider_id": "demo",
        "selected_failover_rank": 1,
        "snapshot_reference": {"snapshot_id": "feed-snap"},
        "line_board": {
            "line_board_fingerprint_sha256": fingerprint,
            "date": DATE,
            "season": SEASON,
            "normalized_line_count": len(lines),
            "step_5l_prop_lines": lines,
        },
    }


def daily_board(fingerprint="c" * 64):
    row = {
        "player_id": 1,
        "game_id": GAME_ID,
        "prop": {"stat": "points", "line": 22.5},
        "selected_side": "over",
        "probability": {"base": 0.61},
    }
    return {
        "daily_board_id": "daily-1",
        "daily_board_fingerprint_sha256": fingerprint,
        "probability_board_count": 1,
        "value_board_count": 0,
        "probability_board": [row],
        "value_board": [],
        "line_generation_audit": [],
    }


def fake_capture_factory(capture):
    def getter(player_id, game_id, season, *, stat, line, **kwargs):
        fp = "d" * 64
        threshold = {
            "game_id": game_id,
            "player_id": player_id,
            "prop": {"stat": stat, "line": line},
            "probability_fingerprint_sha256": fp,
        }
        capture[fp] = {"threshold": threshold, "snapshot": {"snapshot_id": "exact"}}
        return threshold
    return getter


def fake_daily_builder(prop_lines, *, threshold_getter, **kwargs):
    for line in prop_lines:
        threshold_getter(
            line["player_id"], GAME_ID, SEASON,
            stat=line["stat"], line=line["line"],
        )
    return daily_board()


def fake_archive_writer(threshold, snapshot, **kwargs):
    return {
        "persistence": {"stored": True},
        "archive": {"archive_id": "archive-1"},
    }


class Step5PTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.board_path = root / "board.sqlite3"
        self.feed_path = root / "feed.sqlite3"
        self.backtest_path = root / "backtest.sqlite3"
        self.env = {
            store.STORE_PATH_ENV: str(self.board_path),
            "WNBA_PROP_FEED_STORE_PATH": str(self.feed_path),
            "SPORTSGAMEODDS_API_KEY": "demo-key",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def publication(self, *, published=NOW, valid_until=TIP, feed="a" * 64, daily="c" * 64):
        source = {
            "selected_provider_id": "demo",
            "line_board_fingerprint_sha256": feed,
        }
        board = daily_board(daily)
        return s._build_publication(
            target_date=DATE,
            season=SEASON,
            season_type="Regular Season",
            published_at_utc=published,
            valid_until_utc=valid_until,
            serving_state="playable_pregame",
            source_reference=source,
            daily_board=board,
            archive_summary={
                "stored_or_existing_count": 0,
                "stored_count": 0,
                "existing_count": 0,
                "failed_count": 0,
            },
            scheduling={"provider_poll_seconds": 300},
        )

    # Durable publication store
    def test_01_initialize_store_explicit_path(self):
        result = store.initialize_store(self.board_path, env=self.env)
        self.assertTrue(result["persistent_path_explicitly_configured"])
        self.assertTrue(self.board_path.exists())

    def test_02_store_publication(self):
        result = store.persist_publication(self.publication(), path=self.board_path, env=self.env)
        self.assertTrue(result["stored"])

    def test_03_exact_publication_replay_is_idempotent(self):
        pub = self.publication()
        store.persist_publication(pub, path=self.board_path, env=self.env)
        replay = store.persist_publication(pub, path=self.board_path, env=self.env)
        self.assertTrue(replay["idempotent_replay"])

    def test_04_logical_publication_replay_is_idempotent(self):
        pub = self.publication()
        store.persist_publication(pub, path=self.board_path, env=self.env)
        second = self.publication(published=NOW + timedelta(minutes=1), valid_until=TIP)
        replay = store.persist_publication(second, path=self.board_path, env=self.env)
        self.assertTrue(replay["logical_idempotent_replay"])

    def test_05_publication_hash_tamper_rejected(self):
        pub = self.publication()
        pub["content"]["season"] = 2025
        with self.assertRaises(store.WNBACurrentBoardStoreError):
            store.persist_publication(pub, path=self.board_path, env=self.env)

    def test_06_publication_must_expire_after_publish(self):
        with self.assertRaises(store.WNBACurrentBoardStoreError):
            self.publication(valid_until=NOW)
            # _build_publication itself does not validate; persistence does.
            store.persist_publication(self.publication(valid_until=NOW), path=self.board_path, env=self.env)

    def test_07_publication_rows_are_immutable(self):
        store.persist_publication(self.publication(), path=self.board_path, env=self.env)
        conn = sqlite3.connect(self.board_path)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE wnba_board_publications SET serving_state='x'")
        finally:
            conn.close()

    def test_08_publication_rows_cannot_delete(self):
        store.persist_publication(self.publication(), path=self.board_path, env=self.env)
        conn = sqlite3.connect(self.board_path)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM wnba_board_publications")
        finally:
            conn.close()

    def test_09_latest_publication_current_before_expiry(self):
        store.persist_publication(self.publication(), path=self.board_path, env=self.env)
        result = store.get_latest_publication(
            date=DATE, season=SEASON, now_utc=NOW + timedelta(minutes=5),
            require_current=True, path=self.board_path, env=self.env,
        )
        self.assertTrue(result["serving"]["is_current"])

    def test_10_latest_publication_rejects_expired(self):
        store.persist_publication(self.publication(valid_until=NOW + timedelta(minutes=5)), path=self.board_path, env=self.env)
        with self.assertRaises(store.WNBACurrentBoardStoreNotReadyError):
            store.get_latest_publication(
                date=DATE, season=SEASON, now_utc=NOW + timedelta(minutes=6),
                require_current=True, path=self.board_path, env=self.env,
            )

    def test_11_expired_publication_can_be_inspected(self):
        store.persist_publication(self.publication(valid_until=NOW + timedelta(minutes=5)), path=self.board_path, env=self.env)
        result = store.get_latest_publication(
            date=DATE, season=SEASON, now_utc=NOW + timedelta(minutes=6),
            require_current=False, path=self.board_path, env=self.env,
        )
        self.assertFalse(result["serving"]["is_current"])

    def test_12_publication_list_filters_date(self):
        store.persist_publication(self.publication(), path=self.board_path, env=self.env)
        self.assertEqual(1, len(store.list_publications(date=DATE, path=self.board_path, env=self.env)))
        self.assertEqual(0, len(store.list_publications(date="2026-08-25", path=self.board_path, env=self.env)))

    def test_13_publication_limit_validation(self):
        with self.assertRaises(ValueError):
            store.list_publications(limit=0, path=self.board_path, env=self.env)

    def test_14_append_scheduler_run(self):
        pub = self.publication()
        store.persist_publication(pub, path=self.board_path, env=self.env)
        run = s._build_scheduler_run(
            target_date=DATE, season=SEASON, started_at_utc=NOW,
            completed_at_utc=NOW + timedelta(seconds=1), outcome="ok",
            provider_collection_attempted=True, board_rebuild_attempted=True,
            next_due_at_utc=NOW + timedelta(minutes=5), publication_id=pub["publication_id"],
        )
        result = store.append_scheduler_run(run, path=self.board_path, env=self.env)
        self.assertTrue(result["stored"])

    def test_15_scheduler_runs_are_append_only(self):
        run = s._build_scheduler_run(
            target_date=DATE, season=SEASON, started_at_utc=NOW,
            completed_at_utc=NOW, outcome="ok", provider_collection_attempted=False,
            board_rebuild_attempted=False, next_due_at_utc=None,
        )
        store.append_scheduler_run(run, path=self.board_path, env=self.env)
        conn = sqlite3.connect(self.board_path)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM wnba_board_scheduler_runs")
        finally:
            conn.close()

    def test_16_latest_scheduler_run(self):
        run = s._build_scheduler_run(
            target_date=DATE, season=SEASON, started_at_utc=NOW,
            completed_at_utc=NOW, outcome="hello", provider_collection_attempted=False,
            board_rebuild_attempted=False, next_due_at_utc=None,
        )
        store.append_scheduler_run(run, path=self.board_path, env=self.env)
        latest = store.get_latest_scheduler_run(date=DATE, season=SEASON, path=self.board_path, env=self.env)
        self.assertEqual("hello", latest["outcome"])

    def test_17_store_status_counts(self):
        store.persist_publication(self.publication(), path=self.board_path, env=self.env)
        status = store.get_store_status(path=self.board_path, env=self.env)
        self.assertEqual(1, status["publication_count"])
        self.assertEqual(0, status["scheduler_run_count"])

    # Configuration and cadence
    def test_18_scheduler_disabled_without_persistent_paths(self):
        config = s.get_scheduler_configuration({})
        self.assertFalse(config["enabled"])

    def test_19_scheduler_enabled_with_paths_and_provider(self):
        config = s.get_scheduler_configuration(self.env)
        self.assertTrue(config["enabled"])

    def test_20_archive_disabled_without_secret(self):
        config = s.get_scheduler_configuration(self.env)
        self.assertFalse(config["automatic_archive"]["enabled"])

    def test_21_archive_enabled_with_secret_and_store(self):
        env = dict(self.env)
        env[ARCHIVE_SIGNING_ENV] = "s" * 32
        env["WNBA_BACKTEST_STORE_PATH"] = str(self.backtest_path)
        config = s.get_scheduler_configuration(env)
        self.assertTrue(config["automatic_archive"]["enabled"])

    def test_22_poll_far(self):
        self.assertEqual(s.POLL_FAR_SECONDS, s._poll_seconds(7 * 3600))

    def test_23_poll_mid(self):
        self.assertEqual(s.POLL_MID_SECONDS, s._poll_seconds(3 * 3600))

    def test_24_poll_near(self):
        self.assertEqual(s.POLL_NEAR_SECONDS, s._poll_seconds(60 * 60))

    def test_25_model_refresh_final(self):
        self.assertEqual(s.MODEL_REFRESH_FINAL_SECONDS, s._model_refresh_seconds(10 * 60))

    def test_26_target_date_defaults_arizona(self):
        self.assertEqual(DATE, s._target_date(None, NOW))

    def test_27_invalid_date_rejected(self):
        with self.assertRaises(s.WNBAPregameBoardSchedulerModelInputError):
            s._target_date("08/26/2026", NOW)

    # Official slate behavior
    def test_28_playable_slate_state(self):
        result = s._validate_official_slate(official_slate(), target_date=DATE, season=SEASON, now_utc=NOW)
        self.assertEqual("playable_pregame", result["state"])

    def test_29_empty_slate_state(self):
        result = s._validate_official_slate(official_slate(state="empty"), target_date=DATE, season=SEASON, now_utc=NOW)
        self.assertEqual("empty_official_slate", result["state"])

    def test_30_closed_slate_state(self):
        result = s._validate_official_slate(
            official_slate(state="closed", tip=NOW - timedelta(hours=1)),
            target_date=DATE, season=SEASON, now_utc=NOW,
        )
        self.assertEqual("pregame_closed", result["state"])

    def test_31_future_nonplayable_blocks(self):
        with self.assertRaises(s.WNBAPregameBoardSchedulerNotReadyError):
            s._validate_official_slate(
                official_slate(state="closed", tip=NOW + timedelta(hours=1)),
                target_date=DATE, season=SEASON, now_utc=NOW,
            )

    def test_32_integrity_failure_blocks(self):
        with self.assertRaises(s.WNBAPregameBoardSchedulerNotReadyError):
            s._validate_official_slate(
                official_slate(integrity=False), target_date=DATE, season=SEASON, now_utc=NOW,
            )

    def test_33_playable_at_tip_blocks(self):
        with self.assertRaises(s.WNBAPregameBoardSchedulerNotReadyError):
            s._validate_official_slate(
                official_slate(tip=NOW), target_date=DATE, season=SEASON, now_utc=NOW,
            )

    # Scheduler cycle
    def test_34_not_due_skips_before_slate_call(self):
        run = s._build_scheduler_run(
            target_date=DATE, season=SEASON, started_at_utc=NOW - timedelta(minutes=1),
            completed_at_utc=NOW - timedelta(minutes=1), outcome="prior",
            provider_collection_attempted=True, board_rebuild_attempted=False,
            next_due_at_utc=NOW + timedelta(minutes=4),
        )
        store.append_scheduler_run(run, path=self.board_path, env=self.env)
        calls = []
        result = s.run_pregame_board_cycle(
            now_utc=NOW, env=self.env, board_store_path=self.board_path,
            feed_store_path=self.feed_path, slate_getter=lambda *a: calls.append(a),
        )
        self.assertEqual("skipped_not_due", result["outcome"])
        self.assertEqual([], calls)

    def test_35_empty_slate_never_calls_provider(self):
        calls = []
        result = s.run_pregame_board_cycle(
            now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
            feed_store_path=self.feed_path,
            slate_getter=lambda *a: official_slate(state="empty"),
            failover_collector=lambda *a, **k: calls.append((a, k)),
        )
        self.assertEqual("empty_official_slate", result["outcome"])
        self.assertEqual([], calls)
        self.assertEqual(0, result["publication"]["content"]["board"]["probability_board_count"])

    def test_36_closed_slate_never_calls_provider(self):
        calls = []
        result = s.run_pregame_board_cycle(
            now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
            feed_store_path=self.feed_path,
            slate_getter=lambda *a: official_slate(state="closed", tip=NOW - timedelta(hours=1)),
            failover_collector=lambda *a, **k: calls.append((a, k)),
        )
        self.assertEqual("pregame_closed", result["outcome"])
        self.assertEqual([], calls)

    def test_37_hard_provider_spacing_guard_applies_even_force(self):
        run = s._build_scheduler_run(
            target_date=DATE, season=SEASON, started_at_utc=NOW - timedelta(seconds=10),
            completed_at_utc=NOW - timedelta(seconds=10), outcome="prior",
            provider_collection_attempted=True, board_rebuild_attempted=False,
            next_due_at_utc=None,
        )
        store.append_scheduler_run(run, path=self.board_path, env=self.env)
        result = s.run_pregame_board_cycle(
            now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
            feed_store_path=self.feed_path, slate_getter=lambda *a: official_slate(),
        )
        self.assertEqual("skipped_provider_rate_guard", result["outcome"])

    def test_38_provider_failure_records_run(self):
        def fail(*a, **k):
            raise s.WNBAPropFeedFailoverNotReadyError("down")
        with self.assertRaises(s.WNBAPregameBoardSchedulerNotReadyError):
            s.run_pregame_board_cycle(
                now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
                feed_store_path=self.feed_path, slate_getter=lambda *a: official_slate(),
                failover_collector=fail,
            )
        latest = store.get_latest_scheduler_run(date=DATE, season=SEASON, path=self.board_path, env=self.env)
        self.assertEqual("provider_cycle_failed", latest["outcome"])

    def test_39_unchanged_feed_skips_model_rebuild(self):
        pub = self.publication(published=NOW - timedelta(minutes=2), valid_until=TIP)
        store.persist_publication(pub, path=self.board_path, env=self.env)
        calls = []
        result = s.run_pregame_board_cycle(
            now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
            feed_store_path=self.feed_path, slate_getter=lambda *a: official_slate(),
            failover_collector=lambda *a, **k: failover_payload("a" * 64),
            daily_builder=lambda *a, **k: calls.append(1),
        )
        self.assertEqual("feed_unchanged_model_refresh_not_due", result["outcome"])
        self.assertEqual([], calls)

    def test_40_changed_feed_rebuilds_and_publishes(self):
        with patch.object(s, "_capture_threshold_getter", side_effect=fake_capture_factory):
            result = s.run_pregame_board_cycle(
                now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
                feed_store_path=self.feed_path, slate_getter=lambda *a: official_slate(),
                failover_collector=lambda *a, **k: failover_payload("f" * 64),
                daily_builder=fake_daily_builder,
            )
        self.assertEqual("published_new_board", result["outcome"])
        self.assertEqual(1, result["captured_threshold_snapshot_pair_count"])

    def test_41_same_feed_rebuilds_when_model_refresh_due(self):
        pub = self.publication(published=NOW - timedelta(hours=2), valid_until=TIP)
        store.persist_publication(pub, path=self.board_path, env=self.env)
        with patch.object(s, "_capture_threshold_getter", side_effect=fake_capture_factory):
            result = s.run_pregame_board_cycle(
                now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
                feed_store_path=self.feed_path, slate_getter=lambda *a: official_slate(),
                failover_collector=lambda *a, **k: failover_payload("a" * 64),
                daily_builder=fake_daily_builder,
            )
        self.assertTrue(result["board_rebuild_attempted"])

    def test_42_publication_expiry_never_exceeds_tip(self):
        close_tip = NOW + timedelta(minutes=8)
        with patch.object(s, "_capture_threshold_getter", side_effect=fake_capture_factory):
            result = s.run_pregame_board_cycle(
                now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
                feed_store_path=self.feed_path,
                slate_getter=lambda *a: official_slate(tip=close_tip),
                failover_collector=lambda *a, **k: failover_payload("e" * 64),
                daily_builder=fake_daily_builder,
            )
        self.assertEqual(close_tip.isoformat(), result["publication"]["content"]["valid_until_utc"])

    def test_43_playable_slate_without_prop_lines_blocks(self):
        with self.assertRaises(s.WNBAPregameBoardSchedulerNotReadyError):
            s.run_pregame_board_cycle(
                now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
                feed_store_path=self.feed_path, slate_getter=lambda *a: official_slate(),
                failover_collector=lambda *a, **k: failover_payload(with_lines=False),
            )

    def test_44_archive_disabled_without_hmac(self):
        with patch.object(s, "_capture_threshold_getter", side_effect=fake_capture_factory):
            result = s.run_pregame_board_cycle(
                now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
                feed_store_path=self.feed_path, slate_getter=lambda *a: official_slate(),
                failover_collector=lambda *a, **k: failover_payload("1" * 64),
                daily_builder=fake_daily_builder,
            )
        self.assertEqual("disabled", result["archive_summary"]["status"])

    def test_45_archive_enabled_stores_first_prediction(self):
        env = dict(self.env)
        env[ARCHIVE_SIGNING_ENV] = "s" * 32
        env["WNBA_BACKTEST_STORE_PATH"] = str(self.backtest_path)
        with patch.object(s, "_capture_threshold_getter", side_effect=fake_capture_factory):
            result = s.run_pregame_board_cycle(
                now_utc=NOW, force=True, env=env, board_store_path=self.board_path,
                feed_store_path=self.feed_path, backtest_store_path=self.backtest_path,
                slate_getter=lambda *a: official_slate(),
                failover_collector=lambda *a, **k: failover_payload("2" * 64),
                daily_builder=fake_daily_builder, archive_writer=fake_archive_writer,
            )
        self.assertEqual(1, result["archive_summary"]["stored_count"])

    def test_46_existing_first_archive_skips_writer(self):
        s.initialize_backtest_store(self.backtest_path)
        conn = sqlite3.connect(self.backtest_path)
        try:
            conn.execute(
                """INSERT INTO wnba_pregame_archives(
                archive_id,content_sha256,logical_prediction_key,archive_json,stored_at_utc,
                official_game_tip_utc,archived_at_utc,season,season_type,game_id,player_id,
                team_key,opponent_team_key,stat,line,probability_model_version,
                probability_fingerprint_sha256,snapshot_content_sha256,signature_value,signature_verified)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (
                    "existing","1"*64,"2"*64,"{}",NOW.isoformat(),TIP.isoformat(),NOW.isoformat(),
                    SEASON,"Regular Season",GAME_ID,1,"LVA","PHX","points",22.5,
                    "v","3"*64,"4"*64,"5"*64,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        capture = {"d"*64: {"threshold": {
            "game_id": GAME_ID, "player_id": 1,
            "prop": {"stat": "points", "line": 22.5},
            "probability_fingerprint_sha256": "d"*64,
        }, "snapshot": {}}}
        calls = []
        summary = s._archive_captured_predictions(
            capture, enabled=True, backtest_store_path=self.backtest_path,
            signing_secret="s"*32, archived_at_utc=NOW,
            archive_writer=lambda *a, **k: calls.append(1),
        )
        self.assertEqual(1, summary["existing_count"])
        self.assertEqual([], calls)

    def test_47_archive_failure_is_partial_not_fake_success(self):
        capture = {"d"*64: {"threshold": {
            "game_id": GAME_ID, "player_id": 1,
            "prop": {"stat": "points", "line": 22.5},
            "probability_fingerprint_sha256": "d"*64,
        }, "snapshot": {}}}
        summary = s._archive_captured_predictions(
            capture, enabled=True, backtest_store_path=self.backtest_path,
            signing_secret="s"*32, archived_at_utc=NOW,
            archive_writer=lambda *a, **k: (_ for _ in ()).throw(ValueError("bad")),
        )
        self.assertEqual("partial_failure", summary["status"])
        self.assertEqual(1, summary["failed_count"])

    # Exact snapshot capture orchestration
    def test_48_capture_threshold_getter_preserves_exact_snapshot(self):
        snapshot = {"snapshot_id": "snap", "content_sha256": "9"*64}
        readiness = {"snapshot": snapshot}
        monte = {"monte": True}
        threshold = {
            "snapshot_reference": {"snapshot_id": "snap", "content_sha256": "9"*64},
            "probability_fingerprint_sha256": "8"*64,
        }
        capture = {}
        with patch.object(s, "get_player_game_model_input_readiness", return_value=readiness), \
             patch.object(s, "project_scenarios_from_readiness", return_value={"scenarios": True}), \
             patch.object(s, "get_player_game_log_dataset", return_value={"games": []}), \
             patch.object(s, "build_empirical_outcome_distribution", return_value={"dist": True}), \
             patch.object(s, "simulate_correlated_outcomes", return_value=monte), \
             patch.object(s, "evaluate_prop_threshold", return_value=threshold):
            result = s._capture_threshold_getter(capture)(1, GAME_ID, SEASON, stat="points", line=22.5)
        self.assertEqual(threshold, result)
        self.assertEqual(snapshot, capture["8"*64]["snapshot"])

    def test_49_capture_snapshot_reference_mismatch_fails(self):
        capture = {}
        with patch.object(s, "get_player_game_model_input_readiness", return_value={"snapshot": {"snapshot_id":"a","content_sha256":"1"*64}}), \
             patch.object(s, "project_scenarios_from_readiness", return_value={}), \
             patch.object(s, "get_player_game_log_dataset", return_value={}), \
             patch.object(s, "build_empirical_outcome_distribution", return_value={}), \
             patch.object(s, "simulate_correlated_outcomes", return_value={}), \
             patch.object(s, "evaluate_prop_threshold", return_value={"snapshot_reference":{"snapshot_id":"b","content_sha256":"1"*64},"probability_fingerprint_sha256":"2"*64}):
            with self.assertRaises(s.WNBAPropThresholdUpstreamError):
                s._capture_threshold_getter(capture)(1, GAME_ID, SEASON, stat="points", line=22.5)

    def test_50_readiness_not_found_maps_to_step5f_not_found(self):
        with patch.object(s, "get_player_game_model_input_readiness", side_effect=s.WNBAModelInputReadinessNotFoundError("missing")):
            with self.assertRaises(s.WNBAPropThresholdNotFoundError):
                s._capture_threshold_getter({})(1, GAME_ID, SEASON, stat="points", line=22.5)

    # Current read path
    def test_51_current_board_requires_publication(self):
        with self.assertRaises(s.WNBAPregameBoardSchedulerNotReadyError):
            s.get_current_published_board(
                date=DATE, season=SEASON, now_utc=NOW,
                env=self.env, board_store_path=self.board_path,
            )

    def test_52_current_board_returns_published_probability_board(self):
        store.persist_publication(self.publication(), path=self.board_path, env=self.env)
        current = s.get_current_published_board(
            date=DATE, season=SEASON, now_utc=NOW,
            env=self.env, board_store_path=self.board_path,
        )
        self.assertEqual(1, current["probability_board_count"])
        self.assertEqual("demo", current["selected_provider_id"])

    def test_53_current_board_rejects_expired(self):
        store.persist_publication(self.publication(valid_until=NOW + timedelta(minutes=1)), path=self.board_path, env=self.env)
        with self.assertRaises(s.WNBAPregameBoardSchedulerNotReadyError):
            s.get_current_published_board(
                date=DATE, season=SEASON, now_utc=NOW + timedelta(minutes=2),
                env=self.env, board_store_path=self.board_path,
            )

    def test_54_current_board_read_semantics_are_network_free(self):
        store.persist_publication(self.publication(), path=self.board_path, env=self.env)
        current = s.get_current_published_board(
            date=DATE, season=SEASON, now_utc=NOW,
            env=self.env, board_store_path=self.board_path,
        )
        self.assertTrue(current["serving_semantics"]["no_network_call_required"])

    # API/worker surface
    def test_55_routes_registered(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/api/v1/wnba/rankings/player-props/current", paths)
        self.assertIn("/api/v1/wnba/rankings/player-props/current/refresh", paths)
        self.assertIn("/api/v1/wnba/rankings/player-props/current/status", paths)
        self.assertIn("/api/v1/wnba/rankings/player-props/current/history", paths)

    def test_56_provider_id_parser(self):
        self.assertEqual(["a", "b"], api._provider_ids("a, b"))

    def test_57_provider_id_empty_rejected(self):
        with self.assertRaises(s.WNBAPregameBoardSchedulerModelInputError):
            api._provider_ids(" , ")

    def test_58_api_not_ready_maps_409(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(s.WNBAPregameBoardSchedulerNotReadyError("no board"))
        self.assertEqual(409, ctx.exception.status_code)

    def test_59_api_model_input_maps_422(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(s.WNBAPregameBoardSchedulerModelInputError("bad"))
        self.assertEqual(422, ctx.exception.status_code)

    def test_60_api_upstream_maps_502(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(s.WNBAPregameBoardSchedulerUpstreamError("up"))
        self.assertEqual(502, ctx.exception.status_code)

    def test_61_api_store_maps_500(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(s.WNBAPregameBoardSchedulerStoreError("db"))
        self.assertEqual(500, ctx.exception.status_code)

    def test_62_scheduler_status_contains_configuration(self):
        status = s.get_scheduler_status(
            date=DATE, season=SEASON, env=self.env, board_store_path=self.board_path,
        )
        self.assertIn("configuration", status)
        self.assertIn("board_store", status)

    def test_63_closed_publication_has_no_provider(self):
        result = s.run_pregame_board_cycle(
            now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
            feed_store_path=self.feed_path,
            slate_getter=lambda *a: official_slate(state="empty"),
        )
        source = result["publication"]["content"]["source_reference"]
        self.assertIsNone(source["selected_provider_id"])

    def test_64_board_publication_hash_is_deterministic_for_same_content(self):
        one = self.publication()
        two = self.publication()
        self.assertEqual(one["content_sha256"], two["content_sha256"])
        self.assertEqual(one["publication_id"], two["publication_id"])

    def test_65_probability_rank_data_is_preserved(self):
        pub = self.publication()
        row = pub["content"]["board"]["probability_board"][0]
        self.assertEqual(0.61, row["probability"]["base"])

    def test_66_publication_semantics_keep_step5k_authority(self):
        pub = self.publication()
        self.assertTrue(pub["content"]["semantics"]["step_5k_probability_rank_remains_authoritative"])

    def test_67_cycle_guardrail_says_unchanged_feed_skips_rebuild(self):
        with patch.object(s, "_capture_threshold_getter", side_effect=fake_capture_factory):
            result = s.run_pregame_board_cycle(
                now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
                feed_store_path=self.feed_path, slate_getter=lambda *a: official_slate(),
                failover_collector=lambda *a, **k: failover_payload("7"*64),
                daily_builder=fake_daily_builder,
            )
        self.assertTrue(result["guardrails"]["unchanged_feed_can_skip_expensive_model_rebuild"])

    def test_68_cycle_archive_count_matches_capture_when_disabled(self):
        with patch.object(s, "_capture_threshold_getter", side_effect=fake_capture_factory):
            result = s.run_pregame_board_cycle(
                now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
                feed_store_path=self.feed_path, slate_getter=lambda *a: official_slate(),
                failover_collector=lambda *a, **k: failover_payload("8"*64),
                daily_builder=fake_daily_builder,
            )
        self.assertEqual(1, result["captured_threshold_snapshot_pair_count"])
        self.assertEqual(0, result["archive_summary"]["stored_or_existing_count"])

    def test_69_scheduler_run_records_selected_provider(self):
        with patch.object(s, "_capture_threshold_getter", side_effect=fake_capture_factory):
            result = s.run_pregame_board_cycle(
                now_utc=NOW, force=True, env=self.env, board_store_path=self.board_path,
                feed_store_path=self.feed_path, slate_getter=lambda *a: official_slate(),
                failover_collector=lambda *a, **k: failover_payload("6"*64),
                daily_builder=fake_daily_builder,
            )
        self.assertEqual("demo", result["scheduler_run"]["selected_provider_id"])

    def test_70_history_limits_validate(self):
        with self.assertRaises(ValueError):
            store.list_scheduler_runs(limit=0, path=self.board_path, env=self.env)


if __name__ == "__main__":
    unittest.main()
