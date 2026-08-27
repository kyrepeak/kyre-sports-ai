"""Run the existing live Step 4X pregame cert with the exact Cup exclusion installed."""
from __future__ import annotations

from sports_api.wnba_step7g_first_party_team_history_cup_safe import (
    install_exact_cup_exclusion,
)

install_exact_cup_exclusion()

from sports_api.tools.wnba_step7g_pregame_readiness_cert import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
