"""CFB Player Props Page 3 V1 — Player Prop Intelligence Lab.

Professional Analytics V2 keeps every frozen model/data owner intact while
presenting the verified packet as a compact mobile-first analytics dashboard.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    def st_autorefresh(*args, **kwargs):
        return 0

import cfb_over_under_logo_resolver_v3 as logo_exact
import cfb_player_props_model_v1 as frozen_model
import cfb_player_props_page3_analysis_v1 as page3_analysis
import cfb_player_props_page3_context_v1 as page3_context
import cfb_player_props_page3_line_lab_v1 as line_lab
import cfb_player_props_page3_professional_v1 as professional

SPORTSBOOK_PROJECTION_INFLUENCE = frozen_model.SPORTSBOOK_PROJECTION_INFLUENCE
MARKET_LABELS = {
    "passing_yards": "Passing Yards",
    "rushing_yards": "Rushing Yards",
    "receiving_yards": "Receiving Yards",
    "receiving_receptions": "Receptions",
    "passing_touchdowns": "Passing TDs",
    "touchdowns": "Touchdowns",
}

CSS = """
<style>
#cfbpp3-top{position:absolute;top:0}
.cfbpp3-shell,.cfbpp3-panel{border:1px solid rgba(125,211,252,.2);background:radial-gradient(circle at 88% 6%,rgba(14,165,233,.12),transparent 31%),linear-gradient(145deg,rgba(2,8,23,.99),rgba(7,20,36,.99));border-radius:22px;box-shadow:0 18px 48px rgba(0,0,0,.24)}
.cfbpp3-shell{padding:18px;margin-bottom:10px}.cfbpp3-panel{padding:14px 15px;margin:6px 0 12px}
.cfbpp3-kicker,.cfbpp3-section{font-size:.69rem;font-weight:950;letter-spacing:.15em;color:#7dd3fc;text-transform:uppercase}.cfbpp3-section{margin:16px 0 8px}
.cfbpp3-title{font-size:clamp(1.45rem,4vw,2.35rem);font-weight:950;letter-spacing:-.045em;color:#f8fafc;margin:.24rem 0}.cfbpp3-sub{font-size:.78rem;color:#99b1c5;max-width:820px}
.cfbpp3-hero{display:flex;gap:12px;align-items:center;margin-top:13px}.cfbpp3-face,.cfbpp3-logo{width:60px;height:60px;border-radius:17px;object-fit:cover;border:1px solid rgba(125,211,252,.27);background:#07111f;box-shadow:0 8px 24px rgba(0,0,0,.2)}.cfbpp3-logo{object-fit:contain;padding:6px}.cfbpp3-name{font-size:1.12rem;font-weight:950;color:#f8fafc}.cfbpp3-meta{font-size:.76rem;color:#a7bacb}.cfbpp3-chip{display:inline-flex;margin:7px 5px 0 0;border:1px solid rgba(125,211,252,.22);border-radius:999px;padding:5px 8px;font-size:.62rem;font-weight:900;color:#daf4ff;background:rgba(14,165,233,.06)}
.cfbpp3-stat-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.cfbpp3-stat{min-width:0;border:1px solid rgba(125,211,252,.15);background:rgba(5,16,29,.78);border-radius:15px;padding:11px}.cfbpp3-stat span{display:block;color:#8fa9bf;font-size:.61rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase}.cfbpp3-stat b{display:block;color:#f8fafc;font-size:1.02rem;margin-top:3px;line-height:1.15;overflow-wrap:anywhere}.cfbpp3-stat small{display:block;color:#8fa9bf;font-size:.62rem;margin-top:4px;line-height:1.25}
.cfbpp3-decision{border:1px solid rgba(125,211,252,.24);background:linear-gradient(135deg,rgba(6,18,33,.98),rgba(8,29,49,.98));border-radius:19px;padding:14px 15px;margin:7px 0 11px}.cfbpp3-decision-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:9px}.cfbpp3-decision-label{font-size:.63rem;font-weight:950;letter-spacing:.13em;color:#7dd3fc}.cfbpp3-lean{display:inline-flex;border:1px solid rgba(125,211,252,.3);border-radius:999px;padding:5px 8px;font-size:.62rem;font-weight:950;color:#e4f7ff;background:rgba(14,165,233,.08)}
.cfbpp3-evidence-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.cfbpp3-evidence{border:1px solid rgba(125,211,252,.15);background:rgba(5,16,29,.76);border-radius:15px;padding:12px}.cfbpp3-evidence b{color:#f8fafc;font-size:.76rem}.cfbpp3-evidence p{color:#a9bdcc;font-size:.72rem;line-height:1.45;margin:6px 0 0}
.cfbpp3-table-wrap{overflow-x:auto;border:1px solid rgba(125,211,252,.14);border-radius:14px}.cfbpp3-table{width:100%;border-collapse:collapse;font-size:.72rem;background:rgba(5,14,25,.72)}.cfbpp3-table th{padding:9px 10px;text-align:left;color:#8fcfed;background:rgba(14,165,233,.06);font-size:.61rem;letter-spacing:.07em;text-transform:uppercase;white-space:nowrap}.cfbpp3-table td{padding:9px 10px;border-top:1px solid rgba(148,163,184,.12);color:#e4edf5;white-space:nowrap}.cfbpp3-note{font-size:.69rem;color:#8fa9bf;margin-top:7px;line-height:1.4}.cfbpp3-good{color:#86efac!important}.cfbpp3-warn{color:#fde68a!important}.cfbpp3-risk{color:#fda4af!important}
.cfbpp3-top-btn{position:fixed;right:18px;bottom:22px;z-index:99999;text-decoration:none!important;background:#081727;border:1px solid rgba(125,211,252,.42);color:#e6f7ff!important;border-radius:999px;padding:9px 12px;font-size:.7rem;font-weight:950;box-shadow:0 10px 30px rgba(0,0,0,.3)}
div[data-testid="stSlider"]{padding-top:0!important}div[data-testid="stExpander"]{border-color:rgba(125,211,252,.14)!important;background:rgba(5,14,25,.45)!important}
@media(max-width:760px){.cfbpp3-shell{padding:14px;border-radius:18px}.cfbpp3-panel{padding:12px;border-radius:16px}.cfbpp3-face,.cfbpp3-logo{width:52px;height:52px}.cfbpp3-title{font-size:1.5rem}.cfbpp3-name{font-size:1rem}.cfbpp3-stat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbpp3-evidence-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbpp3-stat{padding:10px}.cfbpp3-stat b{font-size:.92rem}.cfbpp3-top-btn{right:10px;bottom:14px;padding:8px 10px}}
</style>
"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{float(value)*100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _price(value: Any) -> str:
    try:
        n = int(value)
        return f"+{n}" if n > 0 else str(n)
    except (TypeError, ValueError):
        return "—"


def _friendly_timestamp(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return "Update time unavailable"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        dt = dt.astimezone(ZoneInfo("America/Phoenix"))
        clock = dt.strftime("%I:%M %p").lstrip("0")
        return f"Updated {clock} MST"
    except (TypeError, ValueError, ZoneInfo.KeyError):
        return f"Updated {raw}"


def _stamp_short(value: Any) -> str:
    friendly = _friendly_timestamp(value)
    return friendly.replace("Updated ", "") if friendly.startswith("Updated ") else "—"


def _team_logo(context: dict[str, Any], player: Any) -> str:
    try:
        visuals = logo_exact.resolve_visuals(context.get("game") or context)
        side = "away" if _text(getattr(player, "official_team_id", "")) == _text(context.get("away_team_id")) else "home"
        return _text((visuals.get(side) or {}).get("logo"))
    except Exception:
        return ""


def _stat_grid(items: Sequence[tuple[str, str, str]]) -> str:
    cards = "".join(
        f'<div class="cfbpp3-stat"><span>{escape(label)}</span><b>{escape(value)}</b><small>{escape(sub)}</small></div>'
        for label, value, sub in items
    )
    return f'<div class="cfbpp3-stat-grid">{cards}</div>'


def _table_html(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    heads = "".join(f"<th>{escape(str(col))}</th>" for col in frame.columns)
    body = []
    for _, row in frame.iterrows():
        body.append("<tr>" + "".join(f"<td>{escape(_text(value) or '—')}</td>" for value in row.tolist()) + "</tr>")
    return f'<div class="cfbpp3-table-wrap"><table class="cfbpp3-table"><thead><tr>{heads}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _book_rows(observations) -> list[dict[str, Any]]:
    books: dict[str, dict[str, Any]] = {}
    for row in observations or []:
        if isinstance(row, Mapping):
            get = row.get
        else:
            get = lambda key, default=None, obj=row: getattr(obj, key, default)
        book = _text(get("sportsbook")) or "Unknown"
        item = books.setdefault(book, {"Book": book, "Over": "—", "Under": "—", "Updated": "—", "_stamp": ""})
        side = _text(get("side")).lower()
        line = get("line")
        if side in {"over", "under"} and line is not None:
            label = "Over" if side == "over" else "Under"
            item[label] = f"{'O' if side == 'over' else 'U'} {_fmt(line)} {_price(get('price'))}"
        stamp = _text(get("observed_at_utc"))
        if stamp > item["_stamp"]:
            item["_stamp"] = stamp
            item["Updated"] = _stamp_short(stamp)
    return [{k: v for k, v in books[key].items() if k != "_stamp"} for key in sorted(books, key=str.casefold)]


def _hero(context: dict[str, Any], packet: dict[str, Any]) -> None:
    player = context["player"]
    face = _text(getattr(player, "headshot_url", ""))
    logo = _team_logo(context, player)
    images = ""
    if face:
        images += f'<img class="cfbpp3-face" src="{escape(face)}" alt="player">'
    if logo:
        images += f'<img class="cfbpp3-logo" src="{escape(logo)}" alt="team">'
    availability = _text((packet.get("availability") or {}).get("state")) or "UNVERIFIED"
    opponent = context.get("home_team") if _text(player.official_team_id) == _text(context.get("away_team_id")) else context.get("away_team")
    market = MARKET_LABELS.get(context["market_key"], context["market_key"])
    line = _fmt((packet.get("line_lab") or {}).get("line"))
    freshness = _friendly_timestamp((packet.get("quality") or {}).get("latest_market_timestamp"))
    kickoff = _text(context.get("kickoff_phoenix")) or _text(context.get("kickoff_iso")) or "Kickoff unavailable"
    st.markdown(
        f'''<div class="cfbpp3-shell"><div class="cfbpp3-kicker">CFB • PLAYER PROPS • PROFESSIONAL ANALYTICS V2</div><div class="cfbpp3-title">{escape(player.canonical_name)} • {escape(market)}</div><div class="cfbpp3-sub">Verified player-prop intelligence, market context and matchup evidence in one compact decision dashboard.</div><div class="cfbpp3-hero">{images}<div><div class="cfbpp3-name">{escape(player.canonical_name)}</div><div class="cfbpp3-meta">{escape(player.position)} • {escape(player.team_name)} vs {escape(_text(opponent))}</div><span class="cfbpp3-chip">{escape(availability)}</span><span class="cfbpp3-chip">LINE {escape(line)}</span><span class="cfbpp3-chip">{escape(kickoff)}</span><span class="cfbpp3-chip">{escape(freshness)}</span></div></div></div>''',
        unsafe_allow_html=True,
    )


def _decision(view: Mapping[str, Any]) -> None:
    decision = view.get("decision") or {}
    lean = _text(decision.get("lean")) or "NO LEAN"
    state = _text(decision.get("evidence_state")) or "LIMITED SAMPLE"
    st.markdown('<div class="cfbpp3-section">MODEL DECISION • KYRE PROJECTION VS CURRENT MARKET</div>', unsafe_allow_html=True)
    grid = _stat_grid((
        ("Kyre Projection", _fmt(decision.get("projection")), state),
        ("Market Line", _fmt(decision.get("market_consensus")), "Verified consensus"),
        ("Selected Line", _fmt(decision.get("selected_line")), "Line Lab target"),
        ("Projection − Market", _fmt(decision.get("market_margin")), "Independent model edge"),
    ))
    st.markdown(
        f'<div class="cfbpp3-decision"><div class="cfbpp3-decision-head"><div class="cfbpp3-decision-label">KYRE SPORTS AI • FROZEN MODEL</div><span class="cfbpp3-lean">MODEL LEAN • {escape(lean)}</span></div>{grid}<div class="cfbpp3-note">Over {_pct(decision.get("over_probability"))} • Under {_pct(decision.get("under_probability"))} • Selected-line margin {_fmt(decision.get("margin"))}</div></div>',
        unsafe_allow_html=True,
    )


def _recent_table(block: Mapping[str, Any]) -> pd.DataFrame:
    rows = []
    for row in block.get("rows") or ():
        item = {
            "Date": row.get("game_date") or row.get("date") or row.get("event_id") or "—",
            "Opponent": row.get("opponent_name") or "—",
            "Result": row.get("value") if row.get("value") is not None else row.get("combined_total"),
        }
        for key, label in (("pass_attempts", "ATT"), ("completions", "CMP"), ("completion_percentage", "CMP%"), ("yards_per_attempt", "Y/A"), ("passing_touchdowns", "TD"), ("interceptions", "INT")):
            if row.get(key) is not None:
                item[label] = row.get(key)
        rows.append(item)
    return pd.DataFrame(rows)


def _team_history_table(block: Mapping[str, Any], context: Mapping[str, Any]) -> pd.DataFrame:
    matchup = f"{_text(context.get('away_team')) or 'Away'} vs {_text(context.get('home_team')) or 'Home'}"
    rows = []
    for row in block.get("rows") or ():
        away = row.get("away_points")
        home = row.get("home_points")
        score = f"{away}–{home}" if away is not None and home is not None else "—"
        total = row.get("combined_total")
        if total is None and away is not None and home is not None:
            try:
                total = float(away) + float(home)
                total = int(total) if float(total).is_integer() else total
            except (TypeError, ValueError):
                total = None
        rows.append({"Date": row.get("date") or row.get("game_date") or "—", "Matchup": matchup, "Score": score, "Total": total if total is not None else "—"})
    return pd.DataFrame(rows, columns=["Date", "Matchup", "Score", "Total"])


def _compact_window(label: str, part: Mapping[str, Any]) -> tuple[str, str, str]:
    sample = int(part.get("sample_size") or 0)
    rate = part.get("hit_rate")
    hits = part.get("hits")
    value = f"{_pct(rate)} • {hits}/{sample}" if rate is not None else f"n={sample}"
    sub = f"Avg {_fmt(part.get('average'))}" if part.get("average") is not None else "Verified sample"
    return label, value, sub


def render_cfb_player_props_page3() -> None:
    st.markdown('<div id="cfbpp3-top"></div>', unsafe_allow_html=True)
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<a class="cfbpp3-top-btn" href="#cfbpp3-top">↑ TOP</a>', unsafe_allow_html=True)
    st_autorefresh(interval=30_000, key="cfbpp3_live_market_refresh")

    if st.button("← Back to Game Props", key="cfbpp3_back_to_page2", use_container_width=False):
        page3_context.clear_page3_selection(st.session_state, st.query_params)
        st.rerun()

    context = page3_context.resolve_page3_context(st.session_state, st.query_params)
    if _text(context.get("state")) != "ready":
        st.error(_text(context.get("reason")) or "Selected player prop is unavailable.")
        return

    packet = page3_analysis.build_page3_analysis(context, selected_line=None)
    current = context["market_key"]
    options = list(dict.fromkeys([current, *list(packet.get("available_markets") or ())]))
    if len(options) > 1:
        selected_market = st.radio("Market", options, index=options.index(current), horizontal=True, format_func=lambda key: MARKET_LABELS.get(key, key), key="cfbpp3_market_selector")
        if selected_market != current and page3_context.switch_page3_market(st.session_state, st.query_params, selected_market):
            st.rerun()

    market = packet.get("market") or {}
    identity = f"{context['official_game_id']}:{context['official_player_id']}:{current}"
    initial = packet.get("line_lab", {}).get("line") or line_lab.default_line(current, consensus_line=market.get("consensus_line"), handoff_line=context.get("handoff_line"))
    if st.session_state.get("cfbpp3_line_identity") != identity:
        st.session_state["cfbpp3_line_identity"] = identity
        st.session_state["cfbpp3_line"] = initial
    slider_state_key=f"cfbpp3_slider_{identity}"
    widget_line=st.session_state.get(slider_state_key)
    if widget_line is not None:
        active_line = float(widget_line)
    else:
        active_line = float(st.session_state.get("cfbpp3_line") or initial)
    st.session_state["cfbpp3_line"] = active_line
    packet = page3_analysis.reline_page3_analysis(packet, active_line)
    view = professional.build_professional_view(context, packet, selected_line=active_line)

    _hero(context, packet)
    _decision(view)

    projection = packet.get("projection") or {}
    market = packet.get("market") or {}
    low, high, step = line_lab.LINE_BOUNDS[current]
    st.markdown('<div class="cfbpp3-section">LINE LAB</div>', unsafe_allow_html=True)
    st.markdown(
        _stat_grid((("Model Marker", _fmt(projection.get("projection")), "Frozen projection"), ("Market Marker", _fmt(market.get("consensus_line")), "Current consensus"), ("Verified Books", str(int(market.get("book_count") or 0)), "Live market inputs"), ("Selected", _fmt(active_line), "Move slider below"))),
        unsafe_allow_html=True,
    )
    if slider_state_key in st.session_state:
        selected_line = st.slider("Move the line", min_value=float(low), max_value=float(high), step=float(step), key=slider_state_key)
    else:
        selected_line = st.slider("Move the line", min_value=float(low), max_value=float(high), value=active_line, step=float(step), key=slider_state_key)
    st.session_state["cfbpp3_line"] = selected_line
    packet = page3_analysis.reline_page3_analysis(packet, selected_line)
    view = professional.build_professional_view(context, packet, selected_line=selected_line)
    lab = packet["line_lab"]
    st.markdown(
        _stat_grid((("Over Probability", _pct(lab.get("over_probability")), "At selected line"), ("Under Probability", _pct(lab.get("under_probability")), "At selected line"), ("Projection Margin", _fmt(lab.get("margin")), "Projection − selected"), ("Sample", f"{int(lab.get('sample_count') or 0)}/{frozen_model.MIN_SAMPLE}", "Verified games"))),
        unsafe_allow_html=True,
    )
    if not lab.get("model_ready"):
        st.caption(f"Model probability unavailable • verified sample {int(lab.get('sample_count') or 0)}/{frozen_model.MIN_SAMPLE} required.")
    curve = packet.get("probability_curve") or []
    if curve and curve[0].get("over_probability") is not None:
        with st.expander("Probability curve", expanded=False):
            df = pd.DataFrame([{"Line": r["line"], "Over": r["over_probability"], "Under": r["under_probability"]} for r in curve]).set_index("Line")
            st.line_chart(df)

    st.markdown('<div class="cfbpp3-section">LAST 3 • LAST 5 • RECENT PRODUCTION</div>', unsafe_allow_html=True)
    last3 = view.get("last3") or {}
    last5 = view.get("last5") or {}
    season = (packet.get("history") or {}).get("season") or {}
    st.markdown(_stat_grid((_compact_window("LAST 3", last3), _compact_window("LAST 5", last5), _compact_window("SEASON", season), ("History Source", ", ".join((view.get("quality") or {}).get("history_sources") or ()) or "—", "Verified only"))), unsafe_allow_html=True)
    recent_frame = _recent_table(last5)
    if not recent_frame.empty:
        st.markdown(_table_html(recent_frame), unsafe_allow_html=True)
    else:
        st.caption("Verified recent player history unavailable.")
    chart = (packet.get("history") or {}).get("chart") or []
    if chart:
        with st.expander("Recent production chart", expanded=False):
            frame = pd.DataFrame([{"Game": r.get("game_date") or r.get("event_id"), "Production": r.get("value"), "Selected Line": r.get("comparison_line")} for r in reversed(chart)])
            st.line_chart(frame.set_index("Game"))

    st.markdown('<div class="cfbpp3-section">SPORTSBOOK MARKET • SPORTSBOOK BOARD</div>', unsafe_allow_html=True)
    book_rows = _book_rows(market.get("observations"))
    if book_rows:
        st.markdown(_table_html(pd.DataFrame(book_rows, columns=["Book", "Over", "Under", "Updated"])), unsafe_allow_html=True)
        bo = market.get("best_over") or {}
        bu = market.get("best_under") or {}
        st.caption(f"Best Over: {_text(bo.get('sportsbook')) or '—'} • O {_fmt(bo.get('line'))} {_price(bo.get('price'))}   |   Best Under: {_text(bu.get('sportsbook')) or '—'} • U {_fmt(bu.get('line'))} {_price(bu.get('price'))}")
    else:
        st.info("Current verified sportsbook market unavailable. Player/market identity remains unchanged.")

    movement = view.get("market_movement") or {}
    st.markdown('<div class="cfbpp3-section">MARKET MOVEMENT</div>', unsafe_allow_html=True)
    if movement.get("available"):
        st.markdown(_stat_grid((("Opening", _fmt(movement.get("opening_line")), _text(movement.get("sportsbook")) or _text(movement.get("source")) or "Verified"), ("Current", _fmt(movement.get("current_line")), "Market line"), ("Change", f"{float(movement.get('delta') or 0):+.1f}", "Opening → current"), ("Direction", "UP" if float(movement.get("delta") or 0) > 0 else "DOWN" if float(movement.get("delta") or 0) < 0 else "FLAT", "Verified movement"))), unsafe_allow_html=True)
    else:
        st.markdown(_stat_grid((("Opening", "—", "Not verified"), ("Current", _fmt(market.get("consensus_line")), "Verified market"), ("Change", "—", "Waiting on opener"), ("Status", "UNAVAILABLE", "No directional claim"))), unsafe_allow_html=True)

    st.markdown('<div class="cfbpp3-section">MATCHUP INTELLIGENCE</div>', unsafe_allow_html=True)
    direct = view.get("direct_opponent") or {}
    team = view.get("team_matchup") or {}
    role = view.get("opponent_vs_role") or {}
    matchup = packet.get("matchup") or {}
    direct_sub = f"Avg {_fmt(direct.get('average'))} • hit {_pct(direct.get('hit_rate'))}" if direct.get("available") else "No verified prior matchup sample."
    role_value = str(int(role.get("sample_size") or 0)) if role.get("available") else "—"
    role_sub = _text(role.get("detail")) or ("Verified comparable-player sample" if role.get("available") else "No directional claim")
    st.markdown(_stat_grid((("OPPONENT DEFENSE", _text(matchup.get("label")) or "CHECK", _text(matchup.get("detail")) or _text(matchup.get("message")) or "Defense data unavailable"), ("DIRECT PLAYER VS OPPONENT", str(int(direct.get("sample_size") or 0)) if direct.get("available") else "—", direct_sub), ("OPPONENT VS ROLE", role_value, role_sub), ("TEAM MATCHUP HISTORY", str(int(team.get("sample_size") or 0)) if team.get("available") else "—", ", ".join(team.get("sources") or ()) or _text(team.get("status")) or "Unavailable"))), unsafe_allow_html=True)

    opportunity = packet.get("opportunity") or {}
    game_status = _text(context.get("status")) or "Unverified"
    venue = _text(context.get("venue")) or "Unavailable"
    broadcast = _text(context.get("broadcast")) or "Unavailable"
    opportunity_value = str(len(opportunity.get("metrics") or {})) if opportunity.get("available") else "—"
    st.markdown(_stat_grid((("GAME STATUS", game_status, "Live-state context"), ("VENUE", venue, "Game environment"), ("BROADCAST", broadcast, "Coverage"), ("OPPORTUNITY", opportunity_value, "Verified fields" if opportunity.get("available") else "Verified opportunity fields unavailable for this market."))), unsafe_allow_html=True)
    if opportunity.get("available"):
        rows = [{"Metric": name.replace("_", " ").title(), "Average": round(float(data["average"]), 1), "Sample": int(data["sample_size"])} for name, data in opportunity.get("metrics", {}).items()]
        with st.expander("Opportunity detail", expanded=False):
            st.markdown(_table_html(pd.DataFrame(rows)), unsafe_allow_html=True)

    st.markdown('<div class="cfbpp3-section">WHY THE MODEL SEES IT THIS WAY</div>', unsafe_allow_html=True)
    reasoning = view.get("reasoning") or packet.get("reasoning") or {}
    why = [str(item) for item in reasoning.get("why") or []]
    driver_text = " • ".join(why) if why else "No additional verified drivers available."
    bull = _text(reasoning.get("bull_case")) or "No additional verified bull-case evidence."
    bear = _text(reasoning.get("bear_case")) or "No additional verified risk evidence."
    st.markdown(f'<div class="cfbpp3-panel"><div class="cfbpp3-note">{escape(driver_text)}</div><div class="cfbpp3-evidence-grid"><div class="cfbpp3-evidence"><b class="cfbpp3-good">SUPPORTIVE EVIDENCE</b><p>{escape(bull)}</p></div><div class="cfbpp3-evidence"><b class="cfbpp3-risk">RISK EVIDENCE</b><p>{escape(bear)}</p></div></div></div>', unsafe_allow_html=True)

    st.markdown('<div class="cfbpp3-section">TEAM MATCHUP HISTORY</div>', unsafe_allow_html=True)
    if team.get("available"):
        st.caption(f"Historical team meetings are separate from player H2H • sample {int(team.get('sample_size') or 0)} • sources {', '.join(team.get('sources') or ()) or 'unavailable'}")
        team_frame = _team_history_table(team, context)
        st.markdown(_table_html(team_frame), unsafe_allow_html=True)
    else:
        status = _text(team.get("status"))
        st.caption(f"Verified team matchup history unavailable for this exact opponent identity{f' • {status}' if status else ''}.")

    st.markdown('<div class="cfbpp3-section">DATA QUALITY & SOURCES • EVIDENCE QUALITY</div>', unsafe_allow_html=True)
    quality = view.get("quality") or packet.get("quality") or {}
    history_sources = ", ".join(quality.get("history_sources") or ()) or "Unavailable"
    sample_count = int(quality.get("model_sample_count") or 0)
    quality_status = "READY" if sample_count >= frozen_model.MIN_SAMPLE else "LIMITED"
    st.markdown(_stat_grid((("Model Sample", str(sample_count), f"Minimum {frozen_model.MIN_SAMPLE}"), ("Books", str(int(quality.get("verified_book_count") or 0)), "Verified market sources"), ("Availability", _text(quality.get("availability_state")) or "UNVERIFIED", "Player status"), ("Evidence", quality_status, f"History n={int(quality.get('history_sample_size') or 0)}"))), unsafe_allow_html=True)
    st.caption(f"History sources actually used: {history_sources} • Latest history: {_friendly_timestamp(quality.get('latest_history_timestamp'))}")
    st.caption(f"Latest verified market observation: {_friendly_timestamp(quality.get('latest_market_timestamp'))} • Sportsbook projection influence: {SPORTSBOOK_PROJECTION_INFLUENCE:.1f}")

    source_status = view.get("source_status") or {}
    with st.expander("Source Audit", expanded=False):
        st.markdown('<div class="cfbpp3-section">ACTIVE FIELD SOURCES</div>', unsafe_allow_html=True)
        source_labels = (
            ("player_props", "Player Props / Sportsbook Lines"),
            ("game_lines", "Game Lines / Movement"),
            ("player_stats", "Player Stats"),
            ("game_state", "Game Status / Live State"),
            ("history", "Player / Matchup History"),
            ("availability", "Availability"),
        )
        for key, label in source_labels:
            block = source_status.get(key) or {}
            active = ", ".join(str(value).replace("_", " ").title() for value in block.get("active_provider_ids") or ()) or "No approved active source observed"
            actual = ", ".join(block.get("actual_provider_labels") or ()) or "No source label observed"
            stamp = _text(block.get("newest_timestamp"))
            suffix = f" • {_friendly_timestamp(stamp)}" if stamp else ""
            st.caption(f"{label}: **{active}** • Observed: {actual}{suffix}")


__all__ = ["MARKET_LABELS", "SPORTSBOOK_PROJECTION_INFLUENCE", "render_cfb_player_props_page3"]
