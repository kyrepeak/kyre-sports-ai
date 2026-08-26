import copy
from datetime import datetime, timezone
from pathlib import Path
import unittest

from fastapi import HTTPException

import sports_api.api.wnba_prop_line_feed_adapter as api
import sports_api.wnba_prop_line_feed_adapter as m
from sports_api.wnba_rosters import WNBAStatsUpstreamError
from sports_api.wnba_schedule import WNBAScheduleUpstreamError

NOW = datetime(2026, 8, 26, 19, 0, 0, tzinfo=timezone.utc)
FRESH = "2026-08-26T18:58:00+00:00"
FRESH2 = "2026-08-26T18:59:00+00:00"
STALE = "2026-08-26T18:40:00+00:00"


def game(game_id="1022600001", away="SEA", home="PHX", *, playable=True):
    names = {
        "SEA": ("Seattle Storm", "Storm", "Seattle"),
        "PHX": ("Phoenix Mercury", "Mercury", "Phoenix"),
        "LAS": ("Los Angeles Sparks", "Sparks", "Los Angeles"),
        "ATL": ("Atlanta Dream", "Dream", "Atlanta"),
    }
    def team(key):
        full, nickname, city = names[key]
        return {
            "team_key": key,
            "full_name": full,
            "team_tricode": key,
            "team_name": nickname,
            "team_city": city,
        }
    return {
        "game_id": game_id,
        "away": team(away),
        "home": team(home),
        "verification": {"playable_pregame": playable},
    }


def slate(*games, integrity=True, date="2026-08-26", season=2026):
    games = list(games) or [game(), game("1022600002", "LAS", "ATL")]
    return {
        "season": season,
        "date": date,
        "verified_at_utc": "2026-08-26T18:59:30+00:00",
        "source_retrieved_at_utc": "2026-08-26T18:59:20+00:00",
        "slate": {
            "slate_integrity_pass": integrity,
            "blocking_reasons": [] if integrity else ["fixture_failure"],
        },
        "games": games,
    }


def roster(*, duplicate_name=False, season=2026):
    players = [
        {"player_id": 1, "full_name": "A'ja Wilson", "display_last_comma_first": "Wilson, A'ja", "team_key": "SEA"},
        {"player_id": 2, "full_name": "Player Two", "display_last_comma_first": "Two, Player", "team_key": "PHX"},
        {"player_id": 3, "full_name": "Player Three", "display_last_comma_first": "Three, Player", "team_key": "LAS"},
        {"player_id": 4, "full_name": "Player Four", "display_last_comma_first": "Four, Player", "team_key": "ATL"},
    ]
    if duplicate_name:
        players.append({"player_id": 5, "full_name": "Player Two", "display_last_comma_first": "Two, Player", "team_key": "SEA"})
    return {
        "season": season,
        "retrieved_at_utc": "2026-08-26T18:59:25+00:00",
        "player_count": len(players),
        "players": players,
    }


def offer(*, sportsbook="Book A", player_id=1, player_name=None, stat="points", side="over",
          line=19.5, odds=-110, captured=FRESH, home_team=None, away_team=None, **extra):
    row = {
        "sportsbook": sportsbook,
        "player_id": player_id,
        "stat": stat,
        "side": side,
        "line": line,
        "american_odds": odds,
        "market_captured_at_utc": captured,
    }
    if player_name is not None:
        row["player_name"] = player_name
    if home_team is not None:
        row["home_team"] = home_team
    if away_team is not None:
        row["away_team"] = away_team
    row.update(extra)
    return row


def canonical(*offers):
    return {"offers": list(offers)}


def two_way(*, sportsbook="Book A", player_id=1, player_name=None, stat="points", line=19.5,
            over=-110, under=-110, over_time=FRESH, under_time=FRESH, **extra):
    return canonical(
        offer(sportsbook=sportsbook, player_id=player_id, player_name=player_name, stat=stat,
              side="over", line=line, odds=over, captured=over_time, **extra),
        offer(sportsbook=sportsbook, player_id=player_id, player_name=player_name, stat=stat,
              side="under", line=line, odds=under, captured=under_time, **extra),
    )


