from __future__ import annotations

from .nfl_rb_wr_step5_prove import install_startup as install_step5_prove


def install_startup(app):
    """One-shot bridge for the Step-5 final mission proof.

    Steps 1-4 are already canonically frozen. This unfrozen bridge installs
    only the Step-5 proof wrapper and does not reopen any prior product scope.
    """
    app.state.nfl_rb_wr_step3_closeout = {
        "status": "NOT_RUN",
        "decision": "STEPS_1_4_FROZEN_STEP5_PROOF_BRIDGE",
    }
    install_step5_prove(app)
    return app
