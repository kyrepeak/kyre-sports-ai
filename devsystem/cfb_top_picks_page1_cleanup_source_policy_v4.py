"""Static certification for CFB Top Picks Page 1 cleanup V4."""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "0506bc838118eb6a429eacdf1e3c73089ce63bdf"
ALLOWED = {
    "app.py",
    "cfb_top_picks_page_v15.py",
    "devsystem/cfb_top_picks_page1_cleanup_source_policy_v4.py",
    "devsystem/runless_proof_plans/api2-cfb-top-picks-page1-cleanup-v4.json",
    "kyre_sports_api_vercel_v1.py",
    "sports_api/api/cfb_top_picks_page1_v4.py",
    "sports_api/collectors/cfb_top_picks_identity_v1.py",
    "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v4.py",
    "tests/test_api2_cfb_top_picks_page1_cleanup_v4.py",
}
FROZEN_V3 = {
    "sports_api/api/cfb_top_picks_page1_v3.py",
    "cfb_top_picks_page_v14.py",
    "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v3.py",
    "tests/test_api2_cfb_top_picks_page1_stier_v3.py",
}


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    page = text("cfb_top_picks_page_v15.py")
    api = text("sports_api/api/cfb_top_picks_page1_v4.py")
    identity = text("sports_api/collectors/cfb_top_picks_identity_v1.py")
    overlay = text("streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v4.py")

    if "/api/v4/cfb/top-picks/page1" not in page or 'prefix="/api/v4/cfb/top-picks"' not in api:
        failures.append("v4_route_contract_missing")
    if "cfb_top_picks_page_v15" not in overlay:
        failures.append("v15_overlay_missing")
    if "NCAA_WIN_PCT_URL" not in identity or "Official team athletics roster" not in identity:
        failures.append("official_identity_sources_missing")

    low = (page + identity).casefold()
    if "espn.com" in low or "sportsgameodds" in low:
        failures.append("forbidden_provider_path_present")
    if "why this pick" in page.casefold() or "why:" in page.casefold():
        failures.append("page1_why_content_present")
    for token in ("tp15-logo", "player_headshot", "player_team_logo", "Tap for full analysis", "dedent"):
        if token not in page:
            failures.append(f"page_cleanup_token_missing:{token}")

    changed = subprocess.check_output(["git", "diff", "--name-only", BASE_SHA, "--"], cwd=ROOT, text=True).splitlines()
    outside = sorted(set(changed) - ALLOWED)
    frozen = sorted(set(changed) & FROZEN_V3)
    if outside:
        failures.append("scope_outside_allowed:" + ",".join(outside))
    if frozen:
        failures.append("frozen_v3_mutated:" + ",".join(frozen))

    if failures:
        print("CFB_TOP_PICKS_PAGE1_CLEANUP_V4_SOURCE_POLICY_RED")
        for item in failures:
            print(item)
        return 1
    print("CFB_TOP_PICKS_PAGE1_CLEANUP_V4_SOURCE_POLICY_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
