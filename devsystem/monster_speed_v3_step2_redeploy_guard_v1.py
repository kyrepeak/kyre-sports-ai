"""Monster Speed V3 Step 2 — cache-safe Streamlit redeploy guard."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
MARKER_REL = "deploy/streamlit-redeploy.txt"
MARKER = ROOT / MARKER_REL
TARGETED_CI = ROOT / ".github/workflows/devsystem-targeted-ci.yml"
MARKER_TOKEN = "STREAMLIT_CACHE_SAFE_REDEPLOY_V1"
COMMENT_ONLY_FAILURE = "COMMENT_ONLY_REQUIREMENTS_CHANGE_FORBIDDEN"


class RedeployGuardFailure(RuntimeError):
    pass


def dependency_lines(text: str) -> tuple[str, ...]:
    """Return only dependency specifications, ignoring blank/comment lines."""
    return tuple(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def validate_requirements_change(base_text: str, head_text: str) -> dict[str, object]:
    """Reject a requirements.txt edit when dependency specs did not change."""
    if base_text == head_text:
        return {"requirements_changed": False, "dependency_change": False}

    base_dependencies = dependency_lines(base_text)
    head_dependencies = dependency_lines(head_text)
    if base_dependencies == head_dependencies:
        raise RedeployGuardFailure(
            f"{COMMENT_ONLY_FAILURE}: use {MARKER_REL} for deployment-only refreshes"
        )
    return {
        "requirements_changed": True,
        "dependency_change": True,
        "base_dependency_count": len(base_dependencies),
        "head_dependency_count": len(head_dependencies),
    }


def _git_show(ref: str, path: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RedeployGuardFailure(
            f"unable to read {path} at {ref}: {proc.stderr.strip() or 'git show failed'}"
        )
    return proc.stdout


def validate_git_range(base: str, head: str) -> dict[str, object]:
    return validate_requirements_change(
        _git_show(base, "requirements.txt"),
        _git_show(head, "requirements.txt"),
    )


def check_repository() -> dict[str, object]:
    if not REQUIREMENTS.is_file():
        raise RedeployGuardFailure("requirements.txt missing")
    if not MARKER.is_file():
        raise RedeployGuardFailure(f"canonical redeploy marker missing: {MARKER_REL}")

    marker_text = MARKER.read_text(encoding="utf-8")
    if MARKER_TOKEN not in marker_text:
        raise RedeployGuardFailure("canonical redeploy marker token missing")

    workflow = TARGETED_CI.read_text(encoding="utf-8")
    if MARKER_REL in workflow:
        raise RedeployGuardFailure(
            f"{MARKER_REL} must not participate in dependency/browser cache keys"
        )

    cache_key_refs = workflow.count("hashFiles('requirements.txt'")
    if cache_key_refs < 4:
        raise RedeployGuardFailure(
            f"expected requirements-based cache keys, found only {cache_key_refs}"
        )

    dependencies = dependency_lines(REQUIREMENTS.read_text(encoding="utf-8"))
    if not dependencies:
        raise RedeployGuardFailure("requirements.txt has no dependency specifications")

    return {
        "status": "GREEN",
        "canonical_redeploy_marker": MARKER_REL,
        "requirements_dependency_count": len(dependencies),
        "requirements_cache_key_references": cache_key_refs,
        "marker_in_cache_keys": False,
        "product_runtime_changed": False,
        "router_changed": False,
        "model_changed": False,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = check_repository()
    if bool(args.base) != bool(args.head):
        raise RedeployGuardFailure("--base and --head must be provided together")
    if args.base and args.head:
        result["git_range"] = validate_git_range(args.base, args.head)

    print("MONSTER_SPEED_V3_STEP2_CACHE_SAFE_REDEPLOY_GREEN")
    print("MONSTER_SPEED_V3_STEP2_REQUIREMENTS_HAMMER_BLOCKED")
    print("MONSTER_SPEED_V3_STEP2_FROZEN_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
