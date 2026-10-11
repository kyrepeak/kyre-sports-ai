from __future__ import annotations
import os

os.environ["RPP_FULL_APP_ENABLED"] = "1"
os.environ["RPP_WNBA_STEP9_ACTIVATE_ON_START"] = "0"
os.environ["RPP_WNBA_STEP9_FREEZE_ON_START"] = "0"
os.environ["RPP_DRY_RUN_ON_START"] = "0"
os.environ["RPP_FINAL_FREEZE_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_SUBMIT_ON_START"] = "0"
os.environ["RPP_NFL_RB_WR_STEP1_CLOSEOUT_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_PREMERGE_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_CLOSEOUT_ON_START"] = "0"
os.environ["RPP_CFB_GAMES_ON_DAY_STEP1_DIAGNOSTIC_ON_START"] = "0"

from .api import app
from . import cfb_step8_terminal_freeze_event_guard_r3 as terminal


def _verified_premerge_authority(client):
    receipt = terminal._decode(
        client.content(terminal.PREMERGE_RECEIPT_PATH, ref=terminal.RECEIPT_BRANCH)
    )
    if (
        receipt.get("proof_id") != terminal.PREMERGE_PROOF_ID
        or receipt.get("candidate_sha") != terminal.CANDIDATE_SHA
        or receipt.get("digest") != terminal.PREMERGE_RECEIPT_DIGEST
        or receipt.get("failure_class") != "NONE"
    ):
        raise terminal.TerminalFreezeFailure("PREMERGE_AUTHORITY_DRIFT")
    return {
        "proof_id": terminal.PREMERGE_PROOF_ID,
        "receipt_digest": terminal.PREMERGE_RECEIPT_DIGEST,
    }


terminal._ensure_authority = _verified_premerge_authority
terminal.install_startup(app)
