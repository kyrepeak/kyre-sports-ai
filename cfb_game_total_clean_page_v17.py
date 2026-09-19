"""CFB Game Total clean page V17 — Step 5 Pace & Expected Possessions.

Additive over frozen Page V16. Only Step 5 advances to the dedicated pace /
expected-possessions presentation owner. Steps 1-4, model math, distribution,
qualification, ranking, APIs, and sportsbook projection influence remain frozen.
"""
from __future__ import annotations

import cfb_game_total_clean_page_v16 as prior_v165
import cfb_game_total_step5_pace_v1 as step5_owner

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V17 • V168 STEP5 PACE POSSESSIONS"
MARKET = prior_v165.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v16"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • V168 STEP5 PACE POSSESSIONS ACTIVE"
STEP5_PRESENTATION_MARKER = step5_owner.STEP5_PRESENTATION_MARKER
STEP5_DATA_MARKER = step5_owner.STEP5_DATA_MARKER
STEP5_VISUAL_MARKER = step5_owner.STEP5_VISUAL_MARKER

# Re-export V16 frozen Step 4 contract markers for certification.
STEP4_PRESENTATION_MARKER = prior_v165.STEP4_PRESENTATION_MARKER
STEP4_DATA_MARKER = prior_v165.STEP4_DATA_MARKER
STEP4_DEPLOYMENT_MARKER = prior_v165.STEP4_DEPLOYMENT_MARKER
STEP4_VISUAL_MARKER = prior_v165.STEP4_VISUAL_MARKER
STEP4_GRADE_MARKER = prior_v165.STEP4_GRADE_MARKER


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    compact_owner = prior_v165.prior_v164.compact_owner
    original_step_evidence = compact_owner._step_evidence_html

    def step_evidence_v168(
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
        if int(number) == 5:
            exact_identity = identity
            try:
                exact_identity = prior_v165.prior_v164._final_presentation_identity_v164(
                    identity,
                    display_game,
                )
            except Exception:
                exact_identity = identity

            step5_game = dict(display_game or {})
            selected_day = (
                prior_v165.prior_v164.logo_identity._game_date(step5_game)
                or prior_v165.prior_v164._query_selected_day()
            )
            event_id = (
                prior_v165.prior_v164.logo_identity._event_id(step5_game)
                or prior_v165.prior_v164.prior_v163._query_event_id()
            )
            if event_id and not prior_v165.prior_v164.logo_identity._event_id(step5_game):
                step5_game["espn_event_id"] = event_id
            if selected_day and not str(step5_game.get("game_date") or "").strip():
                step5_game["game_date"] = selected_day

            try:
                step5_game = prior_v165.prior_v164.logo_identity.enrich_exact_team_ids(
                    step5_game,
                    prior_v165.prior_v164._selector_payload_for_day(selected_day),
                )
            except Exception:
                pass

            step5_away = dict(away or {})
            step5_home = dict(home or {})
            if selected_day:
                try:
                    bundle, _diag = (
                        prior_v165.prior_v164.step3_data_owner.load_matchup_team_data(
                            step5_game,
                            selected_day,
                        )
                    )
                    if isinstance(bundle, dict):
                        away_foundation = bundle.get("away")
                        home_foundation = bundle.get("home")
                        if isinstance(away_foundation, dict):
                            step5_away.update(away_foundation)
                        if isinstance(home_foundation, dict):
                            step5_home.update(home_foundation)
                except Exception:
                    pass

            # Step 5 PBP evidence requires exact completed-game event IDs.
            # The generic NCAA team-data foundation above intentionally omits
            # those IDs, so overlay the certified Step 3 runtime enrichment
            # before the Step 5 owner builds SportsDataverse evidence.
            try:
                step3_away, step3_home, _step3_diag = (
                    prior_v165.prior_v164.step3_owner.enrich_step3_inputs(
                        exact_identity,
                        step5_away,
                        step5_home,
                        step5_game,
                    )
                )
                if isinstance(step3_away, dict):
                    step5_away.update(step3_away)
                if isinstance(step3_home, dict):
                    step5_home.update(step3_home)
            except Exception:
                pass

            return step5_owner.render_step5_html(
                status,
                exact_identity,
                step5_away,
                step5_home,
                step5_game,
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

    compact_owner._step_evidence_html = step_evidence_v168
    try:
        return prior_v165.render_game_total_hub(
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
            f"V168 Game Total V17 page received unsupported market: {market}"
        )
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_DATA_MARKER",
    "STEP4_DEPLOYMENT_MARKER",
    "STEP4_GRADE_MARKER",
    "STEP4_PRESENTATION_MARKER",
    "STEP4_VISUAL_MARKER",
    "STEP5_DATA_MARKER",
    "STEP5_PRESENTATION_MARKER",
    "STEP5_VISUAL_MARKER",
    "render_cfb_hub",
    "render_game_total_hub",
]
