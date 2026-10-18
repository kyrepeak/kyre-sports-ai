"""CFB Moneyline Premium V2 — decision-first presentation over frozen V1/model owners."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st
import cfb_moneyline_clean_page_v1 as prior

MODEL_VERSION = "CFB MONEYLINE PREMIUM V2 • DECISION FIRST"
FROZEN_MONEYLINE_OWNER = prior.FROZEN_MONEYLINE_OWNER
FROZEN_RAW_MODEL = prior.FROZEN_RAW_MODEL
FROZEN_FINAL_MODEL = prior.FROZEN_FINAL_MODEL
SPORTSBOOK_PROJECTION_INFLUENCE = prior.SPORTSBOOK_PROJECTION_INFLUENCE
MAY_MODIFY_PROJECTION = prior.MAY_MODIFY_PROJECTION

_CSS = r"""
<style>
.cfbm2-wrap{margin:8px 0 14px;padding:16px;border:1px solid rgba(76,153,220,.28);border-radius:20px;background:linear-gradient(145deg,#07111d,#091522 64%,#10132a)}
.cfbm2-k{color:#86d7ff;font-size:.62rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase}.cfbm2-h{color:#f7fbff;font-size:1.45rem;font-weight:950;margin-top:4px}.cfbm2-sub{color:#91a4b8;font-size:.66rem;line-height:1.5;margin-top:5px}
.cfbm2-decision{display:grid;grid-template-columns:1.35fr repeat(3,minmax(0,.75fr));gap:8px;margin:10px 0}.cfbm2-main,.cfbm2-stat,.cfbm2-market,.cfbm2-reason{border:1px solid rgba(135,157,180,.17);border-radius:14px;background:#091725;padding:11px}
.cfbm2-main{border-color:rgba(155,113,255,.4);background:linear-gradient(145deg,rgba(73,40,128,.36),#091725)}.cfbm2-main small,.cfbm2-stat small,.cfbm2-market small,.cfbm2-reason small{display:block;color:#7f94a8;font-size:.33rem;font-weight:900;text-transform:uppercase}.cfbm2-main b{display:block;color:#fff;font-size:1.18rem;margin-top:4px}.cfbm2-main strong{display:block;color:#cab8ff;font-size:1.45rem;margin-top:4px}.cfbm2-stat b{display:block;color:#eef6fb;font-size:.82rem;margin-top:5px}.cfbm2-stat span,.cfbm2-main span{display:block;color:#8396a8;font-size:.38rem;line-height:1.4;margin-top:4px}
.cfbm2-market-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:7px}.cfbm2-market b{display:block;color:#f2f7fb;font-size:.65rem;margin-top:4px}.cfbm2-market em{display:block;color:#8ce5b4;font-style:normal;font-size:.36rem;margin-top:4px}.cfbm2-note{border-left:3px solid #7ed7ff;background:rgba(26,75,106,.18);padding:8px 10px;border-radius:0 10px 10px 0;color:#9fb0c0;font-size:.4rem;line-height:1.5;margin:7px 0 10px}
.cfbm2-reasons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.cfbm2-reason b{display:block;color:#edf4f8;font-size:.58rem;margin-top:4px}.cfbm2-reason span{display:block;color:#8498aa;font-size:.36rem;line-height:1.45;margin-top:4px}.cfbm2-reason.good{border-color:rgba(60,207,137,.28);background:rgba(20,72,52,.22)}.cfbm2-reason.warn{border-color:rgba(244,191,77,.26);background:rgba(83,62,18,.19)}
.cfbm2-section{margin:13px 0 7px;color:#eaf2f7;font-size:.58rem;font-weight:950;letter-spacing:.07em}.cfbm2-pass{border:1px solid rgba(244,191,77,.32);border-radius:14px;background:rgba(75,57,17,.22);padding:13px;color:#f7d982}.cfbm2-pass b{font-size:1rem}.cfbm2-pass span{display:block;color:#a89a74;font-size:.42rem;line-height:1.5;margin-top:4px}
@media(max-width:760px){.cfbm2-decision{grid-template-columns:1fr 1fr}.cfbm2-main{grid-column:1/-1}.cfbm2-reasons{grid-template-columns:1fr 1fr}}
@media(max-width:480px){.cfbm2-decision,.cfbm2-reasons{grid-template-columns:1fr}.cfbm2-main{grid-column:auto}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _pct(value: Any) -> str:
    return prior._pct(value)


def _odds(value: Any) -> str:
    return prior._odds(value)


def _num(value: Any, digits: int = 1, signed: bool = False) -> str:
    return prior._num(value, digits, signed)


def _decision_card(game: Mapping[str, Any], raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not final.get("ready"):
        reason = " • ".join(str(x) for x in final.get("reasons") or ["Verified model inputs are incomplete"])
        return f'<div class="cfbm2-pass"><b>PASS • NO QUALIFIED MODEL PICK</b><span>{escape(reason)}. The page stays fail-closed rather than manufacturing a recommendation.</span></div>'
    winner = _clean(final.get("winner_team")) or "Model leader"
    side = prior._winner_side(final)
    fair = final.get("home_fair_moneyline") if side == "home" else final.get("away_fair_moneyline")
    probability = final.get("winner_probability_final")
    grade = _clean(final.get("model_grade")) or "—"
    tier = _clean(final.get("model_tier")) or "MODEL LEAN"
    confidence = _clean(raw.get("confidence")) or "CHECK"
    reliability = final.get("reliability")
    coverage = final.get("feature_coverage")
    return f'''<div class="cfbm2-section">🏆 MONEYLINE DECISION</div>
<div class="cfbm2-decision">
 <div class="cfbm2-main"><small>{escape(tier)} • MODEL PICK</small><b>{escape(winner)}</b><strong>{_pct(probability)}</strong><span>Model win probability • price-independent</span></div>
 <div class="cfbm2-stat"><small>Fair moneyline</small><b>{_odds(fair)}</b><span>Model fair price</span></div>
 <div class="cfbm2-stat"><small>Confidence</small><b>{escape(grade)}</b><span>{escape(confidence)} input confidence</span></div>
 <div class="cfbm2-stat"><small>Model health</small><b>{_pct(reliability)}</b><span>{_pct(coverage)} feature coverage</span></div>
</div>'''


def _price_value(value: Any, side: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(side)
    return None


def _market_price_strip(game: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    prices = game.get("sportsbook_moneylines")
    if not isinstance(prices, Mapping) or not prices:
        return '<div class="cfbm2-section">📈 MARKET CHECK</div><div class="cfbm2-note">No verified sportsbook moneyline is attached to this matchup payload. The model decision remains available and sportsbook influence stays 0%.</div>'
    side = prior._winner_side(final) or "home"
    cards = []
    for book, payload in prices.items():
        value = _price_value(payload, side)
        if value is None:
            continue
        updated = _clean(payload.get("updated_at")) if isinstance(payload, Mapping) else ""
        cards.append(f'<div class="cfbm2-market"><small>{escape(str(book))}</small><b>{_odds(value)}</b><em>DISPLAY ONLY • 0% model weight</em><span>{escape(updated)}</span></div>')
    if not cards:
        return '<div class="cfbm2-section">📈 MARKET CHECK</div><div class="cfbm2-note">No verified sportsbook moneyline is attached to this matchup payload. The model decision remains available and sportsbook influence stays 0%.</div>'
    return '<div class="cfbm2-section">📈 MARKET CHECK</div><div class="cfbm2-market-row">' + ''.join(cards) + '</div>'


def _why_this_pick(raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not raw.get("ready") or not final.get("ready"):
        return '<div class="cfbm2-section">💡 WHY THIS PICK</div><div class="cfbm2-note">Reasoning becomes available only when the verified model inputs are ready.</div>'
    comp = raw.get("components") or {}
    side = prior._winner_side(final)

    def delta(a: str, b: str):
        try:
            return float(comp.get(a)) - float(comp.get(b))
        except Exception:
            return None

    factors = [
        ("Scoring profile", delta("home_base_points", "away_base_points"), "Expected scoring baseline"),
        ("Recent form", delta("home_recent_adjustment", "away_recent_adjustment"), "Recent scoring adjustment"),
        ("Efficiency", delta("home_efficiency_adjustment", "away_efficiency_adjustment"), "Efficiency adjustment"),
        ("Turnovers", comp.get("turnover_edge_home_points"), "Turnover-margin effect"),
        ("Schedule strength", comp.get("sos_edge_home_points"), "Opponent-quality effect"),
        ("Home field", 0.0 if raw.get("neutral_site") else comp.get("home_field_points"), "Venue/context effect"),
    ]
    rows = []
    for label, value, detail in factors:
        try:
            n = float(value)
            supports = n >= 0 if side == "home" else n <= 0
            cls = "good" if supports and abs(n) > .05 else "warn" if abs(n) > .05 else ""
            val = _num(n, 1, True)
        except Exception:
            cls = ""
            val = "—"
        rows.append(f'<div class="cfbm2-reason {cls}"><small>{escape(label)}</small><b>{escape(val)}</b><span>{escape(detail)}</span></div>')
    return '<div class="cfbm2-section">💡 WHY THIS PICK</div><div class="cfbm2-reasons">' + ''.join(rows) + '</div>'


def render_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('''<div class="cfbm2-wrap"><div class="cfbm2-k">KYRE SPORTS AI • CFB MONEYLINE</div><div class="cfbm2-h">🏆 College Football Moneyline</div><div class="cfbm2-sub">Decision first. See the model pick, fair price and strongest football reasons immediately; deeper evidence stays available below.</div></div>''', unsafe_allow_html=True)
    today_phoenix = prior.datetime.now(prior._PHOENIX).date()
    selected = st.date_input("CFB slate", value=today_phoenix, key="cfb_moneyline_premium_v2_date")
    selected_day = selected.isoformat()
    games, schedule_diag = prior.schedule_v3.load_with_diagnostics(selected_day)
    if not games:
        st.warning("No verified upcoming FBS matchups are available for this slate. No pick is invented.")
        return
    index = st.selectbox("🏟️ Moneyline matchup", options=list(range(len(games))), format_func=lambda i: prior._matchup_label(prior._display_game(games[int(i)])), key=f"cfb_moneyline_premium_v2_matchup_{selected_day}")
    game = games[int(index)]
    selected_result = prior.slate.analyze_game(game, selected_day)
    away = selected_result.get("away") or {}
    home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}
    team_diag = selected_result.get("team_diag") or {}
    display_game = prior._display_game(game)
    st.markdown(_decision_card(display_game, raw, final), unsafe_allow_html=True)
    st.markdown(_market_price_strip(display_game, final), unsafe_allow_html=True)
    st.markdown(_why_this_pick(raw, final), unsafe_allow_html=True)
    st.markdown('<div class="cfbm2-section">🏟️ MATCHUP</div>', unsafe_allow_html=True)
    st.markdown(prior._hero(display_game, away, home), unsafe_allow_html=True)
    with st.expander("🏟️ Matchup & team profiles", expanded=False):
        st.markdown(prior.frozen.prior.frozen_step5.frozen_v3._team_data_diagnostics(team_diag), unsafe_allow_html=True)
        st.markdown('<div class="cfb3-grid">' + prior.frozen.prior.frozen_step5.frozen_v3._team_card(away) + prior.frozen.prior.frozen_step5.frozen_v3._team_card(home) + '</div>', unsafe_allow_html=True)
    with st.expander("🧠 Model details", expanded=False):
        st.markdown(prior.frozen.prior.frozen_step5._model_card(game, away, home, raw), unsafe_allow_html=True)
        st.markdown(prior.frozen._final_card(game, away, home, final), unsafe_allow_html=True)
        feature_html = prior.frozen.prior.frozen_step5._feature_panel(raw)
        if feature_html:
            st.markdown(feature_html, unsafe_allow_html=True)
    with st.expander(f"🗓️ Full verified slate • {selected_day}", expanded=False):
        st.dataframe(prior._slate_rows(games), use_container_width=True, hide_index=True)
    st.caption("Model probabilities and fair moneylines come from the existing certified Moneyline engine. Sportsbook prices, when present, are display-only and carry 0% model weight.")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if _clean(market).lower() == "moneyline":
        return render_moneyline_hub(section_header, status_info, team_logo, h)
    return prior.render_cfb_hub(market, section_header, status_info, team_logo, h)


__all__ = ["MODEL_VERSION", "render_moneyline_hub", "render_cfb_hub"]
