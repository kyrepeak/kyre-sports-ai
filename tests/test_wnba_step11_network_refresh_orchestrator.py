from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from sports_api import wnba_step11_draftkings_provider as s11a
from sports_api import wnba_step11_network_refresh_orchestrator as s11b

UTC = timezone.utc
GAME_ID = "1022600291"
PLAYER_ID = 1642301
HOME_TEAM_ID = 1611661330
AWAY_TEAM_ID = 1611661329


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED": "true",
        "WNBA_STEP11B_NETWORK_REFRESH_ENABLED": "true",
        "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
        "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
        "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED": "true",
        "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
    }
    env.update(overrides)
    return env


def _schedule() -> dict:
    return {
        "leagueSchedule": {
            "seasonYear": "2026",
            "gameDates": [{
                "gameDate": "2026-08-28",
                "games": [{
                    "gameId": GAME_ID,
                    "gameDateTimeUTC": "2026-08-28T23:00:00Z",
                    "homeTeam": {
                        "teamId": str(HOME_TEAM_ID),
                        "teamCity": "Atlanta",
                        "teamName": "Dream",
                        "teamTricode": "ATL",
                    },
                    "awayTeam": {
                        "teamId": str(AWAY_TEAM_ID),
                        "teamCity": "Portland",
                        "teamName": "Fire",
                        "teamTricode": "POR",
                    },
                }],
            }],
        }
    }


def _roster_dataset() -> dict:
    return {
        "players": [{
            "player_id": PLAYER_ID,
            "full_name": "Certification Player",
            "team_id": HOME_TEAM_ID,
            "team_key": "atlanta-dream",
        }],
        "team_source_urls": {},
    }


def _market_name(stat: str) -> str:
    return {
        "points": "Player Points",
        "rebounds": "Player Rebounds",
        "assists": "Player Assists",
        "pra": "Player Points + Rebounds + Assists",
    }[stat]


def _document(stat: str, line: float) -> dict:
    market_id = f"market-{stat}"
    return {
        "events": [{
            "id": "dk-event-1",
            "startEventDate": "2026-08-28T23:00:00Z",
            "participants": [{"name": "Atlanta Dream"}, {"name": "Portland Fire"}],
        }],
        "markets": [{
            "id": market_id,
            "eventId": "dk-event-1",
            "name": _market_name(stat),
        }],
        "selections": [
            {
                "id": f"{market_id}-over",
                "marketId": market_id,
                "label": "Over",
                "points": line,
                "playerName": "Certification Player",
                "oddsAmerican": -110,
            },
            {
                "id": f"{market_id}-under",
                "marketId": market_id,
                "label": "Under",
                "points": line,
                "playerName": "Certification Player",
                "oddsAmerican": -110,
            },
        ],
    }


class _Response:
    def __init__(self, document: dict, status_code: int = 200):
        self._document = deepcopy(document)
        self.status_code = status_code
        self.content = b"{}"

    def json(self):
        return deepcopy(self._document)


def _requester():
    documents = {
        s11a.OFFICIAL_SCHEDULE_URL: _schedule(),
        s11a.FROZEN_DRAFTKINGS_ENDPOINTS[0]: _document("points", 20.5),
        s11a.FROZEN_DRAFTKINGS_ENDPOINTS[1]: _document("rebounds", 10.5),
        s11a.FROZEN_DRAFTKINGS_ENDPOINTS[2]: _document("assists", 4.5),
        s11a.FROZEN_DRAFTKINGS_ENDPOINTS[3]: _document("pra", 35.5),
    }

    def requester(url, *, headers, timeout):
        return _Response(documents[url])

    return requester


def _live_bridge(evaluated_at: datetime | None = None) -> dict:
    return s11a.fetch_step11a_draftkings_provider_bridge(
        season=2026,
        slate_date="2026-08-28",
        evaluated_at=evaluated_at or datetime.now(UTC),
        requester=_requester(),
        roster_loader=lambda season: _roster_dataset(),
        env=_env(),
    )


def _fetcher_from_bridge(bridge: dict):
    def fetcher(**kwargs):
        return deepcopy(bridge)
    return fetcher


def _run(*, evaluated_at: datetime | None = None, provider_fetcher=None, **kwargs):
    return s11b.run_step11b_network_refresh_cycle(
        season=2026,
        slate_date="2026-08-28",
        evaluated_at=evaluated_at or datetime.now(UTC),
        provider_fetcher=provider_fetcher,
        env=kwargs.pop("env", _env()),
        **kwargs,
    )


