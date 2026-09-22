from __future__ import annotations

import copy

import pytest

from sports_api.monster_page_factory_v1 import totals_page
from sports_api.monster_test_matrix_v1 import (
    MAY_MODIFY_PROJECTION,
    MAY_MODIFY_SOURCE_DATA,
    MATRIX_VERSION,
    PROJECTION_WEIGHT,
    Disposition,
    Patch,
    Scenario,
    ScenarioCategory,
    apply_scenario,
    baseline_totals_payload,
    default_scenarios,
    main,
    run_matrix,
    run_scenario,
    run_totals_matrix,
    validate_matrix,
)


def _scenario(scenario_id: str) -> Scenario:
    return next(item for item in default_scenarios() if item.scenario_id == scenario_id)


def test_matrix_has_broad_unique_edge_case_coverage() -> None:
    scenarios = default_scenarios()
    validate_matrix(scenarios)
    assert len(scenarios) >= 20
    assert len({item.scenario_id for item in scenarios}) == len(scenarios)
    assert {item.category for item in scenarios} == set(ScenarioCategory)


def test_full_cfb_totals_matrix_passes() -> None:
    report = run_totals_matrix("CFB")
    assert report.version == MATRIX_VERSION
    assert report.sport == "College Football"
    assert report.market == "Game Total"
    assert report.passed is True
    assert report.failed_count == 0
    assert report.passed_count == len(default_scenarios())


def test_matrix_is_sport_agnostic_for_shared_page_contract() -> None:
    for sport in ("NFL", "MLB", "WNBA", "NBA", "NHL"):
        report = run_totals_matrix(sport)
        assert report.passed is True
        assert report.failed_count == 0


def test_missing_optional_market_gracefully_degrades() -> None:
    spec = totals_page("CFB")
    baseline = baseline_totals_payload(sport=spec.sport)
    result = run_scenario(spec, baseline, _scenario("missing-odds"))
    assert result.passed is True
    assert result.actual is Disposition.GRACEFUL_DEGRADE
    assert result.page_ready is True
    assert "market" in result.skipped_optional


def test_missing_required_enrichment_fails_closed() -> None:
    spec = totals_page("CFB")
    baseline = baseline_totals_payload(sport=spec.sport)
    result = run_scenario(spec, baseline, _scenario("missing-team-comparison"))
    assert result.passed is True
    assert result.actual is Disposition.FAIL_CLOSED
    assert result.page_ready is False
    assert result.missing_required == ("team_comparison",)


def test_missing_projection_fails_closed_without_rewriting_baseline() -> None:
    spec = totals_page("CFB")
    baseline = baseline_totals_payload(sport=spec.sport)
    before = copy.deepcopy(baseline)
    result = run_scenario(spec, baseline, _scenario("missing-projection"))
    assert result.actual is Disposition.FAIL_CLOSED
    assert result.missing_required == ("projection",)
    assert baseline == before


def test_stale_market_is_suppressed_and_page_remains_ready() -> None:
    spec = totals_page("CFB")
    baseline = baseline_totals_payload(sport=spec.sport)
    result = run_scenario(spec, baseline, _scenario("stale-market"))
    assert result.passed is True
    assert result.actual is Disposition.GRACEFUL_DEGRADE
    assert result.page_ready is True
    assert "market" in result.skipped_optional
    assert "stale market suppressed" in result.reason


@pytest.mark.parametrize(
    "scenario_id",
    ["missing-official-id", "synthetic-id", "duplicate-event-id"],
)
def test_bad_identity_is_rejected_before_page_compile(scenario_id: str) -> None:
    spec = totals_page("CFB")
    baseline = baseline_totals_payload(sport=spec.sport)
    result = run_scenario(spec, baseline, _scenario(scenario_id))
    assert result.passed is True
    assert result.actual is Disposition.REJECT_INPUT
    assert result.page_ready is False


@pytest.mark.parametrize("scenario_id", ["postponed-game", "cancelled-game"])
def test_non_playable_game_lifecycle_is_skipped(scenario_id: str) -> None:
    spec = totals_page("CFB")
    baseline = baseline_totals_payload(sport=spec.sport)
    result = run_scenario(spec, baseline, _scenario(scenario_id))
    assert result.passed is True
    assert result.actual is Disposition.SKIP_EVENT
    assert result.page_ready is False


def test_tomorrow_future_and_mixed_division_remain_eligible() -> None:
    spec = totals_page("CFB")
    baseline = baseline_totals_payload(sport=spec.sport)
    for scenario_id in ("tomorrow-slate", "future-slate", "mixed-division-valid"):
        result = run_scenario(spec, baseline, _scenario(scenario_id))
        assert result.passed is True
        assert result.actual is Disposition.PASS_THROUGH
        assert result.page_ready is True


def test_optional_provider_failures_are_isolated() -> None:
    spec = totals_page("CFB")
    baseline = baseline_totals_payload(sport=spec.sport)
    for scenario_id in (
        "injuries-unavailable",
        "sources-unavailable",
        "provider-timeout",
        "malformed-optional-provider",
        "missing-environment",
    ):
        result = run_scenario(spec, baseline, _scenario(scenario_id))
        assert result.passed is True
        assert result.actual is Disposition.GRACEFUL_DEGRADE
        assert result.page_ready is True
        assert result.skipped_optional


def test_missing_broadcast_does_not_block_valid_environment() -> None:
    spec = totals_page("CFB")
    baseline = baseline_totals_payload(sport=spec.sport)
    result = run_scenario(spec, baseline, _scenario("missing-broadcast"))
    assert result.passed is True
    assert result.actual is Disposition.PASS_THROUGH
    assert result.page_ready is True


def test_apply_scenario_never_mutates_caller_payload() -> None:
    baseline = baseline_totals_payload()
    before = copy.deepcopy(baseline)
    mutated = apply_scenario(
        baseline,
        Scenario(
            "copy-contract",
            "Copy contract",
            ScenarioCategory.PROVIDER,
            Disposition.GRACEFUL_DEGRADE,
            drops=("market",),
            patches=(Patch("diagnostics", {"status": "changed-in-copy"}),),
        ),
    )
    assert baseline == before
    assert "market" not in mutated
    assert mutated["diagnostics"] != baseline["diagnostics"]


def test_permanent_safety_invariants_are_zero_write() -> None:
    assert PROJECTION_WEIGHT == 0.0
    assert MAY_MODIFY_PROJECTION is False
    assert MAY_MODIFY_SOURCE_DATA is False
    report = run_totals_matrix("CFB")
    for result in report.results:
        assert all(result.safety.values())


def test_matrix_report_exposes_category_counts_and_serializes() -> None:
    report = run_matrix(
        totals_page("CFB"),
        baseline_totals_payload(),
        default_scenarios(),
    )
    payload = report.as_dict()
    assert payload["version"] == MATRIX_VERSION
    assert payload["scenario_count"] == len(default_scenarios())
    assert payload["failed_count"] == 0
    assert payload["category_counts"]["identity"] >= 3
    assert payload["projection_weight"] == 0.0


def test_validate_matrix_rejects_duplicate_ids() -> None:
    duplicate = Scenario(
        "dup",
        "Duplicate id",
        ScenarioCategory.BASELINE,
        Disposition.PASS_THROUGH,
    )
    with pytest.raises(ValueError, match="scenario ids must be unique"):
        validate_matrix(tuple([duplicate] * 20))


def test_cli_returns_success_for_green_matrix(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--sport", "CFB"]) == 0
    output = capsys.readouterr().out
    assert MATRIX_VERSION in output
    assert "passed=" in output
    assert "[PASS] stale-market" in output
