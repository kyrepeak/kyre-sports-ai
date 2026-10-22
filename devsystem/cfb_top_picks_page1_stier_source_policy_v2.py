"""Static policy certification for CFB Top Picks Page 1 S-tier V2 successor."""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "7b7677ecbb5eb982dd4e34ddd46570bac0056fa3"
ALLOWED = {
    "sports_api/api/cfb_top_picks_page1_v2.py",
    "cfb_top_picks_page_v13.py",
    "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v2.py",
    "app.py",
    "kyre_sports_api_vercel_v1.py",
    "tests/test_api2_cfb_top_picks_page1_stier_v2.py",
    "devsystem/cfb_top_picks_page1_stier_source_policy_v2.py",
    "devsystem/runless_proof_plans/api2-cfb-top-picks-page1-stier-v2.json",
}
FROZEN_V1 = {
    "sports_api/api/cfb_top_picks_page1_v1.py",
    "cfb_top_picks_page_v12.py",
    "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py",
    "tests/test_api2_cfb_top_picks_page1_stier_v1.py",
    "devsystem/cfb_top_picks_page1_stier_source_policy_v1.py",
    "devsystem/runless_proof_plans/api2-cfb-top-picks-page1-stier-v1.json",
    "cfb_top_picks_engine_v1.py",
    "cfb_moneyline_model_v1.py",
    "cfb_moneyline_final_v1.py",
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
    print("CFB_TOP_PICKS_V2_SCOPE_DIFF_DEFERRED_TO_RUNLESS_STEP2A_PREFLIGHT")
    return None


def main() -> int:
    failures: list[str] = []
    api = _text("sports_api/api/cfb_top_picks_page1_v2.py")
    page = _text("cfb_top_picks_page_v13.py")
    frozen_terminal = _text("streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py")
    overlay = _text("streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v2.py")
    app = _text("app.py")
    gateway = _text("kyre_sports_api_vercel_v1.py")

    for token in ("sportsgameodds", "sgo", "espn"):
        if token in page.casefold() or token in api.casefold():
            failures.append(f"forbidden_top_picks_reference:{token}")

    for token in (
        'PAGE1_ENDPOINT = "/api/v2/cfb/top-picks/page1"',
        "CONFIDENCE SCORE", "BOOK COMPARISON", "LINE MOVEMENT",
        "AVAILABILITY", "SOURCE HEALTH", "MATCHUP SNAPSHOT", "WHY THIS PICK",
        "High Confidence", "Market Movers", "team-logo",
    ):
        if token not in page:
            failures.append(f"missing_page_contract:{token}")

    for token in (
        'router = APIRouter(prefix="/api/v2/cfb/top-picks"',
        "def rank_moneyline_games_v2(",
        "def _reason_factors(",
        "def _book_prices(",
        "def _line_movement(",
        '"consensus_averaging": False',
        '"fabrication": False',
        '"null_to_zero": False',
        '"application_gateway": "Kyre Sports API"',
        '"sportsbook_projection_weight": 0.0',
    ):
        if token not in api:
            failures.append(f"missing_api_contract:{token}")
    if "average(" in api.casefold() or "statistics.mean" in api.casefold():
        failures.append("sportsbook_prices_must_not_be_averaged")

    if 'importlib.import_module("cfb_top_picks_page_v12")' not in frozen_terminal:
        failures.append("frozen_terminal_v12_contract_missing")
    if 'importlib.import_module("cfb_top_picks_page_v13")' in frozen_terminal:
        failures.append("frozen_terminal_mutated_to_v13")
    if 'importlib.import_module("cfb_top_picks_page_v13")' not in overlay:
        failures.append("successor_overlay_not_pointing_to_v13")
    if "streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_v2" not in app:
        failures.append("production_app_not_pointing_to_successor_overlay")

    for token in (
        "import sports_api.api.cfb_top_picks_page1_v2 as cfb_top_picks_page1_v2_module",
        "cfb_top_picks_page1_v2_router = cfb_top_picks_page1_v2_module.router",
        "app.include_router(cfb_top_picks_page1_v2_router)",
        '"cfb_top_picks_page1_v2": True',
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
        touched_frozen = sorted(set(changed) & FROZEN_V1)
        if touched_frozen:
            failures.append("frozen_v1_mutated:" + ",".join(touched_frozen))

    if failures:
        print("CFB_TOP_PICKS_PAGE1_STIER_SOURCE_POLICY_V2_RED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("CFB_TOP_PICKS_PAGE1_STIER_SOURCE_POLICY_V2_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
