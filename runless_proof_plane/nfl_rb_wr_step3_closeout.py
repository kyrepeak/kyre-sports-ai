from __future__ import annotations

from .nfl_rb_wr_step4_closeout import install_startup as install_step4_closeout


def install_startup(app):
    """One-shot bridge for the Step-4 canonical freeze closeout.

    Step 3 is already canonically frozen. This unfrozen bridge intentionally
    installs only the Step-4 closeout; it does not submit another Step-4 proof.
    """
    app.state.nfl_rb_wr_step3_closeout = {
        "status": "NOT_RUN",
        "decision": "STEP3_FROZEN_NO_FINALIZER",
    }
    install_step4_closeout(app)
    return app