def build(raw_feed, **kwargs):
    slate_value = kwargs.pop("slate_value", slate())
    roster_value = kwargs.pop("roster_value", roster())
    return m.build_prop_line_feed_board(
        raw_feed,
        feed_source=kwargs.pop("feed_source", "Fixture Feed"),
        feed_format=kwargs.pop("feed_format", m.CANONICAL_FEED_FORMAT),
        odds_format=kwargs.pop("odds_format", "american"),
        feed_captured_at_utc=kwargs.pop("feed_captured_at_utc", None),
        date=kwargs.pop("date", "2026-08-26"),
        season=kwargs.pop("season", 2026),
        now_utc=kwargs.pop("now_utc", NOW),
        slate_getter=lambda *a, **k: copy.deepcopy(slate_value),
        roster_getter=lambda *a, **k: copy.deepcopy(roster_value),
        **kwargs,
    )


def nested_feed(*, price_over=-110, price_under=-110, market_key="player_points",
                player_name="A'ja Wilson", point=19.5, last_update=FRESH):
    return {
        "events": [
            {
                "id": "provider-event-1",
                "home_team": "Phoenix Mercury",
                "away_team": "Seattle Storm",
                "bookmakers": [
                    {
                        "key": "book-a",
                        "title": "Book A",
                        "last_update": last_update,
                        "markets": [
                            {
                                "key": market_key,
                                "last_update": last_update,
                                "outcomes": [
                                    {"name": "Over", "description": player_name, "price": price_over, "point": point},
                                    {"name": "Under", "description": player_name, "price": price_under, "point": point},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }


class Step5MTests(unittest.TestCase):
    def test_01_basic_canonical_two_way(self):
        result = build(two_way())
        self.assertEqual(result["normalized_line_count"], 1)
        self.assertEqual(result["paired_two_way_quote_count"], 1)
        self.assertEqual(result["line_board"][0]["sportsbook_quotes"][0]["over_odds"], -110)

    def test_02_two_books_same_line(self):
        raw = canonical(
            *two_way(sportsbook="Book A")["offers"],
            *two_way(sportsbook="Book B", over=105, under=-125)["offers"],
        )
        result = build(raw)
        self.assertEqual(result["normalized_line_count"], 1)
        self.assertEqual(result["paired_two_way_quote_count"], 2)

    def test_03_one_sided_market_keeps_real_line(self):
        result = build(canonical(offer(side="over")))
        self.assertEqual(result["normalized_line_count"], 1)
        self.assertEqual(result["paired_two_way_quote_count"], 0)
        self.assertIsNone(result["step_5l_prop_lines"][0]["sportsbook_quotes"])

    def test_04_different_lines_remain_separate(self):
        raw = canonical(
            *two_way(line=18.5)["offers"],
            *two_way(sportsbook="Book B", line=19.5)["offers"],
        )
        result = build(raw)
        self.assertEqual([row["line"] for row in result["line_board"]], [18.5, 19.5])

    def test_05_same_book_different_lines_never_pair(self):
        raw = canonical(
            offer(side="over", line=18.5),
            offer(side="under", line=19.5),
        )
        result = build(raw)
        self.assertEqual(result["paired_two_way_quote_count"], 0)
        self.assertEqual(result["normalized_line_count"], 2)

    def test_06_points_alias(self):
        result = build(two_way(stat="PTS"))
        self.assertEqual(result["line_board"][0]["stat"], "points")

    def test_07_rebounds_market_alias(self):
        result = build(two_way(stat="player_rebounds"))
        self.assertEqual(result["line_board"][0]["stat"], "rebounds")

    def test_08_assists_alias(self):
        result = build(two_way(stat="AST"))
        self.assertEqual(result["line_board"][0]["stat"], "assists")

    def test_09_pra_alias(self):
        result = build(two_way(stat="player_points_rebounds_assists", line=31.5))
        self.assertEqual(result["line_board"][0]["stat"], "pra")

    def test_10_name_resolution_handles_punctuation(self):
        raw = two_way(player_id=None, player_name="Aja Wilson")
        result = build(raw)
        self.assertEqual(result["line_board"][0]["player_id"], 1)
        self.assertEqual(result["line_board"][0]["player_name"], "A'ja Wilson")

    def test_11_id_resolution_without_name(self):
        result = build(two_way(player_id=2))
        self.assertEqual(result["line_board"][0]["player_name"], "Player Two")

    def test_12_id_name_mismatch_excluded(self):
        result = build(two_way(player_id=1, player_name="Player Two"))
        self.assertEqual(result["normalized_line_count"], 0)
        self.assertIn("player_id_name_identity_mismatch", result["offer_audit"][0]["reason_codes"])

    def test_13_unknown_name_excluded(self):
        result = build(two_way(player_id=None, player_name="Nobody Here"))
        self.assertEqual(result["normalized_line_count"], 0)

    def test_14_missing_identity_excluded(self):
        raw = canonical(offer(player_id=None, player_name=None))
        result = build(raw)
        self.assertIn("player_identity_missing", result["offer_audit"][0]["reason_codes"])

    def test_15_team_off_slate_excluded(self):
        result = build(two_way(player_id=3), slate_value=slate(game()))
        self.assertEqual(result["normalized_line_count"], 0)
        self.assertIn("player_team_not_on_playable_pregame_slate", result["offer_audit"][0]["reason_codes"])

    def test_16_multiple_playable_games_for_team_excluded(self):
        s = slate(game("1022600001", "SEA", "PHX"), game("1022600003", "SEA", "ATL"))
        result = build(two_way(player_id=1), slate_value=s)
        self.assertEqual(result["normalized_line_count"], 0)
        self.assertIn("player_team_maps_to_multiple_playable_games", result["offer_audit"][0]["reason_codes"])

    def test_17_feed_event_team_mismatch_excluded(self):
        raw = two_way(player_id=1, home_team="Atlanta Dream", away_team="Los Angeles Sparks")
        result = build(raw)
        self.assertEqual(result["normalized_line_count"], 0)
        self.assertIn("feed_event_team_mismatch", result["offer_audit"][0]["reason_codes"])

    def test_18_valid_event_context_verified(self):
        raw = two_way(player_id=1, home_team="Phoenix Mercury", away_team="Seattle Storm")
        result = build(raw)
        self.assertTrue(result["offer_audit"][0]["event_verification"]["event_team_context_verified"])

    def test_19_unsupported_stat_excluded_not_global_failure(self):
        raw = canonical(offer(stat="blocks"), *two_way(player_id=2)["offers"])
        result = build(raw)
        self.assertEqual(result["normalized_line_count"], 1)
        self.assertIn("unsupported_or_missing_prop_stat", result["offer_audit"][0]["reason_codes"])

    def test_20_invalid_side_excluded(self):
        result = build(canonical(offer(side="yes")))
        self.assertIn("unsupported_or_missing_side", result["offer_audit"][0]["reason_codes"])

    def test_21_invalid_line_excluded(self):
        result = build(canonical(offer(line=-1)))
        self.assertIn("prop_line_missing_or_invalid", result["offer_audit"][0]["reason_codes"])

    def test_22_invalid_american_odds_excluded(self):
        result = build(canonical(offer(odds=-99)))
        self.assertIn("odds_missing_or_invalid", result["offer_audit"][0]["reason_codes"])

    def test_23_decimal_odds_convert_to_american(self):
        raw = {"offers": [
            {"sportsbook":"Book A","player_id":1,"stat":"points","side":"over","line":19.5,"decimal_odds":2.5,"market_captured_at_utc":FRESH},
            {"sportsbook":"Book A","player_id":1,"stat":"points","side":"under","line":19.5,"decimal_odds":1.5,"market_captured_at_utc":FRESH},
        ]}
        result = build(raw, odds_format="decimal")
        quote = result["line_board"][0]["sportsbook_quotes"][0]
        self.assertEqual(quote["over_odds"], 150)
        self.assertEqual(quote["under_odds"], -200)

    def test_24_positive_american_odds_preserved(self):
        result = build(two_way(over=125, under=-145))
        self.assertEqual(result["line_board"][0]["sportsbook_quotes"][0]["over_odds"], 125)

    def test_25_invalid_timestamp_excluded(self):
        result = build(canonical(offer(captured="yesterday")))
        self.assertIn("market_timestamp_missing_or_invalid", result["offer_audit"][0]["reason_codes"])

    def test_26_stale_excluded_by_default(self):
        result = build(two_way(over_time=STALE, under_time=STALE))
        self.assertEqual(result["normalized_line_count"], 0)
        self.assertEqual(result["stale_offer_count"], 2)

    def test_27_stale_can_be_retained_explicitly(self):
        result = build(two_way(over_time=STALE, under_time=STALE), exclude_stale_quotes=False)
        self.assertEqual(result["normalized_line_count"], 1)
        self.assertEqual(result["paired_two_way_quote_count"], 1)

    def test_28_far_future_timestamp_excluded(self):
        result = build(two_way(over_time="2026-08-26T19:03:00+00:00", under_time="2026-08-26T19:03:00+00:00"))
        self.assertEqual(result["normalized_line_count"], 0)
        self.assertIn("market_timestamp_too_far_in_future", result["offer_audit"][0]["reason_codes"])

    def test_29_future_within_tolerance_allowed(self):
        result = build(two_way(over_time="2026-08-26T19:01:00+00:00", under_time="2026-08-26T19:01:00+00:00"))
        self.assertEqual(result["normalized_line_count"], 1)

    def test_30_latest_duplicate_side_selected(self):
        raw = canonical(
            offer(side="over", odds=-120, captured=FRESH),
            offer(side="over", odds=110, captured=FRESH2),
            offer(side="under", odds=-130, captured=FRESH2),
        )
        result = build(raw)
        self.assertEqual(result["line_board"][0]["sportsbook_quotes"][0]["over_odds"], 110)

    def test_31_same_timestamp_conflicting_price_fails_closed(self):
        raw = canonical(
            offer(side="over", odds=-110, captured=FRESH2),
            offer(side="over", odds=105, captured=FRESH2),
            offer(side="under", odds=-120, captured=FRESH2),
        )
        result = build(raw)
        self.assertEqual(result["duplicate_conflict_count"], 1)
        self.assertEqual(result["paired_two_way_quote_count"], 0)

    def test_32_async_over_under_not_paired(self):
        result = build(
            two_way(over_time="2026-08-26T18:55:00+00:00", under_time="2026-08-26T18:59:00+00:00"),
            max_side_pair_skew_seconds=120,
        )
        self.assertEqual(result["normalized_line_count"], 1)
        self.assertEqual(result["paired_two_way_quote_count"], 0)
        self.assertEqual(result["two_way_pair_audit"][0]["reason"], "over_under_capture_skew_above_maximum")

    def test_33_exact_pair_skew_limit_allowed(self):
        result = build(
            two_way(over_time="2026-08-26T18:57:00+00:00", under_time="2026-08-26T18:59:00+00:00"),
            max_side_pair_skew_seconds=120,
        )
        self.assertEqual(result["paired_two_way_quote_count"], 1)

    def test_34_missing_sportsbook_excluded(self):
        result = build(canonical(offer(sportsbook="")))
        self.assertIn("sportsbook_missing_or_invalid", result["offer_audit"][0]["reason_codes"])

    def test_35_non_object_offer_audited(self):
        result = build({"offers": ["bad"]})
        self.assertEqual(result["raw_offer_count"], 1)
        self.assertIn("offer_not_object", result["offer_audit"][0]["reason_codes"])

    def test_36_bad_canonical_structure_rejected(self):
        with self.assertRaises(m.WNBAPropLineFeedModelInputError):
            build({"offers": "bad"})

    def test_37_bad_nested_structure_rejected(self):
        with self.assertRaises(m.WNBAPropLineFeedModelInputError):
            build({"events": "bad"}, feed_format=m.BOOKMAKER_EVENT_FEED_FORMAT)

    def test_38_nested_bookmaker_feed_extracts_market(self):
        result = build(nested_feed(), feed_format=m.BOOKMAKER_EVENT_FEED_FORMAT)
        self.assertEqual(result["normalized_line_count"], 1)
        self.assertEqual(result["paired_two_way_quote_count"], 1)
        self.assertEqual(result["line_board"][0]["player_id"], 1)

    def test_39_nested_bookmaker_title_used(self):
        result = build(nested_feed(), feed_format=m.BOOKMAKER_EVENT_FEED_FORMAT)
        self.assertEqual(result["line_board"][0]["sportsbook_quotes"][0]["sportsbook"], "Book A")

    def test_40_nested_data_alias_supported(self):
        raw = nested_feed()
        raw = {"data": raw["events"]}
        result = build(raw, feed_format=m.BOOKMAKER_EVENT_FEED_FORMAT)
        self.assertEqual(result["normalized_line_count"], 1)

    def test_41_feed_capture_fallback(self):
        raw = canonical(
            {"sportsbook":"Book A","player_id":1,"stat":"points","side":"over","line":19.5,"american_odds":-110},
            {"sportsbook":"Book A","player_id":1,"stat":"points","side":"under","line":19.5,"american_odds":-110},
        )
        result = build(raw, feed_captured_at_utc=FRESH)
        self.assertEqual(result["paired_two_way_quote_count"], 1)

    def test_42_invalid_feed_capture_rejected(self):
        with self.assertRaises(ValueError):
            build(two_way(), feed_captured_at_utc="bad")

    def test_43_invalid_feed_format_rejected(self):
        with self.assertRaises(ValueError):
            build(two_way(), feed_format="mystery")

    def test_44_invalid_odds_format_rejected(self):
        with self.assertRaises(ValueError):
            build(two_way(), odds_format="fractional")

    def test_45_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            build(two_way(), date="08/26/2026")

    def test_46_invalid_season_rejected(self):
        with self.assertRaises(ValueError):
            build(two_way(), season=0)

    def test_47_invalid_market_age_rejected(self):
        with self.assertRaises(ValueError):
            build(two_way(), max_market_age_minutes=0)

    def test_48_invalid_pair_skew_rejected(self):
        with self.assertRaises(ValueError):
            build(two_way(), max_side_pair_skew_seconds=4000)

    def test_49_slate_integrity_failure_blocks(self):
        with self.assertRaises(m.WNBAPropLineFeedNotReadyError):
            build(two_way(), slate_value=slate(integrity=False))

    def test_50_schedule_upstream_wrapped(self):
        def bad(*args, **kwargs):
            raise WNBAScheduleUpstreamError("schedule down")
        with self.assertRaises(m.WNBAPropLineFeedUpstreamError):
            m.build_prop_line_feed_board(
                two_way(), feed_source="Fixture", date="2026-08-26", now_utc=NOW,
                slate_getter=bad, roster_getter=lambda *a, **k: roster(),
            )

    def test_51_roster_upstream_wrapped(self):
        def bad(*args, **kwargs):
            raise WNBAStatsUpstreamError("roster down")
        with self.assertRaises(m.WNBAPropLineFeedUpstreamError):
            m.build_prop_line_feed_board(
                two_way(), feed_source="Fixture", date="2026-08-26", now_utc=NOW,
                slate_getter=lambda *a, **k: slate(), roster_getter=bad,
            )

    def test_52_fingerprint_deterministic_with_fixed_now(self):
        a = build(two_way())
        b = build(two_way())
        self.assertEqual(a["line_board_fingerprint_sha256"], b["line_board_fingerprint_sha256"])

    def test_53_fingerprint_changes_when_price_changes(self):
        a = build(two_way(over=-110))
        b = build(two_way(over=120))
        self.assertNotEqual(a["line_board_fingerprint_sha256"], b["line_board_fingerprint_sha256"])

    def test_54_step5l_handoff_shape(self):
        result = build(two_way())
        row = result["step_5l_prop_lines"][0]
        self.assertEqual(set(row), {"player_id", "stat", "line", "sportsbook_quotes"})

    def test_55_quote_timestamp_is_latest_side_capture(self):
        result = build(two_way(over_time=FRESH, under_time=FRESH2))
        self.assertEqual(
            result["line_board"][0]["sportsbook_quotes"][0]["market_captured_at_utc"],
            "2026-08-26T18:59:00+00:00",
        )

    def test_56_api_routes_registered(self):
        paths = {route.path for route in api.router.routes}
        self.assertIn("/api/v1/wnba/markets/player-props/line-board", paths)
        self.assertIn("/api/v1/wnba/rankings/player-props/feed-daily-top-five", paths)

    def test_57_api_model_input_maps_422(self):
        with self.assertRaises(HTTPException) as caught:
            api._raise_api_error(m.WNBAPropLineFeedModelInputError("bad"))
        self.assertEqual(caught.exception.status_code, 422)

    def test_58_api_not_ready_maps_409(self):
        with self.assertRaises(HTTPException) as caught:
            api._raise_api_error(m.WNBAPropLineFeedNotReadyError("wait"))
        self.assertEqual(caught.exception.status_code, 409)

    def test_59_api_upstream_maps_502(self):
        with self.assertRaises(HTTPException) as caught:
            api._raise_api_error(m.WNBAPropLineFeedUpstreamError("bad upstream"))
        self.assertEqual(caught.exception.status_code, 502)

    def test_60_pipeline_empty_line_board_is_clean(self):
        def line_builder(*args, **kwargs):
            return {
                "line_board_id": "x", "line_board_fingerprint_sha256": "a" * 64,
                "normalized_line_count": 0, "paired_two_way_quote_count": 0,
                "step_5l_prop_lines": [], "date": "2026-08-26",
            }
        result = m.build_feed_daily_top_five(
            {}, feed_source="Fixture", line_board_builder=line_builder,
            daily_builder=lambda *a, **k: self.fail("daily builder should not run"),
        )
        self.assertEqual(result["probability_board"], [])
        self.assertIsNone(result["step_5l_daily_top_five"])

    def test_61_pipeline_hands_normalized_lines_to_step5l(self):
        captured = {}
        def line_builder(*args, **kwargs):
            return {
                "line_board_id": "x", "line_board_fingerprint_sha256": "a" * 64,
                "normalized_line_count": 1, "paired_two_way_quote_count": 0,
                "step_5l_prop_lines": [{"player_id":1,"stat":"points","line":19.5,"sportsbook_quotes":None}],
                "date": "2026-08-26",
            }
        def daily_builder(lines, **kwargs):
            captured["lines"] = copy.deepcopy(lines)
            return {"daily_board_fingerprint_sha256":"b"*64,"probability_board":[],"value_board":[]}
        m.build_feed_daily_top_five(
            {}, feed_source="Fixture", line_board_builder=line_builder, daily_builder=daily_builder,
        )
        self.assertEqual(captured["lines"][0]["player_id"], 1)

    def test_62_pipeline_exposes_probability_and_value_boards(self):
        def line_builder(*args, **kwargs):
            return {
                "line_board_id": "x", "line_board_fingerprint_sha256": "a" * 64,
                "normalized_line_count": 1, "paired_two_way_quote_count": 0,
                "step_5l_prop_lines": [{"player_id":1,"stat":"points","line":19.5,"sportsbook_quotes":None}],
                "date": "2026-08-26",
            }
        def daily_builder(lines, **kwargs):
            return {
                "daily_board_fingerprint_sha256":"b"*64,
                "probability_board":[{"player_id":1}],
                "value_board":[{"player_id":2}],
            }
        result = m.build_feed_daily_top_five(
            {}, feed_source="Fixture", line_board_builder=line_builder, daily_builder=daily_builder,
        )
        self.assertEqual(result["probability_board"][0]["player_id"], 1)
        self.assertEqual(result["value_board"][0]["player_id"], 2)

    def test_63_guardrails_exposed(self):
        result = build(two_way())
        semantics = result["adapter_semantics"]
        self.assertTrue(semantics["sportsbook_lines_are_never_invented"])
        self.assertTrue(semantics["different_prop_lines_are_never_merged"])
        self.assertTrue(semantics["feed_market_data_cannot_modify_model_probability"])

    def test_64_main_wiring_present(self):
        text = Path("sports_api/main.py").read_text(encoding="utf-8")
        self.assertIn("wnba_prop_line_feed_adapter_router", text)
        self.assertIn("app.include_router(wnba_prop_line_feed_adapter_router)", text)

    def test_65_ambiguous_player_name_fails_closed(self):
        result = build(
            two_way(player_id=None, player_name="Player Two"),
            roster_value=roster(duplicate_name=True),
        )
        self.assertEqual(result["normalized_line_count"], 0)
        self.assertIn("player_name_ambiguous_on_current_roster", result["offer_audit"][0]["reason_codes"])

    def test_66_comma_name_alias_resolves(self):
        result = build(two_way(player_id=None, player_name="Wilson, A'ja"))
        self.assertEqual(result["line_board"][0]["player_id"], 1)

    def test_67_identical_duplicate_same_timestamp_is_not_conflict(self):
        raw = canonical(
            offer(side="over", odds=-110, captured=FRESH2),
            offer(side="over", odds=-110, captured=FRESH2),
            offer(side="under", odds=-110, captured=FRESH2),
        )
        result = build(raw)
        self.assertEqual(result["duplicate_conflict_count"], 0)
        self.assertEqual(result["paired_two_way_quote_count"], 1)

    def test_68_line_source_book_count_includes_one_sided_books(self):
        raw = canonical(
            *two_way(sportsbook="Book A")["offers"],
            offer(sportsbook="Book B", side="over"),
        )
        result = build(raw)
        self.assertEqual(result["line_board"][0]["source_book_count"], 2)
        self.assertEqual(result["line_board"][0]["two_way_sportsbook_quote_count"], 1)

    def test_69_provider_market_key_points_maps(self):
        result = build(two_way(stat="player_points"))
        self.assertEqual(result["line_board"][0]["stat"], "points")

    def test_70_feed_source_required(self):
        with self.assertRaises(ValueError):
            build(two_way(), feed_source="")


if __name__ == "__main__":
    unittest.main()
