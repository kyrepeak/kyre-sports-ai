"""CFB Game Total clean page V18 — Step 6 Scoring Creation.

Additive over frozen Page V17. Only Step 6 advances to the dedicated Scoring
Creation presentation owner. Steps 1-5, model math, distribution, qualification,
ranking, APIs and sportsbook projection influence remain frozen.
"""
from __future__ import annotations

import cfb_game_total_clean_page_v17 as prior_v168
import cfb_game_total_step6_scoring_v1 as step6_owner

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V18 • V184 STEP6 SCORING CREATION"
MARKET = prior_v168.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v17"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • V184 STEP6 SCORING CREATION ACTIVE"
STEP6_PRESENTATION_MARKER = step6_owner.STEP6_PRESENTATION_MARKER
STEP6_DATA_MARKER = step6_owner.STEP6_DATA_MARKER
STEP6_VISUAL_MARKER = step6_owner.STEP6_VISUAL_MARKER
STEP6_DEPLOYMENT_MARKER = step6_owner.STEP6_DEPLOYMENT_MARKER

# Re-export frozen Step 5 contract markers for protection/certification.
STEP5_PRESENTATION_MARKER = prior_v168.STEP5_PRESENTATION_MARKER
STEP5_DATA_MARKER = prior_v168.STEP5_DATA_MARKER
STEP5_VISUAL_MARKER = prior_v168.STEP5_VISUAL_MARKER


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    compact_owner = prior_v168.prior_v165.prior_v164.compact_owner
    original_step_evidence = compact_owner._step_evidence_html

    def step_evidence_v184(
        number,
        title,
        status,
        detail,
        identity,
        away,
        home,
        display_game,
        model,
    ):
        if int(number) == 6:
            exact_identity = identity
            try:
                exact_identity = (
                    prior_v168.prior_v165.prior_v164._final_presentation_identity_v164(
                        identity,
                        display_game,
                    )
                )
            except Exception:
                exact_identity = identity

            step6_game = dict(display_game or {})
            selected_day = (
                prior_v168.prior_v165.prior_v164.logo_identity._game_date(step6_game)
                or prior_v168.prior_v165.prior_v164._query_selected_day()
            )
            event_id = (
                prior_v168.prior_v165.prior_v164.logo_identity._event_id(step6_game)
                or prior_v168.prior_v165.prior_v164.prior_v163._query_event_id()
            )
            if event_id and not prior_v168.prior_v165.prior_v164.logo_identity._event_id(step6_game):
                step6_game["espn_event_id"] = event_id
            if selected_day and not str(step6_game.get("game_date") or "").strip():
                step6_game["game_date"] = selected_day

            try:
                step6_game = (
                    prior_v168.prior_v165.prior_v164.logo_identity.enrich_exact_team_ids(
                        step6_game,
                        prior_v168.prior_v165.prior_v164._selector_payload_for_day(
                            selected_day
                        ),
                    )
                )
            except Exception:
                pass

            step6_away = dict(away or {})
            step6_home = dict(home or {})

            # Snapshot-only completed-game identity handoff. Never reopen the
            # heavy Step 3/NCAA enrichment stack from a presentation step.
            try:
                bundle, _diag = (
                    prior_v168.prior_v165.prior_v164.step3_owner._runtime_v2_step3_bundle(
                        step6_game,
                        selected_day,
                    )
                )
                if isinstance(bundle, dict):
                    away_snapshot = bundle.get("away")
                    home_snapshot = bundle.get("home")
                    if isinstance(away_snapshot, dict):
                        step6_away.update(away_snapshot)
                    if isinstance(home_snapshot, dict):
                        step6_home.update(home_snapshot)
            except Exception:
                pass

            return step6_owner.render_step6_html(
                status,
                exact_identity,
                step6_away,
                step6_home,
                step6_game,
            )

        return original_step_evidence(
            number,
            title,
            status,
            detail,
            identity,
            away,
            home,
            display_game,
            model,
        )

    compact_owner._step_evidence_html = step_evidence_v184
    try:
        return prior_v168.render_game_total_hub(
            section_header,
            status_info,
            team_logo,
            h,
        )
    finally:
        compact_owner._step_evidence_html = original_step_evidence


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(
            f"V184 Game Total V18 page received unsupported market: {market}"
        )
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP5_DATA_MARKER",
    "STEP5_PRESENTATION_MARKER",
    "STEP5_VISUAL_MARKER",
    "STEP6_DATA_MARKER",
    "STEP6_DEPLOYMENT_MARKER",
    "STEP6_PRESENTATION_MARKER",
    "STEP6_VISUAL_MARKER",
    "render_cfb_hub",
    "render_game_total_hub",
]
