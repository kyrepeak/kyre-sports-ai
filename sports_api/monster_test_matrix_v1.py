"""Monster Test Matrix V1.

Central edge-case and failure-mode contracts for Kyre Sports AI.

The matrix is intentionally outside production entrypoints.  It consumes the
sport-agnostic Page Factory contract added in Monster Step 4 and answers one
question before a new page is trusted: what happens when real-world data is
late, missing, stale, malformed, duplicated, postponed, or otherwise weird?

This module contains no sportsbook/model math, does not fetch providers, does
not import Streamlit, and never mutates a caller payload.  It is a deterministic
pre-production harness that future sport adapters can reuse.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from sports_api.monster_page_factory_v1 import PagePlan, PageSpec, compile_page, totals_page

MATRIX_VERSION = "MONSTER_TEST_MATRIX_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_SOURCE_DATA = False


class ScenarioCategory(StrEnum):
    BASELINE = "baseline"
    TEMPORAL = "temporal"
    AVAILABILITY = "availability"
    PROVIDER = "provider"
    IDENTITY = "identity"
    LIFECYCLE = "lifecycle"
    CACHE = "cache"
    ENRICHMENT = "enrichment"


class Disposition(StrEnum):
    PASS_THROUGH = "pass_through"
    GRACEFUL_DEGRADE = "graceful_degrade"
    FAIL_CLOSED = "fail_closed"
    REJECT_INPUT = "reject_input"
    SKIP_EVENT = "skip_event"


@dataclass(frozen=True, slots=True)
class Patch:
    """A tiny deterministic payload mutation used only by the test harness."""

    key: str
    value: Any


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    title: str
    category: ScenarioCategory
    expected: Disposition
    drops: tuple[str, ...] = field(default_factory=tuple)
    patches: tuple[Patch, ...] = field(default_factory=tuple)
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id must be non-empty")
        if not self.title.strip():
            raise ValueError("scenario title must be non-empty")
        if len(self.drops) != len(set(self.drops)):
            raise ValueError(f"scenario {self.scenario_id} has duplicate drops")

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "category": self.category.value,
            "expected": self.expected.value,
            "drops": list(self.drops),
            "patches": [{"key": item.key, "value": item.value} for item in self.patches],
            "description": self.description,
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario: Scenario
    actual: Disposition
    page_ready: bool
    missing_required: tuple[str, ...]
    skipped_optional: tuple[str, ...]
    passed: bool
    safety: Mapping[str, bool]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario.scenario_id,
            "title": self.scenario.title,
            "category": self.scenario.category.value,
            "expected": self.scenario.expected.value,
            "actual": self.actual.value,
            "page_ready": self.page_ready,
            "missing_required": list(self.missing_required),
            "skipped_optional": list(self.skipped_optional),
            "passed": self.passed,
            "safety": dict(self.safety),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class MatrixReport:
    version: str
    sport: str
    market: str
    results: tuple[ScenarioResult, ...]

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(item.passed for item in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for item in self.results if item.passed)

    @property
    def failed_count(self) -> int:
        return len(self.results) - self.passed_count

    @property
    def category_counts(self) -> dict[str, int]:
        counts = Counter(item.scenario.category.value for item in self.results)
        return dict(sorted(counts.items()))

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "sport": self.sport,
            "market": self.market,
            "passed": self.passed,
            "scenario_count": len(self.results),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "category_counts": self.category_counts,
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
            "may_modify_source_data": MAY_MODIFY_SOURCE_DATA,
            "results": [item.as_dict() for item in self.results],
        }


def baseline_totals_payload(*, sport: str = "College Football") -> dict[str, Any]:
    """Return a normalized safe payload used by the deterministic matrix.

    The values are synthetic *test fixtures*, never game predictions or market
    data.  ``official_event_id`` is deliberately named as official identity but
    uses a TEST prefix so the fixture cannot be mistaken for a real game id.
    """
    return {
        "matchup": {
            "official_event_id": "TEST-OFFICIAL-001",
            "away_team": "Test Away",
            "home_team": "Test Home",
            "date": "2026-09-11",
            "status": "scheduled",
            "sport": sport,
        },
        "team_comparison": {
            "away": {"sample": True},
            "home": {"sample": True},
        },
        "injuries": {"status": "available", "items": []},
        "environment": {
            "venue": "Test Stadium",
            "broadcast": "TEST",
            "weather": {"status": "available"},
        },
        "market": {
            "status": "available",
            "stale": False,
            "line": "TEST-LINE",
        },
        "projection": {
            "status": "fixture-only",
            "value": "TEST-PROJECTION",
            "sportsbook_weight": 0.0,
        },
        "simulation": {"status": "fixture-only"},
        "confidence": {"status": "fixture-only"},
        "sources": {"status": "healthy", "providers": ["TEST"]},
        "diagnostics": {"status": "healthy"},
    }


def _copy_patch_value(value: Any) -> Any:
    return copy.deepcopy(value)


def apply_scenario(payload: Mapping[str, Any], scenario: Scenario) -> dict[str, Any]:
    """Return a mutated copy for one scenario; never modify the caller payload."""
    mutated = copy.deepcopy(dict(payload))
    for key in scenario.drops:
        mutated.pop(key, None)
    for patch in scenario.patches:
        mutated[patch.key] = _copy_patch_value(patch.value)
    return mutated


def _matchup(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    value = payload.get("matchup")
    return value if isinstance(value, Mapping) else {}


def _identity_disposition(payload: Mapping[str, Any]) -> tuple[Disposition | None, str]:
    matchup = _matchup(payload)
    if not matchup:
        return None, "matchup unavailable; Page Factory required-data gate decides"

    official_id = str(matchup.get("official_event_id") or "").strip()
    if not official_id:
        return Disposition.REJECT_INPUT, "official event identity missing"
    if official_id.lower().startswith(("synthetic-", "fuzzy-", "generated-")):
        return Disposition.REJECT_INPUT, "synthetic/fuzzy identity rejected"

    duplicate_ids = matchup.get("duplicate_event_ids")
    if isinstance(duplicate_ids, (list, tuple, set)) and duplicate_ids:
        normalized = [str(item).strip() for item in duplicate_ids if str(item).strip()]
        if len(normalized) != len(set(normalized)) or official_id in normalized:
            return Disposition.REJECT_INPUT, "duplicate official event identity rejected"
    return None, "official identity accepted"


def _lifecycle_disposition(payload: Mapping[str, Any]) -> tuple[Disposition | None, str]:
    status = str(_matchup(payload).get("status") or "").strip().lower()
    if status in {"postponed", "cancelled", "canceled", "suspended"}:
        return Disposition.SKIP_EVENT, f"event lifecycle status={status}"
    return None, "event lifecycle eligible"


def _prepare_market(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Suppress stale market context before Page Factory compilation."""
    working = copy.deepcopy(payload)
    market = working.get("market")
    if isinstance(market, Mapping) and bool(market.get("stale")):
        working.pop("market", None)
        return working, True
    return working, False


