"""CFB Game Total Clean Page V15 — V164 universal exact team logos.

Additive presentation-only successor to permanently frozen V163/V14. V164 keeps
all V163 selector, model, market, qualification and ranking behavior unchanged,
and enriches only missing display-logo team IDs from official ESPN event
identity before the frozen exact-ID logo resolver runs.
"""
from __future__ import annotations

from datetime import date
from html import escape
import json
from typing import Any, Mapping

import streamlit as st

import cfb_game_total_clean_page_v3 as identity_owner
import cfb_game_total_clean_page_v14 as prior_v163
import cfb_game_total_clean_page_v10 as presentation_owner
import cfb_game_total_clean_page_v9 as compact_owner
import cfb_game_total_step1_identity_v1 as step1_owner
import cfb_game_total_step1_profile_v1 as step1_profile_owner
import cfb_game_total_step2_profile_v1 as step2_owner
import cfb_game_total_step2_drive_v1 as step2_drive_owner
import cfb_game_total_step3_form_v1 as step3_owner
import cfb_game_total_step4_matchup_v1 as step4_owner
import cfb_team_data_v1 as step3_data_owner
import cfb_game_total_team_logo_identity_v1 as logo_identity
import cfb_game_total_runtime_display_v1 as runtime_display
import cfb_over_under_logo_resolver_v3 as frozen_logo

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V15 • V164 UNIVERSAL EXACT TEAM LOGOS"
MARKET = prior_v163.MARKET
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v14"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V164 ACTIVE"
LOGO_POLICY = "official ESPN event_id -> exact ESPN team IDs -> ESPN NCAA logo CDN"
DEPLOYMENT_PROOF_MARKER = "CFB_GAME_TOTAL_V164_BLANK_EVENT_ID_HANDOFF_PATCH_ACTIVE"
STEP1_PRESENTATION_MARKER = "CFB_GAME_TOTAL_STEP1_TEAM_IDENTITY_ACCORDION_ACTIVE"
STEP1_PROFILE_MARKER = "CFB_GAME_TOTAL_STEP1_FAST_EXACT_PROFILE_ACTIVE"
STEP2_PRESENTATION_MARKER = step2_owner.STEP2_PRESENTATION_MARKER
STEP3_PRESENTATION_MARKER = step3_owner.STEP3_PRESENTATION_MARKER
STEP4_PRESENTATION_MARKER = step4_owner.STEP4_PRESENTATION_MARKER

_FROZEN_RESOLVE_VISUALS = frozen_logo.resolve_visuals
_FROZEN_TEAM_IDENTITY = identity_owner._team_identity
_FROZEN_RECONCILE_DISPLAY_BUNDLE = runtime_display.reconcile_display_bundle


def _selector_payload_for_day(selected_day: Any) -> dict[str, Any]:
    requested_day = selected_day.isoformat() if isinstance(selected_day, date) else str(selected_day or "")[:10]
    if not requested_day:
        return {}
    try:
        return prior_v163._fetch_selector_identity_payload(date.fromisoformat(requested_day))
    except (TypeError, ValueError):
        return {}


def _selector_payload_for_game(game: Mapping[str, Any]) -> dict[str, Any]:
    return _selector_payload_for_day(logo_identity._game_date(game))


def _reconcile_display_bundle_v164(
    game: Mapping[str, Any],
    selected_day: Any,
    frozen_away: Mapping[str, Any],
    frozen_home: Mapping[str, Any],
):
    """Enrich only the display copy with exact ESPN team IDs before logo resolution."""
    display_game, away, home, diag = _FROZEN_RECONCILE_DISPLAY_BUNDLE(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )
    enriched = dict(display_game or game)
    event_id = logo_identity._event_id(game) or logo_identity._event_id(enriched)
    if event_id and not logo_identity._event_id(enriched):
        enriched["espn_event_id"] = event_id

    payload = _selector_payload_for_day(selected_day)
    enriched = logo_identity.enrich_exact_team_ids(enriched, payload)

    out_diag = dict(diag or {})
    away_id = str(enriched.get("away_espn_team_id") or "").strip()
    home_id = str(enriched.get("home_espn_team_id") or "").strip()
    out_diag["v164_logo_team_ids_enriched"] = bool(away_id.isdigit() and home_id.isdigit())
    out_diag["v164_logo_identity_source"] = str(enriched.get("logo_identity_source") or "")
    return enriched, away, home, out_diag



