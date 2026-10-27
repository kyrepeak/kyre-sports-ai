"""NFL Game Totals V13 — S-tier selected-game command center.

Presentation-only successor over frozen V12/V11. Certified projection, market-read,
Page 1, and Kyre Sports API context ownership remain unchanged. Missing context is
rendered semantically and is never synthesized into model inputs.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
from typing import Any, Mapping
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

import nfl_game_totals_hub_v12 as v12

page1 = v12.page1
foundation = v12.foundation
mobile = v12.mobile
v11 = v12.v11

MODEL_VERSION = "NFL GAME TOTALS V13 • PAGE 2 S-TIER V3"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MATCHUP_HISTORY_MODEL_INFLUENCE = 0.0
AVAILABILITY_MODEL_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False
PRESENTATION_ONLY = True
PAGE1_OWNER = "nfl_game_totals_page1_s_tier_v1"
PAGE2_ANCESTRY = "nfl_game_totals_hub_v12"

_CSS = r'''
<style data-api2-nfl-game-total-page2-stier-v3="true">
.kgt13{max-width:980px;margin:0 auto;color:#edf6fb}.kgt13 *{box-sizing:border-box}
.kgt13-back{display:inline-block;margin:2px 0 8px;color:#69cfff!important;text-decoration:none!important;font-size:.62rem;font-weight:900}
.kgt13-card{border:1px solid #265d7a;border-radius:16px;background:linear-gradient(180deg,#071a25,#07131b);padding:12px;margin:7px 0;box-shadow:0 12px 28px rgba(0,0,0,.16)}
.kgt13-hero{background:radial-gradient(circle at 50% -28%,#0d3c59 0,#071923 48%,#07131b 100%);text-align:center;padding:15px 12px}
.kgt13-kicker{color:#69d0fb;font-size:.46rem;font-weight:950;letter-spacing:.18em}.kgt13-title{font-size:1.38rem;font-weight:950;line-height:1.12;margin-top:5px}.kgt13-meta{font-size:.55rem;color:#91a9b7;margin-top:5px}.kgt13-records{display:flex;justify-content:center;gap:24px;color:#718c9a;font-size:.47rem;margin-top:4px}
.kgt13-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:10px}.kgt13-stat{border:1px solid #28516a;border-radius:10px;background:#081823;padding:8px 7px;text-align:left}.kgt13-stat span{display:block;color:#7897aa;font-size:.38rem;font-weight:950;letter-spacing:.08em}.kgt13-stat b{display:block;font-size:.98rem;margin-top:3px}.kgt13-stat.kyre b{color:#64ccff}.kgt13-stat.edge b{color:#68e3bd}.kgt13-stat.read b{color:#79edb9}
.kgt13-intel{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:7px}.kgt13-intel div{border-radius:8px;background:#08161f;padding:6px;border:1px solid #173d51;text-align:left}.kgt13-intel span{display:block;color:#6f8d9d;font-size:.34rem;font-weight:900;letter-spacing:.07em}.kgt13-intel b{display:block;margin-top:2px;font-size:.48rem;color:#cfe2eb}.kgt13-intel .ok{color:#74e6b3}.kgt13-intel .pending{color:#eacb72}
.kgt13-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:7px}.kgt13-head b{font-size:.62rem;color:#83d9fa;letter-spacing:.065em}.kgt13-head span{font-size:.40rem;color:#7798a9;font-weight:900}.kgt13-pill{display:inline-block;border:1px solid #2d7d61;border-radius:999px;padding:3px 7px;color:#74e7b6!important;background:#092219}.kgt13-pill.pending{border-color:#887337;color:#e9cb72!important;background:#211c0b}
.kgt13-semantic{border:1px solid #24495d;border-radius:10px;background:#081720;padding:9px 10px}.kgt13-semantic strong{display:block;font-size:.55rem;color:#e6eef2}.kgt13-semantic small{display:block;margin-top:3px;font-size:.43rem;line-height:1.35;color:#829eac}
.kgt13-script{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:center}.kgt13-team{text-align:center;border:1px solid #1d485e;border-radius:11px;padding:8px;background:#071720}.kgt13-team span{display:block;color:#7897a7;font-size:.39rem}.kgt13-team b{display:block;font-size:1.12rem;margin-top:2px}.kgt13-total{text-align:center}.kgt13-total b{display:block;color:#64ccff;font-size:1.28rem}.kgt13-total span{display:block;color:#718f9f;font-size:.34rem}
.kgt13-why{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.kgt13-reason{border:1px solid #173f53;border-radius:10px;padding:8px;background:#071720}.kgt13-reason i{display:grid;place-items:center;width:21px;height:21px;border:1px solid #279fdf;border-radius:50%;font-style:normal;color:#71d1ff;font-size:.46rem;font-weight:950}.kgt13-reason strong{display:block;font-size:.54rem;margin-top:5px}.kgt13-reason small{display:block;color:#8ba5b3;font-size:.43rem;line-height:1.35;margin-top:2px}
.kgt13-market-grid{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #173d50;border-radius:10px;overflow:hidden}.kgt13-market-grid div{padding:7px;text-align:center;border-left:1px solid #173d50}.kgt13-market-grid div:first-child{border-left:0}.kgt13-market-grid span{display:block;color:#7794a4;font-size:.36rem;font-weight:950}.kgt13-market-grid b{display:block;font-size:.70rem;margin-top:2px}
.kgt13-range-main{text-align:center}.kgt13-range-total{font-size:1.55rem;font-weight:950}.kgt13-range-total span{display:block;color:#7795a5;font-size:.36rem;letter-spacing:.11em}.kgt13-range-row{display:grid;grid-template-columns:55px 1fr 55px;align-items:center;gap:7px;margin-top:7px}.kgt13-range-edge b{display:block;font-size:.66rem}.kgt13-range-edge span{font-size:.32rem;color:#7794a4}.kgt13-trackbox{position:relative;height:58px}.kgt13-track{position:absolute;left:0;right:0;top:23px;height:7px;border-radius:999px;background:linear-gradient(90deg,#16466a,#2aaaf1 45%,#35d3db 60%,#16466a);border:1px solid #32617c}.kgt13-dot{position:absolute;top:18px;transform:translateX(-50%);width:17px;height:17px;border-radius:50%;background:#57c9ff;border:2px solid #e8fbff}.kgt13-dot.market{top:20px;width:13px;height:13px;background:#e9b54e;border-color:#ffe3a4}.kgt13-model-callout{position:absolute;top:0;transform:translateX(-50%);font-size:.34rem;color:#6bd6ff;white-space:nowrap;font-weight:900}.kgt13-market-callout{position:absolute;top:39px;transform:translateX(-50%);font-size:.34rem;color:#efc66f;white-space:nowrap;font-weight:900}
.kgt13-edges{display:grid;grid-template-columns:1fr 1fr;gap:7px}.kgt13-edgecard{border:1px solid #173f53;border-radius:10px;padding:8px;background:#071720}.kgt13-edgecard h4{margin:0;font-size:.52rem}.kgt13-edgecard .big{font-size:.82rem;font-weight:950;margin-top:6px}.kgt13-edgecard small{display:block;color:#829dac;font-size:.42rem;line-height:1.45;margin-top:4px}.favorable{color:#72e7b5}.medium,.balanced{color:#e7c96f}.tough{color:#ff989e}.unavailable{color:#91a6b0}
.kgt13-drivers{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.kgt13-drivercol{border:1px solid #173f53;border-radius:10px;padding:8px;background:#071720}.kgt13-drivercol strong{display:block;font-size:.47rem;margin-bottom:5px}.kgt13-chip{display:block;border-top:1px solid #123448;padding:5px 0;font-size:.45rem}.kgt13-chip:first-of-type{border-top:0}.kgt13-up strong{color:#72e7b5}.kgt13-down strong{color:#ff9a9f}.kgt13-neutral strong{color:#e7c96f}
.kgt13-history-summary{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #173d50;border-radius:9px;overflow:hidden}.kgt13-history-summary div{text-align:center;padding:6px;border-left:1px solid #173d50}.kgt13-history-summary div:first-child{border-left:0}.kgt13-history-summary span{display:block;color:#7897a6;font-size:.35rem}.kgt13-history-summary b{display:block;font-size:.65rem;margin-top:2px}.kgt13-table{width:100%;border-collapse:collapse;margin-top:6px;font-size:.43rem}.kgt13-table th{color:#7595a5;font-size:.34rem;letter-spacing:.06em;text-align:left;padding:4px;border-bottom:1px solid #235069}.kgt13-table td{padding:5px 4px;border-bottom:1px solid #123448;color:#d6e5ed}
.kgt13-avail{display:grid;grid-template-columns:1fr 1fr;gap:7px}.kgt13-avteam{border:1px solid #173f53;border-radius:10px;padding:8px;background:#071720}.kgt13-avteam strong{font-size:.49rem}.kgt13-avrow{border-top:1px solid #123448;margin-top:5px;padding-top:5px;font-size:.43rem;color:#a8bdc7}.kgt13-avrow b{color:#e8f1f5}
.kgt13-env{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.kgt13-env div{border:1px solid #173f53;border-radius:9px;padding:7px;background:#071720}.kgt13-env span{display:block;color:#7896a5;font-size:.34rem}.kgt13-env b{display:block;font-size:.58rem;margin-top:2px}
.kgt13-bottom{display:grid;grid-template-columns:120px 1fr;gap:11px;align-items:center}.kgt13-bottom-read{border:1px solid #279769;border-radius:999px;text-align:center;padding:8px;color:#77e9b6;font-size:.82rem;font-weight:950;background:#082019}.kgt13-bottom-copy{font-size:.49rem;line-height:1.45;color:#b8cad3}.kgt13-bottom-copy strong{color:#edf5f8}.kgt13-details{border:1px solid #245773;border-radius:11px;background:#07151d;margin:7px 0;overflow:hidden}.kgt13-details summary{cursor:pointer;list-style:none;padding:9px 11px;color:#bddae6;font-size:.51rem;font-weight:900}.kgt13-details summary::-webkit-details-marker{display:none}.kgt13-sourcebody{border-top:1px solid #173d50;padding:8px 11px;color:#7896a5;font-size:.42rem;line-height:1.45}.kgt13-note{font-size:.41rem;color:#7f9aa8;line-height:1.4;margin-top:5px}
@media(max-width:760px){.kgt13-card{padding:8px;border-radius:14px;margin:6px 0}.kgt13-title{font-size:1.05rem}.kgt13-summary{grid-template-columns:1fr 1fr}.kgt13-intel{grid-template-columns:1fr 1fr}.kgt13-script{grid-template-columns:1fr 1fr}.kgt13-total{grid-column:1/-1;grid-row:1}.kgt13-team{grid-row:2}.kgt13-why{grid-template-columns:1fr}.kgt13-market-grid{grid-template-columns:1fr 1fr}.kgt13-market-grid div:nth-child(3){border-left:0;border-top:1px solid #173d50}.kgt13-market-grid div:nth-child(4){border-top:1px solid #173d50}.kgt13-edges{grid-template-columns:1fr 1fr}.kgt13-drivers{grid-template-columns:1fr}.kgt13-env{grid-template-columns:1fr 1fr}.kgt13-avail{grid-template-columns:1fr}.kgt13-bottom{grid-template-columns:1fr}.kgt13-bottom-read{max-width:150px}.kgt13-range-row{grid-template-columns:46px 1fr 46px}}
</style>
'''


def _text(value: Any, default: str = "—") -> str:
    return v12._text(value, default)


def _num(value: Any) -> float | None:
    return v12._num(value)


def _fmt(value: Any, digits: int = 1) -> str:
    return v12._fmt(value, digits)


def _signed(value: Any) -> str:
    return v12._signed(value)


def _american(value: Any) -> str:
    return v12._american(value)


def _market(item: Mapping[str, Any]) -> dict[str, Any]:
    return v12._market(item)


def _market_html(item: Mapping[str, Any], model: Mapping[str, Any], read: Mapping[str, Any]) -> str:
    market = _market(item)
    current = _num(model.get("market_total"))
    if current is None:
        current = _num(read.get("market_total"))
    if not market or current is None:
        return ('<div class="kgt13-semantic"><strong>MARKET NOT VERIFIED YET</strong>'
                '<small>Kyre projection remains independent until a verified market total is available.</small></div>')
    opening = _num(market.get("opening_total"))
    sportsbook = _text(market.get("sportsbook"), "Verified market")
    return (
        '<div class="kgt13-market-grid">'
        f'<div><span>{escape(sportsbook.upper())} TOTAL</span><b>{escape(_fmt(current))}</b></div>'
        f'<div><span>OVER</span><b>{escape(_american(market.get("over_price")))}</b></div>'
        f'<div><span>UNDER</span><b>{escape(_american(market.get("under_price")))}</b></div>'
        f'<div><span>OPEN → CURRENT</span><b>{escape(_fmt(opening))} → {escape(_fmt(current))}</b></div>'
        '</div>'
    )


def _game_script_html(item: Mapping[str, Any]) -> str:
    row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
    projection = item.get("projection") if isinstance(item.get("projection"), Mapping) else {}
    away = _text(row.get("away_team"), "Away")
    home = _text(row.get("home_team"), "Home")
    away_pts = _num(projection.get("projected_away_points"))
    home_pts = _num(projection.get("projected_home_points"))
    total = _num(projection.get("projected_total"))
    if away_pts is None or home_pts is None or total is None or abs((away_pts + home_pts) - total) > 0.75:
        return ('<div class="kgt13-semantic"><strong>TEAM SPLIT NOT CERTIFIED</strong>'
                f'<small>Certified game-total projection: {_fmt(total)}. Team points are not inferred from the total.</small></div>')
    return (
        '<div class="kgt13-script">'
        f'<div class="kgt13-team"><span>{escape(away)}</span><b>{escape(_fmt(away_pts))}</b></div>'
        f'<div class="kgt13-total"><b>{escape(_fmt(total))}</b><span>PROJECTED TOTAL</span></div>'
        f'<div class="kgt13-team"><span>{escape(home)}</span><b>{escape(_fmt(home_pts))}</b></div>'
        '</div>'
    )


def _matchup_edges_html(item: Mapping[str, Any]) -> str:
    scoring = item.get("scoring") if isinstance(item.get("scoring"), Mapping) else {}
    if scoring.get("ready") is not True:
        return ('<div class="kgt13-semantic"><strong>MATCHUP EDGE DATA PENDING</strong>'
                '<small>Certified offense-versus-defense scoring context is not available yet.</small></div>')
    cards: list[str] = []
    for side in ("away", "home"):
        payload = scoring.get(side) if isinstance(scoring.get(side), Mapping) else {}
        team = _text(payload.get("team"), side.title())
        offense = _num(payload.get("offense_ppg"))
        defense = _num(payload.get("opponent_defense_papg"))
        signal = _text(payload.get("signal"), "UNAVAILABLE").upper()
        quality = _text(payload.get("quality"), "—").upper()
        css = signal.lower() if signal.lower() in {"favorable", "medium", "tough"} else "unavailable"
        cards.append(
            '<div class="kgt13-edgecard">'
            f'<h4>{escape(team.upper())} OFFENSE → OPPONENT DEFENSE</h4>'
            f'<div class="big {css}">{escape(signal)}</div>'
            f'<small>{escape(_fmt(offense))} PF/G vs {escape(_fmt(defense))} PA/G · data quality {escape(quality)}</small>'
            '</div>'
        )
    return f'<div class="kgt13-edges">{"".join(cards)}</div>'


def _driver_label(name: str) -> str:
    return {"pace": "Pace", "explosive": "Explosive", "sustainability": "Sustainability", "environment": "Environment"}.get(name, name.replace("_", " ").title())


def _driver_value(value: float) -> str:
    if value > 0:
        return f"+{value:.1f}"
    if value < 0:
        return f"−{abs(value):.1f}"
    return "0.0"


def _total_drivers_html(item: Mapping[str, Any]) -> str:
    projection = item.get("projection") if isinstance(item.get("projection"), Mapping) else {}
    adjustments = projection.get("adjustments") if isinstance(projection.get("adjustments"), Mapping) else {}
    buckets: dict[str, list[str]] = {"up": [], "down": [], "neutral": []}
    for key, raw in adjustments.items():
        value = _num(raw)
        if value is None:
            continue
        label = f'{_driver_label(str(key))} {_driver_value(value)}'
        if value > 0.05:
            buckets["up"].append(label)
        elif value < -0.05:
            buckets["down"].append(label)
        else:
            buckets["neutral"].append(label)
    if not any(buckets.values()):
        return '<div class="kgt13-semantic"><strong>TOTAL DRIVERS PENDING</strong><small>Certified model adjustment detail is not available.</small></div>'
    def col(kind: str, title: str) -> str:
        rows = buckets[kind] or ["No material driver"]
        return f'<div class="kgt13-drivercol kgt13-{kind}"><strong>{title}</strong>' + ''.join(f'<span class="kgt13-chip">{escape(row)}</span>' for row in rows) + '</div>'
    return f'<div class="kgt13-drivers">{col("up", "SCORING UP")}{col("down", "SCORING DOWN")}{col("neutral", "NEUTRAL")}</div>'


def _history_html(history: Mapping[str, Any]) -> str:
    if history.get("ready") is not True:
        return ('<div class="kgt13-semantic"><strong>NO RELEVANT RECENT HISTORY</strong>'
                '<small>No verified recent matchup history is available. History remains 0.0% model influence.</small></div>')
    games = int(_num(history.get("games")) or 0)
    overs = int(_num(history.get("overs")) or 0)
    unders = int(_num(history.get("unders")) or 0)
    pushes = int(_num(history.get("pushes")) or 0)
    line_games = int(_num(history.get("line_verified_games")) or 0)
    ou = f"{overs}-{unders}" + (f"-{pushes}" if pushes else "") if line_games else "—"
    rows: list[str] = []
    for raw in history.get("meetings") or []:
        if not isinstance(raw, Mapping):
            continue
        rows.append(
            '<tr>'
            f'<td>{escape(_text(raw.get("date")))}</td><td>{escape(_text(raw.get("score")))}</td>'
            f'<td>{escape(_fmt(raw.get("combined_score"), 0))}</td><td>{escape(_fmt(raw.get("closing_total")))}</td>'
            f'<td>{escape(_text(raw.get("ou_result")))}</td></tr>'
        )
    return (
        '<div class="kgt13-history-summary">'
        f'<div><span>RECENT MEETINGS</span><b>{games}</b></div><div><span>O/U RECORD</span><b>{escape(ou)}</b></div>'
        f'<div><span>AVG TOTAL</span><b>{escape(_fmt(history.get("average_combined_score")))}</b></div></div>'
        '<table class="kgt13-table"><thead><tr><th>DATE</th><th>MATCHUP</th><th>TOTAL</th><th>CLOSE</th><th>O/U</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table><div class="kgt13-note">Verified historical context only · 0.0% model influence.</div>'
    )


def _availability_html(availability: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    if availability.get("ready") is not True:
        return ('<div class="kgt13-semantic"><strong>AVAILABILITY VERIFICATION PENDING</strong>'
                '<small>Official key-player availability has not been verified yet. No status is inferred.</small></div>')
    teams = [("away", _text(row.get("away_team"), "Away")), ("home", _text(row.get("home_team"), "Home"))]
    out: list[str] = []
    for key, label in teams:
        rows = availability.get(key) if isinstance(availability.get(key), list) else []
        body = []
        for raw in rows:
            if not isinstance(raw, Mapping):
                continue
            body.append('<div class="kgt13-avrow">'
                        f'<b>{escape(_text(raw.get("position"), ""))} {escape(_text(raw.get("player_name"), "Player"))}</b> · '
                        f'{escape(_text(raw.get("game_status"), _text(raw.get("practice_status"), "STATUS PENDING")))}'
                        + (f' · {escape(_text(raw.get("injury"), ""))}' if _text(raw.get("injury"), "") else "") + '</div>')
        if not body:
            body = ['<div class="kgt13-avrow">No verified key designation surfaced.</div>']
        out.append(f'<div class="kgt13-avteam"><strong>{escape(label.upper())}</strong>{"".join(body)}</div>')
    return f'<div class="kgt13-avail">{"".join(out)}</div>'


def _environment_html(item: Mapping[str, Any]) -> str:
    env = item.get("environment") if isinstance(item.get("environment"), Mapping) else {}
    if env.get("ready") is not True:
        return '<div class="kgt13-semantic"><strong>ENVIRONMENT VERIFICATION PENDING</strong><small>Verified game-environment context is not available.</small></div>'
    indoor = env.get("indoor") is True
    cells = [
        ("TEMPERATURE", "INDOOR" if indoor else (f'{_num(env.get("temperature")):.0f}°F' if _num(env.get("temperature")) is not None else "—")),
        ("WIND / GUST", "INDOOR" if indoor else (f'{_num(env.get("gust")):.0f} mph' if _num(env.get("gust")) is not None else "—")),
        ("PRECIPITATION", "INDOOR" if indoor else (f'{_num(env.get("precipitation")):.0f}%' if _num(env.get("precipitation")) is not None else "—")),
        ("IMPACT", _text(env.get("weather_pressure"), "UNVERIFIED").upper()),
    ]
    return '<div class="kgt13-env">' + ''.join(f'<div><span>{escape(label)}</span><b>{escape(value)}</b></div>' for label, value in cells) + '</div>'


def _projection_range_html(item: Mapping[str, Any], model: Mapping[str, Any]) -> str:
    projection = item.get("projection") if isinstance(item.get("projection"), Mapping) else {}
    low = _num(projection.get("range_low")); high = _num(projection.get("range_high"))
    model_total = _num(model.get("kyre_total"))
    if model_total is None:
        model_total = _num(projection.get("projected_total"))
    market_total = _num(model.get("market_total"))
    model_pos = v12._range_position(model_total, low, high)
    market_pos = v12._range_position(market_total, low, high)
    market_marker = ""
    if market_total is not None:
        market_marker = (f'<span class="kgt13-dot market" style="left:{market_pos:.1f}%"></span>'
                         f'<span class="kgt13-market-callout" style="left:{market_pos:.1f}%">MARKET {_fmt(market_total)}</span>')
    return (
        '<div class="kgt13-range-main">'
        f'<div class="kgt13-range-total">{escape(_fmt(model_total))}<span>MODEL TOTAL</span></div>'
        '<div class="kgt13-range-row">'
        f'<div class="kgt13-range-edge"><b>{escape(_fmt(low))}</b><span>RANGE LOW</span></div>'
        '<div class="kgt13-trackbox"><div class="kgt13-track"></div>'
        f'<span class="kgt13-dot" style="left:{model_pos:.1f}%"></span>'
        f'<span class="kgt13-model-callout" style="left:{model_pos:.1f}%">KYRE {_fmt(model_total)}</span>{market_marker}</div>'
        f'<div class="kgt13-range-edge"><b>{escape(_fmt(high))}</b><span>RANGE HIGH</span></div></div></div>'
    )


def build_page2_html(item: Mapping[str, Any], history: Mapping[str, Any], availability: Mapping[str, Any], day_str: str) -> str:
    row = item.get("row") if isinstance(item.get("row"), Mapping) else {}
    model = item.get("model") if isinstance(item.get("model"), Mapping) else {}
    read = item.get("read") if isinstance(item.get("read"), Mapping) else {}
    projection = item.get("projection") if isinstance(item.get("projection"), Mapping) else {}
    away = _text(row.get("away_team"), "Away"); home = _text(row.get("home_team"), "Home")
    kyre_total = _num(model.get("kyre_total")); market_total = _num(model.get("market_total")); edge = _num(model.get("edge"))
    if kyre_total is None: kyre_total = _num(projection.get("projected_total"))
    final_read = _text(model.get("lean"), "WAIT").upper()
    confidence = _text(model.get("confidence"), "WAIT").upper()
    market_verified = bool(_market(item) and market_total is not None)
    reasons = v12._reason_rows(item)
    reasons_html = ''.join(f'<div class="kgt13-reason"><i>{idx}</i><strong>{escape(title)}</strong><small>{escape(detail)}</small></div>' for idx, (title, detail) in enumerate(reasons, 1))
    impact = _text(availability.get("impact"), "PENDING").upper() if isinstance(availability, Mapping) else "PENDING"
    market_status = "VERIFIED" if market_verified else "PENDING"
    data_status = "CERTIFIED INPUTS" if projection.get("ready") is True else "PARTIAL INPUTS"
    edge_text = _signed(edge) if edge is not None else "—"
    market_text = _fmt(market_total) if market_total is not None else "—"
    rationale = "Market comparison remains inside the certified range." if final_read == "PASS" and market_verified else ("A verified market total is required before edge certification." if not market_verified else "Certified model and market context determine the final read.")
    source = _text(availability.get("source"), "Official availability source pending") if isinstance(availability, Mapping) else "Official availability source pending"
    return (
        '<div class="kgt13">'
        '<section class="kgt13-card kgt13-hero"><div class="kgt13-kicker">NFL GAME TOTALS • GAME INTELLIGENCE</div>'
        f'<div class="kgt13-title">{escape(away)} @ {escape(home)}</div>'
        f'<div class="kgt13-meta">{escape(day_str)} · {escape(_text(row.get("tip_et"), "TBD"))} · {escape(_text(row.get("venue"), "Venue TBD"))}</div>'
        f'<div class="kgt13-records"><span>{escape(_text(row.get("away_record")))}</span><span>{escape(_text(row.get("home_record")))}</span></div>'
        '<div class="kgt13-summary">'
        f'<div class="kgt13-stat"><span>MARKET TOTAL</span><b>{escape(market_text)}</b></div>'
        f'<div class="kgt13-stat kyre"><span>KYRE TOTAL</span><b>{escape(_fmt(kyre_total))}</b></div>'
        f'<div class="kgt13-stat edge"><span>EDGE</span><b>{escape(edge_text)}</b></div>'
        f'<div class="kgt13-stat read"><span>FINAL READ</span><b>{escape(final_read)}</b></div></div>'
        '<div class="kgt13-intel">'
        f'<div><span>MODEL CONFIDENCE</span><b>{escape(confidence)}</b></div>'
        f'<div><span>MARKET STATUS</span><b class="{"ok" if market_verified else "pending"}">{market_status}</b></div>'
        f'<div><span>DATA STATUS</span><b class="{"ok" if projection.get("ready") is True else "pending"}">{data_status}</b></div></div></section>'
        '<section class="kgt13-card"><div class="kgt13-head"><b>◈ GAME SCRIPT</b><span>CERTIFIED FIELDS ONLY</span></div>' + _game_script_html(item) + '</section>'
        f'<section class="kgt13-card"><div class="kgt13-head"><b>💡 WHY THIS READ</b></div><div class="kgt13-why">{reasons_html}</div></section>'
        '<section class="kgt13-card"><div class="kgt13-head"><b>▥ MARKET CONTEXT</b><span class="kgt13-pill ' + ('' if market_verified else 'pending') + '">' + market_status + '</span></div>' + _market_html(item, model, read) + '</section>'
        '<section class="kgt13-card"><div class="kgt13-head"><b>◎ PROJECTION RANGE</b><span>SEPARATE MODEL / MARKET LANES</span></div>' + _projection_range_html(item, model) + '</section>'
        '<section class="kgt13-card"><div class="kgt13-head"><b>⚔ MATCHUP EDGES</b><span>OFFENSE VS DEFENSE</span></div>' + _matchup_edges_html(item) + '</section>'
        '<section class="kgt13-card"><div class="kgt13-head"><b>↕ TOTAL DRIVERS</b><span>MODEL ADJUSTMENTS</span></div>' + _total_drivers_html(item) + '</section>'
        '<section class="kgt13-card"><div class="kgt13-head"><b>↻ MATCHUP HISTORY</b><span>CONTEXT ONLY</span></div>' + _history_html(history) + '</section>'
        '<section class="kgt13-card"><div class="kgt13-head"><b>✚ KEY AVAILABILITY</b><span class="kgt13-pill ' + ('pending' if availability.get("ready") is not True else '') + '">' + escape(impact) + '</span></div>' + _availability_html(availability, row) + '<div class="kgt13-note">Official availability is context only · 0.0% model influence.</div></section>'
        '<section class="kgt13-card"><div class="kgt13-head"><b>☁ GAME ENVIRONMENT</b><span>' + escape(_text(row.get("venue"), "")) + '</span></div>' + _environment_html(item) + '</section>'
        '<section class="kgt13-card"><div class="kgt13-head"><b>🛡 BOTTOM LINE</b></div><div class="kgt13-bottom">'
        f'<div class="kgt13-bottom-read">{escape(final_read)}</div><div class="kgt13-bottom-copy"><strong>Kyre projects {escape(_fmt(kyre_total))}'
        + (f', a {escape(_signed(edge))} edge versus the {escape(_fmt(market_total))} verified market total.' if market_verified and edge is not None else '. Market edge is pending verification.')
        + f'</strong><br>{escape(rationale)} No stake sizing or wager execution is enabled.</div></div></section>'
        '<details class="kgt13-details"><summary>📋 Data &amp; Sources</summary><div class="kgt13-sourcebody">'
        f'Kyre Sports API application-facing gateway · certified projection stack · matchup history context 0.0% model influence · availability context 0.0% model influence · availability source: {escape(source)} · date: {escape(day_str)}.'
        '</div></details></div>'
    )


def _page2(selected_game_id: str) -> None:
    day_str = v11._query_value("date") or str(st.session_state.get(mobile._STATE_DATE_KEY) or "").strip()
    if not day_str:
        day_str = pd.Timestamp.now(tz=foundation.ET).date().isoformat()
    with st.spinner("Loading selected-game intelligence…"):
        games, diag = foundation.load_nfl_slate(day_str)
    if not isinstance(diag, dict) or diag.get("request_ok") is not True:
        st.error("Verified NFL slate unavailable. Page 2 fails closed."); return
    if games.empty:
        st.info("No verified NFL games are available for this date."); return
    game_ids = games.get("game_id", pd.Series(dtype=str)).astype(str)
    selected = games.loc[game_ids == str(selected_game_id)].copy()
    if selected.empty:
        st.warning("Selected NFL Game Total is no longer available on this verified slate."); return
    one_game = selected.iloc[[0]].copy(); row = one_game.iloc[0].to_dict()
    with st.spinner("Building selected-game analysis…"):
        items = page1._collect(one_game, day_str)
    if not items:
        st.warning("Selected-game analytics are unavailable."); return
    item = items[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        history_future = pool.submit(v12.load_matchup_history, row, limit=3)
        availability_future = pool.submit(v12.load_availability, row, limit_per_team=2)
        history = history_future.result(); availability = availability_future.result()
    back_query = urlencode({"sport": "nfl", "market": "game-total", "date": day_str})
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="kgt13"><a class="kgt13-back" target="_self" href="?{escape(back_query, quote=True)}">← Back to Game Totals</a></div>', unsafe_allow_html=True)
    st.markdown(build_page2_html(item, history, availability, day_str), unsafe_allow_html=True)


def _page1() -> None:
    return v12._page1()


def render_nfl_game_totals_hub() -> None:
    view = v11._query_value("view").lower(); selected_game_id = v11._query_value("game")
    if view == "analysis" and selected_game_id:
        return _page2(selected_game_id)
    return _page1()


def render_nfl_hub(market: str = "Game Total") -> None:
    if str(market or "Game Total") != "Game Total":
        raise ValueError("NFL Game Totals V13 only renders Game Total.")
    return render_nfl_game_totals_hub()


__all__ = [
    "AVAILABILITY_MODEL_INFLUENCE", "MATCHUP_HISTORY_MODEL_INFLUENCE", "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "STAKE_SIZING_ENABLED", "WAGER_ACTIONS_ENABLED",
    "build_page2_html", "render_nfl_game_totals_hub", "render_nfl_hub",
]
