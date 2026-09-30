"""MONSTER V3 Step 6 — Adaptive Proof Engine V1.

Read-only proof router. It selects the cheapest legitimate proof obligations
for the changed surface while preserving exact-head truth and fail-closed
behavior for unknown change types.

It performs no network calls and has no authority to mutate product/runtime
state.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable

VERSION = "MONSTER_ADAPTIVE_PROOF_ENGINE_V1"
NETWORK_CALLS = False
MAY_MODIFY_PRODUCT_RUNTIME = False

FULL_RELEASE_PROOFS = (
    "FULL_MERGED_MAIN",
    "PRODUCTION_CERTIFICATION",
)

_PROOF_ORDER = (
    "STATIC_CONTRACT",
    "TARGETED_BROWSER",
    "FIELD_CONTRACT",
    "PROVENANCE_PROOF",
    "ROUTE_CONTRACT",
    "FRESH_SESSION_NAVIGATION",
    "FULL_MERGED_MAIN",
    "PRODUCTION_CERTIFICATION",
)

_PROOF_MAP = {
    "CSS_UI": (
        "STATIC_CONTRACT",
        "TARGETED_BROWSER",
    ),
    "ROUTER_NAVIGATION": (
        "ROUTE_CONTRACT",
        "FRESH_SESSION_NAVIGATION",
    ),
    "PROVIDER_DATA": (
        "FIELD_CONTRACT",
        "PROVENANCE_PROOF",
    ),
    "RELEASE_DEPLOYMENT": FULL_RELEASE_PROOFS,
    "UNKNOWN": FULL_RELEASE_PROOFS,
}

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class AdaptiveProofFailure(RuntimeError):
    pass


def _clean_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").lower()


def _valid_sha(value: str) -> bool:
    return bool(_SHA_RE.fullmatch(str(value or "").strip().lower()))


def classify_change_type(path: str) -> str:
    value = _clean_path(path)
    if not value:
        return "UNKNOWN"

    if (
        value.endswith(".css")
        or value.startswith(".streamlit/")
        or "theme" in value
        or "style_tokens" in value
        or "design_tokens" in value
    ):
        return "CSS_UI"

    if any(
        token in value
        for token in (
            "router",
            "navigation",
            "nav_",
            "handoff",
            "route_",
        )
    ):
        return "ROUTER_NAVIGATION"

    if (
        value.startswith("sports_api/collectors/")
        or value.startswith("data/")
        or any(
            token in value
            for token in (
                "provider",
                "provenance",
                "market_adapter",
                "source_adapter",
            )
        )
    ):
        return "PROVIDER_DATA"

    if value in {"render.yaml", "render.yml", "procfile"}:
        return "RELEASE_DEPLOYMENT"

    if value.startswith(".github/workflows/") and any(
        token in value
        for token in (
            "deploy",
            "production",
            "release",
            "public-freeze",
            "public_freeze",
        )
    ):
        return "RELEASE_DEPLOYMENT"

    if value.startswith(("devsystem/production_", "devsystem/deployment_")):
        return "RELEASE_DEPLOYMENT"

    return "UNKNOWN"


def _dedupe_proofs(change_types: Iterable[str]) -> list[str]:
    requested = {
        proof
        for change_type in change_types
        for proof in _PROOF_MAP[change_type]
    }
    return [proof for proof in _PROOF_ORDER if proof in requested]


def plan_proof(
    paths: Iterable[str],
    *,
    expected_head_sha: str = "",
    observed_head_sha: str = "",
) -> dict[str, Any]:
    expected = str(expected_head_sha or "").strip().lower()
    observed = str(observed_head_sha or "").strip().lower()

    identity_supplied = bool(expected or observed)
    identity_valid = _valid_sha(expected) and _valid_sha(observed)

    if identity_supplied and (not identity_valid or expected != observed):
        return {
            "version": VERSION,
            "state": "STALE_HEAD",
            "change_types": [],
            "proofs": [],
            "full_release_required": False,
            "certifiable": False,
            "requires_replan": True,
            "identity": {
                "expected_head_sha": expected,
                "observed_head_sha": observed,
            },
            "protections": {
                "stale_head_cannot_certify": True,
                "unknown_change_fail_safe": True,
                "duplicate_proofs_removed": True,
                "network_calls": NETWORK_CALLS,
                "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
            },
        }

    clean_paths = [str(path).strip() for path in paths if str(path or "").strip()]
    change_types = sorted({classify_change_type(path) for path in clean_paths})
    if not change_types:
        change_types = ["UNKNOWN"]

    proofs = _dedupe_proofs(change_types)
    fail_safe = "UNKNOWN" in change_types
    full_release_required = any(proof in FULL_RELEASE_PROOFS for proof in proofs)

    return {
        "version": VERSION,
        "state": "FAIL_SAFE" if fail_safe else "READY",
        "change_types": change_types,
        "proofs": proofs,
        "full_release_required": full_release_required,
        "certifiable": bool(identity_valid and expected == observed),
        "requires_replan": False,
        "identity": {
            "expected_head_sha": expected,
            "observed_head_sha": observed,
        },
        "protections": {
            "stale_head_cannot_certify": True,
            "unknown_change_fail_safe": True,
            "duplicate_proofs_removed": True,
            "network_calls": NETWORK_CALLS,
            "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        },
    }


def contract_self_test() -> dict[str, Any]:
    head = "a" * 40
    old = "b" * 40

    css = plan_proof(
        ["ui/theme.css"],
        expected_head_sha=head,
        observed_head_sha=head,
    )
    router = plan_proof(
        ["streamlit_memory_lazy_router_v999.py"],
        expected_head_sha=head,
        observed_head_sha=head,
    )
    provider = plan_proof(
        ["sports_api/collectors/nfl_provider_v999.py"],
        expected_head_sha=head,
        observed_head_sha=head,
    )
    release = plan_proof(
        [".github/workflows/production-release-v999.yml"],
        expected_head_sha=head,
        observed_head_sha=head,
    )
    mixed = plan_proof(
        [
            "ui/theme.css",
            "streamlit_memory_lazy_router_v999.py",
            "sports_api/collectors/nfl_provider_v999.py",
        ],
        expected_head_sha=head,
        observed_head_sha=head,
    )
    stale = plan_proof(
        ["ui/theme.css"],
        expected_head_sha=head,
        observed_head_sha=old,
    )
    unknown = plan_proof(
        ["mystery/new_surface.bin"],
        expected_head_sha=head,
        observed_head_sha=head,
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "css_targeted_browser": css["proofs"] == [
            "STATIC_CONTRACT",
            "TARGETED_BROWSER",
        ],
        "router_fresh_session": router["proofs"] == [
            "ROUTE_CONTRACT",
            "FRESH_SESSION_NAVIGATION",
        ],
        "provider_provenance": provider["proofs"] == [
            "FIELD_CONTRACT",
            "PROVENANCE_PROOF",
        ],
        "release_full_certification": release["proofs"] == list(FULL_RELEASE_PROOFS),
        "mixed_union_no_duplicates": (
            len(mixed["proofs"]) == len(set(mixed["proofs"]))
            and mixed["proofs"] == [
                "STATIC_CONTRACT",
                "TARGETED_BROWSER",
                "FIELD_CONTRACT",
                "PROVENANCE_PROOF",
                "ROUTE_CONTRACT",
                "FRESH_SESSION_NAVIGATION",
            ]
        ),
        "stale_head_blocked": (
            stale["state"] == "STALE_HEAD"
            and stale["certifiable"] is False
            and stale["requires_replan"] is True
            and stale["proofs"] == []
        ),
        "unknown_fail_safe": (
            unknown["state"] == "FAIL_SAFE"
            and unknown["proofs"] == list(FULL_RELEASE_PROOFS)
            and unknown["full_release_required"] is True
        ),
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "network_calls": NETWORK_CALLS,
    }

    if not all(
        result[key] is True
        for key in (
            "css_targeted_browser",
            "router_fresh_session",
            "provider_provenance",
            "release_full_certification",
            "mixed_union_no_duplicates",
            "stale_head_blocked",
            "unknown_fail_safe",
        )
    ):
        raise AdaptiveProofFailure("adaptive proof engine self-test failed")

    return result


def main() -> int:
    print("MONSTER_ADAPTIVE_PROOF_ENGINE_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
