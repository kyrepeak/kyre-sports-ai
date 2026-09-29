"""Monster Speed V3 Step 6 — permanent exact-lock hot-cache guard."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_INTENT = ROOT / "requirements.txt"
BROWSER_INTENT = ROOT / "devsystem/browser_tooling_v1.txt"
ROOT_LOCK = ROOT / "requirements.lock"
BROWSER_LOCK = ROOT / "devsystem/browser_requirements.lock"

ACTIVE_BROWSER_OWNERS = (
    ROOT / ".github/workflows/devsystem-targeted-ci.yml",
    ROOT / ".github/workflows/devsystem-cache-seed-v1.yml",
    ROOT / ".github/workflows/devsystem-production-verification-v5.yml",
    ROOT / ".github/workflows/monster-speed-v3-step4-user-visible-contract-v1.yml",
    ROOT / ".github/workflows/monster-speed-v3-step6-hot-cache-v1.yml",
)

EXPECTED_KEY = "hashFiles('requirements.lock', 'devsystem/browser_requirements.lock')"


class Step6HotCacheFailure(RuntimeError):
    pass


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _lock_map(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise Step6HotCacheFailure(f"{path.relative_to(ROOT)} contains non-exact lock entry: {line}")
        name, version = line.split("==", 1)
        if not name.strip() or not version.strip():
            raise Step6HotCacheFailure(f"{path.relative_to(ROOT)} contains malformed lock entry: {line}")
        key = _norm(name)
        if key in result:
            raise Step6HotCacheFailure(f"{path.relative_to(ROOT)} duplicates package {name}")
        result[key] = version.strip()
    return result


def _version_tuple(value: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", value)
    return tuple(int(x) for x in nums[:4]) or (0,)


def _intent_specs(path: Path) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?(.*)$", line)
        if not match:
            raise Step6HotCacheFailure(f"unsupported dependency intent: {line}")
        specs.append((_norm(match.group(1)), match.group(2).strip()))
    return specs


def _satisfies(version: str, spec: str) -> bool:
    if not spec:
        return True
    if "," in spec:
        return all(_satisfies(version, part.strip()) for part in spec.split(","))
    if spec.startswith("=="):
        return version == spec[2:].strip()
    current = _version_tuple(version)
    if spec.startswith(">="):
        return current >= _version_tuple(spec[2:].strip())
    if spec.startswith("<"):
        return current < _version_tuple(spec[1:].strip())
    if spec.startswith("~="):
        lower_raw = spec[2:].strip()
        lower = _version_tuple(lower_raw)
        parts = [int(x) for x in re.findall(r"\d+", lower_raw)]
        if len(parts) <= 2:
            upper = (parts[0] + 1, 0)
        else:
            upper = (parts[0], parts[1] + 1, 0)
        return current >= lower and current < upper
    raise Step6HotCacheFailure(f"unsupported dependency constraint: {spec}")


def _validate_intent(path: Path, locked: dict[str, str]) -> None:
    for name, spec in _intent_specs(path):
        version = locked.get(name)
        if version is None:
            raise Step6HotCacheFailure(f"{path.relative_to(ROOT)} package {name} missing from lock")
        if not _satisfies(version, spec):
            raise Step6HotCacheFailure(
                f"{path.relative_to(ROOT)} package {name} lock {version} does not satisfy {spec}"
            )


def check_repository() -> dict[str, object]:
    failures: list[str] = []
    root_lock = _lock_map(ROOT_LOCK)
    browser_lock = _lock_map(BROWSER_LOCK)

    try:
        _validate_intent(ROOT_INTENT, root_lock)
        _validate_intent(BROWSER_INTENT, browser_lock)
    except Step6HotCacheFailure as exc:
        failures.append(str(exc))

    for name, version in root_lock.items():
        if browser_lock.get(name) != version:
            failures.append(f"browser lock does not preserve root lock package {name}=={version}")

    for path in ACTIVE_BROWSER_OWNERS:
        text = path.read_text(encoding="utf-8")
        keys = [
            line.strip()
            for line in text.splitlines()
            if "key: devsystem-browser-stack-" in line
        ]
        if not keys:
            failures.append(f"{path.relative_to(ROOT)} missing shared browser cache key")
            continue
        for key in keys:
            if EXPECTED_KEY not in key:
                failures.append(f"{path.relative_to(ROOT)} browser key is not exact-lock-owned")
            for forbidden in (
                "requirements.txt",
                "root_requirements_fingerprint_v1.txt",
                "browser_tooling_v1.txt",
                "browser_cache_epoch_v1.txt",
            ):
                if forbidden in key:
                    failures.append(f"{path.relative_to(ROOT)} browser key still depends on {forbidden}")

        exact_install = (
            ".venv-browser-qa/bin/python -m pip install "
            "--disable-pip-version-check -q -r devsystem/browser_requirements.lock"
        )
        if exact_install not in text:
            failures.append(f"{path.relative_to(ROOT)} cache miss does not install exact browser lock")
        if re.search(
            r"\.venv-browser-qa/bin/python -m pip install[^\n]+-r "
            r"(requirements\.txt|devsystem/browser_tooling_v1\.txt)",
            text,
        ):
            failures.append(f"{path.relative_to(ROOT)} still installs floating browser dependencies")
        if ".venv-browser-qa/bin/python -m playwright install chromium" not in text:
            failures.append(f"{path.relative_to(ROOT)} missing Chromium prebuild")

    seed = (ROOT / ".github/workflows/devsystem-cache-seed-v1.yml").read_text(encoding="utf-8")
    for token in ("requirements.lock", "devsystem/browser_requirements.lock"):
        if token not in seed:
            failures.append(f"cache seed missing watched lock {token}")

    production = (ROOT / ".github/workflows/devsystem-production-verification-v5.yml").read_text(encoding="utf-8")
    for token in ("requirements.lock", "devsystem/browser_requirements.lock"):
        if token not in production:
            failures.append(f"production V5 missing lock ownership {token}")

    step6 = (ROOT / ".github/workflows/monster-speed-v3-step6-hot-cache-v1.yml").read_text(encoding="utf-8")
    for token in (
        "needs: seed-hot-stack",
        "steps.hot-cache.outputs.cache-hit",
        'MONSTER_SPEED_V3_STEP6_HOT_CACHE_HIT_GREEN',
        'MONSTER_SPEED_V3_STEP6_FROZEN_GREEN',
    ):
        if token not in step6:
            failures.append(f"Step-6 proof missing {token}")

    if failures:
        raise Step6HotCacheFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "root_locked_packages": len(root_lock),
        "browser_locked_packages": len(browser_lock),
        "active_browser_cache_owners": len(ACTIVE_BROWSER_OWNERS),
        "cache_identity": "OS + PYTHON + EXACT_LOCKS_ONLY",
        "requirements_comments_invalidate_browser_cache": False,
        "deployment_markers_invalidate_browser_cache": False,
        "browser_cache_epoch_invalidate_browser_cache": False,
        "cache_miss_installs_exact_lock": True,
        "hot_cache_hit_required": True,
        "product_runtime_changed": False,
    }


def main() -> int:
    result = check_repository()
    print("MONSTER_SPEED_V3_STEP6_EXACT_LOCK_CACHE_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
