from __future__ import annotations

from .cfb_game_total_page1_visual_cleanup_step1_closeout import install_startup as install_cfb_visual_cleanup_step1_closeout
from .cfb_game_total_page1_visual_cleanup_step2_closeout import install_startup as install_cfb_visual_cleanup_step2_closeout
from .cfb_game_total_page1_visual_cleanup_step3_thaw import install_startup as install_cfb_visual_cleanup_step3_thaw
from .cfb_game_total_page1_visual_cleanup_step3_proof import install_startup as install_cfb_visual_cleanup_step3_proof
from .cfb_game_total_page1_visual_cleanup_step3_closeout import install_startup as install_cfb_visual_cleanup_step3_closeout
from .cfb_game_total_page1_visual_cleanup_step4_thaw import install_startup as install_cfb_visual_cleanup_step4_thaw
from .cfb_game_total_page1_visual_cleanup_step4_proof import install_startup as install_cfb_visual_cleanup_step4_proof
from .cfb_game_total_page1_visual_cleanup_step4_closeout import install_startup as install_cfb_visual_cleanup_step4_closeout
from .cfb_game_total_page1_visual_cleanup_step5_thaw import install_startup as install_cfb_visual_cleanup_step5_thaw
from .cfb_game_total_page1_visual_cleanup_step5_proof import install_startup as install_cfb_visual_cleanup_step5_proof
from .cfb_game_total_page1_visual_cleanup_step5_cert import install_startup as install_cfb_visual_cleanup_step5_cert


def _install_optional_404_compat(app):
    client = app.state.github_client
    current = client.content
    if getattr(current, "_cfb_optional_404_compat", False):
        return

    def content(path, ref=None, allow_404=False):
        try:
            return current(path, ref=ref, allow_404=allow_404)
        except Exception as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if allow_404 and (status_code == 404 or "404" in str(exc)):
                return None
            raise

    setattr(content, "_cfb_optional_404_compat", True)
    client.content = content


def install_startup(app):
    """One-shot bridge for CFB Game Total Page1 visual-cleanup finalization."""
    app.state.nfl_rb_wr_step3_closeout = {
        "status": "NOT_RUN",
        "decision": "CFB_GT_PAGE1_VISUAL_CLEANUP_FINALIZER_BRIDGE",
    }
    _install_optional_404_compat(app)
    install_cfb_visual_cleanup_step1_closeout(app)
    install_cfb_visual_cleanup_step2_closeout(app)
    install_cfb_visual_cleanup_step3_thaw(app)
    install_cfb_visual_cleanup_step3_proof(app)
    install_cfb_visual_cleanup_step3_closeout(app)
    install_cfb_visual_cleanup_step4_thaw(app)
    install_cfb_visual_cleanup_step4_proof(app)
    install_cfb_visual_cleanup_step4_closeout(app)
    install_cfb_visual_cleanup_step5_thaw(app)
    install_cfb_visual_cleanup_step5_proof(app)
    install_cfb_visual_cleanup_step5_cert(app)
    return app
