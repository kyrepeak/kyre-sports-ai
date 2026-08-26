import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi import HTTPException

import sports_api.api.wnba_prop_feed_failover as api
import sports_api.collectors.wnba_sportsgameodds as sgo
import sports_api.database.wnba_prop_feed_store as store
import sports_api.wnba_prop_feed_failover as f
from sports_api.collectors.wnba_prop_feed_collector import (
    PROVIDERS_ENV,
    WNBAPropFeedCollectorNotReadyError,
    WNBAPropFeedCollectorUpstreamError,
)
from sports_api.wnba_prop_line_feed_adapter import WNBAPropLineFeedModelInputError

NOW = "2026-08-26T20:00:00+00:00"


def sgo_event(*, league="WNBA", started=False, include_players=True, include_odds=True):
    players = {
        "AJA_WILSON_1_WNBA": {
            "playerID": "AJA_WILSON_1_WNBA",
            "teamID": "LAS_VEGAS_ACES_WNBA",
            "name": "A'ja Wilson",
        }
    } if include_players else {}
    odds = {
        "points-AJA_WILSON_1_WNBA-game-ou-over": {
            "oddID": "points-AJA_WILSON_1_WNBA-game-ou-over",
            "statID": "points",
            "statEntityID": "AJA_WILSON_1_WNBA",
            "periodID": "game",
            "betTypeID": "ou",
            "sideID": "over",
            "started": False,
            "ended": False,
            "cancelled": False,
            "byBookmaker": {
                "draftkings": {
                    "odds": "-110", "overUnder": "22.5",
                    "lastUpdatedAt": "2026-08-26T19:59:00.000Z", "available": True,
                    "altLines": [
                        {"odds": "+105", "overUnder": "23.5", "lastUpdatedAt": "2026-08-26T19:59:01.000Z", "available": True},
                        {"odds": "+120", "overUnder": "24.5", "lastUpdatedAt": "2026-08-26T19:59:01.000Z", "available": False},
                    ],
                },
                "fanduel": {"odds": "-108", "overUnder": "22.5", "lastUpdatedAt": "2026-08-26T19:59:02.000Z", "available": True},
                "oldbook": {"odds": "-115", "overUnder": "22.5", "lastUpdatedAt": "2026-08-26T19:40:00.000Z", "available": False},
            },
        },
        "points-AJA_WILSON_1_WNBA-game-ou-under": {
            "oddID": "points-AJA_WILSON_1_WNBA-game-ou-under",
            "statID": "points",
            "statEntityID": "AJA_WILSON_1_WNBA",
            "periodID": "game",
            "betTypeID": "ou",
            "sideID": "under",
            "byBookmaker": {
                "draftkings": {"odds": "-110", "overUnder": "22.5", "lastUpdatedAt": "2026-08-26T19:59:03.000Z", "available": True},
                "fanduel": {"odds": "-112", "overUnder": "22.5", "lastUpdatedAt": "2026-08-26T19:59:04.000Z", "available": True},
            },
        },
        "rebounds-AJA_WILSON_1_WNBA-game-ou-over": {
            "statID": "rebounds", "statEntityID": "AJA_WILSON_1_WNBA", "periodID": "game", "betTypeID": "ou", "sideID": "over",
            "byBookmaker": {"betmgm": {"odds": "+100", "overUnder": "10.5", "lastUpdatedAt": "2026-08-26T19:59:05Z", "available": True}},
        },
        "assists-AJA_WILSON_1_WNBA-game-ou-over": {
            "statID": "assists", "statEntityID": "AJA_WILSON_1_WNBA", "periodID": "game", "betTypeID": "ou", "sideID": "over",
            "byBookmaker": {"caesars": {"odds": "+105", "overUnder": "2.5", "lastUpdatedAt": "2026-08-26T19:59:06Z", "available": True}},
        },
        "points+rebounds+assists-AJA_WILSON_1_WNBA-game-ou-over": {
            "statID": "points+rebounds+assists", "statEntityID": "AJA_WILSON_1_WNBA", "periodID": "game", "betTypeID": "ou", "sideID": "over",
            "byBookmaker": {"fanatics": {"odds": "-105", "overUnder": "35.5", "lastUpdatedAt": "2026-08-26T19:59:07Z", "available": True}},
        },
        "points-home-game-ou-over": {
            "statID": "points", "statEntityID": "home", "periodID": "game", "betTypeID": "ou", "sideID": "over",
            "byBookmaker": {"draftkings": {"odds": "-110", "overUnder": "85.5", "available": True}},
        },
        "points-AJA_WILSON_1_WNBA-1h-ou-over": {
            "statID": "points", "statEntityID": "AJA_WILSON_1_WNBA", "periodID": "1h", "betTypeID": "ou", "sideID": "over",
            "byBookmaker": {"draftkings": {"odds": "-110", "overUnder": "11.5", "available": True}},
        },
    } if include_odds else {}
    return {
        "eventID": "SGO-EVENT-1",
        "leagueID": league,
        "teams": {
            "home": {"teamID": "LAS_VEGAS_ACES_WNBA", "names": {"long": "Las Vegas Aces", "short": "LVA"}},
            "away": {"teamID": "PHOENIX_MERCURY_WNBA", "names": {"long": "Phoenix Mercury", "short": "PHX"}},
        },
        "status": {"started": started, "live": started, "ended": False, "cancelled": False, "finalized": False},
        "players": players,
        "odds": odds,
    }


