"""CFB Moneyline Premium V6 — runtime-base repair over frozen V5 presentation."""
from __future__ import annotations

import streamlit as st
import cfb_moneyline_clean_page_v5 as prior

MODEL_VERSION = "CFB MONEYLINE PREMIUM V6 • V5 RUNTIME BASE REPAIR"
FROZEN_MONEYLINE_OWNER = prior.FROZEN_MONEYLINE_OWNER
FROZEN_RAW_MODEL = prior.FROZEN_RAW_MODEL
FROZEN_FINAL_MODEL = prior.FROZEN_FINAL_MODEL
SPORTSBOOK_PROJECTION_INFLUENCE = prior.SPORTSBOOK_PROJECTION_INFLUENCE
MAY_MODIFY_PROJECTION = prior.MAY_MODIFY_PROJECTION
market_value_verdict = prior.market_value_verdict
human_reason_summary = prior.human_reason_summary


def render_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    # V5 accidentally stopped at V2. V1 owns datetime/Phoenix/schedule/slate helpers.
    base = prior.prior.prior.prior.prior
    st.markdown(prior.prior._CSS, unsafe_allow_html=True)
    st.markdown(prior._CSS, unsafe_allow_html=True)
    st.markdown('<div class="cfbm4-shell"><div class="cfbm4-eyebrow">KYRE SPORTS AI • CFB MONEYLINE</div><div class="cfbm4-title">College Football Moneyline</div><div class="cfbm4-sub">Decision-first matchup analytics with clean team evidence and transparent model detail.</div></div>', unsafe_allow_html=True)
    today_phoenix = base.datetime.now(base._PHOENIX).date()
    selected = st.date_input("CFB slate", value=today_phoenix, key="cfb_moneyline_premium_v4_date")
    selected_day = selected.isoformat()
    games, _ = base.schedule_v3.load_with_diagnostics(selected_day)
    if not games:
        st.warning("No verified upcoming FBS matchups are available for this slate. No pick is invented.")
        return
    index = st.selectbox("🏟️ Moneyline matchup", options=list(range(len(games))), format_func=lambda i: base._matchup_label(base._display_game(games[int(i)])), key=f"cfb_moneyline_premium_v4_matchup_{selected_day}")
    game = games[int(index)]
    selected_result = base.slate.analyze_game(game, selected_day)
    away = selected_result.get("away") or {}
    home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}
    team_diag = selected_result.get("team_diag") or {}
    display_game = prior.prior.prior._attach_verified_market(base._display_game(game))
    visuals = base._resolve_visuals(display_game)
    st.markdown(prior.prior._matchup_header(display_game, away, home, visuals=visuals), unsafe_allow_html=True)
    st.markdown(prior.prior._decision_html(display_game, raw, final), unsafe_allow_html=True)
    st.markdown(prior.prior._why_html(raw, final), unsafe_allow_html=True)
    st.markdown(prior.prior._freshness_html(display_game), unsafe_allow_html=True)
    away_name = prior._clean(away.get("team")) or prior._clean(display_game.get("away_team")) or "Away"
    home_name = prior._clean(home.get("team")) or prior._clean(display_game.get("home_team")) or "Home"
    with st.expander("🏟️ Team profiles & availability", expanded=False):
        st.markdown(prior._team_profiles_html(away, home, visuals=visuals), unsafe_allow_html=True)
    with st.expander("🔎 Data source details", expanded=False):
        st.markdown('<div class="cfbm5-detail-note">Source diagnostics are kept here for transparency without crowding the primary team cards. They remain evidence-only and do not alter certified betting probabilities.</div>', unsafe_allow_html=True)
        st.markdown(base.frozen.prior.frozen_step5.frozen_v3._team_data_diagnostics(team_diag), unsafe_allow_html=True)
    with st.expander("🧠 Model details", expanded=False):
        st.markdown(prior._model_dashboard_html(raw, final, away_name=away_name, home_name=home_name), unsafe_allow_html=True)
        st.markdown(prior._feature_contributions_html(raw, away_name=away_name, home_name=home_name), unsafe_allow_html=True)
    with st.expander("⚙️ Advanced model details", expanded=False):
        st.markdown('<div class="cfbm5-detail-note">Certified raw/pre-calibration and final synthesis outputs are preserved below for advanced transparency. This section does not change model behavior.</div>', unsafe_allow_html=True)
        st.markdown(base.frozen.prior.frozen_step5._model_card(game, away, home, raw), unsafe_allow_html=True)
        st.markdown(base.frozen._final_card(game, away, home, final), unsafe_allow_html=True)
        feature_html = base.frozen.prior.frozen_step5._feature_panel(raw)
        if feature_html:
            st.markdown(feature_html, unsafe_allow_html=True)
    with st.expander(f"🗓️ Full verified slate • {selected_day}", expanded=False):
        st.dataframe(base._slate_rows(games), use_container_width=True, hide_index=True)
    st.caption("Certified Moneyline probabilities and fair prices remain frozen. Verified sportsbook prices are comparison-only and carry 0.0% projection weight.")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if prior._clean(market).lower() == "moneyline":
        return render_moneyline_hub(section_header, status_info, team_logo, h)
    return prior.render_cfb_hub(market, section_header, status_info, team_logo, h)


__all__ = ["MODEL_VERSION", "FROZEN_MONEYLINE_OWNER", "SPORTSBOOK_PROJECTION_INFLUENCE", "MAY_MODIFY_PROJECTION", "market_value_verdict", "human_reason_summary", "render_moneyline_hub", "render_cfb_hub"]
