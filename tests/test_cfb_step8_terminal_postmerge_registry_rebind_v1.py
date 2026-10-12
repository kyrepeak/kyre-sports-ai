from __future__ import annotations

from runless_proof_plane.cfb_step8_terminal_postmerge_registry_rebind_v1 import (
    FINAL_FREEZE_TOKEN,
    TERMINAL_RECEIPT_DIGEST,
    validate_closeout_snapshot,
)


def test_closeout_snapshot_requires_terminal_ledger_receipt_and_frozen_token():
    result = validate_closeout_snapshot(
        {"status": "GREEN_PLUS_FROZEN", "green_plus_frozen_claimed": True, "next_legal_action": "NONE_TERMINAL"},
        {"digest": TERMINAL_RECEIPT_DIGEST, "github_actions_fallback": 0},
        {"checkpoint_id": FINAL_FREEZE_TOKEN, "status": "FROZEN"},
    )
    assert result == {"status": "GREEN", "github_actions_fallback": 0}
