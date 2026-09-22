"""Run the real Step 4X dependency probe with the certified Step 7G Step 4N
schedule-context adapter injected.

The underlying probe still uses the real frozen Step 4X -> Step 4W -> Step 4V
chain and still installs the unresolved Step 4J team-history sentinel. This
wrapper replaces only the old diagnostic season-schedule helper with the
separately certified Step 7G Step 4N adapter.
"""
from __future__ import annotations

from sports_api.tools import wnba_step7g_model_input_dependency_probe as probe
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)


def main() -> int:
    probe._first_party_season_schedule_dataset = (
        get_step7g_step4n_season_schedule_dataset
    )
    return probe.main()


if __name__ == "__main__":
    raise SystemExit(main())
