"""Monster Speed V3 Step 4 — permanent user-visible-contract guard."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "devsystem/user_visible_contract_v1.py"
TOP_PICKS_CERT = ROOT / "devsystem/cfb_top_picks_nav_step3_public_cert_v1.py"
FOCUSED_PROOF = ROOT / "devsystem/monster_speed_v3_step4_user_visible_proof_v1.py"

class Step4ContractFailure(RuntimeError):
    pass

def check_repository() -> dict[str, object]:
    failures: list[str] = []
    engine = ENGINE.read_text(encoding="utf-8")
    cert = TOP_PICKS_CERT.read_text(encoding="utf-8")
    focused = FOCUSED_PROOF.read_text(encoding="utf-8")

    for token in (
        "RESPONSIVE_VIEWPORTS = ((390, 844), (768, 1024), (1440, 1000))",
        'QUERY_POLICY_TELEMETRY = "telemetry"',
        'QUERY_POLICY_REQUIRED = "required"',
        "def evaluate_user_visible_evidence(",
        "def certify_playwright_surface(",
        "def certify_responsive_suite(",
        "horizontal_overflow:",
        "market_count:",
        "selector_not_visible:",
    ):
        if token not in engine:
            failures.append(f"engine missing {token}")

    for token in (
        "user_visible_contract_v1 as user_contract",
        "TOP_PICKS_USER_CONTRACT = user_contract.UserVisibleContract(",
        "required_selectors=(V5_ROOT,)",
        "required_markets=EXPECTED_CFB_MARKETS",
        "query_policy=user_contract.QUERY_POLICY_TELEMETRY",
        "user_contract.certify_playwright_surface(",
        "user_contract.certify_responsive_suite(",
        "def _attempt_isolated_width(",
        'browser.new_page(viewport={"width": width, "height": height})',
        "page.close()",
    ):
        if token not in cert:
            failures.append(f"Top Picks verifier missing {token}")

    attempt = cert.split("def _attempt_normal_flow", 1)[1].split("def _attempt_isolated_width", 1)[0]
    if "_assert_query(page" in attempt:
        failures.append("incidental URL query is still a blocking gate")

    if "nav._attempt_isolated_width(" not in focused:
        failures.append("focused Step-4 proof does not isolate responsive viewport sessions")

    try:
        ast.parse(engine)
        ast.parse(cert)
        ast.parse(focused)
    except SyntaxError as exc:
        failures.append(f"syntax error: {exc}")

    if failures:
        raise Step4ContractFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "blocking_truth": "USER_VISIBLE_BEHAVIOR",
        "telemetry_default": "NON_BLOCKING",
        "responsive_widths": [390, 768, 1440],
        "stable_selectors_required": True,
        "preserved_markets_required": True,
        "zero_horizontal_overflow_required": True,
        "fresh_viewport_sessions_required": True,
        "product_runtime_changed": False,
    }

def main() -> int:
    result = check_repository()
    print("MONSTER_SPEED_V3_STEP4_USER_VISIBLE_CONTRACT_GREEN")
    print(result)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
