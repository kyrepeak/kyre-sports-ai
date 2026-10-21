"""Thin dict-only Streamlit renderer for the WNBA PRA page snapshot."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

_CSS = """
<style>
.pra-fast-hero{border:1px solid #21394c;border-radius:16px;padding:14px 16px;background:linear-gradient(145deg,#071019,#0b1722);margin-bottom:12px}.pra-fast-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px}.pra-fast-card{border:1px solid #29475f;border-radius:14px;padding:13px;background:#08131d}.pra-fast-name{font-size:17px;font-weight:900;color:#eef8ff}.pra-fast-meta{font-size:11px;color:#8ca7ba;margin-top:2px}.pra-fast-line{font-size:24px;font-weight:1000;color:#9ee7ff;margin:8px 0}.pra-fast-row{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:#bed1df}.pra-fast-good{color:#65e7ad;font-weight:900}.pra-fast-warn{color:#ffd47a;font-weight:900}.pra-fast-final{border:1px solid #3c6f58;border-radius:14px;padding:12px;background:#0a1915;margin:7px 0}
</style>
"""


def _odds(value: Any) -> str:
    try:
        number = int(float(value)); return f"+{number}" if number > 0 else str(number)
    except Exception:
        return "—"


def _pct(value: Any) -> str:
    try: return f"{100.0*float(value):.1f}%"
    except Exception: return "—"


def _num(value: Any, digits: int = 1) -> str:
    try: return f"{float(value):.{digits}f}"
    except Exception: return "—"


def _group_offers(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, float, str], dict[str, Any]] = {}
    for raw in payload.get("offers") or []:
        if not isinstance(raw, Mapping) or raw.get("line") is None:
            continue
        player = str(raw.get("player_name") or "").strip()
        if not player: continue
        key=(player,float(raw["line"]),str(raw.get("sportsbook") or ""))
        entry=grouped.setdefault(key,{"player_name":player,"line":float(raw["line"]),"sportsbook":str(raw.get("sportsbook") or ""),"team":raw.get("team"),"opponent":raw.get("opponent"),"model_state":raw.get("model_state"),"p_over":raw.get("p_over"),"p_under":raw.get("p_under"),"projection_pra":raw.get("projection_pra")})
        side=str(raw.get("side") or "").casefold()
        if side in {"over","under"}: entry[side+"_odds"]=raw.get("american_odds")
    return sorted(grouped.values(),key=lambda r:r["player_name"])


def render_page_snapshot(payload: Mapping[str, Any], **_kwargs: Any) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    state=str(payload.get("snapshot_state") or "MODEL_UNAVAILABLE")
    cache=str(payload.get("cache_state") or "MODEL_UNAVAILABLE")
    provider=str(payload.get("selected_provider") or "unavailable").replace("_"," ").title()
    st.markdown(f'<div class="pra-fast-hero"><div style="font-size:11px;color:#7fa2ba">WNBA PRA • {escape(str(payload.get("date") or ""))}</div><div style="font-size:23px;font-weight:1000;color:#eef8ff">PRA Analytics Board</div><div style="font-size:11px;color:#8ca7ba">Kyre Sports API • {escape(provider)} • {escape(cache)}</div></div>',unsafe_allow_html=True)
    if state == "MODEL_REFRESH_REQUIRED": st.warning("Live PRA line moved. Fresh sportsbook quote is shown; line-specific model probability is refreshing and is not being reused from the old line.")
    elif state == "MODEL_UNAVAILABLE": st.warning("Fresh PRA market is available, but the model artifact is rebuilding. No probability is being forced.")
    elif cache == "STALE_SAFE": st.info("Model context is still within its safe window and is refreshing in the background.")

    st.markdown("### PRA Player Board")
    cards=[]
    for row in _group_offers(payload):
        ready=row.get("model_state")=="LINE_BOUND_READY"
        model_html=(f'<div class="pra-fast-row"><span>Model O/U</span><span class="pra-fast-good">{_pct(row.get("p_over"))} / {_pct(row.get("p_under"))}</span></div><div class="pra-fast-row"><span>Projection</span><span>{_num(row.get("projection_pra"))} PRA</span></div>') if ready else '<div class="pra-fast-row"><span>Model</span><span class="pra-fast-warn">REFRESH REQUIRED</span></div>'
        cards.append(f'<div class="pra-fast-card"><div class="pra-fast-name">{escape(row["player_name"])}</div><div class="pra-fast-meta">{escape(str(row.get("team") or ""))}{" vs "+escape(str(row.get("opponent"))) if row.get("opponent") else ""}</div><div class="pra-fast-line">{row["line"]:.1f} PRA</div><div class="pra-fast-row"><span>{escape(row.get("sportsbook") or "Sportsbook")}</span><span>O {_odds(row.get("over_odds"))} • U {_odds(row.get("under_odds"))}</span></div>{model_html}</div>')
    if cards: st.markdown('<div class="pra-fast-grid">'+''.join(cards)+'</div>',unsafe_allow_html=True)
    else: st.info("No current exact approved WNBA PRA market is available for this verified slate yet.")

    st.markdown("### 🏆 Final PRA Card")
    finals=[x for x in (payload.get("final_card") or []) if isinstance(x,Mapping)]
    if not finals: st.info("No market-qualified PRA selection is certified for this state yet. No pick is being forced.")
    else:
        lookup={(r["player_name"],r["line"]):r for r in _group_offers(payload)}
        for card in finals:
            player=str(card.get("player_name") or card.get("player") or "")
            try: line=float(card.get("line"))
            except Exception: continue
            quote=lookup.get((player,line),{})
            side=str(card.get("side") or "over").upper()
            st.markdown(f'<div class="pra-fast-final"><div class="pra-fast-name">{escape(player)} • {side} {line:.1f} PRA</div><div class="pra-fast-meta">{escape(str(quote.get("sportsbook") or ""))} • {_odds(quote.get("over_odds") if side=="OVER" else quote.get("under_odds"))}</div></div>',unsafe_allow_html=True)


__all__=["render_page_snapshot"]
