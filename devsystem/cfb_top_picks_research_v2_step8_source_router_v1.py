"""CFB Top Picks Research V2 Step 8 — permanent source-router guard."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "cfb_top_picks_source_router_v1.py"
DETAILS = ROOT / "cfb_top_picks_details_v4.py"
PAGE = ROOT / "cfb_top_picks_page_v8.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8.py"
CONTRACT = ROOT / "devsystem/contracts/cfb_top_picks_research_v2_contract_v1.json"
CERT = ROOT / "devsystem/cfb_top_picks_research_v2_step8_source_router_cert_v1.py"


class Step8SourceRouterContractFailure(RuntimeError):
    pass


def check_repository() -> dict[str, object]:
    failures: list[str] = []
    engine = ENGINE.read_text(encoding="utf-8")
    details = DETAILS.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    cert = CERT.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    provenance = contract.get("provenance_contract") or {}

    for key in (
        "no_source_loyalty", "every_material_fact_requires_source",
        "every_material_fact_requires_observed_at", "source_conflicts_must_be_recorded",
        "unsupported_values_must_not_be_invented", "fallback_to_other_sources_before_unavailable",
    ):
        if provenance.get(key) is not True:
            failures.append(f"frozen provenance contract lost {key}")
    if provenance.get("unit_of_work") != "DATA_FIELD":
        failures.append("unit of work is not DATA_FIELD")

    for token in (
        'UNIT_OF_WORK = "DATA_FIELD"', "NO_SOURCE_LOYALTY = True",
        "SOURCE_ROUTER_PROJECTION_WEIGHT = 0.0", "SPORTSBOOK_PROJECTION_WEIGHT = 0.0",
        "MAY_MODIFY_PROBABILITY = False", "MAY_MODIFY_RANKING = False",
        "MAY_MODIFY_SELECTION = False", "API2_USED = False",
        "FIELD_POLICIES", "build_source_freshness_audit",
    ):
        if token not in engine:
            failures.append(f"Step-8 engine missing {token}")

    for forbidden in ("sports_api", "KYRE_SPORTS_API", "/api/v1/"):
        if forbidden in engine:
            failures.append(f"Step-8 engine illegally couples API 2: {forbidden}")

    if "import cfb_top_picks_details_v3 as prior" not in details:
        failures.append("Step-8 details must wrap frozen Step 7")
    if "import cfb_top_picks_page_v7 as prior" not in page:
        failures.append("Step-8 page must wrap frozen Step 7")
    if "Sources + Freshness" not in page or "DATA_FIELD routing" not in page:
        failures.append("Step-8 page missing Sources + Freshness")
    if 'TOP_PICKS_PAGE = "cfb_top_picks_page_v8"' not in router:
        failures.append("Step-8 router not active")
    if "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step7 as prior" not in router:
        failures.append("Step-8 router must delegate through frozen Step 7")

    for token in (
        "CFB_TOP_PICKS_RESEARCH_V2_STEP8_DATA_FIELD_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP8_PROVENANCE_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP8_FROZEN_GREEN",
    ):
        if token not in cert:
            failures.append(f"Step-8 cert missing {token}")

    if failures:
        raise Step8SourceRouterContractFailure(" | ".join(failures))
    return {
        "status": "GREEN", "step": "8/9", "unit_of_work": "DATA_FIELD",
        "no_source_loyalty": True, "projection_weight": 0.0,
        "sportsbook_projection_weight": 0.0, "api2_protected": True,
        "steps1_7_wrapped_not_modified": True,
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP8_SOURCE_ROUTER_CONTRACT_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
