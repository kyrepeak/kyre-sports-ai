"""Step 18B compatibility bridge for the frozen Streamlit replay.

The historical app imports ``wnba_daily_picks_hub_v34`` and then aliases that
module to ``wnba_daily_picks_hub_v4``. Installing V35 under the V34 module name
before the frozen replay lets only Daily Picks move to the certified consumer
GET while every other frozen WNBA route keeps its existing import graph.
"""
from __future__ import annotations

import importlib
import sys
from typing import Any

MODEL_VERSION = "WNBA STEP 18B STREAMLIT CONSUMER BRIDGE V1"


def install_step18b_consumer_bridge() -> dict[str, Any]:
    # Clear only this additive presentation module so Streamlit hot reruns pick up
    # the current V35 file. Do not purge V33/V34/source-model modules globally.
    sys.modules.pop("wnba_daily_picks_hub_v35", None)
    importlib.invalidate_caches()
    v35 = importlib.import_module("wnba_daily_picks_hub_v35")
    if not callable(getattr(v35, "render_wnba_daily_picks_hub", None)):
        raise RuntimeError("Step 18B V35 renderer is unavailable.")

    # 421568e... imports V34 by this exact name; the older preserved shell later
    # imports V4. Bind both presentation names to the same read-only V35 module.
    sys.modules["wnba_daily_picks_hub_v34"] = v35
    sys.modules["wnba_daily_picks_hub_v4"] = v35
    return {
        "installed": True,
        "model_version": MODEL_VERSION,
        "renderer_version": getattr(v35, "MODEL_VERSION", None),
        "v34_alias_is_v35": sys.modules.get("wnba_daily_picks_hub_v34") is v35,
        "v4_alias_is_v35": sys.modules.get("wnba_daily_picks_hub_v4") is v35,
        "backend_mutated": False,
        "legacy_daily_picks_compute_fallback": False,
    }


__all__ = ["MODEL_VERSION", "install_step18b_consumer_bridge"]
