"""Verified route snapshot cache for Universal Runtime V5."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Callable, Mapping, MutableMapping

from universal_runtime_v5_scope import RenderScope, commit_if_current
from universal_runtime_v5_state import RuntimeRoute, RuntimeState

SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SnapshotKey:
    sport_id: str
    market_id: str
    params_fingerprint: str


@dataclass(frozen=True)
class VerifiedSnapshot:
    key: SnapshotKey
    payload: object
    verified_at_epoch_ms: int
    ttl_ms: int
    schema_version: int
    source_version: str


def snapshot_key(route: RuntimeRoute) -> SnapshotKey:
    encoded = json.dumps(
        {str(k): str(v) for k, v in sorted(dict(route.params).items())},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return SnapshotKey(route.sport_id, route.market_id, sha256(encoded).hexdigest())


def _cache_key(key: SnapshotKey) -> str:
    return f"{key.sport_id}:{key.market_id}:{key.params_fingerprint}"


def snapshot_is_compatible(
    snapshot: VerifiedSnapshot,
    now_epoch_ms: int,
    expected_source_version: str,
) -> bool:
    return (
        int(snapshot.schema_version) == SNAPSHOT_SCHEMA_VERSION
        and str(snapshot.source_version) == str(expected_source_version)
        and int(snapshot.verified_at_epoch_ms) >= 0
        and int(snapshot.ttl_ms) >= 0
        and int(now_epoch_ms) >= 0
    )


def snapshot_is_fresh(snapshot: VerifiedSnapshot, now_epoch_ms: int) -> bool:
    age = max(0, int(now_epoch_ms) - int(snapshot.verified_at_epoch_ms))
    return age <= int(snapshot.ttl_ms)


def put_snapshot(cache: MutableMapping[str, object], snapshot: VerifiedSnapshot) -> None:
    cache[_cache_key(snapshot.key)] = snapshot


def get_snapshot(
    cache: Mapping[str, object],
    key: SnapshotKey,
    *,
    now_epoch_ms: int,
    expected_source_version: str,
    allow_stale: bool = False,
) -> VerifiedSnapshot | None:
    value = cache.get(_cache_key(key))
    if not isinstance(value, VerifiedSnapshot):
        return None
    if value.key != key:
        return None
    if not snapshot_is_compatible(value, now_epoch_ms, expected_source_version):
        return None
    if not allow_stale and not snapshot_is_fresh(value, now_epoch_ms):
        return None
    return value


def accept_refresh(
    scope: RenderScope,
    runtime: RuntimeState,
    cache: MutableMapping[str, object],
    snapshot: VerifiedSnapshot,
    visible_commit: Callable[[VerifiedSnapshot], None],
) -> bool:
    put_snapshot(cache, snapshot)
    committed = commit_if_current(scope, runtime, lambda: visible_commit(snapshot))
    # visible_commit commonly returns None, so use the gate predicate via generation/status.
    if committed is not None:
        return True
    from universal_runtime_v5_scope import can_commit

    if can_commit(scope, runtime):
        # The callback was executed and legitimately returned None.
        return True
    return False


__all__ = [
    "SNAPSHOT_SCHEMA_VERSION",
    "SnapshotKey",
    "VerifiedSnapshot",
    "accept_refresh",
    "get_snapshot",
    "put_snapshot",
    "snapshot_is_compatible",
    "snapshot_is_fresh",
    "snapshot_key",
]
