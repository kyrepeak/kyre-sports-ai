"""Monster Speed V3 Step 2 — deployment/cache separation guard."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "requirements.txt"
FINGERPRINT = ROOT / "devsystem/root_requirements_fingerprint_v1.txt"
ACTIVE_WORKFLOWS = (
    ROOT / ".github/workflows/devsystem-targeted-ci.yml",
    ROOT / ".github/workflows/devsystem-production-verification-v5.yml",
    ROOT / ".github/workflows/devsystem-cache-seed-v1.yml",
)

class CacheSplitFailure(RuntimeError):
    pass

def _install_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

def check_repository() -> dict[str, object]:
    actual = _install_lines(REQ)
    expected = _install_lines(FINGERPRINT)
    failures: list[str] = []
    if actual != expected:
        failures.append("root dependency fingerprint does not match install-bearing requirements.txt lines")

    raw_cache_token = "hashFiles('requirements.txt'"
    fingerprint_token = "devsystem/root_requirements_fingerprint_v1.txt"
    for path in ACTIVE_WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        if raw_cache_token in text:
            failures.append(f"{path.relative_to(ROOT)} still keys cache from raw requirements.txt")
        if fingerprint_token not in text:
            failures.append(f"{path.relative_to(ROOT)} missing normalized dependency fingerprint")

    if failures:
        raise CacheSplitFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "root_dependencies": len(actual),
        "active_workflows": len(ACTIVE_WORKFLOWS),
        "comment_only_redeploy_invalidates_cache": False,
        "dependency_change_invalidates_cache": True,
    }

def main() -> int:
    result = check_repository()
    print("MONSTER_SPEED_V3_STEP2_DEPLOY_CACHE_SPLIT_GREEN")
    print("MONSTER_SPEED_V3_STEP2_REQUIREMENTS_COMMENTS_NO_LONGER_BUST_ACTIVE_CACHES")
    print(result)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
