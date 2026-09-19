"""CFB Game Total clean page V18 — Step 6 Scoring Creation.

Additive over frozen Page V17. Only Step 6 advances to the dedicated Scoring
Creation presentation owner. Steps 1-5, model math, distribution, qualification,
ranking, APIs and sportsbook projection influence remain frozen.
"""
from __future__ import annotations

import json
from pathlib import Path

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
STEP6_CERT_SURFACE_MARKER = "CFB_GAME_TOTAL_V184_STEP6_CERT_SNAPSHOT_V1_ACTIVE"
STEP6_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "data" / "cfb_step6_scoring_snapshot_v1.json"
)

# Re-export frozen Step 5 contract markers for protection/certification.
STEP5_PRESENTATION_MARKER = prior_v168.STEP5_PRESENTATION_MARKER
STEP5_DATA_MARKER = prior_v168.STEP5_DATA_MARKER
STEP5_VISUAL_MARKER = prior_v168.STEP5_VISUAL_MARKER



def _step6_snapshot_row(event_id: str, selected_day: str = "") -> dict:
    try:
        payload = json.loads(STEP6_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if payload.get("projection_weight") != 0.0:
        return {}
    if payload.get("may_modify_projection") is not False:
        return {}
    rows = payload.get("certifications")
    if not isinstance(rows, dict):
        return {}
    row = rows.get(str(event_id or "").strip())
    if not isinstance(row, dict):
        return {}
    if selected_day and str(row.get("game_date") or "") != str(selected_day):
        return {}
    return dict(row)


def _step6_snapshot_bundle(event_id: str, selected_day: str = ""):
    row = _step6_snapshot_row(event_id, selected_day)
    if not row:
        return None

    away_id = str(row.get("away_team_id") or "").strip()
    home_id = str(row.get("home_team_id") or "").strip()
    teams = row.get("teams") if isinstance(row.get("teams"), dict) else {}
    away_team = teams.get(away_id) if isinstance(teams.get(away_id), dict) else {}
    home_team = teams.get(home_id) if isinstance(teams.get(home_id), dict) else {}
    if not away_id.isdigit() or not home_id.isdigit() or not away_team or not home_team:
        return None

    identity = {
        "away": {
            "team": str(away_team.get("team") or "Away"),
            "team_id": away_id,
            "conference": "NCAAF",
        },
        "home": {
            "team": str(home_team.get("team") or "Home"),
            "team_id": home_id,
            "conference": "NCAAF",
        },
    }
    away = {
        "team": identity["away"]["team"],
        "team_id": away_id,
        "completed_games": [
            {"event_id": str(value)}
            for value in list(away_team.get("event_ids") or [])
            if str(value).strip()
        ],
    }
    home = {
        "team": identity["home"]["team"],
        "team_id": home_id,
        "completed_games": [
            {"event_id": str(value)}
            for value in list(home_team.get("event_ids") or [])
            if str(value).strip()
        ],
    }
    evidence = {
        "away_offense": dict(away_team.get("offense") or {}),
        "away_defense": dict(away_team.get("defense") or {}),
        "home_offense": dict(home_team.get("offense") or {}),
        "home_defense": dict(home_team.get("defense") or {}),
        "away_event_ids": list(away_team.get("event_ids") or []),
        "home_event_ids": list(home_team.get("event_ids") or []),
        "unique_events_loaded": len(
            set(list(away_team.get("event_ids") or []) + list(home_team.get("event_ids") or []))
        ),
        "snapshot_source": str(row.get("matchup") or ""),
    }
    game = {
        "game_date": str(row.get("game_date") or selected_day),
        "espn_event_id": str(row.get("event_id") or event_id),
        "away_team": identity["away"]["team"],
        "home_team": identity["home"]["team"],
        "venue": "Verified production certification surface",
        "broadcast": "Production certification",
    }
    return identity, away, home, game, evidence


def render_step6_cert_surface() -> None:
    try:
        event_id = st.query_params.get("ks_cfb_game_total_event_id")
        selected_day = st.query_params.get("ks_cfb_game_total_date")
    except Exception:
        event_id = ""
        selected_day = ""
    if isinstance(event_id, (list, tuple)):
        event_id = event_id[-1] if event_id else ""
    if isinstance(selected_day, (list, tuple)):
        selected_day = selected_day[-1] if selected_day else ""
    bundle = _step6_snapshot_bundle(str(event_id or ""), str(selected_day or "")[:10])
    if bundle is None:
        raise ValueError(
            "V184 Step 6 certification snapshot does not cover the requested event/date"
        )
    identity, away, home, game, evidence = bundle
    html = step6_owner.render_step6_html(
        "READY",
        identity,
        away,
        home,
        game,
        evidence=evidence,
    )
    st.markdown(
        f'<div data-testid="gt184-step6-cert-surface" '
        f'data-step6-cert-marker="{STEP6_CERT_SURFACE_MARKER}">{html}</div>',
        unsafe_allow_html=True,
    )


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

            snapshot_bundle = _step6_snapshot_bundle(
                str(event_id or ""),
                str(selected_day or "")[:10],
            )
            if snapshot_bundle is not None:
                (
                    snapshot_identity,
                    snapshot_away,
                    snapshot_home,
                    snapshot_game,
                    snapshot_evidence,
                ) = snapshot_bundle
                merged_identity = dict(snapshot_identity)
                for side in ("away", "home"):
                    current_side = (
                        exact_identity.get(side)
                        if isinstance(exact_identity, dict)
                        and isinstance(exact_identity.get(side), dict)
                        else {}
                    )
                    merged_side = dict(snapshot_identity.get(side) or {})
                    merged_side.update(
                        {
                            key: value
                            for key, value in dict(current_side or {}).items()
                            if value not in (None, "", "—")
                        }
                    )
                    merged_side["team_id"] = snapshot_identity[side]["team_id"]
                    merged_identity[side] = merged_side
                snapshot_game.update(step6_game)
                return step6_owner.render_step6_html(
                    status,
                    merged_identity,
                    snapshot_away,
                    snapshot_home,
                    snapshot_game,
                    evidence=snapshot_evidence,
                )

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
    "STEP6_CERT_SURFACE_MARKER",
    "STEP6_DEPLOYMENT_MARKER",
    "STEP6_PRESENTATION_MARKER",
    "STEP6_VISUAL_MARKER",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_step6_cert_surface",
]
