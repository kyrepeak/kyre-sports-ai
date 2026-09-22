"""Step 6Q durable-storage abstraction for the Kyre-owned WNBA market path.

Phase 6A-6P remains historically frozen. Step 6Q adds a storage contract that
preserves the existing filesystem behavior while reserving a fail-closed slot
for the Supabase implementation in Step 6R. This module performs no sportsbook
collection, no scheduler work, and no paid-service provisioning.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Protocol, runtime_checkable

from sports_api.collectors.wnba_kyre_market_feed import resolve_kyre_market_feed_path

MODEL_SOURCE = "Kyre Sports API WNBA Step 6Q durable storage abstraction"
MODEL_VERSION = "wnba_step_6q_durable_storage_v1"
SCHEMA_VERSION = MODEL_VERSION

STORAGE_BACKEND_ENV = "WNBA_KYRE_DURABLE_STORAGE_BACKEND"
FILESYSTEM_BACKEND = "filesystem"
SUPABASE_BACKEND = "supabase"
SUPPORTED_BACKEND_NAMES = {FILESYSTEM_BACKEND, SUPABASE_BACKEND}

FEED_OBJECT_KEY = "wnba_market_feed.json"
CANARY_MARKER_OBJECT_KEY = ".wnba-step6j-canary-state.json"
CANARY_LOCK_OBJECT_KEY = ".wnba-step6j-canary.lock"
MAX_OBJECT_BYTES = 5_000_000
_KEY_RE = re.compile(r"^[A-Za-z0-9._-]{1,240}$")


class WNBADurableStorageError(RuntimeError):
    pass


class WNBADurableStorageModelInputError(WNBADurableStorageError):
    pass


class WNBADurableStorageNotReadyError(WNBADurableStorageError):
    pass


@dataclass(frozen=True)
class DurableObjectMetadata:
    backend_id: str
    object_key: str
    size_bytes: int
    content_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "object_key": self.object_key,
            "size_bytes": self.size_bytes,
            "content_sha256": self.content_sha256,
        }


@runtime_checkable
class WNBADurableStorageBackend(Protocol):
    """Minimal byte-level contract required by the feed and Step 6J canary."""

    backend_id: str

    def exists(self, object_key: str) -> bool: ...

    def read_bytes(self, object_key: str, *, max_bytes: int = MAX_OBJECT_BYTES) -> bytes: ...

    def write_bytes_atomic(self, object_key: str, payload: bytes) -> DurableObjectMetadata: ...

    def delete(self, object_key: str) -> bool: ...

    def size_bytes(self, object_key: str) -> int | None: ...

    def sha256(self, object_key: str) -> str | None: ...

    def describe(self) -> dict[str, Any]: ...

    def exclusive_lock(self, lock_key: str) -> Iterator[None]: ...


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _object_key(value: Any) -> str:
    key = _clean(value)
    if not key or not _KEY_RE.fullmatch(key) or key in {".", ".."}:
        raise WNBADurableStorageModelInputError(
            "Durable-storage object keys must be single safe filenames with no path traversal."
        )
    return key


def resolve_storage_backend_name(env: Mapping[str, str] | None = None) -> str:
    environment = _environment(env)
    raw = (_clean(environment.get(STORAGE_BACKEND_ENV)) or FILESYSTEM_BACKEND).casefold()
    if raw not in SUPPORTED_BACKEND_NAMES:
        raise WNBADurableStorageModelInputError(
            f"{STORAGE_BACKEND_ENV} must be one of: {', '.join(sorted(SUPPORTED_BACKEND_NAMES))}."
        )
    return raw


class FilesystemDurableStorage:
    """Atomic byte-object store rooted beside the existing Kyre feed file."""

    backend_id = FILESYSTEM_BACKEND

    def __init__(self, root: str | os.PathLike[str]):
        resolved = Path(str(root)).expanduser()
        if not resolved.is_absolute():
            raise WNBADurableStorageModelInputError("Filesystem durable-storage root must be absolute.")
        self.root = resolved

    def _path(self, object_key: str) -> Path:
        return self.root / _object_key(object_key)

    def exists(self, object_key: str) -> bool:
        return self._path(object_key).is_file()

    def read_bytes(self, object_key: str, *, max_bytes: int = MAX_OBJECT_BYTES) -> bytes:
        if int(max_bytes) <= 0:
            raise WNBADurableStorageModelInputError("max_bytes must be positive.")
        path = self._path(object_key)
        try:
            stat = path.stat()
        except FileNotFoundError as exc:
            raise WNBADurableStorageNotReadyError(f"Durable object {object_key!r} does not exist.") from exc
        except OSError as exc:
            raise WNBADurableStorageError(f"Durable object {object_key!r} cannot be inspected.") from exc
        if stat.st_size > int(max_bytes):
            raise WNBADurableStorageModelInputError(
                f"Durable object {object_key!r} exceeds the {int(max_bytes)} byte read limit."
            )
        try:
            return path.read_bytes()
        except OSError as exc:
            raise WNBADurableStorageError(f"Durable object {object_key!r} cannot be read.") from exc

    def write_bytes_atomic(self, object_key: str, payload: bytes) -> DurableObjectMetadata:
        key = _object_key(object_key)
        if not isinstance(payload, bytes):
            raise WNBADurableStorageModelInputError("Durable-storage payload must be bytes.")
        if len(payload) > MAX_OBJECT_BYTES:
            raise WNBADurableStorageModelInputError(
                f"Durable-storage payload exceeds {MAX_OBJECT_BYTES} bytes."
            )
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temporary_name, 0o600)
            except OSError:
                pass
            os.replace(temporary_name, target)
        finally:
            try:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
            except OSError:
                pass
        return DurableObjectMetadata(
            backend_id=self.backend_id,
            object_key=key,
            size_bytes=len(payload),
            content_sha256=_sha256(payload),
        )

    def delete(self, object_key: str) -> bool:
        path = self._path(object_key)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise WNBADurableStorageError(f"Durable object {object_key!r} cannot be deleted.") from exc

    def size_bytes(self, object_key: str) -> int | None:
        path = self._path(object_key)
        try:
            return int(path.stat().st_size)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise WNBADurableStorageError(f"Durable object {object_key!r} cannot be inspected.") from exc

    def sha256(self, object_key: str) -> str | None:
        if not self.exists(object_key):
            return None
        return _sha256(self.read_bytes(object_key))

    @contextmanager
    def exclusive_lock(self, lock_key: str) -> Iterator[None]:
        lock_path = self._path(lock_key)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with lock_path.open("a+b") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError as exc:
            raise WNBADurableStorageError(f"Durable lock {lock_key!r} could not be acquired.") from exc

    def describe(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "implemented": True,
            "root": str(self.root),
            "network_required": False,
            "secret_required": False,
            "atomic_write_supported": True,
            "exclusive_lock_supported": True,
            "durability_note": "Restart durability depends on the filesystem mount supplied by the host.",
        }


def build_durable_storage(
    *,
    env: Mapping[str, str] | None = None,
    feed_path: str | os.PathLike[str] | None = None,
) -> WNBADurableStorageBackend:
    """Build the selected backend without silently falling back across backends."""
    backend_name = resolve_storage_backend_name(env)
    if backend_name == SUPABASE_BACKEND:
        raise WNBADurableStorageNotReadyError(
            "Supabase durable storage is reserved by Step 6Q but is not implemented until Step 6R."
        )
    target = resolve_kyre_market_feed_path(path=feed_path, env=env)
    return FilesystemDurableStorage(target.parent)


def get_step6q_durable_storage_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Read-only, network-free report of the selected Step 6Q storage contract."""
    environment = _environment(env)
    try:
        backend_name = resolve_storage_backend_name(environment)
        configuration_error = None
    except WNBADurableStorageModelInputError as exc:
        backend_name = _clean(environment.get(STORAGE_BACKEND_ENV))
        configuration_error = str(exc)

    backend = None
    if configuration_error is None:
        try:
            backend = build_durable_storage(env=environment)
        except WNBADurableStorageNotReadyError as exc:
            configuration_error = str(exc)

    description = backend.describe() if backend is not None else {
        "backend_id": backend_name,
        "implemented": False,
        "network_required": backend_name == SUPABASE_BACKEND,
        "secret_required": backend_name == SUPABASE_BACKEND,
    }
    feed_exists = bool(backend and backend.exists(FEED_OBJECT_KEY))
    feed_size = backend.size_bytes(FEED_OBJECT_KEY) if backend and feed_exists else None
    feed_sha = backend.sha256(FEED_OBJECT_KEY) if backend and feed_exists else None

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6q_durable_storage_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "selected_backend": backend_name,
        "backend_implemented": bool(backend),
        "configuration_error": configuration_error,
        "feed_exists": feed_exists,
        "feed_size_bytes": feed_size,
        "feed_content_sha256": feed_sha,
        "backend": description,
        "contract": {
            "byte_exact_read": True,
            "atomic_write": True,
            "delete": True,
            "content_sha256": True,
            "exclusive_lock": True,
            "prewrite_backup_compatible": True,
            "step6j_marker_compatible": True,
            "supabase_backend_reserved_for_step6r": True,
            "silent_backend_fallback_allowed": False,
        },
        "safety": {
            "network_used_by_status": False,
            "storage_write_performed_by_status": False,
            "draftkings_called": False,
            "render_provisioned": False,
            "scheduler_started": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
        },
    }
