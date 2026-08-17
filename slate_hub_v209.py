"""V20.9 MLB Slate Command Center — quote freshness protection.

Builds on V20.8 without changing the independent projection engine. V20.9
classifies provider quote age as FRESH (<60s), AGING (60-180s), STALE (>180s)
or UNKNOWN. Stale market signals remain visible on individual matchup cards for
context, but are automatically excluded from the whole-slate Best ML / Run Line
/ Total summary rankings. This prevents an old price from sitting at #1 after
the market has moved.
"""

from html import escape

import streamlit as st

import slate_hub_v206 as base206
import slate_hub_v207 as base207
import slate_hub_v208 as base208

MODEL_VERSION = "V20.9"

V209_CSS = r"""
<style>
.sl-fresh-legend{display:flex;gap:7px;align-items:center;flex-wrap:wrap;border:1px solid #23435f;background:#081725;border-radius:12px;padding:8px 10px;margin:6px 0 10px;color:#91a8c0;font-size:.61rem;line-height:1.4}.sl-fresh-legend b{color:#dcecff}.sl-fresh-pill{display:inline-flex;align-items:center;border-radius:999px;padding:3px 7px;font-size:.53rem;font-weight:950;letter-spacing:.04em}.sl-fresh-pill.fresh{background:#0a3a2a;color:#76efb8;border:1px solid #176448}.sl-fresh-pill.aging{background:#45370c;color:#ffe17b;border:1px solid #725a1c}.sl-fresh-pill.stale{background:#43191d;color:#ff9ca4;border:1px solid #793039}.sl-fresh-pill.unknown{background:#172638;color:#aec2d6;border:1px solid #30465d}
.sl-fresh-state{display:inline-flex;align-items:center;border-radius:999px;padding:2px 6px;margin-left:4px;font-size:.50rem;font-weight:950;letter-spacing:.04em;vertical-align:middle}.sl-fresh-state.fresh{background:#0a3a2a;color:#76efb8}.sl-fresh-state.aging{background:#45370c;color:#ffe17b}.sl-fresh-state.stale{background:#43191d;color:#ff9ca4}.sl-fresh-state.unknown{background:#172638;color:#aec2d6}.sl-edge.stale-quote{border-color:#6d2c34;background:linear-gradient(145deg,#251015,#081723);opacity:.88}.sl-edge.stale-quote .sl-edge-main{color:#ffadb4}.sl-summary-card.aging-quote{box-shadow:inset 0 0 0 1px rgba(255,218,107,.16)}.sl-stale-note{border:1px solid #57313a;background:#1c1015;border-radius:11px;padding:7px 9px;color:#d7a2a7;font-size:.58rem;margin-top:7px}.sl-stale-note b{color:#ffb2b8}
</style>
"""

FRESH_LEGEND = (
    '<div class="sl-fresh-legend"><b>📡 Quote freshness protection</b>'
    '<span class="sl-fresh-pill fresh">🟢 FRESH &lt;60s</span>'
    '<span class="sl-fresh-pill aging">🟡 AGING 1–3m</span>'
    '<span class="sl-fresh-pill stale">🔴 STALE &gt;3m</span>'
    '<span>Stale prices stay visible on game cards but are excluded from Slate Summary rankings.</span></div>'
)


def _freshness_state(item):
    if not item:
        return "unknown", "UNKNOWN"
    age = item.get("age_seconds")
    try:
        age = float(age)
    except Exception:
        return "unknown", "UNKNOWN"
    if age < 60:
        return "fresh", "FRESH"
    if age <= 180:
        return "aging", "AGING"
    return "stale", "STALE"


def _freshness_badge(item):
    css, label = _freshness_state(item)
    icon = {"fresh": "🟢", "aging": "🟡", "stale": "🔴", "unknown": "⚪"}[css]
    return f'<span class="sl-fresh-state {css}">{icon} {label}</span>'


