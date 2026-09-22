"""WNBA PRA V3.6.3 — presentation-only Step-5 Top-5 identity layer.

Adds ESPN WNBA player headshots plus verified slate team/opponent logos to the
existing V2.8 Minutes + Role PRA Top 5. The underlying Step-5 candidate pool,
projection values, ordering, availability/minutes/usage logic and every later PRA
market/Monte Carlo/final-card rule remain unchanged.

Identity is resolved only while rendering the already-selected five rows. Player
IDs reuse the projection identity resolver already proven by the Step-6 visual
board; team logos reuse the verified selected-slate metadata. No sportsbook call,
new simulation or model feature is introduced.
"""
from __future__ import annotations

from html import escape

import streamlit as st

import wnba_pra_hub_v28 as v28
import wnba_pra_visual_v352 as visual

MODEL_VERSION = "PRA V3.6.3 • STEP-5 TOP-5 IDENTITY • MODEL PRESERVED"

_IDENTITY_MEMO = {}


def _day_key(day) -> str:
    try:
        return str(day.strftime("%Y-%m-%d"))
    except Exception:
        return str(day or "")


def _player_key(name: str) -> str:
    try:
        return str(visual.base.sgo._norm(str(name or "")))
    except Exception:
        return visual._norm(str(name or ""))


def _identity_maps(day):
    """Build display-only name/team lookups once for this PRA render."""
    key = _day_key(day)
    if key in _IDENTITY_MEMO:
        return _IDENTITY_MEMO[key]

    # Player IDs come from the same PRA projection identity path already used by
    # the verified Step-6 preliminary visual cards. Collapse game-keyed entries
    # by normalized player name because one WNBA player appears in one slate game.
    player_ids = {}
    try:
        keyed = visual._player_id_lookup(day) or {}
        for (_gid, pkey), pid in keyed.items():
            if pkey and pid is not None and str(pkey) not in player_ids:
                player_ids[str(pkey)] = pid
    except Exception:
        player_ids = {}

    # Team metadata comes only from the already-selected verified slate. Add
    # aliases for both full team name and tricode so legacy Step-5 rows that carry
    # an abbreviation still resolve to the exact same team identity.
    teams = {}
    try:
        raw = visual._team_meta(day) or {}
        for _raw_key, meta in raw.items():
            if not isinstance(meta, dict):
                continue
            name = str(meta.get("name") or "")
            tri = str(meta.get("tricode") or "")
            for alias in (name, tri, _raw_key):
                norm = visual._norm(alias)
                if norm:
                    teams[norm] = meta
    except Exception:
        teams = {}

    _IDENTITY_MEMO[key] = (player_ids, teams)
    return _IDENTITY_MEMO[key]


def _team_meta(teams, label: str):
    return teams.get(visual._norm(label), {}) if isinstance(teams, dict) else {}


def _logo_html(meta: dict, fallback: str, title: str):
    url = str((meta or {}).get("logo") or "")
    abbr = str((meta or {}).get("tricode") or fallback or "TEAM")[:4].upper()
    if url:
        return (
            f'<img src="{escape(url, quote=True)}" alt="{escape(title, quote=True)}" '
            'style="width:30px;height:30px;object-fit:contain;flex:0 0 30px">'
        )
    return (
        '<span style="width:30px;height:30px;border:1px solid #31516e;border-radius:50%;'
        'display:inline-flex;align-items:center;justify-content:center;color:#8ea6bb;'
        f'font-size:8px;font-weight:900;flex:0 0 30px">{escape(abbr)}</span>'
    )


def _headshot_html(pid, player: str):
    try:
        url = visual._headshot_url(pid)
    except Exception:
        url = ""
    if url:
        safe = str(url).replace("'", "%27").replace('"', "%22")
        bg = f"background-image:url('{safe}');"
        fallback = ""
    else:
        bg = ""
        fallback = '<span style="font-size:28px;opacity:.72">👤</span>'
    return (
        '<div style="width:62px;height:62px;min-width:62px;border-radius:50%;'
        'background-color:#102a3d;background-size:cover;background-position:center top;'
        'border:1px solid #2c7598;display:flex;align-items:center;justify-content:center;'
        f'overflow:hidden;{bg}" aria-label="{escape(player, quote=True)} headshot">{fallback}</div>'
    )


