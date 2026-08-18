"""WNBA Rebounds V1.2 cache-busting route wrapper.

The Step-3 implementation currently lives in ``wnba_rebounds_hub_v111`` for
backward compatibility with the existing build chain.  This module gives the
Streamlit router a brand-new import name and explicitly reloads that
implementation, so an already-running app cannot keep serving the old V1.1.1
module from ``sys.modules``.

No model math is changed here; this file is routing/cache protection only.
"""
from __future__ import annotations

import importlib

import wnba_rebounds_hub_v111 as _impl

# Force the on-disk Step-3 code to win over any stale in-process V1.1.1 module.
_impl = importlib.reload(_impl)

MODEL_VERSION = getattr(_impl, "MODEL_VERSION", "WNBA REBOUNDS V1.2 • STEP 3 ROTATION MINUTES")


def render_wnba_rebounds_hub(*args, **kwargs):
    return _impl.render_wnba_rebounds_hub(*args, **kwargs)


def __getattr__(name):
    return getattr(_impl, name)
