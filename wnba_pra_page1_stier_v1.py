"""WNBA PRA Page 1 S-tier presentation over the certified one-read page snapshot.

Presentation only. This module makes no network calls, never averages sportsbook
quotes, never invents missing analytics, and never changes model/projection math.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

PAGE1_HANDOFF_KEY = "ks_wnba_pra_page1_handoff_v1"
NOT_VERIFIED = "Not verified on Page 1"

_CSS = """
<style>
.p1{--ice:#98e7ff;--text:#eef9ff;--muted:#7896aa;--line:#25455c;--good:#6ce9b1;--warn:#ffd371}
.p1-hero{border:1px solid #28506a;border-radius:20px;padding:17px 18px;background:radial-gradient(circle at 90% 0,#12384d 0,transparent 36%),linear-gradient(145deg,#061018,#0b1722);box-shadow:0 14px 42px #0007;margin-bottom:12px}.p1-eye{font-size:9px;letter-spacing:.17em;font-weight:900;color:#72bfdf}.p1-title{font-size:28px;font-weight:1000;color:#f4fbff;line-height:1.05;margin-top:4px}.p1-sub{font-size:10px;color:#8daabd;margin-top:7px}.p1-pills{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.p1-pill{font-size:8px;font-weight:900;border:1px solid #31536a;background:#0a1924;color:#a6c4d6;border-radius:999px;padding:4px 8px}.p1-pill.live{color:#72efb7;border-color:#347359}
.p1-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0 15px}.p1-kpi{border:1px solid #203d51;background:#08131d;border-radius:12px;padding:9px}.p1-kpi span{display:block;font-size:7px;color:#6e8ca1;text-transform:uppercase;font-weight:900;letter-spacing:.08em}.p1-kpi b{display:block;font-size:15px;color:#e9f7ff;margin-top:3px}
.p1-top{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:7px 0 16px}.p1-topcard{border:1px solid #315a73;border-radius:14px;background:linear-gradient(145deg,#091620,#0a1d2a);padding:10px}.p1-rank{font-size:8px;color:#719fba;font-weight:900}.p1-topname{font-size:14px;color:#f2fbff;font-weight:950;margin-top:2px}.p1-topmeta{font-size:9px;color:#86a5b8;margin-top:4px}.p1-edge{font-size:20px;color:#6ce9b1;font-weight:1000;margin-top:5px}
.p1-card{border:1px solid #29485f;border-radius:16px;background:linear-gradient(145deg,#07121b,#0a1721);padding:12px;min-height:326px}.p1-person{display:flex;align-items:center;gap:9px}.p1-face{width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:linear-gradient(145deg,#15384f,#0b2130);border:1px solid #3b6b87;color:#a9e9ff;font-weight:1000;font-size:13px;overflow:hidden}.p1-face img{width:100%;height:100%;object-fit:cover}.p1-logo{width:24px;height:24px;border-radius:8px;display:flex;align-items:center;justify-content:center;background:#0e2130;border:1px solid #2e5269;color:#92b8cd;font-size:7px;font-weight:1000;overflow:hidden}.p1-logo img{width:100%;height:100%;object-fit:contain}.p1-name{font-size:15px;font-weight:1000;color:#f4fbff}.p1-meta{font-size:8px;color:#7897aa;margin-top:2px}.p1-quote{display:flex;justify-content:space-between;align-items:flex-end;margin:10px 0 8px}.p1-linev{font-size:25px;font-weight:1000;color:#9ce6ff}.p1-book{font-size:8px;color:#88a6b9;text-align:right;line-height:1.45}.p1-lean{display:inline-block;margin-top:4px;border:1px solid #347158;border-radius:999px;padding:3px 7px;background:#0b211a;color:#6feab2;font-size:8px;font-weight:950}.p1-lean.under{border-color:#615782;background:#19152a;color:#cbbdff}.p1-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.p1-m{border:1px solid #1c3548;border-radius:9px;padding:7px;background:#07111a}.p1-m span{display:block;font-size:7px;color:#6b889d;text-transform:uppercase;font-weight:900}.p1-m b{display:block;font-size:11px;color:#dff4ff;margin-top:2px}.p1-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-top:7px}.p1-mini{border:1px solid #1c3548;border-radius:8px;padding:6px;text-align:center}.p1-mini span{display:block;font-size:7px;color:#6e8ba0}.p1-mini b{display:block;font-size:9px;color:#d9f0ff;margin-top:2px;line-height:1.25}.p1-foot{border-top:1px solid #193346;margin-top:8px;padding-top:7px;color:#718da0;font-size:8px;line-height:1.55}.p1-final{border:1px solid #39715a;border-radius:15px;background:linear-gradient(145deg,#081a14,#0b2119);padding:11px;margin:7px 0}.p1-final strong{color:#76edb7}.p1-final span{font-size:9px;color:#9ab7a9}
@media(max-width:900px){.p1-kpis{grid-template-columns:repeat(2,1fr)}.p1-top{grid-template-columns:1fr}.p1-card{min-height:0}}
</style>
"""


def optional_label(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else NOT_VERIFIED


def _num(value: Any, digits: int = 1) -> str:
    try:
        number = float(value)
        return f"{number:.{digits}f}" if math.isfinite(number) else "—"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        number = float(value)
        return f"{number * 100.0:.1f}%" if math.isfinite(number) else NOT_VERIFIED
    except (TypeError, ValueError):
        return NOT_VERIFIED


def _odds(value: Any) -> str:
    try:
        number = int(float(value))
        return f"+{number}" if number > 0 else str(number)
    except (TypeError, ValueError):
        return "—"


def _initials(name: Any) -> str:
    parts = [p for p in str(name or "").split() if p]
    return "".join(p[0].upper() for p in parts[:2]) or "WN"


def build_player_board_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, float, str], dict[str, Any]] = {}
    for raw in payload.get("offers") or []:
        if not isinstance(raw, Mapping) or raw.get("line") is None:
            continue
        player = str(raw.get("player_name") or "").strip()
        if not player:
            continue
        try:
            line = float(raw.get("line"))
        except (TypeError, ValueError):
            continue
        book = str(raw.get("sportsbook") or "").strip()
        key = (player, line, book)
        row = grouped.setdefault(
            key,
            {k: v for k, v in dict(raw).items() if k not in {"side", "american_odds"}}
            | {"player_name": player, "line": line, "sportsbook": book},
        )
        side = str(raw.get("side") or "").casefold()
        if side in {"over", "under"}:
            row[f"{side}_odds"] = raw.get("american_odds")
    rows = list(grouped.values())
    for row in rows:
        ready = row.get("model_state") == "LINE_BOUND_READY"
        try:
            over = float(row.get("p_over"))
            under = float(row.get("p_under"))
        except (TypeError, ValueError):
            over = under = float("nan")
        if ready and math.isfinite(over) and math.isfinite(under):
            row["lean"] = "OVER" if over >= under else "UNDER"
            row["model_probability"] = max(over, under)
        else:
            row["lean"] = "REFRESHING"
            row["model_probability"] = None
        try:
            row["model_edge"] = float(row.get("edge"))
        except (TypeError, ValueError):
            row["model_edge"] = None
    return sorted(rows, key=lambda r: str(r.get("player_name") or ""))


def rank_top_edges(rows: list[Mapping[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    ranked = []
    for raw in rows:
        row = dict(raw)
        try:
            edge = float(row.get("model_edge"))
        except (TypeError, ValueError):
            continue
        if row.get("model_state") != "LINE_BOUND_READY" or not math.isfinite(edge):
            continue
        row["_rank_edge"] = abs(edge)
        ranked.append(row)
    ranked.sort(key=lambda r: (-r["_rank_edge"], str(r.get("player_name") or "")))
    return ranked[: max(0, int(limit))]


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
    return NOT_VERIFIED


def _face(row: Mapping[str, Any]) -> str:
    url = str(row.get("headshot_url") or "").strip()
    if url:
        return f'<div class="p1-face"><img src="{escape(url)}" alt="player"></div>'
    return f'<div class="p1-face">{escape(_initials(row.get("player_name")))}</div>'


def _logo(row: Mapping[str, Any]) -> str:
    url = str(row.get("team_logo_url") or "").strip()
    if url:
        return f'<div class="p1-logo"><img src="{escape(url)}" alt="team"></div>'
    return f'<div class="p1-logo">{escape(_initials(row.get("team")))}</div>'


def _card(row: Mapping[str, Any]) -> str:
    lean = str(row.get("lean") or "REFRESHING")
    lean_class = " under" if lean == "UNDER" else ""
    role = optional_label(row.get("role_label"))
    availability = optional_label(row.get("availability_label"))
    l5 = _pct(row.get("l5_hit_rate"))
    l10 = _pct(row.get("l10_hit_rate"))
    season = _pct(row.get("season_hit_rate"))
    h2h = optional_label(row.get("opponent_history") or row.get("h2h_label"))
    edge = _pct(abs(float(row.get("model_edge")))) if row.get("model_edge") is not None else NOT_VERIFIED
    confidence = optional_label(
        row.get("decision_tier")
        or ("LINE BOUND" if row.get("model_state") == "LINE_BOUND_READY" else None)
    )
    return (
        '<div class="p1 p1-card"><div class="p1-person">'
        + _face(row)
        + _logo(row)
        + f'<div><div class="p1-name">{escape(str(row.get("player_name") or ""))}</div>'
        + f'<div class="p1-meta">{escape(optional_label(row.get("team")))} vs {escape(optional_label(row.get("opponent")))} • {escape(availability)} • {escape(role)}</div></div></div>'
        + f'<div class="p1-quote"><div><div class="p1-linev">{float(row.get("line") or 0):.1f} PRA</div>'
        + f'<span class="p1-lean{lean_class}">{escape(lean)} • {_pct(row.get("model_probability"))}</span></div>'
        + f'<div class="p1-book"><b>Current Book</b><br>{escape(optional_label(row.get("sportsbook")))}<br>O {_odds(row.get("over_odds"))} • U {_odds(row.get("under_odds"))}</div></div>'
        + '<div class="p1-grid">'
        + f'<div class="p1-m"><span>Projection</span><b>{_num(row.get("projection_pra"))} PRA</b></div>'
        + f'<div class="p1-m"><span>Model Edge</span><b>{edge}</b></div>'
        + f'<div class="p1-m"><span>Confidence</span><b>{escape(confidence)}</b></div>'
        + f'<div class="p1-m"><span>Model State</span><b>{escape(str(row.get("model_state") or "REFRESHING").replace("_", " "))}</b></div>'
        + '</div><div class="p1-strip">'
        + f'<div class="p1-mini"><span>L5</span><b>{escape(l5)}</b></div>'
        + f'<div class="p1-mini"><span>L10</span><b>{escape(l10)}</b></div>'
        + f'<div class="p1-mini"><span>Season</span><b>{escape(season)}</b></div>'
        + '</div>'
        + f'<div class="p1-foot"><b>Opponent History:</b> {escape(h2h)} • <b>Line Move:</b> {escape(_line_move(row))}<br>'
        + 'Exact provider quote • no conflicting-line averaging • optional context stays explicitly unverified</div></div>'
    )


def _handoff(row: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    handoff = {
        "schema": "wnba_pra_page1_handoff_v1",
        "date": payload.get("date"),
        "market_capture_at": payload.get("market_capture_at"),
        "player": dict(row),
    }
    st.session_state[PAGE1_HANDOFF_KEY] = handoff
    game_id = str(row.get("game_id") or "").strip()
    player_id = str(row.get("player_key") or row.get("player_id") or "").strip()
    if game_id and player_id:
        try:
            import wnba_pra_navigation_v2_step1 as navigation

            navigation.go_to_player(game_id, player_id)
            st.rerun()
            return
        except Exception:
            pass
    st.toast("Player selected. Exact Page 1 snapshot saved for analysis handoff.")


def render_page_snapshot(payload: Mapping[str, Any], **_kwargs: Any) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    state = str(payload.get("snapshot_state") or "MODEL_UNAVAILABLE")
    cache = str(payload.get("cache_state") or "MODEL_UNAVAILABLE")
    provider = str(payload.get("selected_provider") or "unavailable").replace("_", " ").title()
    ready = "Verified" if state == "READY" else "Refreshing"
    st.markdown(
        '<div class="p1 p1-hero"><div class="p1-eye">KYRE SPORTS AI • WNBA PRA • PAGE 1</div>'
        f'<div class="p1-title">PRA Analytics Board</div><div class="p1-sub">{escape(str(payload.get("date") or ""))} • Game Status: {escape(ready)} • Kyre Sports API • {escape(provider)} • {escape(cache)}</div>'
        f'<div class="p1-pills"><span class="p1-pill live">{escape(ready)}</span><span class="p1-pill">Exact sportsbook quotes</span><span class="p1-pill">No averaging</span><span class="p1-pill">{escape(optional_label(payload.get("market_capture_at")))}</span></div></div>',
        unsafe_allow_html=True,
    )
    if state == "MODEL_REFRESH_REQUIRED":
        st.warning("Live PRA line moved. Fresh quote is shown while the exact line-bound model refreshes; old-line probability is not reused.")
    elif state == "MODEL_UNAVAILABLE":
        st.warning("Fresh PRA market is available while model context rebuilds. No probability is being forced.")
    elif cache == "STALE_SAFE":
        st.info("Verified model context remains inside its safe window and refreshes after render.")

    rows = build_player_board_rows(payload)
    top = rank_top_edges(rows, 3)
    ready_count = sum(row.get("model_state") == "LINE_BOUND_READY" for row in rows)
    top_edge = abs(float(top[0]["model_edge"])) if top else None
    st.markdown(
        '<div class="p1 p1-kpis">'
        f'<div class="p1-kpi"><span>Players</span><b>{len(rows)}</b></div>'
        f'<div class="p1-kpi"><span>Model Ready</span><b>{ready_count}/{len(rows)}</b></div>'
        f'<div class="p1-kpi"><span>Top Edge</span><b>{_pct(top_edge)}</b></div>'
        f'<div class="p1-kpi"><span>Current Book</span><b>{escape(provider)}</b></div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Top 3 Model Edges")
    if top:
        cards = []
        for i, row in enumerate(top, 1):
            cards.append(
                f'<div class="p1-topcard"><div class="p1-rank">#{i} MODEL EDGE</div>'
                f'<div class="p1-topname">{escape(str(row.get("player_name") or ""))}</div>'
                f'<div class="p1-topmeta">{escape(str(row.get("lean") or ""))} {float(row.get("line") or 0):.1f} PRA • {_pct(row.get("model_probability"))}</div>'
                f'<div class="p1-edge">{_pct(abs(float(row.get("model_edge") or 0)))}</div></div>'
            )
        st.markdown('<div class="p1 p1-top">' + "".join(cards) + "</div>", unsafe_allow_html=True)
    else:
        st.info("Top edges appear only when the exact current line has a verified model result.")

    st.markdown("### Player Discovery")
    a, b, c = st.columns([2, 1, 1])
    search = a.text_input("Search players", placeholder="Player or team", key="wnba-pra-page1-search")
    sort_by = b.selectbox("Sort by", ("Model Edge", "Probability", "Projection", "Player"), key="wnba-pra-page1-sort")
    status = c.selectbox("Game Status", ("All", "Verified", "Refreshing"), key="wnba-pra-page1-status")
    term = str(search or "").strip().casefold()
    filtered = []
    for row in rows:
        if term and term not in f"{row.get('player_name', '')} {row.get('team', '')} {row.get('opponent', '')}".casefold():
            continue
        is_ready = row.get("model_state") == "LINE_BOUND_READY"
        if status == "Verified" and not is_ready:
            continue
        if status == "Refreshing" and is_ready:
            continue
        filtered.append(row)
    if sort_by == "Model Edge":
        filtered.sort(key=lambda r: -abs(float(r.get("model_edge") or 0)))
    elif sort_by == "Probability":
        filtered.sort(key=lambda r: -float(r.get("model_probability") or -1))
    elif sort_by == "Projection":
        filtered.sort(key=lambda r: -float(r.get("projection_pra") or -1))
    else:
        filtered.sort(key=lambda r: str(r.get("player_name") or ""))
    if not filtered:
        st.info("No Page 1 players match the current filters.")
    for start in range(0, len(filtered), 3):
        cols = st.columns(3)
        for col, row in zip(cols, filtered[start : start + 3]):
            col.markdown(_card(row), unsafe_allow_html=True)
            if col.button(
                "Analyze Player",
                key=f"p1-analyze-{start}-{row.get('player_name')}-{row.get('line')}",
                use_container_width=True,
            ):
                _handoff(row, payload)

    st.markdown("### 🏆 Final PRA Card")
    finals = [x for x in (payload.get("final_card") or []) if isinstance(x, Mapping)]
    if not finals:
        st.info("No market-qualified PRA selection is certified for this state yet. No pick is being forced.")
    else:
        lookup = {(r["player_name"], r["line"]): r for r in rows}
        for i, card in enumerate(finals[:5], 1):
            player = str(card.get("player_name") or card.get("player") or "")
            try:
                line = float(card.get("line"))
            except (TypeError, ValueError):
                continue
            quote = lookup.get((player, line), {})
            side = str(card.get("side") or "over").upper()
            price = quote.get("over_odds") if side == "OVER" else quote.get("under_odds")
            st.markdown(
                f'<div class="p1 p1-final"><strong>#{i} {escape(player)} • {escape(side)} {line:.1f} PRA</strong><br>'
                f'<span>{escape(optional_label(quote.get("sportsbook")))} {_odds(price)} • Model {_pct(quote.get("model_probability"))} • Projection {_num(quote.get("projection_pra"))} • Edge {_pct(abs(float(quote.get("model_edge") or 0)))}</span></div>',
                unsafe_allow_html=True,
            )


__all__ = [
    "PAGE1_HANDOFF_KEY",
    "NOT_VERIFIED",
    "optional_label",
    "build_player_board_rows",
    "rank_top_edges",
    "render_page_snapshot",
]
