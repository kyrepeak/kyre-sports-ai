from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from sports_api import wnba_step10_live_market_input as step10a
from sports_api import wnba_step10_market_adapters as step10b


EVALUATED_AT = datetime(2026, 8, 28, 5, 10, 0, tzinfo=timezone.utc)
SAFE_ENV = {
    "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
    "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
    "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
    "WNBA_BOARD_SCHEDULER_ENABLED": "false",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
    "WNBA_STEP6J_CANARY_ENABLED": "false",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
}


def flat_record(**changes):
    row = {
        "game_id": "1022600291",
        "player_id": 1642301,
        "player_name": "Certification Player",
        "sportsbook": "Book A",
        "stat": "pts",
        "line": 20.5,
        "over_price": -110,
        "under_price": -110,
        "market_captured_at": "2026-08-28T05:09:30Z",
    }
    row.update(changes)
    return row


def flat_payload(records=None, **changes):
    payload = {
        "provider": "Certification Flat Feed",
        "price_format": "american",
        "records": records if records is not None else [flat_record()],
    }
    payload.update(changes)
    return payload


def outcomes_market(**changes):
    market = {
        "game_id": "1022600291",
        "player_id": 1642302,
        "player_name": "Certification Rebounder",
        "sportsbook": "Book B",
        "stat": "reb",
        "market_captured_at": "2026-08-28T05:09:40+00:00",
        "outcomes": [
            {"side": "Over", "price": 2.0, "line": 10.5},
            {"side": "Under", "price": 1.8333333333, "line": 10.5},
        ],
    }
    market.update(changes)
    return market


def outcomes_payload(markets=None, **changes):
    payload = {
        "provider": "Certification Outcomes Feed",
        "price_format": "decimal",
        "markets": markets if markets is not None else [outcomes_market()],
    }
    payload.update(changes)
    return payload


