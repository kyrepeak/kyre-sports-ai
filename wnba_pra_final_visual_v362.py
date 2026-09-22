"""WNBA PRA V3.6.2 — Step 1 presentation-only Final Card identity layer.

Adds player headshots and verified team logos to the existing PRA Step-9 Top-5
Final Card. The production PRA projection, market grading, qualification,
Monte Carlo, ranking, final-ready gates and selection logic are unchanged.

Identity is resolved from the same verified PRA projection/slate already used by
the model. Player images use the existing ESPN WNBA headshot pattern already
proven by the Preliminary PRA visual board. Team logos use the verified WNBA
slate/team-logo resolver. No Python-side image request is introduced.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import wnba_pra_final_v32 as final32
import wnba_pra_visual_v352 as visual

MODEL_VERSION = "PRA V3.6.2 • STEP 1 FINAL TOP-5 IDENTITY • MODEL PRESERVED"

_IDENTITY_MEMO = {}


def _day_key(day) -> str:
    try:
        return str(day.strftime("%Y-%m-%d"))
    except Exception:
        return str(day)


def begin_render():
    """Fresh display-only identity memo for each Streamlit PRA render."""
    _IDENTITY_MEMO.clear()
    install()


def _player_id(day, row: dict):
    key = _day_key(day)
    if key not in _IDENTITY_MEMO:
        try:
            _IDENTITY_MEMO[key] = visual._player_id_lookup(day)
        except Exception:
            _IDENTITY_MEMO[key] = {}
    lookup = _IDENTITY_MEMO.get(key) or {}
    gid = str(row.get("game_id") or "")
    pkey = str(row.get("player_key") or "")
    if not pkey:
        try:
            pkey = final32.market.sgo._norm(str(row.get("player") or ""))
        except Exception:
            pkey = ""
    return lookup.get((gid, pkey))


def _style_bg(url: str) -> str:
    if not url:
        return ""
    safe = str(url).replace("'", "%27").replace('"', "%22")
    return f"background-image:url('{safe}');"


def _card_html_v362(row, rank, day):
    """Existing production card metrics + display-only player/team identity."""
    r = row if isinstance(row, dict) else row.to_dict()
    label = str(r.get("decision_label") or "")
    cls = str(r.get("decision_class") or "strong")
    team_logo = final32._team_logo(day, r.get("team"))

    pid = _player_id(day, r)
    try:
        headshot = visual._headshot_url(pid)
    except Exception:
        headshot = ""

    avatar_style = _style_bg(headshot)
    avatar_fallback = "" if headshot else '<span style="font-size:2rem;opacity:.72">👤</span>'
    logo_html = (
        f'<img src="{escape(team_logo)}" alt="team logo" '
        'style="width:48px;height:48px;object-fit:contain;flex:0 0 48px">'
        if team_logo else
        f'<div style="width:48px;height:48px;border:1px solid #315a78;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#7895aa;font-size:10px;font-weight:900">{escape(str(r.get("team") or "TEAM")[:3].upper())}</div>'
    )

    sims = int(final32._num(r.get("sims"), 0))
    player = escape(str(r.get("player") or "Player"))
    team = escape(str(r.get("team") or ""))
    opponent = escape(str(r.get("opponent") or ""))

    return f'''
<div style="border:1px solid #315a78;background:linear-gradient(145deg,#071a2b,#061420);border-radius:20px;padding:16px;margin:7px 0 4px;min-height:330px;overflow:hidden">
  <div style="font-size:9px;letter-spacing:1.1px;color:#65dfff;font-weight:900">🏆 DAILY #{rank} • PRA OVER</div>
  <div style="margin:8px 0"><span style="{final32._badge_style(cls)}">{escape(label)}</span></div>

  <div style="display:flex;align-items:center;gap:13px;margin-top:9px;min-width:0">
    <div style="width:76px;height:76px;min-width:76px;border-radius:50%;background-color:#102a3d;background-size:cover;background-position:center top;border:1px solid #2c7598;display:flex;align-items:center;justify-content:center;overflow:hidden;{avatar_style}">{avatar_fallback}</div>
    <div style="min-width:0;flex:1">
      <div style="font-size:22px;font-weight:1000;color:#fff;line-height:1.12">{player}</div>
      <div style="font-size:11px;color:#8ca6ba;margin-top:5px;line-height:1.35">{team} vs {opponent}</div>
      <div style="font-size:8px;letter-spacing:.65px;color:#557d98;font-weight:850;margin-top:6px">ESPN WNBA PLAYER IMAGE • VERIFIED SLATE TEAM IDENTITY</div>
    </div>
    {logo_html}
  </div>

  <div style="font-size:13px;color:#fff;margin-top:13px">OVER {float(final32._num(r.get('line'),0.0)):g} PRA • {escape(str(r.get('book') or ''))} {final32._fmt_odds(r.get('over_odds'))}</div>
  <div style="font-size:34px;font-weight:1000;color:#62dcff;margin-top:12px">{final32._fmt_pct(r.get('model_over'))}</div>
  <div style="font-size:8px;letter-spacing:.8px;color:#7d9aaf;font-weight:800">TRUE MC OVER PROBABILITY</div>
  <div style="border-left:4px solid #55d8ff;background:#062033;border-radius:8px;padding:9px 10px;margin-top:10px;font-size:11px;color:#c1d2df">Adj PRA {float(final32._num(r.get('projection'),0.0)):.2f} • MC mean {float(final32._num(r.get('sim_mean'),0.0)):.2f} • Median {float(final32._num(r.get('sim_median'),0.0)):g} • 10–90 {float(final32._num(r.get('p10'),0.0)):g}–{float(final32._num(r.get('p90'),0.0)):g}</div>
  <div style="border:1px solid #31536a;border-radius:10px;padding:9px 10px;margin-top:9px;font-size:10px;color:#c2d2df">No-vig {final32._fmt_pct(r.get('no_vig_over'))} • Edge {final32._fmt_pp(r.get('edge'))} • Fair {final32._fmt_odds(r.get('fair_over'))}</div>
  <div style="font-size:30px;font-weight:1000;color:#fff;margin-top:12px">{float(final32._num(r.get('decision_strength'),0.0)):.1f}<span style="font-size:8px;color:#7895aa"> /100 FINAL CARD STRENGTH</span></div>
  <div style="font-size:9px;color:#7f9aaf;margin-top:8px">{sims:,} sims • {int(final32._num(r.get('batches'),0))} batches • MC SE {100*final32._num(r.get('mc_se'),0.0):.4f} pp • {escape(str(r.get('pass_source') or '5M'))}</div>
</div>'''


def install():
    """Patch only the existing Step-9 Final Card HTML renderer."""
    if getattr(final32, "_v362_final_identity_installed", False):
        return
    if not hasattr(final32, "_v362_original_card_html"):
        final32._v362_original_card_html = final32._card_html
    final32._card_html = _card_html_v362
    final32._v362_final_identity_installed = True


__all__ = ["MODEL_VERSION", "begin_render", "install"]
