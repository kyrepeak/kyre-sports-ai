from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from sports_api import wnba_step10_live_market_input as market


EVALUATED_AT = datetime(2026, 8, 28, 5, 10, 0, tzinfo=timezone.utc)


def _enabled_env() -> dict[str, str]:
    return {
        "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
    }


def _record(**overrides) -> dict:
    result = {
        "game_id": "1022600291",
        "player_id": 1642301,
        "player_name": "Certification Player",
        "sportsbook": "Book A",
        "stat": "points",
        "line": 20.5,
        "over_odds": -110,
        "under_odds": -110,
        "market_captured_at_utc": "2026-08-28T05:09:30+00:00",
    }
    result.update(overrides)
    return result


class Step10LiveMarketInputTests(unittest.TestCase):
    def test_flag_is_default_off(self) -> None:
        self.assertFalse(market.step10a_live_market_input_enabled({}))

    def test_production_switch_fails_closed(self) -> None:
        env = _enabled_env()
        env["WNBA_PRODUCTION_RUNTIME_ENABLED"] = "true"
        with self.assertRaises(market.WNBAStep10LiveMarketInputDisabledError):
            market.build_step10a_live_market_input_snapshot(
                [_record()], evaluated_at=EVALUATED_AT, env=env
            )

    def test_happy_path_normalizes_stat_timestamp_and_snapshot_counts(self) -> None:
        records = [
            _record(stat="PTS", market_captured_at_utc="2026-08-28T01:09:30-04:00"),
            _record(
                sportsbook="Book B",
                line=21.5,
                over_odds=105,
                under_odds=-125,
                market_captured_at_utc="2026-08-28T05:09:40Z",
            ),
            _record(
                player_id=1642302,
                player_name="Second Player",
                sportsbook="Book A",
                stat="rebs",
                line=10.5,
                market_captured_at_utc="2026-08-28T05:09:50+00:00",
            ),
        ]
        result = market.build_step10a_live_market_input_snapshot(
            records, evaluated_at=EVALUATED_AT, env=_enabled_env()
        )
        self.assertEqual(result["schema_version"], market.SCHEMA_VERSION)
        self.assertEqual(result["records"][0]["stat"], "points")
        self.assertTrue(result["records"][0]["market_captured_at_utc"].endswith("+00:00"))
        snapshot = result["snapshot"]
        self.assertEqual(snapshot["record_count"], 3)
        self.assertEqual(snapshot["unique_game_count"], 1)
        self.assertEqual(snapshot["unique_player_game_count"], 2)
        self.assertEqual(snapshot["unique_sportsbook_count"], 2)
        self.assertEqual(snapshot["unique_stat_count"], 2)
        self.assertEqual(snapshot["capture_spread_seconds"], 20.0)
        self.assertEqual(len(result["snapshot_content_sha256"]), 64)

    def test_duplicate_same_book_game_player_stat_line_is_rejected(self) -> None:
        records = [
            _record(),
            _record(market_captured_at_utc="2026-08-28T05:09:40+00:00"),
        ]
        with self.assertRaises(market.WNBAStep10LiveMarketInputDuplicateError):
            market.build_step10a_live_market_input_snapshot(
                records, evaluated_at=EVALUATED_AT, env=_enabled_env()
            )

    def test_duplicate_sportsbook_identity_is_case_insensitive(self) -> None:
        records = [
            _record(sportsbook="Book A"),
            _record(sportsbook="book a", market_captured_at_utc="2026-08-28T05:09:40+00:00"),
        ]
        with self.assertRaises(market.WNBAStep10LiveMarketInputDuplicateError):
            market.build_step10a_live_market_input_snapshot(
                records, evaluated_at=EVALUATED_AT, env=_enabled_env()
            )

    def test_alternative_line_from_same_sportsbook_is_allowed(self) -> None:
        result = market.build_step10a_live_market_input_snapshot(
            [
                _record(line=20.5),
                _record(line=19.5, market_captured_at_utc="2026-08-28T05:09:40+00:00"),
            ],
            evaluated_at=EVALUATED_AT,
            env=_enabled_env(),
        )
        self.assertEqual(result["snapshot"]["record_count"], 2)
        self.assertEqual([row["line"] for row in result["records"]], [19.5, 20.5])

    def test_conflicting_player_name_for_same_game_player_is_rejected(self) -> None:
        records = [
            _record(),
            _record(
                player_name="Different Player",
                sportsbook="Book B",
                market_captured_at_utc="2026-08-28T05:09:40+00:00",
            ),
        ]
        with self.assertRaises(market.WNBAStep10LiveMarketInputIdentityError):
            market.build_step10a_live_market_input_snapshot(
                records, evaluated_at=EVALUATED_AT, env=_enabled_env()
            )

    def test_unknown_and_missing_fields_are_rejected(self) -> None:
        unknown = _record()
        unknown["mystery"] = 1
        with self.assertRaises(ValueError):
            market.build_step10a_live_market_input_snapshot(
                [unknown], evaluated_at=EVALUATED_AT, env=_enabled_env()
            )
        missing = _record()
        missing.pop("over_odds")
        with self.assertRaises(ValueError):
            market.build_step10a_live_market_input_snapshot(
                [missing], evaluated_at=EVALUATED_AT, env=_enabled_env()
            )

    def test_invalid_identity_stat_line_and_odds_are_rejected(self) -> None:
        bad_records = [
            _record(game_id="123"),
            _record(player_id=0),
            _record(stat="blocks"),
            _record(line=-0.5),
            _record(over_odds=-99),
            _record(under_odds=100001),
        ]
        for record in bad_records:
            with self.subTest(record=record):
                with self.assertRaises(ValueError):
                    market.build_step10a_live_market_input_snapshot(
                        [record], evaluated_at=EVALUATED_AT, env=_enabled_env()
                    )

    def test_timezone_is_required_and_far_future_quote_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            market.build_step10a_live_market_input_snapshot(
                [_record(market_captured_at_utc="2026-08-28T05:09:30")],
                evaluated_at=EVALUATED_AT,
                env=_enabled_env(),
            )
        with self.assertRaises(ValueError):
            market.build_step10a_live_market_input_snapshot(
                [_record(market_captured_at_utc="2026-08-28T05:12:01+00:00")],
                evaluated_at=EVALUATED_AT,
                env=_enabled_env(),
            )

    def test_quote_age_is_evaluation_metadata_not_content_hash(self) -> None:
        first = market.build_step10a_live_market_input_snapshot(
            [_record()], evaluated_at=EVALUATED_AT, env=_enabled_env()
        )
        second = market.build_step10a_live_market_input_snapshot(
            [_record()],
            evaluated_at=EVALUATED_AT + timedelta(seconds=20),
            env=_enabled_env(),
        )
        self.assertNotEqual(
            first["records"][0]["market_age_seconds_at_evaluation"],
            second["records"][0]["market_age_seconds_at_evaluation"],
        )
        self.assertEqual(first["snapshot_content_sha256"], second["snapshot_content_sha256"])

    def test_input_order_does_not_change_output_content_hash(self) -> None:
        first_record = _record(sportsbook="Book B", line=21.5)
        second_record = _record(
            sportsbook="Book A",
            line=20.5,
            market_captured_at_utc="2026-08-28T05:09:40+00:00",
        )
        first = market.build_step10a_live_market_input_snapshot(
            [first_record, second_record], evaluated_at=EVALUATED_AT, env=_enabled_env()
        )
        second = market.build_step10a_live_market_input_snapshot(
            [deepcopy(second_record), deepcopy(first_record)],
            evaluated_at=EVALUATED_AT,
            env=_enabled_env(),
        )
        self.assertEqual(first["records"], second["records"])
        self.assertEqual(first["snapshot_content_sha256"], second["snapshot_content_sha256"])

    def test_empty_snapshot_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            market.build_step10a_live_market_input_snapshot(
                [], evaluated_at=EVALUATED_AT, env=_enabled_env()
            )

    def test_guardrails_keep_analytics_network_and_writes_off(self) -> None:
        result = market.build_step10a_live_market_input_snapshot(
            [_record()], evaluated_at=EVALUATED_AT, env=_enabled_env()
        )
        guards = result["guardrails"]
        self.assertTrue(guards["sportsbook_quote_consumed"])
        for key in (
            "basketball_projection_changed",
            "step8_distribution_changed",
            "step9_called",
            "sportsbook_network_fetch_performed",
            "sportsbook_adapter_applied",
            "vig_removed",
            "edge_calculated",
            "expected_value_calculated",
            "cross_sportsbook_consensus_calculated",
            "line_movement_calculated",
            "cross_prop_ranking_calculated",
            "supabase_mutated",
            "persistence_mutated",
            "scheduler_started",
            "production_runtime_enabled",
            "production_activation_allowed",
        ):
            self.assertFalse(guards[key], key)
        self.assertTrue(
            result["contract"]["step10c_owns_staleness_line_movement_and_snapshot_reconciliation"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
