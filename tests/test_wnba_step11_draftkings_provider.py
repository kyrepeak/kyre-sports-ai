from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from sports_api import wnba_step11_draftkings_provider as s11

UTC = timezone.utc
EVALUATED = datetime(2026, 8, 28, 5, 50, 0, tzinfo=UTC)
GAME_ID = "1022600291"
PLAYER_ID = 1642301
HOME_TEAM_ID = 1611661330
AWAY_TEAM_ID = 1611661329


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED": "true",
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
    }
    games = [game]
    if duplicate:
        other = deepcopy(game)
        other["gameId"] = "1022600292"
        games.append(other)
    return {
        "leagueSchedule": {
            "seasonYear": "2026",
            "gameDates": [{"gameDate": "2026-08-28", "games": games}],
        }
    }


def _roster(*, team_id: int = HOME_TEAM_ID, duplicate_name: bool = False) -> list[dict]:
    rows = [
        {
            "player_id": PLAYER_ID,
            "full_name": "Certification Player",
            "team_id": team_id,
            "team_key": "atlanta-dream",
        }
    ]
    if duplicate_name:
        rows.append({
            "player_id": PLAYER_ID + 1,
            "full_name": "Certification Player",
            "team_id": team_id,
            "team_key": "atlanta-dream",
        })
    return rows


def _market_name(stat: str) -> str:
    return {
        "points": "Player Points",
        "rebounds": "Player Rebounds",
        "assists": "Player Assists",
        "pra": "Player Points + Rebounds + Assists",
    }[stat]


def _dk_document(
    stat: str,
    *,
    line: float,
    over: int = -110,
    under: int = -110,
    decimal: bool = False,
    include_under: bool = True,
    duplicate_over: bool = False,
) -> dict:
    market_id = f"market-{stat}"
    event = {
        "id": "dk-event-1",
        "startEventDate": "2026-08-28T23:00:00Z",
        "participants": [
            {"name": "Atlanta Dream"},
            {"name": "Portland Fire"},
        ],
    }
    over_row = {
        "id": f"{market_id}-over",
        "marketId": market_id,
        "label": "Over",
        "points": line,
        "playerName": "Certification Player",
    }
    under_row = {
        "id": f"{market_id}-under",
        "marketId": market_id,
        "label": "Under",
        "points": line,
        "playerName": "Certification Player",
    }
    if decimal:
        over_row["oddsDecimal"] = 1.91
        under_row["oddsDecimal"] = 1.91
    else:
        over_row["oddsAmerican"] = over
        under_row["oddsAmerican"] = under
    selections = [over_row]
    if include_under:
        selections.append(under_row)
    if duplicate_over:
        duplicate = deepcopy(over_row)
        duplicate["id"] = f"{market_id}-over-2"
        selections.append(duplicate)
    return {
        "events": [event],
        "markets": [{
            "id": market_id,
            "eventId": "dk-event-1",
            "name": _market_name(stat),
        }],
        "selections": selections,
    }


def _documents(**stat_overrides: dict) -> list[dict]:
    specs = [
        (s11.FROZEN_DRAFTKINGS_ENDPOINTS[0], "points", 20.5),
        (s11.FROZEN_DRAFTKINGS_ENDPOINTS[1], "rebounds", 10.5),
        (s11.FROZEN_DRAFTKINGS_ENDPOINTS[2], "assists", 4.5),
        (s11.FROZEN_DRAFTKINGS_ENDPOINTS[3], "pra", 35.5),
    ]
    result = []
    for index, (url, stat, line) in enumerate(specs):
        kwargs = stat_overrides.get(stat, {})
        result.append({
            "url": url,
            "captured_at_utc": f"2026-08-28T05:49:{10 + index:02d}+00:00",
            "document": _dk_document(stat, line=line, **kwargs),
        })
    return result