def collection(provider_id="demo", *, raw=None, feed_format="canonical_offers_v1"):
    raw = {"offers": []} if raw is None else raw
    return {
        "collection_id": f"collection-{provider_id}",
        "collection_fingerprint_sha256": (provider_id[0] if provider_id else "a") * 64,
        "provider_id": provider_id,
        "feed_source": f"{provider_id} feed",
        "feed_format": feed_format,
        "odds_format": "american",
        "date": "2026-08-26",
        "season": 2026,
        "collected_at_utc": NOW,
        "raw_feed_sha256": "b" * 64,
        "raw_feed": copy.deepcopy(raw),
        "transport": {"status_code": 200},
    }


def line_board(lines=2, games=1):
    return {
        "line_board_fingerprint_sha256": "c" * 64,
        "date": "2026-08-26",
        "season": 2026,
        "normalized_line_count": lines,
        "official_slate_reference": {"playable_game_ids": [f"g{i}" for i in range(games)]},
        "step_5l_prop_lines": [
            {"player_id": 1, "stat": "points", "line": 22.5, "sportsbook_quotes": None}
        ] if lines else [],
    }


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload).encode("utf-8")
    def json(self):
        return copy.deepcopy(self._payload)


class Recorder:
    def __init__(self, response):
        self.response = response
        self.calls = []
    def __call__(self, url, **kwargs):
        self.calls.append((url, copy.deepcopy(kwargs)))
        return self.response


