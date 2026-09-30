"""MONSTER V3 Step 6 — Adaptive Proof Engine V1.

Read-only proof router. It selects the cheapest legitimate proof obligations
for the changed surface while preserving exact-head truth and fail-closed
behavior for unknown change types.

It performs no network calls and has no authority to mutate product/runtime
state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
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


def _git_changed_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AdaptiveProofFailure(
            f"git diff failed base={base} head={head}: {result.stderr.strip()}"
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip().lower()
    if result.returncode != 0 or not _valid_sha(value):
        raise AdaptiveProofFailure("unable to resolve exact checked-out HEAD")
    return value


def _write_github_output(path: str | Path, plan: dict[str, Any]) -> None:
    proofs = set(plan.get("proofs") or ())
    values = {
        "proof_state": str(plan.get("state") or ""),
        "proof_static_contract": "true" if "STATIC_CONTRACT" in proofs else "false",
        "proof_targeted_browser": "true" if "TARGETED_BROWSER" in proofs else "false",
        "proof_field_contract": "true" if "FIELD_CONTRACT" in proofs else "false",
        "proof_provenance": "true" if "PROVENANCE_PROOF" in proofs else "false",
        "proof_route_contract": "true" if "ROUTE_CONTRACT" in proofs else "false",
        "proof_fresh_session_navigation": "true" if "FRESH_SESSION_NAVIGATION" in proofs else "false",
        "proof_full_merged_main": "true" if "FULL_MERGED_MAIN" in proofs else "false",
        "proof_production_certification": "true" if "PRODUCTION_CERTIFICATION" in proofs else "false",
        "full_release_required": "true" if plan.get("full_release_required") else "false",
        "proof_certifiable": "true" if plan.get("certifiable") else "false",
        "proof_change_types": ",".join(plan.get("change_types") or ()),
        "proof_obligations": ",".join(plan.get("proofs") or ()),
    }
    output = Path(path)
    with output.open("a", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}={value}\n")


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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--paths-file")
    parser.add_argument("--expected-head")
    parser.add_argument("--observed-head")
    parser.add_argument("--github-output")
    parser.add_argument("--manual", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    has_cli_plan = any(
        (
            args.base,
            args.head,
            args.paths_file,
            args.expected_head,
            args.observed_head,
            args.github_output,
            args.manual,
        )
    )

    if not has_cli_plan:
        print("MONSTER_ADAPTIVE_PROOF_ENGINE_V1_GREEN")
        print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
        return 0

    if args.manual:
        observed = _git_head_sha()
        plan = plan_proof(
            ["manual/full-release"],
            expected_head_sha=observed,
            observed_head_sha=observed,
        )
    elif args.paths_file:
        paths = Path(args.paths_file).read_text(encoding="utf-8").splitlines()
        plan = plan_proof(
            paths,
            expected_head_sha=str(args.expected_head or ""),
            observed_head_sha=str(args.observed_head or ""),
        )
    else:
        if not args.base or not args.head:
            raise SystemExit("--base and --head are required unless --manual/--paths-file is used")
        observed = _git_head_sha()
        plan = plan_proof(
            _git_changed_paths(args.base, args.head),
            expected_head_sha=args.head,
            observed_head_sha=observed,
        )

    if args.github_output:
        _write_github_output(args.github_output, plan)

    print("MONSTER_ADAPTIVE_PROOF_PLAN")
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 1 if plan.get("state") == "STALE_HEAD" else 0


if __name__ == "__main__":
    raise SystemExit(main())
