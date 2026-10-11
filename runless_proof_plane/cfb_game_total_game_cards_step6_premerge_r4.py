from __future__ import annotations

from . import cfb_game_total_game_cards_step6_premerge_r3 as prior_wrapper

CANDIDATE_SHA = "16a64a4e4889467fc60685e7343871556bf245cb"
SUPERSEDED_CANDIDATE_SHA = "411c2155062596f321480fc5682b237dea27c924"
FAILURE_CLASS = "FINAL_REVIEW_REPAIR_HEAD_RECONCILIATION"


def install_startup(app):
    prior_wrapper.CANDIDATE_SHA = CANDIDATE_SHA
    prior_wrapper.SUPERSEDED_CANDIDATE_SHA = SUPERSEDED_CANDIDATE_SHA
    return prior_wrapper.install_startup(app)


__all__ = ["CANDIDATE_SHA", "FAILURE_CLASS", "SUPERSEDED_CANDIDATE_SHA", "install_startup"]
