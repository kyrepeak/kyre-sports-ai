"""CFB Game Total clean page V18 — Step 6 Scoring Creation.

Additive over frozen Page V17. Only Step 6 advances to the dedicated Scoring
Creation presentation owner. Steps 1-5, model math, distribution, qualification,
ranking, APIs and sportsbook projection influence remain frozen.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

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


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _early_step6_context():
    """Build Step 6 directly from exact query identity + verified PBP IDs.

    This intentionally avoids the frozen Steps 1-5 enrichment stack. It only
    activates when both sides have exact ESPN IDs and verified completed-game
    event IDs in the dedicated Step 6 snapshot.
    """
    base = prior_v168.prior_v165.prior_v164
    selected_day = base._query_selected_day()
    event_id = base.prior_v163._query_event_id()
    if not selected_day or not event_id:
        return None

    try:
        payload = base._selector_payload_for_day(selected_day)
    except Exception:
        return None
    rows = payload.get("games") if isinstance(payload, Mapping) else []
    row = None
    for candidate in rows or []:
        if not isinstance(candidate, Mapping):
            continue
        if _clean(candidate.get("event_id")) == event_id:
            row = dict(candidate)
            break
    if row is None:
        return None

    game = dict(row)
    game["event_id"] = event_id
    game["espn_event_id"] = event_id
    game["game_date"] = selected_day
    try:
        game = base.logo_identity.enrich_exact_team_ids(game, payload)
    except Exception:
        pass

    away_id = _clean(
        game.get("away_espn_team_id")
        or game.get("away_team_id")
        or row.get("away_team_id")
    )
    home_id = _clean(
        game.get("home_espn_team_id")
        or game.get("home_team_id")
        or row.get("home_team_id")
    )
    if not away_id.isdigit() or not home_id.isdigit():
        return None

    away_events = step6_owner._snapshot_event_ids(away_id)
    home_events = step6_owner._snapshot_event_ids(home_id)
    if not away_events or not home_events:
        return None

    away_name = (
        _clean(row.get("away_team"))
        or _clean(game.get("away_team"))
        or "Away"
    )
    home_name = (
        _clean(row.get("home_team"))
        or _clean(game.get("home_team"))
        or "Home"
    )
    logo_template = base.logo_identity.ESPN_LOGO_CDN_TEMPLATE

    identity = {
        "away": {
            "team": away_name,
            "team_id": away_id,
            "espn_team_id": away_id,
            "logo": logo_template.format(team_id=away_id),
            "conference": "NCAAF",
            "exact_identity": True,
        },
        "home": {
            "team": home_name,
            "team_id": home_id,
            "espn_team_id": home_id,
            "logo": logo_template.format(team_id=home_id),
            "conference": "NCAAF",
            "exact_identity": True,
        },
    }
    away = {
        "team": away_name,
        "team_name": away_name,
        "team_id": away_id,
        "espn_team_id": away_id,
        "completed_games": [{"event_id": value} for value in away_events],
    }
    home = {
        "team": home_name,
        "team_name": home_name,
        "team_id": home_id,
        "espn_team_id": home_id,
        "completed_games": [{"event_id": value} for value in home_events],
    }
    return identity, away, home, game


def _render_early_step6() -> bool:
    context = _early_step6_context()
    if context is None:
        return False
    identity, away, home, game = context
    html = step6_owner.render_step6_html(
        "READY",
        identity,
        away,
        home,
        game,
    )
    st.markdown(
        '<div data-testid="gt184-step6-early-mount" '
        f'data-event-id="{_clean(game.get("espn_event_id"))}">'
        f"{html}</div>",
        unsafe_allow_html=True,
    )
    return True


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    early_step6_rendered = _render_early_step6()
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
            if early_step6_rendered:
                return (
                    '<div data-testid="gt184-step6-inline-delegated" '
                    'style="display:none!important"></div>'
                )
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
    "_early_step6_context",
    "_render_early_step6",
    "render_cfb_hub",
    "render_game_total_hub",
]
