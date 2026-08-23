"""NFL Moneyline V3.1 Step-3 compatibility repair."""
from __future__ import annotations

import nfl_moneyline_hub_v1 as step1
import nfl_moneyline_hub_v2 as step2
import nfl_moneyline_hub_v21 as step21  # import applies verified depth patch

# Step 3 consumes these Step-1 UI/clock helpers through the Step-2 namespace.
# Step 2 did not re-export them, causing the AttributeError seen in production.
step2._CSS = step1._CSS
step2._pregame_partition = step1._pregame_partition
step2._game_foundation_card = step1._game_foundation_card
step2._scheduled_tip = step1._scheduled_tip

_REQUIRED = (
    "_CSS",
    "_pregame_partition",
    "_game_foundation_card",
    "_scheduled_tip",
    "_safe",
    "_league_injuries_payload",
    "_parse_injuries",
    "_team_context",
    "_render_team_step2",
)
for _name in _REQUIRED:
    if not hasattr(step2, _name):
        raise RuntimeError(f"NFL Moneyline V3.1 preflight missing {_name}")

import nfl_moneyline_hub_v3 as v3

MODEL_VERSION = "NFL MONEYLINE V3.1 • STEP 3 HELPER REPAIR"


def render_nfl_moneyline_hub():
    return v3.render_nfl_moneyline_hub()


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
