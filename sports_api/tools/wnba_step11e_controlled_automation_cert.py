"""Offline final certification for WNBA Step 11E controlled automation + Step 11 freeze."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step11_controlled_automation as s11e
from sports_api import wnba_step11_draftkings_provider as dk
from sports_api import wnba_step11_fanduel_provider as fd
from sports_api import wnba_step11_release_freeze as release
from sports_api.tools import wnba_step11d_multibook_shadow_board_cert as s11dcert

UTC = timezone.utc
BRANCH = "wnba-step11e-controlled-automation-freeze-20260828"
CERT_MARKER = "STEP11_FINAL_CONTROLLED_AUTOMATION_FROZEN_CERTIFIED"
OUTPUT_PATH = Path("step11e-final-controlled-automation-cert.json")
T0 = datetime(2026, 8, 28, 6, 20, 0, tzinfo=UTC)


def _env() -> dict[str, str]:
    result = s11dcert._env()
    result["WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED"] = "true"
    return result


def _distributions() -> list[dict]:
    return [
        s11dcert._distribution(player_id, stat, probability)
        for player_id, stat, _line, probability in s11dcert.PROPS
    ]


def _success_tick(at: datetime, previous_state=None) -> dict:
    return s11e.run_step11e_controlled_automation_tick(
        season=2026,
        slate_date="2026-08-28",
        step8_distributions=_distributions(),
        previous_state=previous_state,
        evaluated_at=at,
        draftkings_fetcher=s11dcert._fetcher(s11dcert._bridge(dk.PROVIDER)),
        fanduel_fetcher=s11dcert._fetcher(s11dcert._bridge(fd.PROVIDER)),
        qualification_policy={"top_n": 5, "minimum_books_at_line": 2},
        env=_env(),
    )


def _fail_dk(**kwargs):
    raise dk.WNBAStep11DraftKingsProviderUpstreamError("synthetic transient outage")


def _fail_fd(**kwargs):
    raise fd.WNBAStep11FanDuelProviderUpstreamError("synthetic transient outage")


def _failure_tick(at: datetime, previous_state) -> dict:
    return s11e.run_step11e_controlled_automation_tick(
        season=2026,
        slate_date="2026-08-28",
        step8_distributions=_distributions(),
        previous_state=previous_state,
        evaluated_at=at,
        draftkings_fetcher=_fail_dk,
        fanduel_fetcher=_fail_fd,
        qualification_policy={"top_n": 5, "minimum_books_at_line": 2},
        env=_env(),
    )


def _bomb(**kwargs):
    raise AssertionError("provider fetcher must not run while tick is not due/circuit is open")


def main() -> None:
    first = _success_tick(T0)
    assert first["status"] == "healthy"
    shadow = first["shadow_board_result"]
    assert shadow["sportsbooks"] == ["DraftKings", "FanDuel"]
    assert shadow["shadow_summary"]["eligible_market_record_count"] == 8
    assert shadow["shadow_summary"]["exact_line_multibook_group_count"] == 4
    assert shadow["shadow_summary"]["qualified_prop_count"] == 4
    assert shadow["shadow_summary"]["top_card_count"] == 4
    assert shadow["market_audit"]["different_lines_blended"] is False

    not_due = s11e.run_step11e_controlled_automation_tick(
        season=2026,
        slate_date="2026-08-28",
        step8_distributions=_distributions(),
        previous_state=first["automation_state"],
        evaluated_at=T0 + timedelta(seconds=30),
        draftkings_fetcher=_bomb,
        fanduel_fetcher=_bomb,
        env=_env(),
    )
    assert not_due["status"] == "not_due"
    assert not_due["execution"]["cycle_executed"] is False

    state = not_due["automation_state"]
    failures = []
    for seconds in (60, 120, 180):
        failed = _failure_tick(T0 + timedelta(seconds=seconds), state)
        failures.append(failed["status"])
        state = failed["automation_state"]
    assert failures == ["transient_failure", "transient_failure", "circuit_opened"]
    assert state["circuit_state"] == "open"
    assert state["consecutive_failure_count"] == 3
    assert state["circuit_open_until_utc"] == (T0 + timedelta(seconds=360)).isoformat()

    blocked = s11e.run_step11e_controlled_automation_tick(
        season=2026,
        slate_date="2026-08-28",
        step8_distributions=_distributions(),
        previous_state=state,
        evaluated_at=T0 + timedelta(seconds=240),
        draftkings_fetcher=_bomb,
        fanduel_fetcher=_bomb,
        env=_env(),
    )
    assert blocked["status"] == "circuit_open"
    assert blocked["execution"]["cycle_executed"] is False

    recovered = _success_tick(T0 + timedelta(seconds=360), blocked["automation_state"])
    assert recovered["status"] == "half_open_recovered"
    assert recovered["execution"]["half_open_probe"] is True
    assert recovered["automation_state"]["circuit_state"] == "closed"
    assert recovered["automation_state"]["consecutive_failure_count"] == 0

    guards = recovered["guardrails"]
    for key in (
        "background_scheduler_started",
        "sleep_performed",
        "authentication_used",
        "cookies_used",
        "wager_action_performed",
        "state_persisted",
        "public_fastapi_route_added",
        "supabase_mutated",
        "persistence_mutated",
        "production_runtime_enabled",
        "production_activation_allowed",
        "basketball_projection_changed",
        "step8_distribution_changed",
    ):
        assert guards[key] is False, key

    assert release.DEFAULT_ENABLED is False
    assert release.PRODUCTION_ACTIVATION_ALLOWED is False
    assert release.BACKGROUND_SCHEDULER_ALLOWED is False
    assert release.PUBLIC_FASTAPI_ACTIVATION_ALLOWED is False
    assert all(value is False for value in release.SAFETY_CONTRACT.values())

    evidence = {
        "data_type": "wnba_step11e_final_controlled_automation_cert_v1",
        "certification_result": CERT_MARKER,
        "branch": BRANCH,
        "github_head_sha": os.environ.get("GITHUB_SHA"),
        "release_id": release.RELEASE_ID,
        "schema_version": s11e.SCHEMA_VERSION,
        "model_version": s11e.MODEL_VERSION,
        "frozen_lineage": {
            "step11a_sha": release.STEP11A_FROZEN_SHA,
            "step11b_sha": release.STEP11B_FROZEN_SHA,
            "step11c_sha": release.STEP11C_FROZEN_SHA,
            "step11d_sha": release.STEP11D_FROZEN_SHA,
            "step10_sha": release.STEP10_FROZEN_SHA,
            "step9_sha": release.STEP9_FROZEN_SHA,
            "step8_sha": release.STEP8_FROZEN_SHA,
        },
        "certified_sequence": {
            "statuses": [
                first["status"],
                not_due["status"],
                *failures,
                blocked["status"],
                recovered["status"],
            ],
            "circuit_failure_threshold": s11e.DEFAULT_FAILURE_THRESHOLD,
            "circuit_cooldown_seconds": s11e.DEFAULT_CIRCUIT_COOLDOWN_SECONDS,
            "refresh_interval_seconds": s11e.DEFAULT_REFRESH_INTERVAL_SECONDS,
            "final_state_content_sha256": recovered["automation_state"]["state_content_sha256"],
            "first_shadow_board_content_sha256": first["execution"]["shadow_board_content_sha256"],
            "first_step10_pipeline_content_sha256": first["execution"]["step10_pipeline_content_sha256"],
            "first_step9_ranking_content_sha256": first["execution"]["step9_ranking_content_sha256"],
            "eligible_market_record_count": shadow["shadow_summary"]["eligible_market_record_count"],
            "exact_line_multibook_group_count": shadow["shadow_summary"]["exact_line_multibook_group_count"],
            "qualified_prop_count": shadow["shadow_summary"]["qualified_prop_count"],
            "top_card_count": shadow["shadow_summary"]["top_card_count"],
        },
        "safety": {
            "shadow_only": True,
            "caller_driven_tick_only": True,
            "background_scheduler_started": False,
            "sleep_performed": False,
            "state_persisted": False,
            "public_fastapi_route_added": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
            "wager_action_performed": False,
            "different_lines_blended": False,
        },
    }
    OUTPUT_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(CERT_MARKER)


if __name__ == "__main__":
    main()
