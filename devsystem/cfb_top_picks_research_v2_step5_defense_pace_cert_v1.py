"""CFB Top Picks Research V2 Step 5 — live 10-pick defense + pace certification."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

import cfb_schedule_v7_future_slate as schedule
import cfb_top_picks_engine_v1 as top_engine
import cfb_top_picks_defense_pace_research_v1 as research


def run(artifact_dir: str | Path = "artifacts/cfb-top-picks-research-v2-step5") -> dict:
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    required_picks = 10
    required_teams = 20
    picks, diag = top_engine.build_top_picks(limit=required_picks)
    if len(picks) != required_picks:
        raise AssertionError(f"CFB_TOP_PICKS_RESEARCH_V2_STEP5_PICK_COUNT:{len(picks)}")

    slate_day = str(diag.get("slate_date") or "").strip()
    games = schedule.games_for_date(slate_day)
    by_event = {
        str(game.get("espn_event_id") or game.get("game_id") or "").strip(): dict(game)
        for game in games
    }

    def one(row):
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
        return row, research.build_defense_pace_research(row, game, slate_day)

    resolved = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(one, row) for row in picks]
        for future in as_completed(futures):
            resolved.append(future.result())

    team_evidence = []
    for row, result in sorted(resolved, key=lambda pair: int(pair[0].get("rank") or 99)):
        if result.get("api2_used") is not False:
            raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP5_API2_USED")
        if float(result.get("projection_weight") or 0.0) != 0.0:
            raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP5_PROJECTION_WEIGHT")
        if result.get("may_modify_probability") is not False:
            raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP5_PROBABILITY_MUTATION")
        if result.get("may_modify_ranking") is not False:
            raise AssertionError("CFB_TOP_PICKS_RESEARCH_V2_STEP5_RANKING_MUTATION")

        for side in ("away", "home"):
            profile = result.get(side) or {}
            team_id = str(profile.get("team_id") or "")
            if not team_id.isdigit():
                raise AssertionError(
                    f"CFB_TOP_PICKS_RESEARCH_V2_STEP5_BAD_TEAM_ID:{side}:{team_id}"
                )

            if int(profile.get("core_ready") or 0) != len(research.CORE_FIELDS):
                raise AssertionError(
                    "CFB_TOP_PICKS_RESEARCH_V2_STEP5_CORE_INCOMPLETE:"
                    + str(profile.get("team") or "")
                    + ":"
                    + str(profile.get("core_ready"))
                )

            metrics = profile.get("metrics") or {}
            for field in research.CORE_FIELDS:
                metric = metrics.get(field) or {}
                if metric.get("value") is None:
                    raise AssertionError(
                        f"CFB_TOP_PICKS_RESEARCH_V2_STEP5_CORE_VALUE_MISSING:{field}"
                    )
                if not str(metric.get("source") or "").strip():
                    raise AssertionError(
                        f"CFB_TOP_PICKS_RESEARCH_V2_STEP5_SOURCE_MISSING:{field}"
                    )
                if not str(metric.get("observed_at") or "").strip():
                    raise AssertionError(
                        f"CFB_TOP_PICKS_RESEARCH_V2_STEP5_OBSERVED_AT_MISSING:{field}"
                    )

            for field in research.SUPPORTING_FIELDS:
                metric = metrics.get(field) or {}
                status = str(metric.get("status") or "")
                if status not in {"VERIFIED", "VERIFIED_FALLBACK", "UNAVAILABLE"}:
                    raise AssertionError(
                        f"CFB_TOP_PICKS_RESEARCH_V2_STEP5_BAD_SUPPORT_STATUS:{field}:{status}"
                    )
                if metric.get("value") is not None:
                    if not str(metric.get("source") or "").strip():
                        raise AssertionError(
                            f"CFB_TOP_PICKS_RESEARCH_V2_STEP5_SUPPORT_SOURCE_MISSING:{field}"
                        )
                    if not str(metric.get("observed_at") or "").strip():
                        raise AssertionError(
                            f"CFB_TOP_PICKS_RESEARCH_V2_STEP5_SUPPORT_OBSERVED_AT_MISSING:{field}"
                        )

            if int(profile.get("supporting_ready") or 0) < 2:
                raise AssertionError(
                    "CFB_TOP_PICKS_RESEARCH_V2_STEP5_SUPPORT_TOO_THIN:"
                    + str(profile.get("team") or "")
                    + ":"
                    + str(profile.get("supporting_ready"))
                )

            team_evidence.append({
                "rank": int(row.get("rank") or 0),
                "side": side,
                "team": str(profile.get("team") or ""),
                "team_id": team_id,
                "division": str(profile.get("division") or ""),
                "core_ready": int(profile.get("core_ready") or 0),
                "supporting_ready": int(profile.get("supporting_ready") or 0),
                "metrics": metrics,
                "observed_at": str(profile.get("observed_at") or ""),
            })

    if len(team_evidence) != required_teams:
        raise AssertionError(
            f"CFB_TOP_PICKS_RESEARCH_V2_STEP5_TEAM_COUNT:{len(team_evidence)}"
        )

    payload = {
        "status": "GREEN",
        "slate_day": slate_day,
        "required_picks": required_picks,
        "required_teams": required_teams,
        "teams_certified": len(team_evidence),
        "core_fields_per_team": len(research.CORE_FIELDS),
        "supporting_fields_per_team": len(research.SUPPORTING_FIELDS),
        "teams": team_evidence,
    }
    (artifacts / "cfb_top_picks_research_v2_step5_defense_pace.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP5_20_TEAM_DEFENSE_PACE_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP5_PROVENANCE_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP5_MULTI_SOURCE_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP5_FROZEN_GREEN")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


if __name__ == "__main__":
    run()