class Step10MarketAdapterTests(unittest.TestCase):
    def test_flag_is_default_off(self):
        self.assertFalse(step10b.step10b_market_adapter_enabled({}))

    def test_production_switch_fails_closed(self):
        env = dict(SAFE_ENV, WNBA_PRODUCTION_RUNTIME_ENABLED="true")
        with self.assertRaises(step10b.WNBAStep10MarketAdapterDisabledError):
            step10b.adapt_step10b_market_payload(
                step10b.ADAPTER_FLAT_TWO_WAY_V1,
                flat_payload(),
                evaluated_at=EVALUATED_AT,
                env=env,
            )

    def test_frozen_step10a_gate_is_required(self):
        env = dict(SAFE_ENV, WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED="false")
        with self.assertRaises(step10b.WNBAStep10MarketAdapterDisabledError):
            step10b.adapt_step10b_market_payload(
                step10b.ADAPTER_FLAT_TWO_WAY_V1,
                flat_payload(),
                evaluated_at=EVALUATED_AT,
                env=env,
            )

    def test_flat_adapter_maps_aliases_into_exact_step10a_contract(self):
        result = step10b.adapt_step10b_market_payload(
            step10b.ADAPTER_FLAT_TWO_WAY_V1,
            flat_payload(),
            evaluated_at=EVALUATED_AT,
            env=SAFE_ENV,
        )
        self.assertEqual(result["schema_version"], step10b.SCHEMA_VERSION)
        self.assertEqual(result["adapter"]["provider"], "Certification Flat Feed")
        self.assertEqual(result["step10a_snapshot"]["schema_version"], step10a.SCHEMA_VERSION)
        row = result["step10a_snapshot"]["records"][0]
        self.assertEqual(row["stat"], "points")
        self.assertEqual(row["over_odds"], -110)
        self.assertEqual(row["under_odds"], -110)
        self.assertEqual(row["market_captured_at_utc"], "2026-08-28T05:09:30+00:00")

    def test_outcomes_adapter_is_side_order_independent(self):
        market = outcomes_market()
        forward = step10b.adapt_step10b_market_payload(
            step10b.ADAPTER_OUTCOMES_TWO_WAY_V1,
            outcomes_payload([market]),
            evaluated_at=EVALUATED_AT,
            env=SAFE_ENV,
        )
        reversed_market = deepcopy(market)
        reversed_market["outcomes"] = list(reversed(reversed_market["outcomes"]))
        reverse = step10b.adapt_step10b_market_payload(
            step10b.ADAPTER_OUTCOMES_TWO_WAY_V1,
            outcomes_payload([reversed_market]),
            evaluated_at=EVALUATED_AT,
            env=SAFE_ENV,
        )
        self.assertEqual(
            forward["step10a_snapshot"]["snapshot_content_sha256"],
            reverse["step10a_snapshot"]["snapshot_content_sha256"],
        )
        self.assertEqual(forward["adapter_content_sha256"], reverse["adapter_content_sha256"])

    def test_decimal_prices_convert_to_american(self):
        result = step10b.adapt_step10b_market_payload(
            step10b.ADAPTER_OUTCOMES_TWO_WAY_V1,
            outcomes_payload(),
            evaluated_at=EVALUATED_AT,
            env=SAFE_ENV,
        )
        row = result["step10a_snapshot"]["records"][0]
        self.assertEqual(row["over_odds"], 100)
        self.assertEqual(row["under_odds"], -120)

    def test_mixed_outcome_lines_are_rejected(self):
        market = outcomes_market()
        market["outcomes"][1]["line"] = 11.5
        with self.assertRaises(step10b.WNBAStep10MarketAdapterPayloadError):
            step10b.adapt_step10b_market_payload(
                step10b.ADAPTER_OUTCOMES_TWO_WAY_V1,
                outcomes_payload([market]),
                evaluated_at=EVALUATED_AT,
                env=SAFE_ENV,
            )

    def test_missing_or_duplicate_outcome_side_is_rejected(self):
        for outcomes in (
            [{"side": "Over", "price": -110, "line": 10.5}],
            [
                {"side": "Over", "price": -110, "line": 10.5},
                {"side": "over", "price": -105, "line": 10.5},
            ],
        ):
            market = outcomes_market(outcomes=outcomes)
            with self.subTest(outcomes=outcomes), self.assertRaises(
                step10b.WNBAStep10MarketAdapterPayloadError
            ):
                step10b.adapt_step10b_market_payload(
                    step10b.ADAPTER_OUTCOMES_TWO_WAY_V1,
                    outcomes_payload([market], price_format="american"),
                    evaluated_at=EVALUATED_AT,
                    env=SAFE_ENV,
                )

    def test_unknown_adapter_is_rejected(self):
        with self.assertRaises(step10b.WNBAStep10MarketAdapterPayloadError):
            step10b.adapt_step10b_market_payload(
                "mystery_feed_v9", flat_payload(), evaluated_at=EVALUATED_AT, env=SAFE_ENV
            )

    def test_unknown_payload_and_record_fields_are_rejected(self):
        payload = flat_payload()
        payload["mystery"] = True
        with self.assertRaises(step10b.WNBAStep10MarketAdapterPayloadError):
            step10b.adapt_step10b_market_payload(
                step10b.ADAPTER_FLAT_TWO_WAY_V1,
                payload,
                evaluated_at=EVALUATED_AT,
                env=SAFE_ENV,
            )
        row = flat_record(mystery=True)
        with self.assertRaises(step10b.WNBAStep10MarketAdapterPayloadError):
            step10b.adapt_step10b_market_payload(
                step10b.ADAPTER_FLAT_TWO_WAY_V1,
                flat_payload([row]),
                evaluated_at=EVALUATED_AT,
                env=SAFE_ENV,
            )

    def test_unsupported_price_format_and_bad_decimal_are_rejected(self):
        with self.assertRaises(step10b.WNBAStep10MarketAdapterPayloadError):
            step10b.adapt_step10b_market_payload(
                step10b.ADAPTER_FLAT_TWO_WAY_V1,
                flat_payload(price_format="fractional"),
                evaluated_at=EVALUATED_AT,
                env=SAFE_ENV,
            )
        payload = flat_payload(
            records=[flat_record(over_price=1.0, under_price=1.91)],
            price_format="decimal",
        )
        with self.assertRaises(step10b.WNBAStep10MarketAdapterPayloadError):
            step10b.adapt_step10b_market_payload(
                step10b.ADAPTER_FLAT_TWO_WAY_V1,
                payload,
                evaluated_at=EVALUATED_AT,
                env=SAFE_ENV,
            )

    def test_duplicate_quotes_are_rejected_by_frozen_step10a(self):
        rows = [flat_record(), flat_record(market_captured_at="2026-08-28T05:09:40Z")]
        with self.assertRaises(step10a.WNBAStep10LiveMarketInputDuplicateError):
            step10b.adapt_step10b_market_payload(
                step10b.ADAPTER_FLAT_TWO_WAY_V1,
                flat_payload(rows),
                evaluated_at=EVALUATED_AT,
                env=SAFE_ENV,
            )

    def test_alternative_lines_from_one_book_survive_adapter(self):
        rows = [flat_record(), flat_record(line=19.5, over_price=-125, under_price=105)]
        result = step10b.adapt_step10b_market_payload(
            step10b.ADAPTER_FLAT_TWO_WAY_V1,
            flat_payload(rows),
            evaluated_at=EVALUATED_AT,
            env=SAFE_ENV,
        )
        self.assertEqual(result["step10a_snapshot"]["snapshot"]["record_count"], 2)
        self.assertEqual(
            [row["line"] for row in result["step10a_snapshot"]["records"]],
            [19.5, 20.5],
        )

    def test_adapter_hash_is_stable_across_input_record_order(self):
        rows = [
            flat_record(),
            flat_record(sportsbook="Book B", over_price=-105, under_price=-115),
        ]
        first = step10b.adapt_step10b_market_payload(
            step10b.ADAPTER_FLAT_TWO_WAY_V1,
            flat_payload(rows),
            evaluated_at=EVALUATED_AT,
            env=SAFE_ENV,
        )
        second = step10b.adapt_step10b_market_payload(
            step10b.ADAPTER_FLAT_TWO_WAY_V1,
            flat_payload(list(reversed(rows))),
            evaluated_at=EVALUATED_AT,
            env=SAFE_ENV,
        )
        self.assertEqual(first["adapter_content_sha256"], second["adapter_content_sha256"])

    def test_guardrails_keep_model_market_math_network_and_writes_off(self):
        result = step10b.adapt_step10b_market_payload(
            step10b.ADAPTER_FLAT_TWO_WAY_V1,
            flat_payload(),
            evaluated_at=EVALUATED_AT,
            env=SAFE_ENV,
        )
        guards = result["guardrails"]
        self.assertTrue(guards["raw_provider_payload_consumed"])
        self.assertTrue(guards["sportsbook_adapter_applied"])
        for key in (
            "sportsbook_network_fetch_performed",
            "basketball_projection_changed",
            "step8_distribution_changed",
            "step9_called",
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

    def test_invalid_identity_and_timestamp_fail_through_step10a(self):
        for row in (
            flat_record(player_id=0),
            flat_record(market_captured_at="2026-08-28 05:09:30"),
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                step10b.adapt_step10b_market_payload(
                    step10b.ADAPTER_FLAT_TWO_WAY_V1,
                    flat_payload([row]),
                    evaluated_at=EVALUATED_AT,
                    env=SAFE_ENV,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
