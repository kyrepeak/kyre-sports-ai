from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "wnba_pra_repair_v1_step6_completeness_sweep.py"
STEP2 = ROOT / "wnba_pra_repair_v1_step2_team_identity.py"
STEP3 = ROOT / "wnba_pra_repair_v1_step3_data.py"


def main() -> int:
    source = ENGINE.read_text(encoding="utf-8")
    step2 = STEP2.read_text(encoding="utf-8")
    step3 = STEP3.read_text(encoding="utf-8")

    checks = {
        "engine_exists": ENGINE.exists(),
        "verification_only_contract": "Verification-only" in source,
        "no_network_fetch": "requests." not in source and "httpx." not in source and "KyreWNBAAPIClient" not in source,
        "no_streamlit_runtime": "import streamlit" not in source,
        "game_gate": "def audit_game" in source,
        "player_gate": "def audit_player" in source,
        "card_gate": "def audit_card" in source,
        "full_sweep": "def sweep_game" in source,
        "data_limited_fail_closed": 'source == "DATA LIMITED"' in source and 'direction == "N/A"' in source,
        "step2_registry_present": "TEAM_BY_ID" in step2,
        "step3_registry_present": "TEAM_REGISTRY" in step3,
        "no_projection_mutation": "projected_pra =" not in source and "projected_pts =" not in source,
        "no_market_math": "SPORTSBOOK_PROJECTION_INFLUENCE" not in source,
    }
    ok = all(checks.values())
    print(json.dumps({"status": "GREEN" if ok else "FAIL", "checks": checks}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
