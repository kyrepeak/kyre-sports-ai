import json
import unittest

import sports_api.wnba_draftkings_prop_market_discovery as d


class Response:
    def __init__(self, payload=None, status=200):
        self._payload = payload
        self.status_code = status
        self.content = json.dumps(payload).encode("utf-8") if payload is not None else b""

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def prop_doc(stat: str, *, player="A'ja Wilson", line=22.5, wnba=True):
    market_names = {
        "points": f"{player} Points",
        "rebounds": f"{player} Rebounds",
        "assists": f"{player} Assists",
        "pra": f"{player} Points + Rebounds + Assists",
    }
    league = [{"id": "94682", "name": "WNBA"}] if wnba else [{"id": "42648", "name": "NBA"}]
    return {
        "leagues": league,
        "events": [{"id": "evt1", "leagueId": league[0]["id"], "name": "LVA Aces @ PHX Mercury"}],
        "markets": [{"id": "m1", "eventId": "evt1", "name": market_names[stat]}],
        "selections": [
            {
                "id": "s1",
                "marketId": "m1",
                "outcomeType": "Over",
                "points": line,
                "displayOdds": {"american": "−110"},
                "participants": [{"name": player}],
            },
            {
                "id": "s2",
                "marketId": "m1",
                "outcomeType": "Under",
                "points": line,
                "displayOdds": {"american": "+100"},
                "participants": [{"name": player}],
            },
        ],
    }


