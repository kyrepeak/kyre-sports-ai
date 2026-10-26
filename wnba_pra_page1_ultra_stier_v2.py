"""Ultra-clean MONSTER WNBA PRA Page 1 presentation successor.

Presentation only. Reads the already-certified Page 1 snapshot through the
preserved V1 helpers. No provider calls, model/projection math, market routing,
qualification logic, sportsbook averaging, or background work lives here.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import wnba_pra_page1_stier_v1 as base
import wnba_pra_page1_final_polish_v1 as polish

PAGE1_HANDOFF_KEY = base.PAGE1_HANDOFF_KEY
build_player_board_rows = base.build_player_board_rows
rank_top_edges = base.rank_top_edges
_handoff = base._handoff

_CSS = r"""
<style>
.p1v2{--ice:#8fe8ff;--cyan:#35cfff;--green:#61edaa;--purple:#c8b4ff;--text:#eef9ff;--muted:#7f9aad;--line:#23465e;--panel:#07131c;--panel2:#091923}
.p1v2-hero{border:1px solid #28556f;border-radius:18px;padding:15px 18px;background:radial-gradient(circle at 86% 0,rgba(36,157,201,.16),transparent 35%),linear-gradient(145deg,#07131c,#091923);margin:6px 0 10px}
.p1v2-kicker{font-size:9px;letter-spacing:.17em;font-weight:900;color:#67c7ea}.p1v2-title{font-size:30px;line-height:1;font-weight:1000;color:#f5fbff;margin-top:4px}.p1v2-title b{color:var(--cyan)}.p1v2-sub{font-size:10px;color:#8ba7b8;margin-top:7px}.p1v2-pills{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.p1v2-pill{border:1px solid #315c74;border-radius:999px;padding:4px 8px;font-size:8px;color:#a9c7d7;background:#081722;font-weight:850}.p1v2-pill.good{border-color:#277257;color:#6aefb3}
.p1v2-summary{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--line);border-radius:15px;overflow:hidden;background:var(--panel);margin:10px 0 14px}.p1v2-stat{padding:10px 12px;border-right:1px solid #17364a;min-width:0}.p1v2-stat:last-child{border-right:0}.p1v2-stat span{display:block;font-size:7px;text-transform:uppercase;letter-spacing:.09em;color:#68889e;font-weight:900}.p1v2-stat b{display:block;font-size:17px;color:#e9f7ff;margin-top:2px;white-space:nowrap}.p1v2-stat b.good{color:var(--green)}.p1v2-moves{font-size:12px!important;color:#dff4ff!important}.p1v2-moves .up{color:#65ddff}.p1v2-moves .down{color:#ff7f9c}.p1v2-moves .flat{color:#9caeb9}
.p1v2-section{display:flex;align-items:flex-end;justify-content:space-between;margin:14px 0 7px}.p1v2-section h3{margin:0;color:#f3f9fd;font-size:22px}.p1v2-section p{margin:2px 0 0;font-size:9px;color:#7793a5}
.p1v2-leaderboard{border:1px solid #28526a;border-radius:15px;overflow:hidden;background:linear-gradient(145deg,#07131c,#091923);margin-bottom:16px}.p1v2-leader-head,.p1v2-leader-row{display:grid;grid-template-columns:40px 1.5fr .9fr .75fr .7fr .75fr;align-items:center;gap:8px;padding:9px 12px}.p1v2-leader-head{background:#091c29;border-bottom:1px solid #23465e;color:#6f91a8;font-size:7px;font-weight:900;text-transform:uppercase;letter-spacing:.07em}.p1v2-leader-row{border-bottom:1px solid #17384c;color:#dfeef6;font-size:10px}.p1v2-leader-row:last-child{border-bottom:0}.p1v2-rank{font-weight:1000;color:#9bdfff}.p1v2-leader-name{font-size:12px;font-weight:950;color:#f2f8fc}.p1v2-pick{color:#cabaff;font-weight:900}.p1v2-edge{color:var(--green);font-weight:1000;font-size:13px}.p1v2-prob{color:var(--ice);font-weight:1000}
.p1v2-card{border:1px solid #28526a;border-radius:15px;background:linear-gradient(145deg,#07131c,#091923);padding:11px;min-height:272px}.p1v2-person{display:flex;gap:8px;align-items:center}.p1v2-face{width:44px;height:44px;border-radius:50%;overflow:hidden;border:1px solid #3f7692;background:#123047;display:flex;align-items:center;justify-content:center;font-weight:1000;color:#a9e8ff}.p1v2-face img{width:100%;height:100%;object-fit:cover}.p1v2-logo{width:22px;height:22px;border-radius:7px;border:1px solid #315a70;background:#0c2130;display:flex;align-items:center;justify-content:center;overflow:hidden;font-size:7px;font-weight:900;color:#92b6c9}.p1v2-logo img{width:100%;height:100%;object-fit:contain}.p1v2-name{font-size:14px;font-weight:1000;color:#f4fbff}.p1v2-match{font-size:8px;color:#7697aa;margin-top:2px}.p1v2-pickline{display:flex;justify-content:space-between;gap:8px;align-items:flex-end;margin:10px 0 8px}.p1v2-side{font-size:18px;font-weight:1000;color:#c8b7ff}.p1v2-prob-big{font-size:22px;font-weight:1000;color:var(--ice);text-align:right}.p1v2-prob-big span{display:block;font-size:7px;color:#6f8fa3;text-transform:uppercase;letter-spacing:.08em}.p1v2-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.p1v2-metric{border:1px solid #1d4056;border-radius:9px;padding:7px;background:#07141e}.p1v2-metric span{display:block;font-size:7px;color:#67879b;text-transform:uppercase;font-weight:900}.p1v2-metric b{display:block;font-size:12px;color:#e6f6ff;margin-top:2px}.p1v2-metric b.good{color:var(--green)}.p1v2-trends{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:6px}.p1v2-trend{border:1px solid #1b3d52;border-radius:8px;padding:5px;text-align:center}.p1v2-trend span{display:block;font-size:7px;color:#668599}.p1v2-trend b{font-size:9px;color:#dceff8}.p1v2-market{display:flex;justify-content:space-between;align-items:center;border-top:1px solid #193a4e;margin-top:7px;padding-top:7px;font-size:8px;color:#7d9bad}.p1v2-market b{color:#dcecf5}.p1v2-move.down{color:#ff829d}.p1v2-move.up{color:#65ddff}.p1v2-cta{margin-top:7px;border:1px solid #23698c;border-radius:8px;padding:7px;text-align:center;color:#8edfff;font-size:9px;font-weight:900;background:#071b28}
.p1v2-final{border:1px solid #2d805d;border-radius:17px;background:radial-gradient(circle at 90% 0,rgba(47,220,156,.13),transparent 35%),linear-gradient(145deg,#071711,#0b2118);padding:14px;margin:15px 0}.p1v2-final-eye{font-size:9px;color:#6ce9b1;font-weight:1000;letter-spacing:.13em}.p1v2-final-title{font-size:19px;color:#f2fff8;font-weight:1000;margin-top:4px}.p1v2-final-pick{font-size:16px;color:#7cf0b9;font-weight:1000}.p1v2-final-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:9px}.p1v2-final-m{border:1px solid #295943;border-radius:9px;padding:7px}.p1v2-final-m span{display:block;font-size:7px;color:#7fa592;text-transform:uppercase;font-weight:900}.p1v2-final-m b{display:block;font-size:11px;color:#e8fff3;margin-top:2px}
@media(max-width:900px){.p1v2-summary{grid-template-columns:repeat(3,1fr)}.p1v2-stat:nth-child(3){border-right:0}.p1v2-leader-head{display:none}.p1v2-leader-row{grid-template-columns:28px 1.5fr .85fr .65fr}.p1v2-leader-row .desktop{display:none}.p1v2-final-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.p1v2-summary{grid-template-columns:repeat(2,1fr)}.p1v2-stat:nth-child(odd){border-right:1px solid #17364a}.p1v2-stat:nth-child(even){border-right:0}.p1v2-card{min-height:0}}
</style>
"""


def _pct(value: Any, *, digits: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return "—"
    return f"{number * 100:.{digits}f}%" if math.isfinite(number) else "—"


def _num(value: Any, *, digits: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return "—"
    return f"{number:.{digits}f}" if math.isfinite(number) else "—"


def _odds(value: Any) -> str:
    try:
        number = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return "—"
    return f"+{number}" if number > 0 else str(number)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _initials(value: Any) -> str:
    parts = [part for part in str(value or "").split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "WN"


def _face(row: Mapping[str, Any]) -> str:
    url = str(row.get("headshot_url") or "").strip()
    fallback = escape(_initials(row.get("player_name")))
    if not url:
        return f'<div class="p1v2-face">{fallback}</div>'
    return f'<div class="p1v2-face"><img src="{escape(url, quote=True)}" alt="player" loading="lazy" decoding="async" onerror="this.style.display=\'none\'">{fallback}</div>'


def _logo(row: Mapping[str, Any]) -> str:
    url = str(row.get("team_logo_url") or "").strip()
    fallback = escape(_initials(row.get("team")))
    if not url:
        return f'<div class="p1v2-logo">{fallback}</div>'
    return f'<div class="p1v2-logo"><img src="{escape(url, quote=True)}" alt="team" loading="lazy" decoding="async" onerror="this.style.display=\'none\'">{fallback}</div>'


def _pick_side(row: Mapping[str, Any]) -> str:
    side = str(row.get("lean") or "").strip().upper()
    return side if side in {"OVER", "UNDER"} else "REFRESHING"


def _pick_price(row: Mapping[str, Any]) -> str:
    side = _pick_side(row)
    return _odds(row.get("under_odds") if side == "UNDER" else row.get("over_odds"))


def _line_move_values(row: Mapping[str, Any]) -> tuple[float | None, float | None, float | None]:
    current = _finite(row.get("line"))
    opening = _finite(row.get("line_open"))
    move = _finite(row.get("line_move"))
    if move is None and current is not None and opening is not None:
        move = current - opening
    return opening, current, move


def _line_move_html(row: Mapping[str, Any]) -> str:
    opening, current, move = _line_move_values(row)
    if opening is None or current is None or move is None:
        return ""
    cls = "down" if move < 0 else "up" if move > 0 else ""
    arrow = "↓" if move < 0 else "↑" if move > 0 else "—"
    return f'<span class="p1v2-move {cls}">{opening:.1f} → {current:.1f} {arrow} {abs(move):.1f}</span>'


def _trend_strip_html(row: Mapping[str, Any]) -> str:
    values = (("L5", row.get("l5_hit_rate")), ("L10", row.get("l10_hit_rate")), ("Season", row.get("season_hit_rate")))
    verified = [(label, _finite(value)) for label, value in values]
    verified = [(label, value) for label, value in verified if value is not None]
    if not verified:
        return ""
    cells = "".join(f'<div class="p1v2-trend"><span>{label}</span><b>{value * 100:.0f}%</b></div>' for label, value in verified)
    return f'<div class="p1v2-trends">{cells}</div>'


def _player_card_html(row: Mapping[str, Any]) -> str:
    side = _pick_side(row)
    line = _finite(row.get("line")) or 0.0
    edge = abs(_finite(row.get("model_edge")) or 0.0)
    probability = _finite(row.get("model_probability"))
    team = str(row.get("team") or "").strip()
    opponent = str(row.get("opponent") or "").strip()
    matchup = f"{team} vs {opponent}" if team and opponent else (team or opponent or "WNBA matchup")
    move = _line_move_html(row)
    market = f'<span><b>{escape(str(row.get("sportsbook") or "—"))}</b> {_pick_price(row)}</span>'
    if move:
        market += move
    return (
        '<div class="p1v2 p1v2-card"><div class="p1v2-person">' + _face(row) + _logo(row)
        + f'<div><div class="p1v2-name">{escape(str(row.get("player_name") or ""))}</div><div class="p1v2-match">{escape(matchup)}</div></div></div>'
        + '<div class="p1v2-pickline">'
        + f'<div class="p1v2-side">{escape(side)} {line:.1f} PRA</div>'
        + f'<div class="p1v2-prob-big">{_pct(probability)}<span>Probability</span></div></div>'
        + '<div class="p1v2-metrics">'
        + f'<div class="p1v2-metric"><span>Projection</span><b>{_num(row.get("projection_pra"))}</b></div>'
        + f'<div class="p1v2-metric"><span>Model Edge</span><b class="good">{_pct(edge)}</b></div></div>'
        + _trend_strip_html(row)
        + f'<div class="p1v2-market">{market}</div>'
        + '<div class="p1v2-cta">Analyze Player →</div></div>'
    )


def _leaderboard_html(rows: list[Mapping[str, Any]]) -> str:
    ranked = rank_top_edges([dict(row) for row in rows], 3)
    if not ranked:
        return ""
    body = []
    for rank, row in enumerate(ranked, 1):
        line = _finite(row.get("line")) or 0.0
        edge = abs(_finite(row.get("model_edge")) or 0.0)
        body.append(
            '<div class="p1v2-leader-row">'
            f'<div class="p1v2-rank">#{rank}</div>'
            f'<div class="p1v2-leader-name">{escape(str(row.get("player_name") or ""))}</div>'
            f'<div class="p1v2-pick">{escape(_pick_side(row))} {line:.1f}</div>'
            f'<div class="desktop">{_num(row.get("projection_pra"))}</div>'
            f'<div class="p1v2-edge">{_pct(edge)}</div>'
            f'<div class="p1v2-prob">{_pct(row.get("model_probability"))}</div></div>'
        )
    return (
        '<div class="p1v2 p1v2-leaderboard">'
        '<div class="p1v2-leader-head"><div>#</div><div>Player</div><div>Pick</div><div>Proj</div><div>Edge</div><div>Prob</div></div>'
        + "".join(body) + '</div>'
    )


def _summary_html(rows: list[Mapping[str, Any]], *, provider: str) -> str:
    ready = [row for row in rows if row.get("model_state") == "LINE_BOUND_READY"]
    edges = [abs(value) for row in ready if (value := _finite(row.get("model_edge"))) is not None]
    probs = [value for row in ready if (value := _finite(row.get("model_probability"))) is not None]
    up = down = flat = 0
    for row in rows:
        _opening, _current, move = _line_move_values(row)
        if move is None or abs(move) < 1e-9:
            flat += 1
        elif move > 0:
            up += 1
        else:
            down += 1
    return (
        '<div class="p1v2 p1v2-summary">'
        f'<div class="p1v2-stat"><span>Players</span><b>{len(rows)}</b></div>'
        f'<div class="p1v2-stat"><span>Model Ready</span><b>{len(ready)}/{len(rows)}</b></div>'
        f'<div class="p1v2-stat"><span>Best Edge</span><b class="good">{_pct(max(edges) if edges else None)}</b></div>'
        f'<div class="p1v2-stat"><span>Best Probability</span><b>{_pct(max(probs) if probs else None)}</b></div>'
        f'<div class="p1v2-stat"><span>Market Movement</span><b class="p1v2-moves"><span class="up">↑ {up}</span> · <span class="down">↓ {down}</span> · <span class="flat">— {flat}</span></b></div>'
        f'<div class="p1v2-stat"><span>Top Book Today</span><b>{escape(provider or "—")}</b></div></div>'
    )


def _final_section_html(finals: list[Mapping[str, Any]], rows: list[Mapping[str, Any]]) -> str:
    if not finals:
        return ""
    lookup = {(str(row.get("player_name") or ""), _finite(row.get("line"))): row for row in rows}
    cards = []
    for card in finals[:5]:
        player = str(card.get("player_name") or card.get("player") or "").strip()
        line = _finite(card.get("line"))
        if not player or line is None:
            continue
        row = lookup.get((player, line), {})
        side = str(card.get("side") or row.get("lean") or "OVER").upper()
        price = _odds(row.get("under_odds") if side == "UNDER" else row.get("over_odds"))
        edge = abs(_finite(row.get("model_edge")) or 0.0)
        cards.append(
            '<div class="p1v2 p1v2-final"><div class="p1v2-final-eye">🏆 CERTIFIED PRA PICK</div>'
            f'<div class="p1v2-final-title">{escape(player)}</div><div class="p1v2-final-pick">{escape(side)} {line:.1f} PRA</div>'
            '<div class="p1v2-final-grid">'
            f'<div class="p1v2-final-m"><span>Probability</span><b>{_pct(row.get("model_probability"))}</b></div>'
            f'<div class="p1v2-final-m"><span>Projection</span><b>{_num(row.get("projection_pra"))}</b></div>'
            f'<div class="p1v2-final-m"><span>Model Edge</span><b>{_pct(edge)}</b></div>'
            f'<div class="p1v2-final-m"><span>Best Price</span><b>{escape(str(row.get("sportsbook") or "—"))} {price}</b></div></div></div>'
        )
    return "".join(cards)


def _updated_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Updated recently"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return f"Updated {parsed.strftime('%-I:%M %p')}"
    except (TypeError, ValueError):
        return "Updated recently"


def render_page_snapshot(payload: Mapping[str, Any], **_kwargs: Any) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    rows = build_player_board_rows(payload)
    provider = str(payload.get("selected_provider") or (rows[0].get("sportsbook") if rows else "") or "—").replace("_", " ").title()
    state = str(payload.get("snapshot_state") or "MODEL_UNAVAILABLE")
    ready = state == "READY"
    updated = _updated_label(payload.get("market_capture_at"))
    st.markdown(
        '<div class="p1v2 p1v2-hero"><div class="p1v2-kicker">KYRE SPORTS • WNBA</div>'
        '<div class="p1v2-title">WNBA <b>PRA</b></div><div class="p1v2-sub">Player Props Analytics • '
        + escape(updated)
        + '</div><div class="p1v2-pills">'
        + f'<span class="p1v2-pill good">{"Markets Verified" if ready else "Market Refreshing"}</span>'
        + '<span class="p1v2-pill">Exact Sportsbook Odds</span><span class="p1v2-pill">No Averaging</span><span class="p1v2-pill">Kyre Sports API</span></div></div>',
        unsafe_allow_html=True,
    )
    if state == "MODEL_REFRESH_REQUIRED":
        st.warning("Current market line is fresh while its exact line-bound model refreshes; old-line probability is never reused.")
    elif state == "MODEL_UNAVAILABLE":
        st.warning("Market data is available while model context rebuilds. No probability is being forced.")

    st.markdown(_summary_html(rows, provider=provider), unsafe_allow_html=True)
    leaderboard = _leaderboard_html(rows)
    if leaderboard:
        st.markdown('<div class="p1v2-section"><div><h3>🏆 Top 3 Model Edges</h3><p>Best verified PRA opportunities on the current slate.</p></div></div>' + leaderboard, unsafe_allow_html=True)

    st.markdown('<div class="p1v2-section"><div><h3>Player Discovery</h3><p>Fast decision board. Full context stays one tap away.</p></div></div>', unsafe_allow_html=True)
    a, b, c = st.columns([2, 1, 1])
    search = a.text_input("Search players", placeholder="Player or team", key="wnba-pra-page1-v2-search")
    sort_by = b.selectbox("Sort by", ("Model Edge", "Probability", "Projection", "Player"), key="wnba-pra-page1-v2-sort")
    status = c.selectbox("Game Status", ("All", "Verified", "Refreshing"), key="wnba-pra-page1-v2-status")
    term = str(search or "").strip().casefold()
    filtered: list[dict[str, Any]] = []
    for row in rows:
        haystack = f"{row.get('player_name','')} {row.get('team','')} {row.get('opponent','')}".casefold()
        if term and term not in haystack:
            continue
        is_ready = row.get("model_state") == "LINE_BOUND_READY"
        if status == "Verified" and not is_ready:
            continue
        if status == "Refreshing" and is_ready:
            continue
        filtered.append(row)
    if sort_by == "Model Edge":
        filtered.sort(key=lambda row: -abs(_finite(row.get("model_edge")) or 0.0))
    elif sort_by == "Probability":
        filtered.sort(key=lambda row: -(_finite(row.get("model_probability")) or -1.0))
    elif sort_by == "Projection":
        filtered.sort(key=lambda row: -(_finite(row.get("projection_pra")) or -1.0))
    else:
        filtered.sort(key=lambda row: str(row.get("player_name") or ""))

    if not filtered:
        st.info("No Page 1 players match the current filters.")
    for start in range(0, len(filtered), 3):
        cols = st.columns(3)
        for col, row in zip(cols, filtered[start:start + 3]):
            col.markdown(_player_card_html(row), unsafe_allow_html=True)
            if col.button("Analyze Player", key=f"p1v2-analyze-{start}-{row.get('player_name')}-{row.get('line')}", use_container_width=True):
                _handoff(row, payload)

    finals = [item for item in (payload.get("final_card") or []) if isinstance(item, Mapping)]
    final_html = _final_section_html(finals, rows)
    if final_html:
        st.markdown(final_html, unsafe_allow_html=True)


__all__ = [
    "PAGE1_HANDOFF_KEY", "build_player_board_rows", "rank_top_edges", "_handoff",
    "_trend_strip_html", "_player_card_html", "_leaderboard_html", "_summary_html",
    "_final_section_html", "render_page_snapshot",
]
