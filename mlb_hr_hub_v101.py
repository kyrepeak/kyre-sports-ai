"""MLB Home Run Monster V1.0.1 — null-safe UI bridge.

HOME RUN ONLY. Keeps the V1.0 probability engine intact while preventing a
missing Statcast or starter-HR/9 value from crashing the result cards.
"""
from html import escape

import mlb_hr_hub_v10 as base
from engine import odds, sf

MODEL_VERSION = "HR V1.0.1"


def _e(v):
    return escape(str(v if v is not None else "—"))


def _safe_card(r, rank):
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    confirmed = "✅ CONFIRMED" if r.get("lineup_confirmed") else "🕒 PROJECTED"
    cls = "hr-card one" if rank == 1 else "hr-card"
    sc = r.get("statcast") or {}
    barrel = sf(sc.get("barrel_rate"))
    xslg = sf(sc.get("xslg"))
    hr9 = sf(r.get("pitcher_hr9"))
    barrel_text = f"{barrel*100:.1f}%" if barrel is not None else "—"
    xslg_text = f"{xslg:.3f}" if xslg is not None else "—"
    hr9_text = f"{hr9:.2f}" if hr9 is not None else "—"
    conf_cls = "" if r.get("confidence") == "HIGH" else " med"
    return f'''<div class="{cls}">
      <div class="hr-rank">{medal} Rank {rank} • {confirmed}</div>
      <div class="hr-name">{_e(r.get('player_name'))}</div>
      <div class="hr-meta">{_e(r.get('team'))} vs {_e(r.get('opponent'))}<br>vs {_e(r.get('starter_name'))} • Bat #{_e(r.get('position'))} • {_e(r.get('first_pitch'))}</div>
      <div class="hr-prob">{r['p_hr']*100:.1f}%</div><div class="hr-prob-label">1+ Home Run probability • Fair {odds(r['p_hr'])}</div>
      <div class="hr-stats">
        <div class="hr-stat"><span>Season HR</span><b>{r.get('season_hr',0)}</b></div>
        <div class="hr-stat"><span>2+ HR</span><b>{r.get('p_2hr',0)*100:.1f}%</b></div>
        <div class="hr-stat"><span>Barrel%</span><b>{barrel_text}</b></div>
        <div class="hr-stat"><span>Starter HR/9</span><b>{hr9_text}</b></div>
        <div class="hr-stat"><span>xSLG</span><b>{xslg_text}</b></div>
        <div class="hr-stat"><span>Recent HR</span><b>{r.get('recent_hr',0)} / L10</b></div>
        <div class="hr-stat"><span>Proj PA</span><b>{r.get('projected_pa',0):.1f}</b></div>
        <div class="hr-stat"><span>Data</span><b>{r.get('data_score',0)}/7</b></div>
      </div>
      <div class="hr-conf{conf_cls}">{_e(r.get('confidence'))}</div>
    </div>'''


base._card = _safe_card


def render_home_run_hub(games_df, section_header, status_info, team_logo, h):
    return base.render_home_run_hub(games_df, section_header, status_info, team_logo, h)
