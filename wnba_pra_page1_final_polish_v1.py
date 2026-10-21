"""Final presentation polish for WNBA PRA Page 1.

Composes over the frozen S-tier renderer. No network calls, market routing,
probability math, projection math, or selection logic are introduced here.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st
import wnba_pra_page1_stier_v1 as base

_OVERRIDES = """
<style>
.p1-meta{font-size:10px!important;line-height:1.45}.p1-book{font-size:10px!important;line-height:1.5}
.p1-m span{font-size:8px!important}.p1-m b{font-size:12px!important}.p1-mini span{font-size:8px!important}.p1-mini b{font-size:10px!important}
.p1-foot{font-size:9px!important;color:#86a3b5!important;line-height:1.55}.p1-pill{font-size:9px!important}.p1-topmeta{font-size:10px!important}.p1-rank{font-size:9px!important}
.p1-face,.p1-logo{position:relative}.p1-face span,.p1-logo span{position:relative;z-index:1}.p1-face img,.p1-logo img{position:absolute;inset:0;z-index:2;width:100%;height:100%;background:#0e2130}.p1-face img{object-fit:cover}.p1-logo img{object-fit:contain}
.p1-final-premium{border:1px solid #3b7f63;border-radius:18px;background:radial-gradient(circle at 88% 8%,rgba(45,212,191,.13),transparent 34%),linear-gradient(145deg,#071813,#0b241b);padding:15px;margin:9px 0;box-shadow:0 14px 36px #0005}
.p1-final-eye{font-size:9px;font-weight:1000;letter-spacing:.13em;color:#6ce9b1;text-transform:uppercase}.p1-final-main{display:flex;align-items:center;gap:10px;margin-top:8px}.p1-final-title{font-size:18px;font-weight:1000;color:#f2fff9}.p1-final-pick{font-size:14px;font-weight:950;color:#79efba;margin-top:2px}.p1-final-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:10px}.p1-final-metric{border:1px solid #285844;border-radius:10px;padding:8px;background:#071710}.p1-final-metric span{display:block;font-size:8px;color:#7ca493;text-transform:uppercase;font-weight:900}.p1-final-metric b{display:block;font-size:12px;color:#e5fff2;margin-top:2px}
@media(max-width:700px){.p1-final-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _metric_pct(value: Any) -> str:
    try:
        number = float(value)
        return f"{number * 100.0:.1f}%" if math.isfinite(number) else "—"
    except (TypeError, ValueError):
        return "—"


def _face(row: Mapping[str, Any]) -> str:
    initials = escape(base._initials(row.get("player_name")))
    url = str(row.get("headshot_url") or "").strip()
    image = (
        f'<img src="{escape(url, quote=True)}" alt="{escape(str(row.get("player_name") or "player"), quote=True)} headshot" '
        'loading="lazy" decoding="async" onerror="this.style.display=\'none\'">'
        if url else ""
    )
    return f'<div class="p1-face"><span>{initials}</span>{image}</div>'


def _logo(row: Mapping[str, Any]) -> str:
    initials = escape(base._initials(row.get("team")))
    url = str(row.get("team_logo_url") or "").strip()
    image = (
        f'<img src="{escape(url, quote=True)}" alt="{escape(str(row.get("team") or "team"), quote=True)} logo" '
        'loading="lazy" decoding="async" onerror="this.style.display=\'none\'">'
        if url else ""
    )
    return f'<div class="p1-logo"><span>{initials}</span>{image}</div>'


def _line_move(row: Mapping[str, Any]) -> str:
    try:
        move = float(row.get("line_move"))
        if math.isfinite(move):
            return f"{move:+.1f}"
    except (TypeError, ValueError):
        pass
    try:
        opening = float(row.get("line_open"))
        current = float(row.get("line"))
        if math.isfinite(opening) and math.isfinite(current):
            return f"{current - opening:+.1f}"
    except (TypeError, ValueError):
        pass
    return "—"


def _card(row: Mapping[str, Any]) -> str:
    lean = str(row.get("lean") or "REFRESHING")
    lean_class = " under" if lean == "UNDER" else ""
    edge = base._pct(abs(float(row.get("model_edge")))) if row.get("model_edge") is not None else "—"
    confidence = str(row.get("decision_tier") or ("LINE BOUND" if row.get("model_state") == "LINE_BOUND_READY" else "REFRESHING")).replace("_", " ")
    team, opponent = str(row.get("team") or "").strip(), str(row.get("opponent") or "").strip()
    meta = f"{team} vs {opponent}" if team and opponent else (team or opponent or "WNBA matchup")
    extras = [str(row.get(key) or "").strip() for key in ("availability_label", "role_label")]
    extras = [value for value in extras if value]
    if extras:
        meta += " • " + " • ".join(extras)
    trend_bits = []
    h2h = str(row.get("opponent_history") or row.get("h2h_label") or "").strip()
    move = _line_move(row)
    if h2h:
        trend_bits.append(f"<b>Opponent History:</b> {escape(h2h)}")
    if move != "—":
        trend_bits.append(f"<b>Line Move:</b> {escape(move)}")
    trend = " • ".join(trend_bits) if trend_bits else "<b>More trends in Player Analysis →</b>"
    return (
        '<div class="p1 p1-card"><div class="p1-person">' + _face(row) + _logo(row)
        + f'<div><div class="p1-name">{escape(str(row.get("player_name") or ""))}</div><div class="p1-meta">{escape(meta)}</div></div></div>'
        + f'<div class="p1-quote"><div><div class="p1-linev">{float(row.get("line") or 0):.1f} PRA</div><span class="p1-lean{lean_class}">{escape(lean)} • {base._pct(row.get("model_probability"))}</span></div>'
        + f'<div class="p1-book"><b>Current Book</b><br>{escape(str(row.get("sportsbook") or "—"))}<br>O {base._odds(row.get("over_odds"))} • U {base._odds(row.get("under_odds"))}</div></div>'
        + '<div class="p1-grid">'
        + f'<div class="p1-m"><span>Projection</span><b>{base._num(row.get("projection_pra"))} PRA</b></div><div class="p1-m"><span>Model Edge</span><b>{edge}</b></div>'
        + f'<div class="p1-m"><span>Confidence</span><b>{escape(confidence)}</b></div><div class="p1-m"><span>Model State</span><b>{escape(str(row.get("model_state") or "REFRESHING").replace("_", " "))}</b></div></div>'
        + '<div class="p1-strip">'
        + f'<div class="p1-mini"><span>L5</span><b>{_metric_pct(row.get("l5_hit_rate"))}</b></div><div class="p1-mini"><span>L10</span><b>{_metric_pct(row.get("l10_hit_rate"))}</b></div><div class="p1-mini"><span>Season</span><b>{_metric_pct(row.get("season_hit_rate"))}</b></div></div>'
        + f'<div class="p1-foot">{trend}</div></div>'
    )


def _final_pick_html(card: Mapping[str, Any], quote: Mapping[str, Any], *, rank: int) -> str:
    player = str(card.get("player_name") or card.get("player") or quote.get("player_name") or "").strip()
    try:
        line = float(card.get("line"))
    except (TypeError, ValueError):
        line = float(quote.get("line") or 0.0)
    side = str(card.get("side") or quote.get("lean") or "over").upper()
    price = quote.get("over_odds") if side == "OVER" else quote.get("under_odds")
    return (
        '<div class="p1 p1-final-premium"><div class="p1-final-eye">KYRE MODEL — TOP PRA PICK</div><div class="p1-final-main">'
        + _face(quote) + _logo(quote)
        + f'<div><div class="p1-final-title">#{int(rank)} {escape(player)}</div><div class="p1-final-pick">{escape(side)} {line:.1f} PRA</div></div></div>'
        + '<div class="p1-final-grid">'
        + f'<div class="p1-final-metric"><span>Model Probability</span><b>{base._pct(quote.get("model_probability"))}</b></div>'
        + f'<div class="p1-final-metric"><span>Projection</span><b>{base._num(quote.get("projection_pra"))} PRA</b></div>'
        + f'<div class="p1-final-metric"><span>Model Edge</span><b>{base._pct(abs(float(quote.get("model_edge") or 0)))}</b></div>'
        + f'<div class="p1-final-metric"><span>Best Price</span><b>{escape(str(quote.get("sportsbook") or "—"))} {base._odds(price)}</b></div></div></div>'
    )


def render_page_snapshot(payload: Mapping[str, Any], **kwargs: Any) -> None:
    original_css, original_card, original_face, original_logo = base._CSS, base._card, base._face, base._logo
    original_markdown, original_info = base.st.markdown, base.st.info
    def markdown_proxy(body: Any, *args: Any, **kw: Any):
        if str(body).strip() == "### 🏆 Final PRA Card":
            return None
        return original_markdown(body, *args, **kw)
    def info_proxy(body: Any, *args: Any, **kw: Any):
        if str(body).startswith("No market-qualified PRA selection"):
            return None
        return original_info(body, *args, **kw)
    try:
        base._CSS = base._CSS + _OVERRIDES
        base._card, base._face, base._logo = _card, _face, _logo
        base.st.markdown, base.st.info = markdown_proxy, info_proxy
        shell = dict(payload)
        shell["final_card"] = []
        base.render_page_snapshot(shell, **kwargs)
    finally:
        base._CSS, base._card, base._face, base._logo = original_css, original_card, original_face, original_logo
        base.st.markdown, base.st.info = original_markdown, original_info

    st.markdown("### 🏆 Final PRA Card")
    rows = base.build_player_board_rows(payload)
    lookup = {(row["player_name"], row["line"]): row for row in rows}
    finals = [item for item in (payload.get("final_card") or []) if isinstance(item, Mapping)]
    if not finals:
        st.info("No market-qualified PRA selection is certified for this state yet. No pick is being forced.")
        return
    for rank, card in enumerate(finals[:5], 1):
        player = str(card.get("player_name") or card.get("player") or "")
        try:
            line = float(card.get("line"))
        except (TypeError, ValueError):
            continue
        quote = lookup.get((player, line), {})
        st.markdown(_OVERRIDES + _final_pick_html(card, quote, rank=rank), unsafe_allow_html=True)
        if st.button("Analyze Pick", key=f"p1-final-analyze-{rank}-{player}-{line}", use_container_width=True):
            base._handoff(quote, payload)


__all__ = ["render_page_snapshot", "_card", "_face", "_logo", "_final_pick_html", "_OVERRIDES"]
