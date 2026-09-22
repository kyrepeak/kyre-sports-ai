import copy
import hashlib
import unittest

import sports_api.wnba_official_reconciliation as core
import sports_api.wnba_official_team_page_reconciliation_live as live


class Step6HOfficialTeamPageLiveTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            {
                "source_event_id": "evt-1",
                "event_name": "LVA Aces @ PHX Mercury",
                "event_date": "2026-08-28",
                "participants": ["LVA Aces", "PHX Mercury"],
                "participant_keys": ["lva aces", "phx mercury"],
            }
        ]

    def feed(self):
        offers = []
        for stat_index, stat in enumerate(core.REQUIRED_STATS, start=1):
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
                            "market_captured_at_utc": "2026-08-28T02:00:00+00:00",
                            "source_event_id": "evt-1",
                            "source_market_id": market_id,
                            "source_offer_id": f"sel-{stat_index}-{player_index}-{side}",
                            "american_odds": odds,
                        }
                    )
        return {
            "schema_version": "wnba_step_6c_owned_market_feed_v1",
            "date": "2026-08-28",
            "season": 2026,
            "captured_at_utc": "2026-08-28T02:00:00+00:00",
            "feed_source": "test",
            "feed_format": "canonical_offers_v1",
            "odds_format": "american",
            "offers": offers,
            "source_events": copy.deepcopy(self.events),
        }

    @staticmethod
    def _page(team, path, text):
        payload = f"{team}|{path}|{text}".encode("utf-8")
        return {
            "team_name": team,
            "host": live.TEAM_ROSTER_HOSTS[core._name_key(team)],
            "path": path,
            "http_status": 200,
            "visible_text": f" {core._name_key(text)} ",
            "content_sha256": hashlib.sha256(payload).hexdigest(),
        }

    def pages(self, *, missing_schedule=False, missing_upcoming=False, duplicate_roster=False, missing_player=False):
        pages = {}
        aces_root = "Upcoming Games Phoenix Mercury Tickets"
        mercury_root = "Upcoming Games Las Vegas Aces Tickets"
        if missing_upcoming:
            mercury_root = "Upcoming Games Seattle Storm Tickets"
        aces_schedule = "Schedule August 27 Phoenix Mercury August 30 Seattle Storm"
        mercury_schedule = "Schedule August 27 Las Vegas Aces August 30 Seattle Storm"
        if missing_schedule:
            mercury_schedule = "Schedule August 27 Seattle Storm"
        aces_roster = "2026 Team Roster A'ja Wilson Jackie Young Chelsea Gray Coaching Staff"
        mercury_roster = "2026 Team Roster Kahleah Copper Satou Sabally Coaching Staff"
        if duplicate_roster:
            mercury_roster = "2026 Team Roster A'ja Wilson Kahleah Copper Coaching Staff"
        if missing_player:
            aces_roster = "2026 Team Roster Chelsea Gray Megan Gustafson Coaching Staff"
        for team, root, schedule, roster in (
            ("Las Vegas Aces", aces_root, aces_schedule, aces_roster),
            ("Phoenix Mercury", mercury_root, mercury_schedule, mercury_roster),
        ):
            pages[(team, "/")] = self._page(team, "/", root)
            pages[(team, "/schedule")] = self._page(team, "/schedule", schedule)
            pages[(team, "/roster")] = self._page(team, "/roster", roster)
        return pages

    @staticmethod
    def fetcher(pages):
        def _fetch(team, path):
            return pages[(team, path)]
        return _fetch

    def test_01_aliases_resolve_to_official_registry_names(self):
        registry = live._registry(2026)
        teams = live._event_teams(self.events[0], registry)
        self.assertEqual(["Las Vegas Aces", "Phoenix Mercury"], teams)

    def test_02_utc_date_becomes_near_term_window_not_official_date(self):
        self.assertEqual(["2026-08-27", "2026-08-28"], live._candidate_local_dates("2026-08-28"))

    def test_03_happy_path_is_ready_with_mutual_official_team_pages(self):
        report = live.reconcile_team_page_snapshot(
            self.feed(), season=2026, page_fetcher=self.fetcher(self.pages())
        )
        self.assertTrue(report["ready_for_auto_sync"])
        self.assertEqual([], report["blockers"])
        self.assertEqual(16, report["offer_side_count"])
        self.assertEqual(8, report["market_count"])
        self.assertEqual(1, report["verified_event_count"])
        self.assertEqual(2, report["verified_player_count"])
        self.assertEqual(8, report["verified_market_count"])

    def test_04_numeric_game_id_and_official_date_are_never_fabricated(self):
        report = live.reconcile_team_page_snapshot(
            self.feed(), season=2026, page_fetcher=self.fetcher(self.pages())
        )
        event = report["event_verifications"][0]
        self.assertIsNone(event["official_game_id"])
        self.assertFalse(event["official_game_id_available"])
        self.assertIsNone(event["official_game_date"])
        self.assertFalse(event["official_game_date_claimed"])
        self.assertTrue(event["official_game_evidence_id"].startswith("team-schedule:"))

    def test_05_missing_schedule_pair_fails_closed(self):
        report = live.reconcile_team_page_snapshot(
            self.feed(), season=2026, page_fetcher=self.fetcher(self.pages(missing_schedule=True))
        )
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("official_event_near_term_pair_unverified", report["blockers"])

    def test_06_missing_upcoming_pair_fails_closed(self):
        report = live.reconcile_team_page_snapshot(
            self.feed(), season=2026, page_fetcher=self.fetcher(self.pages(missing_upcoming=True))
        )
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("official_event_near_term_pair_unverified", report["blockers"])

    def test_07_player_missing_from_both_official_rosters_fails_closed(self):
        report = live.reconcile_team_page_snapshot(
            self.feed(), season=2026, page_fetcher=self.fetcher(self.pages(missing_player=True))
        )
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("official_current_roster_membership_unverified", report["blockers"])

    def test_08_player_on_both_event_rosters_is_ambiguous_and_fails_closed(self):
        report = live.reconcile_team_page_snapshot(
            self.feed(), season=2026, page_fetcher=self.fetcher(self.pages(duplicate_roster=True))
        )
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("official_current_roster_membership_unverified", report["blockers"])

    def test_09_duplicate_draftkings_team_pair_fails_closed(self):
        feed = self.feed()
        duplicate = copy.deepcopy(feed["source_events"][0])
        duplicate["source_event_id"] = "evt-2"
        feed["source_events"].append(duplicate)
        report = live.reconcile_team_page_snapshot(
            feed, season=2026, page_fetcher=self.fetcher(self.pages())
        )
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("official_event_near_term_pair_unverified", report["blockers"])

    def test_10_step6g_shadow_failure_is_inherited(self):
        feed = self.feed()
        feed["offers"] = [row for row in feed["offers"] if row["source_offer_id"] != "sel-1-1-under"]
        report = live.reconcile_team_page_snapshot(
            feed, season=2026, page_fetcher=self.fetcher(self.pages())
        )
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("step6g_shadow_validation_failed", report["blockers"])

    def test_11_fingerprint_is_deterministic(self):
        first = live.reconcile_team_page_snapshot(
            self.feed(), season=2026, page_fetcher=self.fetcher(self.pages())
        )
        second = live.reconcile_team_page_snapshot(
            self.feed(), season=2026, page_fetcher=self.fetcher(self.pages())
        )
        self.assertEqual(first["reconciliation_fingerprint_sha256"], second["reconciliation_fingerprint_sha256"])
        self.assertEqual(64, len(first["reconciliation_fingerprint_sha256"]))

    def test_12_safety_contract_stays_read_only_and_activation_free(self):
        report = live.reconcile_team_page_snapshot(
            self.feed(), season=2026, page_fetcher=self.fetcher(self.pages())
        )
        safety = report["safety"]
        self.assertEqual(["GET"], safety["http_methods"])
        self.assertFalse(safety["production_feed_written"])
        self.assertFalse(safety["direct_sync_enablement_changed"])
        self.assertFalse(safety["production_runtime_enablement_changed"])
        self.assertFalse(safety["scheduler_enablement_changed"])
        self.assertFalse(safety["paid_odds_vendor_used"])
        self.assertFalse(safety["monte_carlo_run"])
        self.assertFalse(safety["wager_action_performed"])


if __name__ == "__main__":
    unittest.main()