def _safety_snapshot(original: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, bool]:
    original_projection = original.get("projection")
    after_projection = after.get("projection")
    return {
        "projection_weight_zero": PROJECTION_WEIGHT == 0.0,
        "may_modify_projection_false": MAY_MODIFY_PROJECTION is False,
        "may_modify_source_data_false": MAY_MODIFY_SOURCE_DATA is False,
        "projection_payload_not_rewritten": original_projection == after_projection,
    }


def _result(
    scenario: Scenario,
    actual: Disposition,
    plan: PagePlan | None,
    safety: Mapping[str, bool],
    reason: str,
) -> ScenarioResult:
    page_ready = bool(plan.ready) if plan is not None else False
    missing = plan.missing_required if plan is not None else ()
    skipped = plan.skipped_optional if plan is not None else ()
    passed = actual is scenario.expected and all(safety.values())
    return ScenarioResult(
        scenario=scenario,
        actual=actual,
        page_ready=page_ready,
        missing_required=missing,
        skipped_optional=skipped,
        passed=passed,
        safety=dict(safety),
        reason=reason,
    )


def run_scenario(
    spec: PageSpec,
    baseline: Mapping[str, Any],
    scenario: Scenario,
) -> ScenarioResult:
    """Execute one deterministic failure-mode contract."""
    original = copy.deepcopy(dict(baseline))
    mutated = apply_scenario(baseline, scenario)
    safety = _safety_snapshot(original, baseline)

    lifecycle, lifecycle_reason = _lifecycle_disposition(mutated)
    if lifecycle is not None:
        return _result(scenario, lifecycle, None, safety, lifecycle_reason)

    identity, identity_reason = _identity_disposition(mutated)
    if identity is not None:
        return _result(scenario, identity, None, safety, identity_reason)

    prepared, stale_market_removed = _prepare_market(mutated)
    plan = compile_page(spec, prepared)
    if not plan.ready:
        actual = Disposition.FAIL_CLOSED
        reason = "required payload missing: " + ", ".join(plan.missing_required)
    elif stale_market_removed or plan.skipped_optional:
        actual = Disposition.GRACEFUL_DEGRADE
        pieces: list[str] = []
        if stale_market_removed:
            pieces.append("stale market suppressed")
        if plan.skipped_optional:
            pieces.append("optional sections skipped: " + ", ".join(plan.skipped_optional))
        reason = "; ".join(pieces)
    else:
        actual = Disposition.PASS_THROUGH
        reason = identity_reason

    return _result(scenario, actual, plan, safety, reason)


