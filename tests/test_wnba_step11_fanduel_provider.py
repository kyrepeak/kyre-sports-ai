from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from sports_api import wnba_step11_fanduel_provider as s11c

UTC = timezone.utc
EVALUATED = datetime(2026, 8, 28, 6, 8, 0, tzinfo=UTC)
GAME_ID = "1022600291"
PLAYER_ID = 1642301
HOME_TEAM_ID = 1611661330
AWAY_TEAM_ID = 1611661329
EVENT_ID = "35990001"


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "WNBA_STEP11C_FANDUEL_PROVIDER_ENABLED": "true",
        "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
        "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
    }
    env.update(overrides)
    return env


def _schedule(*, duplicate: bool = False) -> dict:
    game = {
        "gameId": GAME_ID,
        "gameDateTimeUTC": "2026-08-28T23:00:00Z",
        "homeTeam": {"teamId": str(HOME_TEAM_ID), "teamCity": "Atlanta", "teamName": "Dream", "teamTricode": "ATL"},
        "awayTeam": {"teamId": str(AWAY_TEAM_ID), "teamCity": "Portland", "teamName": "Fire", "teamTricode": "POR"},
    }
    games = [game]
    if duplicate:
        other = deepcopy(game); other["gameId"] = "1022600292"; games.append(other)
    return {"leagueSchedule": {"seasonYear": "2026", "gameDates": [{"gameDate": "2026-08-28", "games": games}]}}


def _roster(*, team_id: int = HOME_TEAM_ID, duplicate_name: bool = False) -> list[dict]:
    rows = [{"player_id": PLAYER_ID, "full_name": "Certification Player", "team_id": team_id, "team_key": "atlanta-dream"}]
    if duplicate_name:
        rows.append({"player_id": PLAYER_ID + 1, "full_name": "Certification Player", "team_id": team_id, "team_key": "atlanta-dream"})
    return rows


def _odds(price: int) -> dict:
    return {"americanDisplayOdds": {"americanOdds": price}, "trueOdds": {"decimalOdds": {"decimalOdds": 1.91}}}


def _market(stat: str, line: float, *, suspended_under: bool = False, duplicate_over: bool = False, decimal_only: bool = False) -> dict:
    names = {
        "points": "Certification Player - Player Points",
        "rebounds": "Certification Player - Player Rebounds",
        "assists": "Certification Player - Player Assists",
        "pra": "Certification Player - Player Points + Rebounds + Assists",
    }
    mid = f"fd-{stat}"
    def runner(side: str, price: int, rid: str) -> dict:
        odds = {"trueOdds": {"decimalOdds": {"decimalOdds": 1.91}}} if decimal_only else _odds(price)
        return {
            "selectionId": rid,
            "runnerName": f"{side} {line}",
            "runnerStatus": "SUSPENDED" if suspended_under and side == "Under" else "ACTIVE",
            "winRunnerOdds": odds,
        }
    rows = [runner("Over", -110, f"{mid}-o"), runner("Under", -110, f"{mid}-u")]
    if duplicate_over:
        rows.append(runner("Over", -105, f"{mid}-o2"))
    return {"marketId": mid, "marketName": names[stat], "marketStatus": "OPEN", "runners": rows}


def _event() -> dict:
    return {
        "eventId": EVENT_ID,
        "name": "Portland Fire @ Atlanta Dream",
        "openDate": "2026-08-28T23:00:00Z",
        "homeTeam": {"name": "Atlanta Dream"},
        "awayTeam": {"name": "Portland Fire"},
    }


def _event_doc(*, duplicate_over: bool = False, suspended_under_points: bool = False, decimal_points: bool = False) -> dict:
    markets = {
        "fd-points": _market("points", 20.5, suspended_under=suspended_under_points, duplicate_over=duplicate_over, decimal_only=decimal_points),
        "fd-rebounds": _market("rebounds", 10.5),
        "fd-assists": _market("assists", 4.5),
        "fd-pra": _market("pra", 35.5),
    }
    return {
        "attachments": {"events": {EVENT_ID: _event()}, "markets": markets},
        "layout": {"tabs": [
            {"id": 101, "title": "Player Points"},
            {"id": 102, "title": "Player Rebounds"},
            {"id": 103, "title": "Player Assists"},
            {"id": 104, "title": "Player Combos"},
            {"id": 999, "title": "Team Props"},
        ]},
    }


def _entries(document: dict | None = None) -> list[dict]:
    return [{"event_id": EVENT_ID, "captured_at_utc": "2026-08-28T06:07:45+00:00", "document": document or _event_doc()}]


