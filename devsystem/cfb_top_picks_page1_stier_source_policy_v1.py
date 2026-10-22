"""Static policy certification for CFB Top Picks Page 1 S-tier V1."""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "1ee4c7ea027f3e2c4c8e88c26653343adb7d1aff"
ALLOWED = {
    "sports_api/api/cfb_top_picks_page1_v1.py",
    "cfb_top_picks_page_v12.py",
    "streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py",
    "kyre_sports_api_vercel_v1.py",
    "tests/test_api2_cfb_top_picks_page1_stier_v1.py",
    "devsystem/cfb_top_picks_page1_stier_source_policy_v1.py",
    "devsystem/runless_proof_plans/api2-cfb-top-picks-page1-stier-v1.json",
}
FROZEN_LEGACY = {
    "cfb_top_picks_engine_v1.py",
    "cfb_top_picks_page_v11.py",
    "cfb_top_picks_page_v10.py",
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
    print("CFB_TOP_PICKS_SCOPE_DIFF_DEFERRED_TO_RUNLESS_STEP2A_PREFLIGHT")
    return None


def main() -> int:
    failures: list[str] = []
    api = _text("sports_api/api/cfb_top_picks_page1_v1.py")
    page = _text("cfb_top_picks_page_v12.py")
    terminal = _text("streamlit_memory_lazy_router_universal_runtime_v5_nba_pra_page1_v1.py")
    gateway = _text("kyre_sports_api_vercel_v1.py")

    # The customer-facing page may communicate only with the Kyre gateway.
    page_low = page.casefold()
    for token in ("sportsgameodds", "sgo", "espn"):
        if token in page_low:
            failures.append(f"forbidden_page_reference:{token}")
    for token in ("cfb_top_picks_engine_v1", "cfb_top_picks_page_v11", "cfb_top_picks_page_v10"):
        if token in page:
            failures.append(f"legacy_top_picks_runtime:{token}")
    for token in (
        'PAGE1_ENDPOINT = "/api/v1/cfb/top-picks/page1"',
        "KYRE_SPORTS_API_BASE_URL",
        "Market Edge", "Best Price", "WHY THIS PICK", "SLATE INTEGRITY",
    ):
        if token not in page:
            failures.append(f"missing_page_contract:{token}")

    # The API owns canonical identity, exact quote selection, and null-safe edge.
    for token in (
        'router = APIRouter(prefix="/api/v1/cfb/top-picks"',
        'return _clean(game.get("game_id") or game.get("identity_key"))',
        "def rank_moneyline_games(", "def _best_quote(",
        '"consensus_averaging": False', '"fabrication": False', '"null_to_zero": False',
        '"application_gateway": "Kyre Sports API"',
    ):
        if token not in api:
            failures.append(f"missing_api_contract:{token}")
    if "cfb_top_picks_engine_v1" in api:
        failures.append("legacy_engine_imported_by_api")
    if "average(" in api.casefold() or "statistics.mean" in api.casefold():
        failures.append("sportsbook_prices_must_not_be_averaged")
    if "game.get(\"espn_event_id\")" in api.casefold():
        failures.append("legacy_event_identity_reintroduced")

    if 'route.sport_id == "cfb" and route.market_id == "top-picks"' not in terminal:
        failures.append("terminal_route_missing")
    if 'importlib.import_module("cfb_top_picks_page_v12")' not in terminal:
        failures.append("terminal_not_pointing_to_v12")
    for token in (
        "import sports_api.api.cfb_top_picks_page1_v1 as cfb_top_picks_page1_module",
        "cfb_top_picks_page1_router = cfb_top_picks_page1_module.router",
        "app.include_router(cfb_top_picks_page1_router)",
        '"cfb_top_picks_page1": True',
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
        touched_frozen = sorted(set(changed) & FROZEN_LEGACY)
        if touched_frozen:
            failures.append("frozen_artifact_mutated:" + ",".join(touched_frozen))

    if failures:
        print("CFB_TOP_PICKS_PAGE1_STIER_SOURCE_POLICY_V1_RED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("CFB_TOP_PICKS_PAGE1_STIER_SOURCE_POLICY_V1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
