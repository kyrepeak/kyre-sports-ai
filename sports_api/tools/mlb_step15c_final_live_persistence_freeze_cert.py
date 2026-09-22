"""Command-line certification for MLB Step 15C final live persistence freeze."""
from __future__ import annotations

import json
import os

from sports_api import mlb_step15_final_live_persistence_release_freeze_v1 as step15c


def main() -> int:
    manifest = step15c.final_live_persistence_release_manifest(env=os.environ)
    required = {
        "marker": manifest.get("final_certification_marker")
        == step15c.FINAL_CERTIFICATION_MARKER,
        "step15_frozen": manifest.get("phase_boundary", {}).get(
            "step15_complete_and_frozen"
        )
        is True,
        "tables_clean": manifest.get("phase_boundary", {}).get(
            "live_tables_clean_at_final_freeze"
        )
        is True,
        "production_off": manifest.get("activation_contract", {}).get(
            "production_runtime_enabled"
        )
        is False,
        "scheduler_off": manifest.get("activation_contract", {}).get(
            "production_scheduler_started"
        )
        is False,
        "provider_calls_zero": manifest.get("activation_contract", {}).get(
            "provider_calls"
        )
        == 0,
        "sportsbook_calls_zero": manifest.get("activation_contract", {}).get(
            "sportsbook_calls"
        )
        == 0,
    }
    failed = [name for name, ok in required.items() if not ok]
    if failed:
        raise RuntimeError("Step 15C certification failed: " + ", ".join(failed))
    print(json.dumps(manifest, sort_keys=True))
    print(step15c.FINAL_CERTIFICATION_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