def _query_selected_day() -> str:
    try:
        raw = st.query_params.get(prior_v163.DATE_QUERY_KEY)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "")[:10]


def _team_identity_v164(
    game: Mapping[str, Any],
    profile: Mapping[str, Any],
    visual: Mapping[str, Any],
    side: str,
) -> dict[str, Any]:
    """Fill one side's exact logo identity without replacing V163 identity state."""
    current = _FROZEN_TEAM_IDENTITY(game, profile, visual, side)
    if bool(current.get("exact_identity")):
        return current

    enriched = dict(game)
    event_id = logo_identity._event_id(enriched) or prior_v163._query_event_id()
    selected_day = logo_identity._game_date(enriched) or _query_selected_day()
    # NCAA schedule rows deliberately carry espn_event_id="" until ESPN
    # enrichment succeeds. setdefault() cannot replace that blank placeholder,
    # so explicitly fill the recovered exact query event before logo resolution.
    if event_id and not logo_identity._event_id(enriched):
        enriched["espn_event_id"] = event_id
    if selected_day:
        enriched.setdefault("game_date", selected_day)

    selector_payload = _selector_payload_for_day(selected_day)
    enriched = logo_identity.enrich_exact_team_ids(enriched, selector_payload)
    exact_visuals = _FROZEN_RESOLVE_VISUALS(enriched)
    side_visual = exact_visuals.get(side) if isinstance(exact_visuals.get(side), Mapping) else {}
    return _FROZEN_TEAM_IDENTITY(enriched, profile, side_visual, side)


def _final_presentation_identity_v164(
    identity: Mapping[str, Any],
    display_game: Mapping[str, Any],
) -> dict[str, Any]:
    """Inject exact ESPN logo identity at the final V160 presentation boundary."""
    output = dict(identity or {})
    enriched = dict(display_game or {})
    event_id = logo_identity._event_id(enriched) or prior_v163._query_event_id()
    selected_day = logo_identity._game_date(enriched) or _query_selected_day()
    if event_id:
        enriched.setdefault("espn_event_id", event_id)
    if selected_day:
        enriched.setdefault("game_date", selected_day)

    selector_payload = _selector_payload_for_day(selected_day)
    enriched = logo_identity.enrich_exact_team_ids(enriched, selector_payload)
    visuals = _FROZEN_RESOLVE_VISUALS(enriched)
    for side in ("away", "home"):
        visual = visuals.get(side) if isinstance(visuals.get(side), Mapping) else {}
        team_id = str(visual.get("team_id") or "").strip()
        logo = str(visual.get("logo") or "").strip()
        if not (bool(visual.get("exact_identity")) and team_id.isdigit() and logo):
            continue
        side_state = dict(output.get(side) or {})
        side_state["team_id"] = team_id
        side_state["logo"] = logo
        side_state["exact_identity"] = True
        output[side] = side_state
    return output


