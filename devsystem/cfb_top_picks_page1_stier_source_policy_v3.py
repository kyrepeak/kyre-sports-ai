"""Static certification for the CFB Top Picks Page 1 S-tier V3 successor."""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "472c458d66df7c2bc7caff7dad008bdd4b2cdce1"
ALLOWED = {
    "app.py",
    "cfb_top_picks_page_v14.py",
    "devsystem/cfb_top_picks_page1_stier_source_policy_v3.py",
    "devsystem/runless_proof_plans/api2-cfb-top-picks-page1-stier-v3.json",
    "kyre_sports_api_vercel_v1.py",
    "sports_api/api/cfb_top_picks_page1_v3.py",
    "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v3.py",
    "tests/test_api2_cfb_top_picks_page1_stier_v3.py",
}
FROZEN_V2 = {
    "sports_api/api/cfb_top_picks_page1_v2.py",
    "cfb_top_picks_page_v13.py",
    "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v2.py",
    "tests/test_api2_cfb_top_picks_page1_stier_v2.py",
    "devsystem/cfb_top_picks_page1_stier_source_policy_v2.py",
    "devsystem/runless_proof_plans/api2-cfb-top-picks-page1-stier-v2.json",
}


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _changed_paths() -> list[str] | None:
    base_exists = subprocess.run(
        ["git", "cat-file", "-e", f"{BASE_SHA}^{{commit}}"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0
    if base_exists:
        return subprocess.check_output(
            ["git", "diff", "--name-only", BASE_SHA, "--"], cwd=ROOT, text=True
        ).splitlines()
    shallow = subprocess.check_output(
        ["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, text=True
    ).strip().lower() == "true"
    if not shallow:
        raise RuntimeError("BASE_SHA_UNAVAILABLE_IN_NON_SHALLOW_CHECKOUT")
    print("CFB_TOP_PICKS_V3_SCOPE_DIFF_DEFERRED_TO_RUNLESS_STEP2A_PREFLIGHT")
    return None


def main() -> int:
    failures: list[str] = []
    api = _text("sports_api/api/cfb_top_picks_page1_v3.py")
    page = _text("cfb_top_picks_page_v14.py")
    overlay = _text("streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v3.py")
    app = _text("app.py")
    gateway = _text("kyre_sports_api_vercel_v1.py")

    for token in ("sportsgameodds", "sgo", "espn"):
        if token in page.casefold() or token in api.casefold():
            failures.append(f"forbidden_v3_reference:{token}")

    for token in (
        'PAGE1_ENDPOINT = "/api/v3/cfb/top-picks/page1"',
        "TOP 10 GAME PICKS", "TOP 10 PLAYER PROPS", "HIT PROBABILITY",
        "ODDS", "RECORD", "GAME TIME", "PLAYER ID", "team-logo",
    ):
        if token not in page:
            failures.append(f"missing_simple_page_contract:{token}")
    for token in (
        "WHY THIS PICK", "BOOK COMPARISON", "LINE MOVEMENT", "SOURCE HEALTH",
        "MATCHUP SNAPSHOT", "AVAILABILITY",
    ):
        if token in page:
            failures.append(f"deep_module_leaked_to_page1:{token}")

    for token in (
        'APIRouter(prefix="/api/v3/cfb/top-picks"',
        '"application_gateway": "Kyre Sports API"',
        '"game_picks_10_of_10"', '"player_props_10_of_10"',
        '"FanDuel"', '"The Odds API"',
        '"consensus_averaging": False', '"null_to_zero": False',
        '"fabrication": False', "rank_game_candidates", "rank_player_props",
        "same_book_devig_probability",
    ):
        if token not in api:
            failures.append(f"missing_api_contract:{token}")
    if "statistics.mean" in api.casefold() or "average(" in api.casefold():
        failures.append("sportsbook_lines_must_not_be_averaged")

    if 'importlib.import_module("cfb_top_picks_page_v14")' not in overlay:
        failures.append("overlay_not_pointing_to_v14")
    if "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v3" not in app:
        failures.append("app_not_pointing_to_v3_overlay")
    for token in (
        "cfb_top_picks_page1_v2",
        "cfb_top_picks_page1_v3",
        '"cfb_top_picks_page1_v3": True',
    ):
        if token not in gateway:
            failures.append(f"gateway_registration_missing:{token}")

    try:
        changed = _changed_paths()
    except Exception as exc:
        failures.append(f"scope_diff_unavailable:{type(exc).__name__}")
        changed = []
    if changed is not None:
        unexpected = sorted(set(changed) - ALLOWED)
        if unexpected:
            failures.append("out_of_scope:" + ",".join(unexpected))
        touched_frozen = sorted(set(changed) & FROZEN_V2)
        if touched_frozen:
            failures.append("frozen_v2_mutated:" + ",".join(touched_frozen))

    if failures:
        print("CFB_TOP_PICKS_PAGE1_STIER_SOURCE_POLICY_V3_RED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("CFB_TOP_PICKS_PAGE1_STIER_SOURCE_POLICY_V3_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
