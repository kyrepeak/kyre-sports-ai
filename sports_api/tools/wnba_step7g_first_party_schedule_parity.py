"""Certify Step 7G first-party schedule normalization against frozen Step 4C.

This is a read-only parity test. It fetches the WNBA.com same-origin schedule
once, then feeds that exact raw payload into both:

1. the isolated Step-7G first-party schedule adapter; and
2. the frozen Step-4C normalizer via an in-process monkeypatch of its fetcher.

No frozen source file is modified. No sportsbook, Supabase, scheduler, model,
feed publication, or production activation is performed.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import sports_api.wnba_schedule as frozen
import sports_api.wnba_step7g_first_party_schedule as first_party

REPORT_PATH = Path("step7g-first-party-schedule-parity.json")
SEASON = 2026
FIXED_RETRIEVED_AT = "2026-08-27T18:00:00+00:00"
REFERENCE_SOURCE_URL = "https://www.wnba.com/api/schedule?season=2026"


def _date_blocks(payload: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    root = frozen._schedule_root(payload)
    result: list[tuple[str, list[dict[str, Any]]]] = []
    for block in root.get("gameDates", []):
        if not isinstance(block, dict):
            continue
        day = frozen._date_block_iso(block.get("gameDate"))
        games = block.get("games")
        if day is None or not isinstance(games, list):
            continue
        result.append((day, [game for game in games if isinstance(game, dict)]))
    return result


def _verification_comparable(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    for key in (
        "source_url",
        "source_variant",
        "verified_at_utc",
        "source_retrieved_at_utc",
    ):
        result.pop(key, None)
    return result


def _daily_comparable(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    for key in (
        "source_url",
        "source_variant",
        "retrieved_at_utc",
        "cache_hit",
    ):
        result.pop(key, None)
    return result


def _first_party_fetcher(payload: dict[str, Any]):
    def fetch(season: int):
        if int(season) != SEASON:
            raise AssertionError(f"unexpected first-party parity season: {season}")
        return (
            deepcopy(payload),
            FIXED_RETRIEVED_AT,
            first_party.FIRST_PARTY_SOURCE_VARIANT,
            REFERENCE_SOURCE_URL,
            False,
        )
    return fetch


def _frozen_fetcher(payload: dict[str, Any]):
    def fetch(season: int):
        if int(season) != SEASON:
            raise AssertionError(f"unexpected frozen parity season: {season}")
        return (
            deepcopy(payload),
            FIXED_RETRIEVED_AT,
            "parity_reference_same_raw_payload",
            REFERENCE_SOURCE_URL,
            False,
        )
    return fetch


def build_report() -> dict[str, Any]:
    first_party._CACHE.clear()
    payload, retrieved_at, source_variant, source_url, cache_hit = (
        first_party._fetch_first_party_schedule_payload(SEASON)
    )
    root = frozen._schedule_root(payload)
    if str(root.get("leagueId")) != frozen.WNBA_LEAGUE_ID:
        raise RuntimeError("First-party schedule parity payload returned wrong league ID.")
    if str(root.get("seasonYear")) != str(SEASON):
        raise RuntimeError("First-party schedule parity payload returned wrong season.")

    blocks = _date_blocks(payload)
    if not blocks:
        raise RuntimeError("First-party schedule parity payload contains no usable date blocks.")

    raw_game_ids: list[str] = []
    invalid_raw_game_ids: list[str] = []
    for _, games in blocks:
        for game in games:
            gid = str(game.get("gameId") or "").strip()
            if len(gid) == 10 and gid.isdigit():
                raw_game_ids.append(gid)
            else:
                invalid_raw_game_ids.append(gid)
    duplicates = sorted({gid for gid in raw_game_ids if raw_game_ids.count(gid) > 1})

    all_dates = sorted({day for day, _ in blocks})
    parsed_dates = [date.fromisoformat(day) for day in all_dates]
    empty_candidate = min(parsed_dates) - timedelta(days=1)
    empty_date = empty_candidate.isoformat()
    while empty_date in all_dates:
        empty_candidate -= timedelta(days=1)
        empty_date = empty_candidate.isoformat()

    test_dates = list(all_dates) + [empty_date]
    daily_mismatches: list[dict[str, Any]] = []
    verification_mismatches: list[dict[str, Any]] = []
    integrity_pass_dates = 0
    integrity_fail_dates = 0
    mapped_normalized_games = 0
    unmapped_normalized_games = 0
    normalized_game_count = 0

    first_fetch = _first_party_fetcher(payload)
    frozen_fetch = _frozen_fetcher(payload)
    with patch.object(first_party, "_fetch_first_party_schedule_payload", side_effect=first_fetch), patch.object(
        frozen, "_fetch_schedule_payload", side_effect=frozen_fetch
    ):
        for target_date in test_dates:
            candidate_daily = first_party.get_step7g_daily_schedule_dataset(target_date, SEASON)
            reference_daily = frozen.get_daily_schedule_dataset(target_date, SEASON)
            if _daily_comparable(candidate_daily) != _daily_comparable(reference_daily):
                daily_mismatches.append(
                    {
                        "date": target_date,
                        "candidate_game_count": candidate_daily.get("game_count"),
                        "reference_game_count": reference_daily.get("game_count"),
                        "candidate_game_ids": [row.get("game_id") for row in candidate_daily.get("games", [])],
                        "reference_game_ids": [row.get("game_id") for row in reference_daily.get("games", [])],
                    }
                )

            candidate_verify = first_party.verify_step7g_daily_slate_dataset(target_date, SEASON)
            reference_verify = frozen.verify_daily_slate_dataset(target_date, SEASON)
            if _verification_comparable(candidate_verify) != _verification_comparable(reference_verify):
                verification_mismatches.append(
                    {
                        "date": target_date,
                        "candidate_slate": deepcopy(candidate_verify.get("slate")),
                        "reference_slate": deepcopy(reference_verify.get("slate")),
                        "candidate_status_summary": deepcopy(candidate_verify.get("status_summary")),
                        "reference_status_summary": deepcopy(reference_verify.get("status_summary")),
                    }
                )

            if target_date in all_dates:
                if (candidate_verify.get("slate") or {}).get("slate_integrity_pass") is True:
                    integrity_pass_dates += 1
                else:
                    integrity_fail_dates += 1
                for game in candidate_daily.get("games", []):
                    normalized_game_count += 1
                    verification = game.get("verification") or {}
                    if verification.get("teams_mapped_to_registry") is True:
                        mapped_normalized_games += 1
                    else:
                        unmapped_normalized_games += 1

    representative_dates = [all_dates[0]]
    if "2026-08-27" in all_dates:
        representative_dates.append("2026-08-27")
    middle = all_dates[len(all_dates) // 2]
    if middle not in representative_dates:
        representative_dates.append(middle)
    if all_dates[-1] not in representative_dates:
        representative_dates.append(all_dates[-1])
    representative_dates.append(empty_date)

    parity_pass = not daily_mismatches and not verification_mismatches
    raw_identity_pass = (
        len(raw_game_ids) >= 300
        and not invalid_raw_game_ids
        and not duplicates
        and str(root.get("leagueId")) == "10"
        and str(root.get("seasonYear")) == str(SEASON)
    )

    report = {
        "data_type": "wnba_step7g_first_party_schedule_parity_v1",
        "season": SEASON,
        "read_only": True,
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "frozen_shared_provider_behavior_changed": False,
        "live_source_probe": {
            "source_variant": source_variant,
            "source_url": source_url,
            "retrieved_at_utc": retrieved_at,
            "cache_hit": cache_hit,
            "league_id": root.get("leagueId"),
            "season_year": root.get("seasonYear"),
            "date_block_count": len(blocks),
            "raw_valid_game_id_count": len(raw_game_ids),
            "invalid_raw_game_ids": invalid_raw_game_ids,
            "duplicate_raw_game_ids": duplicates,
        },
        "parity": {
            "tested_date_count": len(test_dates),
            "official_date_count": len(all_dates),
            "included_verified_empty_date": empty_date,
            "representative_dates": representative_dates,
            "daily_dataset_mismatch_count": len(daily_mismatches),
            "verification_mismatch_count": len(verification_mismatches),
            "daily_dataset_mismatches": daily_mismatches[:20],
            "verification_mismatches": verification_mismatches[:20],
            "exact_normalized_contract_parity": parity_pass,
            "raw_schedule_identity_pass": raw_identity_pass,
        },
        "season_normalization": {
            "normalized_game_count": normalized_game_count,
            "mapped_normalized_game_count": mapped_normalized_games,
            "unmapped_normalized_game_count": unmapped_normalized_games,
            "integrity_pass_date_count": integrity_pass_dates,
            "integrity_fail_date_count": integrity_fail_dates,
            "note": (
                "Integrity-fail dates are reported rather than hidden because the frozen contract "
                "must continue to fail closed on any unmapped/non-franchise identity."
            ),
        },
        "certification": {
            "first_party_route_returns_frozen_schedule_schema": raw_identity_pass,
            "adapter_reuses_frozen_normalization_semantics": parity_pass,
            "schedule_replacement_ready_for_step7g_injection_testing": raw_identity_pass and parity_pass,
            "production_activation_safe_now": False,
        },
        "next_required_step": (
            "Keep production OFF. After targeted frozen regressions pass, discover and certify "
            "first-party WNBA.com routes for the required player-history and exact rotation core "
            "dependencies before injecting this schedule getter into the Step 7G one-shot."
        ),
    }
    return report


def main() -> int:
    try:
        report = build_report()
    except Exception as exc:
        report = {
            "data_type": "wnba_step7g_first_party_schedule_parity_v1",
            "season": SEASON,
            "read_only": True,
            "production_mutation_performed": False,
            "supabase_mutation_performed": False,
            "sportsbook_called": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "frozen_shared_provider_behavior_changed": False,
            "parity_completed": False,
            "error_type": type(exc).__name__,
            "error_message_returned": False,
            "production_activation_safe_now": False,
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        raise

    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    certification = report["certification"]
    if certification["first_party_route_returns_frozen_schedule_schema"] is not True:
        raise RuntimeError("Step 7G first-party schedule raw identity certification failed.")
    if certification["adapter_reuses_frozen_normalization_semantics"] is not True:
        raise RuntimeError("Step 7G first-party schedule parity certification failed.")
    if certification["production_activation_safe_now"] is not False:
        raise RuntimeError("Schedule parity must never certify production activation by itself.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
