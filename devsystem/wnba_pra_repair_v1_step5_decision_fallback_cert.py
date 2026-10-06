"""WNBA PRA Repair V1 Step 5 — decision fallback source certification."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback.py"
ENGINE = ROOT / "wnba_pra_repair_v1_step5_decision_fallback.py"
FROZEN_STEP4_OVERLAY = ROOT / "streamlit_memory_lazy_router_wnba_pra_repair_v1_step4_universal_card.py"
FROZEN_STEP4_CARD = ROOT / "wnba_pra_repair_v1_step4_final_card.py"
FROZEN_PLAYER = ROOT / "wnba_pra_player_intelligence_v2_step4.py"

EXPECTED_STEP4_OVERLAY_BLOB = "2d6bcb223bae4a1db5477b27b72604faa68aa66c"
EXPECTED_STEP4_CARD_BLOB = "c9f6f516fe2f650e76cb085439b33c52642b5dc6"
EXPECTED_PLAYER_BLOB = "393c29711962bf1d42b8fc58322938c92e23000a"


class Step5CertificationFailure(RuntimeError):
    pass


def _git_blob(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def certify() -> dict[str, object]:
    app = APP.read_text(encoding="utf-8")
    overlay = OVERLAY.read_text(encoding="utf-8")
    engine = ENGINE.read_text(encoding="utf-8")

    checks = {
        "runtime_marker": "WNBA_PRA_REPAIR_V1_STEP5_DECISION_FALLBACK_RUNTIME" in app,
        "runtime_active": (
            "from streamlit_memory_lazy_router_wnba_pra_repair_v1_step5_decision_fallback "
            "import record_bootstrap_import_ms, render_app"
        ) in app,
        "frozen_step4_compatibility_kept": (
            "Frozen WNBA PRA Repair V1 Step 4 compatibility: from "
            "streamlit_memory_lazy_router_wnba_pra_repair_v1_step4_universal_card"
        ) in app,
        "step4_parent_preserved": (
            'FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step4_universal_card"'
            in overlay
        ),
        "hosted_step5f_only": "/prop-threshold-probability" in overlay and "get_player_game_prop_threshold_probability" not in overlay,
        "exact_market_bypass": 'if base.get("market_ready") is True:' in overlay,
        "history_capture": "player_intelligence.load_player_intelligence" in overlay,
        "step4_build_wrapped": "step4_final_card.build_final_card" in overlay,
        "step4_render_wrapped": "step4_final_card.render_final_card" in overlay,
        "projection_locked": "MAY_MODIFY_PROJECTION_MATH = False" in overlay,
        "market_locked": "MAY_MODIFY_MARKET_MATH = False" in overlay,
        "probability_locked": "MAY_MODIFY_PROBABILITY = False" in overlay,
        "qualification_locked": "MAY_MODIFY_QUALIFICATION = False" in overlay,
        "ranking_locked": "MAY_MODIFY_RANKING = False" in overlay,
        "sportsbook_zero": "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in overlay,
        "market_precedence": '"decision_source": "CERTIFIED MARKET"' in engine,
        "model_fallback": '"decision_source": "MODEL FALLBACK"' in engine,
        "history_fallback": '"decision_source": "HISTORY FALLBACK"' in engine,
        "data_limited": '"decision_source": "DATA LIMITED"' in engine,
        "reference_not_sportsbook": '"reference_line_is_sportsbook": False' in engine,
        "frozen_step4_overlay_exact_blob": _git_blob(FROZEN_STEP4_OVERLAY) == EXPECTED_STEP4_OVERLAY_BLOB,
        "frozen_step4_card_exact_blob": _git_blob(FROZEN_STEP4_CARD) == EXPECTED_STEP4_CARD_BLOB,
        "frozen_player_exact_blob": _git_blob(FROZEN_PLAYER) == EXPECTED_PLAYER_BLOB,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise Step5CertificationFailure("STEP5_SOURCE_CONTRACT_FAILED:" + ",".join(failed))

    print("WNBA_PRA_REPAIR_V1_STEP5_SOURCE_CONTRACT_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP5_FROZEN_DEPENDENCIES_GREEN")
    print("WNBA_PRA_REPAIR_V1_STEP5_NO_FAKE_SPORTSBOOK_LINE_GREEN")
    return {"status": "GREEN", "checks": checks}


if __name__ == "__main__":
    certify()
