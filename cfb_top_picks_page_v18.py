"""CFB Top Picks V18 — canonical Page 2 decision command center.

Frontend data ownership remains Kyre Sports API only. This successor fixes the
Universal Runtime handoff by asserting canonical ``sport`` / ``market`` query
keys and presents the Page 2 evidence in a compact six-section hierarchy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping
from urllib.parse import urlencode

import streamlit as st

import cfb_top_picks_page_v15 as page1
import cfb_top_picks_page_v16 as prior

MODEL_VERSION = "CFB TOP PICKS V18 • S-TIER PAGE2 + CANONICAL ROUTE V2"
PAGE_MARKER = "CFB_TOP_PICKS_PAGE2_STIER_ROUTE_V2_ACTIVE"

CSS = r'''<style id="cfb-top-picks-v18-css">
:root{--kbg:#050c13;--kp:#071725;--kp2:#0a1d2d;--kl:rgba(80,193,255,.20);--kx:#4dc9ff;--kt:#f4fbff;--km:#8fa7b8;--kg:#73e5b5;--ky:#ffd274;--kr:#ff8d8d}
[data-testid="cfb-top-picks-page2-v2-root"]{max-width:1180px;margin:auto;padding:8px 2px 46px;color:var(--kt);font-family:Inter,system-ui,sans-serif}.k18-back{display:inline-block;margin:0 0 10px;padding:7px 11px;border:1px solid var(--kl);border-radius:9px;color:#9bdcff!important;text-decoration:none!important;font-size:.68rem;font-weight:900}.k18-shell{border:1px solid rgba(79,195,255,.27);border-radius:22px;background:radial-gradient(circle at 82% -8%,rgba(33,170,233,.15),transparent 31%),linear-gradient(150deg,#071725,#040c14);box-shadow:0 24px 70px rgba(0,0,0,.28);overflow:hidden}.k18-hero{padding:18px 20px;border-bottom:1px solid rgba(255,255,255,.06)}.k18-kicker{font-size:.52rem;color:var(--kx);font-weight:950;letter-spacing:.11em}.k18-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;align-items:end;margin-top:8px}.k18-head h1{font-size:1.85rem;line-height:1.05;margin:0;letter-spacing:-.04em}.k18-sub{margin-top:6px;color:var(--km);font-size:.68rem}.k18-verdict{min-width:190px;border:1px solid var(--kl);border-radius:14px;padding:11px 13px;background:rgba(9,35,53,.70)}.k18-verdict b{display:block;font-size:1rem}.k18-verdict.pass b{color:var(--ky)}.k18-verdict.bet b{color:var(--kg)}.k18-verdict span{font-size:.55rem;color:var(--km)}.k18-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:13px}.k18-metric{border:1px solid rgba(255,255,255,.055);background:rgba(255,255,255,.025);border-radius:11px;padding:9px;min-width:0}.k18-metric b{display:block;font-size:1rem}.k18-metric span{display:block;color:var(--km);font-size:.49rem;font-weight:900;margin-top:2px}.k18-grid{display:grid;grid-template-columns:1.08fr .92fr;gap:11px;padding:12px 16px 16px}.k18-card{border:1px solid rgba(81,188,245,.14);border-radius:14px;background:linear-gradient(150deg,rgba(8,27,43,.97),rgba(6,18,29,.99));padding:13px;min-width:0}.k18-wide{grid-column:1/-1}.k18-card h2{font-size:.79rem;letter-spacing:.045em;margin:2px 0 10px}.k18-rows{display:grid;gap:6px}.k18-row{display:grid;grid-template-columns:86px minmax(0,1fr) auto;gap:8px;align-items:center;padding:8px 9px;border-radius:9px;background:rgba(255,255,255,.025);font-size:.61rem}.k18-row.current{outline:1px solid rgba(77,201,255,.55);background:rgba(26,91,126,.16)}.k18-row.good{border-left:3px solid var(--kg)}.k18-row.bad{border-left:3px solid var(--kr)}.k18-row.neutral{border-left:3px solid var(--ky)}.k18-pill{display:inline-block;padding:3px 6px;border:1px solid rgba(77,201,255,.28);border-radius:99px;color:#8edcff;font-size:.48rem;font-weight:950}.k18-buy{margin:8px 0 0;padding:8px 10px;border:1px solid rgba(115,229,181,.25);border-radius:9px;background:rgba(17,79,59,.12);color:#aaf3d1;font-size:.61rem}.k18-compare{display:grid;gap:7px}.k18-compare-row{display:grid;grid-template-columns:120px 72px minmax(90px,1fr) 72px;gap:7px;align-items:center;font-size:.58rem}.k18-bar{height:7px;border-radius:99px;background:#122839;overflow:hidden;display:flex}.k18-bar i{display:block;height:100%;background:linear-gradient(90deg,#36aeea,#69e0b5)}.k18-semantic{padding:9px 10px;border:1px dashed rgba(255,210,116,.28);border-radius:9px;background:rgba(85,62,20,.10);color:#e5ca82;font-size:.61rem;line-height:1.35}.k18-list{display:grid;gap:6px}.k18-item{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.045);font-size:.59rem}.k18-item:last-child{border-bottom:0}.k18-item span{color:var(--km);text-align:right}.k18-three{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.k18-mini{border:1px solid rgba(255,255,255,.055);border-radius:10px;padding:9px;background:rgba(255,255,255,.02)}.k18-mini h3{margin:0 0 7px;font-size:.62rem}.k18-audit{margin-top:2px}.k18-audit summary{cursor:pointer;color:#9bdcff;font-size:.64rem;font-weight:950;list-style-position:inside}.k18-audit-body{margin-top:8px;padding-top:7px;border-top:1px solid rgba(255,255,255,.05)}.k18-foot{text-align:center;padding:4px 16px 16px;color:#567186;font-size:.5rem}
@media(max-width:850px){.k18-grid{grid-template-columns:1fr}.k18-wide{grid-column:auto}.k18-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.k18-three{grid-template-columns:1fr}.k18-head{grid-template-columns:1fr}.k18-verdict{min-width:0}.k18-compare-row{grid-template-columns:100px 58px minmax(70px,1fr) 58px}}
</style>'''


def _c(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _n(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number == number else None


def _pct(value: Any, *, empty: str = "Pending verification") -> str:
    n = _n(value)
    if n is None:
        return empty
    if -1 <= n <= 1:
        n *= 100
    return f"{n:.1f}%"


def _num(value: Any, *, empty: str = "Pending verification") -> str:
    n = _n(value)
    return empty if n is None else f"{n:.1f}"


def _odds(value: Any, *, empty: str = "Price pending") -> str:
    n = _n(value)
    if n is None:
        return empty
    x = int(round(n))
    return f"+{x}" if x > 0 else str(x)


def _module(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, Mapping) else {
        "status": "SEMANTIC_EMPTY",
        "semantic_state": "NOT_VERIFIED",
        "reason": "Verified evidence has not been attached to this module yet.",
    }


def _semantic(module: Mapping[str, Any], fallback: str) -> str:
    reason = _c(module.get("reason") or module.get("message")) or fallback
    return f'<div class="k18-semantic">{escape(reason)}</div>'


def _page1_handoff(row: Mapping[str, Any], kind: str) -> str:
    query = {
        "sport": "cfb",
        "market": "top-picks",
        "top_pick_id": _c(row.get("candidate_id")),
        "top_pick_kind": kind,
        "top_pick_date": _c(row.get("selected_date") or _c(row.get("kickoff_iso"))[:10]),
        # Legacy mirror stays only for old bookmarks; Universal Runtime V5 owns
        # navigation from the canonical sport/market pair above.
        "ks_sport": "College Football",
        "ks_cfb_market": "Top Picks",
    }
    return "?" + urlencode({key: value for key, value in query.items() if value})


def _back_href(snapshot: Mapping[str, Any]) -> str:
    query = {
        "sport": "cfb",
        "market": "top-picks",
        "top_pick_date": _c(snapshot.get("selected_date")),
        "ks_sport": "College Football",
        "ks_cfb_market": "Top Picks",
    }
    return "?" + urlencode({key: value for key, value in query.items() if value})


def _metric(label: str, value: str) -> str:
    return f'<div class="k18-metric"><b>{escape(value)}</b><span>{escape(label)}</span></div>'


def _freshness(value: Any, status: Any = None) -> str:
    text = _c(value)
    if text:
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
            return f"Updated {dt.strftime('%H:%M UTC')}"
        except ValueError:
            pass
    state = _c(status).replace("_", " ").title()
    return state or "Freshness timestamp pending"


def _hero(payload: Mapping[str, Any]) -> str:
    s = _module(payload, "selection_snapshot")
    v = _module(payload, "kyre_verdict")
    prop = _c(s.get("kind")) == "player-prop"
    title = _c(s.get("player_name")) if prop else f"{_c(s.get('away_team'))} @ {_c(s.get('home_team'))}"
    selection = _c(s.get("selection")) or f"{_c(s.get('side'))} {_c(s.get('line'))}".strip()
    verdict = _c(v.get("verdict")) or "Decision pending verified inputs"
    cls = "pass" if "PASS" in verdict.upper() else "bet" if "BET" in verdict.upper() else ""
    metrics = "".join((
        _metric("SELECTED PRICE", _odds(v.get("selected_price") if v.get("selected_price") is not None else s.get("american_odds"))),
        _metric("MODEL PROBABILITY", _pct(v.get("outcome_confidence"))),
        _metric("MARKET IMPLIED", _pct(v.get("market_implied_probability"))),
        _metric("MODEL FAIR PRICE", _odds(v.get("model_fair_price"))),
        _metric("VALUE EDGE", _pct(v.get("market_value_edge"))),
    ))
    subtitle = " • ".join(part for part in (_c(s.get("market_type") or s.get("market_label")), _c(s.get("sportsbook")), selection) if part)
    return (
        '<section class="k18-hero"><div class="k18-kicker">GAME DECISION</div>'
        f'<div class="k18-head"><div><h1>{escape(title)}</h1><div class="k18-sub">{escape(subtitle)}</div></div>'
        f'<div class="k18-verdict {cls}"><span>KYRE VERDICT</span><b>{escape(verdict)}</b><span>{escape(selection)}</span></div></div>'
        f'<div class="k18-metrics">{metrics}</div></section>'
    )


def _price_market(payload: Mapping[str, Any]) -> str:
    lab = _module(payload, "line_lab")
    board = _module(payload, "market_board")
    movement = _module(payload, "line_movement")
    snapshot = _module(payload, "selection_snapshot")
    selected_price = _n(snapshot.get("american_odds"))
    scenarios = [dict(row) for row in lab.get("scenarios") or [] if isinstance(row, Mapping)]
    rows: list[str] = []
    positive_prices: list[int] = []
    for row in scenarios:
        price = _n(row.get("american_odds"))
        edge = _n(row.get("market_value_edge"))
        if price is None:
            continue
        if edge is not None and edge > 0:
            positive_prices.append(int(round(price)))
        current = selected_price is not None and int(round(price)) == int(round(selected_price))
        cls = "good" if (edge or 0) > 0 else "bad" if (edge or 0) < 0 else "neutral"
        current_badge = '<span class="k18-pill">CURRENT</span>' if current else ""
        rows.append(
            f'<div class="k18-row {cls} {"current" if current else ""}"><b>{escape(_odds(price))}</b>'
            f'<span>Implied {_pct(row.get("implied_probability"))} • Model {_pct(row.get("model_probability"))}</span>'
            f'<span>{current_badge} Edge {_pct(edge)}</span></div>'
        )
    buy = ""
    if positive_prices:
        # For negative moneyline prices, a less-negative number is a better price.
        threshold = min(positive_prices)
        buy = f'<div class="k18-buy"><b>BUY ZONE</b> • Positive modeled value appears at {_odds(threshold)} or better in the certified price ladder.</div>'
    elif scenarios:
        buy = '<div class="k18-buy"><b>BUY ZONE</b> • No positive-value price appears inside the certified ladder currently tested.</div>'
    quote_rows: list[str] = []
    for quote in board.get("quotes") or []:
        if not isinstance(quote, Mapping):
            continue
        quote_rows.append(
            f'<div class="k18-item"><b>{escape(_c(quote.get("sportsbook")) or "Verified sportsbook")}</b>'
            f'<span>{escape(_c(quote.get("side")))} {_odds(quote.get("american_odds"))} • '
            f'{escape(_freshness(quote.get("observed_at_utc"), quote.get("freshness_status")))}</span></div>'
        )
    lab_body = '<div class="k18-rows">' + "".join(rows) + '</div>' + buy if rows else _semantic(lab, "Certified alternate prices are not posted for this market yet.")
    market_body = "".join(quote_rows) if quote_rows else _semantic(board, "Market Not Posted Yet")
    movement_body = _semantic(movement, "Opening Line Not Independently Verified") if movement.get("status") != "READY" else _semantic(movement, "Line movement verified")
    return (
        '<section class="k18-card k18-wide"><div class="k18-kicker">PRICE + MARKET LAB</div><h2>PRICE + MARKET LAB</h2>'
        f'<div class="k18-three"><div class="k18-mini"><h3>PRICE LADDER</h3>{lab_body}</div>'
        f'<div class="k18-mini"><h3>LIVE MARKET BOARD</h3>{market_body}</div>'
        f'<div class="k18-mini"><h3>OPEN / CURRENT</h3>{movement_body}</div></div></section>'
    )


def _projection(payload: Mapping[str, Any]) -> str:
    p = _module(payload, "projection")
    if p.get("status") not in {"READY", "PARTIAL"}:
        body = _semantic(p, "Projection inputs are still being verified.")
    else:
        body = '<div class="k18-metrics">' + "".join((
            _metric("HOME POINTS", _num(p.get("projected_home_points"))),
            _metric("AWAY POINTS", _num(p.get("projected_away_points"))),
            _metric("HOME MARGIN", _num(p.get("projected_margin_home"))),
            _metric("PROJECTED TOTAL", _num(p.get("projected_total"))),
            _metric("SELECTED HIT", _pct(p.get("selected_hit_probability") if p.get("selected_hit_probability") is not None else p.get("selected_probability"))),
        )) + '</div><div class="k18-sub">Kyre model outputs are displayed from their own raw values; rounded team scores are not re-summed into a replacement total.</div>'
    return f'<section class="k18-card"><div class="k18-kicker">MODEL PROJECTION</div><h2>MODEL PROJECTION</h2>{body}</section>'


def _matchup(payload: Mapping[str, Any]) -> str:
    d = _module(payload, "drivers")
    items = [dict(row) for row in d.get("items") or [] if isinstance(row, Mapping)]
    if not items:
        body = _semantic(d, "No Qualifying Games")
    else:
        rows: list[str] = []
        for item in items:
            away, home = _n(item.get("away")), _n(item.get("home"))
            if away is None and home is None:
                continue
            max_abs = max(abs(away or 0), abs(home or 0), 1.0)
            away_w = int(round(abs(away or 0) / max_abs * 50))
            home_w = int(round(abs(home or 0) / max_abs * 50))
            rows.append(
                f'<div class="k18-compare-row"><b>{escape(_c(item.get("title")))}</b><span>{escape(_num(away))}</span>'
                f'<div class="k18-bar"><i style="width:{away_w}%"></i><i style="width:{home_w}%"></i></div><span>{escape(_num(home))}</span></div>'
            )
        body = '<div class="k18-compare">' + "".join(rows) + '</div>' if rows else _semantic(d, "No Qualifying Games")
    recent = _module(payload, "recent_form")
    history = _module(payload, "history")
    extras = f'<div class="k18-three" style="margin-top:9px"><div class="k18-mini"><h3>RECENT FORM</h3>{_module_list(recent, "Recent form sample is still being verified.")}</div><div class="k18-mini"><h3>MATCHUP HISTORY</h3>{_module_list(history, "No Previous Meetings")}</div><div class="k18-mini"><h3>GAME ENVIRONMENT</h3>{_module_list(_module(payload,"game_environment"), "Pregame environment verification in progress.")}</div></div>'
    return f'<section class="k18-card"><div class="k18-kicker">MATCHUP INTELLIGENCE</div><h2>MATCHUP INTELLIGENCE</h2>{body}{extras}</section>'


def _module_list(module: Mapping[str, Any], fallback: str) -> str:
    items = [row for row in module.get("items") or module.get("rows") or [] if isinstance(row, Mapping)]
    if not items:
        return _semantic(module, fallback)
    body = []
    for item in items[:10]:
        title = _c(item.get("title") or item.get("team") or item.get("date") or item.get("opponent"))
        value = _c(item.get("text") or item.get("value") or item.get("record") or item.get("result"))
        body.append(f'<div class="k18-item"><b>{escape(title)}</b><span>{escape(value)}</span></div>')
    return "".join(body)


def _why_risk_flip(payload: Mapping[str, Any]) -> str:
    drivers = _module(payload, "drivers")
    risks = _module(payload, "risks")
    flips = _module(payload, "flip_conditions")
    why = [row for row in drivers.get("items") or [] if isinstance(row, Mapping)]
    why_body = "".join(
        f'<div class="k18-item"><b>{escape(_c(row.get("title")))}</b><span>{escape(_c(row.get("value")) or ("Away " + _num(row.get("away")) + " • Home " + _num(row.get("home"))))}</span></div>'
        for row in why[:6]
    ) or _semantic(drivers, "Verified decision drivers are still being enriched.")
    return (
        '<section class="k18-card k18-wide"><div class="k18-kicker">WHY / RISKS / FLIP CONDITIONS</div><h2>WHY / RISKS / FLIP CONDITIONS</h2>'
        f'<div class="k18-three"><div class="k18-mini"><h3>WHY THIS PICK</h3>{why_body}</div>'
        f'<div class="k18-mini"><h3>WHAT COULD GO WRONG</h3>{_module_list(risks,"No additional verified risk flags")}</div>'
        f'<div class="k18-mini"><h3>WHAT WOULD FLIP THE PICK</h3>{_module_list(flips,"No verified flip condition has been calculated yet.")}</div></div></section>'
    )


def _audit(payload: Mapping[str, Any]) -> str:
    s = _module(payload, "sources")
    modules = s.get("modules") if isinstance(s.get("modules"), Mapping) else {}
    rows = "".join(
        f'<div class="k18-item"><b>{escape(str(key).replace("_"," ").upper())}</b><span>{escape(_c(value))}</span></div>'
        for key, value in modules.items()
    )
    if not rows:
        rows = _semantic(s, "Source audit is being verified.")
    return (
        '<section class="k18-card k18-wide"><details class="k18-audit"><summary>DATA INTEGRITY</summary>'
        f'<div class="k18-audit-body"><div class="k18-sub">Kyre Sports API owns application delivery, canonical identity, fallback, normalization, freshness, and semantic empty states.</div>{rows}</div>'
        '</details></section>'
    )


def render_page2_html(payload: Mapping[str, Any]) -> str:
    snapshot = _module(payload, "selection_snapshot")
    return (
        '<section data-testid="cfb-top-picks-page2-v2-root" data-page-marker="' + PAGE_MARKER + '"><div class="k18-shell">'
        + _hero(payload)
        + '<div class="k18-grid">'
        + _price_market(payload)
        + _projection(payload)
        + _matchup(payload)
        + _why_risk_flip(payload)
        + _audit(payload)
        + '</div><div class="k18-foot">PAGE 2 • MODEL OUTPUTS OWNED BY KYRE SPORTS API • SPORTSBOOKS PROVIDE MARKET CONTEXT ONLY</div></div></section>'
    )


def _qp(name: str) -> str:
    try:
        value = st.query_params.get(name)
    except Exception:
        value = None
    if isinstance(value, list):
        value = value[0] if value else None
    return _c(value)


def render_cfb_hub(_market_name: str = "Top Picks") -> None:
    # Page 1 stays frozen; only its detail-link callback is swapped at render time.
    page1._handoff = _page1_handoff
    candidate_id = _qp("top_pick_id")
    if not candidate_id:
        page1.render_cfb_hub(_market_name)
        return
    kind = _qp("top_pick_kind")
    date_ = _qp("top_pick_date")
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        payload = prior._load_page2(candidate_id, kind, date_)
    except Exception as exc:
        st.error(f"Top Picks analysis is temporarily unable to verify this selection ({type(exc).__name__}).")
        return
    snapshot = payload.get("selection_snapshot") if isinstance(payload.get("selection_snapshot"), Mapping) else {}
    st.markdown(f'<a class="k18-back" href="{escape(_back_href(snapshot), quote=True)}">← Back to Top Picks</a>', unsafe_allow_html=True)
    st.markdown(render_page2_html(payload), unsafe_allow_html=True)


__all__ = ["MODEL_VERSION", "PAGE_MARKER", "_back_href", "_page1_handoff", "render_page2_html", "render_cfb_hub"]
