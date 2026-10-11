from __future__ import annotations

from . import cfb_game_total_game_cards_step6_premerge as prior

CANDIDATE_SHA = "411c2155062596f321480fc5682b237dea27c924"
FAILURE_CLASS = "HEAD_MOVED_BEFORE_PROOF"
SUPERSEDES_CANDIDATE_SHA = "9107b46a4d41675339799c72a819ea715b49d740"


def install_startup(app):
    prior.CANDIDATE_SHA = CANDIDATE_SHA
    return prior.install_startup(app)


__all__ = ["CANDIDATE_SHA", "FAILURE_CLASS", "SUPERSEDES_CANDIDATE_SHA", "install_startup"]