class Step11NetworkRefreshOrchestratorTests(unittest.TestCase):
    def test_flag_is_default_off(self):
        self.assertFalse(s11b.step11b_network_refresh_enabled({}))
        with self.assertRaises(s11b.WNBAStep11NetworkRefreshDisabledError):
            s11b.run_step11b_network_refresh_cycle(
                season=2026,
                slate_date="2026-08-28",
                provider_fetcher=lambda **kwargs: {},
                env={
                    "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED": "true",
                    "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
                    "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
                    "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED": "true",
                    "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED": "true",
                },
            )

    def test_production_switch_fails_closed(self):
        with self.assertRaises(s11b.WNBAStep11NetworkRefreshDisabledError):
            _run(provider_fetcher=lambda **kwargs: {}, env=_env(WNBA_PRODUCTION_RUNTIME_ENABLED="true"))

    def test_scheduler_switch_fails_closed(self):
        with self.assertRaises(s11b.WNBAStep11NetworkRefreshDisabledError):
            _run(provider_fetcher=lambda **kwargs: {}, env=_env(WNBA_BOARD_SCHEDULER_ENABLED="true"))

    def test_step11a_gate_is_required(self):
        with self.assertRaises(s11b.WNBAStep11NetworkRefreshDisabledError):
            _run(provider_fetcher=lambda **kwargs: {}, env=_env(WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED="false"))

    def test_step10d_gate_is_required(self):
        with self.assertRaises(s11b.WNBAStep11NetworkRefreshDisabledError):
            _run(provider_fetcher=lambda **kwargs: {}, env=_env(WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED="false"))

    def test_successful_first_attempt_drives_frozen_step10d_ready_cycle(self):
        now = datetime.now(UTC)
        bridge = _live_bridge(now)
        result = _run(evaluated_at=now, provider_fetcher=_fetcher_from_bridge(bridge))
        self.assertTrue(result["network_refresh"]["succeeded"])
        self.assertEqual(result["network_refresh"]["attempts_executed"], 1)
        self.assertEqual(result["step10d_cycle"]["status"], "ready")
        self.assertEqual(result["step10d_cycle"]["snapshot_source"], "current_refresh")
        self.assertEqual(result["step10d_cycle"]["refresh"]["successful_provider_count"], 1)

    def test_upstream_failure_then_success_is_real_retry_without_sleep(self):
        now = datetime.now(UTC)
        bridge = _live_bridge(now)
        calls = {"count": 0}

        def fetcher(**kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise s11a.WNBAStep11DraftKingsProviderUpstreamError("temporary")
            return deepcopy(bridge)

        result = _run(evaluated_at=now, provider_fetcher=fetcher, provider_attempts=3)
        self.assertEqual(calls["count"], 2)
        self.assertEqual(result["network_refresh"]["retryable_failures"], 1)
        self.assertFalse(result["network_refresh"]["sleep_performed"])
        self.assertEqual(result["step10d_cycle"]["providers"][0]["attempts_consumed"], 2)
        self.assertEqual(result["step10d_cycle"]["providers"][0]["retries_planned"], 1)
        self.assertFalse(result["step10d_cycle"]["refresh"]["retry_policy"]["sleep_executed"])

    def test_retry_attempts_stop_immediately_after_success(self):
        now = datetime.now(UTC)
        bridge = _live_bridge(now)
        calls = {"count": 0}

        def fetcher(**kwargs):
            calls["count"] += 1
            return deepcopy(bridge)

        result = _run(evaluated_at=now, provider_fetcher=fetcher, provider_attempts=5)
        self.assertEqual(calls["count"], 1)
        self.assertEqual(result["network_refresh"]["attempts_executed"], 1)

    def test_all_transient_failures_are_not_ready_without_last_good(self):
        calls = {"count": 0}

        def fetcher(**kwargs):
            calls["count"] += 1
            raise s11a.WNBAStep11DraftKingsProviderUpstreamError("offline")

        result = _run(provider_fetcher=fetcher, provider_attempts=3)
        self.assertEqual(calls["count"], 3)
        self.assertFalse(result["network_refresh"]["succeeded"])
        self.assertEqual(result["step10d_cycle"]["status"], "not_ready")
        self.assertEqual(result["step10d_cycle"]["snapshot_source"], "none")

    def test_all_transient_failures_can_use_verified_fresh_last_good(self):
        now = datetime.now(UTC)
        bridge = _live_bridge(now)
        first = _run(evaluated_at=now, provider_fetcher=_fetcher_from_bridge(bridge))
        last_good = first["step10d_cycle"]["market_snapshot"]

        def fetcher(**kwargs):
            raise s11a.WNBAStep11DraftKingsProviderUpstreamError("offline")

        later = _run(
            evaluated_at=now + timedelta(seconds=50),
            provider_fetcher=fetcher,
            provider_attempts=2,
            last_good_snapshot=last_good,
        )
        self.assertEqual(later["step10d_cycle"]["status"], "degraded_last_good")
        self.assertEqual(later["step10d_cycle"]["snapshot_source"], "last_good_snapshot")
        self.assertTrue(later["step10d_cycle"]["last_good"]["used"])

    def test_identity_error_is_terminal_and_never_hidden_as_provider_outage(self):
        calls = {"count": 0}

        def fetcher(**kwargs):
            calls["count"] += 1
            raise s11a.WNBAStep11DraftKingsProviderIdentityError("identity mismatch")

        with self.assertRaises(s11a.WNBAStep11DraftKingsProviderIdentityError):
            _run(provider_fetcher=fetcher, provider_attempts=5)
        self.assertEqual(calls["count"], 1)

    def test_not_ready_provider_error_is_retryable(self):
        calls = {"count": 0}

        def fetcher(**kwargs):
            calls["count"] += 1
            raise s11a.WNBAStep11DraftKingsProviderNotReadyError("no complete pairs")

        result = _run(provider_fetcher=fetcher, provider_attempts=2)
        self.assertEqual(calls["count"], 2)
        self.assertEqual(result["network_refresh"]["retryable_failures"], 2)
        self.assertEqual(result["step10d_cycle"]["status"], "not_ready")

    def test_provider_attempt_count_is_bounded(self):
        for bad in (0, 6, 1.5, True):
            with self.subTest(bad=bad), self.assertRaises(s11b.WNBAStep11NetworkRefreshInputError):
                _run(provider_fetcher=lambda **kwargs: {}, provider_attempts=bad)

    def test_unknown_refresh_policy_is_rejected(self):
        with self.assertRaises(s11b.WNBAStep11NetworkRefreshInputError):
            _run(provider_fetcher=lambda **kwargs: {}, refresh_policy={"mystery": 1})

    def test_tampered_step11a_hash_is_rejected(self):
        now = datetime.now(UTC)
        bridge = _live_bridge(now)
        bridge["network"]["sportsbook_get_count"] = 999
        with self.assertRaises(s11b.WNBAStep11NetworkRefreshIntegrityError):
            _run(evaluated_at=now, provider_fetcher=_fetcher_from_bridge(bridge))

    def test_wrong_step11a_release_is_rejected(self):
        now = datetime.now(UTC)
        bridge = _live_bridge(now)
        bridge["release_id"] = "drift"
        with self.assertRaises(s11b.WNBAStep11NetworkRefreshIntegrityError):
            _run(evaluated_at=now, provider_fetcher=_fetcher_from_bridge(bridge))

    def test_pure_step11a_builder_cannot_masquerade_as_network_refresh(self):
        env = _env()
        documents = []
        specs = [
            ("points", 20.5),
            ("rebounds", 10.5),
            ("assists", 4.5),
            ("pra", 35.5),
        ]
        for url, (stat, line) in zip(s11a.FROZEN_DRAFTKINGS_ENDPOINTS, specs, strict=True):
            documents.append({
                "url": url,
                "captured_at_utc": datetime.now(UTC).isoformat(),
                "document": _document(stat, line),
            })
        bridge = s11a.build_step11a_draftkings_provider_bridge(
            draftkings_documents=documents,
            official_schedule_document=_schedule(),
            official_roster_players=_roster_dataset()["players"],
            slate_date="2026-08-28",
            evaluated_at=datetime.now(UTC),
            env=env,
        )
        with self.assertRaises(s11b.WNBAStep11NetworkRefreshIntegrityError):
            _run(provider_fetcher=_fetcher_from_bridge(bridge), env=env)

    def test_provider_refresh_passed_to_step10d_has_exact_frozen_shape(self):
        now = datetime.now(UTC)
        bridge = _live_bridge(now)
        result = _run(evaluated_at=now, provider_fetcher=_fetcher_from_bridge(bridge))
        refresh = result["provider_refresh"]
        self.assertEqual(set(refresh), {"provider", "adapter_type", "attempts"})
        self.assertEqual(refresh["provider"], "DraftKings")
        self.assertEqual(refresh["adapter_type"], "flat_two_way_v1")
        self.assertTrue(refresh["attempts"][0]["ok"])

    def test_guardrails_keep_scheduler_step9_writes_and_production_off(self):
        now = datetime.now(UTC)
        bridge = _live_bridge(now)
        guards = _run(evaluated_at=now, provider_fetcher=_fetcher_from_bridge(bridge))["guardrails"]
        self.assertTrue(guards["sportsbook_network_fetch_attempted"])
        self.assertTrue(guards["sportsbook_network_fetch_performed"])
        self.assertEqual(guards["sportsbook_http_methods"], ["GET"])
        for key in (
            "authentication_used",
            "cookies_used",
            "wager_action_performed",
            "paid_odds_vendor_used",
            "retry_sleep_performed",
            "scheduler_started",
            "step9_called",
            "basketball_projection_changed",
            "step8_distribution_changed",
            "supabase_mutated",
            "persistence_mutated",
            "production_runtime_enabled",
            "production_activation_allowed",
        ):
            self.assertFalse(guards[key], key)

    def test_lineage_pins_frozen_step11a_and_step10(self):
        now = datetime.now(UTC)
        bridge = _live_bridge(now)
        lineage = _run(evaluated_at=now, provider_fetcher=_fetcher_from_bridge(bridge))["lineage"]
        self.assertEqual(lineage["step11a_frozen_head_sha"], s11b.STEP11A_FROZEN_HEAD_SHA)
        self.assertEqual(lineage["step10_frozen_head_sha"], s11b.STEP10_FROZEN_HEAD_SHA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
