"""CFB Top Picks Research V2 Step 3 — live 10-pick history certification."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

import cfb_schedule_v7_future_slate as schedule
import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_history_router_v1 as history


def run(artifact_dir: str | Path = "artifacts/cfb-top-picks-research-v2-step3") -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    required_picks = 10
    picks, diag = engine.build_top_picks(limit=required_picks)
    if len(picks) != required_picks:
        raise AssertionError(f"CFB_TOP_PICKS_RESEARCH_V2_STEP3_PICK_COUNT:{len(picks)}")

    slate_day = str(diag.get("slate_date") or "").strip()
    games = schedule.games_for_date(slate_day)
    by_event = {
        str(game.get("espn_event_id") or game.get("game_id") or "").strip(): dict(game)
        for game in games
    }

    def resolve(row):
        event_id = str(row.get("event_id") or "").strip()
        game = by_event.get(event_id) or {
            "espn_event_id": event_id,
            "game_id": event_id,
            "game_date": slate_day,
            "away_team": row.get("away"),
            "home_team": row.get("home"),
            "away_espn_team_id": row.get("away_team_id"),
            "home_espn_team_id": row.get("home_team_id"),
        }
        return row, history.resolve_matchup_history(row, game)

    resolved = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(resolve, row) for row in picks]
        for future in as_completed(futures):
            resolved.append(future.result())

    evidence = []
    virginia_fsu_seen = False
    for row, result in sorted(resolved, key=lambda pair: int(pair[0].get("rank") or 99)):
        status = str(result.get("status") or "")
        if status not in history.TERMINAL_STATUSES:
            raise AssertionError(f"CFB_TOP_PICKS_RESEARCH_V2_STEP3_NON_TERMINAL:{status}")
        attempted = list(result.get("sources_attempted") or [])
        if int(result.get("source_count_attempted") or 0) < history.MIN_INDEPENDENT_SOURCES:
            raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP3_SOURCE_COUNT")
        if len(attempted) < history.MIN_INDEPENDENT_SOURCES:
            raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP3_ATTEMPT_EVIDENCE")
        if not str(result.get("observed_at") or "").strip():
            raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP3_OBSERVED_AT_MISSING")

        if status == history.VERIFIED_NO_HISTORY:
            if result.get("sources_exhausted") is not True or result.get("no_history_claim_allowed") is not True:
                raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP3_FALSE_NO_HISTORY")
        elif result.get("no_history_claim_allowed") is True:
            raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP3_ILLEGAL_NO_HISTORY_PERMISSION")

        if status == history.VERIFIED_HISTORY and int(result.get("meetings") or 0) <= 0:
            raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP3_HISTORY_WITHOUT_MEETING")

        names = {
            str(row.get("away") or "").strip().casefold(),
            str(row.get("home") or "").strip().casefold(),
        }
        if "virginia" in names and "florida state" in names:
            virginia_fsu_seen = True
            if status != history.VERIFIED_HISTORY:
                raise AssertionError(
                    "CFB_TOP_PICKS_RESEARCH_V2_STEP3_VIRGINIA_FSU_HISTORY_NOT_RECOVERED"
                )

        evidence.append({
            "rank": int(row.get("rank") or 0),
            "event_id": str(row.get("event_id") or ""),
            "away": str(row.get("away") or ""),
            "home": str(row.get("home") or ""),
            "status": status,
            "meetings": int(result.get("meetings") or 0),
            "sources_attempted": attempted,
            "sources_verified": list(result.get("sources_verified") or []),
            "source_count_attempted": int(result.get("source_count_attempted") or 0),
            "source_count_verified": int(result.get("source_count_verified") or 0),
            "no_history_claim_allowed": bool(result.get("no_history_claim_allowed")),
            "observed_at": str(result.get("observed_at") or ""),
        })

    payload = {
        "status": "GREEN",
        "slate_day": slate_day,
        "required_picks": required_picks,
        "terminal_picks": len(evidence),
        "virginia_fsu_seen": virginia_fsu_seen,
        "verified_history_count": sum(item["status"] == history.VERIFIED_HISTORY for item in evidence),
        "verified_no_history_count": sum(item["status"] == history.VERIFIED_NO_HISTORY for item in evidence),
        "source_review_count": sum(item["status"] == history.SOURCE_CONFLICT_REVIEW for item in evidence),
        "picks": evidence,
    }
    (artifacts / "cfb_top_picks_research_v2_step3_history.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP3_10_HISTORY_TERMINAL_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP3_NO_FALSE_NO_HISTORY_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP3_MULTI_SOURCE_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP3_FROZEN_GREEN")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


if __name__ == "__main__":
    run()
