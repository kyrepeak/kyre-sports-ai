"""CFB Moneyline Premium V5 — professional detail-panel presentation.

Presentation-only successor over frozen Premium V4/model owners. The certified
model, probability, fair-price, calibration and sportsbook-influence contracts
remain unchanged; V5 only replaces the two legacy raw-looking detail surfaces.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st
import cfb_moneyline_clean_page_v4 as prior

MODEL_VERSION = "CFB MONEYLINE PREMIUM V5 • PROFESSIONAL DETAIL PANELS"
FROZEN_MONEYLINE_OWNER = prior.FROZEN_MONEYLINE_OWNER
FROZEN_RAW_MODEL = prior.FROZEN_RAW_MODEL
FROZEN_FINAL_MODEL = prior.FROZEN_FINAL_MODEL
SPORTSBOOK_PROJECTION_INFLUENCE = prior.SPORTSBOOK_PROJECTION_INFLUENCE
MAY_MODIFY_PROJECTION = prior.MAY_MODIFY_PROJECTION
market_value_verdict = prior.market_value_verdict
human_reason_summary = prior.human_reason_summary

_CSS = r"""
<style>
.cfbm5-team-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:4px 0 8px}
.cfbm5-team-card{border:1px solid rgba(103,178,224,.24);border-radius:16px;background:linear-gradient(145deg,#081722,#0a1320);padding:13px;box-shadow:0 10px 24px rgba(0,0,0,.12)}
.cfbm5-team-head{display:flex;gap:10px;align-items:center}.cfbm5-team-head .cfbm4-logo{width:50px;height:50px;border-radius:13px}.cfbm5-team-head .cfbm4-logo img{max-width:42px;max-height:42px}
.cfbm5-team-copy{min-width:0;flex:1}.cfbm5-rank{font-size:.31rem;color:#76cfee;text-transform:uppercase;font-weight:900;letter-spacing:.07em}.cfbm5-team-name{font-size:.87rem;color:#f8fbff;font-weight:950;margin-top:2px}.cfbm5-team-meta{font-size:.35rem;color:#849aab;margin-top:2px}
.cfbm5-quality{font-size:.31rem;font-weight:950;border-radius:999px;padding:5px 7px;border:1px solid rgba(94,208,166,.36);background:#0b261f;color:#83e1ba;white-space:nowrap}.cfbm5-quality.warn{border-color:rgba(232,178,78,.38);background:#2a220d;color:#e8c872}
.cfbm5-team-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:11px}.cfbm5-team-metric{border:1px solid rgba(129,155,176,.14);border-radius:10px;background:#091925;padding:8px}.cfbm5-team-metric b{display:block;color:#f0f7fb;font-size:.66rem}.cfbm5-team-metric span{display:block;color:#7790a2;font-size:.29rem;text-transform:uppercase;margin-top:2px;line-height:1.2}
.cfbm5-splits{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.cfbm5-split{font-size:.32rem;color:#b7c9d5;border:1px solid rgba(118,151,173,.17);background:#081520;border-radius:999px;padding:5px 7px}.cfbm5-source{margin-top:8px;font-size:.31rem;line-height:1.45;color:#728899}
.cfbm5-model-hero{border:1px solid rgba(104,185,231,.26);border-radius:16px;background:linear-gradient(145deg,#071622,#0b1726);padding:13px}.cfbm5-model-grid{display:grid;grid-template-columns:1.35fr repeat(3,minmax(0,1fr));gap:7px}.cfbm5-model-primary,.cfbm5-model-stat{border:1px solid rgba(127,158,180,.16);border-radius:12px;background:#091925;padding:10px}.cfbm5-model-primary{background:linear-gradient(145deg,rgba(60,64,133,.46),#091925);border-color:rgba(125,125,225,.34)}.cfbm5-model-primary small,.cfbm5-model-stat small{display:block;color:#7f96a8;font-size:.29rem;text-transform:uppercase;font-weight:900}.cfbm5-model-primary b{display:block;color:#fff;font-size:.88rem;margin-top:4px}.cfbm5-model-primary strong{display:block;color:#d8d4ff;font-size:1.28rem;margin-top:3px}.cfbm5-model-stat b{display:block;color:#f2f8fb;font-size:.69rem;margin-top:4px}.cfbm5-model-stat span{display:block;color:#7890a1;font-size:.3rem;margin-top:2px;line-height:1.3}
.cfbm5-uncertainty{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:7px}.cfbm5-uncertainty-card{border:1px solid rgba(226,174,70,.22);border-radius:11px;background:#19170e;padding:9px}.cfbm5-uncertainty-card small{display:block;color:#b39a61;font-size:.29rem;text-transform:uppercase;font-weight:900}.cfbm5-uncertainty-card b{display:block;color:#f2dfae;font-size:.65rem;margin-top:3px}.cfbm5-uncertainty-card span{display:block;color:#96845e;font-size:.3rem;margin-top:2px}
.cfbm5-feature-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:9px}.cfbm5-feature{border:1px solid rgba(121,151,174,.15);border-radius:11px;background:#091722;padding:9px}.cfbm5-feature-top{display:flex;justify-content:space-between;gap:8px}.cfbm5-feature b{color:#eaf3f8;font-size:.58rem}.cfbm5-feature strong{color:#7ed5f6;font-size:.54rem}.cfbm5-feature span{display:block;color:#7b91a0;font-size:.31rem;margin-top:3px;line-height:1.35}.cfbm5-firewall{margin-top:8px;border-left:3px solid #5bbce6;background:#091925;border-radius:0 10px 10px 0;padding:8px 10px;color:#9eb2c0;font-size:.34rem;line-height:1.45}.cfbm5-firewall b{color:#dcebf4}
.cfbm5-detail-note{border:1px solid rgba(114,153,180,.16);border-radius:11px;background:#091620;padding:9px 10px;color:#8ca1b0;font-size:.34rem;line-height:1.45;margin-bottom:8px}
@media(max-width:800px){.cfbm5-team-grid{grid-template-columns:1fr}.cfbm5-team-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbm5-model-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbm5-model-primary{grid-column:1/-1}.cfbm5-feature-list{grid-template-columns:1fr}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return default


def _num(value: Any, digits: int = 1, signed: bool = False) -> str:
    try:
        x = float(value)
    except Exception:
        return "—"
    prefix = "+" if signed and x > 0 else ""
    return f"{prefix}{x:.{digits}f}"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _odds(value: Any) -> str:
    try:
        n = int(round(float(value)))
    except Exception:
        return "—"
    return f"+{n}" if n > 0 else str(n)


def _record_text(profile: Mapping[str, Any]) -> str:
    direct = _first(profile, "record_text", "record")
    if isinstance(direct, str):
        return direct or "—"
    record = profile.get("record") or {}
    if isinstance(record, Mapping):
        wins = record.get("wins")
        losses = record.get("losses")
        if wins is not None or losses is not None:
            return f"{int(wins or 0)}-{int(losses or 0)}"
    return "—"


def _split_text(value: Any) -> str:
    if isinstance(value, str):
        return value or "—"
    if isinstance(value, Mapping):
        return f"{int(value.get('wins') or 0)}-{int(value.get('losses') or 0)}"
    return "—"


def _sample_size(profile: Mapping[str, Any]) -> int:
    value = profile.get("sample_size")
    if value is None and isinstance(profile.get("record"), Mapping):
        value = (profile.get("record") or {}).get("games")
    try:
        return int(value or 0)
    except Exception:
        return 0


def _official(profile: Mapping[str, Any], key: str, *fallback_keys: str) -> Any:
    item = (profile.get("official_stats") or {}).get(key)
    if isinstance(item, Mapping):
        value = item.get("value")
        if value not in (None, ""):
            return value
    elif item not in (None, ""):
        return item
    return _first(profile, *fallback_keys)


def _team_card_html(profile: Mapping[str, Any], *, logo: str = "") -> str:
    name = _clean(profile.get("team")) or "Team"
    rank = _first(profile, "ap_rank", "rank")
    rank_text = f"#{int(rank)} AP" if rank is not None else "Unranked"
    conference = _clean(profile.get("conference")) or "Conference unavailable"
    quality = profile.get("data_quality") or {}
    grade = _clean(quality.get("grade")) or ("LIMITED" if _sample_size(profile) < 8 else "VERIFIED")
    quality_cls = "warn" if grade.upper() in {"LIMITED", "CHECK", "LOW"} else ""
    ppg = _first(profile, "ppg", "points_per_game")
    allowed = _first(profile, "points_allowed_pg", "points_allowed_per_game")
    diff = _first(profile, "point_diff_pg", "point_diff_per_game")
    offense = _official(profile, "total_offense", "total_offense")
    defense = _official(profile, "total_defense", "total_defense")
    turnovers = _official(profile, "turnover_margin", "turnover_margin")
    source = _clean(profile.get("data_source")) or "Verified team evidence"
    sample = _sample_size(profile)
    return f'''<div class="cfbm5-team-card"><div class="cfbm5-team-head">{prior._logo(logo, name)}<div class="cfbm5-team-copy"><div class="cfbm5-rank">{escape(rank_text)}</div><div class="cfbm5-team-name">{escape(name)}</div><div class="cfbm5-team-meta">{escape(_record_text(profile))} • {escape(conference)}</div></div><span class="cfbm5-quality {quality_cls}">{escape(grade.upper())}</span></div>
<div class="cfbm5-team-metrics"><div class="cfbm5-team-metric"><b>{_num(ppg)}</b><span>Points / game</span></div><div class="cfbm5-team-metric"><b>{_num(allowed)}</b><span>Allowed / game</span></div><div class="cfbm5-team-metric"><b>{_num(diff, signed=True)}</b><span>Point differential</span></div><div class="cfbm5-team-metric"><b>{_num(offense)}</b><span>Total offense</span></div><div class="cfbm5-team-metric"><b>{_num(defense)}</b><span>Total defense</span></div><div class="cfbm5-team-metric"><b>{_num(turnovers, 2, True)}</b><span>Turnover margin</span></div></div>
<div class="cfbm5-splits"><span class="cfbm5-split">Home {_split_text(profile.get('home_record'))}</span><span class="cfbm5-split">Away {_split_text(profile.get('away_record'))}</span><span class="cfbm5-split">Neutral {_split_text(profile.get('neutral_record'))}</span><span class="cfbm5-split">Last 5 {escape(_clean(profile.get('recent_form')) or '—')}</span></div><div class="cfbm5-source"><b>Data quality:</b> {escape(grade.upper())} • {sample} completed-game sample • {escape(source)}</div></div>'''


def _team_profiles_html(away: Mapping[str, Any], home: Mapping[str, Any], *, visuals: Mapping[str, Any] | None = None) -> str:
    visuals = visuals or {}
    away_logo = _clean((visuals.get("away") or {}).get("logo"))
    home_logo = _clean((visuals.get("home") or {}).get("logo"))
    return '<div class="cfbm5-team-grid">' + _team_card_html(away, logo=away_logo) + _team_card_html(home, logo=home_logo) + '</div>'


def _prob(final: Mapping[str, Any], side: str) -> Any:
    return _first(final, f"{side}_win_probability_final", f"{side}_probability_final")


def _score(final: Mapping[str, Any], side: str) -> Any:
    return _first(final, f"projected_{side}_points", f"{side}_projected_score")


def _uncertainty(final: Mapping[str, Any]) -> tuple[str, str]:
    home_unc = final.get("home_probability_uncertainty") or {}
    if isinstance(home_unc, Mapping) and (home_unc.get("p90_low") is not None or home_unc.get("p90_high") is not None):
        probability = f"{_pct(home_unc.get('p90_low'))} – {_pct(home_unc.get('p90_high'))}"
    else:
        pair = final.get("home_probability_structural_90") or []
        probability = f"{_pct(pair[0])} – {_pct(pair[1])}" if len(pair) >= 2 else "—"
    margin_unc = final.get("margin_uncertainty") or {}
    if isinstance(margin_unc, Mapping) and (margin_unc.get("margin90_low") is not None or margin_unc.get("margin90_high") is not None):
        margin = f"{_num(margin_unc.get('margin90_low'), signed=True)} to {_num(margin_unc.get('margin90_high'), signed=True)}"
    else:
        pair = final.get("margin_structural_90") or []
        margin = f"{_num(pair[0], signed=True)} to {_num(pair[1], signed=True)}" if len(pair) >= 2 else "—"
    return probability, margin


def _model_dashboard_html(raw: Mapping[str, Any], final: Mapping[str, Any], *, away_name: str, home_name: str) -> str:
    if not final.get("ready"):
        reasons = " • ".join(str(x) for x in final.get("reasons") or ["Verified final-model inputs incomplete"])
        return f'<div class="cfbm5-detail-note"><b>MODEL DETAILS UNAVAILABLE</b><br>{escape(reasons)}</div>'
    winner = _clean(final.get("winner_team")) or "Model side"
    winner_p = final.get("winner_probability_final")
    grade = _clean(final.get("model_grade")) or "—"
    tier = _clean(final.get("model_tier")) or "LEAN"
    away_p = _prob(final, "away")
    home_p = _prob(final, "home")
    away_score = _score(final, "away")
    home_score = _score(final, "home")
    margin = _first(final, "projected_margin_home", "home_margin")
    reliability = _first(final, "reliability", default=raw.get("reliability"))
    coverage = final.get("feature_coverage")
    if isinstance(coverage, Mapping):
        coverage = coverage.get("score")
    if coverage is None:
        coverage = raw.get("feature_coverage")
        if isinstance(coverage, Mapping):
            coverage = coverage.get("score")
    probability_range, margin_range = _uncertainty(final)
    return f'''<div class="cfbm5-model-hero"><div class="cfbm5-model-grid"><div class="cfbm5-model-primary"><small>Final model pick</small><b>{escape(winner)} ML • {escape(grade)}</b><strong>{_pct(winner_p)}</strong></div><div class="cfbm5-model-stat"><small>Fair moneyline</small><b>{escape(away_name)} {_odds(final.get('away_fair_moneyline'))}<br>{escape(home_name)} {_odds(final.get('home_fair_moneyline'))}</b><span>Model-derived fair prices</span></div><div class="cfbm5-model-stat"><small>Projected score</small><b>{_num(away_score)} – {_num(home_score)}</b><span>Home margin {_num(margin, signed=True)}</span></div><div class="cfbm5-model-stat"><small>Model health</small><b>{_pct(reliability)}</b><span>Reliability • {_pct(coverage)} feature coverage</span></div></div>
<div class="cfbm5-model-grid" style="margin-top:7px"><div class="cfbm5-model-stat"><small>{escape(away_name)} P(win)</small><b>{_pct(away_p)}</b><span>Final probability</span></div><div class="cfbm5-model-stat"><small>{escape(home_name)} P(win)</small><b>{_pct(home_p)}</b><span>Final probability</span></div><div class="cfbm5-model-stat"><small>Confidence</small><b>{escape((_clean(raw.get('confidence')) or 'CHECK').title())}</b><span>{escape(tier)}</span></div><div class="cfbm5-model-stat"><small>Sportsbook weight</small><b>0%</b><span>Never changes model probability</span></div></div>
<div class="cfbm5-uncertainty"><div class="cfbm5-uncertainty-card"><small>Model uncertainty • home win probability</small><b>{probability_range}</b><span>Structural 90% range</span></div><div class="cfbm5-uncertainty-card"><small>Model uncertainty • margin</small><b>{margin_range}</b><span>Structural 90% range</span></div></div></div>'''


def _feature_contributions_html(raw: Mapping[str, Any], *, away_name: str, home_name: str) -> str:
    if not raw.get("ready"):
        return ""
    c = raw.get("components") or {}
    coverage = raw.get("feature_coverage") or {}
    coverage_components = coverage.get("components") or {} if isinstance(coverage, Mapping) else {}
    def state(key: str) -> str:
        return "Verified" if coverage_components.get(key) else "Limited"
    rows = [
        ("Base scoring", f"{_num(c.get('away_base_points'))} / {_num(c.get('home_base_points'))}", f"{away_name} / {home_name} scoring baseline"),
        ("Recent form", f"{_num(c.get('away_recent_adjustment'), signed=True)} / {_num(c.get('home_recent_adjustment'), signed=True)}", state("recent")),
        ("Efficiency", f"{_num(c.get('away_efficiency_adjustment'), signed=True)} / {_num(c.get('home_efficiency_adjustment'), signed=True)}", state("efficiency")),
        ("Turnover edge", _num(c.get("turnover_edge_home_points"), signed=True), f"Home-side adjustment • {state('turnovers')}"),
        ("Strength of schedule", _num(c.get("sos_edge_home_points"), signed=True), f"Home-side adjustment • {state('sos')}"),
        ("Home field", _num(c.get("home_field_points"), signed=True), "Structural home-field adjustment"),
    ]
    cards = ''.join(f'<div class="cfbm5-feature"><div class="cfbm5-feature-top"><b>{escape(label)}</b><strong>{escape(value)}</strong></div><span>{escape(note)}</span></div>' for label, value, note in rows)
    away_qb = _clean(c.get("away_qb_state")) or "UNVERIFIED • ZERO IMPACT"
    home_qb = _clean(c.get("home_qb_state")) or "UNVERIFIED • ZERO IMPACT"
    return '<div class="cfbm5-feature-list">' + cards + '</div><div class="cfbm5-firewall"><b>QB data firewall:</b> ' + escape(away_name) + ' ' + escape(away_qb) + ' • ' + escape(home_name) + ' ' + escape(home_qb) + '. Missing/unverified QB data remains zero model impact.</div>'


def render_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    base = prior.prior.prior
    st.markdown(prior._CSS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)
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
    display_game = prior.prior._attach_verified_market(base._display_game(game))
    visuals = base._resolve_visuals(display_game)
    st.markdown(prior._matchup_header(display_game, away, home, visuals=visuals), unsafe_allow_html=True)
    st.markdown(prior._decision_html(display_game, raw, final), unsafe_allow_html=True)
    st.markdown(prior._why_html(raw, final), unsafe_allow_html=True)
    st.markdown(prior._freshness_html(display_game), unsafe_allow_html=True)
    away_name = _clean(away.get("team")) or _clean(display_game.get("away_team")) or "Away"
    home_name = _clean(home.get("team")) or _clean(display_game.get("home_team")) or "Home"
    with st.expander("🏟️ Team profiles & availability", expanded=False):
        st.markdown(_team_profiles_html(away, home, visuals=visuals), unsafe_allow_html=True)
    with st.expander("🔎 Data source details", expanded=False):
        st.markdown('<div class="cfbm5-detail-note">Source diagnostics are kept here for transparency without crowding the primary team cards. They remain evidence-only and do not alter certified betting probabilities.</div>', unsafe_allow_html=True)
        st.markdown(base.frozen.prior.frozen_step5.frozen_v3._team_data_diagnostics(team_diag), unsafe_allow_html=True)
    with st.expander("🧠 Model details", expanded=False):
        st.markdown(_model_dashboard_html(raw, final, away_name=away_name, home_name=home_name), unsafe_allow_html=True)
        st.markdown(_feature_contributions_html(raw, away_name=away_name, home_name=home_name), unsafe_allow_html=True)
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
    if _clean(market).lower() == "moneyline":
        return render_moneyline_hub(section_header, status_info, team_logo, h)
    return prior.render_cfb_hub(market, section_header, status_info, team_logo, h)


__all__ = ["MODEL_VERSION", "FROZEN_MONEYLINE_OWNER", "SPORTSBOOK_PROJECTION_INFLUENCE", "MAY_MODIFY_PROJECTION", "market_value_verdict", "human_reason_summary", "render_moneyline_hub", "render_cfb_hub"]
