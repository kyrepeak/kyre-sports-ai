"""MLB 1+ Hit UI V13.3 — full-slate lineup coverage.

MLB 1+ HIT ONLY.

Fixes the early-day scanner problem where only games with already-confirmed batting
orders entered the Top 5. V13.3 reuses the same MLB-only lineup context as the
working Slate page:

1. Current official batting order when MLB has posted it.
2. Otherwise the team's most recent official batting order, clearly PROJECTED.

Projected lineups are never presented as confirmed, receive lower data-confidence,
and are not written into clean calibration history unless the displayed Top 5 are
all confirmed. The underlying V13 hit probability model is unchanged.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import hit_hub_v131 as base
import mlb_schedule_v32 as schedule
from slate_lineup_v204 import build_slate_player_context

UI_VERSION = "V13.3"


def _schedule_banner(frame, diag):
    games = int(len(frame)) if frame is not None else 0
    source = str((diag or {}).get("source") or "unknown")
    day = str((diag or {}).get("date") or schedule.current_selected_date())
    if games:
        st.success(f"⚾ 1+ Hit slate verified • {day} • {games} game(s) • {source}")
    else:
        st.error(f"1+ Hit could not load a verified MLB slate for {day}.")
        attempts = (diag or {}).get("attempts") or []
        if attempts:
            with st.expander("🔧 MLB 1+ Hit schedule diagnostics", expanded=True):
                for item in attempts:
                    provider = item.get("provider", "provider")
                    http = item.get("http")
                    count = item.get("games", 0)
                    size = item.get("bytes", 0)
                    err = item.get("error") or ""
                    st.write(
                        f"**{provider}** • HTTP {http if http is not None else '—'} • "
                        f"{count} games • {size} bytes" + (f" • `{err}`" if err else "")
                    )


def _safe_int(v):
    try:
        return int(v)
    except Exception:
        return None


def _candidate_pool(games_df, include_live=False):
    """Build hitters from confirmed lineups or last-official-lineup projections."""
    out = []
    checked = 0
    usable_games = set()
    confirmed_lineups = 0
    projected_lineups = 0
    confirmed_hitters = 0
    projected_hitters = 0

    if games_df is None or games_df.empty:
        return out, {
            "checked": 0, "usable_games": 0, "confirmed_lineups": 0,
            "projected_lineups": 0, "confirmed_hitters": 0, "projected_hitters": 0,
        }

    try:
        ctx = build_slate_player_context(games_df)
    except Exception:
        ctx = {}

    for _, g in games_df.iterrows():
        if not base.actionable(g.get("status"), include_live):
            continue
        checked += 1
        pk = _safe_int(g.get("game_pk"))
        if pk is None:
            continue
        game_ctx = ctx.get(pk) or {}
        game_had_players = False

        for side in ("away", "home"):
            players = list(game_ctx.get(f"{side}_lineup") or [])[:9]
            if not players:
                continue
            confirmed = bool(game_ctx.get(f"{side}_lineup_confirmed"))
            label = "CONFIRMED" if confirmed else "PROJECTED • LAST OFFICIAL"
            if confirmed:
                confirmed_lineups += 1
            else:
                projected_lineups += 1

            team = g.get("away_team") if side == "away" else g.get("home_team")
            tid = g.get("away_team_id") if side == "away" else g.get("home_team_id")
            opp = g.get("home_team") if side == "away" else g.get("away_team")
            oid = g.get("home_team_id") if side == "away" else g.get("away_team_id")
            sid = g.get("home_pitcher_id") if side == "away" else g.get("away_pitcher_id")
            sname = g.get("home_pitcher") if side == "away" else g.get("away_pitcher")

            for h in players:
                pid = _safe_int(h.get("player_id"))
                spot = _safe_int(h.get("spot")) or _safe_int(h.get("position"))
                if pid is None or spot is None or not 1 <= spot <= 9:
                    continue
                avg = base.sf(h.get("avg"))
                if avg is None or avg <= 0:
                    try:
                        avg = base.sf((base.hitter_stats(pid) or {}).get("avg"))
                    except Exception:
                        avg = None
                if avg is None or avg <= 0:
                    continue

                out.append({
                    "player_id": pid,
                    "player_name": h.get("player_name") or f"Player {pid}",
                    "position": spot,
                    "avg": h.get("avg"),
                    "ops": h.get("ops"),
                    "season_avg": avg,
                    "team": team,
                    "team_id": tid,
                    "opponent": opp,
                    "opponent_team_id": oid,
                    "starter_id": sid,
                    "starter_name": sname,
                    "game_pk": pk,
                    "venue_name": g.get("venue_name"),
                    "status": g.get("status"),
                    "first_pitch": g.get("first_pitch_et"),
                    "team_side": side,
                    "lineup_confirmed": confirmed,
                    "lineup_source": label,
                })
                game_had_players = True
                if confirmed:
                    confirmed_hitters += 1
                else:
                    projected_hitters += 1

        if game_had_players:
            usable_games.add(pk)

    return out, {
        "checked": checked,
        "usable_games": len(usable_games),
        "confirmed_lineups": confirmed_lineups,
        "projected_lineups": projected_lineups,
        "confirmed_hitters": confirmed_hitters,
        "projected_hitters": projected_hitters,
    }


def _downgrade_projected(result):
    """Correct V13's confirmed-lineup confidence input for projected batting orders."""
    if not result or result.get("lineup_confirmed"):
        return result
    result = dict(result)
    result["data_score"] = max(0, int(result.get("data_score", 0) or 0) - 1)
    grade = str(result.get("confidence") or "LOW").upper()
    result["confidence"] = {
        "HIGH": "MEDIUM-HIGH",
        "MEDIUM-HIGH": "MEDIUM",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
    }.get(grade, grade)
    return result


