"""NFL Passing Yards V2 — Step 1 verified matchup + QB identity.

Extends the compact V1 workspace without enabling any betting model. The page
verifies the selected ESPN matchup and resolves both teams' depth-chart QB1
identity with current injury context. A depth-chart QB1 is not treated as
confirmed participation, especially in preseason.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

import nfl_hub_v19 as nfl
import nfl_passing_yards_hub_v1 as prior
import nfl_passing_yards_identity_v1 as identity

MODEL_VERSION = "NFL PASSING YARDS V2 • STEP 1 VERIFIED MATCHUP + QB IDENTITY"

_STEP1_CSS = r"""
<style>
.kpy-step{border:1px solid #264863;background:#081521;border-radius:13px;padding:10px 12px;margin:8px 0}
.kpy-step-title{color:#f7fbff;font-size:.9rem;font-weight:950}.kpy-step-sub{color:#7790a6;font-size:.58rem;margin-top:2px}
.kpy-qbgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0}
.kpy-qb{border:1px solid #294760;background:#091725;border-radius:12px;padding:10px}
.kpy-qbteam{color:#7ff2c2;font-size:.58rem;font-weight:950;text-transform:uppercase}.kpy-qbname{color:#f8fafc;font-size:1rem;font-weight:950;margin-top:4px}
.kpy-qbmeta{color:#8299ad;font-size:.54rem;line-height:1.5;margin-top:5px}.kpy-green{color:#7ff2c2;font-weight:900}.kpy-yellow{color:#f1ca72;font-weight:900}
@media(max-width:700px){.kpy-qbgrid{grid-template-columns:1fr}}
</style>
"""


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _status_label(ctx: dict, preseason: bool) -> tuple[str, str]:
    if not ctx.get("identity_verified"):
        return "CHECK", "Verified depth QB1 not resolved"
    if ctx.get("availability_alert"):
        return "CHECK", "QB1 has a significant current injury designation"
    if preseason:
        return "DEPTH QB1 VERIFIED", "Participation remains unconfirmed for preseason"
    return "QB1 ID VERIFIED", "Depth identity verified; game participation is not assumed"


def _qb_card(ctx: dict, preseason: bool) -> str:
    team = _safe(ctx.get("team"), ctx.get("abbr"))
    qb = ctx.get("qb1") or {}
    qb_name = _safe(qb.get("name"), "Unresolved QB1")
    status, note = _status_label(ctx, preseason)
    injury = _safe(qb.get("injury_status"), "Availability not listed")
    source = _safe(ctx.get("depth_source"), "No verified depth source")
    klass = "kpy-green" if ctx.get("identity_verified") and not ctx.get("availability_alert") else "kpy-yellow"
    return (
        '<div class="kpy-qb">'
        f'<div class="kpy-qbteam">{escape(team)}</div>'
        f'<div class="kpy-qbname">{escape(qb_name)}</div>'
        f'<div class="kpy-qbmeta"><span class="{klass}">{escape(status)}</span><br>'
        f'Injury: {escape(injury)}<br>Source: {escape(source)}<br>{escape(note)}</div>'
        '</div>'
    )


def _qb_room_table(ctx: dict) -> pd.DataFrame:
    rows = []
    verified = ctx.get("depth_state") == "VERIFIED"
    for qb in (ctx.get("qbs") or [])[:4]:
        rank = pd.to_numeric(qb.get("rank"), errors="coerce")
        rows.append({
            "Depth": f"QB{int(rank)}" if verified and pd.notna(rank) else "—",
            "Quarterback": _safe(qb.get("name"), "Unknown"),
            "Injury": _safe(qb.get("injury_status"), "No listed injury"),
            "Source": _safe(qb.get("source"), "—"),
        })
    return pd.DataFrame(rows)


def render_nfl_passing_yards_hub() -> None:
    st.markdown(prior._CSS, unsafe_allow_html=True)
    st.markdown(_STEP1_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="kpy-head">'
        '<div><div class="kpy-title">🏈 NFL <span>Passing Yards</span></div>'
        '<div class="kpy-sub">Step 1 • verified matchup identity + ESPN depth-chart QB1 identity • model still protected/off</div></div>'
        '<div class="kpy-chips"><span class="kpy-chip">STEP 1</span><span class="kpy-chip">QB IDENTITY</span><span class="kpy-chip">MODEL OFF</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    key = "nfl_passing_yards_v2_date"
    if key not in st.session_state:
        st.session_state[key] = datetime.now(nfl.ET).date()

    day = st.date_input(
        "NFL Passing Yards slate date",
        value=st.session_state[key],
        key="nfl_passing_yards_v2_date_input",
        label_visibility="collapsed",
    )
    st.session_state[key] = day
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")

    with st.spinner("Verifying NFL slate…"):
        games, diag = nfl.load_nfl_slate(day_str)

    live = int((games.get("state", pd.Series(dtype=str)).astype(str) == "in").sum()) if not games.empty else 0
    final = int((games.get("state", pd.Series(dtype=str)).astype(str) == "post").sum()) if not games.empty else 0
    upcoming = int((games.get("state", pd.Series(dtype=str)).astype(str) == "pre").sum()) if not games.empty else 0
    st.markdown(
        '<div class="kpy-strip">'
        f'<div class="kpy-stat"><b>{len(games)}</b><span>Games</span></div>'
        f'<div class="kpy-stat"><b>{upcoming}</b><span>Upcoming</span></div>'
        f'<div class="kpy-stat"><b>{live}</b><span>Live</span></div>'
        f'<div class="kpy-stat"><b>{final}</b><span>Final</span></div>'
        f'<div class="kpy-stat"><b>{escape(day_str)}</b><span>ET Slate</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not diag.get("request_ok"):
        st.error("NFL schedule verification failed. No matchup or QB identity is synthesized.")
        return
    if games.empty:
        st.info("No verified NFL games were returned for this ET date.")
        return

    labels = []
    index_by_label = {}
    for idx, row in games.iterrows():
        label = f"{_safe(row.get('away_team'), 'Away')} @ {_safe(row.get('home_team'), 'Home')} • {_safe(row.get('tip_et'), 'TBD')}"
        labels.append(label)
        index_by_label[label] = idx
    chosen = st.selectbox("Verified matchup", labels, key="nfl_passing_yards_v2_matchup")
    game = games.loc[index_by_label[chosen]].to_dict()

    st.markdown(
        '<div class="kpy-step">'
        '<div class="kpy-step-title">✅ Step 1 — Verified Matchup + Quarterback Identity</div>'
        f'<div class="kpy-step-sub">ESPN event {escape(_safe(game.get("game_id"), "—"))} • '
        f'{escape(_safe(game.get("tip_et"), "TBD"))} • {escape(_safe(game.get("venue"), "Venue TBD"))} • '
        f'{escape(_safe(game.get("broadcast"), "—"))}</div></div>',
        unsafe_allow_html=True,
    )

    with st.spinner("Resolving verified QB depth identity…"):
        resolved = identity.resolve_matchup_identity(game, int(pd.to_datetime(day).year))

    preseason = _safe(game.get("season_type")).lower() == "preseason"
    away = resolved.get("away") or {}
    home = resolved.get("home") or {}
    st.markdown(
        f'<div class="kpy-qbgrid">{_qb_card(away, preseason)}{_qb_card(home, preseason)}</div>',
        unsafe_allow_html=True,
    )

    if resolved.get("ready"):
        st.success("✅ STEP 1 IDENTITY GREEN • official matchup ID and both ESPN depth-chart QB1 identities are verified.")
    else:
        st.warning("⚠️ STEP 1 IDENTITY CHECK • " + _safe(resolved.get("reason"), "QB identity unresolved."))

    if preseason:
        st.warning("Preseason guardrail: verified depth QB1 does NOT prove the player will start or play a full game. Participation/rotation stays locked for a later step.")

    if not resolved.get("injury_feed_ok"):
        st.warning("Current ESPN injury feed could not be verified. QB identity can still display, but availability remains CHECK.")

    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"{_safe(away.get('team'), 'Away')} QB room")
        table = _qb_room_table(away)
        if not table.empty:
            st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.info("No verified QB depth rows returned.")
    with c2:
        st.caption(f"{_safe(home.get('team'), 'Home')} QB room")
        table = _qb_room_table(home)
        if not table.empty:
            st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.info("No verified QB depth rows returned.")

    st.caption(
        f"{MODEL_VERSION} • sportsbook influence 0.0% • projection/Monte Carlo/ranking/recommendation OFF • roster fallback never counts as verified QB1."
    )


__all__ = ["MODEL_VERSION", "render_nfl_passing_yards_hub"]
