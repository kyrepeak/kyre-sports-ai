from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path


BENCHMARK = Path("devsystem/github_speed_benchmark_v1.json")
PRODUCTION_V5 = Path(".github/workflows/devsystem-production-verification-v5.yml")
LEGACY = Path(".github/workflows/devsystem-production-verification.yml")


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_speed_benchmark_primary_metric_recomputes_and_passes():
    payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    metric = payload["primary_metric"]
    old = metric["baseline"]
    new = metric["optimized"]

    old_seconds = (_ts(old["live_verify_started_at"]) - _ts(old["run_created_at"])).total_seconds()
    new_seconds = (_ts(new["live_verify_started_at"]) - _ts(new["run_created_at"])).total_seconds()
    reduction = (1.0 - (new_seconds / old_seconds)) * 100.0
    speedup = old_seconds / new_seconds

    assert abs(old_seconds - float(old["seconds"])) < 0.001
    assert abs(new_seconds - float(new["seconds"])) < 0.001
    assert abs(reduction - float(metric["reduction_percent"])) < 0.001
    assert abs(speedup - float(metric["speedup_multiple"])) < 0.001

    acceptance = metric["acceptance"]
    assert new_seconds <= float(acceptance["maximum_optimized_seconds"])
    assert reduction >= float(acceptance["minimum_reduction_percent"])
    assert acceptance["passed"] is True
    assert payload["status"] == "GREEN"


def test_speed_benchmark_freezes_steps_1_through_4_contracts():
    payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    frozen = payload["frozen_speed_contracts"]
    assert all(frozen.values())

    production = PRODUCTION_V5.read_text(encoding="utf-8")
    legacy = LEGACY.read_text(encoding="utf-8")

    # Step 1: legacy verifier remains manual-only.
    assert "workflow_dispatch:" in legacy
    assert "\n  push:" not in legacy

    # Step 2: browser stack is restored and only built on cache miss.
    assert "Restore shared Browser QA stack" in production
    assert "steps.browser-stack-cache.outputs.cache-hit != 'true'" in production
    assert "playwright install --with-deps chromium" not in production

    # Step 3: cheap preflight remains ahead of the browser cache restore.
    assert production.index("Run dependency-free production preflight") < production.index(
        "Restore shared Browser QA stack"
    )

    # Step 4: broad repo-wide automatic fanout stays removed.
    push_block = production.split("  push:", 1)[1].split("  workflow_dispatch:", 1)[0]
    assert '- "streamlit_*.py"' not in push_block
    assert '- "sports_api/**"' not in push_block
    assert '- "data/**"' not in push_block


def test_secondary_terminal_duration_is_labeled_non_primary():
    payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    observed = payload["observed_terminal_duration"]

    assert observed["baseline_seconds"] == 246.0
    assert observed["optimized_seconds"] == 37.0
    assert observed["observed_reduction_percent"] > 80.0
    assert "not the primary" in observed["note"].lower()