def _edge_card_v209(title, item):
    if not item:
        return base208._edge_card_v208(title, item)

    fresh_css, fresh_label = _freshness_state(item)
    edge = float(item.get("edge", 0) or 0)
    grade_css, grade = base206._edge_grade(edge)
    if fresh_css == "stale":
        grade_css = "pass stale-quote"
        grade = "STALE • RECHECK"

    nv = item.get("no_vig_edge")
    raw = float(item.get("listed_edge", 0) or 0)
    nv_prob = item.get("no_vig_prob")
    hold = item.get("hold")
    model_p = float(item.get("model_prob", 0) or 0) * 100
    book = escape(str(item.get("book") or "Sportsbook"))
    primary = float(nv if nv is not None else raw) * 100
    nv_line = f'<span class="nv">No-vig {float(nv)*100:+.1f} pts</span>' if nv is not None else '<span class="nv">No-vig unavailable</span>'
    fair_market = f'{float(nv_prob)*100:.1f}%' if nv_prob is not None else "—"
    hold_txt = f'{float(hold)*100:.1f}%' if hold is not None else "—"
    stale_note = (
        '<div class="sl-stale-note"><b>Do not rank this price:</b> provider quote age is over 3 minutes. Refresh the slate for a current market check.</div>'
        if fresh_css == "stale" else ""
    )
    return (
        f'<div class="sl-edge {grade_css}">'
        f'<div class="sl-edge-top"><span class="sl-edge-market">{escape(title)} {_freshness_badge(item)}</span><span class="sl-edge-grade">{escape(grade)}</span></div>'
        f'<div class="sl-edge-pick">{escape(str(item.get("label") or "—"))}</div>'
        f'<div class="sl-edge-main">{primary:+.1f} pts</div>'
        f'<div class="sl-edge-detail">Model <b>{model_p:.1f}%</b> • Fair <b>{escape(str(item.get("fair") or "—"))}</b><br>{book} <b>{base206._fmt_price(item.get("market_price"))}</b></div>'
        f'<div class="sl-edge-cal">{nv_line} • <span class="listed">Listed {raw*100:+.1f} pts</span><br>No-vig market <b>{fair_market}</b> • book hold <b>{hold_txt}</b></div>'
        f'<div class="sl-fresh">📡 <b>{escape(base208._fresh_text(item))}</b> {_freshness_badge(item)}</div>'
        f'{stale_note}</div>'
    )


def _summary_entries_v209(rows, intel, snaps):
    buckets = {"ml": [], "rl": [], "total": []}
    confidence = []
    stale_counts = {"ml": 0, "rl": 0, "total": 0}

    for row in rows:
        try:
            pk = int(row.get("game_pk"))
        except Exception:
            continue
        i = intel.get(pk)
        if not i:
            continue
        game = f'{row.get("away_team","Away")} @ {row.get("home_team","Home")}'
        confidence.append({"game": game, "intel": i})
        comp = base208._model_market_v208(i, snaps.get(pk), row)
        if not comp:
            continue
        for market in ("ml", "rl", "total"):
            item = comp.get(market)
            if not item:
                continue
            state, _ = _freshness_state(item)
            if state == "stale":
                stale_counts[market] += 1
                continue
            buckets[market].append({"game": game, "item": item})

    def strongest(items):
        if not items:
            return None
        known = [x for x in items if _freshness_state(x["item"])[0] != "unknown"]
        pool = known or items
        return max(pool, key=lambda x: float((x.get("item") or {}).get("edge", -99)))

    def conf_key(x):
        i = x["intel"]
        return (int(i.get("data_score", 0) or 0), abs(float(i.get("favorite_prob", .5) or .5) - .5))

    return {
        "ml": strongest(buckets["ml"]),
        "rl": strongest(buckets["rl"]),
        "total": strongest(buckets["total"]),
        "confidence": max(confidence, key=conf_key) if confidence else None,
        "stale_counts": stale_counts,
    }


