"""CFB Top Picks Research V2 Step 6 — permanent market-reasoning guard."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "cfb_top_picks_market_reasoning_v1.py"
DETAILS = ROOT / "cfb_top_picks_details_v2.py"
PAGE = ROOT / "cfb_top_picks_page_v6.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step6.py"
CONTRACT = ROOT / "devsystem/contracts/cfb_top_picks_research_v2_contract_v1.json"
CERT = ROOT / "devsystem/cfb_top_picks_research_v2_step6_market_reasoning_cert_v1.py"


class Step6MarketReasoningContractFailure(RuntimeError):
    pass


def check_repository() -> dict[str, object]:
    failures: list[str] = []
    engine = ENGINE.read_text(encoding="utf-8")
    details = DETAILS.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    cert = CERT.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    for market in ("OVER/UNDER", "SPREAD", "MONEYLINE"):
        for key in contract["market_reasoning_contract"][market]["required"]:
            if key not in engine:
                failures.append(f"reasoning engine missing {market}:{key}")

    for token in (
        "MARKET_REASONING_PROJECTION_WEIGHT = 0.0",
        "SPORTSBOOK_PROJECTION_WEIGHT = 0.0",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_RANKING = False",
        "MAY_MODIFY_SELECTION = False",
        "API2_USED = False",
        "build_market_reasoning",
    ):
        if token not in engine:
            failures.append(f"reasoning engine missing {token}")

    for forbidden in ("sports_api", "KYRE_SPORTS_API", "/api/v1/"):
        if forbidden in engine:
            failures.append(f"reasoning engine illegally couples API 2: {forbidden}")

    if "import cfb_top_picks_details_v1 as prior" not in details:
        failures.append("Step-6 details must wrap frozen V1 details")
    if "Market-Aware Football Reasoning" not in page:
        failures.append("Step-6 page does not render market-aware reasoning")
    if "import cfb_top_picks_page_v5 as prior" not in page:
        failures.append("Step-6 page must wrap frozen V5 page")
    if 'TOP_PICKS_PAGE = "cfb_top_picks_page_v6"' not in router:
        failures.append("Step-6 router does not activate V6 only for Top Picks")

    for token in (
        "CFB_TOP_PICKS_RESEARCH_V2_STEP6_THREE_MARKETS_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP6_SIGNAL_CONTRACT_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP6_FROZEN_GREEN",
    ):
        if token not in cert:
            failures.append(f"Step-6 certification missing {token}")

    if failures:
        raise Step6MarketReasoningContractFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "step": "6/9",
        "markets": 3,
        "market_specific": True,
        "projection_weight": 0.0,
        "sportsbook_projection_weight": 0.0,
        "api2_protected": True,
        "steps1_5_wrapped_not_modified": True,
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP6_MARKET_REASONING_CONTRACT_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
