"""Stable final result aggregator for DevSystem targeted CI."""
from __future__ import annotations

import argparse
import json
import os


class FinalGateFailure(RuntimeError):
    pass


def evaluate(needs: dict) -> dict:
    failures: list[str] = []
    allowed = {"success", "skipped"}

    for name, payload in sorted(needs.items()):
        result = str((payload or {}).get("result") or "")
        if result not in allowed:
            failures.append(f"{name}={result or 'unknown'}")

    if failures:
        raise FinalGateFailure(
            "DevSystem lanes not green: " + " | ".join(failures)
        )

    return {
        "status": "GREEN",
        "jobs_checked": len(needs),
        "results": {
            name: (payload or {}).get("result")
            for name, payload in sorted(needs.items())
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--needs-json")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    raw = args.needs_json or os.environ.get("DEVSYSTEM_NEEDS_JSON") or "{}"
    result = evaluate(json.loads(raw))
    print("DEVSYSTEM_FINAL_GATE_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