class Step5OTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "feed.sqlite3"
        self.env = {store.STORE_PATH_ENV: str(self.path)}
    def tearDown(self):
        self.tmp.cleanup()

    # SportsGameOdds onboarding / translation
    def test_01_sgo_not_ready_without_key(self):
        self.assertFalse(sgo.sportsgameodds_ready({}))

    def test_02_sgo_ready_with_generic_key(self):
        self.assertTrue(sgo.sportsgameodds_ready({sgo.SPORTSGAMEODDS_API_KEY_ENV: "x"}))

    def test_03_sgo_ready_with_wnba_fallback_key(self):
        self.assertTrue(sgo.sportsgameodds_ready({sgo.WNBA_SPORTSGAMEODDS_API_KEY_ENV: "x"}))

    def test_04_profile_never_embeds_key_in_registry_json(self):
        env = sgo.build_sportsgameodds_step5n_env({sgo.SPORTSGAMEODDS_API_KEY_ENV: "secret-value"})
        self.assertNotIn("secret-value", env[PROVIDERS_ENV])
        self.assertIn(sgo.SPORTSGAMEODDS_API_KEY_ENV, env[PROVIDERS_ENV])

    def test_05_profile_uses_official_events_endpoint(self):
        env = sgo.build_sportsgameodds_step5n_env({sgo.SPORTSGAMEODDS_API_KEY_ENV: "x"})
        self.assertIn(sgo.SPORTSGAMEODDS_EVENTS_URL, env[PROVIDERS_ENV])

    def test_06_profile_requests_wnba(self):
        env = sgo.build_sportsgameodds_step5n_env({sgo.SPORTSGAMEODDS_API_KEY_ENV: "x"})
        self.assertIn('"leagueID":"WNBA"', env[PROVIDERS_ENV])

    def test_07_profile_requests_alt_lines(self):
        env = sgo.build_sportsgameodds_step5n_env({sgo.SPORTSGAMEODDS_API_KEY_ENV: "x"})
        self.assertIn('"includeAltLines":"true"', env[PROVIDERS_ENV])

    def test_08_profile_uses_secret_header_binding(self):
        env = sgo.build_sportsgameodds_step5n_env({sgo.SPORTSGAMEODDS_API_KEY_ENV: "x"})
        self.assertIn('"x-api-key":"SPORTSGAMEODDS_API_KEY"', env[PROVIDERS_ENV])

    def test_09_onboarding_is_redacted(self):
        result = sgo.describe_sportsgameodds_onboarding({sgo.SPORTSGAMEODDS_API_KEY_ENV: "secret-value"})
        self.assertTrue(result["ready"])
        self.assertNotIn("secret-value", json.dumps(result))

    def test_10_adapter_requires_event_list(self):
        with self.assertRaises(sgo.WNBASportsGameOddsAdapterError):
            sgo.sportsgameodds_to_canonical({"bad": []}, feed_captured_at_utc=NOW)

    def test_11_adapter_accepts_data_list(self):
        result = sgo.sportsgameodds_to_canonical({"data": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertGreater(result["canonical_offer_count"], 0)

    def test_12_adapter_accepts_events_list(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertGreater(result["canonical_offer_count"], 0)

    def test_13_adapter_outputs_canonical_offers(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertIsInstance(result["raw_feed"]["offers"], list)
        self.assertEqual(result["feed_format"], "canonical_offers_v1")

    def test_14_adapter_preserves_player_name(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertTrue(all(row["player_name"] == "A'ja Wilson" for row in result["raw_feed"]["offers"]))

    def test_15_provider_player_id_not_used_as_wnba_id(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertTrue(all("player_id" not in row for row in result["raw_feed"]["offers"]))

    def test_16_draftkings_display_name(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertIn("DraftKings", {row["sportsbook"] for row in result["raw_feed"]["offers"]})

    def test_17_fanduel_display_name(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertIn("FanDuel", {row["sportsbook"] for row in result["raw_feed"]["offers"]})

    def test_18_primary_line_preserved(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertIn("22.5", {str(row["line"]) for row in result["raw_feed"]["offers"]})

    def test_19_available_alt_line_preserved(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertIn("23.5", {str(row["line"]) for row in result["raw_feed"]["offers"]})

    def test_20_unavailable_alt_line_excluded(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertNotIn("24.5", {str(row["line"]) for row in result["raw_feed"]["offers"]})

    def test_21_unavailable_book_excluded(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertNotIn("oldbook", {row["sportsbook"] for row in result["raw_feed"]["offers"]})

    def test_22_points_supported(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertIn("points", {row["stat"] for row in result["raw_feed"]["offers"]})

    def test_23_rebounds_supported(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertIn("rebounds", {row["stat"] for row in result["raw_feed"]["offers"]})

    def test_24_assists_supported(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertIn("assists", {row["stat"] for row in result["raw_feed"]["offers"]})

    def test_25_pra_supported(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertIn("pra", {row["stat"] for row in result["raw_feed"]["offers"]})

    def test_26_team_total_excluded(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertTrue(all(row["line"] != "85.5" for row in result["raw_feed"]["offers"]))

    def test_27_first_half_excluded(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertTrue(all(row["line"] != "11.5" for row in result["raw_feed"]["offers"]))

    def test_28_wrong_league_excluded(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event(league="NBA")]}, feed_captured_at_utc=NOW)
        self.assertEqual(result["canonical_offer_count"], 0)

    def test_29_started_event_excluded(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event(started=True)]}, feed_captured_at_utc=NOW)
        self.assertEqual(result["canonical_offer_count"], 0)

    def test_30_missing_player_name_excludes_props(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event(include_players=False)]}, feed_captured_at_utc=NOW)
        self.assertEqual(result["canonical_offer_count"], 0)
        self.assertGreater(result["missing_player_name_count"], 0)

    def test_31_no_odds_event_is_processed_empty(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event(include_odds=False)]}, feed_captured_at_utc=NOW)
        self.assertEqual(result["canonical_offer_count"], 0)

    def test_32_adapter_fingerprint_sha256(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertEqual(len(result["adapter_fingerprint_sha256"]), 64)

    def test_33_source_event_id_preserved(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertTrue(all(row["source_event_id"] == "SGO-EVENT-1" for row in result["raw_feed"]["offers"]))

    def test_34_market_timestamp_preserved(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        self.assertIn("2026-08-26T19:59:00.000Z", {row["market_captured_at_utc"] for row in result["raw_feed"]["offers"]})

    def test_35_home_away_team_names_preserved(self):
        result = sgo.sportsgameodds_to_canonical({"events": [sgo_event()]}, feed_captured_at_utc=NOW)
        row = result["raw_feed"]["offers"][0]
        self.assertEqual(row["home_team"], "Las Vegas Aces")
        self.assertEqual(row["away_team"], "Phoenix Mercury")

    def test_36_collect_sgo_runs_frozen_step5n_then_adapter(self):
        rec = Recorder(FakeResponse({"success": True, "data": [sgo_event()]}))
        env = {sgo.SPORTSGAMEODDS_API_KEY_ENV: "secret"}
        result = sgo.collect_sportsgameodds_feed(date="2026-08-26", env=env, requester=rec)
        self.assertEqual(result["provider_id"], sgo.SPORTSGAMEODDS_PROVIDER_ID)
        self.assertEqual(result["feed_format"], "canonical_offers_v1")
        self.assertGreater(len(result["raw_feed"]["offers"]), 0)
        self.assertEqual(rec.calls[0][1]["headers"]["x-api-key"], "secret")
        self.assertNotIn("secret", json.dumps({k: v for k, v in result.items() if k != "collection"}))

    # Store
    def test_37_store_initializes(self):
        result = store.initialize_store(self.path, self.env)
        self.assertTrue(self.path.exists())
        self.assertEqual(result["schema_version"], store.STORE_SCHEMA_VERSION)

    def _persist(self, provider="demo"):
        c = collection(provider, raw={"offers": [{"x": 1}]})
        return store.persist_feed_snapshot(
            provider_id=provider, collection=c, feed_source=c["feed_source"],
            feed_format=c["feed_format"], odds_format=c["odds_format"],
            normalized_input_feed=c["raw_feed"], path=self.path, env=self.env,
        )

    def test_38_snapshot_persists(self):
        result = self._persist()
        self.assertTrue(result["inserted"])
        self.assertEqual(store.get_store_status(path=self.path, env=self.env)["snapshot_count"], 1)

    def test_39_snapshot_exact_replay_idempotent(self):
        first = self._persist()
        second = self._persist()
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(store.get_store_status(path=self.path, env=self.env)["snapshot_count"], 1)

    def test_40_snapshot_hash_sha256(self):
        result = self._persist()
        self.assertEqual(len(result["snapshot_fingerprint_sha256"]), 64)

    def test_41_snapshot_update_rejected(self):
        result = self._persist()
        with self.assertRaises(sqlite3.DatabaseError):
            with sqlite3.connect(self.path) as conn:
                conn.execute("UPDATE wnba_prop_feed_snapshots SET provider_id='x' WHERE snapshot_id=?", (result["snapshot_id"],))

    def test_42_snapshot_delete_rejected(self):
        result = self._persist()
        with self.assertRaises(sqlite3.DatabaseError):
            with sqlite3.connect(self.path) as conn:
                conn.execute("DELETE FROM wnba_prop_feed_snapshots WHERE snapshot_id=?", (result["snapshot_id"],))

    def test_43_attempt_appends(self):
        result = store.append_feed_attempt(provider_id="demo", failover_rank=1, started_at_utc=NOW, outcome="success", path=self.path, env=self.env)
        self.assertGreater(result["attempt_id"], 0)

    def test_44_attempt_update_rejected(self):
        result = store.append_feed_attempt(provider_id="demo", failover_rank=1, started_at_utc=NOW, outcome="success", path=self.path, env=self.env)
        with self.assertRaises(sqlite3.DatabaseError):
            with sqlite3.connect(self.path) as conn:
                conn.execute("UPDATE wnba_prop_feed_attempts SET outcome='x' WHERE attempt_id=?", (result["attempt_id"],))

    def test_45_attempt_delete_rejected(self):
        result = store.append_feed_attempt(provider_id="demo", failover_rank=1, started_at_utc=NOW, outcome="success", path=self.path, env=self.env)
        with self.assertRaises(sqlite3.DatabaseError):
            with sqlite3.connect(self.path) as conn:
                conn.execute("DELETE FROM wnba_prop_feed_attempts WHERE attempt_id=?", (result["attempt_id"],))

    def test_46_snapshot_list_without_payload(self):
        self._persist()
        result = store.list_feed_snapshots(path=self.path, env=self.env)
        self.assertEqual(result["count"], 1)
        self.assertNotIn("normalized_input_feed", result["snapshots"][0])

    def test_47_snapshot_list_with_payload(self):
        self._persist()
        result = store.list_feed_snapshots(path=self.path, env=self.env, include_payload=True)
        self.assertEqual(result["snapshots"][0]["normalized_input_feed"], {"offers": [{"x": 1}]})

    def test_48_snapshot_filter_provider(self):
        self._persist("demo")
        c = collection("backup", raw={"offers": [{"y": 2}]})
        store.persist_feed_snapshot(provider_id="backup", collection=c, feed_source=c["feed_source"], feed_format=c["feed_format"], odds_format=c["odds_format"], normalized_input_feed=c["raw_feed"], path=self.path, env=self.env)
        result = store.list_feed_snapshots(provider_id="demo", path=self.path, env=self.env)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["snapshots"][0]["provider_id"], "demo")

    def test_49_store_status_counts_attempts(self):
        store.append_feed_attempt(provider_id="demo", failover_rank=1, started_at_utc=NOW, outcome="not_ready", path=self.path, env=self.env)
        status = store.get_store_status(path=self.path, env=self.env)
        self.assertEqual(status["attempt_count"], 1)
        self.assertEqual(status["successful_attempt_count"], 0)

    def test_50_health_no_attempts(self):
        result = store.get_provider_health("demo", path=self.path, env=self.env)
        self.assertFalse(result["providers"][0]["healthy"])

    def test_51_health_success(self):
        store.append_feed_attempt(provider_id="demo", failover_rank=1, started_at_utc=NOW, completed_at_utc=NOW, outcome="success", normalized_line_count=5, path=self.path, env=self.env)
        now = datetime(2026, 8, 26, 20, 10, tzinfo=timezone.utc)
        health = store.get_provider_health("demo", now_utc=now, path=self.path, env=self.env)["providers"][0]
        self.assertTrue(health["healthy"])
        self.assertEqual(health["consecutive_failures"], 0)

    def test_52_health_failure_streak(self):
        store.append_feed_attempt(provider_id="demo", failover_rank=1, started_at_utc=NOW, completed_at_utc="2026-08-26T20:00:00+00:00", outcome="success", path=self.path, env=self.env)
        store.append_feed_attempt(provider_id="demo", failover_rank=1, started_at_utc=NOW, completed_at_utc="2026-08-26T20:01:00+00:00", outcome="upstream_error", path=self.path, env=self.env)
        store.append_feed_attempt(provider_id="demo", failover_rank=1, started_at_utc=NOW, completed_at_utc="2026-08-26T20:02:00+00:00", outcome="not_ready", path=self.path, env=self.env)
        now = datetime(2026, 8, 26, 20, 3, tzinfo=timezone.utc)
        health = store.get_provider_health("demo", now_utc=now, path=self.path, env=self.env)["providers"][0]
        self.assertEqual(health["consecutive_failures"], 2)

    def test_53_health_three_failures_marks_unhealthy(self):
        store.append_feed_attempt(provider_id="demo", failover_rank=1, started_at_utc=NOW, completed_at_utc="2026-08-26T20:00:00+00:00", outcome="success", path=self.path, env=self.env)
        for minute in (1, 2, 3):
            store.append_feed_attempt(provider_id="demo", failover_rank=1, started_at_utc=NOW, completed_at_utc=f"2026-08-26T20:0{minute}:00+00:00", outcome="upstream_error", path=self.path, env=self.env)
        now = datetime(2026, 8, 26, 20, 4, tzinfo=timezone.utc)
        self.assertFalse(store.get_provider_health("demo", now_utc=now, path=self.path, env=self.env)["providers"][0]["healthy"])

    def test_54_store_path_directory_rejected(self):
        with self.assertRaises(store.WNBAPropFeedStoreError):
            store.resolve_store_path(Path(self.tmp.name), self.env)

    # Order / failover
    def test_55_explicit_order_preserved(self):
        self.assertEqual(f.resolve_failover_order(["a", "b"], env={}), ["a", "b"])

    def test_56_explicit_order_deduped(self):
        self.assertEqual(f.resolve_failover_order(["a", "a", "b"], env={}), ["a", "b"])

    def test_57_env_order_used(self):
        self.assertEqual(f.resolve_failover_order(env={f.FAILOVER_ORDER_ENV: "b,a"}), ["b", "a"])

    def test_58_invalid_provider_id_rejected(self):
        with self.assertRaises(f.WNBAPropFeedFailoverModelInputError):
            f.resolve_failover_order(["bad id"], env={})

    def test_59_sgo_auto_first_when_ready(self):
        order = f.resolve_failover_order(env={sgo.SPORTSGAMEODDS_API_KEY_ENV: "x"})
        self.assertEqual(order[0], sgo.SPORTSGAMEODDS_PROVIDER_ID)

    def test_60_no_ready_provider_not_ready(self):
        with self.assertRaises(f.WNBAPropFeedFailoverNotReadyError):
            f.resolve_failover_order(env={})

    def test_61_onboarding_reports_persistent_path(self):
        env = {sgo.SPORTSGAMEODDS_API_KEY_ENV: "x", store.STORE_PATH_ENV: str(self.path)}
        result = f.describe_provider_onboarding(env)
        self.assertTrue(result["explicit_persistent_store_configured"])

    def test_62_durable_mode_requires_explicit_store(self):
        with self.assertRaises(f.WNBAPropFeedFailoverNotReadyError):
            f.collect_failover_line_board(["demo"], env={}, require_persistent_store=True)

    def _generic(self, behavior):
        calls = []
        def fn(provider_id, **kwargs):
            calls.append(provider_id)
            value = behavior[provider_id]
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)
        return fn, calls

    def test_63_first_provider_success_selected(self):
        generic, calls = self._generic({"a": collection("a")})
        result = f.collect_failover_line_board(["a"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=lambda *a, **k: line_board(2, 1))
        self.assertEqual(result["selected_provider_id"], "a")
        self.assertEqual(calls, ["a"])

    def test_64_not_ready_fails_over(self):
        generic, calls = self._generic({"a": WNBAPropFeedCollectorNotReadyError("rate limit"), "b": collection("b")})
        result = f.collect_failover_line_board(["a", "b"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=lambda *a, **k: line_board(2, 1))
        self.assertEqual(result["selected_provider_id"], "b")
        self.assertEqual([x["outcome"] for x in result["attempts"]], ["not_ready", "success"])

    def test_65_upstream_error_fails_over(self):
        generic, _ = self._generic({"a": WNBAPropFeedCollectorUpstreamError("down"), "b": collection("b")})
        result = f.collect_failover_line_board(["a", "b"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=lambda *a, **k: line_board(2, 1))
        self.assertEqual(result["selected_provider_id"], "b")
        self.assertEqual(result["attempts"][0]["outcome"], "upstream_error")

    def test_66_market_input_error_fails_over(self):
        generic, _ = self._generic({"a": collection("a"), "b": collection("b")})
        count = {"n": 0}
        def builder(*args, **kwargs):
            count["n"] += 1
            if count["n"] == 1:
                raise WNBAPropLineFeedModelInputError("bad market")
            return line_board(2, 1)
        result = f.collect_failover_line_board(["a", "b"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=builder)
        self.assertEqual(result["selected_provider_id"], "b")
        self.assertEqual(result["attempts"][0]["outcome"], "market_input_error")

    def test_67_empty_board_with_games_fails_over(self):
        generic, _ = self._generic({"a": collection("a"), "b": collection("b")})
        count = {"n": 0}
        def builder(*args, **kwargs):
            count["n"] += 1
            return line_board(0, 1) if count["n"] == 1 else line_board(2, 1)
        result = f.collect_failover_line_board(["a", "b"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=builder)
        self.assertEqual(result["attempts"][0]["outcome"], "unusable_empty_board")
        self.assertEqual(result["selected_provider_id"], "b")

    def test_68_empty_slate_is_success(self):
        generic, _ = self._generic({"a": collection("a")})
        result = f.collect_failover_line_board(["a"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=lambda *a, **k: line_board(0, 0))
        self.assertEqual(result["attempts"][0]["outcome"], "success_empty_slate")

    def test_69_minimum_zero_accepts_empty_with_games(self):
        generic, _ = self._generic({"a": collection("a")})
        result = f.collect_failover_line_board(["a"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=lambda *a, **k: line_board(0, 1), minimum_normalized_lines=0)
        self.assertEqual(result["selected_provider_id"], "a")

    def test_70_exhausted_chain_not_ready(self):
        generic, _ = self._generic({"a": WNBAPropFeedCollectorUpstreamError("down"), "b": WNBAPropFeedCollectorNotReadyError("limited")})
        with self.assertRaises(f.WNBAPropFeedFailoverNotReadyError):
            f.collect_failover_line_board(["a", "b"], env=self.env, store_path=self.path, generic_collector=generic)

    def test_71_successful_collection_snapshotted(self):
        generic, _ = self._generic({"a": collection("a")})
        result = f.collect_failover_line_board(["a"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=lambda *a, **k: line_board(2, 1))
        snapshots = store.list_feed_snapshots(path=self.path, env=self.env)
        self.assertEqual(snapshots["count"], 1)
        self.assertEqual(snapshots["snapshots"][0]["snapshot_id"], result["snapshot_reference"]["snapshot_id"])

    def test_72_collection_snapshotted_even_when_market_rejected(self):
        generic, _ = self._generic({"a": collection("a"), "b": collection("b")})
        count = {"n": 0}
        def builder(*args, **kwargs):
            count["n"] += 1
            return line_board(0, 1) if count["n"] == 1 else line_board(2, 1)
        f.collect_failover_line_board(["a", "b"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=builder)
        self.assertEqual(store.list_feed_snapshots(path=self.path, env=self.env)["count"], 2)

    def test_73_failed_http_collection_not_snapshotted(self):
        generic, _ = self._generic({"a": WNBAPropFeedCollectorUpstreamError("down"), "b": collection("b")})
        f.collect_failover_line_board(["a", "b"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=lambda *a, **k: line_board(2, 1))
        self.assertEqual(store.list_feed_snapshots(path=self.path, env=self.env)["count"], 1)

    def test_74_failover_attempt_history_persisted(self):
        generic, _ = self._generic({"a": WNBAPropFeedCollectorUpstreamError("down"), "b": collection("b")})
        f.collect_failover_line_board(["a", "b"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=lambda *a, **k: line_board(2, 1))
        status = store.get_store_status(path=self.path, env=self.env)
        self.assertEqual(status["attempt_count"], 2)
        self.assertEqual(status["successful_attempt_count"], 1)

    def test_75_selected_rank_is_reported(self):
        generic, _ = self._generic({"a": WNBAPropFeedCollectorUpstreamError("down"), "b": collection("b")})
        result = f.collect_failover_line_board(["a", "b"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=lambda *a, **k: line_board(2, 1))
        self.assertEqual(result["selected_failover_rank"], 2)

    def test_76_failover_fingerprint_sha256(self):
        generic, _ = self._generic({"a": collection("a")})
        result = f.collect_failover_line_board(["a"], env=self.env, store_path=self.path, generic_collector=generic, line_board_builder=lambda *a, **k: line_board(2, 1))
        self.assertEqual(len(result["failover_fingerprint_sha256"]), 64)

    def test_77_daily_builder_receives_step5l_prop_lines(self):
        fake_failover = {
            "failover_id": "f1", "failover_fingerprint_sha256": "a" * 64,
            "selected_provider_id": "a", "selected_failover_rank": 1,
            "snapshot_reference": {"snapshot_id": "s1"},
            "line_board": line_board(2, 1),
        }
        seen = {}
        def fb(*args, **kwargs): return copy.deepcopy(fake_failover)
        def daily(lines, **kwargs):
            seen["lines"] = lines
            seen.update(kwargs)
            return {"daily_board_fingerprint_sha256": "d" * 64, "probability_board": [{"rank": 1}], "value_board": []}
        result = f.build_failover_daily_top_five(["a"], failover_builder=fb, daily_builder=daily, require_persistent_store=False)
        self.assertEqual(seen["lines"][0]["player_id"], 1)
        self.assertEqual(result["probability_board_count"], 1)

    def test_78_daily_empty_slate_skips_daily_builder(self):
        fake_failover = {
            "failover_id": "f1", "failover_fingerprint_sha256": "a" * 64,
            "selected_provider_id": "a", "selected_failover_rank": 1,
            "snapshot_reference": {"snapshot_id": "s1"},
            "line_board": line_board(0, 0),
        }
        called = {"v": False}
        def fb(*args, **kwargs): return copy.deepcopy(fake_failover)
        def daily(*args, **kwargs): called["v"] = True
        result = f.build_failover_daily_top_five(["a"], failover_builder=fb, daily_builder=daily, require_persistent_store=False)
        self.assertFalse(called["v"])
        self.assertEqual(result["probability_board_count"], 0)

    def test_79_daily_probability_rank_semantic_frozen(self):
        fake_failover = {"failover_id": "f1", "failover_fingerprint_sha256": "a" * 64, "selected_provider_id": "a", "selected_failover_rank": 1, "snapshot_reference": {"snapshot_id": "s1"}, "line_board": line_board(0, 0)}
        result = f.build_failover_daily_top_five(["a"], failover_builder=lambda *a, **k: copy.deepcopy(fake_failover), require_persistent_store=False)
        self.assertTrue(result["semantics"]["frozen_step_5k_remains_primary_probability_rank_authority"])

    def test_80_health_wrapper_includes_store_status(self):
        result = f.get_failover_health(store_path=self.path, env=self.env)
        self.assertIn("provider_health", result)
        self.assertIn("store_status", result)

    # API / wiring
    def test_81_provider_ids_parser(self):
        self.assertEqual(api._provider_ids("a,b"), ["a", "b"])

    def test_82_provider_ids_parser_rejects_empty(self):
        with self.assertRaises(ValueError): api._provider_ids(",,")

    def test_83_api_model_input_maps_422(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(f.WNBAPropFeedFailoverModelInputError("bad"))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_84_api_not_ready_maps_409(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(f.WNBAPropFeedFailoverNotReadyError("not ready"))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_85_api_upstream_maps_502(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(f.WNBAPropFeedFailoverUpstreamError("down"))
        self.assertEqual(ctx.exception.status_code, 502)

    def test_86_api_store_maps_500(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(f.WNBAPropFeedFailoverStoreError("store"))
        self.assertEqual(ctx.exception.status_code, 500)

    def test_87_router_has_all_step5o_paths(self):
        paths = {route.path for route in api.router.routes}
        expected = {
            "/api/v1/wnba/markets/player-props/providers/onboarding",
            "/api/v1/wnba/markets/player-props/collection-store/status",
            "/api/v1/wnba/markets/player-props/collection-store/health",
            "/api/v1/wnba/markets/player-props/collection-store/snapshots",
            "/api/v1/wnba/markets/player-props/collect/failover/line-board",
            "/api/v1/wnba/rankings/player-props/collect/failover/daily-top-five",
        }
        self.assertEqual(paths, expected)

    def test_88_main_wires_step5o_router(self):
        main_source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn("wnba_prop_feed_failover_router", main_source)
        self.assertIn("app.include_router(wnba_prop_feed_failover_router)", main_source)


if __name__ == "__main__":
    unittest.main()