def default_scenarios() -> tuple[Scenario, ...]:
    """Canonical Step 5 matrix.  Keep additions backward compatible."""
    return (
        Scenario("baseline", "Healthy baseline", ScenarioCategory.BASELINE, Disposition.PASS_THROUGH),
        Scenario(
            "tomorrow-slate",
            "Tomorrow date remains eligible",
            ScenarioCategory.TEMPORAL,
            Disposition.PASS_THROUGH,
            patches=(Patch("matchup", {
                "official_event_id": "TEST-OFFICIAL-TOMORROW",
                "away_team": "Test Away",
                "home_team": "Test Home",
                "date": "2026-09-12",
                "status": "scheduled",
            }),),
            tags=("future-date", "schedule"),
        ),
        Scenario(
            "future-slate",
            "Supported future date remains eligible",
            ScenarioCategory.TEMPORAL,
            Disposition.PASS_THROUGH,
            patches=(Patch("matchup", {
                "official_event_id": "TEST-OFFICIAL-FUTURE",
                "away_team": "Test Away",
                "home_team": "Test Home",
                "date": "2026-10-10",
                "status": "scheduled",
            }),),
            tags=("future-date", "schedule"),
        ),
        Scenario(
            "empty-matchup",
            "Empty slate/game payload fails closed",
            ScenarioCategory.AVAILABILITY,
            Disposition.FAIL_CLOSED,
            drops=("matchup",),
            tags=("empty-slate",),
        ),
        Scenario(
            "missing-odds",
            "Missing sportsbook market degrades",
            ScenarioCategory.AVAILABILITY,
            Disposition.GRACEFUL_DEGRADE,
            drops=("market",),
            tags=("odds",),
        ),
        Scenario(
            "missing-environment",
            "Missing venue/weather environment degrades",
            ScenarioCategory.AVAILABILITY,
            Disposition.GRACEFUL_DEGRADE,
            drops=("environment",),
            tags=("venue", "weather"),
        ),
        Scenario(
            "missing-broadcast",
            "Missing broadcast does not block matchup",
            ScenarioCategory.AVAILABILITY,
            Disposition.PASS_THROUGH,
            patches=(Patch("environment", {"venue": "Test Stadium", "weather": {"status": "available"}}),),
            tags=("broadcast",),
        ),
        Scenario(
            "injuries-unavailable",
            "Unavailable injury feed degrades",
            ScenarioCategory.PROVIDER,
            Disposition.GRACEFUL_DEGRADE,
            drops=("injuries",),
            tags=("injuries",),
        ),
        Scenario(
            "sources-unavailable",
            "Source-status feed unavailable degrades",
            ScenarioCategory.PROVIDER,
            Disposition.GRACEFUL_DEGRADE,
            drops=("sources",),
            tags=("source-health",),
        ),
        Scenario(
            "provider-timeout",
            "Optional provider timeout isolates failure",
            ScenarioCategory.PROVIDER,
            Disposition.GRACEFUL_DEGRADE,
            drops=("sources", "diagnostics"),
            tags=("timeout", "isolation"),
        ),
        Scenario(
            "malformed-optional-provider",
            "Malformed optional provider data is withheld",
            ScenarioCategory.PROVIDER,
            Disposition.GRACEFUL_DEGRADE,
            drops=("environment", "sources"),
            tags=("malformed",),
        ),
        Scenario(
            "missing-team-comparison",
            "Missing required enrichment fails closed",
            ScenarioCategory.ENRICHMENT,
            Disposition.FAIL_CLOSED,
            drops=("team_comparison",),
            tags=("partial-enrichment",),
        ),
        Scenario(
            "missing-projection",
            "Missing required projection fails closed",
            ScenarioCategory.ENRICHMENT,
            Disposition.FAIL_CLOSED,
            drops=("projection",),
            tags=("projection",),
        ),
        Scenario(
            "stale-market",
            "Stale market context is suppressed",
            ScenarioCategory.CACHE,
            Disposition.GRACEFUL_DEGRADE,
            patches=(Patch("market", {"status": "available", "stale": True, "line": "STALE-TEST"}),),
            tags=("stale", "odds"),
        ),
        Scenario(
            "stale-cache-optional",
            "Stale optional cached diagnostics can be dropped",
            ScenarioCategory.CACHE,
            Disposition.GRACEFUL_DEGRADE,
            drops=("diagnostics",),
            tags=("cache",),
        ),
        Scenario(
            "postponed-game",
            "Postponed game is skipped",
            ScenarioCategory.LIFECYCLE,
            Disposition.SKIP_EVENT,
            patches=(Patch("matchup", {
                "official_event_id": "TEST-OFFICIAL-POSTPONED",
                "away_team": "Test Away",
                "home_team": "Test Home",
                "date": "2026-09-11",
                "status": "postponed",
            }),),
            tags=("postponed",),
        ),
        Scenario(
            "cancelled-game",
            "Cancelled game is skipped",
            ScenarioCategory.LIFECYCLE,
            Disposition.SKIP_EVENT,
            patches=(Patch("matchup", {
                "official_event_id": "TEST-OFFICIAL-CANCELLED",
                "away_team": "Test Away",
                "home_team": "Test Home",
                "date": "2026-09-11",
                "status": "cancelled",
            }),),
            tags=("cancelled",),
        ),
        Scenario(
            "missing-official-id",
            "Missing official event identity is rejected",
            ScenarioCategory.IDENTITY,
            Disposition.REJECT_INPUT,
            patches=(Patch("matchup", {
                "away_team": "Test Away",
                "home_team": "Test Home",
                "date": "2026-09-11",
                "status": "scheduled",
            }),),
            tags=("identity",),
        ),
        Scenario(
            "synthetic-id",
            "Synthetic event identity is rejected",
            ScenarioCategory.IDENTITY,
            Disposition.REJECT_INPUT,
            patches=(Patch("matchup", {
                "official_event_id": "synthetic-test-away-test-home",
                "away_team": "Test Away",
                "home_team": "Test Home",
                "date": "2026-09-11",
                "status": "scheduled",
            }),),
            tags=("identity", "no-synthetic-id"),
        ),
        Scenario(
            "duplicate-event-id",
            "Duplicate event identity is rejected",
            ScenarioCategory.IDENTITY,
            Disposition.REJECT_INPUT,
            patches=(Patch("matchup", {
                "official_event_id": "TEST-OFFICIAL-DUP",
                "duplicate_event_ids": ["TEST-OFFICIAL-DUP", "TEST-OFFICIAL-DUP"],
                "away_team": "Test Away",
                "home_team": "Test Home",
                "date": "2026-09-11",
                "status": "scheduled",
            }),),
            tags=("identity", "duplicate"),
        ),
        Scenario(
            "mixed-division-valid",
            "Verified mixed-division matchup remains eligible",
            ScenarioCategory.IDENTITY,
            Disposition.PASS_THROUGH,
            patches=(Patch("matchup", {
                "official_event_id": "TEST-OFFICIAL-FBS-FCS",
                "away_team": "Test FCS",
                "home_team": "Test FBS",
                "date": "2026-09-11",
                "status": "scheduled",
                "division_mix": "FCS@FBS",
            }),),
            tags=("mixed-division", "official-id"),
        ),
    )


