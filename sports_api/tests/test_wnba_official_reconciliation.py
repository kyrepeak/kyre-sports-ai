import copy
import unittest

import sports_api.wnba_official_reconciliation as r


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = b"{}"

    def json(self):
        return self._payload


class Step6HOfficialReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.players = [
            {
                "player_id": "1001",
                "player_name": "A'ja Wilson",
                "team_id": "1611661319",
                "team_name": "Las Vegas Aces",
            },
            {
                "player_id": "1002",
                "player_name": "Jackie Young",
                "team_id": "1611661319",
                "team_name": "Las Vegas Aces",
            },
        ]
        self.games = [
            {
                "game_id": "1022600290",
                "game_date": "2026-08-27",
                "home_team_id": "1611661317",
                "home_team_name": "Phoenix Mercury",
                "home_team_key": "phoenix mercury",
                "away_team_id": "1611661319",
                "away_team_name": "Las Vegas Aces",
                "away_team_key": "las vegas aces",
            }
        ]
        self.events = [
            {
                "source_event_id": "evt-1",
                "event_name": "Las Vegas Aces vs Phoenix Mercury",
                "event_date": "2026-08-27",
                "participants": ["Las Vegas Aces", "Phoenix Mercury"],
                "participant_keys": ["las vegas aces", "phoenix mercury"],
            }
        ]

    def feed(self):
        offers = []
        for stat_index, stat in enumerate(r.REQUIRED_STATS, start=1):
            for player_index, (player, line) in enumerate((("A'ja Wilson", 20.5), ("Jackie Young", 12.5)), start=1):
                market_id = f"mkt-{stat_index}-{player_index}"
                for side, odds in (("over", -110), ("under", -120)):
                    offers.append(
                        {
                            "sportsbook": "DraftKings",
                            "player_name": player,
                            "stat": stat,
                            "side": side,
                            "line": line,
                            "market_captured_at_utc": "2026-08-27T00:00:00+00:00",
                            "source_event_id": "evt-1",
                            "source_market_id": market_id,
                            "source_offer_id": f"sel-{stat_index}-{player_index}-{side}",
                            "american_odds": odds,
                        }
                    )
        return {
            "schema_version": "wnba_step_6c_owned_market_feed_v1",
            "date": "2026-08-27",
            "season": 2026,
            "captured_at_utc": "2026-08-27T00:00:00+00:00",
            "feed_source": "test",
            "feed_format": "canonical_offers_v1",
            "odds_format": "american",
            "offers": offers,
            "source_events": copy.deepcopy(self.events),
        }

    def official_players_doc(self):
        return {
            "resultSets": [{
                "name": "CommonAllPlayers",
                "headers": [
                    "PERSON_ID", "DISPLAY_FIRST_LAST", "ROSTERSTATUS", "TEAM_ID",
                    "TEAM_CITY", "TEAM_NAME", "TEAM_ABBREVIATION",
                ],
                "rowSet": [
                    ["1001", "A'ja Wilson", 1, "1611661319", "Las Vegas", "Las Vegas Aces", "LVA"],
                    ["1002", "Jackie Young", 1, "1611661319", "Las Vegas", "Las Vegas Aces", "LVA"],
                    ["1003", "Waived Player", 0, "1611661319", "Las Vegas", "Las Vegas Aces", "LVA"],
                ],
            }]
        }

    def official_schedule_doc(self):
        return {
            "leagueSchedule": {
                "gameDates": [{
                    "gameDate": "08/27/2026 00:00:00",
                    "games": [{
                        "gameId": "1022600290",
                        "gameDateTimeUTC": "2026-08-28T02:00:00Z",
                        "homeTeam": {
                            "teamId": "1611661317", "teamCity": "Phoenix", "teamName": "Mercury", "teamTricode": "PHX"
                        },
                        "awayTeam": {
                            "teamId": "1611661319", "teamCity": "Las Vegas", "teamName": "Aces", "teamTricode": "LVA"
                        },
                    }],
                }]
            }
        }

    def dk_payload(self, stat, suffix):
        market_name = {
            "points": "Player Points",
            "rebounds": "Player Rebounds",
            "assists": "Player Assists",
            "pra": "Player Points + Rebounds + Assists",
        }[stat]
        return {
            "events": [{
                "id": "evt-1",
                "name": "Las Vegas Aces vs Phoenix Mercury",
                "startEventDate": "2026-08-28T02:00:00Z",
                "participants": [{"name": "Las Vegas Aces"}, {"name": "Phoenix Mercury"}],
            }],
            "markets": [
                {"id": f"mkt-{suffix}-1", "eventId": "evt-1", "name": market_name,
                 "participants": [{"name": "A'ja Wilson"}]},
                {"id": f"mkt-{suffix}-2", "eventId": "evt-1", "name": market_name,
                 "participants": [{"name": "Jackie Young"}]},
            ],
            "selections": [
                {"id": f"sel-{suffix}-1-o", "marketId": f"mkt-{suffix}-1", "label": "Over 20.5",
                 "displayOdds": {"american": "-110"}, "participants": [{"name": "A'ja Wilson"}]},
                {"id": f"sel-{suffix}-1-u", "marketId": f"mkt-{suffix}-1", "label": "Under 20.5",
                 "displayOdds": {"american": "-120"}, "participants": [{"name": "A'ja Wilson"}]},
                {"id": f"sel-{suffix}-2-o", "marketId": f"mkt-{suffix}-2", "label": "Over 12.5",
                 "displayOdds": {"american": "+100"}, "participants": [{"name": "Jackie Young"}]},
                {"id": f"sel-{suffix}-2-u", "marketId": f"mkt-{suffix}-2", "label": "Under 12.5",
                 "displayOdds": {"american": "-130"}, "participants": [{"name": "Jackie Young"}]},
            ],
        }

    def draftkings_requester(self, url, **kwargs):
        for index, stat in enumerate(r.REQUIRED_STATS, start=1):
            if url.endswith(r.frozen_draftkings_urls()[index - 1].split("draftkings.com", 1)[1]):
                return FakeResponse(self.dk_payload(stat, str(index)))
        raise AssertionError(url)

    def official_requester(self, url, **kwargs):
        if url == r.OFFICIAL_SCHEDULE_URL:
            return FakeResponse(self.official_schedule_doc())
        if url.startswith(r.OFFICIAL_PLAYERS_BASE_URL):
            return FakeResponse(self.official_players_doc())
        raise AssertionError(url)

    def test_01_readiness_contract_is_safe(self):
        report = r.get_reconciliation_readiness()
        self.assertFalse(report["automatic_sync_enabled_by_step6h"])
        self.assertFalse(report["production_runtime_enabled_by_step6h"])
        self.assertFalse(report["scheduler_enabled_by_step6h"])
        self.assertFalse(report["safety"]["production_feed_written"])

    def test_02_official_schedule_uses_wnba_cdn(self):
        self.assertEqual("cdn.wnba.com", r.OFFICIAL_SCHEDULE_URL.split("/", 3)[2])

    def test_03_official_roster_uses_wnba_stats(self):
        self.assertEqual("stats.wnba.com", r.OFFICIAL_PLAYERS_BASE_URL.split("/", 3)[2])
        self.assertIn("LeagueID=10", r._official_players_url(2026))

    def test_04_parse_official_players_filters_inactive(self):
        rows = r.parse_official_players(self.official_players_doc())
        self.assertEqual(2, len(rows))
        self.assertEqual({"A'ja Wilson", "Jackie Young"}, {row["player_name"] for row in rows})

    def test_05_parse_official_schedule_keeps_wnba_game_date(self):
        rows = r.parse_official_schedule(self.official_schedule_doc())
        self.assertEqual(1, len(rows))
        self.assertEqual("2026-08-27", rows[0]["game_date"])
        self.assertEqual("1022600290", rows[0]["game_id"])

    def test_06_name_normalization_handles_apostrophe(self):
        self.assertEqual("a ja wilson", r._name_key("A’ja Wilson"))
        self.assertEqual(r._name_key("A’ja Wilson"), r._name_key("A'ja Wilson"))

    def test_07_happy_path_is_activation_ready_evidence(self):
        report = r.reconcile_snapshot(
            self.feed(),
            official_players=self.players,
            official_games=self.games,
            draftkings_events=self.events,
        )
        self.assertTrue(report["ready_for_auto_sync"])
        self.assertEqual([], report["blockers"])
        self.assertEqual(2, report["verified_player_count"])
        self.assertEqual(1, report["verified_event_count"])
        self.assertEqual(8, report["verified_market_count"])

    def test_08_unknown_player_fails_closed(self):
        feed = self.feed()
        for row in feed["offers"]:
            if row["player_name"] == "Jackie Young":
                row["player_name"] = "Unknown Player"
        report = r.reconcile_snapshot(feed, official_players=self.players, official_games=self.games, draftkings_events=self.events)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("unverified_official_player", report["blockers"])

    def test_09_ambiguous_player_identity_fails_closed(self):
        players = copy.deepcopy(self.players)
        players.append({"player_id": "9999", "player_name": "A’ja Wilson", "team_id": "1611661319", "team_name": "Las Vegas Aces"})
        report = r.reconcile_snapshot(self.feed(), official_players=players, official_games=self.games, draftkings_events=self.events)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("ambiguous_official_player_identity", report["blockers"])

    def test_10_missing_official_game_fails_closed(self):
        report = r.reconcile_snapshot(self.feed(), official_players=self.players, official_games=[], draftkings_events=self.events)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("official_game_not_found", report["blockers"])

    def test_11_wrong_roster_team_fails_closed(self):
        players = copy.deepcopy(self.players)
        players[1]["team_id"] = "999"
        players[1]["team_name"] = "Other Team"
        report = r.reconcile_snapshot(self.feed(), official_players=players, official_games=self.games, draftkings_events=self.events)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertTrue(
            "official_game_not_found" in report["blockers"] or "player_game_team_mismatch" in report["blockers"]
        )

    def test_12_step6g_failure_is_inherited(self):
        feed = self.feed()
        feed["offers"] = [row for row in feed["offers"] if row["source_offer_id"] != "sel-1-1-under"]
        report = r.reconcile_snapshot(feed, official_players=self.players, official_games=self.games, draftkings_events=self.events)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("step6g_shadow_validation_failed", report["blockers"])

    def test_13_fingerprint_is_deterministic(self):
        first = r.reconcile_snapshot(self.feed(), official_players=self.players, official_games=self.games, draftkings_events=self.events)
        second = r.reconcile_snapshot(self.feed(), official_players=self.players, official_games=self.games, draftkings_events=self.events)
        self.assertEqual(first["reconciliation_fingerprint_sha256"], second["reconciliation_fingerprint_sha256"])
        self.assertEqual(64, len(first["reconciliation_fingerprint_sha256"]))

    def test_14_timezone_shift_still_matches_same_official_game(self):
        events = copy.deepcopy(self.events)
        events[0]["event_date"] = "2026-08-28"
        report = r.reconcile_snapshot(self.feed(), official_players=self.players, official_games=self.games, draftkings_events=events)
        self.assertTrue(report["ready_for_auto_sync"])
        self.assertEqual("1022600290", report["event_verifications"][0]["official_game_id"])

    def test_15_fetch_official_snapshot_uses_two_gets(self):
        report = r.fetch_official_snapshot(season=2026, requester=self.official_requester)
        self.assertEqual(2, len(report["players"]))
        self.assertEqual(1, len(report["games"]))
        self.assertEqual(2, len(report["source_summary"]))

    def test_16_extract_draftkings_event_metadata(self):
        rows = r.extract_draftkings_events(self.dk_payload("points", "1"))
        self.assertEqual(1, len(rows))
        self.assertEqual({"las vegas aces", "phoenix mercury"}, set(rows[0]["participant_keys"]))

    def test_17_full_run_is_read_only_and_ready(self):
        report = r.run_official_reconciliation(
            date="2026-08-27",
            season=2026,
            draftkings_requester=self.draftkings_requester,
            official_requester=self.official_requester,
        )
        self.assertTrue(report["ready_for_auto_sync"])
        self.assertEqual(16, report["offer_side_count"])
        self.assertFalse(report["safety"]["production_feed_written"])
        self.assertFalse(report["safety"]["scheduler_enablement_changed"])
        self.assertEqual(["GET"], report["safety"]["http_methods"])


if __name__ == "__main__":
    unittest.main()
