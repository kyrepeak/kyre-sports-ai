from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
import jwt

from .config import Settings
from .models import ProofRequest, RegistryThawRequest
from .receipt_contract import validate_receipt

APP_ID_EXPECTED = "5204253"
LEASE_BRANCH = "monster-scope-aware-execution-leases"
LEASE_PATH = "devsystem/scope_aware_execution_lease_state_v1.json"
REGISTRY_BRANCH = "monster-frozen-artifact-registry"
REGISTRY_PATH = "devsystem/frozen_artifact_registry_state_v1.json"


class GithubAuthorityError(RuntimeError):
    pass


class GithubAuthority:
    def __init__(self, settings: Settings, *, client: httpx.Client | None = None):
        if settings.github_app_id != APP_ID_EXPECTED:
            raise GithubAuthorityError("RUNLESS_V2_GITHUB_APP_ID_MISMATCH")
        self.settings = settings
        self.client = client or httpx.Client(timeout=20)
        self.base = f"https://api.github.com/repos/{settings.repository}"
        self._token: str | None = None
        self._token_until = 0.0

    def _app_jwt(self) -> str:
        now = int(time.time())
        return jwt.encode(
            {"iat": now - 30, "exp": now + 540, "iss": self.settings.github_app_id},
            self.settings.github_app_private_key,
            algorithm="RS256",
        )

    def installation_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_until - 60:
            return self._token
        response = self.client.post(
            f"https://api.github.com/app/installations/{self.settings.github_app_installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {self._app_jwt()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("token")
        if not token:
            raise GithubAuthorityError("RUNLESS_V2_INSTALLATION_TOKEN_MISSING")
        self._token = str(token)
        self._token_until = now + 2700
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.installation_token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, method: str, path: str, *, allow_404: bool = False, **kwargs: Any) -> Any:
        response = self.client.request(method, self.base + path, headers=self._headers(), **kwargs)
        if allow_404 and response.status_code == 404:
            return None
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    def commit(self, sha: str) -> dict[str, Any]:
        return self._request("GET", f"/commits/{sha}")

    def main_sha(self) -> str:
        payload = self._request("GET", "/git/ref/heads/main")
        return str(payload["object"]["sha"])

    def tree_blobs(self, sha: str) -> dict[str, str]:
        commit = self.commit(sha)
        tree_sha = commit["commit"]["tree"]["sha"]
        payload = self._request("GET", f"/git/trees/{tree_sha}?recursive=1")
        return {
            item["path"]: item["sha"]
            for item in payload.get("tree", [])
            if item.get("type") == "blob"
        }

    def _content_json(self, path: str, ref: str) -> dict[str, Any]:
        raw = self._request("GET", f"/contents/{quote(path, safe='/')}?ref={quote(ref, safe='/')}")
        if not raw or raw.get("encoding") != "base64":
            raise GithubAuthorityError("RUNLESS_V2_GITHUB_CONTENT_READ_FAILED")
        try:
            return json.loads(base64.b64decode(raw["content"]).decode())
        except Exception as exc:
            raise GithubAuthorityError("RUNLESS_V2_GITHUB_CONTENT_DECODE_FAILED") from exc

    @staticmethod
    def _utc(value: str) -> datetime:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def read_live_scope_lease(self, lease_id: str) -> dict[str, Any]:
        state = self._content_json(LEASE_PATH, LEASE_BRANCH)
        now = datetime.now(timezone.utc)
        matches = [
            holder for holder in state.get("holders", [])
            if holder.get("lease_id") == lease_id
            and now < self._utc(holder["expires_at_utc"])
        ]
        if len(matches) != 1:
            raise GithubAuthorityError("RUNLESS_V2_SCOPE_LEASE_NOT_LIVE")
        return dict(matches[0])

    def read_frozen_registry(self) -> dict[str, Any]:
        return self._content_json(REGISTRY_PATH, REGISTRY_BRANCH)

    @staticmethod
    def _plan_value(plan: Any, name: str, default: Any = None) -> Any:
        if isinstance(plan, dict):
            return plan.get(name, default)
        return getattr(plan, name, default)

    @staticmethod
    def _path_map(tree: dict[str, str], paths: list[str] | tuple[str, ...], label: str) -> dict[str, str]:
        missing = [path for path in paths if path not in tree]
        if missing:
            raise GithubAuthorityError(f"RUNLESS_V2_{label}_MISSING:" + ",".join(sorted(missing)))
        return {path: tree[path] for path in sorted(paths)}

    @staticmethod
    def _flatten_registry_artifacts(registry: dict[str, Any]) -> dict[str, str]:
        out: dict[str, str] = {}
        for entry in registry.get("entries", {}).values():
            for path, blob in (entry.get("artifacts") or {}).items():
                if path in out and out[path] != blob:
                    raise GithubAuthorityError("RUNLESS_V2_REGISTRY_ARTIFACT_CONFLICT")
                out[path] = str(blob).lower()
        return out

    def _verify_frozen_candidate(
        self,
        candidate_sha: str,
        candidate_tree: dict[str, str],
        main_sha: str,
        main_tree: dict[str, str],
        registry: dict[str, Any],
    ) -> None:
        # The registry source-main identity may legitimately lag after an unrelated
        # main advance. Frozen artifact blobs are the authoritative invariant: every
        # frozen path below must still match its baseline (or an exact candidate thaw).
        artifacts = self._flatten_registry_artifacts(registry)
        for path, expected in sorted(artifacts.items()):
            main_blob = main_tree.get(path)
            candidate_blob = candidate_tree.get(path)
            if not main_blob or not candidate_blob:
                raise GithubAuthorityError("RUNLESS_V2_FROZEN_ARTIFACT_MISSING:" + path)
            main_blob = str(main_blob).lower()
            candidate_blob = str(candidate_blob).lower()
            if candidate_blob == main_blob:
                if main_blob != expected:
                    raise GithubAuthorityError("RUNLESS_V2_FROZEN_BASELINE_DRIFT:" + path)
                continue
            if main_blob != expected:
                raise GithubAuthorityError("RUNLESS_V2_FROZEN_BASELINE_DRIFT:" + path)
            matches = []
            for grant in registry.get("active_thaws", []):
                if str(grant.get("target_head_sha") or "") != candidate_sha:
                    continue
                pair = (grant.get("files") or {}).get(path)
                if isinstance(pair, dict) and str(pair.get("from_blob") or "").lower() == expected and str(pair.get("to_blob") or "").lower() == candidate_blob:
                    matches.append(str(grant.get("thaw_id") or ""))
            if len(matches) != 1:
                raise GithubAuthorityError("RUNLESS_V2_FROZEN_DELTA_WITHOUT_THAW:" + path)

    def verify_step2a(
        self,
        request: ProofRequest,
        plan: Any,
        candidate_tree: dict[str, str],
        main_tree: dict[str, str],
    ) -> dict[str, Any]:
        commit = self.commit(request.candidate_sha)
        if str(commit.get("sha") or "") != request.candidate_sha:
            raise GithubAuthorityError("RUNLESS_V2_EXACT_HEAD_DRIFT")
        if self._plan_value(plan, "workstream") != request.workstream:
            raise GithubAuthorityError("RUNLESS_V2_PLAN_WORKSTREAM_MISMATCH")
        main_sha = self.main_sha()
        if request.expected_main_sha and main_sha != request.expected_main_sha:
            raise GithubAuthorityError("RUNLESS_V2_MAIN_IDENTITY_DRIFT")
        scope_lease = self.read_live_scope_lease(request.lease_id)
        registry = self.read_frozen_registry()
        self._verify_frozen_candidate(request.candidate_sha, candidate_tree, main_sha, main_tree, registry)
        artifacts = tuple(self._plan_value(plan, "artifacts", ()))
        dependencies = tuple(self._plan_value(plan, "dependencies", ()))
        return {
            "candidate_sha": request.candidate_sha,
            "main_sha": main_sha,
            "scope_lease": scope_lease,
            "registry": {
                "revision": registry.get("revision"),
                "state_hash": registry.get("state_hash"),
                "active_thaws": [item.get("thaw_id") for item in registry.get("active_thaws", [])],
            },
            "artifact_map": self._path_map(candidate_tree, artifacts, "ARTIFACT"),
            "dependency_map": self._path_map(candidate_tree, dependencies, "DEPENDENCY"),
        }

    def request_registry_thaw(self, request: RegistryThawRequest) -> dict[str, Any]:
        from .registry_thaw import request_registry_thaw

        return request_registry_thaw(self, request)

    def _receipt_path(self, proof_id: str) -> str:
        return f"{self.settings.receipt_path.rstrip('/')}/{proof_id}.json"

    def _read_receipt(self, proof_id: str) -> dict[str, Any] | None:
        path = self._receipt_path(proof_id)
        raw = self._request(
            "GET",
            f"/contents/{quote(path, safe='/')}?ref={quote(self.settings.receipt_ref, safe='/')}",
            allow_404=True,
        )
        if raw is None:
            return None
        try:
            return json.loads(base64.b64decode(raw["content"]).decode())
        except Exception as exc:
            raise GithubAuthorityError("RUNLESS_V2_RECEIPT_READ_FAILED") from exc

    def _ensure_receipt_ref(self, candidate_sha: str) -> None:
        ref = self._request(
            "GET",
            f"/git/ref/heads/{quote(self.settings.receipt_ref, safe='/')}",
            allow_404=True,
        )
        if ref is None:
            self._request("POST", "/git/refs", json={"ref": f"refs/heads/{self.settings.receipt_ref}", "sha": candidate_sha})

    def put_or_read_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        validate_receipt(receipt)
        existing = self._read_receipt(receipt["proof_id"])
        if existing is not None:
            try:
                validate_receipt(existing)
            except ValueError as exc:
                raise GithubAuthorityError("RUNLESS_V2_RECEIPT_TAMPERED") from exc
            keys = ("proof_id", "task_id", "workstream", "candidate_sha", "digest")
            if any(existing.get(key) != receipt.get(key) for key in keys):
                raise GithubAuthorityError("RUNLESS_V2_RECEIPT_IDENTITY_COLLISION")
            return existing
        self._ensure_receipt_ref(receipt["candidate_sha"])
        path = self._receipt_path(receipt["proof_id"])
        content = base64.b64encode((json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()).decode()
        self._request(
            "PUT",
            f"/contents/{quote(path, safe='/')}",
            json={
                "message": f"runless v2 receipt: {receipt['proof_id']}",
                "content": content,
                "branch": self.settings.receipt_ref,
            },
        )
        readback = self._read_receipt(receipt["proof_id"])
        if readback is None or readback.get("digest") != receipt["digest"]:
            raise GithubAuthorityError("RUNLESS_V2_RECEIPT_READBACK_FAILED")
        validate_receipt(readback)
        return readback

    def _publish_check(self, candidate_sha: str, receipt: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/check-runs",
            json={
                "name": self.settings.gate_name,
                "head_sha": candidate_sha,
                "status": "completed",
                "conclusion": "success",
                "output": {
                    "title": "Runless V2 Proof Authority",
                    "summary": f"runless-v2 receipt={receipt['digest']} proof={receipt['proof_id']}",
                },
            },
        )

    def _check_runs(self, candidate_sha: str) -> list[dict[str, Any]]:
        payload = self._request("GET", f"/commits/{candidate_sha}/check-runs")
        return list(payload.get("check_runs", []))

    def publish_gate_and_readback(self, candidate_sha: str, receipt: dict[str, Any]) -> dict[str, Any]:
        validate_receipt(receipt)
        if receipt["candidate_sha"] != candidate_sha:
            raise GithubAuthorityError("RUNLESS_V2_GATE_SHA_MISMATCH")
        self._publish_check(candidate_sha, receipt)
        for check in self._check_runs(candidate_sha):
            summary = str((check.get("output") or {}).get("summary") or "")
            if (
                check.get("name") == self.settings.gate_name
                and check.get("conclusion") == "success"
                and str(check.get("head_sha") or "") == candidate_sha
                and str((check.get("app") or {}).get("id")) == APP_ID_EXPECTED
                and receipt["digest"] in summary
                and receipt["proof_id"] in summary
            ):
                return check
        raise GithubAuthorityError("RUNLESS_V2_GATE_READBACK_FAILED")
