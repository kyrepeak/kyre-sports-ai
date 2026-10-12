from __future__ import annotations

import pytest

from runless_proof_plane.cfb_step8_terminal_immutable_finalization_v1 import (
    IMMUTABLE_PUBLIC_CHECKPOINT,
    IMMUTABLE_PUBLIC_SOURCE_MAIN_SHA,
    ROUTER_BLOB,
    ROUTER_PATH,
    ImmutableFinalizationFailure,
    verify_immutable_public_authority,
)


def _registry(*, status: str = "FROZEN", router_blob: str = ROUTER_BLOB):
    return {
        "entries": {
            IMMUTABLE_PUBLIC_CHECKPOINT: {
                "status": status,
                "checkpoint_id": IMMUTABLE_PUBLIC_CHECKPOINT,
                "source_main_sha": IMMUTABLE_PUBLIC_SOURCE_MAIN_SHA,
                "artifacts": {ROUTER_PATH: router_blob},
            }
        }
    }


def test_immutable_public_authority_accepts_exact_frozen_checkpoint_and_current_router_blob():
    result = verify_immutable_public_authority(
        _registry(),
        {ROUTER_PATH: ROUTER_BLOB},
    )
    assert result["status"] == "GREEN"
    assert result["proof_mode"] == "IMMUTABLE_FROZEN_PUBLIC_PROOF_REUSE"
    assert result["checkpoint_id"] == IMMUTABLE_PUBLIC_CHECKPOINT
    assert result["router_blob"] == ROUTER_BLOB
    assert result["public_browser_recheck"] is False
    assert result["github_actions_fallback"] == 0


def test_immutable_public_authority_fails_closed_on_current_router_blob_drift():
    with pytest.raises(ImmutableFinalizationFailure, match="CURRENT_ROUTER_BLOB_DRIFT"):
        verify_immutable_public_authority(
            _registry(),
            {ROUTER_PATH: "bad"},
        )


def test_immutable_public_authority_fails_closed_when_checkpoint_not_frozen():
    with pytest.raises(ImmutableFinalizationFailure, match="IMMUTABLE_PUBLIC_CHECKPOINT_NOT_FROZEN"):
        verify_immutable_public_authority(
            _registry(status="THAWED"),
            {ROUTER_PATH: ROUTER_BLOB},
        )