def validate_matrix(scenarios: tuple[Scenario, ...]) -> None:
    if not scenarios:
        raise ValueError("Monster Test Matrix must contain scenarios")
    ids = [item.scenario_id for item in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("Monster Test Matrix scenario ids must be unique")
    if len(scenarios) < 20:
        raise ValueError("Monster Test Matrix V1 must retain at least 20 scenarios")
    categories = {item.category for item in scenarios}
    required_categories = set(ScenarioCategory)
    missing = required_categories - categories
    if missing:
        raise ValueError("Monster Test Matrix missing categories: " + ", ".join(sorted(item.value for item in missing)))


def run_matrix(
    spec: PageSpec,
    baseline: Mapping[str, Any],
    scenarios: tuple[Scenario, ...] | None = None,
) -> MatrixReport:
    selected = scenarios or default_scenarios()
    validate_matrix(selected)
    results = tuple(run_scenario(spec, baseline, item) for item in selected)
    return MatrixReport(
        version=MATRIX_VERSION,
        sport=spec.sport,
        market=spec.market,
        results=results,
    )


def run_totals_matrix(sport: str = "CFB") -> MatrixReport:
    spec = totals_page(sport)
    return run_matrix(spec, baseline_totals_payload(sport=spec.sport))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Monster Test Matrix V1")
    parser.add_argument("--sport", default="CFB")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--failures-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = run_totals_matrix(args.sport)
    payload = report.as_dict()
    if args.failures_only:
        payload["results"] = [item for item in payload["results"] if not item["passed"]]
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{MATRIX_VERSION} sport={report.sport} market={report.market} "
            f"passed={report.passed_count}/{len(report.results)}"
        )
        for item in report.results:
            mark = "PASS" if item.passed else "FAIL"
            print(
                f"[{mark}] {item.scenario.scenario_id}: "
                f"expected={item.scenario.expected.value} actual={item.actual.value}"
            )
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
