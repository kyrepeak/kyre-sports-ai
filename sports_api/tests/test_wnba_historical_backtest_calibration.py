import copy
from datetime import datetime, timezone, timedelta
import math
import unittest
from unittest.mock import patch

import sports_api.wnba_historical_backtest_calibration as h

SECRET = "s" * 32
TIP = datetime(2026, 8, 26, 23, 0, tzinfo=timezone.utc)


def snap(*, side="away", role="mostly_starter", rest=1, b2b=False):
    team, opp = "SEA", "PHX"
    s = {
        "schema_version": "wnba_step_4w_v1", "season": 2026,
        "season_type": "Regular Season", "game_id": "1022600001",
        "player_id": 123, "recent_window_games": 5,
        "game_identity": {
            "game_id": "1022600001", "date": "2026-08-26",
            "away_team_key": team if side == "away" else opp,
            "home_team_key": team if side == "home" else opp,
            "game_datetime_utc": TIP.isoformat(),
            "game_datetime_eastern": None, "venue": None, "status": None,
            "schedule_change": None,
        },
        "focal_identity": {
            "player_id": 123, "team_key": team, "side": side,
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
    content = {k: s[k] for k in (
        "schema_version", "season", "season_type", "game_id", "player_id",
        "recent_window_games", "game_identity", "focal_identity",
        "component_status", "inputs",
    )}
    s["content_sha256"] = h._canonical_hash(content)
    return s


def scenario(name, stat, line, mean, p):
    return {
        "conditional_scenario": name, "stat": stat, "line": line,
        "raw_probabilities": {
            "over": {"probability": p},
            "under": {"probability": 1-p},
            "push": {"probability": 0.0},
        },
        "fair_odds": {
            "over": {"available": True, "fair_probability": p},
            "under": {"available": True, "fair_probability": 1-p},
        },
        "source_distribution_summary": {"mean": mean},
    }


def threshold(s=None, *, stat="points", line=19.5, p=.60):
    s = s or snap()
    means = {
        "points": (16., 20., 24.), "rebounds": (5., 7., 9.),
        "assists": (3., 5., 7.), "pra": (25., 32., 39.),
    }[stat]
    probs = (max(.01, p-.20), p, min(.99, p+.18))
    results = {
        k: scenario(k, stat, line, means[i], probs[i])
        for i, k in enumerate(("low", "base", "high"))
    }
    t = {
        "model_version": h.THRESHOLD_MODEL_VERSION, "player_id": 123,
        "game_id": "1022600001", "team_key": "SEA",
        "opponent_team_key": "PHX", "season": 2026,
        "season_type": "Regular Season",
        "generated_at_utc": (TIP - timedelta(hours=1, minutes=30)).isoformat(),
        "prop": {"stat": stat, "line": line},
        "conditional_scenario_results": results,
        "primary_result": copy.deepcopy(results["base"]),
        "scenario_sensitivity": {"fixture": True},
        "model_config": {"fixture": True},
        "step_5e_reference": {"simulation_fingerprint_sha256": "a"*64},
        "snapshot_reference": {
            k: s[k] for k in (
                "snapshot_id", "content_sha256", "captured_at_utc",
                "finalized_at_utc", "season", "season_type", "game_id",
                "player_id", "recent_window_games",
            )
        },
        "probability_id": "prob-1",
    }
    t["probability_fingerprint_sha256"] = h._canonical_hash({
        "step_5e_simulation_fingerprint_sha256": "a"*64,
        "model_config": t["model_config"],
        "conditional_threshold_results": results,
        "scenario_sensitivity": t["scenario_sensitivity"],
    })
    return t


def game_log(*, pts=22, reb=7, ast=5, minutes=32.5):
    return {
        "player_id": 123, "season": 2026, "season_type": "Regular Season",
        "games": [{
            "game_id": "1022600001", "game_date": "2026-08-26",
            "minutes": minutes, "points": pts, "rebounds": reb, "assists": ast,
            "result": "W",
            "matchup": {"team_key": "SEA", "opponent_team_key": "PHX"},
        }],
    }


def archive(*, stat="points", line=19.5, p=.60, snapshot=None):
    s = snapshot or snap()
    return h.build_pregame_archive_envelope(
        threshold(s, stat=stat, line=line, p=p), s,
        archived_at_utc=TIP-timedelta(hours=1), signing_secret=SECRET,
    )


def obs(*, stat="points", line=19.5, p=.60, pts=22, reb=7, ast=5, snapshot=None):
    return h.grade_archived_prediction(
        archive(stat=stat, line=line, p=p, snapshot=snapshot),
        game_log(pts=pts, reb=reb, ast=ast),
        signing_secret=SECRET,
    )


def rehash(o):
    o = copy.deepcopy(o)
    o["observation_content_sha256"] = h._canonical_hash(o["content"])
    return o


class Step5IExplicitTests(unittest.TestCase):
    def test_01_signed_archive(self):
        self.assertTrue(archive()["signature"]["signed"])

    def test_02_unsigned_not_audit_grade(self):
        s = snap()
        a = h.build_pregame_archive_envelope(
            threshold(s), s, archived_at_utc=TIP-timedelta(hours=1), signing_secret=None
        )
        self.assertFalse(a["trust"]["audit_grade_candidate"])

    def test_03_wrong_secret(self):
        with self.assertRaises(h.WNBAHistoricalBacktestUpstreamError):
            h._verify_archive_envelope(
                archive(), signing_secret="z"*32, require_audit_grade=True
            )

    def test_04_unsigned_rejected_when_strict(self):
        s = snap()
        a = h.build_pregame_archive_envelope(
            threshold(s), s, archived_at_utc=TIP-timedelta(hours=1), signing_secret=None
        )
        with self.assertRaises(h.WNBAHistoricalBacktestNotReadyError):
            h._verify_archive_envelope(a, signing_secret=None, require_audit_grade=True)

    def test_05_snapshot_tamper(self):
        s = snap()
        t = threshold(s)
        s["inputs"]["tamper"] = True
        with self.assertRaises(h.WNBAHistoricalBacktestUpstreamError):
            h.build_pregame_archive_envelope(
                t, s, archived_at_utc=TIP-timedelta(hours=1), signing_secret=SECRET
            )

    def test_06_threshold_tamper(self):
        s = snap(); t = threshold(s)
        t["conditional_scenario_results"]["base"]["source_distribution_summary"]["mean"] = 99
        with self.assertRaises(h.WNBAHistoricalBacktestUpstreamError):
            h.build_pregame_archive_envelope(
                t, s, archived_at_utc=TIP-timedelta(hours=1), signing_secret=SECRET
            )

    def test_07_post_tip_probability_blocks(self):
        s = snap(); t = threshold(s)
        t["generated_at_utc"] = TIP.isoformat()
        with self.assertRaises(h.WNBAHistoricalBacktestNotReadyError):
            h.build_pregame_archive_envelope(
                t, s, archived_at_utc=TIP-timedelta(hours=1), signing_secret=SECRET
            )

    def test_08_post_tip_archive_blocks(self):
        s = snap()
        with self.assertRaises(h.WNBAHistoricalBacktestNotReadyError):
            h.build_pregame_archive_envelope(
                threshold(s), s, archived_at_utc=TIP, signing_secret=SECRET
            )

    def test_09_context_home(self):
        a = archive(snapshot=snap(side="home"))
        self.assertEqual(a["content"]["context"]["home_away"], "home")

    def test_10_context_role(self):
        a = archive(snapshot=snap(role="mostly_bench"))
        self.assertEqual(a["content"]["context"]["pregame_observed_role_band"], "mostly_bench")

    def test_11_context_b2b(self):
        a = archive(snapshot=snap(rest=0, b2b=True))
        self.assertEqual(a["content"]["context"]["rest_bucket"], "back_to_back_second_night")

    def test_12_grade_over(self):
        self.assertEqual(obs(pts=22)["content"]["actual"]["settlement"], "over")

    def test_13_grade_under(self):
        self.assertEqual(obs(pts=18)["content"]["actual"]["settlement"], "under")

    def test_14_grade_push(self):
        self.assertEqual(obs(line=20.0, pts=20)["content"]["actual"]["settlement"], "push")

    def test_15_push_not_binary(self):
        score = obs(line=20.0, pts=20)["content"]["probability_scoring"]
        self.assertFalse(score["eligible_resolved_non_push"])
        self.assertIsNone(score["brier_score"])

    def test_16_brier(self):
        self.assertAlmostEqual(obs(p=.60)["content"]["probability_scoring"]["brier_score"], .16)

    def test_17_log_loss(self):
        self.assertAlmostEqual(
            obs(p=.60)["content"]["probability_scoring"]["log_loss"], -math.log(.60), places=9
        )

    def test_18_pra_recomputed(self):
        self.assertEqual(obs(pts=22, reb=8, ast=6)["content"]["actual"]["pra"], 36)

    def test_19_zero_minutes_not_ready(self):
        with self.assertRaises(h.WNBAHistoricalBacktestNotReadyError):
            h.grade_archived_prediction(archive(), game_log(minutes=0), signing_secret=SECRET)

    def test_20_official_result_identity(self):
        gl = game_log(); gl["games"][0]["matchup"]["team_key"] = "PHX"
        with self.assertRaises(h.WNBAHistoricalBacktestUpstreamError):
            h.grade_archived_prediction(archive(), gl, signing_secret=SECRET)

    def test_21_wrapper_fetches_once(self):
        with patch.object(h, "get_player_game_log_dataset", return_value=game_log()) as getter:
            h.get_graded_archived_prediction(archive(), signing_secret=SECRET)
        getter.assert_called_once()

    def test_22_wrapper_not_found_translation(self):
        with patch.object(h, "get_player_game_log_dataset", side_effect=h.WNBAHistoryNotFoundError("x")):
            with self.assertRaises(h.WNBAHistoricalBacktestNotFoundError):
                h.get_graded_archived_prediction(archive(), signing_secret=SECRET)

    def test_23_observation_tamper(self):
        o = obs(); o["content"]["actual"]["points"] = 99
        with self.assertRaises(h.WNBAHistoricalBacktestUpstreamError):
            h.evaluate_backtest_observations([o])

    def test_24_one_record_mae(self):
        r = h.evaluate_backtest_observations([obs()])
        self.assertEqual(r["pooled_report"]["projection_error"]["mae"], 2.0)

    def test_25_push_excluded_calibration(self):
        r = h.evaluate_backtest_observations([obs(line=20.0, pts=20), obs(line=19.5, pts=20)])
        self.assertEqual(r["pooled_report"]["probability"]["resolved_observation_count"], 1)

    def test_26_alternate_lines_dedupe_projection(self):
        r = h.evaluate_backtest_observations([obs(line=18.5, pts=20), obs(line=19.5, pts=20)])
        self.assertEqual(r["pooled_report"]["projection_observation_count"], 1)

    def test_27_mixed_versions_reject(self):
        a, b = obs(), obs(line=18.5)
        b["content"]["probability_model_version"] = "other"; b = rehash(b)
        with self.assertRaises(h.WNBAHistoricalBacktestModelInputError):
            h.evaluate_backtest_observations([a,b])

    def test_28_mixed_versions_separate(self):
        a, b = obs(), obs(line=18.5)
        b["content"]["probability_model_version"] = "other"; b = rehash(b)
        r = h.evaluate_backtest_observations(
            [a,b], require_single_probability_model_version=False
        )
        self.assertFalse(r["pooled_report_available"])

    def test_29_duplicate_hash_reject(self):
        a = obs()
        with self.assertRaises(h.WNBAHistoricalBacktestModelInputError):
            h.evaluate_backtest_observations([a, copy.deepcopy(a)])

    def test_30_report_order_invariant(self):
        a,b = obs(line=18.5, pts=20), obs(line=19.5, pts=20)
        x=h.evaluate_backtest_observations([a,b])
        y=h.evaluate_backtest_observations([b,a])
        self.assertEqual(x["calibration_report_fingerprint_sha256"], y["calibration_report_fingerprint_sha256"])

    def test_31_empty_reject(self):
        with self.assertRaises(ValueError):
            h.evaluate_backtest_observations([])

    def test_32_short_secret_reject(self):
        s=snap()
        with self.assertRaises(h.WNBAHistoricalBacktestModelInputError):
            h.build_pregame_archive_envelope(
                threshold(s), s, archived_at_utc=TIP-timedelta(hours=1), signing_secret="short"
            )


def _make_stat_test(stat):
    def test(self):
        row = obs(stat=stat, line={"points":19.5,"rebounds":6.5,"assists":4.5,"pra":31.5}[stat])
        self.assertEqual(row["content"]["prop"]["stat"], stat)
    return test


for i, stat in enumerate(("points","rebounds","assists","pra"), start=33):
    setattr(Step5IExplicitTests, f"test_{i:02d}_stat_{stat}", _make_stat_test(stat))


def _make_probability_bin_test(i):
    p = .05 + i*.10
    def test(self):
        row = obs(line=10.5+i/100.0, p=min(.95,p), pts=22)
        report = h.evaluate_backtest_observations([row])
        bins = report["pooled_report"]["probability"]["calibration"]["bins"]
        self.assertEqual(sum(b["resolved_observation_count"] for b in bins), 1)
    return test


for j in range(10):
    setattr(Step5IExplicitTests, f"test_{37+j:02d}_calibration_bin_{j}", _make_probability_bin_test(j))


def _make_valid_lead_test(i):
    def test(self):
        s=snap()
        a=h.build_pregame_archive_envelope(
            threshold(s), s, archived_at_utc=TIP-timedelta(minutes=5+i), signing_secret=SECRET
        )
        self.assertGreater(a["content"]["lead_time_minutes"]["archive_creation_to_tip"], 0)
    return test


for j in range(10):
    setattr(Step5IExplicitTests, f"test_{47+j:02d}_valid_lead_{j}", _make_valid_lead_test(j))


def _make_line_settlement_test(i):
    line = 15.5 + i
    def test(self):
        value = 20
        row = obs(line=line, pts=value)
        expected = "over" if value > line else ("under" if value < line else "push")
        self.assertEqual(row["content"]["actual"]["settlement"], expected)
    return test


for j in range(10):
    setattr(Step5IExplicitTests, f"test_{57+j:02d}_line_settlement_{j}", _make_line_settlement_test(j))


def _make_slice_test(i):
    roles=("mostly_starter","mostly_bench","mixed_starter_bench_history","unresolved")
    role=roles[i%4]
    rest=i%4
    side="home" if i%2 else "away"
    def test(self):
        row=obs(snapshot=snap(side=side,role=role,rest=rest))
        report=h.evaluate_backtest_observations([row])["pooled_report"]
        self.assertIn(side, report["bias_slices"]["by_home_away"])
        self.assertIn(role, report["bias_slices"]["by_pregame_observed_role_band"])
    return test


for j in range(10):
    setattr(Step5IExplicitTests, f"test_{67+j:02d}_slice_{j}", _make_slice_test(j))


def _make_integrity_test(i):
    def test(self):
        row=obs(line=18.5+i/100.0)
        row["content"]["projection_error"]["signed_error_prediction_minus_actual"] += 1
        row=rehash(row)
        with self.assertRaises(h.WNBAHistoricalBacktestUpstreamError):
            h.evaluate_backtest_observations([row])
    return test


for j in range(8):
    setattr(Step5IExplicitTests, f"test_{77+j:02d}_integrity_{j}", _make_integrity_test(j))


if __name__ == "__main__":
    unittest.main()
