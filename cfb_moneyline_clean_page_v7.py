"""CFB Moneyline Premium V7 — S-tier decision-first analytics presentation.

Presentation-only successor over frozen V6. Certified model math, probabilities,
fair prices, schedule/model inputs, sportsbook projection influence and slate
analysis remain owned by the prior frozen chain. V7 only reorganizes verified
outputs into a cleaner decision-first dashboard.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import json
import os
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st
import cfb_moneyline_clean_page_v6 as prior
import cfb_moneyline_clean_page_v5 as detail
import cfb_moneyline_clean_page_v3 as market

MODEL_VERSION = "CFB MONEYLINE PREMIUM V7 • S-TIER DECISION ANALYTICS"
FROZEN_MONEYLINE_OWNER = prior.FROZEN_MONEYLINE_OWNER
FROZEN_RAW_MODEL = prior.FROZEN_RAW_MODEL
FROZEN_FINAL_MODEL = prior.FROZEN_FINAL_MODEL
SPORTSBOOK_PROJECTION_INFLUENCE = prior.SPORTSBOOK_PROJECTION_INFLUENCE
MAY_MODIFY_PROJECTION = prior.MAY_MODIFY_PROJECTION
market_value_verdict = prior.market_value_verdict
human_reason_summary = prior.human_reason_summary
KYRE_SPORTS_API_BASE_URL = "KYRE_SPORTS_API_BASE_URL"
PAGE1_ENDPOINT = "/api/v1/cfb/moneyline/page1"
_PHOENIX = ZoneInfo("America/Phoenix")

_CSS = r"""
<style>
.cfbm7-shell{margin:4px 0 10px}.cfbm7-eyebrow{font-size:.58rem;letter-spacing:.13em;font-weight:950;color:#79ddff;text-transform:uppercase}.cfbm7-title{font-size:1.52rem;font-weight:950;color:#f7fbff;margin-top:3px}.cfbm7-sub{font-size:.62rem;color:#8299ab;margin-top:3px}.cfbm7-date{display:inline-flex;margin-top:8px;border:1px solid rgba(108,189,232,.22);background:#081721;border-radius:999px;padding:6px 9px;color:#a9c9da;font-size:.43rem;font-weight:800}
.cfbm7-section{margin:17px 0 7px;font-size:.59rem;letter-spacing:.11em;text-transform:uppercase;font-weight:950;color:#e0eff7}.cfbm7-section span{color:#74d9ff}
.cfbm7-hero{padding:16px;border:1px solid rgba(91,185,235,.30);border-radius:20px;background:radial-gradient(circle at 50% 10%,rgba(33,91,128,.16),transparent 48%),linear-gradient(145deg,#07121d,#091a27 68%,#10152a);box-shadow:0 16px 36px rgba(0,0,0,.23)}
.cfbm7-hero-main{display:grid;grid-template-columns:1fr auto 1fr;gap:14px;align-items:center}.cfbm7-team{display:flex;align-items:center;gap:11px}.cfbm7-team.home{justify-content:flex-end;text-align:right}.cfbm7-logo{width:70px;height:70px;display:grid;place-items:center;border:1px solid rgba(122,188,226,.26);border-radius:18px;background:#0a1c29;overflow:hidden}.cfbm7-logo img{max-width:60px;max-height:60px}.cfbm7-logo b{font-size:1.05rem;color:#dff7ff}.cfbm7-team-name{font-size:1.05rem;font-weight:950;color:#fff}.cfbm7-team-meta{font-size:.45rem;color:#8299aa;margin-top:3px}.cfbm7-at{font-size:.68rem;font-weight:950;color:#7edcff;border:1px solid rgba(126,220,255,.30);padding:6px 9px;border-radius:999px}.cfbm7-context{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px;justify-content:center}.cfbm7-chip{font-size:.40rem;color:#b9d4e3;background:#071825;border:1px solid rgba(116,164,191,.18);border-radius:999px;padding:6px 9px}
.cfbm7-command{display:grid;grid-template-columns:1.5fr repeat(5,minmax(0,1fr));gap:8px;padding:10px;border:1px solid rgba(96,190,235,.30);border-radius:18px;background:linear-gradient(145deg,#071620,#081925)}.cfbm7-command-cell{padding:11px;border-radius:13px;background:#091925;border:1px solid rgba(126,163,187,.15)}.cfbm7-command-cell.primary{background:linear-gradient(145deg,rgba(71,46,142,.58),#0a1825);border-color:rgba(151,118,255,.44)}.cfbm7-command-cell small{display:block;font-size:.29rem;letter-spacing:.07em;text-transform:uppercase;color:#7893a6;font-weight:950}.cfbm7-command-cell b{display:block;margin-top:5px;color:#f6fbff;font-size:.73rem}.cfbm7-command-cell.primary b{font-size:.9rem}.cfbm7-command-cell strong{display:block;color:#d9d0ff;font-size:1.35rem;margin-top:3px}.cfbm7-verdict{grid-column:1/-1;margin-top:1px;border-radius:12px;padding:11px 13px;background:#081e2a;border:1px solid rgba(91,208,239,.34);display:flex;align-items:center;justify-content:space-between;gap:10px}.cfbm7-verdict b{font-size:.78rem;color:#e8fbff}.cfbm7-verdict span{font-size:.4rem;color:#82a5b8}.cfbm7-verdict.value{border-color:rgba(71,205,136,.38);background:#08231c}.cfbm7-verdict.watch{border-color:rgba(226,177,73,.35);background:#221b0a}.cfbm7-verdict.pass{border-color:rgba(217,101,108,.30);background:#241114}
.cfbm7-driver-wrap{border:1px solid rgba(109,175,211,.20);border-radius:17px;background:#07151f;padding:13px}.cfbm7-summary{font-size:.52rem;color:#a9bdc9;line-height:1.5;margin-bottom:10px}.cfbm7-driver{display:grid;grid-template-columns:130px 1fr 58px;gap:9px;align-items:center;margin:8px 0}.cfbm7-driver label{font-size:.44rem;color:#c9dbe5;font-weight:800}.cfbm7-track{height:9px;border-radius:999px;background:#101f2b;overflow:hidden}.cfbm7-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,#3e7ca5,#6ddcff)}.cfbm7-fill.negative{background:linear-gradient(90deg,#7b4755,#db6f81)}.cfbm7-driver b{font-size:.44rem;text-align:right;color:#e8f7ff}
.cfbm7-compare{display:grid;grid-template-columns:1.2fr .8fr .8fr .75fr;border:1px solid rgba(111,175,211,.20);border-radius:16px;overflow:hidden;background:#07151f}.cfbm7-compare>div{padding:9px 10px;border-bottom:1px solid rgba(123,160,184,.10);font-size:.45rem;color:#c4d6e0}.cfbm7-compare .head{font-size:.34rem;text-transform:uppercase;letter-spacing:.07em;color:#7191a5;font-weight:950;background:#091a26}.cfbm7-compare .metric{font-weight:850;color:#e8f4f9}.cfbm7-compare .edge{color:#79dcff;font-weight:900}.cfbm7-compare .last{border-bottom:0}
.cfbm7-prob{border:1px solid rgba(102,186,231,.22);border-radius:17px;background:#07151f;padding:13px}.cfbm7-prob-row{display:grid;grid-template-columns:135px 1fr 55px;gap:9px;align-items:center;margin:9px 0}.cfbm7-prob-row label{font-size:.48rem;color:#e5f2f7;font-weight:900}.cfbm7-prob-track{height:13px;background:#111e29;border-radius:999px;overflow:hidden}.cfbm7-prob-fill{height:100%;background:linear-gradient(90deg,#4e82be,#77ddff);border-radius:999px}.cfbm7-prob-row b{font-size:.48rem;color:#dff7ff;text-align:right}.cfbm7-uncertainty{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:11px}.cfbm7-unc{background:#10180f;border:1px solid rgba(224,177,74,.21);border-radius:11px;padding:9px}.cfbm7-unc small{display:block;font-size:.29rem;color:#aa9566;text-transform:uppercase;font-weight:900}.cfbm7-unc b{display:block;margin-top:3px;font-size:.56rem;color:#f0dda8}
.cfbm7-market{border:1px solid rgba(105,185,225,.22);border-radius:17px;background:#07151f;overflow:hidden}.cfbm7-market-row{display:grid;grid-template-columns:1.15fr .8fr .8fr 1fr;gap:8px;padding:9px 11px;border-bottom:1px solid rgba(122,157,178,.10);align-items:center}.cfbm7-market-row:last-child{border-bottom:0}.cfbm7-market-row.head{font-size:.3rem;text-transform:uppercase;letter-spacing:.08em;color:#718fa1;font-weight:950;background:#091b27}.cfbm7-market-row div{font-size:.44rem;color:#cedde5}.cfbm7-market-row b{color:#79ddff}.cfbm7-market-foot{padding:10px 12px;background:#081a25;font-size:.4rem;color:#83a0b2}.cfbm7-lab-note{font-size:.43rem;color:#8098aa;margin:4px 0 8px;line-height:1.45}
@media(max-width:900px){.cfbm7-command{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbm7-command-cell.primary{grid-column:1/-1}.cfbm7-driver{grid-template-columns:95px 1fr 52px}.cfbm7-hero-main{grid-template-columns:1fr auto 1fr}.cfbm7-logo{width:56px;height:56px}.cfbm7-logo img{max-width:48px;max-height:48px}.cfbm7-team-name{font-size:.82rem}.cfbm7-compare{grid-template-columns:1.15fr .75fr .75fr .7fr}.cfbm7-market-row{grid-template-columns:1fr .75fr .75fr .85fr}}
@media(max-width:620px){.cfbm7-command{grid-template-columns:1fr 1fr}.cfbm7-hero{padding:12px}.cfbm7-team{gap:6px}.cfbm7-logo{width:44px;height:44px;border-radius:13px}.cfbm7-logo img{max-width:38px;max-height:38px}.cfbm7-team-name{font-size:.68rem}.cfbm7-team-meta{font-size:.34rem}.cfbm7-uncertainty{grid-template-columns:1fr}.cfbm7-compare>div{padding:8px 6px;font-size:.38rem}.cfbm7-market-row{padding:8px 7px}.cfbm7-market-row div{font-size:.38rem}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _pct(value: Any) -> str:
    return detail._pct(value)


def _num(value: Any, digits: int = 1, signed: bool = False) -> str:
    return detail._num(value, digits, signed)


def _odds(value: Any) -> str:
    return detail._odds(value)


def _monogram(name: str) -> str:
    parts = [part for part in _clean(name).replace("-", " ").split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "CF"


def _kickoff_phoenix(game: Mapping[str, Any]) -> str:
    text = _clean(game.get("kickoff_iso") or game.get("start_time_utc"))
    if not text:
        return "Kickoff unavailable"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return "Kickoff unavailable"
        return parsed.astimezone(_PHOENIX).strftime("%-I:%M %p Phoenix")
    except (ValueError, TypeError):
        return "Kickoff unavailable"


def _record_text(profile: Mapping[str, Any], game: Mapping[str, Any], side: str) -> str:
    direct = _clean(profile.get("record_text"))
    if direct:
        return direct
    record = profile.get("record") if isinstance(profile.get("record"), Mapping) else {}
    wins, losses = record.get("wins"), record.get("losses")
    if wins is not None and losses is not None:
        return f"{wins}-{losses}"
    summary = _clean(game.get(f"{side}_record_summary"))
    return summary or "Record unavailable"


def _logo(url: str, name: str) -> str:
    if url:
        return f'<div class="cfbm7-logo"><img src="{escape(url)}" alt="{escape(name)} logo"></div>'
    return f'<div class="cfbm7-logo"><b>{escape(_monogram(name))}</b></div>'


def _rail_label(game: Mapping[str, Any]) -> str:
    away = _clean(game.get("away_team")) or "Away"
    home = _clean(game.get("home_team")) or "Home"
    return f"{away} @ {home} · {_kickoff_phoenix(game)}"


def _api_base() -> str:
    value = _clean(os.getenv(KYRE_SPORTS_API_BASE_URL))
    if not value:
        try:
            value = _clean(st.secrets.get(KYRE_SPORTS_API_BASE_URL))
        except Exception:
            value = ""
    if not value:
        raise RuntimeError("Kyre Sports API gateway is not configured.")
    return value.rstrip("/")


@st.cache_data(ttl=30, show_spinner=False)
def _load_page_payload(game_date: str = "", game_id: str = "") -> dict[str, Any]:
    params: dict[str, str] = {}
    if _clean(game_date):
        params["game_date"] = _clean(game_date)
    if _clean(game_id):
        params["game_id"] = _clean(game_id)
    url = _api_base() + PAGE1_ENDPOINT
    if params:
        url += "?" + urlencode(params)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-CFB-Moneyline-V7/1"})
    with urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or _clean(payload.get("service")) != "Kyre Sports API":
        raise RuntimeError("Kyre Sports API returned an invalid CFB Moneyline payload.")
    return payload


def _hero_html(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any], visuals: Mapping[str, Any]) -> str:
    away_name = _clean(away.get("team")) or _clean(game.get("away_team")) or "Away"
    home_name = _clean(home.get("team")) or _clean(game.get("home_team")) or "Home"
    away_logo = _clean((visuals.get("away") or {}).get("logo"))
    home_logo = _clean((visuals.get("home") or {}).get("logo"))
    away_record = _record_text(away, game, "away")
    home_record = _record_text(home, game, "home")
    away_conf = _clean(away.get("conference")) or "Conference unavailable"
    home_conf = _clean(home.get("conference")) or "Conference unavailable"
    venue = _clean(game.get("venue")) or "Venue TBD"
    broadcast = _clean(game.get("broadcast")) or "Broadcast unavailable"
    kickoff = _kickoff_phoenix(game)
    site = "Neutral site" if game.get("neutral_site") else f"Home field: {home_name}"
    return f'''<div class="cfbm7-hero"><div class="cfbm7-hero-main">
<div class="cfbm7-team">{_logo(away_logo, away_name)}<div><div class="cfbm7-team-name">{escape(away_name)}</div><div class="cfbm7-team-meta">{escape(away_record)} • {escape(away_conf)}</div></div></div>
<div class="cfbm7-at">@</div>
<div class="cfbm7-team home"><div><div class="cfbm7-team-name">{escape(home_name)}</div><div class="cfbm7-team-meta">{escape(home_record)} • {escape(home_conf)}</div></div>{_logo(home_logo, home_name)}</div></div>
<div class="cfbm7-context"><span class="cfbm7-chip">🕒 {escape(kickoff)}</span><span class="cfbm7-chip">📍 {escape(venue)}</span><span class="cfbm7-chip">📺 {escape(broadcast)}</span><span class="cfbm7-chip">🏟️ {escape(site)}</span></div></div>'''


def _decision_command_html(game: Mapping[str, Any], raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not final.get("ready"):
        reasons = " • ".join(str(x) for x in final.get("reasons") or ["Verified model inputs incomplete"])
        return f'<div class="cfbm7-section"><span>🏆</span> DECISION COMMAND CENTER</div><div class="cfbm7-command"><div class="cfbm7-verdict pass"><b>PASS • NO QUALIFIED MODEL PICK</b><span>{escape(reasons)}</span></div></div>'
    side = market._winner_side(final)
    winner = _clean(final.get("winner_team")) or "Model side"
    tier = _clean(final.get("model_tier")) or "LEAN"
    grade = _clean(final.get("model_grade")) or "—"
    confidence = _clean(raw.get("confidence")) or "CHECK"
    fair = final.get("home_fair_moneyline") if side == "home" else final.get("away_fair_moneyline")
    value = market_value_verdict(game, final, side)
    best_price = value.get("best_price")
    verdict = _clean(value.get("verdict")) or "WAIT FOR PRICE"
    if verdict in {"VALUE", "LEAN VALUE"} and best_price is not None:
        action = f"BET AT {_odds(best_price)} OR BETTER"
        action_cls = "value"
    elif best_price is None:
        action = "PRICE WATCH • MODEL READY, VERIFIED PRICE NEEDED"
        action_cls = "watch"
    else:
        action = verdict
        action_cls = "pass"
    best_book = _clean(value.get("best_book")) or "Unavailable"
    edge = f"{float(value['edge_pp']):+.1f} pp" if value.get("edge_pp") is not None else "—"
    return f'''<div class="cfbm7-section"><span>🏆</span> DECISION COMMAND CENTER</div><div class="cfbm7-command">
<div class="cfbm7-command-cell primary"><small>Model pick</small><b>{escape(tier)}: {escape(winner)} ML</b><strong>{_pct(final.get('winner_probability_final'))}</strong></div>
<div class="cfbm7-command-cell"><small>Fair ML</small><b>{_odds(fair)}</b></div>
<div class="cfbm7-command-cell"><small>Best book</small><b>{escape(best_book)}</b></div>
<div class="cfbm7-command-cell"><small>Best market</small><b>{_odds(best_price) if best_price is not None else '—'}</b></div>
<div class="cfbm7-command-cell"><small>Model edge</small><b>{escape(edge)}</b></div>
<div class="cfbm7-command-cell"><small>Confidence</small><b>{escape(confidence.title())} • {escape(grade)}</b></div>
<div class="cfbm7-verdict {action_cls}"><b>{escape(action)}</b><span>{escape(verdict)} • sportsbook probability weight 0%</span></div></div>'''


def _drivers_html(raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    if not raw.get("ready") or not final.get("ready"):
        return '<div class="cfbm7-section"><span>💡</span> MODEL DRIVERS</div><div class="cfbm7-driver-wrap"><div class="cfbm7-summary">Verified model drivers appear when the certified inputs are ready.</div></div>'
    side = market._winner_side(final)
    rows = market._factor_rows(raw, final, side)
    rows = sorted(rows, key=lambda row: abs(row[1]), reverse=True)[:6]
    max_abs = max([abs(float(row[1])) for row in rows] or [1.0])
    bars = []
    for label, value, direction in rows:
        width = max(3.0, min(100.0, abs(float(value)) / max_abs * 100.0))
        cls = "negative" if float(value) < 0 else ""
        bars.append(f'<div class="cfbm7-driver"><label>{escape(label)}</label><div class="cfbm7-track"><div class="cfbm7-fill {cls}" style="width:{width:.1f}%"></div></div><b>{float(value):+.1f}</b></div>')
    summary = human_reason_summary(raw, final, side)
    return '<div class="cfbm7-section"><span>💡</span> MODEL DRIVERS</div><div class="cfbm7-driver-wrap"><div class="cfbm7-summary">' + escape(summary) + '</div>' + ''.join(bars) + '</div>'


def _edge_name(a: Any, h: Any, away_name: str, home_name: str) -> str:
    try:
        av, hv = float(a), float(h)
    except (TypeError, ValueError):
        return "Neutral"
    if abs(av - hv) < 1e-9:
        return "Neutral"
    return away_name if av > hv else home_name


def _comparison_html(raw: Mapping[str, Any], final: Mapping[str, Any], *, away_name: str, home_name: str) -> str:
    c = raw.get("components") or {}
    rows = [
        ("Projected score", detail._score(final, "away"), detail._score(final, "home")),
        ("Base scoring", c.get("away_base_points"), c.get("home_base_points")),
        ("Efficiency adj.", c.get("away_efficiency_adjustment"), c.get("home_efficiency_adjustment")),
        ("Recent form", c.get("away_recent_adjustment"), c.get("home_recent_adjustment")),
        ("Turnover adj.", 0.0, c.get("turnover_edge_home_points")),
        ("Home field", 0.0, c.get("home_field_points")),
    ]
    cells = ['<div class="head">MATCHUP EDGE</div><div class="head">'+escape(away_name)+'</div><div class="head">'+escape(home_name)+'</div><div class="head">Edge</div>']
    for idx, (label, av, hv) in enumerate(rows):
        last = " last" if idx == len(rows)-1 else ""
        cells += [f'<div class="metric{last}">{escape(label)}</div>', f'<div class="{last.strip()}">{_num(av, signed="adj" in label.lower() or label=="Home field")}</div>', f'<div class="{last.strip()}">{_num(hv, signed="adj" in label.lower() or label=="Home field")}</div>', f'<div class="edge{last}">{escape(_edge_name(av,hv,away_name,home_name))}</div>']
    return '<div class="cfbm7-section"><span>📊</span> MATCHUP EDGE</div><div class="cfbm7-compare">' + ''.join(cells) + '</div>'


def _probabilities(final: Mapping[str, Any], away_name: str, home_name: str) -> tuple[float | None, float | None]:
    try:
        home_p = float(final.get("home_probability_final"))
    except (TypeError, ValueError):
        home_p = None
    try:
        away_p = float(final.get("away_probability_final"))
    except (TypeError, ValueError):
        away_p = None
    if home_p is None or away_p is None:
        winner = _clean(final.get("winner_team"))
        try:
            wp = float(final.get("winner_probability_final"))
        except (TypeError, ValueError):
            wp = None
        if wp is not None:
            if winner == home_name:
                home_p, away_p = wp, 1.0-wp
            elif winner == away_name:
                away_p, home_p = wp, 1.0-wp
    return away_p, home_p


def _probability_html(final: Mapping[str, Any], *, away_name: str, home_name: str) -> str:
    away_p, home_p = _probabilities(final, away_name, home_name)
    prob_range, margin_range = detail._uncertainty(final)
    reliability = _pct(final.get("reliability"))
    if away_p is None or home_p is None:
        return f'''<div class="cfbm7-section"><span>📈</span> WIN PROBABILITY & UNCERTAINTY</div><div class="cfbm7-prob"><div class="cfbm7-market-row"><div><b>Unavailable</b></div><div>—</div><div>—</div><div>Verified probability inputs are incomplete</div></div><div class="cfbm7-uncertainty"><div class="cfbm7-unc"><small>Home structural 90%</small><b>{escape(prob_range)}</b></div><div class="cfbm7-unc"><small>Margin structural 90%</small><b>{escape(margin_range)}</b></div><div class="cfbm7-unc"><small>Reliability</small><b>{escape(reliability)}</b></div></div></div>'''
    ap = max(0.0, min(1.0, away_p))
    hp = max(0.0, min(1.0, home_p))
    return f'''<div class="cfbm7-section"><span>📈</span> WIN PROBABILITY & UNCERTAINTY</div><div class="cfbm7-prob">
<div class="cfbm7-prob-row"><label>{escape(away_name)}</label><div class="cfbm7-prob-track"><div class="cfbm7-prob-fill" style="width:{ap*100:.1f}%"></div></div><b>{_pct(away_p)}</b></div>
<div class="cfbm7-prob-row"><label>{escape(home_name)}</label><div class="cfbm7-prob-track"><div class="cfbm7-prob-fill" style="width:{hp*100:.1f}%"></div></div><b>{_pct(home_p)}</b></div>
<div class="cfbm7-uncertainty"><div class="cfbm7-unc"><small>Home structural 90%</small><b>{escape(prob_range)}</b></div><div class="cfbm7-unc"><small>Margin structural 90%</small><b>{escape(margin_range)}</b></div><div class="cfbm7-unc"><small>Reliability</small><b>{escape(reliability)}</b></div></div></div>'''


def _market_html(game: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    books: dict[str, dict[str, Any]] = {}
    for side in ("away", "home"):
        for book, price, stamp in market._verified_prices(game, side):
            row = books.setdefault(book, {"away": None, "home": None, "stamp": ""})
            row[side] = price
            if stamp:
                row["stamp"] = stamp
    rows = []
    for book, data in books.items():
        rows.append(f'<div class="cfbm7-market-row"><div><b>{escape(book)}</b></div><div>{_odds(data.get("away")) if data.get("away") is not None else "—"}</div><div>{_odds(data.get("home")) if data.get("home") is not None else "—"}</div><div>{escape(_clean(data.get("stamp")) or "Verified")}</div></div>')
    if not rows:
        rows.append('<div class="cfbm7-market-row"><div><b>PRICE WATCH</b></div><div>—</div><div>—</div><div>No verified sportsbook price currently available</div></div>')
    away_name = _clean(game.get("away_team")) or "Away"
    home_name = _clean(game.get("home_team")) or "Home"
    return f'''<div class="cfbm7-section"><span>💰</span> LIVE MONEYLINE MARKET</div><div class="cfbm7-market"><div class="cfbm7-market-row head"><div>Sportsbook</div><div>{escape(away_name)}</div><div>{escape(home_name)}</div><div>Updated</div></div>{''.join(rows)}<div class="cfbm7-market-foot">Verified sportsbook prices are comparison-only • 0% model probability influence • no conflicting-line averaging</div></div>'''


def _freshness_html(game: Mapping[str, Any], routing: Mapping[str, Any]) -> str:
    quotes = game.get("market_quotes") if isinstance(game.get("market_quotes"), list) else []
    stamps = sorted(_clean(row.get("observed_at_utc")) for row in quotes if isinstance(row, Mapping) and _clean(row.get("observed_at_utc")))
    stamp = stamps[-1] if stamps else "Market timestamp unavailable"
    books = sorted({_clean(row.get("sportsbook")) for row in quotes if isinstance(row, Mapping) and _clean(row.get("sportsbook"))})
    book_text = ", ".join(books) if books else "No verified sportsbook price"
    return f'<div class="cfbm7-section"><span>◷</span> DATA FRESHNESS</div><div class="cfbm7-fresh">✅ Kyre Sports API • NCAA model data • {escape(book_text)} • {escape(stamp)} • projection weight {escape(str(routing.get("sportsbook_projection_weight")))}%</div>'


def _slate_rows(games: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for game in games:
        quotes = game.get("market_quotes") if isinstance(game.get("market_quotes"), list) else []
        rows.append({
            "Matchup": f'{_clean(game.get("away_team"))} @ {_clean(game.get("home_team"))}',
            "Kickoff Phoenix": _kickoff_phoenix(game),
            "Venue": _clean(game.get("venue")) or "—",
            "Verified books": len({str(q.get("sportsbook")) for q in quotes if isinstance(q, Mapping) and q.get("sportsbook")}),
        })
    return rows


def render_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(detail._CSS, unsafe_allow_html=True)
    try:
        payload = _load_page_payload()
    except Exception as exc:
        st.error(f"Kyre Sports API Moneyline gateway unavailable: {type(exc).__name__}. No direct provider fallback is allowed in the app.")
        return
    selected_day = _clean(payload.get("selected_date")) or "Unavailable"
    games = [dict(row) for row in payload.get("games") or [] if isinstance(row, Mapping)]
    routing = payload.get("routing") if isinstance(payload.get("routing"), Mapping) else {}
    st.markdown(f'<div class="cfbm7-shell"><div class="cfbm7-eyebrow">KYRE SPORTS AI • CFB MONEYLINE</div><div class="cfbm7-title">College Football Moneyline</div><div class="cfbm7-sub">Decision-first matchup intelligence • model edge, market value and transparent uncertainty</div><div class="cfbm7-date">📅 AUTO NEXT SLATE • {escape(selected_day)}</div></div>', unsafe_allow_html=True)
    if not games:
        st.warning("No verified upcoming CFB matchups are available from Kyre Sports API. No pick is invented.")
        return
    st.markdown('<div class="cfbm7-section"><span>🏟️</span> MATCHUP RAIL</div>', unsafe_allow_html=True)
    game_ids = [_clean(game.get("game_id") or game.get("identity_key")) for game in games]
    label_map = {gid: _rail_label(game) for gid, game in zip(game_ids, games) if gid}
    options = [gid for gid in game_ids if gid]
    if not options:
        st.warning("Verified slate identity is unavailable. No matchup is invented.")
        return
    default_id = _clean((payload.get("analysis") or {}).get("game_id")) if isinstance(payload.get("analysis"), Mapping) else ""
    default_id = default_id if default_id in options else options[0]
    chosen = st.segmented_control("MATCHUP RAIL", options=options, format_func=lambda gid: label_map.get(gid, gid), default=default_id, selection_mode="single", label_visibility="collapsed", key=f"cfbm7_matchup_rail_{selected_day}")
    selected_id = _clean(chosen) or default_id
    if selected_id != default_id:
        try:
            payload = _load_page_payload(selected_day, selected_id)
            games = [dict(row) for row in payload.get("games") or [] if isinstance(row, Mapping)]
            routing = payload.get("routing") if isinstance(payload.get("routing"), Mapping) else {}
        except Exception as exc:
            st.error(f"Kyre Sports API player selection refresh failed: {type(exc).__name__}. The previous verified view is kept fail-closed.")
            return
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), Mapping) else {}
    game = next((row for row in games if _clean(row.get("game_id") or row.get("identity_key")) == selected_id), games[0])
    away = analysis.get("away") if isinstance(analysis.get("away"), Mapping) else {}
    home = analysis.get("home") if isinstance(analysis.get("home"), Mapping) else {}
    raw = analysis.get("raw") if isinstance(analysis.get("raw"), Mapping) else {}
    final = analysis.get("final") if isinstance(analysis.get("final"), Mapping) else {}
    team_diag = analysis.get("team_diag") if isinstance(analysis.get("team_diag"), Mapping) else {}
    visuals = {"away": {}, "home": {}}
    away_name = _clean(away.get("team")) or _clean(game.get("away_team")) or "Away"
    home_name = _clean(home.get("team")) or _clean(game.get("home_team")) or "Home"

    st.markdown(_hero_html(game, away, home, visuals), unsafe_allow_html=True)
    st.markdown(_decision_command_html(game, raw, final), unsafe_allow_html=True)
    st.markdown(_drivers_html(raw, final), unsafe_allow_html=True)
    st.markdown(_comparison_html(raw, final, away_name=away_name, home_name=home_name), unsafe_allow_html=True)
    st.markdown(_probability_html(final, away_name=away_name, home_name=home_name), unsafe_allow_html=True)
    st.markdown(_market_html(game, final), unsafe_allow_html=True)
    st.markdown(_freshness_html(game, routing), unsafe_allow_html=True)

    st.markdown('<div class="cfbm7-section"><span>🔬</span> ANALYTICS LAB</div>', unsafe_allow_html=True)
    team_tab, model_tab, sources_tab, slate_tab = st.tabs(["Team Data", "Model Audit", "Sources", "Full Slate"])
    with team_tab:
        st.markdown(detail._team_profiles_html(away, home, visuals=visuals), unsafe_allow_html=True)
    with model_tab:
        st.markdown(detail._model_dashboard_html(raw, final, away_name=away_name, home_name=home_name), unsafe_allow_html=True)
        st.markdown(detail._feature_contributions_html(raw, away_name=away_name, home_name=home_name), unsafe_allow_html=True)
    with sources_tab:
        st.caption("Kyre Sports API owns routing, normalization, fallback and delivery. Only actually consulted providers appear below.")
        st.json({"routing": dict(routing), "team_data": dict(team_diag)})
    with slate_tab:
        st.dataframe(_slate_rows(games), use_container_width=True, hide_index=True)
    st.caption("Certified Moneyline probabilities remain price-indepent. Sportsbook prices are comparison-only and carry 0.0% projection weight.")


def render_cfb_hub(market_id: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if _clean(market_id).lower() == "moneyline":
        return render_moneyline_hub(section_header, status_info, team_logo, h)
    return prior.render_cfb_hub(market_id, section_header, status_info, team_logo, h)


__all__ = ["MODEL_VERSION", "FROZEN_MONEYLINE_OWNER", "FROZEN_RAW_MODEL", "FROZEN_FINAL_MODEL", "SPORTSBOOK_PROJECTION_INFLUENCE", "MAY_MODIFY_PROJECTION", "market_value_verdict", "human_reason_summary", "render_moneyline_hub", "render_cfb_hub"]