def _summary_edge_card_v209(title, entry):
    if not entry:
        return (
            '<div class="sl-summary-card pass">'
            f'<div class="sl-summary-label">{escape(title)} • NO FRESH SIGNAL</div>'
            '<div class="sl-summary-pick">No eligible current quote</div>'
            '<div class="sl-summary-edge">—</div>'
            '<div class="sl-summary-game">Any quote older than 3 minutes is automatically excluded from this ranking.</div>'
            '</div>'
        )
    item = entry["item"]
    edge = float(item.get("edge", 0) or 0)
    css, grade = base206._edge_grade(edge)
    state, _ = _freshness_state(item)
    extra_css = " aging-quote" if state == "aging" else ""
    game = entry["game"]
    nv = item.get("no_vig_edge")
    raw = float(item.get("listed_edge", 0) or 0)
    primary = float(nv if nv is not None else raw)
    nv_text = f'No-vig <span class="nv">{float(nv)*100:+.1f}</span>' if nv is not None else 'No-vig unavailable'
    return (
        f'<div class="sl-summary-card {css}{extra_css}">'
        f'<div class="sl-summary-label">{escape(title)} • {escape(grade)} {_freshness_badge(item)}</div>'
        f'<div class="sl-summary-pick">{escape(str(item.get("label") or "—"))}</div>'
        f'<div class="sl-summary-edge">{primary*100:+.1f} pts</div>'
        f'<div class="sl-summary-game"><b>{escape(game)}</b><br>Model {float(item.get("model_prob",0) or 0)*100:.1f}% • {escape(str(item.get("book") or "Book"))} {base206._fmt_price(item.get("market_price"))}</div>'
        f'<div class="sl-summary-cal">{nv_text} • Listed <span class="raw">{raw*100:+.1f}</span></div>'
        f'<div class="sl-summary-fresh">📡 {escape(base208._fresh_text(item))} {_freshness_badge(item)}</div>'
        '</div>'
    )


def _render_summary_v209(rows, intel, snaps):
    if not intel:
        st.markdown(
            '<div class="sl-summary-lock">⚡ <b>Slate Summary:</b> run <b>BUILD V20.9 MODEL + MARKET INTELLIGENCE</b> to unlock freshness-protected, no-vig calibrated slate rankings.</div>',
            unsafe_allow_html=True,
        )
        return
    entries = _summary_entries_v209(rows, intel, snaps)
    stale = entries.get("stale_counts") or {}
    hidden = int(stale.get("ml", 0)) + int(stale.get("rl", 0)) + int(stale.get("total", 0))
    hidden_note = (
        f'<div class="sl-stale-note">🔴 <b>{hidden} stale market signal(s) excluded</b> from the Best ML / Run Line / Total rankings because the provider quote was over 3 minutes old.</div>'
        if hidden else ""
    )
    html = (
        '<div class="sl-summary-wrap"><div class="sl-summary-head"><b>⚡ V20.9 Slate Summary</b><span>no-vig calibrated • freshness protected</span></div>'
        '<div class="sl-summary-grid">'
        + _summary_edge_card_v209("Best ML edge", entries.get("ml"))
        + _summary_edge_card_v209("Best Run Line edge", entries.get("rl"))
        + _summary_edge_card_v209("Best Total edge", entries.get("total"))
        + base207._confidence_card(entries.get("confidence"))
        + '</div>' + hidden_note + '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_slate_hub(games_df, section_header, status_info, team_logo, h):
    """Render V20.8 with V20.9 freshness protections patched into its UI."""
    st.markdown(V209_CSS, unsafe_allow_html=True)

    # V20.8's render function is stable and already owns all data/model logic.
    # Patch only presentation/ranking hooks, then restore them immediately.
    old_edge = base208._edge_card_v208
    old_summary_entries = base208._summary_entries
    old_summary_edge = base208._summary_edge_card
    old_summary_render = base208._render_summary
    old_markdown = st.markdown
    old_caption = st.caption
    old_button = st.button

    def markdown_v209(body, *args, **kwargs):
        if isinstance(body, str):
            body = body.replace("V20.8", "V20.9")
        return old_markdown(body, *args, **kwargs)

    def caption_v209(body, *args, **kwargs):
        if isinstance(body, str):
            body = body.replace("V20.8", "V20.9")
        result = old_caption(body, *args, **kwargs)
        if isinstance(body, str) and "Odds connected permanently" in body:
            old_markdown(FRESH_LEGEND, unsafe_allow_html=True)
        return result

    def button_v209(label, *args, **kwargs):
        if isinstance(label, str):
            label = label.replace("V20.8", "V20.9")
        return old_button(label, *args, **kwargs)

    try:
        base208._edge_card_v208 = _edge_card_v209
        base208._summary_entries = _summary_entries_v209
        base208._summary_edge_card = _summary_edge_card_v209
        base208._render_summary = _render_summary_v209
        st.markdown = markdown_v209
        st.caption = caption_v209
        st.button = button_v209
        return base208.render_slate_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        base208._edge_card_v208 = old_edge
        base208._summary_entries = old_summary_entries
        base208._summary_edge_card = old_summary_edge
        base208._render_summary = old_summary_render
        st.markdown = old_markdown
        st.caption = old_caption
        st.button = old_button
