from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FreezeWrite:
    token: str
    merged_sha: str
    revision: int
    state_hash: str
    receipt_digest: str


@dataclass(frozen=True)
class FreezeReadback:
    token: str
    merged_sha: str
    revision: int
    state_hash: str
    receipt_digest: str


def can_claim_green_frozen(write: FreezeWrite, readback: FreezeReadback | None) -> bool:
    if readback is None:
        return False
    return (
        write.token == readback.token
        and write.merged_sha == readback.merged_sha
        and write.revision == readback.revision
        and write.state_hash == readback.state_hash
        and write.receipt_digest == readback.receipt_digest
        and bool(write.token)
        and len(write.merged_sha) == 40
        and len(write.state_hash) == 64
        and len(write.receipt_digest) == 64
    )
