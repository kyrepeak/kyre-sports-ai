"""CFB Top Picks Research V2 Step 7 — permanent Benefits/Risks guard."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "cfb_top_picks_benefits_risks_v1.py"
DETAILS = ROOT / "cfb_top_picks_details_v3.py"
PAGE = ROOT / "cfb_top_picks_page_v7.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step7.py"
CONTRACT = ROOT / "devsystem/contracts/cfb_top_picks_research_v2_contract_v1.json"
CERT = ROOT / "devsystem/cfb_top_picks_research_v2_step7_benefits_risks_cert_v1.py"


class Step7BenefitsRisksContractFailure(RuntimeError):
    pass


def check_repository() -> dict[str, object]:
    failures: list[str] = []
    engine = ENGINE.read_text(encoding="utf-8")
    details = DETAILS.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    cert = CERT.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    gate = contract.get("completeness_gate") or {}
    if gate.get("benefits_must_have_verified_evidence") is not True:
        failures.append("frozen contract no longer requires verified benefits")
    if gate.get("risks_must_have_verified_evidence") is not True:
        failures.append("frozen contract no longer requires verified risks")

    for token in (
        "BENEFITS_RISKS_PROJECTION_WEIGHT = 0.0",
        "SPORTSBOOK_PROJECTION_WEIGHT = 0.0",
        "MAY_MODIFY_PROBABILITY = False",
        "MAY_MODIFY_RANKING = False",
        "MAY_MODIFY_SELECTION = False",
        "API2_USED = False",
        "build_benefits_risks",
        "football_benefit_count",
        "football_risk_count",
    ):
        if token not in engine:
            failures.append(f"Step-7 engine missing {token}")

    for forbidden in ("sports_api", "KYRE_SPORTS_API", "/api/v1/"):
        if forbidden in engine:
            failures.append(f"Step-7 engine illegally couples API 2: {forbidden}")

    if "import cfb_top_picks_details_v2 as prior" not in details:
        failures.append("Step-7 details must wrap frozen Step-6 details")
    if "import cfb_top_picks_page_v6 as prior" not in page:
        failures.append("Step-7 page must wrap frozen Step-6 page")
    if "<h4>Benefits</h4>" not in page or "<h4>Risks</h4>" not in page:
        failures.append("Step-7 page must render Benefits and Risks")
    if 'TOP_PICKS_PAGE = "cfb_top_picks_page_v7"' not in router:
        failures.append("Step-7 router does not activate V7 only for Top Picks")
    if "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step6 as prior" not in router:
        failures.append("Step-7 router must delegate through frozen Step 6")

    for token in (
        "CFB_TOP_PICKS_RESEARCH_V2_STEP7_THREE_MARKETS_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP7_VERIFIED_EVIDENCE_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP7_FROZEN_GREEN",
    ):
        if token not in cert:
            failures.append(f"Step-7 certification missing {token}")

    if failures:
        raise Step7BenefitsRisksContractFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "step": "7/9",
        "verified_benefits_required": True,
        "verified_risks_required": True,
        "projection_weight": 0.0,
        "sportsbook_projection_weight": 0.0,
        "api2_protected": True,
        "steps1_6_wrapped_not_modified": True,
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP7_BENEFITS_RISKS_CONTRACT_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
