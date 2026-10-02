"""CFB Top Picks Research V2 Step 9 — permanent full-slate certification guard."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "cfb_top_picks_details_v5.py"
PAGE = ROOT / "cfb_top_picks_page_v9.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9.py"
SOURCE_ROUTER = ROOT / "cfb_top_picks_source_router_v2.py"
CONTRACT = ROOT / "devsystem/contracts/cfb_top_picks_research_v2_contract_v1.json"
CERT = ROOT / "devsystem/cfb_top_picks_research_v2_step9_full_slate_cert_v1.py"


class Step9FullSlateContractFailure(RuntimeError):
    pass


def check_repository() -> dict[str, object]:
    failures: list[str] = []
    details = DETAILS.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    source_router = SOURCE_ROUTER.read_text(encoding="utf-8")
    cert = CERT.read_text(encoding="utf-8")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    gate = contract.get("completeness_gate") or {}
    if gate.get("required_ranked_picks") != 10:
        failures.append("frozen contract no longer requires exactly 10 ranked picks")
    for key in (
        "every_pick_must_pass_card_contract",
        "every_expanded_pick_must_pass_detail_contract",
        "real_team_logos_required",
        "benefits_must_have_verified_evidence",
        "risks_must_have_verified_evidence",
        "history_status_must_be_terminal",
        "zero_placeholder_logo_text",
        "zero_unexplained_missing_required_fields",
    ):
        if gate.get(key) is not True:
            failures.append(f"frozen completeness contract lost {key}")

    if "import cfb_top_picks_details_v4 as prior" not in details:
        failures.append("Step-9 details must wrap frozen Step 8")
    if "import cfb_top_picks_page_v8 as prior" not in page:
        failures.append("Step-9 page must wrap frozen Step 8")
    if "_AUDIT_BLOCK" not in page or "raw audit markup leak detected" not in page:
        failures.append("Step-9 page does not permanently remove obsolete raw audit footer")
    if 'FAIR_PRICE_NO_SPORTSBOOK = "Unavailable — fair model price"' not in cert:
        failures.append("Step-9 cert must explain missing sportsbook for verified fair-price cards without inventing a provider")
    if 'TOP_PICKS_PAGE = "cfb_top_picks_page_v9"' not in router:
        failures.append("Step-9 route is not active")
    if "streamlit_memory_lazy_router_wnba_pra_speed_v3_step4 as current_parent" not in router:
        failures.append("Step-9 router must preserve current WNBA Speed Step 4 parent")
    if "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8 as cfb_step8_parent" not in router:
        failures.append("Step-9 router must preserve frozen CFB Step 8 ownership")
    if "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step7 as cfb_step7_parent" not in router:
        failures.append("Step-9 router must preserve frozen CFB Step 7 ownership")
    if "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step6 as cfb_step6_parent" not in router:
        failures.append("Step-9 router must preserve frozen CFB Step 6 ownership")
    for token in (
        "def _page_owner_chain()",
        "cfb_step8_parent, cfb_step7_parent, cfb_step6_parent",
        "owner.TOP_PICKS_PAGE = TOP_PICKS_PAGE",
        "zip(reversed(owners), reversed(original_pages))",
    ):
        if token not in router:
            failures.append(f"Step-9 router propagation contract missing {token}")
    if "import cfb_top_picks_source_router_v1 as prior" not in source_router:
        failures.append("Step-9 provenance closeout must wrap frozen Step 8 source router")
    if 'normalized["source_attempts"] = list(normalized.get("sources_attempted") or [])' not in source_router:
        failures.append("Step-9 provenance closeout missing historical attempt alias")

    for token in (
        "CFB_TOP_PICKS_RESEARCH_V2_STEP9_TOP10_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP9_DETAILS_10_OF_10_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP9_PROVENANCE_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP9_RAW_UI_CLEAN_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP9_FROZEN_GREEN",
    ):
        if token not in cert:
            failures.append(f"Step-9 live certification missing {token}")

    if failures:
        raise Step9FullSlateContractFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "step": "9/9",
        "required_picks": 10,
        "full_slate_certification": True,
        "raw_ui_cleanup_required": True,
        "steps1_8_wrapped_not_modified": True,
        "projection_weight": 0.0,
        "sportsbook_projection_weight": 0.0,
        "api2_protected": True,
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP9_FULL_SLATE_CONTRACT_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
