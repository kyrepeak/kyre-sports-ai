"""CFB Game Total Page 1 A-tier V6 — S-tier selected-game decision card."""
from __future__ import annotations

from datetime import date
from html import escape
import json
from math import isfinite
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st

import cfb_game_total_page1_api_bootstrap_repair_r1 as gateway
import cfb_game_total_page1_atier_v1 as base
import cfb_game_total_page1_atier_v3 as market_ui
import cfb_game_total_page1_atier_v4 as selector
import cfb_game_total_page1_atier_v5 as prior

MODEL_VERSION = "CFB GAME TOTAL PAGE1 A-TIER V6 • S-TIER DECISION CARD R1"
MARKET = "Game Total"
PAGE1_ENDPOINT = prior.PAGE1_ENDPOINT
DECISION_ENDPOINT = "/api/v1/cfb/game-total/decision"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False

_CSS = prior._CSS + r"""
<style>
.cfbgt6-card{border:1px solid rgba(83,181,226,.29);border-radius:18px;background:radial-gradient(circle at 8% 0%,rgba(34,101,137,.16),transparent 38%),linear-gradient(145deg,#07141f,#081b27);margin:9px 0 11px;overflow:hidden;box-shadow:0 12px 30px rgba(0,0,0,.20)}
.cfbgt6-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 13px;border-bottom:1px solid rgba(112,159,187,.12)}
.cfbgt6-match{display:flex;align-items:center;gap:8px;min-width:0}.cfbgt6-team-logo{position:relative;width:30px;height:30px;flex:0 0 30px;border-radius:50%;display:grid;place-items:center;background:#0a2332;border:1px solid rgba(103,197,238,.25);overflow:hidden;color:#7ddfff;font-size:.28rem;font-weight:1000}.cfbgt6-team-logo img{position:absolute;inset:2px;width:26px;height:26px;object-fit:contain;border-radius:50%;background:#07141f}.cfbgt6-team{font-size:.68rem;color:#f7fbff;font-weight:1000;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:155px}.cfbgt6-at{font-size:.46rem;color:#688a9b;font-weight:950}.cfbgt6-kick{display:block;margin-top:3px;font-size:.30rem;color:#7d99a9;font-weight:800}.cfbgt6-badge{border:1px solid rgba(84,220,164,.34);background:rgba(13,82,61,.24);color:#7cebc0;border-radius:999px;padding:5px 8px;font-size:.27rem;font-weight:950;letter-spacing:.04em;white-space:nowrap}.cfbgt6-badge.pending{border-color:rgba(229,185,87,.34);background:rgba(103,74,13,.20);color:#efd083}
.cfbgt6-primary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;padding:10px}.cfbgt6-metric{min-width:0;min-height:65px;padding:9px;border:1px solid rgba(111,161,190,.15);border-radius:12px;background:#081923}.cfbgt6-metric small{display:block;font-size:.23rem;letter-spacing:.07em;text-transform:uppercase;color:#6f8c9f;font-weight:950}.cfbgt6-metric strong{display:block;margin-top:6px;font-size:.88rem;color:#f4fbff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfbgt6-metric em{display:block;margin-top:3px;font-size:.24rem;font-style:normal;color:#7898a9}.cfbgt6-market{background:linear-gradient(145deg,#092338,#0b2b42);border-color:rgba(79,204,255,.34)}.cfbgt6-market strong{color:#7fe3ff}.cfbgt6-proj strong{color:#f4fbff}.cfbgt6-prob strong{font-size:.60rem;color:#83e9c1;white-space:normal;line-height:1.25}
.cfbgt6-tilt{margin:0 10px 8px;padding:9px 10px;border:1px solid rgba(91,181,224,.17);border-radius:11px;background:rgba(5,20,30,.74)}.cfbgt6-tilt-top{display:flex;align-items:center;justify-content:space-between;gap:8px}.cfbgt6-tilt small{font-size:.23rem;letter-spacing:.075em;text-transform:uppercase;color:#6f8c9f;font-weight:950}.cfbgt6-tilt b{font-size:.38rem;color:#8ee6ff}.cfbgt6-tilt.over b{color:#78e8bd}.cfbgt6-tilt.under b{color:#f0ca79}.cfbgt6-modelbar{display:flex;height:5px;border-radius:999px;overflow:hidden;margin-top:7px;background:#26313a}.cfbgt6-overbar{height:100%;background:linear-gradient(90deg,#48cfa2,#78e8bd)}.cfbgt6-underbar{height:100%;background:rgba(240,202,121,.62)}.cfbgt6-pushbar{height:100%;background:#6f8796}.cfbgt6-tilt-note{margin-top:5px;font-size:.28rem;color:#8da9b8;line-height:1.35}.cfbgt6-tilt-note strong{color:#cbe8f4;font-size:inherit}
.cfbgt6-secondary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin:0 10px 8px}.cfbgt6-secondary>div{min-width:0;padding:7px 8px;border:1px solid rgba(92,181,222,.11);border-radius:9px;background:#071722}.cfbgt6-secondary small{display:block;font-size:.20rem;letter-spacing:.06em;text-transform:uppercase;color:#6f8c9f;font-weight:950}.cfbgt6-secondary strong{display:block;margin-top:3px;font-size:.31rem;color:#c7e4ef;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfbgt6-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:0 10px 10px}.cfbgt6-proof{min-width:0;font-size:.24rem;color:#6f8f9f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfbgt6-open{display:inline-flex;align-items:center;justify-content:center;min-width:112px;min-height:30px;padding:0 11px;border:1px solid rgba(72,201,255,.46);border-radius:999px;background:#082639;color:#83e3ff!important;text-decoration:none!important;font-size:.27rem;font-weight:1000;letter-spacing:.055em;white-space:nowrap}
@media(max-width:620px){.cfbgt6-head{padding:10px}.cfbgt6-team-logo{width:28px;height:28px;flex-basis:28px}.cfbgt6-team-logo img{width:24px;height:24px}.cfbgt6-team{font-size:.58rem;max-width:103px}.cfbgt6-primary{gap:5px;padding:8px}.cfbgt6-metric{min-height:61px;padding:8px 6px}.cfbgt6-metric small{font-size:.19rem}.cfbgt6-metric strong{font-size:.72rem}.cfbgt6-prob strong{font-size:.48rem}.cfbgt6-secondary{grid-template-columns:1fr;gap:5px;margin:0 8px 7px}.cfbgt6-tilt{margin:0 8px 7px}.cfbgt6-foot{padding:0 8px 8px}.cfbgt6-open{min-width:103px}}
@media(max-width:390px){.cfbgt6-primary{grid-template-columns:1fr 1fr}.cfbgt6-prob{grid-column:1/-1}.cfbgt6-head{align-items:flex-start}.cfbgt6-badge{font-size:.22rem}.cfbgt6-team{max-width:87px}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _pct(value: Any) -> str:
    number = _num(value)
    return "—" if number is None else f"{number * 100.0:.1f}%"


def _metric(value: Any) -> str:
    number = _num(value)
    return "—" if number is None else f"{number:.1f}"


def _width(value: Any) -> str:
    number = _num(value)
    return "0%" if number is None else f"{max(0.0, min(1.0, number)) * 100.0:.3f}%"


def _identity(game: Mapping[str, Any], side: str) -> Mapping[str, Any]:
    identities = game.get("team_identity") if isinstance(game.get("team_identity"), Mapping) else {}
    value = identities.get(side) if isinstance(identities.get(side), Mapping) else {}
    return value


def _logo(game: Mapping[str, Any], side: str) -> str:
    identity = _identity(game, side)
    name = base._name(game, side)
    fallback = _clean(identity.get("fallback_monogram")) or prior._abbr(game, side)
    url = _clean(identity.get("logo_url"))
    image = (
        f'<img src="{escape(url, quote=True)}" alt="{escape(name, quote=True)} logo" loading="lazy" '
        'onerror="this.style.display=\'none\'">'
        if url else ""
    )
    return f'<span class="cfbgt6-team-logo"><span>{escape(fallback)}</span>{image}</span>'


@st.cache_data(ttl=60, show_spinner=False)
def _load_decision(game_date: str, game_id: str) -> dict[str, Any]:
    params = urlencode({"game_date": _clean(game_date), "game_id": _clean(game_id)})
    url = gateway._api_base() + DECISION_ENDPOINT + "?" + params
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-CFB-GameTotal-Decision-V6/1"})
    with urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or _clean(payload.get("service")) != "Kyre Sports API":
        raise RuntimeError("Kyre Sports API returned an invalid Game Total decision payload.")
    return payload


def _decision_card_html(game: Mapping[str, Any], decision: Mapping[str, Any], selected_day: date) -> str:
    quote = base._quote(game)
    away = base._name(game, "away")
    home = base._name(game, "home")
    market_total = decision.get("market_total") if decision.get("market_total") is not None else quote.get("total_line")
    projected = decision.get("projected_total")
    over = decision.get("over_probability")
    under = decision.get("under_probability")
    push = decision.get("push_probability")
    tilt = _clean(decision.get("model_tilt")) or "MODEL_PENDING"
    edge = _num(decision.get("model_edge"))
    grade = _clean(decision.get("forecast_grade"))
    confidence = _clean(decision.get("confidence"))
    status = _clean(decision.get("status")) or "MODEL_PENDING"
    badge_class = "" if status == "READY" else " pending"
    badge = "MODEL READY" if status == "READY" else "MODEL PENDING"
    tilt_class = tilt.casefold() if tilt in {"OVER", "UNDER"} else ""
    edge_text = "Edge pending" if edge is None else f"{edge:+.1f} vs market"
    tilt_text = "MODEL PENDING" if tilt == "MODEL_PENDING" else f"{tilt} TILT • {edge_text}"
    model_meta = " • ".join(part for part in (grade and f"Grade {grade}", confidence and confidence.title()) if part) or "Frozen model snapshot"
    probability = f"O {_pct(over)} • U {_pct(under)}"
    if (_num(push) or 0.0) > 0.0005:
        probability += f" • P {_pct(push)}"
    consensus = game.get("market_consensus") if isinstance(game.get("market_consensus"), Mapping) else {}
    movement = game.get("line_movement") if isinstance(game.get("line_movement"), Mapping) else {}
    book = _clean(quote.get("sportsbook")) or "Verified market"
    observed = _clean(quote.get("observed_at_utc")) or "Freshness pending"
    integrity = _clean(game.get("market_integrity")) or "PENDING"
    href = base._game_href(game, selected_day)
    open_link = (
        f'<a class="cfbgt6-open" href="{escape(href, quote=True)}" target="_self">OPEN ANALYSIS →</a>'
        if href else '<span class="cfbgt6-open">ANALYSIS PENDING</span>'
    )
    price_text = f"O {base._american(quote.get('over_price'))} • U {base._american(quote.get('under_price'))}"
    return (
        '<div class="cfbgt6-card">'
        '<div class="cfbgt6-head">'
        '<div><div class="cfbgt6-match">'
        f'{_logo(game, "away")}<span class="cfbgt6-team">{escape(away)}</span><span class="cfbgt6-at">@</span>'
        f'<span class="cfbgt6-team">{escape(home)}</span>{_logo(game, "home")}'
        f'</div><span class="cfbgt6-kick">{escape(base._kickoff(game))}</span></div>'
        f'<span class="cfbgt6-badge{badge_class}">{escape(badge)}</span></div>'
        '<div class="cfbgt6-primary">'
        f'<div class="cfbgt6-metric cfbgt6-market"><small>MARKET TOTAL</small><strong>{escape(base._line(market_total))}</strong><em>{escape(book)}</em></div>'
        f'<div class="cfbgt6-metric cfbgt6-proj"><small>KYRE PROJECTED TOTAL</small><strong>{escape(_metric(projected))}</strong><em>Independent frozen model</em></div>'
        f'<div class="cfbgt6-metric cfbgt6-prob"><small>KYRE O/U PROBABILITY</small><strong>{escape(probability)}</strong><em>At verified market total</em></div>'
        '</div>'
        f'<div class="cfbgt6-tilt {escape(tilt_class)}"><div class="cfbgt6-tilt-top"><small>MODEL TILT</small><b>{escape(tilt_text)}</b></div>'
        f'<div class="cfbgt6-modelbar"><span class="cfbgt6-overbar" style="width:{escape(_width(over), quote=True)}"></span><span class="cfbgt6-pushbar" style="width:{escape(_width(push), quote=True)}"></span><span class="cfbgt6-underbar" style="width:{escape(_width(under), quote=True)}"></span></div>'
        f'<div class="cfbgt6-tilt-note"><strong>KYRE MODEL</strong> • {escape(model_meta)} • sportsbook projection weight 0%</div></div>'
        '<div class="cfbgt6-secondary">'
        f'<div><small>MARKET PRICES</small><strong>{escape(price_text)}</strong></div>'
        f'<div><small>BOOK CONSENSUS</small><strong>{escape(market_ui._consensus_text(consensus))}</strong></div>'
        f'<div><small>OPEN / MOVEMENT</small><strong>{escape(market_ui._movement_text(movement))}</strong></div>'
        '</div>'
        f'<div class="cfbgt6-foot"><div class="cfbgt6-proof">{escape(integrity)} • {escape(book)} • {escape(observed)}</div>{open_link}</div>'
        '</div>'
    )


def render_game_total_page1() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    requested = base._requested_date()
    try:
        payload = base._load_payload(requested)
    except Exception as exc:
        st.error(f"Kyre Sports API could not load the Game Total board: {type(exc).__name__}")
        return

    selected_day = base._selected_date(payload)
    games = [row for row in payload.get("games") or [] if isinstance(row, Mapping)]
    generated = _clean(payload.get("generated_at_utc")) or "Freshness pending"
    st.markdown(
        '<div class="cfbgt5-shell"><div class="cfbgt5-eyebrow">KYRE SPORTS AI • CFB GAME TOTALS</div>'
        '<div class="cfbgt5-title">Game Total Intelligence</div>'
        '<div class="cfbgt5-sub">Upcoming games only. Swipe the matchup rail, choose a game, then open the deeper analysis when you want the full research.</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="cfbgt5-date">📅 {escape(selected_day.strftime("%A • %B %d, %Y"))} • Phoenix</div>', unsafe_allow_html=True)
    picked = st.date_input("Slate date", value=selected_day, key="cfbgt6_date", label_visibility="collapsed")
    if picked != selected_day:
        st.query_params["date"] = picked.isoformat()
        st.query_params["ks_cfb_game_total_date"] = picked.isoformat()
        st.query_params.pop("cfbgt_game", None)
        st.rerun()

    st.markdown(
        '<div class="cfbgt5-board"><b>UPCOMING MATCHUPS</b>'
        f'<span>{len(games)} actionable games • started/final hidden • refreshed {escape(generated)}</span></div>',
        unsafe_allow_html=True,
    )
    if not games:
        st.markdown('<div class="cfbgt5-empty">No upcoming CFB games remain on this slate. Started and completed games are hidden automatically.</div>', unsafe_allow_html=True)
        return

    selected = selector._select_game(games, selector._requested_game())
    if selected is None:
        return
    st.markdown(prior._rail_html(games, selected, selected_day), unsafe_allow_html=True)
    st.markdown('<div class="cfbgt5-selected-label">Selected matchup</div>', unsafe_allow_html=True)
    game_id = selector._game_id(selected)
    try:
        decision = _load_decision(selected_day.isoformat(), game_id)
    except Exception:
        decision = {"service": "Kyre Sports API", "status": "MODEL_PENDING", "model_tilt": "MODEL_PENDING"}
    st.markdown(_decision_card_html(selected, decision, selected_day), unsafe_allow_html=True)


def render_cfb_hub(market: str, *args, **kwargs) -> None:
    del args, kwargs
    if market != MARKET:
        raise ValueError(f"CFB Game Total A-tier V6 cannot render market={market!r}")
    render_game_total_page1()


__all__ = [
    "DECISION_ENDPOINT",
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
