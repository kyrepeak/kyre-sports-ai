"""NFL Game Totals V12 — premium selected-game Page 2 presentation.

V12 preserves the frozen S-tier Page 1/handoff from V11 and replaces only the
selected-game Page 2 presentation. Certified V8/V9/V10 analytics remain the
projection and market-read authorities. Matchup history and official injury
availability are display-only context with 0.0 model influence.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
import math
from typing import Any, Mapping
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v11 as v11
from nfl_game_totals_page2_context_v2 import load_availability, load_matchup_history

MODEL_VERSION = "NFL GAME TOTALS V12 • PAGE 2 S-TIER V2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MATCHUP_HISTORY_MODEL_INFLUENCE = 0.0
AVAILABILITY_MODEL_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False

page1 = v11.page1
foundation = v11.foundation
mobile = v11.mobile

_CSS = r'''
<style>
.kgt12{max-width:980px;margin:0 auto;color:#edf6fb}.kgt12 *{box-sizing:border-box}
.kgt12-back{display:inline-block;margin:2px 0 10px;color:#65c8f5!important;text-decoration:none!important;font-size:.62rem;font-weight:900}
.kgt12-card{border:1px solid #245773;border-radius:16px;background:linear-gradient(180deg,#071924,#07131b);padding:12px;margin:8px 0;box-shadow:0 14px 30px rgba(0,0,0,.18)}
.kgt12-hero{background:radial-gradient(circle at 50% -20%,#0d3651 0,#071923 45%,#07131b 100%);text-align:center;padding:15px 12px}.kgt12-kicker{color:#58c9f5;font-size:.48rem;font-weight:950;letter-spacing:.16em}.kgt12-title{font-size:1.38rem;font-weight:950;line-height:1.12;margin-top:5px}.kgt12-meta{font-size:.56rem;color:#8ea8b7;margin-top:5px}.kgt12-records{display:flex;justify-content:center;gap:22px;color:#708b9a;font-size:.48rem;margin-top:5px}
.kgt12-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:11px}.kgt12-stat{border:1px solid #28506a;border-radius:10px;background:#081722;padding:8px 6px;text-align:left}.kgt12-stat span{display:block;color:#7897aa;font-size:.39rem;font-weight:950;letter-spacing:.09em}.kgt12-stat b{display:block;font-size:1.02rem;margin-top:3px}.kgt12-stat.kyre b{color:#59c7ff}.kgt12-stat.edge b{color:#62e9be}.kgt12-stat.read b{color:#77efbd}.kgt12-integrity{margin-top:7px;border:1px solid #258760;border-radius:9px;background:#082019;padding:6px 8px;color:#86e7bc;font-size:.48rem;text-align:left}
.kgt12-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px}.kgt12-head b{font-size:.64rem;color:#7fd6f7;letter-spacing:.06em}.kgt12-head span{font-size:.43rem;color:#79a0b1;font-weight:900}.kgt12-pill{border:1px solid #2d7d61;border-radius:999px;padding:3px 7px;color:#74e7b6!important;background:#092219;font-size:.42rem!important}
.kgt12-why{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0}.kgt12-reason{padding:3px 10px;border-left:1px solid #1b4357;min-height:64px}.kgt12-reason:first-child{border-left:0;padding-left:2px}.kgt12-reason i{display:inline-grid;place-items:center;width:22px;height:22px;border:1px solid #279fdf;border-radius:50%;font-style:normal;color:#70d1ff;font-size:.48rem;font-weight:950}.kgt12-reason strong{display:block;font-size:.56rem;margin:5px 0 2px}.kgt12-reason small{display:block;color:#8ca7b6;font-size:.45rem;line-height:1.35}
.kgt12-market{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border:1px solid #173b4e;border-radius:10px;overflow:hidden}.kgt12-market div{padding:7px;text-align:center;border-left:1px solid #173b4e}.kgt12-market div:first-child{border-left:0}.kgt12-market span{display:block;color:#7393a4;font-size:.38rem;font-weight:950;letter-spacing:.07em}.kgt12-market b{display:block;font-size:.72rem;margin-top:2px}
.kgt12-history-summary{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #173b4e;border-radius:9px;overflow:hidden}.kgt12-history-summary div{text-align:center;padding:6px;border-left:1px solid #173b4e}.kgt12-history-summary div:first-child{border-left:0}.kgt12-history-summary span{display:block;color:#7e9dad;font-size:.38rem}.kgt12-history-summary b{display:block;font-size:.68rem;margin-top:2px}.kgt12-table{width:100%;border-collapse:collapse;margin-top:7px;font-size:.45rem}.kgt12-table th{color:#7398aa;font-size:.36rem;letter-spacing:.07em;text-align:left;padding:4px 5px;border-bottom:1px solid #235069}.kgt12-table td{padding:5px;border-bottom:1px solid #123448;color:#d6e6ee}.kgt12-result{display:inline-block;border:1px solid #3b6576;border-radius:999px;padding:2px 6px;font-weight:950;font-size:.38rem}.kgt12-result.over{border-color:#23885e;color:#69e9ad}.kgt12-result.under{border-color:#8c4850;color:#ff9aa5}.kgt12-result.push{border-color:#8a7337;color:#f0cf7d}.kgt12-note{font-size:.43rem;color:#809aa8;line-height:1.4;margin-top:6px}
.kgt12-availability{display:grid;grid-template-columns:1fr 1fr;gap:6px}.kgt12-teamavail{border:1px solid #173b4e;border-radius:10px;padding:7px;background:#07151d}.kgt12-teamavail strong{font-size:.53rem}.kgt12-avrow{margin-top:5px;padding-top:5px;border-top:1px solid #123448;font-size:.46rem;color:#a9bfca}.kgt12-avrow b{color:#edf5f8}.kgt12-empty{color:#829ca9;font-size:.47rem;padding:5px 0}
.kgt12-profile{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:5px}.kgt12-profile div{border-left:1px solid #173b4e;padding:4px 8px}.kgt12-profile div:first-child{border-left:0;padding-left:2px}.kgt12-profile span{display:block;color:#7998a8;font-size:.38rem}.kgt12-profile b{display:block;font-size:.62rem;margin-top:2px}.kgt12-profile small{display:block;color:#718c9a;font-size:.36rem;margin-top:2px;line-height:1.25}.low{color:#61cfff!important}.balanced{color:#f0cf75!important}.high{color:#67eab4!important}.neutral{color:#e5edf1!important}
.kgt12-range{text-align:center}.kgt12-range-total{font-size:1.65rem;font-weight:950}.kgt12-range-total span{display:block;font-size:.39rem;color:#7d9aaa;letter-spacing:.11em}.kgt12-range-row{display:grid;grid-template-columns:60px 1fr 60px;align-items:center;gap:8px;margin-top:7px}.kgt12-range-edge b{display:block;font-size:.68rem}.kgt12-range-edge span{font-size:.34rem;color:#7895a5}.kgt12-trackwrap{position:relative;padding-top:17px}.kgt12-track{height:7px;border-radius:999px;background:linear-gradient(90deg,#16466a,#2aaaf1 45%,#35d3db 60%,#16466a);border:1px solid #32617c}.kgt12-marker{position:absolute;top:9px;transform:translateX(-50%);width:15px;height:15px;border-radius:50%;background:#55c9ff;border:2px solid #e7fbff}.kgt12-marker.market{background:#f0b34d;border-color:#ffe1a1}.kgt12-labels{position:relative;height:27px}.kgt12-label{position:absolute;transform:translateX(-50%);top:3px;font-size:.36rem;line-height:1.15}.kgt12-label b{display:block}.kgt12-label.market{color:#f0c36d}.kgt12-label.model{color:#69d5ff}
.kgt12-bottom{display:grid;grid-template-columns:130px 1fr;gap:12px;align-items:center}.kgt12-bottom-read{border:1px solid #25a96f;border-radius:999px;text-align:center;padding:8px;color:#74edb6;font-size:.86rem;font-weight:950;background:#082119}.kgt12-bottom-copy{font-size:.51rem;line-height:1.45;color:#b9cbd4}.kgt12-bottom-copy strong{color:#ecf5f9}.kgt12-details{border:1px solid #245773;border-radius:11px;background:#07151d;margin:8px 0;overflow:hidden}.kgt12-details summary{cursor:pointer;list-style:none;padding:9px 11px;color:#b9d8e6;font-size:.53rem;font-weight:900}.kgt12-details summary::-webkit-details-marker{display:none}.kgt12-sourcebody{border-top:1px solid #173b4e;padding:8px 11px;color:#7897a6;font-size:.43rem;line-height:1.45}
@media(max-width:760px){.kgt12-card{padding:9px;border-radius:14px}.kgt12-title{font-size:1.05rem}.kgt12-summary{grid-template-columns:1fr 1fr}.kgt12-stat b{font-size:.88rem}.kgt12-why{grid-template-columns:1fr}.kgt12-reason{border-left:0;border-top:1px solid #173b4e;padding:6px 2px;min-height:0}.kgt12-reason:first-child{border-top:0}.kgt12-market{grid-template-columns:1fr 1fr}.kgt12-market div:nth-child(3){border-left:0;border-top:1px solid #173b4e}.kgt12-market div:nth-child(4){border-top:1px solid #173b4e}.kgt12-table{font-size:.41rem}.kgt12-table th{font-size:.32rem}.kgt12-availability{grid-template-columns:1fr}.kgt12-profile{grid-template-columns:1fr 1fr}.kgt12-profile div{border-left:0;border-top:1px solid #173b4e;padding:6px 2px}.kgt12-profile div:first-child{border-top:0}.kgt12-bottom{grid-template-columns:1fr}.kgt12-bottom-read{max-width:160px}.kgt12-range-row{grid-template-columns:48px 1fr 48px}}
</style>
'''


def _text(value: Any, default: str = "—") -> str:
    raw = str(value if value is not None else "").strip()
    return raw or default


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return out if math.isfinite(out) else None


def _fmt(value: Any, digits: int = 1) -> str:
    number = _num(value)
    return f"{number:.{digits}f}" if number is not None else "—"


def _signed(value: Any) -> str:
    number = _num(value)
    return f"{number:+.1f}" if number is not None else "—"


def _american(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _market(item: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = item.get("snapshot") if isinstance(item.get("snapshot"), Mapping) else {}
    markets = snapshot.get("markets") if isinstance(snapshot.get("markets"), list) else []
    if snapshot.get("ready") is True and snapshot.get("market_available") is True and markets and isinstance(markets[0], Mapping):
        return dict(markets[0])
    return {}


def _status_class(value: str) -> str:
    token = str(value or "").strip().lower()
    return token if token in {"high", "balanced", "low", "neutral"} else "neutral"


def _reason_rows(item: Mapping[str, Any]) -> list[tuple[str, str]]:
    pace = item.get("pace") if isinstance(item.get("pace"), Mapping) else {}
    red = item.get("red_zone") if isinstance(item.get("red_zone"), Mapping) else {}
    env = item.get("environment") if isinstance(item.get("environment"), Mapping) else {}
    read = item.get("read") if isinstance(item.get("read"), Mapping) else {}
    pace_match = pace.get("matchup") if isinstance(pace.get("matchup"), Mapping) else {}
    red_match = red.get("matchup") if isinstance(red.get("matchup"), Mapping) else {}
    pace_signal = _text(pace_match.get("pace_signal"), "UNAVAILABLE").upper()
    avg_plays = _fmt(pace_match.get("average_plays_per_game"))
    if pace_signal == "LOW":
        pace_title = "Slow combined pace"
    elif pace_signal == "HIGH":
        pace_title = "Fast combined pace supports scoring"
    else:
        pace_title = "Balanced combined pace"
    pace_detail = f"Combined opportunity pace {avg_plays} plays/game."
    rz_signal = _text(red_match.get("signal"), "UNAVAILABLE").upper()
    rz_avg = _fmt(red_match.get("average_red_zone_td_pct"))
    if rz_signal == "HIGH":
        rz_title = "Red-zone efficiency supports scoring"
    elif rz_signal == "LOW":
        rz_title = "Red-zone efficiency limits scoring"
    else:
        rz_title = "Red-zone efficiency is balanced"
    rz_detail = f"Verified matchup RZ TD rate {rz_avg}%."
    pressure = "INDOOR" if env.get("indoor") is True else _text(env.get("weather_pressure"), "UNAVAILABLE").upper()
    final_read = _text(read.get("final_read"), "PASS").upper()
    if pressure in {"LOW", "INDOOR"} and final_read == "PASS":
        env_title = "Weather low impact; market remains inside model range"
    elif pressure in {"HIGH", "WATCH"}:
        env_title = f"Weather pressure is {pressure.lower()}"
    else:
        env_title = "Environment is not a major separator"
    temp = _num(env.get("temperature")); gust = _num(env.get("gust"))
    bits = []
    if temp is not None: bits.append(f"{temp:.0f}°F")
    if gust is not None: bits.append(f"{gust:.0f} mph gust")
    env_detail = ", ".join(bits) + ("." if bits else "Certified environment context.")
    return [(pace_title, pace_detail), (rz_title, rz_detail), (env_title, env_detail)]


def _history_html(history: Mapping[str, Any]) -> str:
    if history.get("ready") is not True:
        return '<div class="kgt12-empty">Verified matchup history is unavailable for this matchup.</div><div class="kgt12-note">Matchup history is context only and has 0.0% model influence.</div>'
    games = int(_num(history.get("games")) or 0); overs = int(_num(history.get("overs")) or 0); unders = int(_num(history.get("unders")) or 0); pushes = int(_num(history.get("pushes")) or 0)
    ou = f"{overs}-{unders}" + (f"-{pushes}" if pushes else "")
    rows = []
    for raw in history.get("meetings") or []:
        if not isinstance(raw, Mapping): continue
        result = _text(raw.get("ou_result"), "—").upper(); css = result.lower() if result in {"OVER", "UNDER", "PUSH"} else ""
        rows.append('<tr>' f'<td>{escape(_text(raw.get("date")))}</td>' f'<td>{escape(_text(raw.get("score")))}</td>' f'<td>{escape(_fmt(raw.get("combined_score"), 0))}</td>' f'<td>{escape(_fmt(raw.get("closing_total")))}</td>' f'<td><span class="kgt12-result {css}">{escape(result)}</span></td>' '</tr>')
    return ('<div class="kgt12-history-summary">' f'<div><span>Last meetings</span><b>{games}</b></div>' f'<div><span>O/U record</span><b>{escape(ou if int(_num(history.get("line_verified_games")) or 0) else "—")}</b></div>' f'<div><span>Avg combined points</span><b>{escape(_fmt(history.get("average_combined_score")))}</b></div>' '</div>' '<table class="kgt12-table"><thead><tr><th>DATE</th><th>MATCHUP</th><th>FINAL TOTAL</th><th>CLOSE</th><th>O/U</th></tr></thead>' f'<tbody>{"".join(rows)}</tbody></table>' '<div class="kgt12-note">Recent meetings are verified historical context only. Matchup history is context only and never enters projection math.</div>')


def _team_availability(label: str, rows: list[Mapping[str, Any]]) -> str:
    if not rows: body = '<div class="kgt12-empty">No major key-offense designation listed.</div>'
    else:
        body = "".join('<div class="kgt12-avrow">' f'<b>{escape(_text(row.get("player_name")))}</b> · {escape(_text(row.get("position")))} · {escape(_text(row.get("game_status")))}' + (f'<br>{escape(_text(row.get("injury")))}' if _text(row.get("injury"), "") else "") + '</div>' for row in rows)
    return f'<div class="kgt12-teamavail"><strong>{escape(label)}</strong>{body}</div>'


def _availability_html(availability: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    if availability.get("ready") is not True: return '<div class="kgt12-empty">Official key-availability verification is temporarily unavailable.</div>'
    away_rows = [r for r in (availability.get("away") or []) if isinstance(r, Mapping)]; home_rows = [r for r in (availability.get("home") or []) if isinstance(r, Mapping)]
    return '<div class="kgt12-availability">' + _team_availability(_text(row.get("away_abbr"), "AWAY"), away_rows) + _team_availability(_text(row.get("home_abbr"), "HOME"), home_rows) + '</div>'


def _profile(item: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    pace = item.get("pace") if isinstance(item.get("pace"), Mapping) else {}; explosive = item.get("explosive") if isinstance(item.get("explosive"), Mapping) else {}; red = item.get("red_zone") if isinstance(item.get("red_zone"), Mapping) else {}; env = item.get("environment") if isinstance(item.get("environment"), Mapping) else {}; read = item.get("read") if isinstance(item.get("read"), Mapping) else {}
    pace_m = pace.get("matchup") if isinstance(pace.get("matchup"), Mapping) else {}; boom_m = explosive.get("matchup") if isinstance(explosive.get("matchup"), Mapping) else {}; red_m = red.get("matchup") if isinstance(red.get("matchup"), Mapping) else {}
    pressure = "INDOOR" if env.get("indoor") is True else _text(env.get("weather_pressure"), "UNAVAILABLE").upper(); final_read = _text(read.get("final_read"), "PASS").upper(); outlook = "NEUTRAL / PASS RANGE" if final_read == "PASS" else f"LEAN {final_read}"
    temp = _num(env.get("temperature")); gust = _num(env.get("gust")); weather_detail = " · ".join(x for x in [f"{temp:.0f}°F" if temp is not None else "", f"{gust:.0f} mph" if gust is not None else ""] if x) or "Certified context"
    return [("Pace", _text(pace_m.get("pace_signal"), "UNAVAILABLE").upper(), f'{_fmt(pace_m.get("average_plays_per_game"))} plays/g'), ("Explosiveness", _text(boom_m.get("signal"), "UNAVAILABLE").upper(), f'{_fmt(boom_m.get("average_explosive_plays_per_game"))} explosive plays/g'), ("Red Zone", _text(red_m.get("signal"), "UNAVAILABLE").upper(), f'{_fmt(red_m.get("average_red_zone_td_pct"))}% matchup RZ TD'), ("Environment", "LOW IMPACT" if pressure in {"LOW", "INDOOR"} else pressure, weather_detail), ("Scoring Outlook", outlook, "Market vs certified range")]


def _range_position(value: float | None, low: float | None, high: float | None) -> float:
    if value is None or low is None or high is None or high <= low: return 50.0
    return max(5.0, min(95.0, (value - low) / (high - low) * 100.0))


def build_page2_html(item: Mapping[str, Any], history: Mapping[str, Any], availability: Mapping[str, Any], day_str: str) -> str:
    row = item.get("row") if isinstance(item.get("row"), Mapping) else {}; model = item.get("model") if isinstance(item.get("model"), Mapping) else {}; read = item.get("read") if isinstance(item.get("read"), Mapping) else {}; projection = item.get("projection") if isinstance(item.get("projection"), Mapping) else {}; market = _market(item)
    away = _text(row.get("away_team"), "Away"); home = _text(row.get("home_team"), "Home"); market_total = _num(model.get("market_total")); kyre_total = _num(model.get("kyre_total")); edge = _num(model.get("edge")); final_read = _text(model.get("lean"), _text(read.get("final_read"), "PASS")).upper()
    over = market.get("over_price") if market else read.get("over_price"); under = market.get("under_price") if market else read.get("under_price"); sportsbook = _text(market.get("sportsbook"), "Verified market"); opening = _num(market.get("opening_total")); open_text = _fmt(opening) if opening is not None else "—"; current_text = _fmt(market_total)
    reasons_html = "".join(f'<div class="kgt12-reason"><i>{idx}</i><strong>{escape(title)}</strong><small>{escape(detail)}</small></div>' for idx, (title, detail) in enumerate(_reason_rows(item), 1))
    profile_html = "".join(f'<div><span>{escape(label)}</span><b class="{_status_class(value.split()[0])}">{escape(value)}</b><small>{escape(detail)}</small></div>' for label, value, detail in _profile(item))
    low = _num(projection.get("range_low")); high = _num(projection.get("range_high")); market_pos = _range_position(market_total, low, high); model_pos = _range_position(kyre_total, low, high); rationale = _text(read.get("rationale"), "Market comparison remains inside the certified range."); impact = _text(availability.get("impact"), "UNAVAILABLE").upper(); kickoff = foundation._phoenix_kickoff(row); clock = _text((kickoff or {}).get("clock"), _text(row.get("tip_et"), "TBD")); venue = _text(row.get("venue"), _text((item.get("environment") or {}).get("venue_name"), "Venue TBD"))
    return ('<div class="kgt12">' '<section class="kgt12-card kgt12-hero">' '<div class="kgt12-kicker">NFL GAME TOTALS • FULL ANALYSIS</div>' f'<div class="kgt12-title">{escape(away)} @ {escape(home)}</div>' f'<div class="kgt12-meta">{escape(day_str)} · {escape(clock)} · {escape(venue)}</div>' f'<div class="kgt12-records"><span>{escape(_text(row.get("away_record")))}</span><span>{escape(_text(row.get("home_record")))}</span></div>' '<div class="kgt12-summary">' f'<div class="kgt12-stat"><span>MARKET TOTAL</span><b>{escape(_fmt(market_total))}</b></div>' f'<div class="kgt12-stat kyre"><span>KYRE TOTAL</span><b>{escape(_fmt(kyre_total))}</b></div>' f'<div class="kgt12-stat edge"><span>EDGE</span><b>{escape(_signed(edge))}</b></div>' f'<div class="kgt12-stat read"><span>FINAL READ</span><b>{escape(final_read)}</b></div>' '</div><div class="kgt12-integrity">🛡 Projection remains sportsbook-free • sportsbook influence 0.0% • no wager actions.</div></section>' '<section class="kgt12-card"><div class="kgt12-head"><b>💡 WHY THIS READ</b></div>' f'<div class="kgt12-why">{reasons_html}</div></section>' '<section class="kgt12-card"><div class="kgt12-head"><b>▥ MARKET CONTEXT</b><span class="kgt12-pill">LIVE</span></div><div class="kgt12-market">' f'<div><span>{escape(sportsbook.upper())} TOTAL</span><b>{escape(current_text)}</b></div>' f'<div><span>OVER</span><b>{escape(_american(over))}</b></div>' f'<div><span>UNDER</span><b>{escape(_american(under))}</b></div>' f'<div><span>OPEN → CURRENT</span><b>{escape(open_text)} → {escape(current_text)}</b></div></div></section>' '<section class="kgt12-card"><div class="kgt12-head"><b>↻ MATCHUP HISTORY</b><span>CONTEXT ONLY</span></div>' f'{_history_html(history)}</section>' '<section class="kgt12-card"><div class="kgt12-head"><b>✚ KEY AVAILABILITY</b><span class="kgt12-pill">' + escape(impact) + '</span></div>' + _availability_html(availability, row) + '<div class="kgt12-note">Official availability is context only and has 0.0% model influence.</div></section>' '<section class="kgt12-card"><div class="kgt12-head"><b>▥ GAME PROFILE</b></div>' f'<div class="kgt12-profile">{profile_html}</div></section>' '<section class="kgt12-card kgt12-range"><div class="kgt12-head"><b>◎ PROJECTION RANGE</b></div>' f'<div class="kgt12-range-total">{escape(_fmt(kyre_total))}<span>MODEL TOTAL</span></div><div class="kgt12-range-row">' f'<div class="kgt12-range-edge"><b>{escape(_fmt(low))}</b><span>RANGE LOW</span></div><div class="kgt12-trackwrap"><div class="kgt12-track"></div>' f'<span class="kgt12-marker market" style="left:{market_pos:.1f}%"></span><span class="kgt12-marker" style="left:{model_pos:.1f}%"></span><div class="kgt12-labels">' f'<span class="kgt12-label market" style="left:{market_pos:.1f}%"><b>{escape(_fmt(market_total))}</b>MARKET</span>' f'<span class="kgt12-label model" style="left:{model_pos:.1f}%"><b>{escape(_fmt(kyre_total))}</b>MODEL</span></div></div>' f'<div class="kgt12-range-edge"><b>{escape(_fmt(high))}</b><span>RANGE HIGH</span></div></div><div class="kgt12-note">Market total sits inside the certified model range when the final read is PASS.</div></section>' '<section class="kgt12-card"><div class="kgt12-head"><b>🛡 BOTTOM LINE</b></div><div class="kgt12-bottom">' f'<div class="kgt12-bottom-read">{escape(final_read)}</div>' f'<div class="kgt12-bottom-copy"><strong>Model projects {escape(_fmt(kyre_total))}, a {escape(_signed(edge))} edge versus the {escape(_fmt(market_total))} market total.</strong><br>{escape(rationale)} No stake sizing or wager execution is enabled.</div></div></section>' '<details class="kgt12-details"><summary>▤ Data & Sources⌄</summary><div class="kgt12-sourcebody">Certified Kyre Game Totals scoring, pace, explosive-play, red-zone, environment, projection, and market-read contexts. Matchup history: nflverse completed exact-team games. Availability: NFL.com Official Injury Report. Market prices are comparison-only. Matchup history and availability each have 0.0% model influence.</div></details></div>')


def _page2(selected_game_id: str) -> None:
    day_str = v11._query_value("date") or str(st.session_state.get(mobile._STATE_DATE_KEY) or "").strip()
    if not day_str: day_str = pd.Timestamp.now(tz=foundation.ET).date().isoformat()
    with st.spinner("Loading selected-game intelligence…"): games, diag = foundation.load_nfl_slate(day_str)
    if not isinstance(diag, dict) or diag.get("request_ok") is not True: st.error("Verified NFL slate unavailable. Page 2 fails closed."); return
    if games.empty: st.info("No verified NFL games are available for this date."); return
    game_ids = games.get("game_id", pd.Series(dtype=str)).astype(str); selected = games.loc[game_ids == str(selected_game_id)].copy()
    if selected.empty: st.warning("Selected NFL Game Total is no longer available on this verified slate."); return
    one_game = selected.iloc[[0]].copy(); row = one_game.iloc[0].to_dict()
    with st.spinner("Building selected-game analysis…"): items = page1._collect(one_game, day_str)
    if not items: st.warning("Selected-game analytics are unavailable."); return
    item = items[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        history_future = pool.submit(load_matchup_history, row, limit=3); availability_future = pool.submit(load_availability, row, limit_per_team=2); history = history_future.result(); availability = availability_future.result()
    back_query = urlencode({"sport": "nfl", "market": "game-total", "date": day_str})
    st.markdown(_CSS, unsafe_allow_html=True); st.markdown(f'<div class="kgt12"><a class="kgt12-back" target="_self" href="?{escape(back_query, quote=True)}">← Back to Game Totals</a></div>', unsafe_allow_html=True); st.markdown(build_page2_html(item, history, availability, day_str), unsafe_allow_html=True)


def _page1() -> None:
    return v11._page1()


def render_nfl_game_totals_hub() -> None:
    view = v11._query_value("view").lower(); selected_game_id = v11._query_value("game")
    if view == "analysis" and selected_game_id: return _page2(selected_game_id)
    return _page1()


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total": raise ValueError("NFL Game Totals V12 only renders Game Total.")
    return render_nfl_game_totals_hub()


__all__ = ["AVAILABILITY_MODEL_INFLUENCE", "MATCHUP_HISTORY_MODEL_INFLUENCE", "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "STAKE_SIZING_ENABLED", "WAGER_ACTIONS_ENABLED", "build_page2_html", "render_nfl_game_totals_hub", "render_nfl_hub"]
