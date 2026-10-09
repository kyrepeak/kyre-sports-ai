from __future__ import annotations

from .nfl_rb_wr_step5_closeout import install_startup as install_step5_closeout


def install_startup(app):
    """One-shot bridge for the Step-5 final mission freeze closeout.

    The Step-5 proof is already Runless GREEN. This unfrozen bridge installs
    only the finalizer, so the proof wrapper cannot rerun during closeout.
    """
    app.state.nfl_rb_wr_step3_closeout = {
        "status": "NOT_RUN",
        "decision": "STEPS_1_4_FROZEN_STEP5_FINALIZER_BRIDGE",
    }
    install_step5_closeout(app)
    return app