def _render_top5_v363(picks):
    """Render the exact inherited Step-5 ranking with identity added only."""
    if not picks:
        st.markdown('<div class="w2-empty">No eligible Step 5 projections are available.</div>', unsafe_allow_html=True)
        return

    day = st.session_state.get("wnba_pra_v2_date")
    player_ids, teams = _identity_maps(day)
    cards = []

    for i, p in enumerate(picks, 1):
        first = " first" if i == 1 else ""
        status = "STARTER" if p["starter"] else p["status"] if p["status"] != "NO DESIGNATION" else "ACTIVE"
        name = str(p.get("name") or "Player")
        team = str(p.get("team") or "")
        opponent = str(p.get("opponent") or "")
        pid = player_ids.get(_player_key(name))
        tm = _team_meta(teams, team)
        om = _team_meta(teams, opponent)

        headshot = _headshot_html(pid, name)
        team_logo = _logo_html(tm, team, f"{team} logo")
        opp_logo = _logo_html(om, opponent, f"{opponent} logo")

        cards.append(
            f'<div class="w28-pick{first}">'
            f'<div class="w28-rank">#{i} STEP-5 PRA • 🖼️ IDENTITY</div>'
            '<div style="display:flex;align-items:center;gap:10px;margin-top:7px;min-width:0">'
            f'{headshot}'
            '<div style="min-width:0;flex:1">'
            f'<div class="w28-name" style="margin-top:0">{escape(name)}</div>'
            '<div style="display:flex;align-items:center;gap:6px;margin-top:6px;min-width:0">'
            f'{team_logo}<span style="color:#8da3b8;font-size:.5rem;font-weight:800">vs</span>{opp_logo}'
            '</div></div></div>'
            f'<div class="w28-meta" style="margin-top:7px">{escape(team)} vs {escape(opponent)} • {escape(status)} • {p["min"]:.1f} MIN</div>'
            f'<div class="w28-pra">{p["pra"]:.1f} <span>Projected PRA</span></div>'
            '<div class="w28-split">'
            f'<div><span>PTS</span><b>{p["p"]:.1f}</b></div>'
            f'<div><span>REB</span><b>{p["r"]:.1f}</b></div>'
            f'<div><span>AST</span><b>{p["a"]:.1f}</b></div>'
            f'<div><span>USG</span><b>{v28._fmt(p["usg"],1)}</b></div>'
            '</div>'
            '<div style="font-size:.4rem;color:#577892;margin-top:7px;letter-spacing:.04em">'
            'ESPN WNBA PLAYER IMAGE • VERIFIED SLATE TEAM / OPPONENT IDENTITY • DISPLAY ONLY'
            '</div></div>'
        )

    st.markdown(
        '<div class="w23-summary"><div class="w23-title">🏆 V2.8 Minutes + Role PRA — Top 5</div>'
        '<div class="w23-sub">First adjusted ranking: current availability, projected team minutes and role/USG changes are active. Player headshots and team/opponent logos are presentation-only. Opponent defensive matchup and sportsbook line grading remain off.</div>'
        f'<div class="w28-topgrid">{"".join(cards)}</div></div>',
        unsafe_allow_html=True,
    )


def begin_render():
    """Fresh display memo and idempotent patch for one PRA page render."""
    _IDENTITY_MEMO.clear()
    install()


def install():
    """Patch only the inherited V2.8 Step-5 Top-5 HTML renderer."""
    if not hasattr(v28, "_v363_original_render_top5"):
        v28._v363_original_render_top5 = v28._render_top5
    v28._render_top5 = _render_top5_v363
    v28._v363_step5_identity_installed = True


__all__ = ["MODEL_VERSION", "begin_render", "install"]
