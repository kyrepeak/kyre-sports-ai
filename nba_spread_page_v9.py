"""NBA Spread Page V9 — S-tier Page-1 analytics surface.

Additive presentation successor over frozen V8. V9 preserves Step-9/Step-10
model, probability, decision and ranking ownership while exposing richer verified
multi-book market intelligence in a decision-first analytics hierarchy. Page 2
remains owned by V8 and is reached through one explicit Streamlit CTA.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from html import escape
import math
from typing import Any

import streamlit as st

import nba_spread_page_v8 as prior
import nba_spread_live_data_repair_v3 as live_v3
from nba_spread_decision_board_data_v2 import build_decision_board_state_v2
from nba_spread_team_identity_v1 import resolve_nba_team_logo
from nba_spread_page1_handoff_v1 import apply_analysis_handoff

MODEL_VERSION = "NBA_SPREAD_PAGE_V9_S_TIER_ANALYTICS_V2"
FROZEN_PARENT_PAGE = "nba_spread_page_v8"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_PAGE2 = False

_CSS = r"""
<style>
.nba9-hero{position:relative;overflow:hidden;border:1px solid rgba(84,207,255,.30);border-radius:24px;padding:20px;background:radial-gradient(circle at 88% 10%,rgba(48,169,255,.18),transparent 30%),linear-gradient(145deg,#07111d 0%,#081a2a 55%,#0b2638 100%);box-shadow:0 16px 48px rgba(0,0,0,.28);margin:8px 0 12px}.nba9-kicker{font-size:.68rem;font-weight:950;letter-spacing:.15em;color:#6edcff}.nba9-title{font-size:clamp(1.85rem,5vw,2.6rem);font-weight:950;color:#f8fbff;letter-spacing:-.045em;margin:3px 0}.nba9-sub{font-size:.82rem;color:#91a9bb}.nba9-slate{display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid rgba(148,163,184,.13);border-radius:14px;padding:10px 12px;background:#08131f;margin:0 0 14px}.nba9-slate b{font-size:.9rem;color:#f6f9fb}.nba9-slate span{font-size:.71rem;color:#8198a9}.nba9-section{font-size:.7rem;font-weight:950;letter-spacing:.12em;color:#b8c9d5;margin:17px 1px 8px;text-transform:uppercase}.nba9-card{border:1px solid rgba(101,214,255,.22);border-radius:22px;background:linear-gradient(150deg,#07131f,#0a1d2d 58%,#0b2535);padding:16px;margin:0 0 10px;box-shadow:0 15px 38px rgba(0,0,0,.23)}.nba9-match{display:flex;justify-content:space-between;gap:14px;align-items:center}.nba9-teamblock{display:flex;align-items:center;gap:11px;min-width:0}.nba9-logos{display:flex;align-items:center}.nba9-logo,.nba9-mono{width:46px;height:46px;border-radius:50%;object-fit:contain;background:rgba(255,255,255,.055);padding:4px;border:1px solid rgba(255,255,255,.055)}.nba9-logo+ .nba9-logo,.nba9-mono+ .nba9-logo,.nba9-logo+ .nba9-mono,.nba9-mono+ .nba9-mono{margin-left:-8px}.nba9-mono{display:flex;align-items:center;justify-content:center;color:#daf5ff;font-size:.65rem;font-weight:950}.nba9-matchup{font-size:1.15rem;font-weight:950;color:#f8fbff;letter-spacing:-.025em}.nba9-names{font-size:.7rem;color:#8098aa;margin-top:3px;white-space:normal}.nba9-time{text-align:right;white-space:nowrap;font-size:.83rem;font-weight:950;color:#f3f8fb}.nba9-date{font-size:.64rem;color:#728b9d;margin-top:3px}.nba9-verdict{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,.65fr);gap:10px;margin-top:14px}.nba9-primary{border:1px solid rgba(57,211,132,.24);border-radius:17px;padding:14px;background:linear-gradient(145deg,rgba(11,58,48,.62),rgba(7,30,35,.72))}.nba9-primary.wait{border-color:rgba(101,214,255,.18);background:rgba(6,19,30,.62)}.nba9-eyebrow{font-size:.61rem;font-weight:950;letter-spacing:.12em;color:#8fcfa9}.nba9-primary.wait .nba9-eyebrow{color:#78cfee}.nba9-pick{font-size:1.28rem;font-weight:950;color:#f8fff9;margin-top:4px}.nba9-pct{font-size:clamp(2.25rem,9vw,3.35rem);font-weight:950;color:#aaf0c4;letter-spacing:-.06em;line-height:.98;margin-top:7px}.nba9-pctlabel{font-size:.65rem;font-weight:900;letter-spacing:.08em;color:#80af91;margin-top:3px}.nba9-strength{display:inline-flex;border:1px solid rgba(100,220,150,.24);background:rgba(51,180,106,.12);border-radius:999px;padding:4px 8px;color:#acebc6;font-size:.62rem;font-weight:950;margin-top:9px}.nba9-edgebox{border:1px solid rgba(101,214,255,.17);border-radius:17px;padding:13px;background:rgba(5,15,25,.58);display:flex;flex-direction:column;justify-content:center}.nba9-edgebox small{font-size:.59rem;font-weight:950;letter-spacing:.11em;color:#7294aa}.nba9-edgebox b{font-size:1.38rem;color:#eef9ff;margin-top:4px;letter-spacing:-.03em}.nba9-edgebox span{font-size:.65rem;color:#7892a4;margin-top:3px}.nba9-compare{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:9px}.nba9-metric{border:1px solid rgba(148,163,184,.11);border-radius:13px;background:rgba(4,12,20,.48);padding:11px}.nba9-metric small{display:block;font-size:.58rem;letter-spacing:.1em;font-weight:950;color:#71899b}.nba9-metric b{display:block;font-size:.96rem;color:#edf7fb;margin-top:5px}.nba9-metric span{display:block;font-size:.63rem;color:#7891a2;margin-top:3px}.nba9-market{border:1px solid rgba(101,214,255,.14);border-radius:15px;padding:11px;margin-top:9px;background:rgba(7,18,29,.55)}.nba9-markethead{display:flex;justify-content:space-between;gap:10px;align-items:center}.nba9-markethead b{font-size:.7rem;color:#dcebf4;letter-spacing:.07em}.nba9-markethead span{font-size:.62rem;color:#78a8c2}.nba9-books{display:flex;gap:6px;overflow-x:auto;padding:8px 0 2px;scrollbar-width:none}.nba9-books::-webkit-scrollbar{display:none}.nba9-book{flex:0 0 auto;border:1px solid rgba(148,163,184,.12);border-radius:10px;background:#07111b;padding:7px 8px;min-width:91px}.nba9-book strong{display:block;font-size:.62rem;color:#aec1ce}.nba9-book b{display:block;font-size:.73rem;color:#f0f7fb;margin-top:3px}.nba9-best{font-size:.64rem;color:#8fb3c7;margin-top:7px;line-height:1.5}.nba9-move{display:flex;justify-content:space-between;gap:10px;border-top:1px solid rgba(148,163,184,.09);margin-top:9px;padding-top:8px}.nba9-move small{font-size:.58rem;color:#72899b;font-weight:950;letter-spacing:.08em}.nba9-move b{font-size:.7rem;color:#dbeaf3}.nba9-inj{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.nba9-chip{border:1px solid rgba(148,163,184,.11);border-radius:999px;padding:6px 9px;background:rgba(5,13,22,.5);font-size:.64rem;color:#a9bbc7}.nba9-signals{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.nba9-signal{font-size:.58rem;font-weight:900;letter-spacing:.04em;color:#8ecce6;border:1px solid rgba(91,198,240,.13);border-radius:8px;padding:5px 7px;background:rgba(24,86,112,.10)}.nba9-pending{font-size:.7rem;color:#8ca1b0;margin-top:9px;border:1px dashed rgba(148,163,184,.16);border-radius:11px;padding:9px}.nba9-opps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-bottom:12px}.nba9-opp{border:1px solid rgba(57,211,132,.20);border-radius:13px;background:rgba(9,48,38,.38);padding:10px}.nba9-opp small{font-size:.58rem;color:#83cda0;font-weight:950}.nba9-opp b{display:block;font-size:.82rem;color:#f4fff7;margin-top:3px}.nba9-opp span{display:block;font-size:.62rem;color:#84a492;margin-top:3px}.nba9-diag{font-size:.73rem;color:#8da2b2;line-height:1.65}.nba9-diag b{color:#e2edf4}.nba9-empty{border:1px dashed rgba(148,163,184,.18);border-radius:14px;padding:14px;color:#8399aa;font-size:.78rem}
@media(max-width:800px){.nba9-opps{grid-template-columns:1fr}.nba9-verdict{grid-template-columns:1.25fr .75fr}}
@media(max-width:600px){.nba9-card{padding:13px}.nba9-match{align-items:flex-start}.nba9-logo,.nba9-mono{width:40px;height:40px}.nba9-time{font-size:.75rem}.nba9-names{font-size:.64rem}.nba9-verdict{grid-template-columns:1fr}.nba9-compare{grid-template-columns:1fr 1fr}.nba9-pct{font-size:2.7rem}.nba9-slate{align-items:flex-start;flex-direction:column}}
</style>
"""


def _clean(value: object) -> str:
    return str(value or "").strip()


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _line(value: object) -> str:
    parsed = _number(value)
    if parsed is None:
        return "—"
    return "PK" if math.isclose(parsed, 0.0, abs_tol=1e-9) else f"{parsed:+g}"


def _price(value: object) -> str:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return ""
    return f"{parsed:+d}"


def _pct(value: object) -> str:
    parsed = _number(value)
    return f"{parsed * 100.0:.1f}%" if parsed is not None else "—"


def _logo_html(code: str, url: str | None) -> str:
    if url:
        return f'<img class="nba9-logo" alt="{escape(code)} logo" src="{escape(url)}">'
    return f'<div class="nba9-mono">{escape(code)}</div>'


def _focus(record: Mapping[str, Any]) -> dict[str, Any]:
    away = _clean(record.get("away_tricode"))
    home = _clean(record.get("home_tricode"))
    decision = dict(record.get("decision") or {})
    cover = dict(record.get("cover") or {})
    pick = _clean(decision.get("pick_text"))
    if decision.get("verification") == "VERIFIED" and decision.get("decision_state") == "PLAY" and pick:
        side = away if pick.upper().startswith(away.upper()) else home if pick.upper().startswith(home.upper()) else ""
    else:
        side = ""
    away_prob = _number(cover.get("away_probability")) if cover.get("verification") == "VERIFIED" else None
    home_prob = _number(cover.get("home_probability")) if cover.get("verification") == "VERIFIED" else None
    if not side and away_prob is not None and home_prob is not None:
        side = away if away_prob >= home_prob else home
    prob = away_prob if side == away else home_prob if side == home else None
    title = pick if pick else "NO PLAY"
    strength = _clean(decision.get("pick_strength")) if decision.get("verification") == "VERIFIED" else ""
    return {"side": side, "probability": prob, "title": title, "strength": strength, "is_play": decision.get("verification") == "VERIFIED" and decision.get("decision_state") == "PLAY"}


def _quotes_html(record: Mapping[str, Any]) -> str:
    market = dict(record.get("market_intelligence") or {})
    if market.get("verification") != "VERIFIED":
        return ""
    away = _clean(record.get("away_tricode"))
    home = _clean(record.get("home_tricode"))
    quote_bits: list[str] = []
    for raw in list(market.get("quotes") or [])[:8]:
        if not isinstance(raw, Mapping):
            continue
        book = _clean(raw.get("sportsbook"))
        away_line = _line(raw.get("away_spread"))
        away_price = _price(raw.get("away_price"))
        price_bit = f" {away_price}" if away_price else ""
        quote_bits.append(f'<div class="nba9-book"><strong>{escape(book)}</strong><b>{escape(away)} {escape(away_line + price_bit)}</b></div>')
    best_away = dict(market.get("best_away") or {})
    best_home = dict(market.get("best_home") or {})
    best_parts: list[str] = []
    if best_away:
        best_parts.append(f'Best {away}: {best_away.get("sportsbook")} {_line(best_away.get("spread"))} {_price(best_away.get("price"))}'.strip())
    if best_home:
        best_parts.append(f'Best {home}: {best_home.get("sportsbook")} {_line(best_home.get("spread"))} {_price(best_home.get("price"))}'.strip())
    movement = dict(market.get("movement") or {})
    movement_html = ""
    if movement.get("verification") == "VERIFIED":
        movement_html = f'<div class="nba9-move"><small>LINE MOVEMENT</small><b>{escape(_clean(movement.get("label")))}</b></div>'
    count = int(market.get("sportsbook_count") or 0)
    return (
        '<div class="nba9-market">'
        f'<div class="nba9-markethead"><b>MARKET CONSENSUS</b><span>{count} verified book{"s" if count != 1 else ""}</span></div>'
        f'<div class="nba9-books">{"".join(quote_bits)}</div>'
        + (f'<div class="nba9-best">{escape(" • ".join(best_parts))}</div>' if best_parts else "")
        + movement_html
        + '</div>'
    )


def _decision_card_html(record: Mapping[str, Any]) -> str:
    away = _clean(record.get("away_tricode")) or "AWAY"
    home = _clean(record.get("home_tricode")) or "HOME"
    away_name = _clean(record.get("away_name")) or away
    home_name = _clean(record.get("home_name")) or home
    away_logo = record.get("away_logo") or resolve_nba_team_logo(away)
    home_logo = record.get("home_logo") or resolve_nba_team_logo(home)
    tip = _clean(record.get("tip_phoenix")) or "Time pending"
    date = _clean(record.get("date") or record.get("game_date_phoenix")) or "Date pending"
    venue = _clean(record.get("venue"))
    venue_bit = f" • {venue}" if venue else ""
    fair = dict(record.get("fair") or {})
    market = dict(record.get("market") or {})
    intelligence = dict(record.get("market_intelligence") or {})
    injuries = dict(record.get("injuries") or {})
    focus = _focus(record)

    verdict_cls = "" if focus["is_play"] else " wait"
    verdict_title = focus["title"] if focus["is_play"] else "NO PLAY"
    probability = focus["probability"]
    prob_html = f'<div class="nba9-pct">{escape(_pct(probability))}</div><div class="nba9-pctlabel">COVER PROBABILITY</div>' if probability is not None else '<div class="nba9-pending">Cover probability waiting for verified model + current market.</div>'
    strength_html = f'<div class="nba9-strength">{escape(focus["strength"])}</div>' if focus["strength"] else ""
    edge = _number(record.get("edge_points"))
    edge_value = f"{edge:.1f} pts" if edge is not None else "Pending"
    edge_sub = "LINE VALUE" if edge is not None else "Waiting for verified market"

    if intelligence.get("verification") == "VERIFIED":
        market_away = intelligence.get("consensus_away_spread")
        market_home = intelligence.get("consensus_home_spread")
        market_label = f"{away} {_line(market_away)} • {home} {_line(market_home)}"
    elif market.get("verification") == "VERIFIED":
        market_label = f"{away} {_line(market.get('away_spread'))} • {home} {_line(market.get('home_spread'))}"
    else:
        market_label = _clean(market.get("label")) or "Verification pending"

    fair_label = f"{away} {_line(fair.get('away_spread'))} • {home} {_line(fair.get('home_spread'))}" if fair.get("verification") == "VERIFIED" else _clean(fair.get("reason")) or "Verification pending"

    injury_bits = []
    for key in ("away_summary", "home_summary"):
        text = _clean(injuries.get(key))
        if text:
            injury_bits.append(f'<div class="nba9-chip">{escape(text)}</div>')

    signals: list[str] = []
    book_count = int(intelligence.get("sportsbook_count") or 0)
    if book_count:
        signals.append(f"{book_count} BOOKS VERIFIED")
    if fair.get("verification") == "VERIFIED":
        signals.append("FAIR LINE VERIFIED")
    if injuries.get("verification") == "VERIFIED":
        signals.append("INJURY CONTEXT VERIFIED")
    signal_html = '<div class="nba9-signals">' + ''.join(f'<span class="nba9-signal">{escape(item)}</span>' for item in signals) + '</div>' if signals else ""

    return f'''<article class="nba9-card" data-testid="nba-spread-v9-game-card">
      <div class="nba9-match">
        <div class="nba9-teamblock"><div class="nba9-logos">{_logo_html(away, away_logo)}{_logo_html(home, home_logo)}</div><div><div class="nba9-matchup">{escape(away)} @ {escape(home)}</div><div class="nba9-names">{escape(away_name)} at {escape(home_name + venue_bit)}</div></div></div>
        <div class="nba9-time">{escape(tip)}<div class="nba9-date">{escape(date)} • Phoenix</div></div>
      </div>
      <div class="nba9-verdict">
        <div class="nba9-primary{verdict_cls}"><div class="nba9-eyebrow">KYRE AI VERDICT</div><div class="nba9-pick">{escape(verdict_title)}</div>{prob_html}{strength_html}</div>
        <div class="nba9-edgebox"><small>LINE VALUE</small><b>{escape(edge_value)}</b><span>{escape(edge_sub)}</span></div>
      </div>
      <div class="nba9-compare">
        <div class="nba9-metric"><small>MARKET CONSENSUS</small><b>{escape(market_label)}</b><span>Verified sportsbook market</span></div>
        <div class="nba9-metric"><small>KYRE FAIR LINE</small><b>{escape(fair_label)}</b><span>Sportsbook-independent model</span></div>
      </div>
      {_quotes_html(record)}
      {('<div class="nba9-inj">' + ''.join(injury_bits) + '</div>') if injury_bits else ''}
      {signal_html}
    </article>'''


def _best_opportunities_html(rows: Sequence[Mapping[str, Any]]) -> str:
    cards: list[str] = []
    for index, row in enumerate(list(rows)[:3], start=1):
        pick = _clean(row.get("pick_text")) or "VERIFIED PLAY"
        strength = _clean(row.get("pick_strength")) or "Verified"
        grade = _clean(row.get("production_grade"))
        detail = " • ".join(item for item in (strength, grade) if item)
        cards.append(f'<div class="nba9-opp"><small>#{index} VERIFIED OPPORTUNITY</small><b>{escape(pick)}</b><span>{escape(detail)}</span></div>')
    return '<div class="nba9-opps">' + ''.join(cards) + '</div>' if cards else ""


def _load_schedule_and_market_once() -> tuple[dict, dict | None]:
    captured: dict[str, dict] = {}
    original = prior.frozen_v7.live_repair_page._load_verified_market_payload

    def _market_once(games: list[dict]) -> dict:
        if "payload" not in captured:
            captured["payload"] = dict(live_v3.load_market_payload_v3(games) or {})
        return captured["payload"]

    prior.frozen_v7.live_repair_page._load_verified_market_payload = _market_once
    try:
        schedule = prior.frozen_v7._load_launch_schedule()
    finally:
        prior.frozen_v7.live_repair_page._load_verified_market_payload = original
    return dict(schedule or {}), captured.get("payload")


@st.cache_data(ttl=90, show_spinner=False)
def _load_market_once(games: list[dict]) -> dict:
    return dict(live_v3.load_market_payload_v3(games) or {})


def render_nba_spread_page() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div data-testid="nba-spread-v9-s-tier-active" style="display:none!important"></div>', unsafe_allow_html=True)
    st.markdown('<div class="nba9-hero"><div class="nba9-kicker">KYRE SPORTS AI • NBA SPREAD</div><div class="nba9-title">NBA Spread Intelligence</div><div class="nba9-sub">Multi-book market consensus • sportsbook-independent fair line • verified decision intelligence</div></div>', unsafe_allow_html=True)

    schedule, captured_market = _load_schedule_and_market_once()
    if schedule.get("verification") != "VERIFIED":
        st.markdown('<div class="nba9-empty">Verified NBA schedule is temporarily unavailable. No matchup will be invented.</div>', unsafe_allow_html=True)
        return

    selected_id = prior._query_value("game_id")
    selected_date = prior._query_value("date")
    if selected_id:
        prior._render_selected(schedule, date=selected_date, game_id=selected_id)
        return

    slate_date, games = prior.frozen_v7._next_active_slate_games(list(schedule.get("games") or []))
    if not games:
        st.markdown('<div class="nba9-empty">No verified upcoming NBA games are available in the current rolling window.</div>', unsafe_allow_html=True)
        return

    market_payload = captured_market if isinstance(captured_market, Mapping) else _load_market_once(games)
    injury_payload = prior._load_injuries_once(games)
    public_payload = prior._load_public_once(games)
    history = prior._market_history(market_payload)
    board = build_decision_board_state_v2(
        games,
        market_payload,
        injury_payload,
        public_payload,
        now_utc=datetime.now(timezone.utc),
        market_history=history,
    )

    chain = [str(x) for x in market_payload.get("source_chain") or [] if str(x).strip()]
    source_text = " → ".join(chain) if chain else _clean(market_payload.get("source")) or "market verification pending"
    st.markdown(
        f'<div class="nba9-slate"><b>{escape(prior._human_slate_label(slate_date))}</b><span>{len(games)} game{"s" if len(games) != 1 else ""} • Phoenix time • {escape(source_text)}</span></div>',
        unsafe_allow_html=True,
    )

    opportunities = _best_opportunities_html(board.get("best_opportunities") or [])
    if opportunities:
        st.markdown('<div class="nba9-section">BEST OPPORTUNITIES</div>' + opportunities, unsafe_allow_html=True)

    st.markdown('<div class="nba9-section">NEXT SLATE</div>', unsafe_allow_html=True)
    game_by_key = {_clean(game.get("game_key")): game for game in games}
    for raw in board.get("games") or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        row["away_logo"] = resolve_nba_team_logo(_clean(row.get("away_tricode")))
        row["home_logo"] = resolve_nba_team_logo(_clean(row.get("home_tricode")))
        st.markdown(_decision_card_html(row), unsafe_allow_html=True)
        game = game_by_key.get(_clean(row.get("game_key")))
        if game and st.button("View Full Analysis →", key=f"nba_spread_v9_open_{_clean(row.get('game_key'))}", use_container_width=True):
            query = dict(st.query_params)
            patch = apply_analysis_handoff(st.session_state, query, game)
            if patch:
                st.query_params.clear()
                st.query_params.update(query)
                st.rerun()

    with st.expander("Sources & Diagnostics", expanded=False):
        st.markdown(
            f'<div class="nba9-diag"><b>Schedule:</b> {escape(_clean(schedule.get("verification")) or "UNAVAILABLE")} • NBA Official + ESPN NBA<br>'
            f'<b>Market:</b> {escape(_clean(market_payload.get("verification")) or "UNAVAILABLE")} • {escape(source_text)}<br>'
            f'<b>Injuries:</b> {escape(_clean(injury_payload.get("verification")) or "CHECK")}<br>'
            f'<b>Public betting:</b> {escape(_clean(public_payload.get("verification")) or "UNAVAILABLE")}<br>'
            f'<b>Model boundary:</b> frozen Step-9 / Step-10 • sportsbook projection influence 0.0%</div>',
            unsafe_allow_html=True,
        )


__all__ = [
    "FROZEN_PARENT_PAGE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PAGE2",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_decision_card_html",
    "render_nba_spread_page",
]