def _pick_html(result, rank):
    sim = result["sim"]
    cls = "hit-pick rank1" if rank == 1 else "hit-pick"
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    source = "✅ CONFIRMED" if result.get("lineup_confirmed") else "🕒 PROJECTED"
    return (
        f'<div class="{cls}">'
        f'<div class="hit-rank">{medal} Rank {rank} • {source}</div>'
        f'<div class="hit-pick-name">{base._e(result.get("player_name"))}</div>'
        f'<div class="hit-pick-meta">{base._e(result.get("team"))} vs {base._e(result.get("opponent"))}<br>'
        f'vs {base._e(result.get("starter_name"))} • Bat #{base._e(result.get("position"))} • {base._e(result.get("first_pitch"))}</div>'
        f'<div class="hit-pick-prob">{sim["p_one_plus"]*100:.1f}%</div>'
        f'<div class="hit-pick-sub">2+ {sim["p_two_plus"]*100:.1f}% • xH {sim["expected_hits"]:.2f}<br>'
        f'90% {sim["scenario_low"]*100:.1f}–{sim["scenario_high"]*100:.1f}% • Data {int(result.get("data_score",0) or 0)}/8</div>'
        f'<div class="hit-conf">{base._e(result.get("confidence","—"))}</div>'
        '</div>'
    )


