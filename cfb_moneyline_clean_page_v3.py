"""CFB Moneyline Premium V3 — market value + professional matchup presentation.

Presentation-only successor over frozen Premium V2/model owners. Verified market
prices are comparison context only and carry exactly 0.0% model influence.
"""
from __future__ import annotations

from html import escape
from math import isfinite
from typing import Any, Mapping

import streamlit as st
import cfb_moneyline_clean_page_v2 as prior

MODEL_VERSION = "CFB MONEYLINE PREMIUM V3 • MARKET VALUE"
FROZEN_MONEYLINE_OWNER = prior.FROZEN_MONEYLINE_OWNER
FROZEN_RAW_MODEL = prior.FROZEN_RAW_MODEL
FROZEN_FINAL_MODEL = prior.FROZEN_FINAL_MODEL
SPORTSBOOK_PROJECTION_INFLUENCE = prior.SPORTSBOOK_PROJECTION_INFLUENCE
MAY_MODIFY_PROJECTION = prior.MAY_MODIFY_PROJECTION

_CSS = r"""
<style>
.cfbm3-hero{margin:8px 0 14px;padding:16px 18px;border:1px solid rgba(80,157,220,.28);border-radius:20px;background:linear-gradient(145deg,#07111d,#091522 62%,#11152d)}
.cfbm3-k{font-size:.62rem;letter-spacing:.1em;text-transform:uppercase;font-weight:900;color:#84d8ff}.cfbm3-title{font-size:1.45rem;font-weight:950;color:#f7fbff;margin-top:5px}.cfbm3-sub{font-size:.68rem;color:#91a4b8;margin-top:5px;line-height:1.5}
.cfbm3-section{font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;font-weight:950;color:#dbe8f5;margin:18px 0 7px}.cfbm3-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}.cfbm3-card{border:1px solid rgba(140,165,190,.18);border-radius:15px;background:#091724;padding:12px}.cfbm3-card.primary{background:linear-gradient(145deg,rgba(70,38,128,.40),#091724);border-color:rgba(157,114,255,.48)}.cfbm3-card.good{border-color:rgba(72,191,133,.42)}.cfbm3-card.warn{border-color:rgba(228,176,70,.42)}.cfbm3-card.bad{border-color:rgba(220,86,98,.42)}
.cfbm3-card small{display:block;font-size:.34rem;text-transform:uppercase;font-weight:900;color:#8196aa;letter-spacing:.06em}.cfbm3-card b{display:block;font-size:.9rem;color:#f6fbff;margin-top:5px}.cfbm3-card strong{display:block;font-size:1.28rem;color:#cdbaff;margin-top:5px}.cfbm3-card span{display:block;font-size:.42rem;color:#8ea1b3;line-height:1.45;margin-top:4px}
.cfbm3-verdict{margin:10px 0;padding:12px 14px;border-radius:15px;border:1px solid rgba(95,171,229,.28);background:#0a1a28;display:grid;grid-template-columns:1.2fr repeat(4,minmax(0,.8fr));gap:8px;align-items:center}.cfbm3-vmain{font-size:.85rem;font-weight:950;color:#fff}.cfbm3-vmain em{display:block;font-style:normal;font-size:.38rem;color:#8ea4b7;text-transform:uppercase}.cfbm3-vcell small{display:block;color:#7f94a7;font-size:.31rem;text-transform:uppercase;font-weight:900}.cfbm3-vcell b{display:block;color:#f3f9fd;font-size:.72rem;margin-top:3px}
.cfbm3-reasons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.cfbm3-reason{border:1px solid rgba(135,158,180,.17);border-radius:13px;background:#091724;padding:10px}.cfbm3-reason small{display:block;font-size:.32rem;text-transform:uppercase;color:#8296a8;font-weight:900}.cfbm3-reason b{display:block;font-size:.72rem;color:#f1f7fb;margin-top:4px}.cfbm3-reason.good{border-color:rgba(62,180,125,.35)}.cfbm3-reason.bad{border-color:rgba(222,151,59,.35)}
.cfbm3-summary{padding:10px 12px;border-left:3px solid #74ccff;background:#0a1926;border-radius:0 12px 12px 0;color:#c7d6e4;font-size:.64rem;line-height:1.55;margin:7px 0 10px}
.cfbm3-match{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;padding:14px;border:1px solid rgba(93,151,202,.24);border-radius:17px;background:#081622}.cfbm3-team{display:flex;gap:10px;align-items:center}.cfbm3-team.home{justify-content:flex-end;text-align:right}.cfbm3-logo{width:52px;height:52px;border-radius:14px;border:1px solid rgba(140,170,200,.22);display:grid;place-items:center;background:#0c1d2b;overflow:hidden}.cfbm3-logo img{max-width:42px;max-height:42px}.cfbm3-name{font-weight:950;color:#fff;font-size:.9rem}.cfbm3-meta{color:#8ea2b4;font-size:.42rem;margin-top:3px}.cfbm3-at{color:#78cfff;font-weight:950}.cfbm3-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:8px}.cfbm3-context div{padding:8px 9px;border:1px solid rgba(135,158,180,.14);border-radius:11px;background:#091724}.cfbm3-context small{display:block;font-size:.29rem;text-transform:uppercase;color:#74899c;font-weight:900}.cfbm3-context b{display:block;color:#eef6fb;font-size:.55rem;margin-top:3px}
.cfbm3-note{padding:10px 12px;border-radius:12px;background:#0a1a28;color:#9fb1c1;font-size:.58rem;line-height:1.5}.cfbm3-fresh{color:#7890a5;font-size:.48rem;margin:8px 0 0}
@media(max-width:800px){.cfbm3-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbm3-verdict{grid-template-columns:1fr 1fr}.cfbm3-vmain{grid-column:1/-1}.cfbm3-reasons{grid-template-columns:1fr}.cfbm3-match{grid-template-columns:1fr}.cfbm3-at{text-align:center}.cfbm3-team.home{justify-content:flex-start;text-align:left}.cfbm3-context{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _odds(value: Any) -> str:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError, OverflowError):
        return "—"
    return f"+{number}" if number > 0 else str(number)


def _pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return "—"
    if not isfinite(number):
        return "—"
    if abs(number) <= 1.0:
        number *= 100.0
    return f"{number:.1f}%"


def american_implied_probability(odds: Any) -> float | None:
    try:
        value = float(odds)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(value) or value == 0 or abs(value) < 100:
        return None
    return (-value) / ((-value) + 100.0) if value < 0 else 100.0 / (value + 100.0)


def _winner_side(final: Mapping[str, Any]) -> str:
    return prior.prior._winner_side(final) or "home"


def _verified_prices(game: Mapping[str, Any], side: str) -> list[tuple[str, float, str]]:
    prices = game.get("sportsbook_moneylines")
    if not isinstance(prices, Mapping):
        return []
    out: list[tuple[str, float, str]] = []
    for book, payload in prices.items():
        if not isinstance(payload, Mapping):
            continue
        try:
            price = float(payload.get(side))
        except (TypeError, ValueError, OverflowError):
            continue
        if not isfinite(price) or abs(price) < 100:
            continue
        out.append((_clean(book) or "Verified market", price, _clean(payload.get("updated_at"))))
    return out


def market_value_verdict(game: Mapping[str, Any], final: Mapping[str, Any], winner_side: str | None = None) -> dict[str, Any]:
    side = winner_side or _winner_side(final)
    try:
        model_probability = float(final.get("winner_probability_final"))
    except (TypeError, ValueError, OverflowError):
        model_probability = float("nan")
    rows = _verified_prices(game, side)
    if not rows or not isfinite(model_probability):
        return {"verdict": "WAIT FOR PRICE", "best_book": None, "best_price": None, "market_probability": None, "edge_pp": None}
    best_book, best_price, updated_at = max(rows, key=lambda row: row[1])
    implied = american_implied_probability(best_price)
    if implied is None:
        return {"verdict": "WAIT FOR PRICE", "best_book": None, "best_price": None, "market_probability": None, "edge_pp": None}
    edge_pp = (model_probability - implied) * 100.0
    if edge_pp >= 4.0:
        verdict = "VALUE"
    elif edge_pp >= 1.5:
        verdict = "LEAN VALUE"
    elif edge_pp < 0:
        verdict = "PASS — PRICE TOO EXPENSIVE"
    else:
        verdict = "PASS — MARKET EFFICIENT"
    return {"verdict": verdict, "best_book": best_book, "best_price": best_price, "market_probability": implied, "edge_pp": edge_pp, "updated_at": updated_at}


def _factor_rows(raw: Mapping[str, Any], final: Mapping[str, Any], winner_side: str) -> list[tuple[str, float, str]]:
    comp = raw.get("components") or {}
    def delta(home_key: str, away_key: str) -> float | None:
        try:
            value = float(comp.get(home_key)) - float(comp.get(away_key))
        except (TypeError, ValueError, OverflowError):
            return None
        return value if winner_side == "home" else -value
    specs = [
        ("Scoring profile", "home_base_points", "away_base_points"),
        ("Recent form", "home_recent_adjustment", "away_recent_adjustment"),
        ("Efficiency", "home_efficiency_adjustment", "away_efficiency_adjustment"),
        ("Turnovers", "home_turnover_adjustment", "away_turnover_adjustment"),
        ("Schedule strength", "home_schedule_adjustment", "away_schedule_adjustment"),
        ("Home field", "home_field_adjustment", "away_field_adjustment"),
    ]
    out = []
    for label, h, a in specs:
        value = delta(h, a)
        if value is not None:
            out.append((label, value, "supports" if value > 0 else "pushes against" if value < 0 else "neutral"))
    return out


def human_reason_summary(raw: Mapping[str, Any], final: Mapping[str, Any], winner_side: str | None = None) -> str:
    side = winner_side or _winner_side(final)
    winner = _clean(final.get("winner_team")) or "The model side"
    rows = _factor_rows(raw, final, side)
    positive = [label.lower() for label, value, _ in sorted(rows, key=lambda x: x[1], reverse=True) if value > 0][:2]
    negative = [label.lower() for label, value, _ in sorted(rows, key=lambda x: x[1]) if value < 0][:2]
    support = " and ".join(positive) if positive else "the verified model inputs"
    counter = " and ".join(negative) if negative else "no major negative factor"
    return f"{winner}'s strongest support comes from {support}; the main counterweight is {counter}. The market price is evaluated only after the model is complete."


def _attach_verified_market(game: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(game)
    if isinstance(out.get("sportsbook_moneylines"), Mapping) and out.get("sportsbook_moneylines"):
        return out
    try:
        from cfb_game_total_page1_v2_step4_side_market_completeness_v1 import enrich_verified_side_market
        enriched = enrich_verified_side_market(out)
    except Exception:
        return out
    if enriched.get("verified_side_market_status") != "GREEN":
        return out
    if float(enriched.get("verified_side_market_projection_weight") or 0.0) != 0.0:
        return out
    away = enriched.get("verified_away_moneyline")
    home = enriched.get("verified_home_moneyline")
    if away is None and home is None:
        return out
    provider = _clean(enriched.get("verified_side_market_provider")) or "Verified market"
    out.update(enriched)
    out["sportsbook_moneylines"] = {provider: {"away": away, "home": home, "updated_at": _clean((enriched.get("verified_side_market_diagnostics") or {}).get("date"))}}
    return out


def _decision_html(game: Mapping[str, Any], raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not final.get("ready"):
        reasons = " • ".join(str(x) for x in final.get("reasons") or ["Verified model inputs incomplete"])
        return f'<div class="cfbm3-section">🏆 MONEYLINE DECISION</div><div class="cfbm3-note"><b>PASS • NO QUALIFIED MODEL PICK</b><br>{escape(reasons)}</div>'
    side = _winner_side(final)
    winner = _clean(final.get("winner_team")) or "Model side"
    tier = _clean(final.get("model_tier")) or "LEAN"
    headline = f"{tier}: {winner} ML" if "pass" not in tier.lower() else "PASS"
    fair = final.get("home_fair_moneyline") if side == "home" else final.get("away_fair_moneyline")
    value = market_value_verdict(game, final, side)
    grade = _clean(final.get("model_grade")) or "—"
    confidence = _clean(raw.get("confidence")) or "CHECK"
    return f'''<div class="cfbm3-section">🏆 MONEYLINE DECISION</div>
<div class="cfbm3-grid">
 <div class="cfbm3-card primary"><small>Model verdict</small><b>{escape(headline)}</b><strong>{_pct(final.get('winner_probability_final'))}</strong><span>Model win probability • price-independent</span></div>
 <div class="cfbm3-card"><small>Fair moneyline</small><b>{_odds(fair)}</b><span>Model fair price</span></div>
 <div class="cfbm3-card"><small>Confidence</small><b>{escape(confidence.title())}</b><span>Grade {escape(grade)}</span></div>
 <div class="cfbm3-card"><small>Model health</small><b>{_pct(final.get('reliability'))}</b><span>{_pct(final.get('feature_coverage'))} feature coverage</span></div>
</div>
<div class="cfbm3-section">🎯 BET VERDICT</div>
<div class="cfbm3-verdict"><div class="cfbm3-vmain">{escape(value['verdict'])}<em>Price-aware decision • 0% projection influence</em></div>
<div class="cfbm3-vcell"><small>BEST VERIFIED PRICE</small><b>{escape(_clean(value.get('best_book')) or 'Unavailable')} {_odds(value.get('best_price')) if value.get('best_price') is not None else ''}</b></div>
<div class="cfbm3-vcell"><small>Model fair</small><b>{_odds(fair)}</b></div>
<div class="cfbm3-vcell"><small>Market implied</small><b>{_pct(value.get('market_probability'))}</b></div>
<div class="cfbm3-vcell"><small>Model edge</small><b>{f"{value['edge_pp']:+.1f} pp" if value.get('edge_pp') is not None else '—'}</b></div></div>'''


def _why_html(raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not raw.get("ready") or not final.get("ready"):
        return '<div class="cfbm3-section">💡 WHY THIS SIDE</div><div class="cfbm3-note">Reasoning appears only when verified model inputs are ready.</div>'
    side = _winner_side(final)
    winner = _clean(final.get("winner_team")) or "Model side"
    rows = _factor_rows(raw, final, side)
    cards = []
    for label, value, direction in rows:
        cls = "good" if value > 0 else "bad" if value < 0 else ""
        cards.append(f'<div class="cfbm3-reason {cls}"><small>{escape(label)}</small><b>{escape(winner)} {value:+.1f}</b><span>{escape(direction)} the selected side</span></div>')
    return '<div class="cfbm3-section">💡 WHY THIS SIDE</div><div class="cfbm3-summary">' + escape(human_reason_summary(raw, final, side)) + '</div><div class="cfbm3-reasons">' + ''.join(cards) + '</div>'


def _logo(url: str, name: str) -> str:
    return f'<div class="cfbm3-logo"><img src="{escape(url)}" alt="{escape(name)} logo"></div>' if url else f'<div class="cfbm3-logo"><b>{escape(prior.prior._monogram(name))}</b></div>'


def _matchup_snapshot(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    visuals = prior.prior._resolve_visuals(game)
    away_name = _clean(away.get("team")) or _clean(game.get("away_team")) or "Away"
    home_name = _clean(home.get("team")) or _clean(game.get("home_team")) or "Home"
    away_record = prior.prior._record_text(away, game, "away")
    home_record = prior.prior._record_text(home, game, "home")
    away_rank = prior.prior._rank_text(away, game, "away")
    home_rank = prior.prior._rank_text(home, game, "home")
    away_logo = _clean((visuals.get("away") or {}).get("logo"))
    home_logo = _clean((visuals.get("home") or {}).get("logo"))
    site = "Neutral site" if game.get("neutral_site") else "Home field"
    return f'''<div class="cfbm3-section">🏟️ MATCHUP SNAPSHOT</div><div class="cfbm3-match">
<div class="cfbm3-team">{_logo(away_logo, away_name)}<div><div class="cfbm3-name">{escape(away_name)}</div><div class="cfbm3-meta">{escape(away_rank)} • {escape(away_record)}</div></div></div>
<div class="cfbm3-at">@</div>
<div class="cfbm3-team home"><div><div class="cfbm3-name">{escape(home_name)}</div><div class="cfbm3-meta">{escape(home_rank)} • {escape(home_record)}</div></div>{_logo(home_logo, home_name)}</div></div>
<div class="cfbm3-context"><div><small>Kickoff</small><b>{escape(prior.prior._kickoff_phoenix(game))}</b></div><div><small>Venue</small><b>{escape(_clean(game.get('venue')) or 'TBD')}</b></div><div><small>Broadcast</small><b>{escape(_clean(game.get('broadcast')) or 'TBD')}</b></div><div><small>Site</small><b>{escape(site)}</b></div></div>'''


def _freshness_html(game: Mapping[str, Any]) -> str:
    rows = _verified_prices(game, "home") + _verified_prices(game, "away")
    stamps = [stamp for _, _, stamp in rows if stamp]
    text = max(stamps) if stamps else "Verified model/schedule data • market timestamp unavailable"
    return f'<div class="cfbm3-section">🕒 DATA FRESHNESS</div><div class="cfbm3-note">{escape(text)} • sportsbook prices are descriptive context only.</div>'


def render_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div class="cfbm3-hero"><div class="cfbm3-k">KYRE SPORTS AI • CFB MONEYLINE</div><div class="cfbm3-title">🏆 College Football Moneyline</div><div class="cfbm3-sub">Model first, price second. See the fair line, verified market value, strongest football reasons and matchup context without exposing internal audit plumbing.</div></div>', unsafe_allow_html=True)
    today_phoenix = prior.prior.datetime.now(prior.prior._PHOENIX).date()
    selected = st.date_input("CFB slate", value=today_phoenix, key="cfb_moneyline_premium_v3_date")
    selected_day = selected.isoformat()
    games, _schedule_diag = prior.prior.schedule_v3.load_with_diagnostics(selected_day)
    if not games:
        st.warning("No verified upcoming FBS matchups are available for this slate. No pick is invented.")
        return
    index = st.selectbox("🏟️ Moneyline matchup", options=list(range(len(games))), format_func=lambda i: prior.prior._matchup_label(prior.prior._display_game(games[int(i)])), key=f"cfb_moneyline_premium_v3_matchup_{selected_day}")
    game = games[int(index)]
    selected_result = prior.prior.slate.analyze_game(game, selected_day)
    away = selected_result.get("away") or {}
    home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}
    team_diag = selected_result.get("team_diag") or {}
    display_game = _attach_verified_market(prior.prior._display_game(game))
    st.markdown(_decision_html(display_game, raw, final), unsafe_allow_html=True)
    st.markdown(_why_html(raw, final), unsafe_allow_html=True)
    st.markdown(_matchup_snapshot(display_game, away, home), unsafe_allow_html=True)
    st.markdown(_freshness_html(display_game), unsafe_allow_html=True)
    with st.expander("🏟️ Team profiles & availability", expanded=False):
        st.markdown(prior.prior.frozen.prior.frozen_step5.frozen_v3._team_data_diagnostics(team_diag), unsafe_allow_html=True)
        st.markdown('<div class="cfb3-grid">' + prior.prior.frozen.prior.frozen_step5.frozen_v3._team_card(away) + prior.prior.frozen.prior.frozen_step5.frozen_v3._team_card(home) + '</div>', unsafe_allow_html=True)
    with st.expander("🧠 Model details", expanded=False):
        st.markdown(prior.prior.frozen.prior.frozen_step5._model_card(game, away, home, raw), unsafe_allow_html=True)
        st.markdown(prior.prior.frozen._final_card(game, away, home, final), unsafe_allow_html=True)
        feature_html = prior.prior.frozen.prior.frozen_step5._feature_panel(raw)
        if feature_html:
            st.markdown(feature_html, unsafe_allow_html=True)
    with st.expander(f"🗓️ Full verified slate • {selected_day}", expanded=False):
        st.dataframe(prior.prior._slate_rows(games), use_container_width=True, hide_index=True)
    st.caption("Moneyline probabilities and fair prices remain owned by the frozen certified model. Verified market prices are evaluated only after the model is complete and carry 0.0% projection weight.")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if _clean(market).lower() == "moneyline":
        return render_moneyline_hub(section_header, status_info, team_logo, h)
    return prior.render_cfb_hub(market, section_header, status_info, team_logo, h)


__all__ = ["MODEL_VERSION", "FROZEN_MONEYLINE_OWNER", "SPORTSBOOK_PROJECTION_INFLUENCE", "MAY_MODIFY_PROJECTION", "american_implied_probability", "market_value_verdict", "human_reason_summary", "render_moneyline_hub", "render_cfb_hub"]
