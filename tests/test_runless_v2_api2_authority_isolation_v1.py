import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone

from runless_v2.config import Settings
from runless_v2.github_authority import (
    API2_LEASE_BRANCH,
    API2_LEASE_PATH,
    API2_REGISTRY_BRANCH,
    API2_REGISTRY_PATH,
    GithubAuthority,
)


def _settings():
    return Settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="svc",
        github_app_id="5204253",
        github_app_installation_id="99",
        github_app_private_key="key",
        proof_auth_token="proof",
    )


def _with_state_hash(value):
    out = copy.deepcopy(value)
    raw = json.dumps(out, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    out["state_hash"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return out


def test_api2_workstream_reads_only_api2_authority_sources():
    authority = GithubAuthority(_settings())
    calls = []
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    lease_state = _with_state_hash(
        {
            "schema_version": 1,
            "version": "API2_SCOPE_AWARE_EXECUTION_LEASE_V1",
            "system": "api2",
            "repository": "kyrepeak/kyre-sports-ai",
            "lease_ref": f"refs/heads/{API2_LEASE_BRANCH}",
            "lease_state_path": API2_LEASE_PATH,
            "revision": 1,
            "generation": 1,
            "holders": [
                {
                    "lease_id": "SCOPE-LEASE-API2-TEST",
                    "owner_id": "chatgpt:api2:test",
                    "expires_at_utc": expires,
                    "scope": {"dependency_tokens": ["system:api2"]},
                }
            ],
        }
    )
    registry_state = _with_state_hash(
        {
            "system": "api2",
            "repository": "kyrepeak/kyre-sports-ai",
            "registry_ref": f"refs/heads/{API2_REGISTRY_BRANCH}",
            "registry_path": API2_REGISTRY_PATH,
            "version": "API2_FROZEN_ARTIFACT_REGISTRY_V1",
            "revision": 5,
            "entries": {},
            "active_thaws": [],
        }
    )

    def fake_content(path, ref):
        calls.append((path, ref))
        if (path, ref) == (API2_LEASE_PATH, API2_LEASE_BRANCH):
            return lease_state
        if (path, ref) == (API2_REGISTRY_PATH, API2_REGISTRY_BRANCH):
            return registry_state
        raise AssertionError(f"foreign authority read: {ref}:{path}")

    authority._content_json = fake_content
    lease = authority._read_live_scope_lease_for_workstream(
        "api2-nba-pra-page2-insights-live-main-r1",
        "SCOPE-LEASE-API2-TEST",
    )
    registry = authority._read_frozen_registry_for_workstream(
        "api2-nba-pra-page2-insights-live-main-r1"
    )

    assert lease["lease_id"] == "SCOPE-LEASE-API2-TEST"
    assert registry["system"] == "api2"
    assert calls == [
        (API2_LEASE_PATH, API2_LEASE_BRANCH),
        (API2_REGISTRY_PATH, API2_REGISTRY_BRANCH),
    ]
    assert all("monster" not in ref.lower() and "monster" not in path.lower() for path, ref in calls)


def test_non_api2_workstream_keeps_legacy_authority_methods():
    authority = GithubAuthority(_settings())
    authority.read_live_scope_lease = lambda lease_id: {"lease_id": lease_id}
    authority.read_frozen_registry = lambda: {"entries": {}, "active_thaws": []}

    lease = authority._read_live_scope_lease_for_workstream("ws-legacy", "legacy-lease")
    registry = authority._read_frozen_registry_for_workstream("ws-legacy")

    assert lease["lease_id"] == "legacy-lease"
    assert registry == {"entries": {}, "active_thaws": []}
