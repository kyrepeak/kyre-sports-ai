"""MONSTER V6 Step 1 — Content-Addressed Proof Reuse CI adapter.

This read-only adapter converts the generic content-addressed proof-reuse engine
into a GitHub Actions decision for expensive sport-critical merged-main proof.

Reuse is fail-closed. It is approved only when:
- the immediately previous main commit has a completed successful DevSystem
  targeted CI push run,
- that run published a terminal proof receipt,
- every protected non-control-plane repository blob is byte-identical between
  the previous main commit and the candidate commit,
- proof-policy dependencies are byte-identical,
- the generic V6 proof-reuse engine approves the resulting receipt.

Any missing ref, missing artifact, API error, policy drift, or content drift
returns reuse=false so the expensive proof runs normally.

No repository mutation is performed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.content_addressed_proof_reuse_v1 import build_receipt, evaluate_reuse

VERSION = "MONSTER_V6_CONTENT_ADDRESSED_PROOF_REUSE_CI_V1"
NETWORK_CALLS = True
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
TARGET_WORKFLOW_NAME = "DevSystem targeted CI"
TERMINAL_ARTIFACT_PREFIX = "monster-v4-step5-terminal-proof-"
REQUIRED_SCOPE = (
    "CFB_CRITICAL",
    "MLB_CRITICAL",
    "WNBA_CRITICAL",
    "NFL_CRITICAL",
)
POLICY_DEPENDENCIES = (
    ".github/workflows/devsystem-targeted-ci.yml",
    "devsystem/change_classifier_v1.py",
    "devsystem/content_addressed_proof_reuse_v1.py",
    "devsystem/content_addressed_proof_reuse_ci_v1.py",
    "devsystem/permanent_gate_v1.py",
)
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ProofReuseCIFailure(RuntimeError):
    pass


def _valid_sha(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not _SHA40.fullmatch(text):
        raise ProofReuseCIFailure("full 40-character SHA required")
    return text


def _control_plane_excluded(path: str) -> bool:
    value = str(path or "").strip().replace("\\", "/")
    if value.startswith("devsystem/"):
        return True
    if value.startswith("tests/test_devsystem_"):
        return True
    if value.startswith("docs/"):
        return True
    return False


def parse_ls_tree(text: str) -> dict[str, str]:
    blobs: dict[str, str] = {}
    for raw in str(text or "").splitlines():
        if not raw.strip():
            continue
        try:
            meta, path = raw.split("\t", 1)
            mode, kind, sha = meta.split(" ", 2)
        except ValueError as exc:
            raise ProofReuseCIFailure("invalid git ls-tree row") from exc
        if kind != "blob":
            continue
        path = path.strip().replace("\\", "/")
        if not path or path.startswith("../") or "/../" in path:
            raise ProofReuseCIFailure("invalid tree path")
        blobs[path] = _valid_sha(sha)
    return dict(sorted(blobs.items()))


def protected_blob_map(tree: Mapping[str, str]) -> dict[str, str]:
    out = {
        str(path): _valid_sha(sha)
        for path, sha in tree.items()
        if not _control_plane_excluded(str(path))
    }
    if not out:
        raise ProofReuseCIFailure("protected repository surface is empty")
    return dict(sorted(out.items()))


def policy_dependency_map(tree: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in POLICY_DEPENDENCIES:
        sha = tree.get(path)
        if sha is None:
            raise ProofReuseCIFailure(f"policy dependency missing: {path}")
        out[path] = _valid_sha(sha)
    return dict(sorted(out.items()))


def _git_tree(ref: str, root: Path) -> dict[str, str]:
    sha = _valid_sha(ref)
    completed = subprocess.run(
        ["git", "ls-tree", "-r", "--full-tree", sha],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise ProofReuseCIFailure(completed.stderr.strip() or "git ls-tree failed")
    return parse_ls_tree(completed.stdout)


def _api_json(url: str, token: str) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "monster-v6-proof-reuse",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ProofReuseCIFailure("GitHub API response must be an object")
    return payload


def discover_parent_terminal_proof(
    *,
    repository: str,
    base_sha: str,
    token: str,
    api_json: Callable[[str, str], dict[str, Any]] = _api_json,
    api_root: str = "https://api.github.com",
) -> dict[str, Any] | None:
    repo = str(repository or "").strip()
    base = _valid_sha(base_sha)
    if "/" not in repo:
        raise ProofReuseCIFailure("repository must be owner/name")
    query = urllib.parse.urlencode(
        {
            "head_sha": base,
            "event": "push",
            "status": "completed",
            "per_page": "50",
        }
    )
    runs_url = f"{api_root}/repos/{repo}/actions/runs?{query}"
    runs_payload = api_json(runs_url, token)
    candidates = [
        run
        for run in (runs_payload.get("workflow_runs") or [])
        if isinstance(run, Mapping)
        and str(run.get("name") or "") == TARGET_WORKFLOW_NAME
        and str(run.get("event") or "") == "push"
        and str(run.get("head_sha") or "").lower() == base
        and str(run.get("conclusion") or "").lower() == "success"
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda run: (int(run.get("run_number") or 0), int(run.get("id") or 0)),
        reverse=True,
    )
    run = candidates[0]
    run_id = int(run.get("id") or 0)
    if run_id <= 0:
        return None
    artifacts_url = f"{api_root}/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    artifacts_payload = api_json(artifacts_url, token)
    receipts = [
        artifact
        for artifact in (artifacts_payload.get("artifacts") or [])
        if isinstance(artifact, Mapping)
        and str(artifact.get("name") or "").startswith(TERMINAL_ARTIFACT_PREFIX)
        and not bool(artifact.get("expired"))
        and _DIGEST.fullmatch(str(artifact.get("digest") or "").lower())
        and str((artifact.get("workflow_run") or {}).get("head_sha") or "").lower() == base
    ]
    if not receipts:
        return None
    receipts.sort(key=lambda artifact: int(artifact.get("id") or 0), reverse=True)
    artifact = receipts[0]
    return {
        "run_id": run_id,
        "terminal_receipt_digest": str(artifact["digest"]).lower(),
        "artifact_id": int(artifact.get("id") or 0),
        "head_sha": base,
    }


def evaluate_ci_reuse(
    *,
    base_sha: str,
    head_sha: str,
    repository: str,
    token: str,
    root: Path,
    api_json: Callable[[str, str], dict[str, Any]] = _api_json,
) -> dict[str, Any]:
    try:
        base = _valid_sha(base_sha)
        head = _valid_sha(head_sha)
        if base == "0" * 40:
            raise ProofReuseCIFailure("zero base SHA cannot reuse proof")

        base_tree = _git_tree(base, root)
        head_tree = _git_tree(head, root)
        base_artifacts = protected_blob_map(base_tree)
        head_artifacts = protected_blob_map(head_tree)
        base_dependencies = policy_dependency_map(base_tree)
        head_dependencies = policy_dependency_map(head_tree)

        parent = discover_parent_terminal_proof(
            repository=repository,
            base_sha=base,
            token=token,
            api_json=api_json,
        )
        if parent is None:
            return {
                "version": VERSION,
                "decision": "RUN_FRESH_SPORT_PROOF",
                "reuse_sport_critical": False,
                "reason": "PARENT_TERMINAL_PROOF_UNAVAILABLE",
                "base_sha": base,
                "head_sha": head,
            }

        receipt = build_receipt(
            checkpoint_id=f"MAIN_{base[:12]}_SPORT_CRITICAL",
            source_main_sha=base,
            proof_run_id=int(parent["run_id"]),
            terminal_receipt_digest=str(parent["terminal_receipt_digest"]),
            proof_policy_version=VERSION,
            proof_scope=REQUIRED_SCOPE,
            artifacts=base_artifacts,
            dependencies=base_dependencies,
            proof_kind="STATIC_CONTENT",
        )
        reuse = evaluate_reuse(
            receipt,
            observed_artifacts=head_artifacts,
            observed_dependencies=head_dependencies,
            required_scope=REQUIRED_SCOPE,
            proof_policy_version=VERSION,
            current_head_sha=head,
        )
        approved = reuse.get("reusable") is True
        return {
            "version": VERSION,
            "decision": "REUSE_PARENT_SPORT_PROOF" if approved else "RUN_FRESH_SPORT_PROOF",
            "reuse_sport_critical": approved,
            "reason": "EXACT_CONTENT_MATCH" if approved else ",".join(reuse.get("reasons") or []),
            "base_sha": base,
            "head_sha": head,
            "protected_blob_count": len(head_artifacts),
            "policy_dependency_count": len(head_dependencies),
            "parent_proof_run_id": int(parent["run_id"]),
            "parent_terminal_receipt_digest": str(parent["terminal_receipt_digest"]),
            "content_fingerprint": reuse.get("content_fingerprint"),
            "protections": {
                "parent_success_required": True,
                "terminal_receipt_required": True,
                "exact_blob_identity_required": True,
                "policy_dependency_identity_required": True,
                "fail_closed_to_fresh_proof": True,
                "auto_mutate": AUTO_MUTATE,
                "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
                "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
            },
        }
    except Exception as exc:
        return {
            "version": VERSION,
            "decision": "RUN_FRESH_SPORT_PROOF",
            "reuse_sport_critical": False,
            "reason": f"FAIL_CLOSED:{type(exc).__name__}:{exc}",
            "base_sha": str(base_sha or "").lower(),
            "head_sha": str(head_sha or "").lower(),
            "protections": {
                "fail_closed_to_fresh_proof": True,
                "auto_mutate": AUTO_MUTATE,
                "may_modify_product_runtime": MAY_MODIFY_PRODUCT_RUNTIME,
                "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
            },
        }


def _write_github_output(path: Path, result: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            "reuse_sport_critical="
            + ("true" if result.get("reuse_sport_critical") is True else "false")
            + "\n"
        )
        handle.write(f"decision={result.get('decision', 'RUN_FRESH_SPORT_PROOF')}\n")
        handle.write(f"parent_proof_run_id={result.get('parent_proof_run_id', '')}\n")


def contract_self_test() -> dict[str, Any]:
    a = "a" * 40
    b = "b" * 40
    c = "c" * 40
    rows = "\n".join(
        [
            f"100644 blob {a}\tdevsystem/internal.py",
            f"100644 blob {a}\ttests/test_devsystem_internal.py",
            f"100644 blob {a}\tdocs/readme.md",
            f"100644 blob {b}\tcfb_runtime.py",
            f"100644 blob {c}\tsports_api/nfl_runtime.py",
            f"100644 blob {b}\t.github/workflows/devsystem-targeted-ci.yml",
        ]
    )
    tree = parse_ls_tree(rows)
    protected = protected_blob_map(tree)
    return {
        "status": "GREEN",
        "version": VERSION,
        "control_plane_excluded": (
            "devsystem/internal.py" not in protected
            and "tests/test_devsystem_internal.py" not in protected
            and "docs/readme.md" not in protected
        ),
        "product_surface_protected": (
            protected["cfb_runtime.py"] == b
            and protected["sports_api/nfl_runtime.py"] == c
        ),
        "workflow_surface_protected": ".github/workflows/devsystem-targeted-ci.yml" in protected,
        "network_is_read_only": NETWORK_CALLS is True and AUTO_MUTATE is False,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MONSTER V6 proof reuse CI adapter")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--github-output")
    args = parser.parse_args()

    result = evaluate_ci_reuse(
        base_sha=args.base,
        head_sha=args.head,
        repository=args.repository,
        token=os.environ.get("GITHUB_TOKEN", ""),
        root=Path(args.root).resolve(),
    )
    print("MONSTER_V6_CONTENT_ADDRESSED_PROOF_REUSE_CI_DECISION")
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.github_output:
        _write_github_output(Path(args.github_output), result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
