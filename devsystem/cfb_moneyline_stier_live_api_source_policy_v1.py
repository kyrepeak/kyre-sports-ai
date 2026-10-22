"""Static certification for the dedicated Kyre Sports API CFB Moneyline repair."""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "241547bd2dc1a43ad425670551a104a9fcc76e66"
ALLOWED = {
    "kyre_sports_api_vercel_v1.py",
    "pyproject.toml",
    "tests/test_monster_cfb_moneyline_stier_live_api_repair_v1.py",
    "devsystem/cfb_moneyline_stier_live_api_source_policy_v1.py",
    "devsystem/runless_proof_plans/monster-cfb-moneyline-stier-live-api-repair-v1.json",
}


def _changed_paths() -> list[str] | None:
    base_exists = subprocess.run(
        ["git", "cat-file", "-e", f"{BASE_SHA}^{{commit}}"], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0
    if base_exists:
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", BASE_SHA, "--"], cwd=ROOT, text=True
        ).splitlines()
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True
        ).splitlines()
        untracked = [
            path for path in untracked
            if "__pycache__/" not in path and not path.endswith(".pyc")
        ]
        return sorted(set(changed + untracked))
    shallow = subprocess.check_output(
        ["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, text=True
    ).strip().lower() == "true"
    if shallow:
        print("CFB_MONEYLINE_LIVE_API_SCOPE_DIFF_DEFERRED_TO_RUNLESS_STEP2A_PREFLIGHT")
        return None
    raise RuntimeError("BASE_SHA_UNAVAILABLE_IN_NON_SHALLOW_CHECKOUT")


def main() -> int:
    failures: list[str] = []
    entry_path = ROOT / "kyre_sports_api_vercel_v1.py"
    config_path = ROOT / "pyproject.toml"
    schedule_path = ROOT / "runless_v2/wnba_schedule_v1.py"
    dead_bridge = ROOT / "runless_v2/cfb_moneyline_public_v1.py"
    if not entry_path.is_file():
        failures.append("dedicated_gateway_entrypoint_missing")
        entry = ""
    else:
        entry = entry_path.read_text(encoding="utf-8")
    config = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    schedule = schedule_path.read_text(encoding="utf-8")

    for token in (
        "FastAPI",
        "sports_api.api.cfb_moneyline_page1_v1",
        "app.include_router(cfb_moneyline_router)",
        '"service": "Kyre Sports API"',
        '"direct_app_provider_fallback": False',
    ):
        if token not in entry:
            failures.append(f"missing_gateway_contract:{token}")
    if "[project]" not in config or 'name = "kyre-sports-api"' not in config:
        failures.append("vercel_python_project_metadata_missing")
    for dependency in ("fastapi", "streamlit", "requests", "httpx", "tzdata"):
        if f'"{dependency}' not in config:
            failures.append(f"vercel_runtime_dependency_missing:{dependency}")
    if 'entrypoint = "kyre_sports_api_vercel_v1:app"' not in config:
        failures.append("vercel_entrypoint_not_dedicated_gateway")
    for forbidden in ("espn", "espn bet", "sportsgameodds", "sgo", "runless_v2"):
        if forbidden in entry.casefold():
            failures.append(f"forbidden_gateway_dependency:{forbidden}")
    if "cfb_moneyline_public_v1" in schedule:
        failures.append("runless_schedule_still_hosts_cfb_moneyline")
    if dead_bridge.exists():
        failures.append("dead_runless_cfb_bridge_still_present")

    try:
        changed = _changed_paths()
    except Exception as exc:
        failures.append(f"scope_diff_unavailable:{type(exc).__name__}")
        changed = []
    if changed is not None:
        unexpected = sorted(set(changed) - ALLOWED)
        missing = sorted(ALLOWED - set(changed))
        if unexpected:
            failures.append("out_of_scope:" + ",".join(unexpected))
        if missing:
            failures.append("missing_expected_change:" + ",".join(missing))

    if failures:
        print("CFB_MONEYLINE_STIER_LIVE_API_SOURCE_POLICY_V1_RED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("CFB_MONEYLINE_STIER_LIVE_API_SOURCE_POLICY_V1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
