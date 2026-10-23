"""CFB Top Picks Page 2 V19 — identity + market intelligence successor.

Presentation-only. All application data comes from the normalized Kyre Sports API
Page 2 payload. This module does not call sportsbooks, stat providers, or model
providers directly and does not alter projection math.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping
from urllib.parse import urlencode

PAGE_MARKER = "CFB_TOP_PICKS_PAGE2_IDENTITY_MARKET_V3_ACTIVE"
MODEL_VERSION = "CFB TOP PICKS V19 • IDENTITY + MARKET INTELLIGENCE V3"

CSS = r'''<style id="cfb-top-picks-v19-css">
:root{--x:#4dc9ff;--g:#73e5b5;--y:#ffd274;--t:#f4fbff;--m:#8fa7b8;--l:rgba(80,193,255,.20)}
[data-testid="cfb-top-picks-page2-v3-root"]{max-width:1180px;margin:auto;padding:8px 2px 48px;color:var(--t);font-family:Inter,system-ui,sans-serif}.v19-shell{border:1px solid rgba(79,195,255,.28);border-radius:22px;background:radial-gradient(circle at 82% -8%,rgba(33,170,233,.16),transparent 31%),linear-gradient(150deg,#071725,#040c14);overflow:hidden}.v19-back{display:inline-block;margin:0 0 10px;padding:7px 11px;border:1px solid var(--l);border-radius:9px;color:#9bdcff!important;text-decoration:none!important;font-size:.68rem;font-weight:900}.v19-hero{padding:18px 20px;border-bottom:1px solid rgba(255,255,255,.06)}.v19-kicker{font-size:.52rem;color:var(--x);font-weight:950;letter-spacing:.11em}.v19-matchup{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;margin:10px 0 12px}.v19-team{display:flex;align-items:center;gap:10px;min-width:0}.v19-team.home{justify-content:flex-end;text-align:right}.v19-logo-wrap{width:46px;height:46px;display:grid;place-items:center;flex:0 0 46px}.v19-logo{width:42px;height:42px;object-fit:contain}.v19-small-logo{width:20px;height:20px;object-fit:contain}.v19-fallback{width:42px;height:42px;border:1px solid var(--l);border-radius:50%;display:grid;place-items:center;font-size:.62rem;font-weight:950;color:#a7ddf6;background:rgba(77,201,255,.08)}.v19-vs{font-size:.58rem;font-weight:950;color:#6d8a9e}.v19-team-name{font-size:1.12rem;font-weight:950}.v19-record,.v19-meta{font-size:.57rem;color:var(--m)}.v19-verdictline{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:10px 12px;border:1px solid var(--l);border-radius:13px;background:rgba(9,35,53,.70)}.v19-verdict b{display:block;font-size:1rem;color:var(--g)}.v19-verdict span{font-size:.57rem;color:var(--m)}.v19-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:10px}.v19-metric,.v19-mini{border:1px solid rgba(255,255,255,.055);background:rgba(255,255,255,.025);border-radius:11px;padding:9px;min-width:0}.v19-metric b{display:block;font-size:1rem}.v19-metric span{display:block;color:var(--m);font-size:.49rem;font-weight:900;margin-top:2px}.v19-edge{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:9px}.v19-edge div{padding:8px 9px;border-radius:9px;background:rgba(77,201,255,.055);border:1px solid rgba(77,201,255,.10);font-size:.58rem;font-weight:900}.v19-fresh{display:flex;gap:7px;flex-wrap:wrap;margin:10px 20px 0}.v19-chip{padding:5px 7px;border:1px solid rgba(77,201,255,.14);border-radius:99px;background:rgba(77,201,255,.05);font-size:.51rem;color:#a7c3d3}.v19-grid{display:grid;grid-template-columns:1fr 1fr;gap:11px;padding:12px 16px 16px}.v19-card{border:1px solid rgba(81,188,245,.14);border-radius:14px;background:linear-gradient(150deg,rgba(8,27,43,.97),rgba(6,18,29,.99));padding:13px;min-width:0}.v19-wide{grid-column:1/-1}.v19-card h2{font-size:.79rem;letter-spacing:.045em;margin:2px 0 10px}.v19-three{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.v19-mini h3{margin:0 0 7px;font-size:.62rem}.v19-item{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.045);font-size:.59rem;align-items:center}.v19-item:last-child{border-bottom:0}.v19-item span{color:var(--m);text-align:right}.v19-semantic{padding:9px 10px;border:1px dashed rgba(255,210,116,.28);border-radius:9px;background:rgba(85,62,20,.10);color:#e5ca82;font-size:.61rem;line-height:1.35}.v19-books{display:flex;gap:7px;overflow-x:auto}.v19-book{min-width:112px;padding:8px 9px;border:1px solid rgba(255,255,255,.06);border-radius:9px;background:rgba(255,255,255,.025);font-size:.55rem}.v19-book.best{border-color:rgba(115,229,181,.45);background:rgba(17,79,59,.13)}.v19-book b,.v19-book span{display:block}.v19-book span{color:var(--m)}.v19-best{color:var(--g)!important;font-weight:950}.v19-sensitivity{display:grid;gap:6px}.v19-sens{display:grid;grid-template-columns:72px 1fr auto;gap:8px;align-items:center;padding:7px 8px;border-radius:8px;background:rgba(255,255,255,.022);font-size:.57rem}.v19-track{height:6px;border-radius:99px;background:#122839;overflow:hidden}.v19-track i{display:block;height:100%;background:linear-gradient(90deg,#36aeea,#69e0b5)}.v19-compare-head,.v19-compare-row{display:grid;grid-template-columns:126px 1fr 1fr;gap:8px;align-items:center}.v19-compare-head{padding:0 5px 6px;color:var(--m);font-size:.54rem;font-weight:900}.v19-side,.v19-teamvalue{display:flex;align-items:center;gap:5px}.v19-side.home,.v19-teamvalue.home{justify-content:flex-end}.v19-compare-row{padding:8px 5px;border-top:1px solid rgba(255,255,255,.04);font-size:.58rem}.v19-audit summary{cursor:pointer;color:#9bdcff;font-size:.64rem;font-weight:950}.v19-foot{text-align:center;padding:4px 16px 16px;color:#567186;font-size:.5rem}
@media(max-width:850px){.v19-grid{grid-template-columns:1fr}.v19-wide{grid-column:auto}.v19-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.v19-three{grid-template-columns:1fr}.v19-compare-head,.v19-compare-row{grid-template-columns:106px 1fr 1fr}}
@media(max-width:560px){.v19-team-name{font-size:.92rem}.v19-verdictline{align-items:flex-start;flex-direction:column}.v19-edge{grid-template-columns:1fr}.v19-grid{padding:10px}}
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


def _pct(value: Any, *, signed: bool = False, empty: str = "Pending verification") -> str:
    number = _n(value)
    if number is None:
        return empty
    if -1 <= number <= 1:
        number *= 100
    return f"{'+' if signed and number > 0 else ''}{number:.1f}%"


def _num(value: Any, *, empty: str = "Pending verification") -> str:
    number = _n(value)
    return empty if number is None else f"{number:.1f}"


def _odds(value: Any, *, empty: str = "Price pending") -> str:
    number = _n(value)
    if number is None:
        return empty
    out = int(round(number))
    return f"+{out}" if out > 0 else str(out)


def _module(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, Mapping) else {"status": "SEMANTIC_EMPTY", "reason": "Verified evidence has not been attached yet."}


def _semantic(module: Mapping[str, Any], fallback: str) -> str:
    text = _c(module.get("reason") or module.get("message")) or fallback
    return f'<div class="v19-semantic">{escape(text)}</div>'


def _initials(name: str) -> str:
    words = [word for word in name.replace("-", " ").split() if word]
    return "".join(word[0] for word in words[:2]).upper() if words else "CFB"


def _logo(url: Any, name: str, side: str, *, small: bool = False) -> str:
    src = _c(url)
    size_class = "v19-small-logo" if small else "v19-logo"
    fallback_style = "display:none" if src.startswith(("https://", "http://")) else ""
    fallback = f'<span class="v19-fallback" style="{fallback_style}">{escape(_initials(name))}</span>'
    if not src.startswith(("https://", "http://")):
        return fallback
    return (
        f'<img class="{size_class}" data-team-logo="{escape(side, quote=True)}" src="{escape(src, quote=True)}" '
        f'alt="{escape(name, quote=True)} logo" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'grid\'">{fallback}'
    )


def _team(snapshot: Mapping[str, Any], side: str) -> dict[str, str]:
    return {
        "name": _c(snapshot.get(f"{side}_team")) or side.title(),
        "record": _c(snapshot.get(f"{side}_record")) or "Record pending verification",
        "logo": _c(snapshot.get(f"{side}_logo")),
    }


def _page1_handoff(row: Mapping[str, Any], kind: str) -> str:
    query = {
        "sport": "cfb",
        "market": "top-picks",
        "top_pick_id": _c(row.get("candidate_id")),
        "top_pick_kind": kind,
        "top_pick_date": _c(row.get("selected_date") or _c(row.get("kickoff_iso"))[:10]),
        "ks_sport": "College Football",
        "ks_cfb_market": "Top Picks",
    }
    return "?" + urlencode({k: v for k, v in query.items() if v})


def _back_href(snapshot: Mapping[str, Any]) -> str:
    query = {"sport": "cfb", "market": "top-picks", "top_pick_date": _c(snapshot.get("selected_date")), "ks_sport": "College Football", "ks_cfb_market": "Top Picks"}
    return "?" + urlencode({k: v for k, v in query.items() if v})


def _time(value: Any) -> str:
    text = _c(value)
    if not text:
        return "timestamp pending"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%H:%M UTC")
    except ValueError:
        return text


def _metric(label: str, value: str) -> str:
    return f'<div class="v19-metric"><b>{escape(value)}</b><span>{escape(label)}</span></div>'


def _hero(payload: Mapping[str, Any]) -> str:
    snapshot, verdict = _module(payload, "selection_snapshot"), _module(payload, "kyre_verdict")
    away, home = _team(snapshot, "away"), _team(snapshot, "home")
    selection = _c(snapshot.get("selection")) or f"{_c(snapshot.get('side'))} {_c(snapshot.get('line'))}".strip()
    subtitle = " • ".join(x for x in (_c(snapshot.get("market_type") or snapshot.get("market_label")), _c(snapshot.get("sportsbook")), selection) if x)
    return (
        '<section class="v19-hero"><div class="v19-kicker">GAME DECISION • TEAM IDENTITY LOCKED</div><div class="v19-matchup">'
        f'<div class="v19-team"><div class="v19-logo-wrap">{_logo(away["logo"], away["name"], "away")}</div><div><div class="v19-team-name">{escape(away["name"])}</div><div class="v19-record">{escape(away["record"])}</div></div></div>'
        '<div class="v19-vs">VS</div>'
        f'<div class="v19-team home"><div><div class="v19-team-name">{escape(home["name"])}</div><div class="v19-record">{escape(home["record"])}</div></div><div class="v19-logo-wrap">{_logo(home["logo"], home["name"], "home")}</div></div></div>'
        f'<div class="v19-verdictline"><div class="v19-verdict"><span>KYRE VERDICT</span><b>{escape(_c(verdict.get("verdict")) or "Decision pending verified inputs")}</b><span>{escape(subtitle)}</span></div><div class="v19-meta">{escape(_c(snapshot.get("selected_date")) or "Date pending verification")} • Market {_time(snapshot.get("market_timestamp"))}</div></div>'
        '<div class="v19-metrics">'
        + _metric("SELECTED PRICE", _odds(verdict.get("selected_price") if verdict.get("selected_price") is not None else snapshot.get("american_odds")))
        + _metric("MODEL PROBABILITY", _pct(verdict.get("outcome_confidence")))
        + _metric("MARKET IMPLIED", _pct(verdict.get("market_implied_probability")))
        + _metric("MODEL FAIR PRICE", _odds(verdict.get("model_fair_price")))
        + _metric("VALUE EDGE", _pct(verdict.get("market_value_edge"), signed=True))
        + '</div><div class="v19-edge">'
        + f'<div>MODEL {_pct(verdict.get("outcome_confidence"))}</div><div>MARKET {_pct(verdict.get("market_implied_probability"))}</div><div>EDGE {_pct(verdict.get("market_value_edge"), signed=True)}</div></div></section>'
    )


def _market(payload: Mapping[str, Any]) -> str:
    board, lab, movement = _module(payload, "market_board"), _module(payload, "line_lab"), _module(payload, "line_movement")
    best = board.get("best_available_price") if isinstance(board.get("best_available_price"), Mapping) else {}
    best_key = (_c(best.get("sportsbook")), _n(best.get("line")), _n(best.get("american_odds")))
    books: list[str] = []
    for quote in [q for q in board.get("quotes") or [] if isinstance(q, Mapping)][:12]:
        key = (_c(quote.get("sportsbook")), _n(quote.get("line")), _n(quote.get("american_odds")))
        is_best = bool(best_key[0]) and key == best_key
        line = _num(quote.get("line")) if quote.get("line") is not None else "Line pending"
        books.append(
            f'<div class="v19-book {"best" if is_best else ""}"><b>{escape(_c(quote.get("sportsbook")) or "Verified book")}</b>'
            f'<span>{escape(_c(quote.get("side")) or "Side pending")} • {escape(line)} • {_odds(quote.get("american_odds"))}</span>'
            + ('<span class="v19-best">BEST PRICE</span>' if is_best else f'<span>{escape(_time(quote.get("observed_at_utc")))}</span>') + '</div>'
        )
    book_body = '<div class="v19-books">' + "".join(books) + '</div>' if books else _semantic(board, "Market Not Posted Yet")

    rows: list[str] = []
    for scenario in [r for r in lab.get("scenarios") or [] if isinstance(r, Mapping)][:9]:
        if _c(lab.get("lab_type")).upper() == "PRICE":
            label, probability = _odds(scenario.get("american_odds")), scenario.get("model_probability")
        else:
            label = f"Line {_num(scenario.get('line'))}"
            probability = scenario.get("selected_side_probability")
            if probability is None:
                probability = scenario.get("over_probability") if scenario.get("over_probability") is not None else scenario.get("under_probability")
        number = _n(probability)
        if number is None:
            rows.append(f'<div class="v19-sens" data-probability-state="pending"><b>{escape(label)}</b><div class="v19-semantic">Pending verification</div><span>Pending verification</span></div>')
            continue
        normalized = number * 100 if -1 <= number <= 1 else number
        width = max(0, min(100, int(round(normalized))))
        rows.append(f'<div class="v19-sens" data-probability-state="verified"><b>{escape(label)}</b><div class="v19-track"><i style="width:{width}%"></i></div><span>{_pct(probability)}</span></div>')
    sensitivity = '<div class="v19-sensitivity">' + "".join(rows) + '</div>' if rows else _semantic(lab, "Certified alternate prices are not posted for this market yet.")
    movement_body = _module_list(movement, "Line movement verified") if movement.get("status") == "READY" else _semantic(movement, "Opening Line Not Independently Verified")
    return f'<section class="v19-card v19-wide"><div class="v19-kicker">PRICE + MARKET LAB</div><h2>PRICE + MARKET LAB</h2><div class="v19-three"><div class="v19-mini"><h3>SPORTSBOOK CONSENSUS</h3>{book_body}</div><div class="v19-mini"><h3>PROBABILITY SENSITIVITY</h3>{sensitivity}</div><div class="v19-mini"><h3>OPEN / CURRENT</h3>{movement_body}</div></div></section>'


def _projection(payload: Mapping[str, Any]) -> str:
    snapshot, projection = _module(payload, "selection_snapshot"), _module(payload, "projection")
    away, home = _team(snapshot, "away"), _team(snapshot, "home")
    if projection.get("status") not in {"READY", "PARTIAL"}:
        body = _semantic(projection, "Projection inputs are still being verified.")
    else:
        body = (
            '<div class="v19-compare-head"><span>PROJECTED SCORE</span>'
            f'<span class="v19-side">{_logo(away["logo"], away["name"], "away-projection", small=True)} {escape(away["name"])}</span>'
            f'<span class="v19-side home">{escape(home["name"])} {_logo(home["logo"], home["name"], "home-projection", small=True)}</span></div>'
            '<div class="v19-metrics">'
            + _metric(f'{home["name"]} projected', _num(projection.get("projected_home_points")))
            + _metric(f'{away["name"]} projected', _num(projection.get("projected_away_points")))
            + _metric("HOME MARGIN", _num(projection.get("projected_margin_home")))
            + _metric("PROJECTED TOTAL", _num(projection.get("projected_total")))
            + _metric("SELECTED HIT", _pct(projection.get("selected_hit_probability") if projection.get("selected_hit_probability") is not None else projection.get("selected_probability"))) + '</div>'
        )
    return f'<section class="v19-card"><div class="v19-kicker">MODEL PROJECTION</div><h2>MODEL PROJECTION</h2>{body}</section>'


def _module_list(module: Mapping[str, Any], fallback: str, *, payload: Mapping[str, Any] | None = None) -> str:
    items = [r for r in module.get("items") or module.get("rows") or [] if isinstance(r, Mapping)]
    if not items:
        return _semantic(module, fallback)
    snapshot = _module(payload or {}, "selection_snapshot") if payload else {}
    away, home = (_team(snapshot, "away"), _team(snapshot, "home")) if snapshot else ({}, {})
    out: list[str] = []
    for item in items[:10]:
        title = _c(item.get("title") or item.get("team") or item.get("date") or item.get("opponent")) or "Verified field"
        raw = item.get("text") if item.get("text") is not None else item.get("value") if item.get("value") is not None else item.get("record") if item.get("record") is not None else item.get("result")
        if title.casefold() == "model reliability":
            number = _n(raw)
            value = f"{number * 100:.1f}%" if number is not None and 0 <= number <= 1 else _c(raw) or "Pending verification"
        else:
            value = _c(raw) or "Pending verification"
        identity = ""
        if away and title.casefold() == _c(away.get("name")).casefold():
            identity = _logo(away.get("logo"), _c(away.get("name")), "away-note", small=True)
        elif home and title.casefold() == _c(home.get("name")).casefold():
            identity = _logo(home.get("logo"), _c(home.get("name")), "home-note", small=True)
        out.append(f'<div class="v19-item"><b>{identity}{escape(title)}</b><span>{escape(value)}</span></div>')
    return "".join(out)


def _matchup(payload: Mapping[str, Any]) -> str:
    snapshot, drivers = _module(payload, "selection_snapshot"), _module(payload, "drivers")
    away, home = _team(snapshot, "away"), _team(snapshot, "home")
    items = [r for r in drivers.get("items") or [] if isinstance(r, Mapping)]
    if items:
        body = '<div class="v19-compare-head"><span>METRIC</span>' + f'<span class="v19-side">{_logo(away["logo"], away["name"], "away-mini", small=True)} {escape(away["name"])}</span><span class="v19-side home">{escape(home["name"])} {_logo(home["logo"], home["name"], "home-mini", small=True)}</span></div>'
        for item in items:
            body += f'<div class="v19-compare-row"><b>{escape(_c(item.get("title")) or "Verified metric")}</b><span class="v19-teamvalue">{_logo(away["logo"], away["name"], "away-stat", small=True)} {_num(item.get("away"))}</span><span class="v19-teamvalue home">{_num(item.get("home"))} {_logo(home["logo"], home["name"], "home-stat", small=True)}</span></div>'
    else:
        body = _semantic(drivers, "No Qualifying Games")
    recent = _module_list(_module(payload, "recent_form"), "No Qualifying Games", payload=payload)
    history = _module_list(_module(payload, "history"), "No Previous Meetings", payload=payload)
    environment = _module_list(_module(payload, "game_environment"), "Pregame environment verification in progress.", payload=payload)
    return f'<section class="v19-card"><div class="v19-kicker">MATCHUP INTELLIGENCE</div><h2>MATCHUP INTELLIGENCE</h2>{body}<div class="v19-three" style="margin-top:9px"><div class="v19-mini"><h3>RECENT FORM</h3>{recent}</div><div class="v19-mini"><h3>MATCHUP HISTORY</h3>{history}</div><div class="v19-mini"><h3>GAME ENVIRONMENT</h3>{environment}</div></div></section>'


def _why_risk_flip(payload: Mapping[str, Any]) -> str:
    snapshot, drivers = _module(payload, "selection_snapshot"), _module(payload, "drivers")
    away, home = _team(snapshot, "away"), _team(snapshot, "home")
    why: list[str] = []
    for row in [r for r in drivers.get("items") or [] if isinstance(r, Mapping)][:6]:
        value = _c(row.get("value"))
        rendered = escape(value) if value else f'{_logo(away["logo"], away["name"], "away-why", small=True)} {escape(away["name"])} {escape(_num(row.get("away")))} • {_logo(home["logo"], home["name"], "home-why", small=True)} {escape(home["name"])} {escape(_num(row.get("home")))}'
        why.append(f'<div class="v19-item"><b>{escape(_c(row.get("title")) or "Verified driver")}</b><span>{rendered}</span></div>')
    why_body = "".join(why) or _semantic(drivers, "Verified decision drivers are still being enriched.")
    risks = _module_list(_module(payload, "risks"), "No additional verified risk flags", payload=payload)
    flips = _module_list(_module(payload, "flip_conditions"), "No verified flip condition has been calculated yet.", payload=payload)
    return f'<section class="v19-card v19-wide"><div class="v19-kicker">WHY / RISKS / FLIP CONDITIONS</div><h2>WHY / RISKS / FLIP CONDITIONS</h2><div class="v19-three"><div class="v19-mini"><h3>WHY THIS PICK</h3>{why_body}</div><div class="v19-mini"><h3>WHAT COULD GO WRONG</h3>{risks}</div><div class="v19-mini"><h3>WHAT WOULD FLIP THE PICK</h3>{flips}</div></div></section>'


def _freshness(payload: Mapping[str, Any]) -> str:
    snapshot, sources = _module(payload, "selection_snapshot"), _module(payload, "sources")
    modules = sources.get("modules") if isinstance(sources.get("modules"), Mapping) else {}
    chips = [f'<span class="v19-chip">MARKET {_time(snapshot.get("market_timestamp"))}</span>', f'<span class="v19-chip">API {_time(payload.get("generated_at_utc"))}</span>']
    for key in ("market_board", "projection", "history", "game_environment"):
        if key in modules:
            chips.append(f'<span class="v19-chip">{escape(key.replace("_", " ").upper())}: {escape(_c(modules[key]) or "Pending verification")}</span>')
    return '<div class="v19-fresh">' + "".join(chips) + '</div>'


def _audit(payload: Mapping[str, Any]) -> str:
    sources = _module(payload, "sources")
    modules = sources.get("modules") if isinstance(sources.get("modules"), Mapping) else {}
    rows = "".join(f'<div class="v19-item"><b>{escape(str(k).replace("_", " ").upper())}</b><span>{escape(_c(v) or "Pending verification")}</span></div>' for k, v in modules.items())
    rows = rows or _semantic(sources, "Source audit is being verified.")
    return f'<section class="v19-card v19-wide"><details class="v19-audit"><summary>DATA INTEGRITY</summary><div style="margin-top:8px"><div class="v19-meta">Kyre Sports API owns application delivery, identity, fallback, normalization, freshness, and semantic empty states.</div>{rows}</div></details></section>'


def render_page2_html(payload: Mapping[str, Any]) -> str:
    return f'<section data-testid="cfb-top-picks-page2-v3-root" data-page-marker="{PAGE_MARKER}"><div class="v19-shell">{_hero(payload)}{_freshness(payload)}<div class="v19-grid">{_market(payload)}{_projection(payload)}{_matchup(payload)}{_why_risk_flip(payload)}{_audit(payload)}</div><div class="v19-foot">PAGE 2 • MODEL OUTPUTS OWNED BY KYRE SPORTS API • EXACT-BOOK MARKET CONTEXT • NO FABRICATED VALUES</div></div></section>'


def _qp(st: Any, name: str) -> str:
    try:
        value = st.query_params.get(name)
    except Exception:
        value = None
    if isinstance(value, list):
        value = value[0] if value else None
    return _c(value)


def render_cfb_hub(_market_name: str = "Top Picks") -> None:
    import streamlit as st
    import cfb_top_picks_page_v15 as page1
    import cfb_top_picks_page_v16 as loader

    page1._handoff = _page1_handoff
    candidate_id = _qp(st, "top_pick_id")
    if not candidate_id:
        page1.render_cfb_hub(_market_name)
        return
    kind, date_ = _qp(st, "top_pick_kind"), _qp(st, "top_pick_date")
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        payload = loader._load_page2(candidate_id, kind, date_)
    except Exception as exc:
        st.error(f"Top Picks analysis is temporarily unable to verify this selection ({type(exc).__name__}).")
        return
    snapshot = payload.get("selection_snapshot") if isinstance(payload.get("selection_snapshot"), Mapping) else {}
    st.markdown(f'<a class="v19-back" href="{escape(_back_href(snapshot), quote=True)}">← Back to Top Picks</a>', unsafe_allow_html=True)
    st.markdown(render_page2_html(payload), unsafe_allow_html=True)


__all__ = ["MODEL_VERSION", "PAGE_MARKER", "_back_href", "_page1_handoff", "render_page2_html", "render_cfb_hub"]
