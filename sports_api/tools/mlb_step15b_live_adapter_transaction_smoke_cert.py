"""Offline certification entry point for MLB Step 15B frozen live-smoke evidence."""
from __future__ import annotations

import json
import os

from sports_api import mlb_step15b_live_adapter_transaction_smoke_v1 as step15b


def main() -> int:
    env = dict(os.environ)
    env[step15b.STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV] = "true"
    manifest = step15b.live_adapter_transaction_smoke_manifest(env=env)
    evidence = step15b.load_live_smoke_evidence()

    assert evidence["cleanup"]["checkpoint_history_rows_after_cleanup"] == 0
    assert evidence["cleanup"]["checkpoint_heads_rows_after_cleanup"] == 0
    assert evidence["cleanup"]["lease_rows_after_cleanup"] == 0
    assert manifest["execution_boundary"]["production_activation"] == 0
    assert manifest["execution_boundary"]["runtime_cycle_executed"] is False
    assert manifest["execution_boundary"]["provider_calls"] == 0
    assert manifest["execution_boundary"]["sportsbook_calls"] == 0
    assert manifest["phase_boundary"]["step15c_final_live_persistence_freeze_required"] is True

    print(json.dumps(manifest, sort_keys=True))
    print(step15b.FINAL_CERTIFICATION_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
