from __future__ import annotations

from .nfl_rb_wr_step4_prove import install_startup as install_step4_prove


def install_startup(app):
    """Temporary Step-4 proof bridge.

    Step 3 is already canonically frozen and its finalizer authority has been
    garbage-collected, so the normal Step-3 closeout would be a no-op here.
    This unfrozen bridge exists only on the Runless proof branch for one
    Step-4 proof deploy and is rolled back immediately afterward.
    """
    app.state.nfl_rb_wr_step3_closeout = {
        "status": "NOT_RUN",
        "decision": "STEP3_FROZEN_NO_FINALIZER",
    }
    install_step4_prove(app)
    return app