def _build(**kwargs):
    return s11c.build_step11c_fanduel_provider_bridge(
        event_page_documents=kwargs.pop("event_page_documents", _entries()),
        official_schedule_document=kwargs.pop("official_schedule_document", _schedule()),
        official_roster_players=kwargs.pop("official_roster_players", _roster()),
        slate_date="2026-08-28",
        evaluated_at=EVALUATED,
        env=kwargs.pop("env", _env()),
        **kwargs,
    )


class _Response:
    def __init__(self, document: dict, status_code: int = 200, size: int = 32):
        self._document = document; self.status_code = status_code; self.content = b"x" * size
    def json(self): return deepcopy(self._document)


class Step11FanDuelProviderTests(unittest.TestCase):
    def test_flag_is_default_off(self):
        self.assertFalse(s11c.step11c_fanduel_provider_enabled({}))

    def test_production_and_scheduler_switches_fail_closed(self):
        with self.assertRaises(s11c.WNBAStep11FanDuelProviderDisabledError):
            _build(env=_env(WNBA_PRODUCTION_RUNTIME_ENABLED="true"))
        with self.assertRaises(s11c.WNBAStep11FanDuelProviderDisabledError):
            _build(env=_env(WNBA_BOARD_SCHEDULER_ENABLED="true"))

    def test_happy_path_builds_four_official_identity_two_way_records(self):
        result = _build()
        self.assertEqual(result["identity"]["two_way_record_count"], 4)
        records = result["provider_refresh"]["attempts"][0]["payload"]["records"]
        self.assertEqual({row["stat"] for row in records}, {"points", "rebounds", "assists", "pra"})
        self.assertEqual({row["game_id"] for row in records}, {GAME_ID})
        self.assertEqual({row["player_id"] for row in records}, {PLAYER_ID})

    def test_step7g_first_party_official_team_id_is_accepted(self):
        roster = _roster()
        for row in roster:
            row["official_team_id"] = row.pop("team_id")
        result = _build(official_roster_players=roster)
        self.assertEqual(result["identity"]["two_way_record_count"], 4)

    def test_conflicting_team_id_fields_fail_closed(self):
        roster = _roster()
        roster[0]["official_team_id"] = AWAY_TEAM_ID
        with self.assertRaises(s11c.WNBAStep11FanDuelProviderIdentityError):
            _build(official_roster_players=roster)

    def test_exact_step10_provider_refresh_shape_and_validation(self):
        result = _build(); refresh = result["provider_refresh"]
        self.assertEqual(set(refresh), {"provider", "adapter_type", "attempts"})
        self.assertEqual(refresh["provider"], "FanDuel")
        self.assertEqual(refresh["adapter_type"], "flat_two_way_v1")
        self.assertEqual(result["step10_validation"]["record_count"], 4)

    def test_alt_line_pairs_can_coexist_in_one_market(self):
        doc = _event_doc()
        market = doc["attachments"]["markets"]["fd-points"]
        market["runners"].extend([
            {"selectionId": "alt-o", "runnerName": "Over 21.5", "runnerStatus": "ACTIVE", "winRunnerOdds": _odds(105)},
            {"selectionId": "alt-u", "runnerName": "Under 21.5", "runnerStatus": "ACTIVE", "winRunnerOdds": _odds(-125)},
        ])
        result = _build(event_page_documents=_entries(doc))
        points = [r for r in result["provider_refresh"]["attempts"][0]["payload"]["records"] if r["stat"] == "points"]
        self.assertEqual({r["line"] for r in points}, {20.5, 21.5})

    def test_suspended_incomplete_line_is_skipped_not_promoted(self):
        result = _build(event_page_documents=_entries(_event_doc(suspended_under_points=True)))
        stats = {r["stat"] for r in result["provider_refresh"]["attempts"][0]["payload"]["records"]}
        self.assertNotIn("points", stats); self.assertIn("rebounds", stats)

    def test_duplicate_same_side_quote_fails_closed(self):
        with self.assertRaises(s11c.WNBAStep11FanDuelProviderIdentityError):
            _build(event_page_documents=_entries(_event_doc(duplicate_over=True)))

    def test_decimal_fallback_converts_to_american(self):
        result = _build(event_page_documents=_entries(_event_doc(decimal_points=True)))
        point = next(r for r in result["provider_refresh"]["attempts"][0]["payload"]["records"] if r["stat"] == "points")
        self.assertLessEqual(point["over_price"], -100)

    def test_ambiguous_roster_name_fails_closed(self):
        with self.assertRaises(s11c.WNBAStep11FanDuelProviderIdentityError):
            _build(official_roster_players=_roster(duplicate_name=True))

    def test_player_must_belong_to_official_game(self):
        with self.assertRaises(s11c.WNBAStep11FanDuelProviderIdentityError):
            _build(official_roster_players=_roster(team_id=999999))

    def test_ambiguous_official_game_fails_closed(self):
        with self.assertRaises(s11c.WNBAStep11FanDuelProviderIdentityError):
            _build(official_schedule_document=_schedule(duplicate=True))

    def test_hash_stable_across_generation_time(self):
        self.assertEqual(_build()["provider_bridge_content_sha256"], _build()["provider_bridge_content_sha256"])

    def test_relevant_tab_discovery_is_bounded_and_ignores_team_props(self):
        ids = s11c._relevant_tab_ids(_event_doc())
        self.assertEqual(ids, ["101", "102", "103", "104"])

    def test_pure_builder_has_no_network_writes_scheduler_or_step9(self):
        guards = _build()["guardrails"]
        for key in ("sportsbook_network_fetch_performed", "official_wnba_network_fetch_performed", "authentication_used", "cookies_used", "wager_action_performed", "paid_odds_vendor_used", "basketball_projection_changed", "step8_distribution_changed", "step9_called", "supabase_mutated", "persistence_mutated", "scheduler_started", "production_runtime_enabled", "production_activation_allowed"):
            self.assertFalse(guards[key], key)

    def test_live_wrapper_uses_only_get_public_fanduel_and_official_schedule(self):
        content = {"attachments": {"events": {EVENT_ID: _event()}}}
        event_doc = _event_doc()
        calls = []
        def requester(url, *, params, headers, timeout):
            calls.append((url, dict(params), dict(headers)))
            if url == s11c.FANDUEL_BASE_URL + s11c.CONTENT_PAGE_PATH: return _Response(content)
            if url == s11c.FANDUEL_BASE_URL + s11c.EVENT_PAGE_PATH: return _Response(event_doc)
            if url == s11c.OFFICIAL_SCHEDULE_URL: return _Response(_schedule())
            raise AssertionError(url)
        result = s11c.fetch_step11c_fanduel_provider_bridge(
            season=2026, slate_date="2026-08-28", evaluated_at=datetime.now(UTC), requester=requester,
            roster_loader=lambda season: {"players": _roster()}, env=_env(),
        )
        self.assertTrue(result["guardrails"]["sportsbook_network_fetch_performed"])
        self.assertEqual(result["network"]["http_methods"], ["GET"])
        self.assertTrue(any(call[1].get("_ak") == s11c.FANDUEL_PUBLIC_WEB_KEY for call in calls if "fanduel" in call[0]))
        for _, _, headers in calls:
            self.assertNotIn("Authorization", headers); self.assertNotIn("Cookie", headers)

    def test_non_200_fails_closed(self):
        def requester(url, *, params, headers, timeout): return _Response({}, status_code=503)
        with self.assertRaises(s11c.WNBAStep11FanDuelProviderUpstreamError):
            s11c.fetch_step11c_fanduel_provider_bridge(season=2026, slate_date="2026-08-28", evaluated_at=EVALUATED, requester=requester, roster_loader=lambda season: {"players": _roster()}, env=_env())

    def test_oversize_response_fails_closed(self):
        def requester(url, *, params, headers, timeout): return _Response({}, size=s11c.MAX_RESPONSE_BYTES + 1)
        with self.assertRaises(s11c.WNBAStep11FanDuelProviderUpstreamError):
            s11c.fetch_step11c_fanduel_provider_bridge(season=2026, slate_date="2026-08-28", evaluated_at=EVALUATED, requester=requester, roster_loader=lambda season: {"players": _roster()}, env=_env())

    def test_lineage_pins_frozen_step11b_step11a_and_step10(self):
        result = _build(); lineage = result["lineage"]
        self.assertEqual(lineage["step11b_frozen_git_sha"], s11c.STEP11B_FROZEN_HEAD_SHA)
        self.assertEqual(lineage["step11a_frozen_git_sha"], s11c.STEP11A_FROZEN_HEAD_SHA)
        self.assertEqual(lineage["step10_frozen_git_sha"], s11c.STEP10_FROZEN_HEAD_SHA)


if __name__ == "__main__": unittest.main(verbosity=2)
