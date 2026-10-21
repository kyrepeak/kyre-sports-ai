"""Private durable storage for WNBA PRA page model artifacts and refresh leases."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Mapping

import httpx


class WNBAPRASnapshotStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class SnapshotStoreSettings:
    supabase_url: str
    supabase_service_role_key: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SnapshotStoreSettings":
        values = os.environ if env is None else env
        url = str(values.get("SUPABASE_URL") or "").strip().rstrip("/")
        key = str(values.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not url or not key:
            raise WNBAPRASnapshotStoreError("WNBA_PRA_SNAPSHOT_STORE_CONFIG_REQUIRED")
        return cls(url, key)


class WNBAPRASnapshotStore:
    def __init__(self, settings: Any, *, client: Any | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=12.0)

    @classmethod
    def from_env(cls) -> "WNBAPRASnapshotStore":
        return cls(SnapshotStoreSettings.from_env())

    @property
    def _headers(self) -> dict[str, str]:
        key = str(self.settings.supabase_service_role_key)
        headers = {
            "apikey": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if not key.startswith(("sb_secret_", "sb_publishable_")):
            headers["Authorization"] = f"Bearer {key}"
        return headers

    @property
    def _read_headers(self) -> dict[str, str]:
        return {**self._headers, "Accept-Profile": "runless_v2"}

    @property
    def _write_headers(self) -> dict[str, str]:
        return {**self._headers, "Content-Profile": "runless_v2"}

    def _url(self, path: str) -> str:
        return str(self.settings.supabase_url).rstrip("/") + path

    @staticmethod
    def _payload(response: Any) -> Any:
        if int(response.status_code) >= 400:
            raise WNBAPRASnapshotStoreError(f"WNBA_PRA_SNAPSHOT_STORE_HTTP_{response.status_code}")
        try:
            return response.json()
        except Exception as exc:
            raise WNBAPRASnapshotStoreError("WNBA_PRA_SNAPSHOT_STORE_BAD_JSON") from exc

    @staticmethod
    def _single(payload: Any, *, allow_empty: bool = False) -> dict[str, Any] | None:
        if isinstance(payload, list):
            if not payload and allow_empty:
                return None
            if len(payload) != 1:
                raise WNBAPRASnapshotStoreError("WNBA_PRA_SNAPSHOT_STORE_EXPECTED_SINGLE_ROW")
            return dict(payload[0])
        if isinstance(payload, Mapping):
            return dict(payload)
        raise WNBAPRASnapshotStoreError("WNBA_PRA_SNAPSHOT_STORE_BAD_SHAPE")

    def read(self, *, date: str, season: int, schema_version: str) -> dict[str, Any] | None:
        response = self.client.get(
            self._url("/rest/v1/wnba_pra_page_snapshots"),
            headers=self._read_headers,
            params={
                "select": "artifact,content_hash,generated_at",
                "snapshot_date": f"eq.{date}",
                "season": f"eq.{int(season)}",
                "schema_version": f"eq.{schema_version}",
                "limit": "1",
            },
        )
        row = self._single(self._payload(response), allow_empty=True)
        if row is None:
            return None
        artifact = row.get("artifact")
        if not isinstance(artifact, Mapping):
            raise WNBAPRASnapshotStoreError("WNBA_PRA_SNAPSHOT_ARTIFACT_INVALID")
        return dict(artifact)

    def upsert(self, artifact: Mapping[str, Any]) -> dict[str, Any]:
        date = str(artifact.get("date") or "")
        season = int(artifact.get("season") or 0)
        schema_version = str(artifact.get("schema_version") or "")
        content_hash = str(artifact.get("content_hash") or "")
        generated_at = str(artifact.get("generated_at") or "")
        model_version = str(artifact.get("model_version") or "")
        if not all((date, season, schema_version, content_hash, generated_at, model_version)):
            raise WNBAPRASnapshotStoreError("WNBA_PRA_SNAPSHOT_ARTIFACT_REQUIRED_FIELDS")
        response = self.client.post(
            self._url("/rest/v1/wnba_pra_page_snapshots?on_conflict=snapshot_date,season,schema_version"),
            headers={**self._write_headers, "Prefer": "resolution=merge-duplicates,return=representation"},
            json={
                "snapshot_date": date,
                "season": season,
                "schema_version": schema_version,
                "model_version": model_version,
                "content_hash": content_hash,
                "generated_at": generated_at,
                "artifact": dict(artifact),
            },
        )
        row = self._single(self._payload(response))
        return dict(row or {})

    def publish_with_lease(self, artifact: Mapping[str, Any], *, owner_id: str, lease_token: str) -> dict[str, Any]:
        response = self.client.post(
            self._url("/rest/v1/rpc/publish_wnba_pra_page_snapshot"),
            headers=self._write_headers,
            json={
                "p_snapshot_date": str(artifact.get("date") or ""),
                "p_season": int(artifact.get("season") or 0),
                "p_schema_version": str(artifact.get("schema_version") or ""),
                "p_model_version": str(artifact.get("model_version") or ""),
                "p_content_hash": str(artifact.get("content_hash") or ""),
                "p_generated_at": str(artifact.get("generated_at") or ""),
                "p_artifact": dict(artifact),
                "p_owner_id": str(owner_id),
                "p_lease_token": str(lease_token),
            },
        )
        row = self._single(self._payload(response))
        return dict(row or {})

    def claim_refresh(self, *, date: str, season: int, owner_id: str, ttl_seconds: int = 300) -> dict[str, Any]:
        response = self.client.post(
            self._url("/rest/v1/rpc/claim_wnba_pra_snapshot_refresh"),
            headers=self._write_headers,
            json={
                "p_snapshot_date": date,
                "p_season": int(season),
                "p_owner_id": str(owner_id),
                "p_ttl_seconds": int(ttl_seconds),
            },
        )
        row = self._single(self._payload(response))
        return dict(row or {})

    def release_refresh(self, *, date: str, season: int, owner_id: str, lease_token: str) -> dict[str, Any]:
        response = self.client.post(
            self._url("/rest/v1/rpc/release_wnba_pra_snapshot_refresh"),
            headers=self._write_headers,
            json={
                "p_snapshot_date": date,
                "p_season": int(season),
                "p_owner_id": str(owner_id),
                "p_lease_token": str(lease_token),
            },
        )
        row = self._single(self._payload(response))
        return dict(row or {})


__all__ = ["SnapshotStoreSettings", "WNBAPRASnapshotStore", "WNBAPRASnapshotStoreError"]
