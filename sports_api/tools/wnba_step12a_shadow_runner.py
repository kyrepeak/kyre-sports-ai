"""STDIN/STDOUT execution surface for WNBA Step 12A.

Usage:
    cat request.json | python -m sports_api.tools.wnba_step12a_shadow_runner

The runner writes no runtime state or output files. JSON goes in through stdin and the
versioned response goes to stdout. Repeated execution requires an external caller.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from sports_api import wnba_step12_shadow_runner as step12a


def _error_payload(exc: Exception) -> dict[str, Any]:
    return {
        "data_type": "wnba_step12a_shadow_runner_error",
        "schema_version": step12a.SCHEMA_VERSION,
        "error_type": type(exc).__name__,
        "error_message": " ".join(str(exc).split())[:500],
        "guardrails": {
            "scheduler_started": False,
            "state_persisted": False,
            "supabase_mutated": False,
            "production_runtime_enabled": False,
            "wager_action_performed": False,
        },
    }


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print(
            json.dumps(
                _error_payload(
                    step12a.WNBAStep12ShadowRunnerInputError(
                        "Step 12A requires one JSON request on stdin."
                    )
                ),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    try:
        request = json.loads(raw)
        response = step12a.run_step12a_shadow_job(request)
    except (
        json.JSONDecodeError,
        step12a.WNBAStep12ShadowRunnerDisabledError,
        step12a.WNBAStep12ShadowRunnerInputError,
        step12a.WNBAStep12ShadowRunnerIntegrityError,
    ) as exc:
        print(json.dumps(_error_payload(exc), sort_keys=True), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps(_error_payload(exc), sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(response, sort_keys=True, separators=(",", ":"), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