def _render_top_scanner_v133(games_df):
    st.markdown(
        '<div class="hit-panel"><div class="hit-panel-title"><b>🏆 Daily Top 5 Scanner</b>'
        '<span>confirmed + projected lineups → deep finalists</span></div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1, 1.6])
    with c1:
        include_live = st.checkbox("Include live games", value=False, key="hit133_include_live")
    with c2:
        depth = st.selectbox(
            "Simulation depth",
            ["Fast — 100K/finalist", "Standard — 500K/finalist", "Deep — 1M/finalist"],
            index=1,
            key="hit133_depth",
        )
    sims = {
        "Fast — 100K/finalist": 100_000,
        "Standard — 500K/finalist": 500_000,
        "Deep — 1M/finalist": 1_000_000,
    }[depth]

    if st.button("🔥 SCAN FULL SELECTED SLATE", use_container_width=True, type="primary", key="hit133_scan"):
        if games_df is None or games_df.empty:
            st.error("No verified MLB games are loaded for the selected slate.")
        else:
            with st.spinner("Building confirmed + projected batting orders for every actionable game..."):
                candidates, meta = _candidate_pool(games_df, include_live)
            if not candidates:
                st.warning(f"No usable hitters found across {meta['checked']} actionable game(s).")
            else:
                st.info(
                    f"{len(candidates)} hitters • {meta['usable_games']}/{meta['checked']} actionable games covered • "
                    f"{meta['confirmed_hitters']} confirmed hitters • {meta['projected_hitters']} projected hitters"
                )
                st.caption(
                    "Projected hitters come from each team's most recent official MLB batting order. "
                    "They are labeled PROJECTED and receive lower data confidence until today's lineup is confirmed."
                )

                screened = []
                bar = st.progress(0, text="Screening the full slate...")
                for i, candidate in enumerate(candidates, 1):
                    try:
                        screened.append(base.prescreen(candidate))
                    except Exception:
                        pass
                    bar.progress(i / max(len(candidates), 1), text=f"Screening {i}/{len(candidates)}")
                bar.empty()

                screened.sort(key=lambda x: x.get("screen_p1", 0), reverse=True)
                finalists = screened[: min(12, len(screened))]
                deep = []
                bar = st.progress(0, text="Running deep V13 models across the strongest full-slate finalists...")
                for i, candidate in enumerate(finalists, 1):
                    try:
                        deep.append(_downgrade_projected(base.deep_scan(candidate, sims)))
                    except Exception:
                        pass
                    bar.progress(i / max(len(finalists), 1), text=f"Modeling finalist {i}/{len(finalists)}")
                bar.empty()

                deep.sort(key=lambda x: x["sim"]["p_one_plus"], reverse=True)
                st.session_state["hit133_results"] = deep
                st.session_state["hit133_meta"] = meta

                top5 = deep[:5]
                all_confirmed = bool(top5) and all(bool(x.get("lineup_confirmed")) for x in top5)
                if top5 and not include_live and all_confirmed:
                    added, total, _ = base.save_top5_snapshot(top5, model_version=base.MODEL_VERSION)
                    st.session_state["hit133_save_note"] = f"Clean confirmed-lineup calibration snapshot: {added} new • {total} stored."
                elif include_live:
                    st.session_state["hit133_save_note"] = "Live scans are not saved to calibration history."
                else:
                    st.session_state["hit133_save_note"] = "Calibration snapshot not saved because the Top 5 contains projected lineups."

    st.markdown('</div>', unsafe_allow_html=True)

    results = st.session_state.get("hit133_results") or []
    if results:
        st.markdown(
            '<div class="hit-panel-title"><b>🔥 Strongest 1+ Hit Probabilities</b>'
            '<span>full-slate pure probability ranking</span></div>',
            unsafe_allow_html=True,
        )
        cards = ''.join(_pick_html(r, i) for i, r in enumerate(results[:5], 1))
        st.markdown(f'<div class="hit-top-grid">{cards}</div>', unsafe_allow_html=True)
        note = st.session_state.get("hit133_save_note")
        if note:
            st.caption(note)
        with st.expander("📋 Full finalist details"):
            rows = []
            for r in results:
                s = r["sim"]
                rows.append({
                    "Player": r.get("player_name"),
                    "Team": r.get("team"),
                    "Opp": r.get("opponent"),
                    "Starter": r.get("starter_name"),
                    "Spot": r.get("position"),
                    "Lineup": "CONFIRMED" if r.get("lineup_confirmed") else "PROJECTED",
                    "Time": r.get("first_pitch"),
                    "1+": f"{s['p_one_plus']*100:.1f}%",
                    "2+": f"{s['p_two_plus']*100:.1f}%",
                    "3+": f"{s['p_three_plus']*100:.1f}%",
                    "xH": f"{s['expected_hits']:.2f}",
                    "90% Range": f"{s['scenario_low']*100:.1f}–{s['scenario_high']*100:.1f}%",
                    "Confidence": r.get("confidence"),
                    "Data": f"{r.get('data_score',0)}/8",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.markdown(
            '<div class="hit-empty">Run the full-slate scanner. V13.3 uses confirmed batting orders when posted and otherwise falls back to the team\'s most recent official lineup, clearly labeled PROJECTED.</div>',
            unsafe_allow_html=True,
        )


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    """Render MLB 1+ Hit only, with a fresh slate and full-slate lineup coverage."""
    try:
        day = schedule.current_selected_date()
        fresh_games, diag = schedule.load_with_diagnostics(day)
    except Exception as exc:
        fresh_games = games_df
        diag = {
            "date": str(schedule.current_selected_date()),
            "source": "shared fallback",
            "games": int(len(games_df)) if games_df is not None else 0,
            "attempts": [{"provider": "V13.3 wrapper", "error": f"{type(exc).__name__}: {exc}"}],
        }

    if (fresh_games is None or fresh_games.empty) and games_df is not None and not games_df.empty:
        fresh_games = games_df.copy()
        diag = dict(diag or {})
        diag["source"] = "verified shared MLB fallback"
        diag["games"] = len(fresh_games)

    _schedule_banner(fresh_games, diag)

    # Patch only the scanner renderer inside the 1+ Hit hub for this call.
    old_scanner = base._render_top_scanner
    old_ui = base.UI_VERSION
    try:
        base._render_top_scanner = _render_top_scanner_v133
        base.UI_VERSION = UI_VERSION
        return base.render_hit_hub(fresh_games, section_header, status_info, team_logo, h)
    finally:
        base._render_top_scanner = old_scanner
        base.UI_VERSION = old_ui
