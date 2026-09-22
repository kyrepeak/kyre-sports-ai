"""Step 6R Supabase durable-storage backend for the Kyre-owned WNBA market path.

Step 6Q remains historically frozen. Step 6R implements the previously reserved
Supabase slot without changing the Step 6Q filesystem backend. The backend uses
Supabase's server-side Data API, stores byte-exact payloads as base64 with
client-verified SHA-256 metadata, performs row-atomic upserts, and maps the
Step 6Q exclusive-lock contract to a database lease acquired/released by RPC.

This module does not provision Supabase, create schema, call sportsbooks, start
a scheduler, run Monte Carlo, or place wagers. Schema installation is an
explicit later operator action using sports_api/sql/wnba_step6r_supabase.sql.
"""
from __future__ import annotations

import base64
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlsplit
import uuid

import httpx

from sports_api.collectors.wnba_kyre_market_feed import resolve_kyre_market_feed_path
from sports_api.wnba_step6q_durable_storage import (
    FILESYSTEM_BACKEND,
    MAX_OBJECT_BYTES,
    SUPABASE_BACKEND,
    DurableObjectMetadata,
    FilesystemDurableStorage,
    WNBADurableStorageBackend,
    WNBADurableStorageError,
    WNBADurableStorageModelInputError,
    WNBADurableStorageNotReadyError,
    _object_key,
    resolve_storage_backend_name,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6R Supabase durable storage backend"
MODEL_VERSION = "wnba_step_6r_supabase_storage_v1"
SCHEMA_VERSION = MODEL_VERSION

SUPABASE_URL_ENV = "WNBA_KYRE_SUPABASE_URL"
SUPABASE_SECRET_KEY_ENV = "WNBA_KYRE_SUPABASE_SECRET_KEY"
SUPABASE_OBJECT_TABLE_ENV = "WNBA_KYRE_SUPABASE_OBJECT_TABLE"
SUPABASE_LOCK_ACQUIRE_RPC_ENV = "WNBA_KYRE_SUPABASE_LOCK_ACQUIRE_RPC"
SUPABASE_LOCK_RELEASE_RPC_ENV = "WNBA_KYRE_SUPABASE_LOCK_RELEASE_RPC"
SUPABASE_TIMEOUT_SECONDS_ENV = "WNBA_KYRE_SUPABASE_TIMEOUT_SECONDS"
SUPABASE_LOCK_LEASE_SECONDS_ENV = "WNBA_KYRE_SUPABASE_LOCK_LEASE_SECONDS"

DEFAULT_OBJECT_TABLE = "wnba_durable_objects"
DEFAULT_LOCK_ACQUIRE_RPC = "wnba_durable_lock_acquire"
DEFAULT_LOCK_RELEASE_RPC = "wnba_durable_lock_release"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_LOCK_LEASE_SECONDS = 300
MIN_LOCK_LEASE_SECONDS = 30
MAX_LOCK_LEASE_SECONDS = 900
SCHEMA_FILE = "sports_api/sql/wnba_step6r_supabase.sql"
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _identifier(value: Any, *, name: str, default: str) -> str:
    text = (_clean(value) or default).casefold()
    if not _IDENTIFIER_RE.fullmatch(text):
        raise WNBADurableStorageModelInputError(f"{name} must be a safe lowercase PostgreSQL identifier.")
    return text


def _positive_float(value: Any, *, name: str, default: float, maximum: float) -> float:
    text = _clean(value)
    if text is None:
        return default
    try:
        parsed = float(text)
    except (TypeError, ValueError) as exc:
        raise WNBADurableStorageModelInputError(f"{name} must be numeric.") from exc
    if parsed <= 0 or parsed > maximum:
        raise WNBADurableStorageModelInputError(f"{name} must be > 0 and <= {maximum:g}.")
    return parsed


def _lease_seconds(value: Any) -> int:
    text = _clean(value)
    if text is None:
        return DEFAULT_LOCK_LEASE_SECONDS
    try:
        parsed = int(text)
    except (TypeError, ValueError) as exc:
        raise WNBADurableStorageModelInputError(f"{SUPABASE_LOCK_LEASE_SECONDS_ENV} must be an integer.") from exc
    if parsed < MIN_LOCK_LEASE_SECONDS or parsed > MAX_LOCK_LEASE_SECONDS:
        raise WNBADurableStorageModelInputError(
            f"{SUPABASE_LOCK_LEASE_SECONDS_ENV} must be between {MIN_LOCK_LEASE_SECONDS} and {MAX_LOCK_LEASE_SECONDS}."
        )
    return parsed


def _supabase_base_url(value: Any) -> str:
    text = _clean(value)
    if text is None:
        raise WNBADurableStorageNotReadyError(f"{SUPABASE_URL_ENV} is required for the Supabase backend.")
    parsed = urlsplit(text)
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise WNBADurableStorageModelInputError(
            f"{SUPABASE_URL_ENV} must be an HTTPS project origin with no credentials, query, fragment, or path."
        )
    return f"https://{parsed.netloc.rstrip('/')}"


def _secret_key(value: Any) -> str:
    text = _clean(value)
    if text is None:
        raise WNBADurableStorageNotReadyError(
            f"{SUPABASE_SECRET_KEY_ENV} is required server-side and must never be exposed to clients."
        )
    if len(text) < 20:
        raise WNBADurableStorageModelInputError(f"{SUPABASE_SECRET_KEY_ENV} is not a plausible Supabase secret key.")
    return text


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _decode_json(response: httpx.Response, *, operation: str) -> Any:
    try:
        return response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise WNBADurableStorageError(f"Supabase returned invalid JSON during {operation}.") from exc


class SupabaseDurableStorage:
    """Step 6Q byte-object contract implemented over Supabase PostgREST."""

    backend_id = SUPABASE_BACKEND

    def __init__(
        self,
        *,
        base_url: str,
        secret_key: str,
        object_table: str = DEFAULT_OBJECT_TABLE,
        lock_acquire_rpc: str = DEFAULT_LOCK_ACQUIRE_RPC,
        lock_release_rpc: str = DEFAULT_LOCK_RELEASE_RPC,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        lock_lease_seconds: int = DEFAULT_LOCK_LEASE_SECONDS,
        client: httpx.Client | None = None,
    ):
        self.base_url = _supabase_base_url(base_url)
        self.secret_key = _secret_key(secret_key)
        self.object_table = _identifier(object_table, name=SUPABASE_OBJECT_TABLE_ENV, default=DEFAULT_OBJECT_TABLE)
        self.lock_acquire_rpc = _identifier(
            lock_acquire_rpc,
            name=SUPABASE_LOCK_ACQUIRE_RPC_ENV,
            default=DEFAULT_LOCK_ACQUIRE_RPC,
        )
        self.lock_release_rpc = _identifier(
            lock_release_rpc,
            name=SUPABASE_LOCK_RELEASE_RPC_ENV,
            default=DEFAULT_LOCK_RELEASE_RPC,
        )
        self.timeout_seconds = _positive_float(
            timeout_seconds,
            name=SUPABASE_TIMEOUT_SECONDS_ENV,
            default=DEFAULT_TIMEOUT_SECONDS,
            maximum=60.0,
        )
        self.lock_lease_seconds = _lease_seconds(lock_lease_seconds)
        self._client = client or httpx.Client(timeout=self.timeout_seconds)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> "SupabaseDurableStorage":
        environment = _environment(env)
        return cls(
            base_url=_supabase_base_url(environment.get(SUPABASE_URL_ENV)),
            secret_key=_secret_key(environment.get(SUPABASE_SECRET_KEY_ENV)),
            object_table=_identifier(
                environment.get(SUPABASE_OBJECT_TABLE_ENV),
                name=SUPABASE_OBJECT_TABLE_ENV,
                default=DEFAULT_OBJECT_TABLE,
            ),
            lock_acquire_rpc=_identifier(
                environment.get(SUPABASE_LOCK_ACQUIRE_RPC_ENV),
                name=SUPABASE_LOCK_ACQUIRE_RPC_ENV,
                default=DEFAULT_LOCK_ACQUIRE_RPC,
            ),
            lock_release_rpc=_identifier(
                environment.get(SUPABASE_LOCK_RELEASE_RPC_ENV),
                name=SUPABASE_LOCK_RELEASE_RPC_ENV,
                default=DEFAULT_LOCK_RELEASE_RPC,
            ),
            timeout_seconds=_positive_float(
                environment.get(SUPABASE_TIMEOUT_SECONDS_ENV),
                name=SUPABASE_TIMEOUT_SECONDS_ENV,
                default=DEFAULT_TIMEOUT_SECONDS,
                maximum=60.0,
            ),
            lock_lease_seconds=_lease_seconds(environment.get(SUPABASE_LOCK_LEASE_SECONDS_ENV)),
            client=client,
        )

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.secret_key,
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "kyre-sports-api-step6r/1",
        }
        # Legacy service_role keys are JWTs and historically use Authorization.
        # New sb_secret_* keys are not JWTs and are intentionally sent only via
        # the apikey header, matching Supabase's current server-side key model.
        if self.secret_key.count(".") == 2:
            headers["authorization"] = f"Bearer {self.secret_key}"
        if prefer:
            headers["prefer"] = prefer
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json_body: Any = None,
        prefer: str | None = None,
        operation: str,
    ) -> httpx.Response:
        url = f"{self.base_url}/rest/v1/{path}"
        try:
            response = self._client.request(
                method,
                url,
                params=dict(params or {}),
                json=json_body,
                headers=self._headers(prefer=prefer),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise WNBADurableStorageError(f"Supabase network failure during {operation}.") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise WNBADurableStorageError(
                f"Supabase durable-storage request failed during {operation} with HTTP {response.status_code}."
            )
        return response

    def _select_one(self, object_key: str, columns: str) -> dict[str, Any] | None:
        key = _object_key(object_key)
        response = self._request(
            "GET",
            self.object_table,
            params={"select": columns, "object_key": f"eq.{key}", "limit": "1"},
            operation=f"select {key}",
        )
        data = _decode_json(response, operation=f"select {key}")
        if not isinstance(data, list):
            raise WNBADurableStorageError("Supabase object query returned an unexpected response shape.")
        if not data:
            return None
        row = data[0]
        if not isinstance(row, dict):
            raise WNBADurableStorageError("Supabase object query returned an invalid row.")
        return row

    def exists(self, object_key: str) -> bool:
        return self._select_one(object_key, "object_key") is not None

    def read_bytes(self, object_key: str, *, max_bytes: int = MAX_OBJECT_BYTES) -> bytes:
        if int(max_bytes) <= 0:
            raise WNBADurableStorageModelInputError("max_bytes must be positive.")
        key = _object_key(object_key)
        row = self._select_one(key, "payload_base64,size_bytes,content_sha256")
        if row is None:
            raise WNBADurableStorageNotReadyError(f"Durable object {key!r} does not exist.")
        try:
            size = int(row["size_bytes"])
            encoded = str(row["payload_base64"])
            expected_sha = str(row["content_sha256"]).casefold()
        except (KeyError, TypeError, ValueError) as exc:
            raise WNBADurableStorageError(f"Supabase durable object {key!r} has invalid metadata.") from exc
        if size < 0 or size > MAX_OBJECT_BYTES or size > int(max_bytes):
            raise WNBADurableStorageModelInputError(
                f"Durable object {key!r} exceeds the {int(max_bytes)} byte read limit."
            )
        if not _HEX_SHA256_RE.fullmatch(expected_sha):
            raise WNBADurableStorageError(f"Supabase durable object {key!r} has an invalid SHA-256 value.")
        try:
            payload = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (ValueError, UnicodeError) as exc:
            raise WNBADurableStorageError(f"Supabase durable object {key!r} contains invalid base64.") from exc
        if len(payload) != size or _sha256(payload) != expected_sha:
            raise WNBADurableStorageError(f"Supabase durable object {key!r} failed byte-integrity verification.")
        return payload

    def write_bytes_atomic(self, object_key: str, payload: bytes) -> DurableObjectMetadata:
        key = _object_key(object_key)
        if not isinstance(payload, bytes):
            raise WNBADurableStorageModelInputError("Durable-storage payload must be bytes.")
        if len(payload) > MAX_OBJECT_BYTES:
            raise WNBADurableStorageModelInputError(
                f"Durable-storage payload exceeds {MAX_OBJECT_BYTES} bytes."
            )
        content_sha = _sha256(payload)
        body = {
            "object_key": key,
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "size_bytes": len(payload),
            "content_sha256": content_sha,
            "updated_at": _utc_now_iso(),
        }
        response = self._request(
            "POST",
            self.object_table,
            params={"on_conflict": "object_key"},
            json_body=body,
            prefer="resolution=merge-duplicates,return=representation",
            operation=f"atomic upsert {key}",
        )
        data = _decode_json(response, operation=f"atomic upsert {key}")
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise WNBADurableStorageError("Supabase atomic upsert did not return exactly one object row.")
        row = data[0]
        if (
            str(row.get("object_key")) != key
            or int(row.get("size_bytes", -1)) != len(payload)
            or str(row.get("content_sha256", "")).casefold() != content_sha
        ):
            raise WNBADurableStorageError("Supabase atomic upsert acknowledgement failed integrity verification.")
        return DurableObjectMetadata(
            backend_id=self.backend_id,
            object_key=key,
            size_bytes=len(payload),
            content_sha256=content_sha,
        )

    def delete(self, object_key: str) -> bool:
        key = _object_key(object_key)
        response = self._request(
            "DELETE",
            self.object_table,
            params={"object_key": f"eq.{key}", "select": "object_key"},
            prefer="return=representation",
            operation=f"delete {key}",
        )
        data = _decode_json(response, operation=f"delete {key}")
        if not isinstance(data, list):
            raise WNBADurableStorageError("Supabase delete returned an unexpected response shape.")
        return bool(data)

    def size_bytes(self, object_key: str) -> int | None:
        key = _object_key(object_key)
        row = self._select_one(key, "size_bytes")
        if row is None:
            return None
        try:
            size = int(row["size_bytes"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WNBADurableStorageError(f"Supabase durable object {key!r} has invalid size metadata.") from exc
        if size < 0 or size > MAX_OBJECT_BYTES:
            raise WNBADurableStorageError(f"Supabase durable object {key!r} has out-of-range size metadata.")
        return size

    def sha256(self, object_key: str) -> str | None:
        key = _object_key(object_key)
        row = self._select_one(key, "content_sha256")
        if row is None:
            return None
        value = str(row.get("content_sha256", "")).casefold()
        if not _HEX_SHA256_RE.fullmatch(value):
            raise WNBADurableStorageError(f"Supabase durable object {key!r} has invalid SHA-256 metadata.")
        return value

    def _rpc_bool(self, rpc_name: str, body: dict[str, Any], *, operation: str) -> bool:
        response = self._request("POST", f"rpc/{rpc_name}", json_body=body, operation=operation)
        data = _decode_json(response, operation=operation)
        if isinstance(data, bool):
            return data
        if isinstance(data, list) and len(data) == 1:
            if isinstance(data[0], bool):
                return data[0]
            if isinstance(data[0], dict) and len(data[0]) == 1:
                value = next(iter(data[0].values()))
                if isinstance(value, bool):
                    return value
        if isinstance(data, dict) and len(data) == 1:
            value = next(iter(data.values()))
            if isinstance(value, bool):
                return value
        raise WNBADurableStorageError(f"Supabase RPC returned an unexpected response during {operation}.")

    @contextmanager
    def exclusive_lock(self, lock_key: str) -> Iterator[None]:
        key = _object_key(lock_key)
        owner_token = str(uuid.uuid4())
        acquired = self._rpc_bool(
            self.lock_acquire_rpc,
            {
                "p_lock_key": key,
                "p_owner_token": owner_token,
                "p_lease_seconds": self.lock_lease_seconds,
            },
            operation=f"acquire lock {key}",
        )
        if not acquired:
            raise WNBADurableStorageNotReadyError(f"Durable lock {key!r} is already held by another owner.")
        try:
            yield
        finally:
            active_exception = sys.exc_info()[0] is not None
            try:
                released = self._rpc_bool(
                    self.lock_release_rpc,
                    {"p_lock_key": key, "p_owner_token": owner_token},
                    operation=f"release lock {key}",
                )
                if not released and not active_exception:
                    raise WNBADurableStorageError(f"Durable lock {key!r} could not be released by its owner.")
            except WNBADurableStorageError:
                if not active_exception:
                    raise
                # Preserve the caller's primary failure. The DB lease expires
                # automatically, preventing an indefinite stale lock.

    def describe(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "implemented": True,
            "project_host": urlsplit(self.base_url).hostname,
            "object_table": self.object_table,
            "lock_acquire_rpc": self.lock_acquire_rpc,
            "lock_release_rpc": self.lock_release_rpc,
            "request_timeout_seconds": self.timeout_seconds,
            "lock_lease_seconds": self.lock_lease_seconds,
            "network_required": True,
            "secret_required": True,
            "secret_configured": True,
            "secret_value_exposed": False,
            "atomic_write_supported": True,
            "exclusive_lock_supported": True,
            "integrity_verification": "base64 byte round-trip + size + sha256",
            "durability_note": "Durability is provided by the configured Supabase Postgres project.",
        }


def build_step6r_durable_storage(
    *,
    env: Mapping[str, str] | None = None,
    feed_path: str | os.PathLike[str] | None = None,
    client: httpx.Client | None = None,
) -> WNBADurableStorageBackend:
    """Build filesystem or Supabase explicitly; never fall back across backends."""
    backend_name = resolve_storage_backend_name(env)
    if backend_name == SUPABASE_BACKEND:
        return SupabaseDurableStorage.from_env(env, client=client)
    target = resolve_kyre_market_feed_path(path=feed_path, env=env)
    return FilesystemDurableStorage(target.parent)


def get_step6r_supabase_storage_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Network-free configuration/schema readiness report for the Step 6R backend."""
    environment = _environment(env)
    selected_backend: str | None = None
    configuration_error: str | None = None
    backend_description: dict[str, Any] | None = None

    try:
        selected_backend = resolve_storage_backend_name(environment)
        if selected_backend == SUPABASE_BACKEND:
            backend_description = SupabaseDurableStorage.from_env(environment).describe()
    except (WNBADurableStorageModelInputError, WNBADurableStorageNotReadyError) as exc:
        configuration_error = str(exc)

    supabase_selected = selected_backend == SUPABASE_BACKEND
    configured = bool(supabase_selected and backend_description is not None and configuration_error is None)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6r_supabase_storage_status",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "selected_backend": selected_backend,
        "supabase_selected": supabase_selected,
        "backend_implemented": True,
        "configuration_ready": configured,
        "configuration_error": configuration_error,
        "backend": backend_description,
        "schema_contract": {
            "sql_file": SCHEMA_FILE,
            "object_table": _clean(environment.get(SUPABASE_OBJECT_TABLE_ENV)) or DEFAULT_OBJECT_TABLE,
            "lock_acquire_rpc": _clean(environment.get(SUPABASE_LOCK_ACQUIRE_RPC_ENV)) or DEFAULT_LOCK_ACQUIRE_RPC,
            "lock_release_rpc": _clean(environment.get(SUPABASE_LOCK_RELEASE_RPC_ENV)) or DEFAULT_LOCK_RELEASE_RPC,
            "rls_required": True,
            "anon_access_allowed": False,
            "authenticated_access_allowed": False,
            "server_secret_required": True,
            "schema_installed_by_status": False,
        },
        "handoff": {
            "step6q_filesystem_contract_preserved": True,
            "ready_for_step6s_code_migration": True,
            "live_supabase_canary_attempted": False,
        },
        "safety": {
            "network_used_by_status": False,
            "storage_write_performed_by_status": False,
            "schema_mutation_performed_by_status": False,
            "secret_value_returned": False,
            "draftkings_called": False,
            "render_provisioned": False,
            "scheduler_started": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
        },
    }