def _build(**kwargs):
    return s11.build_step11a_draftkings_provider_bridge(
        draftkings_documents=kwargs.pop("draftkings_documents", _documents()),
        official_schedule_document=kwargs.pop("official_schedule_document", _schedule()),
        official_roster_players=kwargs.pop("official_roster_players", _roster()),
        slate_date="2026-08-28",
        evaluated_at=EVALUATED,
        env=kwargs.pop("env", _env()),
        **kwargs,
    )


class _Response:
    def __init__(self, document: dict, status_code: int = 200, content_size: int | None = None):
        self._document = document
        self.status_code = status_code
        self.content = b"x" * (content_size if content_size is not None else 32)

    def json(self):
        return deepcopy(self._document)


class Step11DraftKingsProviderTests(unittest.TestCase):
    def test_flag_is_default_off(self):
        self.assertFalse(s11.step11a_draftkings_provider_enabled({}))
        with self.assertRaises(s11.WNBAStep11DraftKingsProviderDisabledError):
            s11.build_step11a_draftkings_provider_bridge(
                draftkings_documents=_documents(),
                official_schedule_document=_schedule(),
                official_roster_players=_roster(),
                slate_date="2026-08-28",
                evaluated_at=EVALUATED,
                env={
                    "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
                    "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
                },
            )

    def test_production_switch_fails_closed(self):
        with self.assertRaises(s11.WNBAStep11DraftKingsProviderDisabledError):
            _build(env=_env(WNBA_PRODUCTION_RUNTIME_ENABLED="true"))

    def test_exact_four_frozen_urls_are_required(self):
        docs = _documents()
        docs[3]["url"] = docs[0]["url"]
        with self.assertRaises(ValueError):
            _build(draftkings_documents=docs)

    def test_happy_path_reconciles_official_game_and_player_identity(self):
        result = _build()
        self.assertEqual(result["identity"]["two_way_record_count"], 4)
        records = result["provider_refresh"]["attempts"][0]["payload"]["records"]
        self.assertEqual({row["game_id"] for row in records}, {GAME_ID})
        self.assertEqual({row["player_id"] for row in records}, {PLAYER_ID})
        self.assertEqual({row["player_name"] for row in records}, {"Certification Player"})
        self.assertEqual({row["stat"] for row in records}, {"points", "rebounds", "assists", "pra"})

    def test_output_is_exact_step10d_provider_refresh_shape_and_step10b_validated(self):
        result = _build()
        refresh = result["provider_refresh"]
        self.assertEqual(set(refresh), {"provider", "adapter_type", "attempts"})
        self.assertEqual(refresh["provider"], "DraftKings")
        self.assertEqual(refresh["adapter_type"], "flat_two_way_v1")
        self.assertEqual(refresh["attempts"][0]["ok"], True)
        self.assertEqual(result["step10_validation"]["record_count"], 4)
        self.assertEqual(result["lineage"]["step10_frozen_git_sha"], s11.STEP10_FROZEN_SHA)

    def test_decimal_prices_are_converted_to_frozen_step10_american_contract(self):
        result = _build(draftkings_documents=_documents(points={"decimal": True}))
        point = next(
            row for row in result["provider_refresh"]["attempts"][0]["payload"]["records"]
            if row["stat"] == "points"
        )
        self.assertLessEqual(point["over_price"], -100)
        self.assertLessEqual(point["under_price"], -100)

    def test_incomplete_two_way_market_fails_closed(self):
        with self.assertRaises(s11.WNBAStep11DraftKingsProviderNotReadyError):
            _build(draftkings_documents=_documents(points={"include_under": False}))

    def test_duplicate_same_side_quote_fails_closed(self):
        with self.assertRaises(s11.WNBAStep11DraftKingsProviderIdentityError):
            _build(draftkings_documents=_documents(points={"duplicate_over": True}))

    def test_ambiguous_official_player_name_fails_closed(self):
        with self.assertRaises(s11.WNBAStep11DraftKingsProviderIdentityError):
            _build(official_roster_players=_roster(duplicate_name=True))

    def test_player_team_must_belong_to_reconciled_game(self):
        with self.assertRaises(s11.WNBAStep11DraftKingsProviderIdentityError):
            _build(official_roster_players=_roster(team_id=999999))

    def test_ambiguous_official_game_match_fails_closed(self):
        with self.assertRaises(s11.WNBAStep11DraftKingsProviderIdentityError):
            _build(official_schedule_document=_schedule(duplicate=True))

    def test_pure_builder_keeps_network_writes_scheduler_and_production_off(self):
        guards = _build()["guardrails"]
        for key in (
            "sportsbook_network_fetch_performed",
            "official_wnba_network_fetch_performed",
            "authentication_used",
            "cookies_used",
            "wager_action_performed",
            "paid_odds_vendor_used",
            "basketball_projection_changed",
            "step8_distribution_changed",
            "supabase_mutated",
            "persistence_mutated",
            "scheduler_started",
            "production_runtime_enabled",
            "production_activation_allowed",
        ):
            self.assertFalse(guards[key], key)

    def test_content_hash_is_stable_across_generation_time_only(self):
        first = _build()
        second = _build()
        self.assertEqual(
            first["provider_bridge_content_sha256"],
            second["provider_bridge_content_sha256"],
        )

    def test_live_wrapper_calls_only_frozen_market_urls_plus_official_schedule(self):
        documents = {
            s11.OFFICIAL_SCHEDULE_URL: _schedule(),
            s11.FROZEN_DRAFTKINGS_ENDPOINTS[0]: _dk_document("points", line=20.5),
            s11.FROZEN_DRAFTKINGS_ENDPOINTS[1]: _dk_document("rebounds", line=10.5),
            s11.FROZEN_DRAFTKINGS_ENDPOINTS[2]: _dk_document("assists", line=4.5),
            s11.FROZEN_DRAFTKINGS_ENDPOINTS[3]: _dk_document("pra", line=35.5),
        }
        calls = []

        def requester(url, *, headers, timeout):
            calls.append((url, dict(headers), timeout))
            return _Response(documents[url])

        result = s11.fetch_step11a_draftkings_provider_bridge(
            season=2026,
            slate_date="2026-08-28",
            evaluated_at=datetime.now(UTC),
            requester=requester,
            roster_loader=lambda season: {"players": _roster(), "team_source_urls": {}},
            env=_env(),
        )
        self.assertEqual([row[0] for row in calls], [
            s11.OFFICIAL_SCHEDULE_URL,
            *s11.FROZEN_DRAFTKINGS_ENDPOINTS,
        ])
        self.assertTrue(result["guardrails"]["sportsbook_network_fetch_performed"])
        self.assertTrue(result["guardrails"]["official_wnba_network_fetch_performed"])
        self.assertEqual(result["network"]["sportsbook_get_count"], 4)
        self.assertEqual(result["network"]["official_schedule_get_count"], 1)
        for _, headers, _ in calls:
            self.assertNotIn("Authorization", headers)
            self.assertNotIn("Cookie", headers)

    def test_non_200_network_response_fails_closed(self):
        def requester(url, *, headers, timeout):
            if url == s11.OFFICIAL_SCHEDULE_URL:
                return _Response(_schedule(), status_code=503)
            return _Response({})

        with self.assertRaises(s11.WNBAStep11DraftKingsProviderUpstreamError):
            s11.fetch_step11a_draftkings_provider_bridge(
                season=2026,
                slate_date="2026-08-28",
                evaluated_at=EVALUATED,
                requester=requester,
                roster_loader=lambda season: {"players": _roster(), "team_source_urls": {}},
                env=_env(),
            )

    def test_oversize_network_response_fails_closed(self):
        def requester(url, *, headers, timeout):
            return _Response(_schedule(), content_size=s11.MAX_RESPONSE_BYTES + 1)

        with self.assertRaises(s11.WNBAStep11DraftKingsProviderUpstreamError):
            s11.fetch_step11a_draftkings_provider_bridge(
                season=2026,
                slate_date="2026-08-28",
                evaluated_at=EVALUATED,
                requester=requester,
                roster_loader=lambda season: {"players": _roster(), "team_source_urls": {}},
                env=_env(),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
