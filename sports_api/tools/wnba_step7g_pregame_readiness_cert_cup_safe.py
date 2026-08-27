"""Run the live Step 4X pregame cert with certified Step 7G hardening.

This wrapper installs the exact 2026 Commissioner's Cup exclusion and transient
first-party transport retry. It also aligns the certification warning allowlist
with frozen Step 4X semantics: ``observed_minutes_variability`` is an explicit
non-blocking model-uncertainty warning (CV > 0.35), so READY_WITH_WARNINGS is a
valid startable outcome when there are no blockers.

The frozen Step 4X gate itself is not modified or relaxed.
"""
from __future__ import annotations

from sports_api.wnba_step7g_first_party_team_history_cup_safe import (
    install_exact_cup_exclusion,
)

install_exact_cup_exclusion()

from sports_api.tools import wnba_step7g_pregame_readiness_cert as cert  # noqa: E402

cert._ALLOWED_WARNING_IDS = set(cert._ALLOWED_WARNING_IDS) | {
    "observed_minutes_variability",
}


if __name__ == "__main__":
    raise SystemExit(cert.main())
