"""WNBA PRA V3.5.1 — strict 10M Final Ready gate.

Small production wrapper over V3.5. A 5M result may qualify and remain MONITOR,
but the Daily Master Card FINAL READY counter cannot increment until the matching
row comes from the completed 10M finalist pass.
"""
from __future__ import annotations

import pandas as pd

import wnba_pra_hub_v35 as v35
import wnba_pra_final_v32 as final32

MODEL_VERSION = "PRA V3.5.1 • STRICT 10M FINAL READY"
MLB_FROZEN_BASELINE = v35.MLB_FROZEN_BASELINE
MLB_FROZEN_BRANCH = v35.MLB_FROZEN_BRANCH


def _install_strict_final_ready():
    if getattr(final32, "_v351_strict_final_ready_installed", False):
        return
    original = final32._stored_rows

    def stored_rows_v351(day):
        rows, meta = original(day)
        if isinstance(rows, pd.DataFrame) and not rows.empty:
            rows = rows.copy()
            source = rows.get("pass_source", pd.Series("5M", index=rows.index)).astype(str).str.upper()
            if "final_ready" not in rows.columns:
                rows["final_ready"] = False
            rows.loc[~source.eq("10M"), "final_ready"] = False
        return rows, meta

    final32._stored_rows = stored_rows_v351
    final32._v351_strict_final_ready_installed = True


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install_strict_final_ready()
    return v35.render_wnba_pra_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(v35, name)


__all__ = [
    "MODEL_VERSION", "MLB_FROZEN_BASELINE", "MLB_FROZEN_BRANCH", "render_wnba_pra_hub",
]