def _resolve_visuals_v164(game: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return logo_identity.resolve_visuals(
        game,
        _FROZEN_RESOLVE_VISUALS,
        _selector_payload_for_game(game),
    )


def _render_v164_identity() -> None:
    st.markdown(
        '<div data-testid="cfb-game-total-v164-active" '
        'style="display:none!important">'
        f'{ACTIVE_MARKER} • {DEPLOYMENT_PROOF_MARKER} • {STEP1_PRESENTATION_MARKER} • {STEP1_PROFILE_MARKER} • {STEP2_PRESENTATION_MARKER} • {STEP3_PRESENTATION_MARKER} • {STEP4_PRESENTATION_MARKER} • exact ESPN team logos • V163 frozen parent • '
        'sportsbook projection influence 0.0%</div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    original_resolver = frozen_logo.resolve_visuals
    original_reconcile = runtime_display.reconcile_display_bundle
    original_team_identity = identity_owner._team_identity
    original_target_matchup = presentation_owner._target_matchup_header_html
    original_target_evidence = presentation_owner._target_team_evidence_html
    original_step_evidence = compact_owner._step_evidence_html
    rendered_identity: dict[str, Any] = {}

    def target_matchup_v164(identity, away, home, display_game):
        exact_identity = _final_presentation_identity_v164(identity, display_game)
        rendered_identity["value"] = exact_identity
        return original_target_matchup(exact_identity, away, home, display_game)

    def target_evidence_v164(identity, away, home):
        exact_identity = rendered_identity.get("value") or identity
        rendered_identity["away_stats"] = dict(away or {})
        rendered_identity["home_stats"] = dict(home or {})
        return original_target_evidence(exact_identity, away, home)

    def _merge_step2_evidence(*rows):
        merged: dict[str, Any] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            for key, value in row.items():
                if value in (None, "", "—", [], {}):
                    continue
                if isinstance(value, str) and value.strip().lower() in {
                    "unavailable",
                    "data limited",
                    "record unavailable",
                }:
                    continue
                merged[key] = value
        return merged

    def _step3_certified_foundation(display_game):
        selected_day = logo_identity._game_date(display_game) or _query_selected_day()
        if not selected_day:
            return {}, {}
        try:
            bundle, _diag = step3_data_owner.load_matchup_team_data(
                dict(display_game or {}),
                selected_day,
            )
        except Exception:
            return {}, {}
        if not isinstance(bundle, Mapping):
            return {}, {}
        away_foundation = bundle.get("away") if isinstance(bundle.get("away"), Mapping) else {}
        home_foundation = bundle.get("home") if isinstance(bundle.get("home"), Mapping) else {}
        return dict(away_foundation), dict(home_foundation)

    def step_evidence_v164(number, title, status, detail, identity, away, home, display_game, model):
        if int(number) == 1:
            exact_identity = rendered_identity.get("value") or identity
            step_away = dict(away or {})
            step_home = dict(home or {})
            away_stats = rendered_identity.get("away_stats") or {}
            home_stats = rendered_identity.get("home_stats") or {}
            if away_stats.get("record") not in (None, "", "—"):
                step_away["record"] = away_stats.get("record")
            if home_stats.get("record") not in (None, "", "—"):
                step_home["record"] = home_stats.get("record")

            # Step 1 needs the same exact event handoff already proven for V164
            # logos. The V9 display copy can still carry espn_event_id="" even
            # when final presentation identity has exact team IDs.
            step_game = dict(display_game or {})
            event_id = logo_identity._event_id(step_game) or prior_v163._query_event_id()
            selected_day = logo_identity._game_date(step_game) or _query_selected_day()
            if event_id and not logo_identity._event_id(step_game):
                step_game["espn_event_id"] = event_id
            if selected_day:
                step_game.setdefault("game_date", selected_day)
            step_game = logo_identity.enrich_exact_team_ids(
                step_game,
                _selector_payload_for_day(selected_day),
            )

            step_away, step_home, _ = step1_profile_owner.enrich_step1_inputs(
                exact_identity,
                step_away,
                step_home,
                step_game,
            )
            rendered_identity["step1_away"] = dict(step_away)
            rendered_identity["step1_home"] = dict(step_home)
            return step1_owner.render_step1_html(
                status,
                exact_identity,
                step_away,
                step_home,
                step_game,
            )
        if int(number) == 2:
            exact_identity = rendered_identity.get("value") or identity
            step2_foundation_away, step2_foundation_home = _step3_certified_foundation(
                display_game
            )
            # Certified NCAA/runtime current-season evidence wins over stale
            # presentation/profile values for scoring, form and split fields.
            step2_away = _merge_step2_evidence(
                away,
                rendered_identity.get("away_stats") or {},
                rendered_identity.get("step1_away") or {},
                step2_foundation_away,
            )
            step2_home = _merge_step2_evidence(
                home,
                rendered_identity.get("home_stats") or {},
                rendered_identity.get("step1_home") or {},
                step2_foundation_home,
            )

            selected_day = logo_identity._game_date(display_game) or _query_selected_day()
            try:
                step2_season = int(str(selected_day or "")[:4])
            except (TypeError, ValueError):
                step2_season = date.today().year
            step2_away, step2_home, step2_drive_diag = (
                step2_drive_owner.enrich_step2_drive_metrics(
                    step2_away,
                    step2_home,
                    step2_season,
                )
            )
            rendered_identity["step2_drive_diag"] = dict(step2_drive_diag)
            rendered_identity["step2_away"] = dict(step2_away)
            rendered_identity["step2_home"] = dict(step2_home)
            return step2_owner.render_step2_html(
                status,
                exact_identity,
                step2_away,
                step2_home,
            )
        if int(number) == 3:
            exact_identity = rendered_identity.get("value") or identity
            step3_foundation_away, step3_foundation_home = _step3_certified_foundation(
                display_game
            )
            step3_away = _merge_step2_evidence(
                step3_foundation_away,
                away,
                rendered_identity.get("away_stats") or {},
                rendered_identity.get("step1_away") or {},
                rendered_identity.get("step2_away") or {},
            )
            step3_home = _merge_step2_evidence(
                step3_foundation_home,
                home,
                rendered_identity.get("home_stats") or {},
                rendered_identity.get("step1_home") or {},
                rendered_identity.get("step2_home") or {},
            )

            step3_game = dict(display_game or {})
            event_id = logo_identity._event_id(step3_game) or prior_v163._query_event_id()
            selected_day = logo_identity._game_date(step3_game) or _query_selected_day()
            if event_id and not logo_identity._event_id(step3_game):
                step3_game["espn_event_id"] = event_id
            if selected_day and not str(step3_game.get("game_date") or "").strip():
                step3_game["game_date"] = selected_day
            step3_game = logo_identity.enrich_exact_team_ids(
                step3_game,
                _selector_payload_for_day(selected_day),
            )
            step3_away, step3_home, step3_diag = step3_owner.enrich_step3_inputs(
                exact_identity,
                step3_away,
                step3_home,
                step3_game,
            )
            rendered_identity["step3_away"] = dict(step3_away)
            rendered_identity["step3_home"] = dict(step3_home)
            rendered_identity["step3_diag"] = dict(step3_diag or {})

            diag_summary = {}
            for side_name in ("away", "home"):
                row = dict((step3_diag or {}).get(side_name) or {})
                attempts = []
                for attempt in list(row.get("attempts") or [])[:20]:
                    if isinstance(attempt, Mapping):
                        attempts.append({
                            "provider": str(attempt.get("provider") or "")[:120],
                            "http": attempt.get("http"),
                            "bytes": attempt.get("bytes"),
                            "error": str(attempt.get("error") or "")[:220],
                        })
                diag_summary[side_name] = {
                    "team_id": row.get("team_id"),
                    "source": row.get("source"),
                    "rows": row.get("rows"),
                    "team_schedule_rows": row.get("team_schedule_rows"),
                    "scoreboard_rows": row.get("scoreboard_rows"),
                    "scoreboard_range_rows": row.get("scoreboard_range_rows"),
                    "candidate_days": row.get("candidate_days"),
                    "scoreboard_quality_universe": row.get("scoreboard_quality_universe"),
                    "runtime_v2": row.get("runtime_v2"),
                    "runtime_v2_contract_state": row.get("runtime_v2_contract_state"),
                    "ncaa_combined": row.get("ncaa_combined"),
                    "ncaa_contract_state": row.get("ncaa_contract_state"),
                    "strength_of_schedule_rank": row.get("strength_of_schedule_rank"),
                    "opponent_record_resolution": row.get("opponent_record_resolution"),
                    "opponent_defense_rank_resolution": row.get("opponent_defense_rank_resolution"),
                    "attempts": attempts,
                }
            diag_summary["game"] = {
                "game_date": step3_game.get("game_date"),
                "espn_event_id": step3_game.get("espn_event_id"),
                "away_espn_team_id": step3_game.get("away_espn_team_id"),
                "home_espn_team_id": step3_game.get("home_espn_team_id"),
                "selected_day": selected_day,
            }

            step3_html = step3_owner.render_step3_html(
                status,
                exact_identity,
                step3_away,
                step3_home,
            )
            diag_attr = escape(
                json.dumps(diag_summary, sort_keys=True, default=str),
                quote=True,
            )
            return step3_html.replace(
                'data-step3-state="',
                f'data-step3-diag="{diag_attr}" data-step3-state="',
                1,
            )
        if int(number) == 4:
            exact_identity = rendered_identity.get("value") or identity
            step4_foundation_away, step4_foundation_home = _step3_certified_foundation(
                display_game
            )
            step4_away = _merge_step2_evidence(
                step4_foundation_away,
                away,
                rendered_identity.get("away_stats") or {},
                rendered_identity.get("step1_away") or {},
                rendered_identity.get("step2_away") or {},
                rendered_identity.get("step3_away") or {},
            )
            step4_home = _merge_step2_evidence(
                step4_foundation_home,
                home,
                rendered_identity.get("home_stats") or {},
                rendered_identity.get("step1_home") or {},
                rendered_identity.get("step2_home") or {},
                rendered_identity.get("step3_home") or {},
            )
            return step4_owner.render_step4_html(
                status,
                exact_identity,
                step4_away,
                step4_home,
            )
        return original_step_evidence(number, title, status, detail, identity, away, home, display_game, model)

    frozen_logo.resolve_visuals = _resolve_visuals_v164
    runtime_display.reconcile_display_bundle = _reconcile_display_bundle_v164
    identity_owner._team_identity = _team_identity_v164
    presentation_owner._target_matchup_header_html = target_matchup_v164
    presentation_owner._target_team_evidence_html = target_evidence_v164
    compact_owner._step_evidence_html = step_evidence_v164
    st.markdown(step1_owner.STEP1_CSS + step2_owner.STEP2_CSS + step3_owner.STEP3_CSS + step4_owner.STEP4_CSS, unsafe_allow_html=True)
    _render_v164_identity()
    try:
        result = prior_v163.render_game_total_hub(section_header, status_info, team_logo, h)
        st.markdown(step1_owner.STEP1_CSS + step2_owner.STEP2_CSS + step3_owner.STEP3_CSS, unsafe_allow_html=True)
        return result
    finally:
        compact_owner._step_evidence_html = original_step_evidence
        presentation_owner._target_team_evidence_html = original_target_evidence
        presentation_owner._target_matchup_header_html = original_target_matchup
        identity_owner._team_identity = original_team_identity
        runtime_display.reconcile_display_bundle = original_reconcile
        frozen_logo.resolve_visuals = original_resolver


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V164 Game Total V15 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "DEPLOYMENT_PROOF_MARKER",
    "FROZEN_PRESENTATION",
    "LOGO_POLICY",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP1_PRESENTATION_MARKER",
    "STEP1_PROFILE_MARKER",
    "STEP2_PRESENTATION_MARKER",
    "STEP3_PRESENTATION_MARKER",
    "STEP4_PRESENTATION_MARKER",
    "_final_presentation_identity_v164",
    "_team_identity_v164",
    "_query_selected_day",
    "_reconcile_display_bundle_v164",
    "_resolve_visuals_v164",
    "_selector_payload_for_day",
    "_selector_payload_for_game",
    "render_cfb_hub",
    "render_game_total_hub",
]
