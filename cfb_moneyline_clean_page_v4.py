"""CFB Moneyline Premium V4 — lean Streamlit presentation redesign.

Presentation-only successor over frozen Premium V3/model owners. Certified model
math, probabilities, fair prices, team identity and sportsbook projection weight
remain unchanged.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st
import cfb_moneyline_clean_page_v3 as prior

MODEL_VERSION = "CFB MONEYLINE PREMIUM V4 • STREAMLIT REDESIGN"
FROZEN_MONEYLINE_OWNER = prior.FROZEN_MONEYLINE_OWNER
FROZEN_RAW_MODEL = prior.FROZEN_RAW_MODEL
FROZEN_FINAL_MODEL = prior.FROZEN_FINAL_MODEL
SPORTSBOOK_PROJECTION_INFLUENCE = prior.SPORTSBOOK_PROJECTION_INFLUENCE
MAY_MODIFY_PROJECTION = prior.MAY_MODIFY_PROJECTION
market_value_verdict = prior.market_value_verdict
human_reason_summary = prior.human_reason_summary

_CSS = r"""
<style>
.cfbm4-shell{margin:6px 0 12px}.cfbm4-eyebrow{font-size:.58rem;letter-spacing:.12em;text-transform:uppercase;font-weight:900;color:#73d8ff}.cfbm4-title{font-size:1.35rem;font-weight:950;color:#f8fbff;margin:3px 0}.cfbm4-sub{font-size:.6rem;color:#8ea4b8;line-height:1.45}
.cfbm4-matchup-hero{margin:12px 0;padding:14px;border:1px solid rgba(76,169,230,.28);border-radius:18px;background:linear-gradient(145deg,#07111d,#0a1927 70%,#10162a);box-shadow:0 12px 30px rgba(0,0,0,.18)}
.cfbm4-matchup-main{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center}.cfbm4-team{display:flex;align-items:center;gap:10px}.cfbm4-team.home{justify-content:flex-end;text-align:right}.cfbm4-logo{width:64px;height:64px;border-radius:16px;display:grid;place-items:center;background:#0b1b29;border:1px solid rgba(124,181,221,.26);overflow:hidden}.cfbm4-logo img{max-width:54px;max-height:54px}.cfbm4-logo b{font-size:1rem;color:#dff6ff}.cfbm4-name{font-size:1rem;font-weight:950;color:#fff}.cfbm4-meta{font-size:.43rem;color:#8ea2b5;margin-top:3px}.cfbm4-vs{font-size:.72rem;font-weight:950;color:#6ed4ff;border:1px solid rgba(110,212,255,.28);border-radius:999px;padding:5px 8px}.cfbm4-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.cfbm4-chip{font-size:.38rem;color:#cfe7f8;background:#091a28;border:1px solid rgba(122,163,190,.18);border-radius:999px;padding:6px 8px}
.cfbm4-section{font-size:.62rem;letter-spacing:.09em;text-transform:uppercase;font-weight:950;color:#dceaf5;margin:16px 0 7px}.cfbm4-decision-grid{display:grid;grid-template-columns:1.35fr repeat(3,minmax(0,1fr));gap:8px}.cfbm4-stat{padding:12px;border-radius:14px;background:#091724;border:1px solid rgba(139,165,189,.17)}.cfbm4-stat.primary{background:linear-gradient(145deg,rgba(67,45,132,.58),#091724);border-color:rgba(149,117,255,.48)}.cfbm4-stat small{display:block;font-size:.31rem;letter-spacing:.07em;text-transform:uppercase;color:#8198aa;font-weight:900}.cfbm4-stat b{display:block;font-size:.88rem;color:#fff;margin-top:5px}.cfbm4-stat strong{display:block;font-size:1.42rem;color:#d5c6ff;margin-top:3px}.cfbm4-stat span{display:block;font-size:.38rem;color:#899eaf;margin-top:4px;line-height:1.35}
.cfbm4-verdict{padding:12px 14px;border-radius:14px;background:#081a28;border:1px solid rgba(65,194,225,.36);display:grid;grid-template-columns:1.25fr repeat(4,minmax(0,.78fr));gap:8px;align-items:center}.cfbm4-verdict-main{font-size:.86rem;font-weight:950;color:#fff}.cfbm4-verdict-main span{display:block;font-size:.34rem;color:#85a0b2;margin-top:3px;text-transform:uppercase}.cfbm4-verdict-cell small{display:block;font-size:.29rem;color:#778fa2;text-transform:uppercase;font-weight:900}.cfbm4-verdict-cell b{display:block;font-size:.65rem;color:#f4f9fc;margin-top:3px}
.cfbm4-summary{font-size:.56rem;color:#bfd0dc;line-height:1.5;padding:9px 11px;border-left:3px solid #69d5ff;background:#091925;border-radius:0 12px 12px 0}.cfbm4-reasons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:7px}.cfbm4-reason{padding:10px;border-radius:12px;background:#091724;border:1px solid rgba(133,157,180,.16)}.cfbm4-reason.good{border-color:rgba(48,190,132,.42)}.cfbm4-reason.bad{border-color:rgba(232,172,71,.42)}.cfbm4-reason small{display:block;font-size:.29rem;text-transform:uppercase;color:#7c92a5;font-weight:900}.cfbm4-reason b{display:block;font-size:.64rem;color:#f4f8fb;margin-top:4px}.cfbm4-reason span{display:block;font-size:.34rem;color:#8298aa;margin-top:3px}
.cfbm4-fresh{padding:10px 12px;border-radius:12px;background:#091925;border:1px solid rgba(125,160,185,.16);font-size:.5rem;color:#9db1c1;line-height:1.45}
@media(max-width:800px){.cfbm4-matchup-main{grid-template-columns:1fr auto 1fr}.cfbm4-logo{width:52px;height:52px}.cfbm4-logo img{max-width:44px;max-height:44px}.cfbm4-name{font-size:.8rem}.cfbm4-decision-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbm4-stat.primary{grid-column:1/-1}.cfbm4-verdict{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbm4-verdict-main{grid-column:1/-1}.cfbm4-reasons{grid-template-columns:1fr}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _logo(url: str, name: str) -> str:
    if url:
        return f'<div class="cfbm4-logo"><img src="{escape(url)}" alt="{escape(name)} logo"></div>'
    base = prior.prior.prior
    return f'<div class="cfbm4-logo"><b>{escape(base._monogram(name))}</b></div>'


def _matchup_header(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], *, visuals: Mapping[str, Any] | None = None, kickoff: str | None = None) -> str:
    base = prior.prior.prior
    visuals = visuals or base._resolve_visuals(game)
    away_name = _clean(away.get("team")) or _clean(game.get("away_team")) or "Away"
    home_name = _clean(home.get("team")) or _clean(game.get("home_team")) or "Home"
    away_logo = _clean((visuals.get("away") or {}).get("logo"))
    home_logo = _clean((visuals.get("home") or {}).get("logo"))
    away_record = base._record_text(away, game, "away")
    home_record = base._record_text(home, game, "home")
    site = "Neutral site" if game.get("neutral_site") else f"Home field ({home_name})"
    kickoff = kickoff or base._kickoff_phoenix(game)
    venue = _clean(game.get("venue")) or "Venue TBD"
    broadcast = _clean(game.get("broadcast")) or "Broadcast unavailable"
    return f'''<div class="cfbm4-matchup-hero"><div class="cfbm4-matchup-main">
<div class="cfbm4-team">{_logo(away_logo, away_name)}<div><div class="cfbm4-name">{escape(away_name)}</div><div class="cfbm4-meta">{escape(away_record)}</div></div></div>
<div class="cfbm4-vs">@</div>
<div class="cfbm4-team home"><div><div class="cfbm4-name">{escape(home_name)}</div><div class="cfbm4-meta">{escape(home_record)}</div></div>{_logo(home_logo, home_name)}</div></div>
<div class="cfbm4-chips"><span class="cfbm4-chip">🕒 {escape(kickoff)}</span><span class="cfbm4-chip">📍 {escape(venue)}</span><span class="cfbm4-chip">📺 {escape(broadcast)}</span><span class="cfbm4-chip">🏟️ {escape(site)}</span></div></div>'''


def _decision_html(game: Mapping[str, Any], raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not final.get("ready"):
        reasons = " • ".join(str(x) for x in final.get("reasons") or ["Verified model inputs incomplete"])
        return f'<div class="cfbm4-section">🏆 MONEYLINE DECISION</div><div class="cfbm4-fresh"><b>PASS • NO QUALIFIED MODEL PICK</b><br>{escape(reasons)}</div>'
    side = prior._winner_side(final)
    winner = _clean(final.get("winner_team")) or "Model side"
    tier = _clean(final.get("model_tier")) or "LEAN"
    headline = f"{tier}: {winner} ML" if "pass" not in tier.lower() else "PASS"
    fair = final.get("home_fair_moneyline") if side == "home" else final.get("away_fair_moneyline")
    value = market_value_verdict(game, final, side)
    confidence = _clean(raw.get("confidence")) or "CHECK"
    grade = _clean(final.get("model_grade")) or "—"
    return f'''<div class="cfbm4-section">🏆 MONEYLINE DECISION</div><div class="cfbm4-decision-grid">
<div class="cfbm4-stat primary"><small>Model pick</small><b>{escape(headline)}</b><strong>{prior._pct(final.get('winner_probability_final'))}</strong><span>Win probability • price-independent</span></div>
<div class="cfbm4-stat"><small>Fair moneyline</small><b>{prior._odds(fair)}</b><span>Model fair price</span></div>
<div class="cfbm4-stat"><small>Confidence</small><b>{escape(confidence.title())}</b><span>Grade {escape(grade)}</span></div>
<div class="cfbm4-stat"><small>Model health</small><b>{prior._pct(final.get('reliability'))}</b><span>{prior._pct(final.get('feature_coverage'))} coverage</span></div></div>
<div class="cfbm4-section">🎯 BET VERDICT</div><div class="cfbm4-verdict"><div class="cfbm4-verdict-main">{escape(value['verdict'])}<span>Price-aware • 0% projection influence</span></div>
<div class="cfbm4-verdict-cell"><small>Best verified price</small><b>{escape(_clean(value.get('best_book')) or 'Unavailable')} {prior._odds(value.get('best_price')) if value.get('best_price') is not None else ''}</b></div>
<div class="cfbm4-verdict-cell"><small>Model fair</small><b>{prior._odds(fair)}</b></div><div class="cfbm4-verdict-cell"><small>Market implied</small><b>{prior._pct(value.get('market_probability'))}</b></div><div class="cfbm4-verdict-cell"><small>Model edge</small><b>{f"{value['edge_pp']:+.1f} pp" if value.get('edge_pp') is not None else '—'}</b></div></div>'''


def _why_html(raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not raw.get("ready") or not final.get("ready"):
        return '<div class="cfbm4-section">💡 WHY THIS SIDE</div><div class="cfbm4-fresh">Reasoning appears only when verified model inputs are ready.</div>'
    side = prior._winner_side(final)
    winner = _clean(final.get("winner_team")) or "Model side"
    rows = prior._factor_rows(raw, final, side)
    ranked = sorted(rows, key=lambda x: abs(x[1]), reverse=True)[:3]
    cards = []
    for label, value, direction in ranked:
        cls = "good" if value > 0 else "bad" if value < 0 else ""
        cards.append(f'<div class="cfbm4-reason {cls}"><small>{escape(label)}</small><b>{escape(winner)} {value:+.1f}</b><span>{escape(direction)} the side</span></div>')
    return '<div class="cfbm4-section">💡 WHY THIS SIDE</div><div class="cfbm4-summary">' + escape(human_reason_summary(raw, final, side)) + '</div><div class="cfbm4-reasons">' + ''.join(cards) + '</div>'


def _freshness_html(game: Mapping[str, Any]) -> str:
    rows = prior._verified_prices(game, "home") + prior._verified_prices(game, "away")
    stamps = [stamp for _, _, stamp in rows if stamp]
    text = max(stamps) if stamps else "Verified model/schedule data • market timestamp unavailable"
    return f'<div class="cfbm4-section">🕒 DATA FRESHNESS</div><div class="cfbm4-fresh">✅ {escape(text)} • sportsbook prices remain descriptive context only.</div>'


def render_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    base = prior.prior.prior
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div class="cfbm4-shell"><div class="cfbm4-eyebrow">KYRE SPORTS AI • CFB MONEYLINE</div><div class="cfbm4-title">College Football Moneyline</div><div class="cfbm4-sub">A lean decision-first view: matchup, model probability, fair price, market value and the three strongest football reasons.</div></div>', unsafe_allow_html=True)
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
    display_game = prior._attach_verified_market(base._display_game(game))
    st.markdown(_matchup_header(display_game, away, home), unsafe_allow_html=True)
    st.markdown(_decision_html(display_game, raw, final), unsafe_allow_html=True)
    st.markdown(_why_html(raw, final), unsafe_allow_html=True)
    st.markdown(_freshness_html(display_game), unsafe_allow_html=True)
    with st.expander("🏟️ Team profiles & availability", expanded=False):
        st.markdown(base.frozen.prior.frozen_step5.frozen_v3._team_data_diagnostics(team_diag), unsafe_allow_html=True)
        st.markdown('<div class="cfb3-grid">' + base.frozen.prior.frozen_step5.frozen_v3._team_card(away) + base.frozen.prior.frozen_step5.frozen_v3._team_card(home) + '</div>', unsafe_allow_html=True)
    with st.expander("🧠 Model details", expanded=False):
        st.markdown(base.frozen.prior.frozen_step5._model_card(game, away, home, raw), unsafe_allow_html=True)
        st.markdown(base.frozen._final_card(game, away, home, final), unsafe_allow_html=True)
        feature_html = base.frozen.prior.frozen_step5._feature_panel(raw)
        if feature_html:
            st.markdown(feature_html, unsafe_allow_html=True)
    with st.expander(f"🗓️ Full verified slate • {selected_day}", expanded=False):
        st.dataframe(base._slate_rows(games), use_container_width=True, hide_index=True)
    st.caption("Certified Moneyline probabilities and fair prices remain frozen. Verified sportsbook prices are comparison-only and carry 0.0% projection weight.")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if _clean(market).lower() == "moneyline":
        return render_moneyline_hub(section_header, status_info, team_logo, h)
    return prior.render_cfb_hub(market, section_header, status_info, team_logo, h)


__all__ = ["MODEL_VERSION", "FROZEN_MONEYLINE_OWNER", "SPORTSBOOK_PROJECTION_INFLUENCE", "MAY_MODIFY_PROJECTION", "market_value_verdict", "human_reason_summary", "render_moneyline_hub", "render_cfb_hub"]
