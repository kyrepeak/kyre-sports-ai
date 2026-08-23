"""WNBA PRA V3.6.6 — Step-5 opponent defensive context presentation layer.

Presentation-only wrapper over the verified V3.6.5 Step-5 identity cards. Reuses
existing cached ESPN WNBA team context already built by V2.6/V2.7: season/L10
points allowed, approximate L10 pace and approximate L10 defensive rating.

The simple matchup grade is derived only from the opponent's season points-allowed
league rank (top third = difficult, middle third = neutral, bottom third =
favorable). It is DISPLAY ONLY and is never written into projections or model
features. Rebounds/assists allowed remain N/A until a separately verified source
is wired; no values are invented.

No PRA projection, availability, minutes/usage, sportsbook, qualification,
Monte Carlo, final-ready, ranking or selection logic is changed.
"""
from __future__ import annotations

from html import escape
import math

import pandas as pd
import streamlit as st

import wnba_pra_step5_identity_v365 as identity
import wnba_pra_step5_identity_v363 as cards
import wnba_context_v26 as context

MODEL_VERSION = "PRA V3.6.6 • STEP-5 OPPONENT DEFENSE CONTEXT • MODEL PRESERVED"

_DEFENSE_MEMO = {}


def _day_key(day) -> str:
    try:
        return pd.to_datetime(day).strftime("%Y-%m-%d")
    except Exception:
        return str(day or "")


def _norm(value) -> str:
    try:
        return cards.visual._norm(str(value or ""))
    except Exception:
        return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _num(value, default=float("nan")):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _fmt(value, digits=1):
    x = _num(value)
    return "N/A" if not math.isfinite(x) else f"{x:.{digits}f}"


def _opponent_context_map(day):
    """Build one display-only defense map for the whole Step-5 board."""
    key = _day_key(day)
    if key in _DEFENSE_MEMO:
        return _DEFENSE_MEMO[key]

    by_alias = {}
    try:
        contexts, _diag = context.slate_context(key)
    except Exception:
        contexts = {}
    try:
        schedule = context.players.schedule_for_date(key)
    except Exception:
        schedule = pd.DataFrame()

    # Season points-allowed league ranks come from the same cached completed-game
    # frame already used by context.slate_context. This adds no new provider.
    pa_rank = {}
    league_teams = 0
    try:
        selected = pd.to_datetime(key)
        season_games = context._season_team_games(int(selected.year))
        if season_games is not None and not season_games.empty:
            season_games = season_games[
                pd.to_datetime(season_games["GAME_DATE"], errors="coerce") < selected
            ].copy()
            grouped = (
                season_games.groupby("TEAM_ID", as_index=True)["PA"]
                .mean()
                .dropna()
                .sort_values(ascending=True)
            )
            league_teams = int(len(grouped))
            for rank, tid in enumerate(grouped.index.tolist(), 1):
                pa_rank[int(tid)] = int(rank)
    except Exception:
        pa_rank = {}
        league_teams = 0

    if schedule is not None and not schedule.empty:
        for _, game in schedule.iterrows():
            gid = str(game.get("game_id") or "")
            game_ctx = contexts.get(gid, {}) if isinstance(contexts, dict) else {}
            for side in ("away", "home"):
                try:
                    tid = int(float(game.get(f"{side}_team_id") or 0))
                except Exception:
                    tid = 0
                name = str(game.get(f"{side}_team") or "")
                abbr = str(
                    game.get(f"{side}_tricode")
                    or game.get(f"{side}_abbr")
                    or name[:3]
                    or ""
                ).upper()
                raw = game_ctx.get(side, {}) if isinstance(game_ctx, dict) else {}
                entry = dict(raw or {})
                entry.update({
                    "TEAM_ID": tid,
                    "TEAM_NAME": name,
                    "TEAM_ABBR": abbr,
                    "PA_RANK": pa_rank.get(tid),
                    "LEAGUE_TEAMS": league_teams,
                    "SOURCE": str(game_ctx.get("source") or "ESPN WNBA cached team context")
                    if isinstance(game_ctx, dict) else "ESPN WNBA cached team context",
                })
                aliases = {name, abbr}
                try:
                    aliases.add(str(raw.get("TEAM_NAME") or ""))
                except Exception:
                    pass
                for alias in aliases:
                    n = _norm(alias)
                    if n:
                        by_alias[n] = entry

    _DEFENSE_MEMO[key] = by_alias
    return by_alias


def _matchup_grade(obj: dict):
    """Display-only tier from season points-allowed league rank."""
    try:
        rank = int(obj.get("PA_RANK") or 0)
        total = int(obj.get("LEAGUE_TEAMS") or 0)
    except Exception:
        rank = total = 0
    if not rank or total < 3:
        return "⚪ N/A", "#9aa9b8"
    if rank <= math.ceil(total / 3):
        return "🔴 Difficult", "#ff9daa"
    if rank > (2 * total / 3):
        return "🟢 Favorable", "#78efba"
    return "🟡 Neutral", "#ffe083"


