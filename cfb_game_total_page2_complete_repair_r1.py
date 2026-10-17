"""MONSTER CFB Game Total Page 2 — complete selected-game repair R1.

Direct selected-event renderer replacing the legacy injected-tail composition.
The frozen Game Total analyzer remains authoritative. Page 2 loads exactly the
event carried by the Page-1 handoff, enriches display evidence through existing
verified multi-source owners, and keeps sportsbook data at 0.0 projection weight.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from typing import Any

import streamlit as st

import cfb_game_total_clean_page_v9 as frozen_runtime
import cfb_game_total_clean_page_v23 as team_evidence_ui
import cfb_game_total_page1_market_truth_r5 as market_truth
import cfb_game_total_page2_line_lab_v2 as line_lab
import cfb_game_total_page2_live_data_unified_repair_v1 as live_data
import cfb_game_total_page2_step8_final_runtime_v1 as page2
import streamlit_memory_lazy_router_cfb_game_total_page1_daily_slate_v1 as page1_market_transport
import streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1 as cfb_router

MODEL_VERSION = "MONSTER CFB GAME TOTAL PAGE2 COMPLETE REPAIR R1"
ACTIVE_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_COMPLETE_REPAIR_R1_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_COMPLETE_REPAIR_R1_FROZEN"
SAME_PAGE_ROUTE = "cfb_game_total_page2_complete_repair_r1"
MARKET = page2.MARKET
DATE_QUERY_KEY = "ks_cfb_game_total_date"
SELECTED_GAME_ONLY = True
MULTI_SOURCE_REQUIRED = True
LEGACY_TAIL_SUPPRESSED = True
CUSTOM_LINE_MAY_MODIFY_BEST_BET = False
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STRAY_MARKUP_GUARD = "no raw closing-tag payloads"

_PAGE_CSS = r"""
<style>
.gtp2r1-source{max-width:1180px;margin:0 auto 12px;padding:9px 11px;border:1px solid rgba(86,202,246,.22);border-radius:12px;background:rgba(6,29,43,.82);color:#91adbd;font-size:8px;font-weight:800;line-height:1.45}.gtp2r1-source b{color:#82e4ff}.gtp2r1-line{max-width:1180px;margin:0 auto 20px;padding:14px;border:1px solid rgba(75,197,255,.34);border-radius:20px;background:linear-gradient(180deg,rgba(7,27,41,.98),rgba(4,15,24,.99));color:#f7fbff}.gtp2r1-line-head{display:flex;align-items:end;justify-content:space-between;gap:12px;margin-bottom:10px}.gtp2r1-line-head span{color:#66d9ff;font-size:8px;font-weight:1000;letter-spacing:.13em;text-transform:uppercase}.gtp2r1-line-head h3{margin:4px 0 0;font-size:20px}.gtp2r1-line-head em{font-style:normal;color:#83dfff;font-size:7px;font-weight:950;text-transform:uppercase}.gtp2r1-presets{display:flex;flex-wrap:wrap;gap:7px;margin:3px 0 8px}.gtp2r1-results{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:10px}.gtp2r1-results article{padding:11px 9px;border:1px solid rgba(84,163,196,.18);border-radius:11px;background:rgba(7,28,42,.80);text-align:center}.gtp2r1-results span{display:block;color:#7899ac;font-size:6px;font-weight:950;letter-spacing:.07em;text-transform:uppercase}.gtp2r1-results strong{display:block;margin-top:5px;color:#f8fdff;font-size:14px;font-weight:1000}.gtp2r1-results .over strong{color:#72e0ff}.gtp2r1-results .under strong{color:#7ce9c0}.gtp2r1-results .push strong{color:#ffd47a}.gtp2r1-note{margin:9px 0 0;color:#8ba6b6;font-size:8px;font-weight:760;line-height:1.45}.gtp2r1-team-wrap{max-width:1180px;margin:0 auto 20px}.gtp2r1-team-head{padding:12px 14px;border:1px solid rgba(91,192,255,.28);border-radius:16px 16px 0 0;background:rgba(7,28,43,.96);color:#fff}.gtp2r1-team-head span{display:block;color:#76dfff;font-size:8px;font-weight:1000;letter-spacing:.13em;text-transform:uppercase}.gtp2r1-team-head h3{margin:5px 0 0;font-size:20px}.gtp2r1-cert{max-width:1180px;margin:0 auto 18px;padding:10px 12px;border:1px solid rgba(71,224,174,.25);border-radius:12px;background:rgba(8,56,47,.22);color:#80efc3;font-size:8px;font-weight:950;text-align:center;letter-spacing:.04em}div[data-testid="stSlider"]{max-width:1180px;margin:0 auto}.st-key-gtp2r1-line-slider label{font-weight:900!important}
@media(max-width:760px){.gtp2r1-results{grid-template-columns:repeat(3,minmax(0,1fr))}.gtp2r1-line-head{align-items:start;flex-direction:column}}@media(max-width:480px){.gtp2r1-results{grid-template-columns:repeat(2,minmax(0,1fr))}.gtp2r1-line{padding:11px;border-radius:16px}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _event_id(game: Mapping[str, Any]) -> str:
    for key in ("event_id", "espn_event_id", "game_id", "id"):
        value = _clean(game.get(key))
        if value:
            return value
    return ""


def _query_value(key: str) -> str:
    return cfb_router._query_value(key)


def _selected_identity() -> tuple[str, str] | None:
    event_id = _query_value(cfb_router.EVENT_QUERY_KEY)
    sync_id = _query_value(cfb_router.SELECTOR_SYNC_QUERY_KEY)
    day = _query_value(DATE_QUERY_KEY)[:10]
    if not event_id or sync_id != event_id or not day:
        return None
    return day, event_id


def _market_truth_games(games: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    action_games = None
    try:
        direct = page1_market_transport._fetch_action_json_board()
        if direct:
            action_games = direct
    except Exception:
        action_games = None
    return market_truth.enrich_games_with_market_truth(games, action_games=action_games)


def _selected_game(day: str, event_id: str) -> tuple[dict[str, Any] | None, Mapping[str, Any]]:
    games, diagnostics = frozen_runtime.frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(day)
    enriched = _market_truth_games([g for g in games if isinstance(g, Mapping)])
    for game in enriched:
        if _event_id(game) == event_id:
            return game, diagnostics
    return None, diagnostics


def _apply_featured_market(display_game: Mapping[str, Any], selected_game: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(display_game)
    observations = [row for row in selected_game.get("market_observations") or [] if isinstance(row, Mapping)]
    quote, quotes = market_truth.select_featured_book_quote(observations)
    if quote is None:
        fallback = page2._enrich_page2_market_context(out)
        return dict(fallback) if isinstance(fallback, Mapping) else out
    out.update({
        "market_total": quote.get("total"),
        "verified_market_total": quote.get("total"),
        "market_sportsbook": quote.get("book"),
        "verified_total_market_provider": quote.get("book"),
        "market_identity_verified": True,
        "market_projection_weight": 0.0,
        "market_context_only": True,
        "market_may_modify_projection": False,
        "market_source": "Action Network multi-book + existing ESPN/Kyre observations",
        "market_quote_count": len(quotes),
        "market_books": sorted(quotes),
        "market_observed_at_utc": quote.get("observed_at_utc"),
    })
    return out


def _build_payload(game: Mapping[str, Any], day: str) -> dict[str, Any]:
    result = frozen_runtime.frozen_page.slate.analyze_game(game, day)
    frozen_away, frozen_home = _mapping(result.get("away")), _mapping(result.get("home"))
    raw, final = _mapping(result.get("raw")), _mapping(result.get("final"))
    display_game, display_away, display_home, _ = frozen_runtime.runtime_display.reconcile_display_bundle(
        game, day, frozen_away, frozen_home
    )
    display_game = _apply_featured_market(display_game, game)
    visuals = frozen_runtime.logo_v3.resolve_visuals(display_game)
    identity = frozen_runtime.step_owner.prior.prior.prior._identity_state(
        display_game, display_away, display_home, visuals
    )
    away = frozen_runtime.step_owner.prior.prior._team_stats_state(display_away, display_game, "away")
    home = frozen_runtime.step_owner.prior.prior._team_stats_state(display_home, display_game, "home")
    away_evidence = frozen_runtime.step_owner.prior._team_evidence_state(display_away, display_game, "away")
    home_evidence = frozen_runtime.step_owner.prior._team_evidence_state(display_home, display_game, "home")
    statuses = frozen_runtime.step_owner._existing_step_status(identity, away_evidence, home_evidence, display_game)
    payload = {
        "identity": identity,
        "away": away,
        "home": home,
        "display_game": display_game,
        "raw": raw,
        "final": final,
        "statuses": statuses,
        "ready_count": sum(1 for n in range(1, 11) if statuses.get(n) == "READY") + int(bool(raw.get("ready"))) + int(bool(final.get("ready"))),
        "away_logo_html": frozen_runtime._matchup_header_html(identity, away, home, display_game),
        "home_logo_html": "",
    }
    # The verified adapter can consult the already-certified form, pace, scoring,
    # ESPN/Kyre and SportsDataverse owners. It cannot mutate frozen model truth.
    try:
        payload = live_data._live_enrich(payload)
    except Exception:
        pass
    return payload


def _header_html(payload: Mapping[str, Any], day: str) -> str:
    html = page2.build_page2_header_html(payload)
    old_href = "?ks_jump_sport=CFB&amp;ks_jump_market=Game+Total"
    back_href = f"?sport=cfb&amp;market=game-total&amp;date={escape(day, quote=True)}&amp;ks_cfb_game_total_date={escape(day, quote=True)}"
    html = html.replace(old_href, back_href).replace("← Back to Slate", "← Back to CFB Game Totals")
    return html


def _profile_values(payload: Mapping[str, Any]):
    identity, away, home, display_game, raw, final = map(
        _mapping,
        (payload.get("identity"), payload.get("away"), payload.get("home"), payload.get("display_game"), payload.get("raw"), payload.get("final")),
    )
    away_name = page2._first(_mapping(identity.get("away")), "team", "name") or page2._first(away, "team", "name")
    home_name = page2._first(_mapping(identity.get("home")), "team", "name") or page2._first(home, "team", "name")
    return identity, away, home, display_game, raw, final, away_name, home_name


def _render_source_strip(display_game: Mapping[str, Any]) -> None:
    book = _clean(display_game.get("market_sportsbook") or display_game.get("verified_total_market_provider")) or "verified market"
    count = int(display_game.get("market_quote_count") or 0)
    books = ", ".join(display_game.get("market_books") or [])
    market_text = f"{escape(book)} • {count} complete book quote{'s' if count != 1 else ''}"
    if books:
        market_text += f" • {escape(books)}"
    st.markdown(
        _PAGE_CSS
        + '<div class="gtp2r1-source"><b>MULTI-SOURCE VERIFIED PAGE 2</b> • '
        + market_text
        + ' • team/form/pace/scoring evidence uses the existing verified CFB owner stack; unavailable fields fail soft rather than fabricate.</div>',
        unsafe_allow_html=True,
    )


def _render_outlook_snapshot_trends(payload: Mapping[str, Any], day: str) -> None:
    identity, away, home, display_game, raw, final, away_name, home_name = _profile_values(payload)
    projected = page2._projected(raw, final)
    market = page2._market_line(raw, display_game)
    edge = page2._display_edge(projected, market)
    over, under = page2._distribution_line_probabilities(raw, market)
    if over is None and under is None:
        over, under = raw.get("over_probability"), raw.get("under_probability")
    outlook = page2.step4.build_outlook_projection_summary_html(
        over_probability=page2.data_quality.format_optional_percent(over) or "No verified Over probability available",
        under_probability=page2.data_quality.format_optional_percent(under) or "No verified Under probability available",
        projected_total=page2.data_quality.display_number(projected, missing="No verified projected total available"),
        market_line=page2.data_quality.display_number(market, missing="No verified market total available"),
        edge=page2.data_quality.display_number(edge, missing="No verified edge available"),
        confidence_label=page2._first(final, "grade", "confidence_label") or page2._percent(page2._first(final, "forecast_strength", "confidence")),
    )
    favorable = raw.get("favorable_for") if isinstance(raw.get("favorable_for"), Mapping) else {}
    away_pace = page2._team_profile_value(away, "plays_per_game", "expected_plays", "pace", "pace_label")
    home_pace = page2._team_profile_value(home, "plays_per_game", "expected_plays", "pace", "pace_label")
    away_explosive = page2._team_profile_value(away, "yards_per_play", "explosive_rate", "explosive_efficiency", "explosive")
    home_explosive = page2._team_profile_value(home, "yards_per_play", "explosive_rate", "explosive_efficiency", "explosive")
    away_red_zone = page2._team_profile_value(away, "red_zone_td_rate", "red_zone_rate", "red_zone")
    home_red_zone = page2._team_profile_value(home, "red_zone_td_rate", "red_zone_rate", "red_zone")
    away_defense = page2._team_profile_value(away, "points_allowed_pg", "points_allowed", "defensive_efficiency", "defense")
    home_defense = page2._team_profile_value(home, "points_allowed_pg", "points_allowed", "defensive_efficiency", "defense")
    snapshot = page2.step5.build_team_snapshot_key_drivers_html(
        away_team=away_name, home_team=home_name,
        away_pace=page2._display_profile_number(away_pace), home_pace=page2._display_profile_number(home_pace),
        away_explosive=page2._display_explosive(away_explosive), home_explosive=page2._display_explosive(home_explosive),
        away_red_zone=page2._display_profile_percent(away_red_zone), home_red_zone=page2._display_profile_percent(home_red_zone),
        away_defense=page2._display_profile_number(away_defense), home_defense=page2._display_profile_number(home_defense),
        favorable_for=favorable,
    )
    scoring_map = raw.get("scoring_breakdown") if isinstance(raw.get("scoring_breakdown"), Mapping) else {}
    scoring_map = {key: (page2._display_profile_number(value) if key in {"away_1h", "home_1h", "away_2h", "home_2h", "q1", "q2", "q3", "q4"} else value) for key, value in scoring_map.items()}
    recent_totals = raw.get("recent_totals") if isinstance(raw.get("recent_totals"), Sequence) and not isinstance(raw.get("recent_totals"), (str, bytes)) else []
    trends = page2.step6.build_trends_scoring_breakdown_html(
        recent_totals=recent_totals,
        market_line=page2.data_quality.display_number(market, missing="No verified market total available"),
        scoring_breakdown=scoring_map,
        explosive_scoring=page2._display_trend_number(page2._first(raw, "explosive_scoring", "explosive_scoring_label"), missing="No verified explosive-scoring data available"),
        scoring_opportunities=page2._display_trend_number(page2._first(raw, "scoring_opportunities", "scoring_opportunity_rate"), missing="No verified scoring-opportunity data available"),
        red_zone_finishing=page2._display_trend_percent(page2._first(raw, "red_zone_finishing", "red_zone_finish_rate"), missing="No verified red-zone finishing data available"),
        away_team=away_name, home_team=home_name, away_profile=away, home_profile=home, as_of_day=day,
    )
    st.markdown(outlook + snapshot + trends, unsafe_allow_html=True)


def _preset_values(market: Any) -> list[float]:
    base = line_lab.clamp_line(market, fallback=50.0)
    values = [line_lab.clamp_line(base - 3.0), base, line_lab.clamp_line(base + 3.0)]
    return list(dict.fromkeys(values))


def _render_line_lab(payload: Mapping[str, Any], event_id: str) -> None:
    _, _, _, display_game, raw, final, _, _ = _profile_values(payload)
    market = page2._market_line(raw, display_game)
    projected = page2._projected(raw, final)
    default = line_lab.clamp_line(market, fallback=page2._number(projected) or 50.0)
    key = f"gtp2r1_line_lab_{event_id}"
    if key not in st.session_state:
        st.session_state[key] = default

    st.markdown(
        _PAGE_CSS
        + '<section class="gtp2r1-line" data-line-lab-analysis-only="true"><div class="gtp2r1-line-head"><div><span>Stage 4 • Line Lab</span><h3>Move the Total Line</h3></div><em>Frozen distribution • no model rerun</em></div><p class="gtp2r1-note">Choose any half-point from 0.0 to 60.0. The verified market line remains the Best Bet benchmark.</p></section>',
        unsafe_allow_html=True,
    )
    presets = _preset_values(market)
    columns = st.columns(len(presets)) if presets else []
    for index, value in enumerate(presets):
        market_badge = " • MARKET" if page2._number(market) is not None and abs(float(market) - value) < 1e-9 else ""
        if columns[index].button(f"{value:.1f}{market_badge}", key=f"gtp2r1_preset_{event_id}_{value:.1f}", use_container_width=True):
            st.session_state[key] = value

    selected_line = float(
        st.slider(
            "Move total line",
            min_value=line_lab.LINE_MIN,
            max_value=line_lab.LINE_MAX,
            step=line_lab.LINE_STEP,
            key=key,
            help="Analysis-only threshold from the already-owned frozen distribution. This never reruns the model or changes Best Bet.",
        )
    )
    probabilities = line_lab.line_probabilities(raw.get("distribution"), selected_line)
    if probabilities is None or raw.get("distribution_ready") is not True:
        st.info("Frozen distribution probabilities are unavailable for this game. The Line Lab fails soft and does not invent a probability.")
        return
    over, under, push = probabilities["over"], probabilities["under"], probabilities["push"]
    lean = "OVER" if over > under else ("UNDER" if under > over else "EVEN")
    projected_number = page2._number(projected)
    difference = None if projected_number is None else projected_number - selected_line
    difference_text = "—" if difference is None else f"{difference:+.1f}"
    projected_text = page2.data_quality.format_optional_number(projected) or "—"
    grade = escape(_clean(page2._first(final, "grade", "confidence_label", "confidence")) or "—")
    st.markdown(
        '<div class="gtp2r1-line" data-line-lab-analysis-only="true">'
        '<div class="gtp2r1-results">'
        f'<article><span>Selected Line</span><strong>{selected_line:.1f}</strong></article>'
        f'<article class="over"><span>Over</span><strong>{line_lab.percent(over)}</strong></article>'
        f'<article class="under"><span>Under</span><strong>{line_lab.percent(under)}</strong></article>'
        f'<article class="push"><span>Push</span><strong>{line_lab.percent(push)}</strong></article>'
        f'<article><span>Projected Total</span><strong>{escape(projected_text)}</strong></article>'
        f'<article><span>Projection Diff</span><strong>{difference_text}</strong></article>'
        '</div>'
        f'<p class="gtp2r1-note"><b>Model lean:</b> {lean} • <b>Grade:</b> {grade} • Over + Under + Push = 100% of valid frozen probability mass.</p></div>',
        unsafe_allow_html=True,
    )


def _render_best_bet(payload: Mapping[str, Any]) -> None:
    _, _, _, display_game, raw, final, _, _ = _profile_values(payload)
    recommendation = dict(page2._recommendation(raw, final, display_game))
    expected = page2._number(recommendation.get("expected_total"))
    if expected is not None:
        recommendation["expected_total"] = round(expected, 1)
    st.markdown(page2.stage5.build_best_bet_html(recommendation), unsafe_allow_html=True)


def _render_matchup_and_team_evidence(payload: Mapping[str, Any]) -> None:
    identity, away, home, display_game, _, _, _, _ = _profile_values(payload)
    matchup = page2._matchup_contract(identity, away, home, display_game)
    st.markdown(page2.stage6.build_tough_favorable_html(matchup), unsafe_allow_html=True)

    def team_profile(source: Mapping[str, Any]) -> dict[str, Any]:
        out = dict(source)
        ppg = page2._number(page2._first(out, "ppg", "recent_ppg", "points_per_game"))
        allowed = page2._number(page2._first(out, "allowed_pg", "points_allowed_pg", "recent_points_allowed_pg"))
        if ppg is not None:
            out["ppg"] = ppg
        if allowed is not None:
            out["allowed_pg"] = allowed
        if ppg is not None and allowed is not None:
            out["point_diff_pg"] = ppg - allowed
        return out

    evidence = team_evidence_ui._team_evidence_html_v23(identity, team_profile(away), team_profile(home))
    # gt204-team-evidence is the existing verified Team Evidence card contract.
    st.markdown(
        '<section class="gtp2r1-team-wrap" data-testid="gtp2r1-team-evidence"><div class="gtp2r1-team-head"><span>Stage 7 • Evidence</span><h3>Team Evidence</h3></div>'
        + evidence
        + '</section>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    selected = _selected_identity()
    if selected is None:
        st.error("Selected-game identity is incomplete. Return to CFB Game Totals and tap a game again.")
        st.markdown('<a href="?sport=cfb&market=game-total" target="_self">← Back to CFB Game Totals</a>', unsafe_allow_html=True)
        return None
    day, event_id = selected
    game, diagnostics = _selected_game(day, event_id)
    if game is None:
        st.error("That exact selected game is not present in the verified slate. Page 2 will not substitute another matchup.")
        st.markdown(f'<a href="?sport=cfb&market=game-total&date={escape(day, quote=True)}" target="_self">← Back to CFB Game Totals</a>', unsafe_allow_html=True)
        return None

    payload = _build_payload(game, day)
    if _event_id(_mapping(payload.get("display_game"))) != event_id:
        st.error("Selected-event identity verification failed. No alternate game was rendered.")
        return None

    st.markdown(_header_html(payload, day), unsafe_allow_html=True)
    _render_source_strip(_mapping(payload.get("display_game")))
    _render_outlook_snapshot_trends(payload, day)
    _render_line_lab(payload, event_id)
    _render_best_bet(payload)
    _render_matchup_and_team_evidence(payload)
    st.markdown(
        '<div class="gtp2r1-cert" data-testid="gtp2r1-cert" data-event-id="'
        + escape(event_id, quote=True)
        + '">EXACT SELECTED GAME • MULTI-SOURCE VERIFIED DISPLAY • FROZEN MODEL • SPORTSBOOK PROJECTION INFLUENCE 0.0%</div>',
        unsafe_allow_html=True,
    )
    return {"event_id": event_id, "date": day, "diagnostics": diagnostics}


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None):
    if market != MARKET:
        raise ValueError(f"Page2 complete repair received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


def render_selected_in_shared_shell():
    with cfb_router._ROUTE_POINTER_LOCK:
        original_page1 = cfb_router.PAGE1_NATIVE_ROUTE
        cfb_router.PAGE1_NATIVE_ROUTE = SAME_PAGE_ROUTE
        try:
            return cfb_router._render_page1_in_shared_shell()
        finally:
            cfb_router.PAGE1_NATIVE_ROUTE = original_page1


__all__ = [
    "ACTIVE_MARKER", "CUSTOM_LINE_MAY_MODIFY_BEST_BET", "FREEZE_TOKEN", "LEGACY_TAIL_SUPPRESSED",
    "MARKET", "MAY_MODIFY_MODEL", "MAY_MODIFY_OTHER_SPORTS", "MAY_MODIFY_PAGE1", "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION", "MAY_MODIFY_RANKING", "MAY_MODIFY_SELECTION", "MODEL_VERSION", "MULTI_SOURCE_REQUIRED",
    "SAME_PAGE_ROUTE", "SELECTED_GAME_ONLY", "SPORTSBOOK_PROJECTION_INFLUENCE", "render_cfb_hub",
    "render_game_total_hub", "render_selected_in_shared_shell",
]