class Step6FTests(unittest.TestCase):
    def test_01_required_stats_exact(self):
        self.assertEqual(("points", "rebounds", "assists", "pra"), d.REQUIRED_STATS)

    def test_02_default_candidate_count(self):
        self.assertEqual(8, len(d.default_prop_candidates()))

    def test_03_two_candidates_per_stat(self):
        rows = d.default_prop_candidates()
        self.assertEqual({s: 2 for s in d.REQUIRED_STATS}, {s: sum(r["expected_stat"] == s for r in rows) for s in d.REQUIRED_STATS})

    def test_04_controlled_ids(self):
        self.assertEqual("16477", d.CONTROLLED_DATA_SUBCATEGORY_HINTS["points"])
        self.assertEqual("16479", d.CONTROLLED_DATA_SUBCATEGORY_HINTS["rebounds"])
        self.assertEqual("16478", d.CONTROLLED_DATA_SUBCATEGORY_HINTS["assists"])
        self.assertEqual("16483", d.CONTROLLED_DATA_SUBCATEGORY_HINTS["pra"])

    def test_05_dkusva_ids(self):
        self.assertEqual(("1215", "12488"), d.DKUSVA_CATEGORY_SUBCATEGORY_HINTS["points"])
        self.assertEqual(("1216", "12492"), d.DKUSVA_CATEGORY_SUBCATEGORY_HINTS["rebounds"])
        self.assertEqual(("1217", "12495"), d.DKUSVA_CATEGORY_SUBCATEGORY_HINTS["assists"])
        self.assertEqual(("583", "5001"), d.DKUSVA_CATEGORY_SUBCATEGORY_HINTS["pra"])

    def test_06_controlled_url_contains_league_and_subcat(self):
        url = d.build_controlled_data_url("points", "16477")
        self.assertIn("94682", url)
        self.assertIn("16477", url)
        self.assertTrue(url.startswith("https://sportsbook-nash.draftkings.com/"))

    def test_07_invalid_stat_rejected(self):
        with self.assertRaises(d.WNBADraftKingsPropDiscoveryInputError):
            d.build_controlled_data_url("steals", "1")

    def test_08_non_numeric_subcat_rejected(self):
        with self.assertRaises(d.WNBADraftKingsPropDiscoveryInputError):
            d.build_controlled_data_url("points", "abc")

    def test_09_resolve_defaults(self):
        self.assertEqual(8, len(d.resolve_prop_candidates(env={})))

    def test_10_custom_env_candidates(self):
        row = d.default_prop_candidates()[0]
        env = {d.CANDIDATES_ENV: json.dumps([row])}
        self.assertEqual([row], d.resolve_prop_candidates(env=env))

    def test_11_bad_json_rejected(self):
        with self.assertRaises(d.WNBADraftKingsPropDiscoveryInputError):
            d.resolve_prop_candidates(env={d.CANDIDATES_ENV: "["})

    def test_12_non_draftkings_url_rejected(self):
        row = dict(d.default_prop_candidates()[0])
        row["url"] = "https://example.com/x"
        with self.assertRaises(d.WNBADraftKingsPropDiscoveryInputError):
            d.resolve_prop_candidates([row])

    def test_13_embedded_credentials_rejected(self):
        row = dict(d.default_prop_candidates()[0])
        row["url"] = "https://user:pass@sportsbook-nash.draftkings.com/x"
        with self.assertRaises(d.WNBADraftKingsPropDiscoveryInputError):
            d.resolve_prop_candidates([row])

    def test_14_status_ready(self):
        report = d.get_prop_market_discovery_status({})
        self.assertTrue(report["configuration_ready"])
        self.assertFalse(report["live_probe_performed"])
        self.assertFalse(report["all_required_stats_verified"])

    def test_15_status_is_account_free(self):
        safety = d.get_prop_market_discovery_status({})["safety"]
        self.assertFalse(safety["authentication_used"])
        self.assertFalse(safety["cookies_used"])
        self.assertFalse(safety["sportsbook_account_required"])
        self.assertFalse(safety["wager_actions"])

    def test_16_compatibility_outcome_type_maps_side(self):
        rows = d.normalize_prop_candidate_document(prop_doc("points"), expected_stat="points", captured_at_utc="2026-08-27T00:00:00+00:00")
        self.assertEqual({"over", "under"}, {r["side"] for r in rows})

    def test_17_normalization_filters_expected_stat(self):
        rows = d.normalize_prop_candidate_document(prop_doc("points"), expected_stat="rebounds")
        self.assertEqual([], rows)

    def test_18_pra_normalizes(self):
        rows = d.normalize_prop_candidate_document(prop_doc("pra", line=35.5), expected_stat="pra")
        self.assertEqual(2, len(rows))
        self.assertTrue(all(r["stat"] == "pra" for r in rows))

    def test_19_pair_summary_two_sided(self):
        rows = d.normalize_prop_candidate_document(prop_doc("rebounds", line=10.5), expected_stat="rebounds")
        summary = d._pair_summary(rows)
        self.assertEqual(1, summary["two_sided_player_line_count"])
        self.assertEqual(2, summary["two_sided_offer_count"])

    def test_20_probe_all_four_stats_verified(self):
        by_id = {
            "16477": prop_doc("points"),
            "16479": prop_doc("rebounds", line=10.5),
            "16478": prop_doc("assists", line=4.5),
            "16483": prop_doc("pra", line=37.5),
        }

        def requester(url, **kwargs):
            for sid, payload in by_id.items():
                if sid in url:
                    return Response(payload)
            return Response({}, status=404)

        candidates = [r for r in d.default_prop_candidates() if r["family"] == "controlled_data_league_subcategory"]
        report = d.probe_draftkings_wnba_prop_markets(candidates, requester=requester, env={})
        self.assertTrue(report["all_required_stats_verified"])
        self.assertEqual(4, report["verified_stat_count"])
        self.assertTrue(report["step6d_configuration"]["generated"])

    def test_21_probe_fails_closed_when_one_stat_empty(self):
        by_id = {
            "16477": prop_doc("points"),
            "16479": prop_doc("rebounds"),
            "16478": prop_doc("assists"),
            "16483": {"leagues": [{"id": "94682", "name": "WNBA"}], "markets": [], "selections": []},
        }

        def requester(url, **kwargs):
            for sid, payload in by_id.items():
                if sid in url:
                    return Response(payload)
            return Response({}, status=404)

        candidates = [r for r in d.default_prop_candidates() if r["family"] == "controlled_data_league_subcategory"]
        report = d.probe_draftkings_wnba_prop_markets(candidates, requester=requester, env={})
        self.assertFalse(report["all_required_stats_verified"])
        self.assertIsNone(report["step6d_configuration"]["value"])

    def test_22_non_wnba_response_not_usable(self):
        candidate = d.default_prop_candidates()[0]
        report = d.probe_draftkings_wnba_prop_markets([candidate], requester=lambda *a, **k: Response(prop_doc("points", wnba=False)), env={})
        self.assertFalse(report["attempts"][0]["usable_for_step6d"])

    def test_23_http_error_recorded_not_raised(self):
        candidate = d.default_prop_candidates()[0]
        report = d.probe_draftkings_wnba_prop_markets([candidate], requester=lambda *a, **k: Response({}, status=403), env={})
        self.assertEqual("http_403", report["attempts"][0]["response_error"])
        self.assertFalse(report["attempts"][0]["usable_for_step6d"])

    def test_24_network_error_recorded_not_raised(self):
        candidate = d.default_prop_candidates()[0]
        def requester(*args, **kwargs):
            raise TimeoutError("test")
        report = d.probe_draftkings_wnba_prop_markets([candidate], requester=requester, env={})
        self.assertEqual("request_failed", report["attempts"][0]["response_error"])
        self.assertEqual("TimeoutError", report["attempts"][0]["network_error_type"])

    def test_25_probe_never_enables_direct_sync(self):
        candidate = d.default_prop_candidates()[0]
        report = d.probe_draftkings_wnba_prop_markets([candidate], requester=lambda *a, **k: Response(prop_doc("points")), env={})
        self.assertFalse(report["step6d_configuration"]["direct_sync_enablement_changed"])
        self.assertFalse(report["safety"]["step_6d_auto_enabled"])
        self.assertFalse(report["safety"]["production_runtime_enabled"])
        self.assertFalse(report["safety"]["monte_carlo_run"])


if __name__ == "__main__":
    unittest.main()
