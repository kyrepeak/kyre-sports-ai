from __future__ import annotations

from typing import Any

from devsystem.frozen_artifact_registry_v1 import (
    FrozenArtifactRegistryFailure,
    validate_registry,
)

from . import cfb_step8_route_pointer_lock_premerge_r1 as r1
from . import cfb_step8_route_pointer_lock_premerge_registry_baseline_r2 as r2  # noqa: F401
from . import prove
from .registry import GithubRegistryBackend
from .step2a import Step2AError


def _is_ancestor(client, ancestor: str, descendant: str) -> bool:
    if ancestor == descendant:
        return True
    comparison = client.request("GET", f"/compare/{ancestor}...{descendant}")
    return comparison.get("status") in {"ahead", "identical"}


def _verify_frozen_candidate_descendant(
    client,
    candidate_sha: str,
    tree: dict[str, str],
    *,
    main_sha: str | None = None,
    main_tree: dict[str, str] | None = None,
) -> dict[str, Any]:
    registry = GithubRegistryBackend(client).read_registry()
    validated = validate_registry(registry)

    registry_source = str(registry.get("source_main_sha") or "")
    effective_main_sha = main_sha or registry_source
    effective_main_tree = main_tree if main_tree is not None else validated["artifacts"]

    inherited_authority: dict[str, str] = {}
    if main_sha is not None and registry_source != main_sha:
        if not _is_ancestor(client, registry_source, effective_main_sha):
            raise Step2AError("RUNLESS_REGISTRY_MAIN_IDENTITY_DRIFT")

        for path, expected in sorted(validated["artifacts"].items()):
            main_blob_raw = effective_main_tree.get(path)
            main_blob = str(main_blob_raw).lower() if main_blob_raw else None
            if main_blob is None:
                raise FrozenArtifactRegistryFailure(f"frozen artifact missing from main: {path}")
            if main_blob == expected:
                continue

            matches: list[str] = []
            for grant in registry.get("active_thaws", []):
                pair = (grant.get("files") or {}).get(path)
                if not isinstance(pair, dict):
                    continue
                target = str(grant.get("target_head_sha") or "")
                if (
                    str(pair.get("from_blob") or "").lower() == expected
                    and str(pair.get("to_blob") or "").lower() == main_blob
                    and target
                    and _is_ancestor(client, target, effective_main_sha)
                ):
                    matches.append(str(grant.get("thaw_id") or ""))

            if len(matches) != 1:
                raise FrozenArtifactRegistryFailure(
                    "INHERITED_FROZEN_STATE_WITHOUT_EXACT_MERGED_THAW:"
                    f"{path}:expected={expected}:main={main_blob}:matches={len(matches)}"
                )
            inherited_authority[path] = matches[0]

    inherited: list[str] = []
    thawed: list[str] = []
    for path, expected in sorted(validated["artifacts"].items()):
        main_blob_raw = effective_main_tree.get(path)
        candidate_blob_raw = tree.get(path)
        main_blob = str(main_blob_raw).lower() if main_blob_raw else None
        candidate_blob = str(candidate_blob_raw).lower() if candidate_blob_raw else None
        if main_blob is None or candidate_blob is None:
            raise FrozenArtifactRegistryFailure(f"frozen artifact missing: {path}")

        if candidate_blob == main_blob:
            if candidate_blob != expected:
                if path not in inherited_authority:
                    raise FrozenArtifactRegistryFailure(
                        "INHERITED_FROZEN_STATE_WITHOUT_EXACT_MERGED_THAW:" + path
                    )
                inherited.append(path)
            continue

        if main_blob != expected:
            raise FrozenArtifactRegistryFailure(
                f"candidate modifies unreconciled inherited frozen state: {path}"
            )

        matches = []
        for grant in registry.get("active_thaws", []):
            if str(grant.get("target_head_sha") or "") != candidate_sha:
                continue
            pair = (grant.get("files") or {}).get(path)
            if not isinstance(pair, dict):
                continue
            if (
                str(pair.get("from_blob") or "").lower() == expected
                and str(pair.get("to_blob") or "").lower() == candidate_blob
            ):
                matches.append(str(grant.get("thaw_id") or ""))
        if len(matches) != 1:
            raise FrozenArtifactRegistryFailure(
                "candidate frozen delta without exact thaw grant: "
                f"{path} expected={expected} main={main_blob} candidate={candidate_blob}"
            )
        thawed.append(path)

    return {
        "revision": int(registry["revision"]),
        "state_hash": str(registry["state_hash"]),
        "source_main_sha": effective_main_sha,
        "registry_source_main_sha": registry_source,
        "active_thaws": [str(item["thaw_id"]) for item in registry.get("active_thaws", [])],
        "inherited_frozen_paths": inherited,
        "inherited_authority": inherited_authority,
        "exact_thawed_paths": thawed,
    }


prove._verify_frozen_candidate = _verify_frozen_candidate_descendant
install_startup = r1.install_startup
