"""Static certification for Monster CFB Moneyline S-tier Page 1 V1.

Full-history workspaces verify changed paths against BASE_SHA. Runless uses a
candidate-only shallow checkout; in that environment changed-path ownership is
already enforced by Runless Step 2A candidate-vs-main tree preflight, while this
module continues to certify all route/content/frozen-owner contracts.
"""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "2a28c385b27b075f28b0fcfe75050c1100b0006d"
ALLOWED = {
    "cfb_moneyline_clean_page_v7.py",
    "universal_runtime_v5_loader_v17.py",
    "sports_api/api/cfb_moneyline_page1_v1.py",
    "sports_api/collectors/cfb_fanduel_moneyline_v1.py",
    "sports_api/api/health.py",
    "tests/test_monster_cfb_moneyline_stier_page1_v1.py",
    "sports_api/tests/test_cfb_moneyline_page1_v1.py",
    "devsystem/cfb_moneyline_stier_page1_source_policy_v1.py",
    "devsystem/runless_proof_plans/monster-cfb-moneyline-stier-page1-v1.json",
}
FROZEN_PRESENTATION = {
    "cfb_moneyline_clean_page_v1.py", "cfb_moneyline_clean_page_v2.py",
    "cfb_moneyline_clean_page_v3.py", "cfb_moneyline_clean_page_v4.py",
    "cfb_moneyline_clean_page_v5.py", "cfb_moneyline_clean_page_v6.py",
}
FROZEN_MODEL = {"cfb_moneyline_model_v1.py", "cfb_moneyline_final_v1.py", "cfb_moneyline_slate_v1.py"}


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _changed_paths() -> list[str] | None:
    base_exists = subprocess.run(
        ["git", "cat-file", "-e", f"{BASE_SHA}^{{commit}}"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
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
    print("CFB_MONEYLINE_SCOPE_DIFF_DEFERRED_TO_RUNLESS_STEP2A_PREFLIGHT")
    return None


def main() -> int:
    failures: list[str] = []
    page = _text("cfb_moneyline_clean_page_v7.py")
    loader = _text("universal_runtime_v5_loader_v17.py")
    api = _text("sports_api/api/cfb_moneyline_page1_v1.py")
    collector = _text("sports_api/collectors/cfb_fanduel_moneyline_v1.py")
    health = _text("sports_api/api/health.py")

    route_text = (page + "\n" + api + "\n" + collector).casefold()
    for token in ("espn", "sportsgameodds", "espn bet"):
        if token in route_text:
            failures.append(f"forbidden_provider_reference:{token}")
    if "import requests" in page.casefold() or "import httpx" in page.casefold():
        failures.append("streamlit_must_not_call_external_providers_directly")
    for token in ("sportsbook.fanduel.com", "api.sportsbook.fanduel.com", "ncaa.com"):
        if token in page.casefold():
            failures.append(f"direct_provider_url_in_streamlit:{token}")

    for token in (
        "import cfb_moneyline_clean_page_v6 as prior",
        "FROZEN_MONEYLINE_OWNER = prior.FROZEN_MONEYLINE_OWNER",
        "FROZEN_RAW_MODEL = prior.FROZEN_RAW_MODEL",
        "FROZEN_FINAL_MODEL = prior.FROZEN_FINAL_MODEL",
        "SPORTSBOOK_PROJECTION_INFLUENCE = prior.SPORTSBOOK_PROJECTION_INFLUENCE",
        "MAY_MODIFY_PROJECTION = prior.MAY_MODIFY_PROJECTION",
        "market_value_verdict = prior.market_value_verdict",
        "KYRE_SPORTS_API_BASE_URL",
        'PAGE1_ENDPOINT = "/api/v1/cfb/moneyline/page1"',
        "st.segmented_control(", "st.tabs(", "DECISION COMMAND CENTER",
        "MODEL DRIVERS", "MATCHUP EDGE", "WIN PROBABILITY",
        "LIVE MONEYLINE MARKET", "ANALYTICS LAB",
    ):
        if token not in page:
            failures.append(f"missing_page_contract:{token}")
    for token in (
        "cfb_universal_next_slate_navigation_v1", "schedule_v3.load_with_diagnostics",
        "slate.analyze_game", "st.date_input(", "st.selectbox(",
    ):
        if token in page:
            failures.append(f"legacy_app_path_reintroduced:{token}")
    if page.count("st.expander(") > 1:
        failures.append("accordion_stack_reintroduced")
    if "or 0.0" in page:
        failures.append("missing_probability_must_not_become_zero")

    for token in (
        'router = APIRouter(prefix="/api/v1/cfb/moneyline"',
        "import cfb_schedule_v3 as ncaa_schedule", "import cfb_team_data_v1 as team_data",
        "import cfb_moneyline_model_v1 as raw_model", "import cfb_moneyline_final_v1 as final_model",
        "ncaa_schedule._fetch_ncaa_scoreboard_payload", "ncaa_schedule._official_scoreboard_games",
        '"application_gateway": "Kyre Sports API"',
        '"sportsbook_projection_weight": SPORTSBOOK_PROJECTION_INFLUENCE',
        '"consensus_averaging": False', '"null_to_zero": False',
        "_repair_ncaa_stats_profile", "stats-only repair",
    ):
        if token not in api:
            failures.append(f"missing_api_contract:{token}")
    for token in ("load_with_diagnostics", "games_for_date"):
        if token in api:
            failures.append(f"legacy_schedule_path_in_api:{token}")

    for token in (
        '"sportsbook": "FanDuel"', '"market": "moneyline"',
        "collect_the_odds_api_moneylines", "match_moneylines_to_ncaa_games", "THE_ODDS_API_KEY",
    ):
        if token not in collector:
            failures.append(f"missing_market_contract:{token}")
    if "average" in collector.casefold() or "consensus" in collector.casefold():
        failures.append("book_prices_must_remain_separate")

    if 'page = importlib.import_module("cfb_moneyline_clean_page_v7")' not in loader:
        failures.append("loader_not_pointing_to_v7")
    moneyline_block = loader.split('if route.sport_id == "cfb" and route.market_id == "moneyline":', 1)[-1]
    moneyline_block = moneyline_block.split("return prior.resolve_destination(route)", 1)[0]
    for token in ("cfb_universal_next_slate_navigation_v1", "cfb_schedule_v1"):
        if token in moneyline_block:
            failures.append(f"legacy_navigation_in_runtime:{token}")
    if 'cfb_moneyline_page1_v1 import router as cfb_moneyline_page1_router' not in health:
        failures.append("api_router_import_missing")
    if "router.routes.extend(cfb_moneyline_page1_router.routes)" not in health:
        failures.append("api_router_registration_missing")

    try:
        changed = _changed_paths()
    except Exception as exc:
        failures.append(f"scope_diff_unavailable:{type(exc).__name__}")
        changed = []
    if changed is not None:
        unexpected = sorted(set(changed) - ALLOWED)
        if unexpected:
            failures.append("out_of_scope:" + ",".join(unexpected))
        touched_frozen = sorted(set(changed) & (FROZEN_PRESENTATION | FROZEN_MODEL))
        if touched_frozen:
            failures.append("frozen_artifact_mutated:" + ",".join(touched_frozen))

    if failures:
        print("CFB_MONEYLINE_STIER_PAGE1_SOURCE_POLICY_V1_RED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("CFB_MONEYLINE_STIER_PAGE1_SOURCE_POLICY_V1_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
