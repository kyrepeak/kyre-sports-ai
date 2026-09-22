"""MLB H+R+RBI V1.0.1 — null-safe UI bridge.

H+R+RBI ONLY. Keeps the V1.0 joint-event model intact while making result cards
safe when a player has no usable L10/L5 game-log sample.
"""
from html import escape

import mlb_hrrbi_hub_v10 as base
from engine import odds

MODEL_VERSION = "H+R+RBI V1.0.1"


def _e(v):
    return escape(str(v if v is not None else "—"))


def _fmt_recent(v):
    try:
        return f"{float(v):.1f}"
    except Exception:
        return "—"


def _safe_card(r, rank, threshold):
    sim = r["sim"]
    p = base._threshold_prob(sim, threshold)
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    source = "✅ CONFIRMED" if r.get("lineup_confirmed") else "🕒 PROJECTED"
    cls = "hrr-card one" if rank == 1 else "hrr-card"
    conf_cls = "" if r.get("confidence") == "HIGH" else " med"
    l10 = (r.get("l10") or {}).get("combined_pg")
    l5 = (r.get("l5") or {}).get("combined_pg")
    return f'''<div class="{cls}">
      <div class="hrr-rank">{medal} Rank {rank} • {source}</div>
      <div class="hrr-name">{_e(r.get('player_name'))}</div>
      <div class="hrr-meta">{_e(r.get('team'))} vs {_e(r.get('opponent'))}<br>vs {_e(r.get('starter_name'))} • Bat #{_e(r.get('position'))} • {_e(r.get('first_pitch'))}</div>
      <div class="hrr-prob">{p*100:.1f}%</div><div class="hrr-prob-label">{threshold}+ H+R+RBI probability • Fair {odds(p)}</div>
      <div class="hrr-stats">
        <div class="hrr-stat"><span>xH</span><b>{sim['expected_h']:.2f}</b></div>
        <div class="hrr-stat"><span>xR</span><b>{sim['expected_r']:.2f}</b></div>
        <div class="hrr-stat"><span>xRBI</span><b>{sim['expected_rbi']:.2f}</b></div>
        <div class="hrr-stat"><span>xCombined</span><b>{sim['expected_total']:.2f}</b></div>
        <div class="hrr-stat"><span>3+</span><b>{sim['p3']*100:.1f}%</b></div>
        <div class="hrr-stat"><span>4+</span><b>{sim['p4']*100:.1f}%</b></div>
        <div class="hrr-stat"><span>L10</span><b>{_fmt_recent(l10)}</b></div>
        <div class="hrr-stat"><span>L5</span><b>{_fmt_recent(l5)}</b></div>
      </div>
      <div class="hrr-conf{conf_cls}">{_e(r.get('confidence'))}</div>
    </div>'''


base._card = _safe_card


def render_hrrbi_hub(games_df, section_header, status_info, team_logo, h):
    return base.render_hrrbi_hub(games_df, section_header, status_info, team_logo, h)
