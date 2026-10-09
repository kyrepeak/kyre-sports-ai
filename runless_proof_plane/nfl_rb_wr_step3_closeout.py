from __future__ import annotations

from .cfb_game_total_page1_visual_cleanup_step1_closeout import install_startup as install_cfb_visual_cleanup_step1_closeout
from .cfb_game_total_page1_visual_cleanup_step2_closeout import install_startup as install_cfb_visual_cleanup_step2_closeout
from .cfb_game_total_page1_visual_cleanup_step3_thaw import install_startup as install_cfb_visual_cleanup_step3_thaw
from .cfb_game_total_page1_visual_cleanup_step3_proof import install_startup as install_cfb_visual_cleanup_step3_proof
from .cfb_game_total_page1_visual_cleanup_step3_closeout import install_startup as install_cfb_visual_cleanup_step3_closeout


def install_startup(app):
    """One-shot bridge for CFB Game Total Page1 visual-cleanup finalization."""
    app.state.nfl_rb_wr_step3_closeout = {
        "status": "NOT_RUN",
        "decision": "CFB_GT_PAGE1_VISUAL_CLEANUP_FINALIZER_BRIDGE",
    }
    install_cfb_visual_cleanup_step1_closeout(app)
    install_cfb_visual_cleanup_step2_closeout(app)
    install_cfb_visual_cleanup_step3_thaw(app)
    install_cfb_visual_cleanup_step3_proof(app)
    install_cfb_visual_cleanup_step3_closeout(app)
    return app
