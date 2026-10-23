"""CFB Game Total Page 1 A-tier V1 — compact Kyre Sports API market board."""
from __future__ import annotations

from datetime import date, datetime
from html import escape
import json
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_game_total_page1_api_bootstrap_repair_r1 as gateway

MODEL_VERSION = "CFB GAME TOTAL PAGE1 A-TIER V1 • MARKET DECISION BOARD"
MARKET = "Game Total"
PAGE1_ENDPOINT = "/api/v1/cfb/game-total/page1"
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
.cfbgt1-shell{margin:6px 0 14px}.cfbgt1-eyebrow{font-size:.56rem;letter-spacing:.15em;font-weight:950;color:#68d9ff;text-transform:uppercase}.cfbgt1-title{font-size:1.72rem;line-height:1.03;font-weight:1000;color:#f7fbff;margin:5px 0}.cfbgt1-sub{font-size:.61rem;color:#8299aa;max-width:720px}.cfbgt1-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0 14px}.cfbgt1-summary>div{padding:10px 12px;border:1px solid rgba(91,181,224,.18);border-radius:13px;background:#071722}.cfbgt1-summary small{display:block;font-size:.29rem;letter-spacing:.09em;text-transform:uppercase;color:#6f8fa2;font-weight:950}.cfbgt1-summary b{display:block;margin-top:4px;color:#e9f9ff;font-size:.58rem}.cfbgt1-summary .good b{color:#78e8bd}.cfbgt1-summary .warn b{color:#f0ca79}.cfbgt1-date{display:inline-flex;align-items:center;border:1px solid rgba(95,190,233,.22);background:#081925;border-radius:999px;padding:7px 10px;font-size:.42rem;font-weight:850;color:#b8d7e6}.cfbgt1-board{padding:10px 12px;border:1px solid rgba(87,193,238,.24);border-radius:15px;background:linear-gradient(145deg,#071923,#081d2a);margin:11px 0 13px}.cfbgt1-board b{display:block;font-size:.47rem;color:#7ddfff;letter-spacing:.07em;text-transform:uppercase}.cfbgt1-board span{display:block;margin-top:4px;font-size:.39rem;color:#7897a8}.cfbgt1-card{border:1px solid rgba(83,181,226,.25);border-radius:19px;background:radial-gradient(circle at 7% 3%,rgba(34,101,137,.15),transparent 38%),linear-gradient(145deg,#07141f,#081b27);margin:10px 0 14px;overflow:hidden;box-shadow:0 14px 34px rgba(0,0,0,.20)}.cfbgt1-head{display:grid;grid-template-columns:1fr auto;gap:12px;padding:13px 14px;border-bottom:1px solid rgba(112,159,187,.13)}.cfbgt1-match{display:flex;align-items:center;gap:9px}.cfbgt1-num{width:29px;height:29px;display:grid;place-items:center;border:1px solid rgba(77,202,255,.48);border-radius:50%;color:#83e2ff;font-size:.48rem;font-weight:1000}.cfbgt1-teams{font-size:.79rem;color:#f7fbff;font-weight:950;line-height:1.2}.cfbgt1-teams small{display:block;margin-top:3px;font-size:.36rem;color:#7d99a9;font-weight:750}.cfbgt1-badge{align-self:center;border:1px solid rgba(84,220,164,.34);background:rgba(13,82,61,.24);color:#7cebc0;border-radius:999px;padding:6px 8px;font-size:.31rem;font-weight:950;letter-spacing:.05em}.cfbgt1-badge.partial{border-color:rgba(229,185,87,.36);background:rgba(103,74,13,.22);color:#efd083}.cfbgt1-badge.empty{border-color:rgba(130,153,168,.25);background:rgba(61,74,83,.18);color:#9db3bf}.cfbgt1-grid{display:grid;grid-template-columns:1.25fr repeat(3,minmax(0,1fr));gap:8px;padding:12px}.cfbgt1-cell{min-height:70px;padding:10px;border:1px solid rgba(111,161,190,.14);border-radius:13px;background:#081923}.cfbgt1-cell.primary{background:linear-gradient(145deg,#0a2232,#0c2940);border-color:rgba(79,204,255,.36)}.cfbgt1-cell small{display:block;font-size:.28rem;letter-spacing:.075em;text-transform:uppercase;color:#6f8c9f;font-weight:950}.cfbgt1-cell strong{display:block;margin-top:7px;font-size:.72rem;color:#f4fbff}.cfbgt1-cell.primary strong{font-size:1.3rem;color:#7fe3ff}.cfbgt1-cell em{display:block;margin-top:4px;font-size:.3rem;font-style:normal;color:#7898a9}.cfbgt1-read{margin:0 12px 10px;padding:10px 11px;border:1px solid rgba(92,181,222,.16);border-radius:13px;background:rgba(5,20,30,.72)}.cfbgt1-read b{font-size:.43rem;letter-spacing:.08em;color:#82ddff}.cfbgt1-read span{display:block;margin-top:4px;font-size:.39rem;color:#9ab2bf;line-height:1.45}.cfbgt1-read.over b{color:#78e8bd}.cfbgt1-read.under b{color:#f0ca79}.cfbgt1-read.empty b{color:#a9bac3}.cfbgt1-foot{display:grid;grid-template-columns:1fr auto;gap:10px;padding:0 12px 12px;align-items:center}.cfbgt1-proof{font-size:.34rem;color:#7797a9}.cfbgt1-proof b{color:#b9dbe9}.cfbgt1-open{display:inline-flex;justify-content:center;min-width:128px;padding:8px 12px;border:1px solid rgba(72,201,255,.48);border-radius:999px;background:#082639;color:#83e3ff!important;text-decoration:none!important;font-size:.34rem;font-weight:1000;letter-spacing:.06em}.cfbgt1-empty{padding:18px;border:1px solid rgba(130,153,168,.24);border-radius:16px;background:#0a151c;color:#aec1cb;font-size:.48rem}
@media(max-width:850px){.cfbgt1-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cfbgt1-cell.primary{grid-column:1/-1}.cfbgt1-summary{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:620px){.cfbgt1-grid{grid-template-columns:1fr 1fr;padding:9px}.cfbgt1-cell.primary{grid-column:1/-1}.cfbgt1-summary{grid-template-columns:1fr}.cfbgt1-head{padding:11px}.cfbgt1-foot{grid-template-columns:1fr}.cfbgt1-open{width:100%;box-sizing:border-box}.cfbgt1-title{font-size:1.43rem}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


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


@st.cache_data(ttl=30, show_spinner=False)
def _load_payload(game_date: str = "") -> dict[str, Any]:
    params = {"game_date": _clean(game_date)} if _clean(game_date) else {}
    url = gateway._api_base() + PAGE1_ENDPOINT
    if params:
        url += "?" + urlencode(params)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-CFB-GameTotal-ATier/1"})
    with urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or _clean(payload.get("service")) != "Kyre Sports API":
        raise RuntimeError("Kyre Sports API returned an invalid Game Total payload.")
    return payload


def _name(game: Mapping[str, Any], side: str) -> str:
    direct = _clean(game.get(f"{side}_team"))
    if direct:
        return direct
    nested = game.get(side) if isinstance(game.get(side), Mapping) else {}
    return _clean(nested.get("name")) or side.title()


def _kickoff(game: Mapping[str, Any]) -> str:
    text = _clean(game.get("kickoff_iso") or game.get("start_time_utc"))
    if not text:
        return "Kickoff time not published"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return "Kickoff time not published"
        return parsed.astimezone(_PHOENIX).strftime("%a • %-I:%M %p MST")
    except (ValueError, TypeError):
        return "Kickoff time not published"


def _american(value: Any) -> str:
    if value is None or value == "":
        return "Price pending"
    try:
        number = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return "Price pending"
    if number == 0:
        return "Price pending"
    return f"+{number}" if number > 0 else str(number)


def _line(value: Any) -> str:
    if value is None or value == "":
        return "Market not posted"
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return "Market not posted"
    return f"{number:g}"


def _implied_probability(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        odds = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if odds == 0:
        return None
    if odds < 0:
        return (-odds) / ((-odds) + 100.0)
    return 100.0 / (odds + 100.0)


def _no_vig_probabilities(over_price: Any, under_price: Any) -> tuple[float | None, float | None]:
    over = _implied_probability(over_price)
    under = _implied_probability(under_price)
    if over is None or under is None:
        return None, None
    total = over + under
    if total <= 0:
        return None, None
    return over / total, under / total


def _pct(value: float | None) -> str:
    return "Pending" if value is None else f"{value * 100:.1f}%"


def _market_read(over: float | None, under: float | None, *, has_total: bool) -> tuple[str, str, str]:
    if not has_total:
        return (
            "MARKET NOT POSTED YET",
            "No verified game-total quote is currently available through Kyre Sports API.",
            "empty",
        )
    if over is None or under is None:
        return (
            "PRICE DATA PENDING",
            "A verified total is posted, but both sides do not yet have valid prices for no-vig market math.",
            "empty",
        )
    delta = over - under
    if abs(delta) < 0.02:
        return (
            "BALANCED MARKET",
            f"No-vig pricing is balanced: Over {_pct(over)} • Under {_pct(under)}.",
            "",
        )
    if delta > 0:
        return (
            "OVER MARKET LEAN",
            f"Current no-vig pricing leans Over: {_pct(over)} vs {_pct(under)} Under.",
            "over",
        )
    return (
        "UNDER MARKET LEAN",
        f"Current no-vig pricing leans Under: {_pct(under)} vs {_pct(over)} Over.",
        "under",
    )


def _quote(game: Mapping[str, Any]) -> Mapping[str, Any]:
    """Consume Kyre Sports API quote order; provider selection is not a UI concern."""
    quotes = [row for row in game.get("market_quotes") or [] if isinstance(row, Mapping)]
    if not quotes:
        return {}
    for row in quotes:
        if row.get("total_line") is not None and row.get("total_line") != "":
            return row
    return quotes[0]


def _selected_date(payload: Mapping[str, Any]) -> date:
    try:
        return date.fromisoformat(_clean(payload.get("selected_date")))
    except ValueError:
        return datetime.now(_PHOENIX).date()


def _game_href(game: Mapping[str, Any], selected_day: date) -> str:
    event_id = _clean(game.get("game_id") or game.get("identity_key"))
    if not event_id:
        return ""
    day = selected_day.isoformat()
    return "?" + urlencode({
        "sport": "cfb",
        "market": "game-total",
        "date": day,
        "game_id": event_id,
        "ks_sport": "College Football",
        "ks_cfb_market": "Game Total",
        "ks_cfb_game_total_date": day,
        "ks_cfb_game_total_event_id": event_id,
        "ks_cfb_game_total_selector_sync": event_id,
    })


def _badge(integrity: str) -> tuple[str, str]:
    value = integrity.upper()
    if value == "VERIFIED":
        return "VERIFIED TOTAL", ""
    if value == "PARTIAL":
        return "PARTIAL MARKET", " partial"
    return "MARKET PENDING", " empty"


def _render_card(game: Mapping[str, Any], index: int, selected_day: date) -> None:
    quote = _quote(game)
    total_value = quote.get("total_line")
    has_total = total_value is not None and total_value != ""
    over, under = _no_vig_probabilities(quote.get("over_price"), quote.get("under_price"))
    read_title, read_body, read_class = _market_read(over, under, has_total=has_total)
    book = _clean(quote.get("sportsbook")) or "Kyre Sports API verified market search"
    observed = _clean(quote.get("observed_at_utc")) or "Freshness timestamp pending"
    integrity = _clean(game.get("market_integrity")) or "PENDING"
    badge, badge_class = _badge(integrity)
    href = _game_href(game, selected_day)
    link = (
        f'<a class="cfbgt1-open" href="{escape(href, quote=True)}" target="_self">OPEN ANALYSIS →</a>'
        if href else '<span class="cfbgt1-open">ANALYSIS ROUTE PENDING</span>'
    )
    no_vig = "Pending" if over is None or under is None else f"O {_pct(over)} • U {_pct(under)}"
    st.markdown(
        '<div class="cfbgt1-card">'
        '<div class="cfbgt1-head">'
        f'<div class="cfbgt1-match"><span class="cfbgt1-num">{index}</span><div class="cfbgt1-teams">{escape(_name(game,"away"))} <span style="color:#66889a">@</span> {escape(_name(game,"home"))}<small>{escape(_kickoff(game))}</small></div></div>'
        f'<span class="cfbgt1-badge{badge_class}">{escape(badge)}</span>'
        '</div>'
        '<div class="cfbgt1-grid">'
        f'<div class="cfbgt1-cell primary"><small>MARKET TOTAL</small><strong>{escape(_line(total_value))}</strong><em>{escape(book)}</em></div>'
        f'<div class="cfbgt1-cell"><small>OVER PRICE</small><strong>{escape(_american(quote.get("over_price")))}</strong><em>Sportsbook-specific</em></div>'
        f'<div class="cfbgt1-cell"><small>UNDER PRICE</small><strong>{escape(_american(quote.get("under_price")))}</strong><em>Sportsbook-specific</em></div>'
        f'<div class="cfbgt1-cell"><small>NO-VIG MARKET</small><strong>{escape(no_vig)}</strong><em>Safe price derivation</em></div>'
        '</div>'
        f'<div class="cfbgt1-read {read_class}"><b>MARKET READ • {escape(read_title)}</b><span>{escape(read_body)}</span></div>'
        f'<div class="cfbgt1-foot"><div class="cfbgt1-proof"><b>Market integrity</b> • {escape(integrity)} • {escape(book)} • {escape(observed)} • quotes preserved separately by Kyre Sports API</div>{link}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_game_total_page1() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    requested = _requested_date()
    try:
        payload = _load_payload(requested)
    except Exception as exc:
        st.error(f"Kyre Sports API could not load the Game Total board: {type(exc).__name__}")
        return

    selected_day = _selected_date(payload)
    games = [row for row in payload.get("games") or [] if isinstance(row, Mapping)]
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    generated = _clean(payload.get("generated_at_utc")) or "Freshness timestamp pending"
    verified = int(summary.get("verified_market_games") or 0)
    pending = int(summary.get("market_unavailable_games") or 0)

    st.markdown(
        '<div class="cfbgt1-shell"><div class="cfbgt1-eyebrow">KYRE SPORTS AI • CFB GAME TOTALS</div>'
        '<div class="cfbgt1-title">Game Total Intelligence</div>'
        '<div class="cfbgt1-sub">A clean decision board for verified totals, sportsbook-specific O/U prices, and safe market probability context. Deep matchup research stays one tap away.</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="cfbgt1-summary">'
        f'<div><small>Games</small><b>{len(games)}</b></div>'
        f'<div class="good"><small>Verified Totals</small><b>{verified}</b></div>'
        f'<div class="{("good" if pending == 0 else "warn")}"><small>Markets Pending</small><b>{pending}</b></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([3, 1])
    with left:
        st.markdown(f'<div class="cfbgt1-date">📅 {escape(selected_day.strftime("%A • %B %d, %Y"))} • Phoenix</div>', unsafe_allow_html=True)
    with right:
        picked = st.date_input("Slate date", value=selected_day, key="cfbgt1_date")
        if picked != selected_day:
            st.query_params["date"] = picked.isoformat()
            st.query_params["ks_cfb_game_total_date"] = picked.isoformat()
            st.rerun()

    st.markdown(
        '<div class="cfbgt1-board"><b>GAME TOTAL DECISION BOARD</b>'
        f'<span>{len(games)} games • generated {escape(generated)} • one normalized Kyre Sports API quote per card • no consensus averaging</span></div>',
        unsafe_allow_html=True,
    )

    if not games:
        st.markdown('<div class="cfbgt1-empty">No qualifying pregame CFB games are currently available for this slate through Kyre Sports API.</div>', unsafe_allow_html=True)
        return

    search = st.text_input("Search matchup", placeholder="Search team", key="cfbgt1_search")
    needle = _clean(search).casefold()
    visible = [game for game in games if not needle or needle in (_name(game,"away") + " " + _name(game,"home")).casefold()]
    for index, game in enumerate(visible, start=1):
        _render_card(game, index, selected_day)


def render_cfb_hub(market: str, *args, **kwargs) -> None:
    del args, kwargs
    if market != MARKET:
        raise ValueError(f"CFB Game Total A-tier Page 1 cannot render market={market!r}")
    render_game_total_page1()


__all__ = [
    "MARKET",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "PAGE1_ENDPOINT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_page1",
]
