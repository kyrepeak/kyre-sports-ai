from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step19l_fanduel_identity_trace as step19l
from sports_api import wnba_step19m_fanduel_line_move as step19m

UTC = timezone.utc
GAME_ID = "1022600291"
PLAYER_ID = 1642301
HOME_TEAM_ID = 1611661330
AWAY_TEAM_ID = 1611661329
EVENT_ID = "35990001"


def _env() -> dict[str, str]:
    return {
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


def _schedule() -> dict:
    return {
        "leagueSchedule": {
            "seasonYear": "2026",
            "gameDates": [
                {
                    "gameDate": "2026-08-28",
                    "games": [
                        {
                            "gameId": GAME_ID,
                            "gameDateTimeUTC": "2026-08-28T23:00:00Z",
                            "homeTeam": {"teamId": str(HOME_TEAM_ID), "teamCity": "Atlanta", "teamName": "Dream", "teamTricode": "ATL"},
                            "awayTeam": {"teamId": str(AWAY_TEAM_ID), "teamCity": "Portland", "teamName": "Fire", "teamTricode": "POR"},
                        }
                    ],
                }
            ],
        }
    }


def _roster() -> list[dict]:
    return [
        {
            "player_id": PLAYER_ID,
            "full_name": "Certification Player",
            "team_id": HOME_TEAM_ID,
            "team_key": "atlanta-dream",
        }
    ]


def _odds(price: int) -> dict:
    return {
        "americanDisplayOdds": {"americanOdds": price},
        "trueOdds": {"decimalOdds": {"decimalOdds": 1.91}},
    }


def _event() -> dict:
    return {
        "eventId": EVENT_ID,
        "name": "Portland Fire @ Atlanta Dream",
        "openDate": "2026-08-28T23:00:00Z",
        "homeTeam": {"name": "Atlanta Dream"},
        "awayTeam": {"name": "Portland Fire"},
    }


def _market(line: float, *, over_id: str = "fd-points-o", under_id: str = "fd-points-u") -> dict:
    return {
        "marketId": "fd-points",
        "marketName": "Certification Player - Player Points",
        "marketType": "PLAYER_POINTS_TOTAL_WNBA",
        "marketStatus": "OPEN",
        "runners": [
            {
                "selectionId": over_id,
                "runnerName": f"Over {line}",
                "runnerStatus": "ACTIVE",
                "handicap": line,
                "result": {"type": "OVER"},
                "winRunnerOdds": _odds(-110),
            },
            {
                "selectionId": under_id,
                "runnerName": f"Under {line}",
                "runnerStatus": "ACTIVE",
                "handicap": line,
                "result": {"type": "UNDER"},
                "winRunnerOdds": _odds(-110),
            },
        ],
    }


def _doc(line: float, **market_kwargs) -> dict:
    return {
        "attachments": {
            "events": {EVENT_ID: _event()},
            "markets": {"fd-points": _market(line, **market_kwargs)},
        },
        "layout": {"tabs": []},
    }


def _build(entries: list[dict]) -> dict:
    return fd.build_step11c_fanduel_provider_bridge(
        event_page_documents=entries,
        official_schedule_document=_schedule(),
        official_roster_players=_roster(),
        slate_date="2026-08-28",
        evaluated_at=datetime(2026, 8, 28, 6, 8, tzinfo=UTC),
        env=_env(),
    )


class Step19MFanDuelLineMoveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_surface = fd._market_identity_surface
        fd._market_identity_surface = step19l.market_identity_surface_step19l
        step19m.install_step19m_fanduel_line_move()
        step19m._reset_for_test()

    def tearDown(self) -> None:
        fd._market_identity_surface = self.previous_surface

    def test_same_market_same_selections_line_move_has_same_immutable_identity(self) -> None:
        before = step19m.market_identity_surface_step19m(_market(20.5))
        after = step19m.market_identity_surface_step19m(_market(21.5))
        self.assertEqual(before, after)

    def test_selection_identity_change_remains_fatal_identity_drift(self) -> None:
        before = step19m.market_identity_surface_step19m(_market(20.5))
        after = step19m.market_identity_surface_step19m(_market(21.5, over_id="replacement-over"))
        self.assertNotEqual(before, after)

    def test_market_type_change_remains_fatal_identity_drift(self) -> None:
        before_market = _market(20.5)
        after_market = _market(21.5)
        after_market["marketType"] = "DIFFERENT_PLAYER_MARKET_WNBA"
        self.assertNotEqual(
            step19m.market_identity_surface_step19m(before_market),
            step19m.market_identity_surface_step19m(after_market),
        )

    def test_player_identity_change_remains_fatal_identity_drift(self) -> None:
        before_market = _market(20.5)
        after_market = _market(21.5)
        after_market["playerName"] = "Different Person"
        self.assertNotEqual(
            step19m.market_identity_surface_step19m(before_market),
            step19m.market_identity_surface_step19m(after_market),
        )

    def test_newer_same_market_line_move_selects_newest_complete_line(self) -> None:
        entries = [
            {"event_id": EVENT_ID, "captured_at_utc": "2026-08-28T06:07:45+00:00", "document": _doc(20.5)},
            {"event_id": EVENT_ID, "captured_at_utc": "2026-08-28T06:07:46+00:00", "document": _doc(21.5)},
        ]
        result = _build(entries)
        records = result["provider_refresh"]["attempts"][0]["payload"]["records"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["line"], 21.5)
        self.assertEqual(records[0]["market_captured_at"], "2026-08-28T06:07:46+00:00")

    def test_same_timestamp_line_move_still_fails_closed(self) -> None:
        entries = [
            {"event_id": EVENT_ID, "captured_at_utc": "2026-08-28T06:07:45+00:00", "document": _doc(20.5)},
            {"event_id": EVENT_ID, "captured_at_utc": "2026-08-28T06:07:45+00:00", "document": _doc(21.5)},
        ]
        with self.assertRaises(fd.WNBAStep11FanDuelProviderIdentityError):
            _build(entries)

    def test_changed_selection_ids_still_fail_closed_in_frozen_builder(self) -> None:
        entries = [
            {"event_id": EVENT_ID, "captured_at_utc": "2026-08-28T06:07:45+00:00", "document": _doc(20.5)},
            {"event_id": EVENT_ID, "captured_at_utc": "2026-08-28T06:07:46+00:00", "document": _doc(21.5, over_id="replacement-over")},
        ]
        with self.assertRaises(fd.WNBAStep11FanDuelProviderIdentityError):
            _build(entries)

    def test_guardrails_keep_exact_lines_and_official_identity_strict(self) -> None:
        guards = step19m.installation_status()["guardrails"]
        self.assertTrue(guards["same_market_line_move_allowed"])
        self.assertTrue(guards["same_selection_ids_required"])
        self.assertTrue(guards["same_runner_side_identity_required"])
        self.assertTrue(guards["same_market_name_and_type_required"])
        self.assertTrue(guards["same_player_identity_required"])
        self.assertFalse(guards["selection_id_change_allowed"])
        self.assertFalse(guards["runner_side_change_allowed"])
        self.assertFalse(guards["different_lines_blended"])
        self.assertFalse(guards["exact_line_matching_modified"])
        self.assertFalse(guards["official_game_reconciliation_modified"])
        self.assertFalse(guards["official_roster_reconciliation_modified"])
        self.assertFalse(guards["projection_logic_modified"])
        self.assertFalse(guards["monte_carlo_simulation_count_modified"])
        self.assertFalse(guards["readiness_relaxed"])
        self.assertFalse(guards["wagering_enabled"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
