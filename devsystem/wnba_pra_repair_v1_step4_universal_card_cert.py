"""WNBA PRA Repair V1 Step 4 — universal final PRA card source certification."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step4_universal_card.py"
CARD = ROOT / "wnba_pra_repair_v1_step4_final_card.py"
FROZEN_STEP3 = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py"
FROZEN_PLAYER = ROOT / "wnba_pra_player_intelligence_v2_step4.py"

EXPECTED_STEP3_BLOB = "5bfc0aae913f96a083406a835bb21bc99438781b"
EXPECTED_PLAYER_BLOB = "393c29711962bf1d42b8fc58322938c92e23000a"


class Step4CertificationFailure(RuntimeError):
    pass


def _git_blob(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _require(name: str, value: bool) -> None:
    if not value:
        raise Step4CertificationFailure(name)


def certify() -> dict[str, object]:
    app = APP.read_text(encoding="utf-8")
    overlay = OVERLAY.read_text(encoding="utf-8")
    card = CARD.read_text(encoding="utf-8")

    checks = {
        "runtime_active": (
            "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step4_universal_card "
            "import record_bootstrap_import_ms, render_app"
        ) in app,
        "runtime_marker": "WNBA_PRA_REPAIR_V1_STEP4_UNIVERSAL_CARD_RUNTIME" in app,
        "step3_parent_preserved": (
            'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness"'
            in overlay
        ),
        "captures_exact_card_once": "player_intelligence._exact_pra_card" in overlay,
        "wraps_existing_player_renderer": "player_intelligence.render_player_intelligence" in overlay,
        "restores_exact_card": "player_intelligence._exact_pra_card = original_exact" in overlay,
        "restores_player_renderer": "player_intelligence.render_player_intelligence = original_player_renderer" in overlay,
        "model_locked": "MAY_MODIFY_WNBA_MODEL = False" in overlay,
        "projection_locked": "MAY_MODIFY_PROJECTION_MATH = False" in overlay,
        "market_locked": "MAY_MODIFY_MARKET_MATH = False" in overlay,
        "probability_locked": "MAY_MODIFY_PROBABILITY = False" in overlay,
        "qualification_locked": "MAY_MODIFY_QUALIFICATION = False" in overlay,
        "ranking_locked": "MAY_MODIFY_RANKING = False" in overlay,
        "sportsbook_zero": "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in overlay,
        "universal_fields": all(label in card for label in ("Expected PRA", "Line", "Direction", "Probability")),
        "truthful_missing_market": 'return "N/A"' in card and '"direction": direction if market_ready else "N/A"' in card,
        "no_random_math": all(token not in card.lower() for token in ("random.", "numpy.random", "norm.cdf", "monte_carlo")),
        "frozen_step3_exact_blob": _git_blob(FROZEN_STEP3) == EXPECTED_STEP3_BLOB,
        "frozen_player_exact_blob": _git_blob(FROZEN_PLAYER) == EXPECTED_PLAYER_BLOB,
    }
    failed = [name for name, ok in checks.items() if not ok]
    _require("STEP4_SOURCE_CONTRACT_FAILED:" + ",".join(failed), not failed)

    print("WNBA_PRA_REPAIR_V1_STEP4_SOURCE_CONTRACT_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP4_FROZEN_DEPENDENCIES_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP4_NO_FABRICATED_MARKET_GREEN")
    return {"status": "GREEN", "checks": checks}


if __name__ == "__main__":
    certify()