def _defense_box(obj: dict, opponent: str) -> str:
    obj = obj if isinstance(obj, dict) else {}
    grade, grade_color = _matchup_grade(obj)
    rank = obj.get("PA_RANK")
    total = obj.get("LEAGUE_TEAMS")
    rank_text = f"#{int(rank)}/{int(total)}" if rank and total else "N/A"
    samples = int(_num(obj.get("ADV_GAMES"), 0) or 0)

    def metric(label, value):
        return (
            '<div style="border:1px solid #203a51;border-radius:8px;padding:6px 7px;'
            'background:#07131f;min-width:0">'
            f'<span style="display:block;color:#6f89a0;font-size:.36rem;font-weight:900;'
            f'letter-spacing:.04em">{escape(label)}</span>'
            f'<b style="display:block;color:#eef6ff;font-size:.58rem;margin-top:2px">{escape(value)}</b>'
            '</div>'
        )

    return (
        '<div style="border:1px solid #31536a;background:#071927;border-radius:10px;'
        'padding:8px;margin-top:8px">'
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:6px">'
        f'<b style="color:#dff5ff;font-size:.5rem">🛡️ {escape(opponent)} DEFENSIVE CONTEXT</b>'
        f'<span style="font-size:.45rem;font-weight:950;color:{grade_color};white-space:nowrap">{grade}</span>'
        '</div>'
        '<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;margin-top:6px">'
        f'{metric("DEF RTG L10*", _fmt(obj.get("DRTG_L10"),1))}'
        f'{metric("PACE L10*", _fmt(obj.get("PACE_L10"),1))}'
        f'{metric("PTS ALLOW SZN", _fmt(obj.get("PA"),1))}'
        f'{metric("PTS ALLOW L10", _fmt(obj.get("L10_PA"),1))}'
        f'{metric("REB ALLOW", "N/A")}'
        f'{metric("AST ALLOW", "N/A")}'
        '</div>'
        '<div style="display:flex;justify-content:space-between;gap:6px;align-items:center;margin-top:6px">'
        f'<span style="font-size:.39rem;color:#7892a8">PTS DEF RANK {escape(rank_text)}</span>'
        f'<span style="font-size:.39rem;color:#7892a8">ADV SAMPLE {samples} GP</span>'
        '</div>'
        '<div style="font-size:.34rem;color:#55758e;margin-top:4px;line-height:1.35">'
        'Existing cached ESPN WNBA team context • grade = season points-allowed tier • '
        'display only • *pace/ratings approximate • REB/AST not manufactured'
        '</div></div>'
    )


def _render_top5_v366(picks):
    """Exact inherited Step-5 ranking + identity + display-only defense context."""
    if not picks:
        st.markdown('<div class="w2-empty">No eligible Step 5 projections are available.</div>', unsafe_allow_html=True)
        return

    day = st.session_state.get("wnba_pra_v2_date")
    player_ids, teams = cards._identity_maps(day)
    defenses = _opponent_context_map(day)
    rendered = []

    for i, p in enumerate(picks, 1):
        first = " first" if i == 1 else ""
        status = "STARTER" if p["starter"] else p["status"] if p["status"] != "NO DESIGNATION" else "ACTIVE"
        name = str(p.get("name") or "Player")
        team = str(p.get("team") or "")
        opponent = str(p.get("opponent") or "")
        pid = player_ids.get(cards._player_key(name))
        tm = cards._team_meta(teams, team)
        om = cards._team_meta(teams, opponent)
        defense = defenses.get(_norm(opponent), {})

        headshot = cards._headshot_html(pid, name)
        team_logo = cards._logo_html(tm, team, f"{team} logo")
        opp_logo = cards._logo_html(om, opponent, f"{opponent} logo")
        defense_html = _defense_box(defense, opponent)

        rendered.append(
            f'<div class="w28-pick{first}">'
            f'<div class="w28-rank">#{i} STEP-5 PRA • 🖼️ IDENTITY • 🛡️ DEFENSE</div>'
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
            f'<div><span>USG</span><b>{cards.v28._fmt(p["usg"],1)}</b></div>'
            '</div>'
            f'{defense_html}'
            '<div style="font-size:.4rem;color:#577892;margin-top:7px;letter-spacing:.04em">'
            'ESPN WNBA PLAYER IMAGE • VERIFIED SLATE IDENTITY • OPPONENT DEFENSE DISPLAY ONLY'
            '</div></div>'
        )

    st.markdown(
        '<div class="w23-summary"><div class="w23-title">🏆 V2.8 Minutes + Role PRA — Top 5</div>'
        '<div class="w23-sub">First adjusted ranking: current availability, projected team minutes and role/USG changes are active. Player identity and opponent defensive context are presentation-only. Defensive context does not alter these projections, qualification or ranking.</div>'
        f'<div class="w28-topgrid">{"".join(rendered)}</div></div>',
        unsafe_allow_html=True,
    )


def install():
    """Patch only the inherited V2.8 Step-5 HTML renderer."""
    identity.install()
    cards.v28._render_top5 = _render_top5_v366
    cards.v28._v366_step5_defense_context_installed = True


def begin_render():
    """Fresh presentation memos, retain V3.6.5 identity, install defense cards."""
    cards._IDENTITY_MEMO.clear()
    _DEFENSE_MEMO.clear()
    identity.install()
    install()


__all__ = ["MODEL_VERSION", "begin_render", "install"]
