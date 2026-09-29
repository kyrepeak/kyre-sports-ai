"""CFB Top Picks Step 3 — live ranked daily board.

Additive over frozen Step 2 visual card system. Step 3 replaces layout-preview
rows with fail-closed live model candidates from cfb_top_picks_engine_v1.
Why/history/benefit accordions remain deferred to Step 4.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import os
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_page_v2 as prior

MODEL_VERSION = "CFB TOP PICKS V3 • STEP 3 LIVE RANKING"
PAGE_MARKER = "CFB_TOP_PICKS_STEP3_LIVE_RANKING_ACTIVE"
_PHOENIX = ZoneInfo("America/Phoenix")

CSS = prior.CSS + r"""
<style>
.tp3-livebar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 2px 10px;padding:7px 10px;border:1px solid rgba(109,198,255,.13);border-radius:9px;background:rgba(5,14,23,.58)}
.tp3-liveleft{display:flex;align-items:center;gap:8px;color:#8da5ba;font-size:.69rem;font-weight:850;letter-spacing:.08em;text-transform:uppercase}
.tp3-live-dot{width:7px;height:7px;border-radius:50%;background:#1ee787;box-shadow:0 0 10px rgba(30,231,135,.55)}
.tp3-meta{color:#6f879b;font-size:.68rem;font-weight:700}
.tp3-empty{padding:24px 18px;border:1px solid rgba(109,198,255,.16);border-radius:13px;background:#07111b;color:#a8bdd0;text-align:center}
.tp3-source{display:none}
</style>
"""


def _fixture_board() -> tuple[list[dict], dict]:
    """CI-only browser fixture. Production never enters this path."""
    base = []
    markets = ("MONEYLINE","SPREAD","OVER/UNDER")
    for index in range(1, 11):
        market = markets[(index - 1) % len(markets)]
        probability = 0.78 - (index - 1) * 0.022
        level, label = engine._toughness(probability, 0.82, 0.84)
        base.append({
            "rank": index,
            "identity": f"fixture-{index}",
            "event_id": str(9000 + index),
            "away": f"Away {index}",
            "home": f"Home {index}",
            "kickoff_iso": "2026-10-03T19:30:00Z",
            "network": "ESPN",
            "market": market,
            "pick": f"Fixture Pick {index}",
            "odds": "-110" if market != "MONEYLINE" else "-145",
            "probability": probability,
            "reliability": 0.82,
            "coverage": 0.84,
            "toughness": level,
            "toughness_label": label,
            "rank_score": engine._rank_score(probability, 0.82, 0.84),
            "source": "CI fixture only",
            "market_projection_weight": 0.0,
        })
    return base, {
        "status":"GREEN",
        "requested_day":"2026-10-03",
        "resolved_day":"2026-10-03",
        "auto_advanced":False,
        "pick_count":10,
        "market_counts":{"MONEYLINE":4,"SPREAD":3,"OVER/UNDER":3},
        "market_projection_weight":0.0,
        "fixture_mode":True,
    }


def _market_class(value: str) -> str:
    return {"MONEYLINE":"ml","SPREAD":"sp","OVER/UNDER":"ou"}.get(value, "ml")


def _level_class(value: str) -> str:
    return str(value or "").strip().lower()


def _meter(level: int) -> str:
    safe=max(0,min(5,int(level)))
    return "".join('<i class="on"></i>' if i < safe else "<i></i>" for i in range(5))


def _kickoff(value: str) -> tuple[str,str]:
    try:
        parsed=datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(_PHOENIX)
        return parsed.strftime("%a, %I:%M %p").replace(" 0"," "), "Phoenix"
    except Exception:
        return "Kickoff TBD", ""


def _abbr(team: str) -> str:
    words=[word for word in str(team or "").replace("("," ").replace(")"," ").split() if word]
    if not words:
        return "CFB"
    if len(words)==1:
        return words[0][:3].upper()
    return "".join(word[0] for word in words[:3]).upper()


def _card(row: dict) -> str:
    rank=int(row.get("rank") or 0)
    away=escape(str(row.get("away") or "Away"))
    home=escape(str(row.get("home") or "Home"))
    time_text,tz_text=_kickoff(str(row.get("kickoff_iso") or ""))
    probability=int(round(float(row.get("probability") or 0.0)*100))
    toughness=int(row.get("toughness") or 4)
    label=str(row.get("toughness_label") or "Tough")
    source=escape(str(row.get("source") or ""))
    return f"""
    <article class="tp2-card" data-testid="cfb-top-picks-card-{rank}" data-expanded="false" data-market="{escape(str(row.get('market') or ''))}">
      <div class="tp2-rank">{rank}</div>
      <div class="tp2-cell tp2-matchup">
        <div class="tp2-logos">
          <div class="tp2-logo a">{escape(_abbr(row.get("away")))}</div>
          <div class="tp2-logo h">{escape(_abbr(row.get("home")))}</div>
        </div>
        <div class="tp2-teams">
          <div class="tp2-teamline">{away}</div>
          <div class="tp2-teamline"><span class="tp2-vs">vs</span>{home}</div>
        </div>
      </div>
      <div class="tp2-cell tp2-timecell"><div class="tp2-time">{escape(time_text)}<br><span class="tp2-network">{escape(str(row.get("network") or tz_text or "TBD"))}</span></div></div>
      <div class="tp2-cell tp2-betcell">
        <div class="tp2-bet">
          <span class="tp2-market {_market_class(str(row.get("market") or ""))}">{escape(str(row.get("market") or ""))}</span>
          <div class="tp2-pickline"><span class="tp2-pick">{escape(str(row.get("pick") or ""))}</span><span class="tp2-odds">{escape(str(row.get("odds") or "—"))}</span></div>
        </div>
      </div>
      <div class="tp2-cell tp2-probcell"><div class="tp2-prob" style="--pct:{probability}">{probability}%</div></div>
      <div class="tp2-cell tp2-toughcell">
        <div class="tp2-toughness">
          <div class="tp2-tough-copy"><span class="tp2-tough-label">Toughness</span><span class="tp2-meter">{_meter(toughness)}</span></div>
          <span class="tp2-level {_level_class(label)}">{escape(label)}</span>
        </div>
      </div>
      <div class="tp2-chevroncell"><div class="tp2-chevron">⌄</div></div>
      <span class="tp3-source">{source}</span>
    </article>
    """


def render_top_picks_page() -> None:
    today=datetime.now(_PHOENIX).date().isoformat()
    fixture=os.environ.get("CFB_TOP_PICKS_BROWSER_FIXTURE","").strip()=="1"
    if fixture:
        picks,diag=_fixture_board()
    else:
        with st.spinner("Building today's verified CFB Top Picks..."):
            picks,diag=engine.cached_daily_board(today)

    resolved=str(diag.get("resolved_day") or today)
    auto=bool(diag.get("auto_advanced"))
    badge=("Today" if resolved==today else f"Next • {resolved}")
    market_counts=diag.get("market_counts") or {}

    st.markdown(CSS,unsafe_allow_html=True)
    cards="".join(_card(row) for row in picks)
    board=cards if cards else '<div class="tp3-empty" data-testid="cfb-top-picks-empty">No qualified model picks are available for the verified slate. Nothing was fabricated.</div>'
    st.markdown(
        f"""
        <section data-testid="cfb-top-picks-step3-root">
          <div class="tp2-step-marker" data-testid="cfb-top-picks-step1-marker">CFB_TOP_PICKS_STEP1_SHELL_ACTIVE</div>
          <div class="tp2-step-marker" data-testid="cfb-top-picks-step2-marker">CFB_TOP_PICKS_STEP2_COMPACT_CARDS_ACTIVE</div>
          <div class="tp2-step-marker" data-testid="cfb-top-picks-step3-marker">{PAGE_MARKER}</div>
          <div class="tp1-hero">
            <div><h1 class="tp1-title">Top <span>Picks</span></h1><div class="tp1-subtitle">10 Best Daily College Football Picks</div></div>
            <div class="tp1-actions">
              <div class="tp1-segmented" data-testid="cfb-top-picks-market-tabs">
                <div class="tp1-chip active">Moneyline</div><div class="tp1-chip">Spread</div><div class="tp1-chip">Over/Under</div>
              </div>
              <div class="tp1-date" data-testid="cfb-top-picks-date"><span class="tp1-date-icon">▣</span><span>{escape(badge)}</span><span>⌄</span></div>
            </div>
          </div>
          <div class="tp3-livebar" data-testid="cfb-top-picks-live-status">
            <div class="tp3-liveleft"><span class="tp3-live-dot"></span>Live model board • market data has 0% projection weight</div>
            <div class="tp3-meta">{len(picks)} picks • ML {int(market_counts.get("MONEYLINE") or 0)} • Spread {int(market_counts.get("SPREAD") or 0)} • O/U {int(market_counts.get("OVER/UNDER") or 0)}</div>
          </div>
          <div class="tp2-board" data-testid="cfb-top-picks-card-board">{board}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Model probabilities are estimates — not guarantees. Market lines are comparison thresholds/context only and do not alter the projection models.")
    with st.expander("🧪 Top Picks data status",expanded=False):
        st.json({
            "status":diag.get("status"),
            "requested_day":diag.get("requested_day"),
            "resolved_day":diag.get("resolved_day"),
            "auto_advanced":diag.get("auto_advanced"),
            "pick_count":diag.get("pick_count"),
            "candidate_count":diag.get("candidate_count"),
            "market_counts":market_counts,
            "market_projection_weight":diag.get("market_projection_weight"),
        })


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if str(market or "").strip()!="Top Picks":
        raise RuntimeError("CFB Top Picks Step 3 owns only the Top Picks route.")
    render_top_picks_page()


__all__=["CSS","MODEL_VERSION","PAGE_MARKER","render_cfb_hub","render_top_picks_page"]
