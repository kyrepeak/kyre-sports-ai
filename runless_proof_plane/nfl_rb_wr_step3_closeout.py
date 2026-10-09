from __future__ import annotations

from .cfb_game_total_page1_visual_cleanup_step1_prove import install_startup as install_cfb_visual_cleanup_step1_proof


def install_startup(app):
    """One-shot bridge for CFB Game Total Page1 visual-cleanup Step1 proof."""
    app.state.nfl_rb_wr_step3_closeout = {
        "status": "NOT_RUN",
        "decision": "CFB_GT_PAGE1_VISUAL_CLEANUP_STEP1_PROOF_BRIDGE",
    }
    install_cfb_visual_cleanup_step1_proof(app)
    return app
