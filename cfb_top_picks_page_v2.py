"""CFB Top Picks Step 2 — compact 10-card visual board.

Additive over frozen Step 1. This file implements only the compact card layout
approved in the visual mockup. The displayed rows are explicit layout-preview
samples; real daily ranking, probability, toughness and data logic belong to
later steps.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import cfb_top_picks_page_v1 as prior

MODEL_VERSION = "CFB TOP PICKS V2 • STEP 2 COMPACT CARDS"
PAGE_MARKER = "CFB_TOP_PICKS_STEP2_COMPACT_CARDS_ACTIVE"
LAYOUT_PREVIEW = True

SAMPLE_LAYOUT_ROWS = (
    {"rank":1,"away":"Georgia","away_abbr":"G","home":"Kentucky","home_abbr":"UK","time":"Sat, 12:00 PM","network":"ESPN","market":"MONEYLINE","pick":"Georgia","odds":"-320","probability":76,"toughness":2,"toughness_label":"Easy"},
    {"rank":2,"away":"Ohio State","away_abbr":"OSU","home":"Michigan State","home_abbr":"MSU","time":"Sat, 12:00 PM","network":"FOX","market":"SPREAD","pick":"Ohio State -10.5","odds":"-110","probability":74,"toughness":2,"toughness_label":"Easy"},
    {"rank":3,"away":"Texas","away_abbr":"TEX","home":"Oklahoma","home_abbr":"OU","time":"Sat, 3:30 PM","network":"ABC","market":"OVER/UNDER","pick":"Over 56.5","odds":"-110","probability":68,"toughness":3,"toughness_label":"Medium"},
    {"rank":4,"away":"Oregon","away_abbr":"ORE","home":"Washington","home_abbr":"WASH","time":"Sat, 7:30 PM","network":"FOX","market":"MONEYLINE","pick":"Oregon","odds":"-185","probability":67,"toughness":3,"toughness_label":"Medium"},
    {"rank":5,"away":"Alabama","away_abbr":"ALA","home":"Tennessee","home_abbr":"TENN","time":"Sat, 3:30 PM","network":"CBS","market":"SPREAD","pick":"Tennessee +7.0","odds":"-110","probability":63,"toughness":3,"toughness_label":"Medium"},
    {"rank":6,"away":"Notre Dame","away_abbr":"ND","home":"Florida State","home_abbr":"FSU","time":"Sat, 7:30 PM","network":"NBC","market":"MONEYLINE","pick":"Notre Dame","odds":"-145","probability":62,"toughness":3,"toughness_label":"Medium"},
    {"rank":7,"away":"LSU","away_abbr":"LSU","home":"Ole Miss","home_abbr":"MISS","time":"Sat, 12:00 PM","network":"ESPN","market":"OVER/UNDER","pick":"Over 63.5","odds":"-110","probability":60,"toughness":3,"toughness_label":"Medium"},
    {"rank":8,"away":"Penn State","away_abbr":"PSU","home":"USC","home_abbr":"USC","time":"Sat, 8:00 PM","network":"FOX","market":"SPREAD","pick":"Penn State -3.5","odds":"-110","probability":58,"toughness":4,"toughness_label":"Tough"},
    {"rank":9,"away":"Miami (FL)","away_abbr":"MIA","home":"Louisville","home_abbr":"LOU","time":"Sat, 7:30 PM","network":"ACC Network","market":"MONEYLINE","pick":"Miami (FL)","odds":"-175","probability":57,"toughness":4,"toughness_label":"Tough"},
    {"rank":10,"away":"Kansas State","away_abbr":"KSU","home":"Iowa","home_abbr":"IOWA","time":"Sat, 12:00 PM","network":"FS1","market":"OVER/UNDER","pick":"Under 38.5","odds":"-110","probability":55,"toughness":4,"toughness_label":"Tough"},
)

CSS = prior.CSS + r"""
<style>
[data-testid="cfb-top-picks-step2-root"]{width:100%;max-width:1500px;margin:0 auto;padding:4px 2px 18px;color:#f7fbff}
.tp2-preview{display:flex;align-items:center;gap:8px;margin:0 2px 10px;color:#71879d;font-size:.68rem;font-weight:800;letter-spacing:.10em;text-transform:uppercase}
.tp2-preview-dot{width:6px;height:6px;border-radius:50%;background:#119dff;box-shadow:0 0 10px rgba(17,157,255,.65)}
.tp2-board{display:flex;flex-direction:column;gap:8px;margin-top:8px}
.tp2-card{display:grid;grid-template-columns:56px minmax(250px,1.5fr) 145px 230px 104px minmax(210px,1fr) 34px;align-items:center;min-height:76px;border:1px solid rgba(109,198,255,.16);border-radius:13px;background:linear-gradient(180deg,rgba(9,21,34,.96),rgba(5,14,23,.96));box-shadow:inset 0 1px 0 rgba(255,255,255,.018);overflow:hidden}
.tp2-card:hover{border-color:rgba(17,157,255,.48);box-shadow:0 0 0 1px rgba(17,157,255,.08),0 8px 28px rgba(0,0,0,.18)}
.tp2-cell{min-width:0;padding:10px 13px;border-left:1px solid rgba(109,198,255,.10)}
.tp2-cell:first-of-type{border-left:0}
.tp2-rank{justify-self:center;width:38px;height:38px;border-radius:50%;display:grid;place-items:center;border:2px solid #119dff;background:rgba(6,26,43,.85);font-size:1rem;font-weight:900;box-shadow:0 0 14px rgba(17,157,255,.16)}
.tp2-matchup{display:grid;grid-template-columns:42px minmax(0,1fr);gap:11px;align-items:center}
.tp2-logos{position:relative;width:40px;height:44px}
.tp2-logo{position:absolute;left:0;width:30px;height:30px;border-radius:9px;display:grid;place-items:center;background:#0b1d2d;border:1px solid rgba(120,211,255,.32);color:#dff5ff;font-size:.58rem;font-weight:950;box-shadow:0 3px 10px rgba(0,0,0,.24)}
.tp2-logo.a{top:0}.tp2-logo.h{bottom:0;left:9px;background:#0d1723}
.tp2-logo-img{object-fit:contain;padding:2px;background:#071522}
.tp2-teams{display:flex;flex-direction:column;gap:3px;font-weight:800;line-height:1.07}
.tp2-teamline{display:flex;align-items:center;gap:8px;white-space:nowrap}
.tp2-vs{color:#71879d;font-size:.74rem;font-weight:700}
.tp2-time{color:#c3d1df;font-size:.78rem;line-height:1.35}
.tp2-network{color:#849ab0}
.tp2-bet{display:flex;flex-direction:column;gap:7px}
.tp2-market{width:max-content;max-width:100%;padding:5px 10px;border-radius:7px;font-size:.62rem;font-weight:950;line-height:1;letter-spacing:.03em}
.tp2-market.ml{color:#dff5ff;background:rgba(17,157,255,.19);border:1px solid #119dff}
.tp2-market.sp{color:#ddffeb;background:rgba(0,214,117,.13);border:1px solid #15d879}
.tp2-market.ou{color:#fff1a8;background:rgba(255,202,40,.13);border:1px solid #ffca28}
.tp2-pickline{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
.tp2-pick{font-size:.96rem;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tp2-odds{color:#9bb0c4;font-size:.72rem;font-weight:750}
.tp2-prob{justify-self:center;width:59px;height:59px;border-radius:50%;display:grid;place-items:center;background:radial-gradient(circle at center,#08131d 57%,transparent 59%),conic-gradient(#119dff calc(var(--pct)*1%),#183149 0);box-shadow:0 0 17px rgba(17,157,255,.14);font-weight:950;font-size:.9rem}
.tp2-toughness{display:flex;align-items:center;justify-content:space-between;gap:12px}
.tp2-tough-copy{display:flex;flex-direction:column;gap:7px}
.tp2-tough-label{color:#a8bdd0;font-size:.72rem}
.tp2-meter{display:flex;gap:4px}
.tp2-meter i{display:block;width:13px;height:10px;border-radius:3px;background:#183149;border:1px solid rgba(126,190,229,.08)}
.tp2-meter i.on{background:#20b8ff;box-shadow:0 0 7px rgba(32,184,255,.28)}
.tp2-level{font-size:.8rem;font-weight:900}
.tp2-level.easy{color:#1ee787}.tp2-level.medium{color:#ffd23f}.tp2-level.tough{color:#ff754a}
.tp2-chevron{justify-self:center;color:#a9c5db;font-size:1.25rem;font-weight:600;transform:translateY(-1px)}
.tp2-step-marker{position:absolute;width:1px;height:1px;overflow:hidden;opacity:.001;pointer-events:none}
@media(max-width:1100px){
  .tp2-card{grid-template-columns:50px minmax(220px,1.35fr) 120px minmax(190px,1fr) 82px minmax(180px,1fr) 30px}
  .tp2-cell{padding:9px 10px}
}
@media(max-width:820px){
  .tp2-card{grid-template-columns:46px minmax(0,1fr) 76px 30px;min-height:92px}
  .tp2-timecell{display:none}
  .tp2-betcell{grid-column:2;grid-row:2;border-left:0;padding-top:0}
  .tp2-probcell{grid-column:3;grid-row:1/3;border-left:1px solid rgba(109,198,255,.10)}
  .tp2-toughcell{display:none}
  .tp2-chevroncell{grid-column:4;grid-row:1/3}
  .tp2-prob{width:52px;height:52px;font-size:.8rem}
}
</style>
"""


def _market_class(value: str) -> str:
    return {"MONEYLINE":"ml","SPREAD":"sp","OVER/UNDER":"ou"}.get(value, "ml")


def _level_class(value: str) -> str:
    return str(value or "").strip().lower()


def _meter(level: int) -> str:
    safe = max(0, min(5, int(level)))
    return "".join('<i class="on"></i>' if i < safe else "<i></i>" for i in range(5))


def _logo_markup(row: dict, side: str, rank: int) -> str:
    url = str(row.get(f"{side}_logo_url") or "").strip()
    team = str(row.get(side) or "").strip()
    abbr = str(row.get(f"{side}_abbr") or "").strip()
    team_id = str(row.get(f"{side}_team_id") or "").strip()
    provider = str(row.get(f"{side}_logo_provider") or "").strip()
    pos = "a" if side == "away" else "h"
    if url.startswith(("https://", "http://")):
        return (
            f'<img class="tp2-logo tp2-logo-img {pos}" '
            f'data-testid="cfb-top-picks-logo-{side}-{rank}" '
            f'data-top-picks-real-logo="true" '
            f'data-team-id="{escape(team_id, quote=True)}" '
            f'data-logo-provider="{escape(provider, quote=True)}" '
            f'src="{escape(url, quote=True)}" '
            f'alt="{escape(team, quote=True)} logo" loading="eager">'
        )
    return (
        f'<div class="tp2-logo {pos}" data-testid="cfb-top-picks-logo-{side}-{rank}" '
        f'data-logo-placeholder="true">{escape(abbr)}</div>'
    )


def _card(row: dict) -> str:
    rank = int(row["rank"])
    return f"""
    <article class="tp2-card" data-testid="cfb-top-picks-card-{rank}" data-expanded="false">
      <div class="tp2-rank">{rank}</div>
      <div class="tp2-cell tp2-matchup">
        <div class="tp2-logos">
          {_logo_markup(row, "away", rank)}
          {_logo_markup(row, "home", rank)}
        </div>
        <div class="tp2-teams">
          <div class="tp2-teamline">{escape(str(row["away"]))}</div>
          <div class="tp2-teamline"><span class="tp2-vs">vs</span>{escape(str(row["home"]))}</div>
        </div>
      </div>
      <div class="tp2-cell tp2-timecell">
        <div class="tp2-time">{escape(str(row["time"]))}<br><span class="tp2-network">{escape(str(row["network"]))}</span></div>
      </div>
      <div class="tp2-cell tp2-betcell">
        <div class="tp2-bet">
          <span class="tp2-market {_market_class(str(row["market"]))}">{escape(str(row["market"]))}</span>
          <div class="tp2-pickline"><span class="tp2-pick">{escape(str(row["pick"]))}</span><span class="tp2-odds">{escape(str(row["odds"]))}</span></div>
        </div>
      </div>
      <div class="tp2-cell tp2-probcell"><div class="tp2-prob" style="--pct:{int(row["probability"])}">{int(row["probability"])}%</div></div>
      <div class="tp2-cell tp2-toughcell">
        <div class="tp2-toughness">
          <div class="tp2-tough-copy"><span class="tp2-tough-label">Toughness</span><span class="tp2-meter">{_meter(int(row["toughness"]))}</span></div>
          <span class="tp2-level {_level_class(str(row["toughness_label"]))}">{escape(str(row["toughness_label"]))}</span>
        </div>
      </div>
      <div class="tp2-chevroncell"><div class="tp2-chevron">⌄</div></div>
    </article>
    """


def render_top_picks_page() -> None:
    cards = "".join(_card(row) for row in SAMPLE_LAYOUT_ROWS)
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <section data-testid="cfb-top-picks-step2-root">
          <div class="tp2-step-marker" data-testid="cfb-top-picks-step1-marker">CFB_TOP_PICKS_STEP1_SHELL_ACTIVE</div>
          <div class="tp2-step-marker" data-testid="cfb-top-picks-step2-marker">{PAGE_MARKER}</div>
          <div class="tp1-hero">
            <div>
              <h1 class="tp1-title">Top <span>Picks</span></h1>
              <div class="tp1-subtitle">10 Best Daily College Football Picks</div>
            </div>
            <div class="tp1-actions">
              <div class="tp1-segmented" data-testid="cfb-top-picks-market-tabs">
                <div class="tp1-chip active">Moneyline</div>
                <div class="tp1-chip">Spread</div>
                <div class="tp1-chip">Over/Under</div>
              </div>
              <div class="tp1-date" data-testid="cfb-top-picks-date">
                <span class="tp1-date-icon">▣</span><span>Today</span><span>⌄</span>
              </div>
            </div>
          </div>
          <div class="tp2-preview"><span class="tp2-preview-dot"></span>Layout preview • live daily rankings connect in Step 3</div>
          <div class="tp2-board" data-testid="cfb-top-picks-card-board">{cards}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if str(market or "").strip() != "Top Picks":
        raise RuntimeError("CFB Top Picks Step 2 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = ["CSS","LAYOUT_PREVIEW","MODEL_VERSION","PAGE_MARKER","SAMPLE_LAYOUT_ROWS","render_cfb_hub","render_top_picks_page"]
