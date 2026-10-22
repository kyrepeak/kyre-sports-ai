"""CFB Game Total Page 1 V1 — Kyre Sports API market command center.

This discovery surface makes exactly one application-facing data request: Kyre
Sports API. It never calls an underlying schedule, sportsbook, aggregator, or
model provider directly. Selected-game Page 2 remains owned by the frozen
existing runtime.
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape
import json
import os
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st

MODEL_VERSION = "CFB GAME TOTAL PAGE1 S-TIER V1 • KYRE SPORTS API"
PAGE1_ENDPOINT = "/api/v1/cfb/game-total/page1"
KYRE_SPORTS_API_BASE_URL = "KYRE_SPORTS_API_BASE_URL"
MARKET = "Game Total"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False
_PHOENIX = ZoneInfo("America/Phoenix")

_CSS = r"""
<style>
.cfbgtx-shell{margin:5px 0 12px}.cfbgtx-eyebrow{font-size:.56rem;letter-spacing:.14em;font-weight:950;color:#67d8ff;text-transform:uppercase}.cfbgtx-title{font-size:1.75rem;line-height:1.05;font-weight:1000;color:#f7fbff;margin:4px 0}.cfbgtx-sub{font-size:.62rem;color:#8299aa}.cfbgtx-status{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:12px 0}.cfbgtx-status div{padding:9px 10px;border:1px solid rgba(95,181,226,.19);border-radius:12px;background:#071722}.cfbgtx-status small{display:block;font-size:.29rem;letter-spacing:.08em;text-transform:uppercase;color:#6f8fa2;font-weight:950}.cfbgtx-status b{display:block;margin-top:4px;font-size:.55rem;color:#e4f7ff}.cfbgtx-status .good b{color:#78e8bd}.cfbgtx-status .warn b{color:#f0ca79}
.cfbgtx-toolbar{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:end;margin:10px 0 15px}.cfbgtx-date-chip{display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(95,190,233,.23);background:#081925;border-radius:999px;padding:7px 10px;font-size:.42rem;font-weight:850;color:#b8d7e6}
.cfbgtx-board{padding:10px 12px;border:1px solid rgba(87,193,238,.27);border-radius:15px;background:linear-gradient(145deg,#071923,#081d2a);margin:8px 0 13px}.cfbgtx-board b{display:block;font-size:.48rem;color:#7ddfff;letter-spacing:.07em;text-transform:uppercase}.cfbgtx-board span{display:block;margin-top:4px;font-size:.4rem;color:#7795a7}
.cfbgtx-card{border:1px solid rgba(83,181,226,.25);border-radius:19px;background:radial-gradient(circle at 7% 3%,rgba(34,101,137,.15),transparent 38%),linear-gradient(145deg,#07141f,#081b27);margin:10px 0 14px;overflow:hidden;box-shadow:0 14px 34px rgba(0,0,0,.20)}.cfbgtx-card-head{display:grid;grid-template-columns:1fr auto;gap:12px;padding:13px 14px;border-bottom:1px solid rgba(112,159,187,.13)}.cfbgtx-match{display:flex;align-items:center;gap:9px}.cfbgtx-seed{width:29px;height:29px;display:grid;place-items:center;border:1px solid rgba(77,202,255,.48);border-radius:50%;color:#83e2ff;font-size:.48rem;font-weight:1000}.cfbgtx-teams{font-size:.78rem;color:#f7fbff;font-weight:950;line-height:1.25}.cfbgtx-teams small{display:block;margin-top:2px;font-size:.36rem;color:#7895a6;font-weight:750}.cfbgtx-integrity{align-self:center;border:1px solid rgba(84,220,164,.34);background:rgba(13,82,61,.24);color:#7cebc0;border-radius:999px;padding:6px 8px;font-size:.32rem;font-weight:950;letter-spacing:.05em}.cfbgtx-integrity.partial{border-color:rgba(229,185,87,.36);background:rgba(103,74,13,.22);color:#efd083}.cfbgtx-integrity.unavailable{border-color:rgba(211,100,111,.28);background:rgba(84,20,29,.18);color:#e8a0a8}
.cfbgtx-market{display:grid;grid-template-columns:1.45fr repeat(5,minmax(0,1fr));gap:7px;padding:12px}.cfbgtx-cell{min-height:62px;padding:9px;border:1px solid rgba(111,161,190,.14);border-radius:12px;background:#081923}.cfbgtx-cell.primary{background:linear-gradient(145deg,#0a2232,#0c2940);border-color:rgba(79,204,255,.36)}.cfbgtx-cell small{display:block;font-size:.27rem;letter-spacing:.07em;text-transform:uppercase;color:#6f8c9f;font-weight:950}.cfbgtx-cell strong{display:block;margin-top:6px;font-size:.68rem;color:#f4fbff}.cfbgtx-cell.primary strong{font-size:1.18rem;color:#7fe3ff}.cfbgtx-cell em{display:block;margin-top:3px;font-size:.29rem;font-style:normal;color:#7394a6}.cfbgtx-foot{display:grid;grid-template-columns:1fr auto;gap:10px;padding:0 12px 12px;align-items:center}.cfbgtx-proof{font-size:.34rem;color:#7797a9}.cfbgtx-proof b{color:#b9dbe9}.cfbgtx-open{display:inline-flex;justify-content:center;min-width:118px;padding:8px 11px;border:1px solid rgba(72,201,255,.48);border-radius:999px;background:#082639;color:#83e3ff!important;text-decoration:none!important;font-size:.34rem;font-weight:1000;letter-spacing:.06em}.cfbgtx-books{padding:0 12px 12px}.cfbgtx-book{display:grid;grid-template-columns:1.1fr repeat(4,minmax(0,1fr));gap:7px;padding:7px 8px;border-top:1px solid rgba(114,153,176,.10);font-size:.34rem;color:#94adbb}.cfbgtx-book b{color:#dff5ff}.cfbgtx-empty{padding:20px;border:1px solid rgba(214,116,125,.25);border-radius:16px;background:#1d1014;color:#d9aab0;font-size:.5rem}
@media(max-width:900px){.cfbgtx-market{grid-template-columns:repeat(3,minmax(0,1fr))}.cfbgtx-cell.primary{grid-column:span 2}.cfbgtx-status{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.cfbgtx-market{grid-template-columns:repeat(2,minmax(0,1fr));padding:9px}.cfbgtx-cell.primary{grid-column:1/-1}.cfbgtx-card-head{padding:11px}.cfbgtx-book{grid-template-columns:1fr 1fr}.cfbgtx-foot{grid-template-columns:1fr}.cfbgtx-open{width:100%;box-sizing:border-box}.cfbgtx-title{font-size:1.45rem}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


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
def _load_payload(game_date: str = "") -> dict[str, Any]:
    params = {"game_date": _clean(game_date)} if _clean(game_date) else {}
    url = _api_base() + PAGE1_ENDPOINT
    if params:
        url += "?" + urlencode(params)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-CFB-GameTotal-V1/1"})
    with urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or _clean(payload.get("service")) != "Kyre Sports API":
        raise RuntimeError("Kyre Sports API returned an invalid CFB Game Total payload.")
    return payload


def _scalar(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return _clean(value)


def _requested_date() -> str:
    for key in ("date", "ks_cfb_game_total_date"):
        value = _scalar(st.query_params.get(key))
        if value:
            return value[:10]
    return ""


def _name(game: Mapping[str, Any], side: str) -> str:
    direct = _clean(game.get(f"{side}_team"))
    if direct:
        return direct
    nested = game.get(side) if isinstance(game.get(side), Mapping) else {}
    return _clean(nested.get("name")) or side.title()


def _record(game: Mapping[str, Any], side: str) -> str:
    direct = _clean(game.get(f"{side}_record_summary"))
    if direct:
        return direct
    nested = game.get(side) if isinstance(game.get(side), Mapping) else {}
    return _clean(nested.get("record")) or "Record unavailable"


def _kickoff(game: Mapping[str, Any]) -> str:
    text = _clean(game.get("kickoff_iso") or game.get("start_time_utc"))
    if not text:
        return "Kickoff unavailable"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return "Kickoff unavailable"
        return parsed.astimezone(_PHOENIX).strftime("%a %-I:%M %p MST")
    except (ValueError, TypeError):
        return "Kickoff unavailable"


def _american(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return "—"
    return f"+{number}" if number > 0 else str(number)


def _line(value: Any, *, signed: bool = False) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return "—"
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number:g}"


def _quote(game: Mapping[str, Any]) -> Mapping[str, Any]:
    quotes = [row for row in game.get("market_quotes") or [] if isinstance(row, Mapping)]
    if not quotes:
        return {}
    priority = {"FanDuel": 0, "DraftKings": 1, "BetMGM": 2, "Caesars": 3, "bet365": 4, "Fanatics": 5}
    return sorted(quotes, key=lambda row: (priority.get(_clean(row.get("sportsbook")), 99), _clean(row.get("sportsbook"))))[0]


def _status_class(value: str) -> str:
    value = value.upper()
    if value == "VERIFIED":
        return ""
    if value == "PARTIAL":
        return " partial"
    return " unavailable"


def _selected_date(payload: Mapping[str, Any]) -> date:
    text = _clean(payload.get("selected_date"))
    try:
        return date.fromisoformat(text)
    except ValueError:
        return datetime.now(_PHOENIX).date()


def _game_href(game: Mapping[str, Any], selected_day: date) -> str:
    event_id = _clean(game.get("game_id") or game.get("identity_key"))
    if not event_id:
        return ""
    day = selected_day.isoformat()
    return "?" + urlencode({
        "sport": "cfb", "market": "game-total", "date": day, "game_id": event_id,
        "ks_sport": "College Football", "ks_cfb_market": "Game Total",
        "ks_cfb_game_total_date": day, "ks_cfb_game_total_event_id": event_id,
        "ks_cfb_game_total_selector_sync": event_id,
    })


def _render_book_rows(game: Mapping[str, Any]) -> str:
    rows = [row for row in game.get("market_quotes") or [] if isinstance(row, Mapping)]
    if len(rows) <= 1:
        return ""
    html: list[str] = ['<div class="cfbgtx-books">']
    for row in rows:
        html.append(
            '<div class="cfbgtx-book">'
            f'<b>{escape(_clean(row.get("sportsbook")) or "Book")}</b>'
            f'<span>O/U {_line(row.get("total_line"))}</span>'
            f'<span>O {_american(row.get("over_price"))}</span>'
            f'<span>U {_american(row.get("under_price"))}</span>'
            f'<span>{escape(_clean(row.get("line_integrity")) or "PARTIAL")}</span>'
            '</div>'
        )
    html.append('</div>')
    return "".join(html)


def _render_card(game: Mapping[str, Any], index: int, selected_day: date) -> None:
    quote = _quote(game)
    away, home = _name(game, "away"), _name(game, "home")
    integrity = _clean(game.get("market_integrity")) or "UNAVAILABLE"
    book = _clean(quote.get("sportsbook")) or "Market unavailable"
    observed = _clean(quote.get("observed_at_utc")) or "Timestamp unavailable"
    total = _line(quote.get("total_line"))
    href = _game_href(game, selected_day)
    link = f'<a class="cfbgtx-open" href="{escape(href, quote=True)}" target="_self">OPEN ANALYSIS →</a>' if href else '<span class="cfbgtx-open">ANALYSIS UNAVAILABLE</span>'
    st.markdown(
        '<div class="cfbgtx-card">'
        '<div class="cfbgtx-card-head">'
        f'<div class="cfbgtx-match"><span class="cfbgtx-seed">{index}</span><div class="cfbgtx-teams">{escape(away)} <span style="color:#66889a">@</span> {escape(home)}<small>{escape(_record(game,"away"))} • {escape(_record(game,"home"))} • {escape(_kickoff(game))}</small></div></div>'
        f'<span class="cfbgtx-integrity{_status_class(integrity)}">{escape(integrity)} LINE</span></div>'
        '<div class="cfbgtx-market">'
        f'<div class="cfbgtx-cell primary"><small>Market Total</small><strong>{escape(total)}</strong><em>{escape(book)}</em></div>'
        f'<div class="cfbgtx-cell"><small>Over Price</small><strong>{escape(_american(quote.get("over_price")))}</strong><em>O {escape(total)}</em></div>'
        f'<div class="cfbgtx-cell"><small>Under Price</small><strong>{escape(_american(quote.get("under_price")))}</strong><em>U {escape(total)}</em></div>'
        f'<div class="cfbgtx-cell"><small>Away Spread</small><strong>{escape(_line(quote.get("away_spread"), signed=True))}</strong><em>{escape(_american(quote.get("away_spread_price")))}</em></div>'
        f'<div class="cfbgtx-cell"><small>Home Spread</small><strong>{escape(_line(quote.get("home_spread"), signed=True))}</strong><em>{escape(_american(quote.get("home_spread_price")))}</em></div>'
        f'<div class="cfbgtx-cell"><small>Moneyline</small><strong>{escape(_american(quote.get("away_moneyline")))} / {escape(_american(quote.get("home_moneyline")))}</strong><em>Away / Home</em></div>'
        '</div>'
        f'<div class="cfbgtx-foot"><div class="cfbgtx-proof"><b>Line Integrity</b> • {escape(book)} • {escape(observed)} • {int(game.get("market_quote_count") or 0)} book quote(s) preserved separately</div>{link}</div>'
        f'{_render_book_rows(game)}'
        '</div>',
        unsafe_allow_html=True,
    )


def render_game_total_page1() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    requested = _requested_date()
    try:
        payload = _load_payload(requested)
    except Exception as exc:
        st.error(f"Kyre Sports API is unavailable for Game Totals: {type(exc).__name__}")
        return
    selected_day = _selected_date(payload)
    games = [row for row in payload.get("games") or [] if isinstance(row, Mapping)]
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    routing = payload.get("routing") if isinstance(payload.get("routing"), Mapping) else {}
    generated = _clean(payload.get("generated_at_utc")) or "Unavailable"

    st.markdown(
        '<div class="cfbgtx-shell"><div class="cfbgtx-eyebrow">College Football • MARKET COMMAND CENTER</div>'
        '<div class="cfbgtx-title">Game Totals</div>'
        '<div class="cfbgtx-sub">Professional O/U market analytics • exact sportsbook quotes • canonical game identity</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="cfbgtx-status">'
        '<div class="good"><small>Gateway</small><b>KYRE SPORTS API • LIVE</b></div>'
        f'<div class="good"><small>Canonical Slate</small><b>{escape(_clean(routing.get("schedule_primary")) or "NCAA")}</b></div>'
        f'<div class="good"><small>Verified Markets</small><b>{int(summary.get("verified_market_games") or 0)} / {len(games)}</b></div>'
        f'<div class="{("good" if int(summary.get("market_unavailable_games") or 0) == 0 else "warn")}"><small>Missing Markets</small><b>{int(summary.get("market_unavailable_games") or 0)}</b></div>'
        '</div>', unsafe_allow_html=True,
    )

    left, right = st.columns([3, 1])
    with left:
        st.markdown(f'<div class="cfbgtx-date-chip">📅 {escape(selected_day.strftime("%A • %B %d, %Y"))} • Phoenix</div>', unsafe_allow_html=True)
    with right:
        picked = st.date_input("Slate date", value=selected_day, key="cfbgtx_date")
        if picked != selected_day:
            st.query_params["date"] = picked.isoformat()
            st.query_params["ks_cfb_game_total_date"] = picked.isoformat()
            st.rerun()

    st.markdown(
        '<div class="cfbgtx-board"><b>LIVE MARKET BOARD</b>'
        f'<span>{len(games)} games • primary {_clean(routing.get("market_primary")) or "FanDuel"} • secondary only when needed • generated {escape(generated)}</span></div>',
        unsafe_allow_html=True,
    )
    if not games:
        st.markdown('<div class="cfbgtx-empty">No verified games are available for this slate from Kyre Sports API.</div>', unsafe_allow_html=True)
        return

    search = st.text_input("Search matchup", placeholder="Search team", key="cfbgtx_search")
    needle = _clean(search).casefold()
    visible = [game for game in games if not needle or needle in (_name(game,"away") + " " + _name(game,"home")).casefold()]
    for index, game in enumerate(visible, start=1):
        _render_card(game, index, selected_day)


def render_cfb_hub(market: str, *args, **kwargs) -> None:
    del args, kwargs
    if market != MARKET:
        raise ValueError(f"S-tier Game Total Page 1 cannot render market={market!r}")
    render_game_total_page1()


__all__ = [
    "MARKET",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PAGE1_ENDPOINT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_page1",
]
