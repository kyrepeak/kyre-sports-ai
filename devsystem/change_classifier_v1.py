"""Permanent DevSystem change classifier.

One source of truth for deciding which sport lanes should run. It intentionally
uses token-boundary path rules so WNBA is never accidentally classified as NBA.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "devsystem" / "devsystem_manifest_v1.json"
DOMAIN_KEYS = ("cfb", "mlb", "wnba", "nfl", "nba", "nhl", "soccer")


def _load_manifest(path: Path = MANIFEST_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _domain_match(path: str, domain: str) -> bool:
    p = path.strip().replace("\\", "/").lower()
    candidates = (
        f"{domain}_",
        f"tests/test_{domain}_",
        f"data/{domain}_",
        f"scripts/build_{domain}_",
        f"sports_api/{domain}_",
        f"sports_api/api/{domain}",
        f"sports_api/collectors/{domain}_",
        f".github/workflows/{domain}",
    )
    if p.startswith(candidates):
        return True
    return f"/{domain}_" in p


def _is_core(path: str, matched_domains: set[str]) -> bool:
    p = path.strip().replace("\\", "/")
    low = p.lower()
    if low in {
        "app.py",
        "engine.py",
        "history.py",
        "spread_engine.py",
        ".github/workflows/devsystem-targeted-ci.yml",
        ".github/workflows/devsystem-production-verification.yml",
    }:
        return True
    if low.startswith(
        (
            "requirements",
            ".streamlit/",
            "devsystem/",
            "tests/test_devsystem_",
            "streamlit_",
        )
    ):
        return True
    if low.startswith("sports_api/") and not matched_domains:
        return True
    return False


def _risk_flags(paths: Iterable[str]) -> dict[str, bool]:
    lower = [p.lower().replace("\\", "/") for p in paths]
    ui = any(
        p == "app.py"
        or p.startswith("streamlit_")
        or "clean_page" in p
        or "_hub_" in p
        for p in lower
    )
    api = any(
        p.startswith("sports_api/")
        or "/api/" in p
        or "/collectors/" in p
        for p in lower
    )
    data = any(
        p.startswith("data/")
        or "snapshot" in p
        or p.startswith("scripts/build_")
        for p in lower
    )
    model = any(
        token in p
        for p in lower
        for token in (
            "_model",
            "_engine",
            "monte_carlo",
            "simulation",
            "projection",
            "probability",
        )
    )
    infra = any(
        p.startswith(".github/")
        or p.startswith("devsystem/")
        or p.startswith("requirements")
        for p in lower
    )
    return {
        "ui": ui,
        "api": api,
        "data": data,
        "model": model,
        "infra": infra,
    }


def classify(paths: Iterable[str], manifest: dict | None = None) -> dict:
    payload = manifest or _load_manifest()
    clean_paths = [p.strip() for p in paths if p and p.strip()]
    domains: dict[str, bool] = {key: False for key in DOMAIN_KEYS}
    per_path_domains: dict[str, set[str]] = {}

    for path in clean_paths:
        matches = {key for key in DOMAIN_KEYS if _domain_match(path, key)}
        per_path_domains[path] = matches
        for key in matches:
            domains[key] = True

    core = any(
        _is_core(path, per_path_domains.get(path, set()))
        for path in clean_paths
    )
    flags = _risk_flags(clean_paths)

    unsafe = []
    domain_cfg = payload.get("domains") or {}
    for key, touched in domains.items():
        if not touched:
            continue
        status = str((domain_cfg.get(key) or {}).get("status") or "")
        if status != "active":
            unsafe.append(key)

    if unsafe:
        risk_tier = "blocked"
    elif flags["model"] or core:
        risk_tier = "high"
    elif any(flags.values()) or any(domains.values()):
        risk_tier = "medium"
    else:
        risk_tier = "low"

    return {
        **domains,
        "core": core,
        **flags,
        "unprotected_domains": unsafe,
        "risk_tier": risk_tier,
        "changed_count": len(clean_paths),
        "paths": clean_paths,
    }


def _git_changed_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _write_github_output(path: Path, result: dict) -> None:
    keys = (
        *DOMAIN_KEYS,
        "core",
        "ui",
        "api",
        "data",
        "model",
        "infra",
    )
    with path.open("a", encoding="utf-8") as fh:
        for key in keys:
            fh.write(f"{key}={'true' if result[key] else 'false'}\n")
        fh.write(
            "unprotected_domains="
            + ",".join(result["unprotected_domains"])
            + "\n"
        )
        fh.write(f"risk_tier={result['risk_tier']}\n")
        fh.write(f"changed_count={result['changed_count']}\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--paths-file")
    parser.add_argument("--github-output")
    parser.add_argument("--manual", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = _load_manifest()

    if args.manual:
        result = {
            **{key: (manifest["domains"][key]["status"] == "active") for key in DOMAIN_KEYS},
            "core": True,
            "ui": True,
            "api": True,
            "data": True,
            "model": True,
            "infra": True,
            "unprotected_domains": [],
            "risk_tier": "high",
            "changed_count": "manual",
            "paths": [],
        }
    elif args.paths_file:
        paths = Path(args.paths_file).read_text(encoding="utf-8").splitlines()
        result = classify(paths, manifest)
    else:
        if not args.base or not args.head:
            raise SystemExit("--base and --head are required unless --manual/--paths-file is used")
        result = classify(_git_changed_paths(args.base, args.head), manifest)

    print("DEVSYSTEM_CHANGE_CLASSIFICATION")
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.github_output:
        _write_github_output(Path(args.github_output), result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
