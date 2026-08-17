"""V13.1 MLB 1+ Hit Command Center.

UI/UX upgrade around the existing V13 probability engine. The underlying hit
model is intentionally unchanged. V13.1 adds a mobile-first Top 5 scanner,
cleaner single-player matchup intelligence, persistent projection results,
explicit baseline-only protection when no selected-slate matchup exists, and a
more readable calibration workspace.
"""

from html import escape

import pandas as pd
import requests
import streamlit as st

from engine import (
    ab_for_spot,
    actionable,
    combined,
    confidence,
    deep_scan,
    load_player,
    model_inputs,
    monte,
    odds,
    p_from_avg,
    prescreen,
    sf,
    sim_seed,
    slate_candidates,
    starter_exposure,
)
from history import (
    calibration_metrics,
    calibration_table,
    grade_finished_games,
    history_download_bytes,
    load_history,
    merge_uploaded_history,
    model_version_table,
    save_single_snapshot,
    save_top5_snapshot,
    top5_performance,
)
from schedule_future import current_selected_date

MODEL_VERSION = "V13"
UI_VERSION = "V13.1"

HIT_CSS = r"""
<style>
.hit-hero{background:radial-gradient(circle at 12% 8%,rgba(27,172,255,.15),transparent 32%),linear-gradient(145deg,#0a1a31,#07111f);border:1px solid #21476c;border-radius:22px;padding:20px 22px;margin:4px 0 16px;box-shadow:0 16px 38px rgba(0,0,0,.18)}
.hit-kicker{font-size:.68rem;font-weight:900;letter-spacing:.17em;color:#39ccff;text-transform:uppercase}.hit-title{font-size:2rem;font-weight:950;color:#f5f9ff;margin-top:4px;line-height:1}.hit-sub{color:#91a8c0;margin-top:9px;font-size:.88rem}.hit-pills{display:flex;flex-wrap:wrap;gap:8px;margin-top:13px}.hit-pill{border:1px solid #294965;background:#091827;border-radius:999px;padding:6px 10px;color:#bfd2e3;font-size:.68rem;font-weight:800}.hit-pill b{color:#fff}
.hit-panel{border:1px solid #203b58;background:linear-gradient(145deg,#0c1b2e,#08131f);border-radius:18px;padding:15px 16px;margin:10px 0}.hit-panel-title{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:10px}.hit-panel-title b{font-size:1rem;color:#eef7ff}.hit-panel-title span{font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;color:#6f95b4;font-weight:900}
.hit-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.hit-stat{border:1px solid #213e5d;background:#0a1726;border-radius:14px;padding:11px 12px;min-width:0}.hit-stat span{display:block;color:#7894ad;font-size:.59rem;text-transform:uppercase;letter-spacing:.08em;font-weight:900}.hit-stat b{display:block;color:#f7fbff;font-size:1.2rem;margin-top:5px;overflow:hidden;text-overflow:ellipsis}.hit-stat.good b{color:#72efb4}.hit-stat.cyan b{color:#45d6ff}.hit-stat.warn b{color:#ffe07d}
.hit-player{display:flex;align-items:center;gap:13px}.hit-player-copy{min-width:0}.hit-player-name{font-size:1.45rem;font-weight:950;color:#f8fbff}.hit-player-meta{color:#91a8c0;margin-top:4px;font-size:.78rem}
.hit-matchup{display:grid;grid-template-columns:1.2fr .9fr;gap:10px}.hit-match-card{border:1px solid #224866;background:#091827;border-radius:16px;padding:13px}.hit-match-card .eyebrow{color:#45d7ff;font-size:.58rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase}.hit-match-card .big{color:#f5f9ff;font-size:1.05rem;font-weight:950;margin-top:5px}.hit-match-card .meta{color:#93a8bc;font-size:.71rem;line-height:1.55;margin-top:4px}
.hit-ready{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.hit-ready span{border-radius:999px;padding:4px 7px;font-size:.55rem;font-weight:900;border:1px solid #2d465c;color:#aebfd0;background:#101d2a}.hit-ready .yes{background:#0b3427;border-color:#1a6549;color:#79eeb7}.hit-ready .no{background:#32181c;border-color:#653038;color:#f5a7ad}
.hit-baseline{border:1px solid #6b5920;background:#2d280d;border-radius:14px;padding:12px 13px;color:#f6e7a6;font-size:.74rem;line-height:1.55;margin:9px 0}.hit-baseline b{color:#fff0ad}
.hit-result{background:radial-gradient(circle at 83% 13%,rgba(50,221,255,.13),transparent 30%),linear-gradient(145deg,#0b2039,#081522);border:1px solid #29719b;border-radius:20px;padding:17px 18px;margin:13px 0}.hit-result-top{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.hit-result-player{font-size:1.25rem;font-weight:950;color:#fff}.hit-result-match{font-size:.72rem;color:#8fa8bd;margin-top:4px}.hit-prob{font-size:3.1rem;line-height:.95;font-weight:1000;color:#fff;text-align:right}.hit-prob-label{text-align:right;color:#7f9ab2;font-size:.65rem;margin-top:5px}.hit-badge{display:inline-flex;border-radius:999px;padding:4px 8px;font-size:.55rem;font-weight:950;margin-top:8px}.hit-badge.high{background:#0b3b2b;color:#77efb7;border:1px solid #176448}.hit-badge.medium-high,.hit-badge.medium{background:#49390c;color:#ffe27b;border:1px solid #765c1b}.hit-badge.low{background:#3d1820;color:#ff9ca7;border:1px solid #71313a}
.hit-result-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:14px}.hit-mini{border:1px solid #22425e;background:#081522;border-radius:12px;padding:9px}.hit-mini span{display:block;color:#7591a8;font-size:.52rem;text-transform:uppercase;font-weight:900;letter-spacing:.06em}.hit-mini b{display:block;color:#f5fbff;font-size:.95rem;margin-top:4px}.hit-move{margin-top:10px;border-left:3px solid #35cbff;background:#081a29;padding:8px 10px;color:#a7bbcc;font-size:.67rem}.hit-move strong{color:#eaf7ff}
.hit-top-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:10px 0 13px}.hit-pick{position:relative;border:1px solid #24455e;background:linear-gradient(155deg,#0d1c2d,#08131f);border-radius:16px;padding:13px;min-width:0}.hit-pick.rank1{border-color:#a98a13;box-shadow:inset 3px 0 #c9a514}.hit-rank{font-size:.58rem;color:#49d4ff;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.hit-pick-name{font-size:.96rem;font-weight:950;color:#fff;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hit-pick-meta{font-size:.63rem;color:#8fa5b9;line-height:1.5;margin-top:4px;min-height:39px}.hit-pick-prob{font-size:2rem;font-weight:1000;color:#fff;margin-top:8px}.hit-pick-sub{font-size:.59rem;color:#91a6b8;line-height:1.55;margin-top:4px}.hit-conf{display:inline-flex;border-radius:999px;padding:3px 7px;background:#0a3326;color:#7aefb8;border:1px solid #1b6349;font-size:.51rem;font-weight:950;margin-top:7px}
.hit-backtest{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:10px 0}.hit-empty{border:1px dashed #31506a;background:#081522;border-radius:14px;padding:13px;color:#8ea6ba;font-size:.7rem}
@media(max-width:1000px){.hit-top-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hit-result-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.hit-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:700px){.hit-title{font-size:1.55rem}.hit-matchup{grid-template-columns:1fr}.hit-result-top{display:block}.hit-prob{text-align:left;margin-top:12px;font-size:2.7rem}.hit-prob-label{text-align:left}.hit-top-grid{grid-template-columns:1fr}.hit-result-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hit-backtest{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _e(v):
    return escape(str(v if v is not None else "—"))


def _selected_date():
    try:
        return current_selected_date()
    except Exception:
        return "Selected slate"


def _hero():
    day = _selected_date()
    st.markdown(
        '<div class="hit-hero">'
        '<div class="hit-kicker">KYRE SPORTS AI • MLB HIT PROBABILITY LAB</div>'
        '<div class="hit-title">⚾ 1+ Hit Command Center</div>'
        '<div class="hit-sub">Pure hit probability — season skill, handedness, starter quality, recent form, Statcast, bullpen exposure, park/weather and Monte Carlo uncertainty.</div>'
        '<div class="hit-pills">'
        f'<div class="hit-pill">📅 Slate <b>{_e(day)}</b></div>'
        '<div class="hit-pill">🧠 Model <b>V13</b></div>'
        '<div class="hit-pill">✨ UI <b>V13.1</b></div>'
        '<div class="hit-pill">🎯 Ranking <b>Probability, not price</b></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def _readiness(data):
    checks = [
        ("Season", bool(data.get("stats"))),
        ("Matchup", bool(data.get("matchup"))),
        ("Starter", bool(data.get("pitcher"))),
        ("Hand split", bool(data.get("split_r") or data.get("split_l"))),
        ("Recent", bool(data.get("recent"))),
        ("Park", bool(data.get("environment"))),
        ("Statcast", bool(data.get("statcast"))),
        ("Bullpen", bool(data.get("bullpen"))),
    ]
    return ''.join(
        f'<span class="{"yes" if ok else "no"}">{"✓" if ok else "–"} {_e(label)}</span>'
        for label, ok in checks
    )


def _top_pick_html(result, rank):
    sim = result["sim"]
    cls = "hit-pick rank1" if rank == 1 else "hit-pick"
    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "•"
    return (
        f'<div class="{cls}">'
        f'<div class="hit-rank">{medal} Rank {rank}</div>'
        f'<div class="hit-pick-name">{_e(result.get("player_name"))}</div>'
        f'<div class="hit-pick-meta">{_e(result.get("team"))} vs {_e(result.get("opponent"))}<br>vs {_e(result.get("starter_name"))} • Bat #{_e(result.get("position"))}</div>'
        f'<div class="hit-pick-prob">{sim["p_one_plus"]*100:.1f}%</div>'
        f'<div class="hit-pick-sub">2+ {sim["p_two_plus"]*100:.1f}% • xH {sim["expected_hits"]:.2f}<br>90% {sim["scenario_low"]*100:.1f}–{sim["scenario_high"]*100:.1f}% • Data {int(result.get("data_score",0) or 0)}/8</div>'
        f'<div class="hit-conf">{_e(result.get("confidence","—"))}</div>'
        '</div>'
    )


def _render_top_scanner(games_df):
    st.markdown('<div class="hit-panel"><div class="hit-panel-title"><b>🏆 Daily Top 5 Scanner</b><span>confirmed lineups → deep finalists</span></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1.6])
    with c1:
        include_live = st.checkbox("Include live games", value=False, key="hit131_include_live")
    with c2:
        depth = st.selectbox(
            "Simulation depth",
            ["Fast — 100K/finalist", "Standard — 500K/finalist", "Deep — 1M/finalist"],
            index=1,
            key="hit131_depth",
        )
    sims = {"Fast — 100K/finalist": 100_000, "Standard — 500K/finalist": 500_000, "Deep — 1M/finalist": 1_000_000}[depth]
    if st.button("🔥 SCAN SELECTED SLATE", use_container_width=True, type="primary", key="hit131_scan"):
        if games_df is None or games_df.empty:
            st.error("No verified MLB games are loaded for the selected slate.")
        else:
            with st.spinner("Reading confirmed batting orders..."):
                candidates, checked, with_lineups = slate_candidates(games_df, include_live)
            if not candidates:
                st.warning(f"No confirmed hitters found across {checked} actionable game(s). Future lineups may not be posted yet.")
            else:
                st.info(f"{len(candidates)} confirmed hitters • {with_lineups}/{checked} actionable games with lineups")
                screened = []
                bar = st.progress(0, text="Screening hitters...")
                for i, candidate in enumerate(candidates, 1):
                    try:
                        screened.append(prescreen(candidate))
                    except Exception:
                        pass
                    bar.progress(i / max(len(candidates), 1), text=f"Screening {i}/{len(candidates)}")
                bar.empty()
                screened.sort(key=lambda x: x.get("screen_p1", 0), reverse=True)
                finalists = screened[: min(8, len(screened))]
                deep = []
                bar = st.progress(0, text="Running deep V13 finalist models...")
                for i, candidate in enumerate(finalists, 1):
                    try:
                        deep.append(deep_scan(candidate, sims))
                    except Exception:
                        pass
                    bar.progress(i / max(len(finalists), 1), text=f"Modeling finalist {i}/{len(finalists)}")
                bar.empty()
                deep.sort(key=lambda x: x["sim"]["p_one_plus"], reverse=True)
                st.session_state["hit131_results"] = deep
                if deep and not include_live:
                    added, total, _ = save_top5_snapshot(deep[:5], model_version=MODEL_VERSION)
                    st.session_state["hit131_save_note"] = f"Pregame calibration snapshot: {added} new • {total} stored."
                elif include_live:
                    st.session_state["hit131_save_note"] = "Live scans are not saved to calibration history."
    st.markdown('</div>', unsafe_allow_html=True)

    results = st.session_state.get("hit131_results") or []
    if results:
        st.markdown('<div class="hit-panel-title"><b>🔥 Strongest 1+ Hit Probabilities</b><span>pure probability ranking</span></div>', unsafe_allow_html=True)
        cards = ''.join(_top_pick_html(r, i) for i, r in enumerate(results[:5], 1))
        st.markdown(f'<div class="hit-top-grid">{cards}</div>', unsafe_allow_html=True)
        note = st.session_state.get("hit131_save_note")
        if note:
            st.caption(note)
        with st.expander("📋 Full finalist details"):
            rows = []
            for r in results:
                s = r["sim"]
                rows.append({
                    "Player": r.get("player_name"), "Team": r.get("team"), "Opp": r.get("opponent"),
                    "Starter": r.get("starter_name"), "Spot": r.get("position"),
                    "1+": f"{s['p_one_plus']*100:.1f}%", "2+": f"{s['p_two_plus']*100:.1f}%",
                    "3+": f"{s['p_three_plus']*100:.1f}%", "xH": f"{s['expected_hits']:.2f}",
                    "90% Range": f"{s['scenario_low']*100:.1f}–{s['scenario_high']*100:.1f}%",
                    "Confidence": r.get("confidence"), "Data": f"{r.get('data_score',0)}/8",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.markdown('<div class="hit-empty">Run the selected-slate scanner to build the Top 5. Confirmed batting orders are required by default so the ranking is not built on guessed lineup spots.</div>', unsafe_allow_html=True)


def _player_header(data, team_logo):
    player = data["player"]
    stats = data["stats"]
    logo = team_logo(player.get("team_id"))
    recent = data.get("recent") or {}
    recent_avg = recent.get("avg")
    st.markdown(
        '<div class="hit-panel">'
        '<div class="hit-player">'
        f'{logo}<div class="hit-player-copy"><div class="hit-player-name">{_e(player.get("name"))}</div>'
        f'<div class="hit-player-meta">{_e(player.get("team_name"))} • Bats {_e(player.get("bat_side"))} • {_e(stats.get("season"))}</div></div></div>'
        '<div class="hit-grid" style="margin-top:13px">'
        f'<div class="hit-stat cyan"><span>Season AVG</span><b>{_e(stats.get("avg"))}</b></div>'
        f'<div class="hit-stat"><span>OPS</span><b>{_e(stats.get("ops"))}</b></div>'
        f'<div class="hit-stat"><span>Hits</span><b>{_e(stats.get("hits"))}</b></div>'
        f'<div class="hit-stat"><span>Last-10 AVG</span><b>{f"{recent_avg:.3f}" if recent_avg is not None else "—"}</b></div>'
        '</div>'
        f'<div class="hit-ready">{_readiness(data)}</div>'
        '</div>', unsafe_allow_html=True,
    )


def _matchup_panel(data, status_info):
    m = data.get("matchup")
    p = data.get("pitcher")
    if not m:
        st.markdown(
            f'<div class="hit-baseline"><b>⚠️ No matchup on {_e(_selected_date())}.</b> This player is not attached to a game on the selected MLB slate. Game-specific starter, bullpen and park layers are unavailable, so a projection can only be run as a clearly labeled season/recent-form baseline.</div>',
            unsafe_allow_html=True,
        )
        return
    status_label, _ = status_info(m.get("status"))
    hand = (p or {}).get("hand", "—")
    split = data.get("split_r") if hand == "R" else data.get("split_l") if hand == "L" else None
    env = data.get("environment") or {}
    starter_meta = "Starter TBD"
    if p:
        starter_meta = f"ERA {p.get('era','—')} • WHIP {p.get('whip','—')} • K/9 {p.get('k9',0):.2f}" if p.get("k9") is not None else f"ERA {p.get('era','—')} • WHIP {p.get('whip','—')}"
    split_meta = f"Batter vs {hand}HP: AVG {split.get('avg','—')} • OPS {split.get('ops','—')}" if split else "Handedness split unavailable"
    weather = f"{env.get('temperature'):.0f}°F • {env.get('condition','—')}" if env.get("temperature") is not None else env.get("condition", "Weather unavailable")
    st.markdown(
        '<div class="hit-matchup">'
        '<div class="hit-match-card"><div class="eyebrow">Selected-slate matchup</div>'
        f'<div class="big">{_e(data["player"].get("team_name"))} vs {_e(m.get("opponent"))}</div>'
        f'<div class="meta">📍 {_e(m.get("venue_name"))} • 🕒 {_e(m.get("first_pitch"))} • {_e(status_label)}<br>🌤️ {_e(weather)}</div></div>'
        '<div class="hit-match-card"><div class="eyebrow">Opposing starter</div>'
        f'<div class="big">{_e((p or {}).get("name", m.get("pitcher","TBD")))} • {_e(hand)}HP</div>'
        f'<div class="meta">{_e(starter_meta)}<br>{_e(split_meta)}</div></div>'
        '</div>', unsafe_allow_html=True,
    )


def _result_html(data, result):
    sim = result["sim"]
    player = data["player"]
    m = data.get("matchup") or {}
    grade = result["grade"]
    cls = grade.lower().replace(" ", "-")
    baseline = result["baseline_p1"]
    delta = sim["p_one_plus"] - baseline
    matchup = m.get("opponent") or "baseline only — no selected-slate opponent"
    return (
        '<div class="hit-result">'
        '<div class="hit-result-top"><div>'
        f'<div class="hit-result-player">{_e(player.get("name"))}</div>'
        f'<div class="hit-result-match">{_e(player.get("team_name"))} vs {_e(matchup)} • Bat #{result["spot"]} • {result["expected_ab"]:.1f} projected AB</div>'
        f'<span class="hit-badge {cls}">{_e(grade)} CONFIDENCE • DATA {result["score"]}/8</span>'
        '</div><div>'
        f'<div class="hit-prob">{sim["p_one_plus"]*100:.1f}%</div><div class="hit-prob-label">PROJECTED 1+ HIT PROBABILITY</div>'
        '</div></div>'
        '<div class="hit-result-grid">'
        f'<div class="hit-mini"><span>Expected Hits</span><b>{sim["expected_hits"]:.2f}</b></div>'
        f'<div class="hit-mini"><span>0 Hits</span><b>{sim["p_zero"]*100:.1f}%</b></div>'
        f'<div class="hit-mini"><span>Exactly 1</span><b>{sim["p_exact_one"]*100:.1f}%</b></div>'
        f'<div class="hit-mini"><span>2+ Hits</span><b>{sim["p_two_plus"]*100:.1f}%</b></div>'
        f'<div class="hit-mini"><span>3+ Hits</span><b>{sim["p_three_plus"]*100:.1f}%</b></div>'
        f'<div class="hit-mini"><span>Fair 1+</span><b>{_e(odds(sim["p_one_plus"]))}</b></div>'
        '</div>'
        f'<div class="hit-move"><strong>Model movement:</strong> season AVG + projected AB baseline {baseline*100:.1f}% → final {sim["p_one_plus"]*100:.1f}% ({delta*100:+.1f} pts). 90% scenario range {sim["scenario_low"]*100:.1f}–{sim["scenario_high"]*100:.1f}%.</div>'
        '</div>'
    )


def _render_analyzer(games_df, team_logo, status_info):
    st.markdown('<div class="hit-panel"><div class="hit-panel-title"><b>🔎 Single-Player Analyzer</b><span>selected slate aware</span></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([2.4, 1])
    with c1:
        name = st.text_input("Player", placeholder="Yordan Alvarez", label_visibility="collapsed", key="hit131_player_name")
    with c2:
        load = st.button("📡 LOAD PLAYER", use_container_width=True, key="hit131_load")
    if load:
        st.session_state.pop("hit131_player", None)
        st.session_state.pop("hit131_projection", None)
        if not name.strip():
            st.error("Enter a player name.")
        else:
            try:
                with st.spinner("Loading hitter • selected-slate matchup • Statcast • bullpen..."):
                    data = load_player(name, games_df)
                if data and data.get("stats"):
                    st.session_state["hit131_player"] = data
                elif data:
                    st.error("Player found, but current-season hitting stats are unavailable.")
                else:
                    st.error("Player not found.")
            except requests.RequestException as exc:
                st.error(f"Could not load MLB data: {exc}")
    st.markdown('</div>', unsafe_allow_html=True)

    data = st.session_state.get("hit131_player")
    if not data:
        st.markdown('<div class="hit-empty">Search a hitter to load season performance, recent form, selected-slate opponent, probable starter, handedness splits, Statcast, bullpen and park/weather context.</div>', unsafe_allow_html=True)
        return

    _player_header(data, team_logo)
    _matchup_panel(data, status_info)

    recent = data.get("recent") or {}
    sc = data.get("statcast") or {}
    bp = data.get("bullpen") or {}
    with st.expander("🔥 Recent form + Statcast", expanded=False):
        rows = [
            ("L10 AVG", f"{recent.get('avg'):.3f}" if recent.get("avg") is not None else "—"),
            ("L10 Hit Games", f"{recent.get('hit_games','—')}/{recent.get('games','—')}"),
            ("xBA", f"{sc.get('xba'):.3f}" if sc.get("xba") is not None else "—"),
            ("Exit Velo", f"{sc.get('avg_ev'):.1f}" if sc.get("avg_ev") is not None else "—"),
            ("Hard-Hit", f"{sc.get('hard_hit_rate')*100:.1f}%" if sc.get("hard_hit_rate") is not None else "—"),
            ("Barrel", f"{sc.get('barrel_rate')*100:.1f}%" if sc.get("barrel_rate") is not None else "—"),
            ("Bullpen ERA", f"{bp.get('era'):.2f}" if bp.get("era") is not None else "—"),
            ("Bullpen WHIP", f"{bp.get('whip'):.2f}" if bp.get("whip") is not None else "—"),
        ]
        st.markdown('<div class="hit-grid">' + ''.join(f'<div class="hit-stat"><span>{_e(k)}</span><b>{_e(v)}</b></div>' for k,v in rows) + '</div>', unsafe_allow_html=True)

    confirmed = data.get("confirmed_lineup")
    estimated = data.get("recent_lineup")
    projected = int(confirmed) if confirmed else int(estimated["position"]) if estimated else 4
    source = "✅ Confirmed batting order" if confirmed else f"🕒 Recent estimate ({estimated['sample_games']} games)" if estimated else "⚠️ Manual fallback"
    m = data.get("matchup")

    st.markdown('<div class="hit-panel"><div class="hit-panel-title"><b>🎛️ Projection Controls</b><span>' + _e(source) + '</span></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        spot = st.selectbox("Batting spot", list(range(1,10)), index=max(0,min(8,projected-1)), key="hit131_spot")
    with c2:
        expected_ab = st.number_input("Projected AB", 2.5, 6.0, float(ab_for_spot(spot)), 0.1, key="hit131_ab")
    with c3:
        mode = st.selectbox("Simulation size", ["Quick — 500K", "Standard — 5M", "Deep — 10M"], index=1, key="hit131_sim")
    sim_n = {"Quick — 500K":500_000,"Standard — 5M":5_000_000,"Deep — 10M":10_000_000}[mode]
    allow_baseline = True
    if not m:
        allow_baseline = st.checkbox("I understand this is a baseline-only projection, not a current game prop", value=False, key="hit131_baseline_ok")
    run = st.button("🔥 RUN DEEP HIT PROJECTION", use_container_width=True, type="primary", disabled=(not m and not allow_baseline), key="hit131_run")
    st.markdown('</div>', unsafe_allow_html=True)

    if run:
        player = data["player"]; stats = data["stats"]
        base = sf(stats.get("avg"), 0) or 0
        model = model_inputs(base, spot, m, data.get("pitcher"), data.get("split_r"), data.get("split_l"), data.get("recent"), data.get("environment"), data.get("statcast"), data.get("bullpen"))
        exposure = starter_exposure(data.get("pitcher"), expected_ab)
        deterministic = combined(model["starter_rate"], model["bullpen_rate"], exposure["starter_ab"], exposure["bullpen_ab"])
        seed = sim_seed(player["id"], (m or {}).get("game_pk",0))
        with st.spinner(f"Running {sim_n:,} Monte Carlo simulations..."):
            sim = monte(
                model["starter_rate"], model["bullpen_rate"], expected_ab, exposure["starter_share"],
                model["split_weight"], model["statcast_model"].get("reliability",0),
                model["pitcher_quality"].get("reliability",0) if model["pitcher_quality"] else 0,
                model["bullpen_quality"].get("reliability",0) if model["bullpen_quality"] else 0,
                sim_n, seed,
            )
        grade, score = confidence(stats, data.get("pitcher"), model.get("starter_split"), data.get("recent"), data.get("confirmed_lineup"), data.get("environment"), data.get("statcast"), data.get("bullpen"), sim)
        baseline = p_from_avg(base, expected_ab)
        result = {"sim":sim,"grade":grade,"score":score,"spot":spot,"expected_ab":expected_ab,"baseline_p1":baseline["p_one_plus"],"model":model,"exposure":exposure,"deterministic":deterministic}
        st.session_state["hit131_projection"] = result

        if m and actionable(m.get("status"), include_live=False):
            added, total = save_single_snapshot(player, m, data.get("pitcher"), spot, expected_ab, sim, grade, score, model_version=MODEL_VERSION)
            st.session_state["hit131_history_note"] = f"Pregame calibration history: {'saved' if added else 'already stored'} • {total} row(s)."
        else:
            st.session_state["hit131_history_note"] = "Baseline/live/final projection not saved to calibration history."

    result = st.session_state.get("hit131_projection")
    if result:
        st.markdown(_result_html(data, result), unsafe_allow_html=True)
        model = result["model"]; exposure = result["exposure"]; sim = result["sim"]
        with st.expander("🧠 Model stack", expanded=False):
            vals = [
                ("Season AVG", f"{sf(data['stats'].get('avg'),0):.3f}"),
                ("Starter Rate", f"{model['starter_rate']:.3f}"),
                ("Bullpen Rate", f"{model['bullpen_rate']:.3f}"),
                ("Starter Exposure", f"{exposure['starter_share']*100:.0f}%"),
                ("Recent Adj", f"{(model['recent_model']-model['pitcher_avg'])*100:+.1f} pts"),
                ("Environment", f"{model['env_model']['total_adjustment']*100:+.1f}%"),
                ("Contact", f"{model['statcast_model']['quality_adjustment']*100:+.1f}%"),
                ("Deterministic 1+", f"{result['deterministic']['p_one_plus']*100:.1f}%"),
            ]
            st.markdown('<div class="hit-grid">' + ''.join(f'<div class="hit-stat"><span>{_e(k)}</span><b>{_e(v)}</b></div>' for k,v in vals) + '</div>', unsafe_allow_html=True)
        with st.expander("🎲 Simulation diagnostics", expanded=False):
            vals = [
                ("Simulations", f"{sim['simulations']:,}"),("Batches",sim['batches']),("Convergence","PASS" if sim['converged'] else "CHECK"),("MC SE",f"{sim['mc_se']*100:.3f} pts"),
                ("Batch Spread",f"{sim['batch_range']*100:.2f} pts"),("90% Range",f"{sim['scenario_low']*100:.1f}–{sim['scenario_high']*100:.1f}%"),("Median Hits",sim['median_hits']),("Mode Hits",sim['mode_hits']),
            ]
            st.markdown('<div class="hit-grid">' + ''.join(f'<div class="hit-stat"><span>{_e(k)}</span><b>{_e(v)}</b></div>' for k,v in vals) + '</div>', unsafe_allow_html=True)
        st.caption(st.session_state.get("hit131_history_note", ""))


def _render_backtest():
    st.markdown('<div class="hit-panel"><div class="hit-panel-title"><b>📈 Prediction History & Calibration</b><span>clean pregame grading only</span></div>', unsafe_allow_html=True)
    history = load_history()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 GRADE FINISHED GAMES", use_container_width=True, type="primary", key="hit131_grade"):
            with st.spinner("Checking official MLB box scores..."):
                summary = grade_finished_games()
            st.success(f"Graded {summary['graded']} • DNP {summary['dnp']} • Void {summary['void']} • Pending {summary['still_pending']}")
            history = load_history()
    with c2:
        if not history.empty:
            st.download_button("⬇️ DOWNLOAD HISTORY CSV", data=history_download_bytes(history), file_name="kyre_sports_ai_v13_history.csv", mime="text/csv", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if history.empty:
        st.markdown('<div class="hit-empty">No clean pregame history yet. Run a pregame Top 5 scan or a pregame single-player projection first.</div>', unsafe_allow_html=True)
    else:
        metrics = calibration_metrics(history); top5 = top5_performance(history)
        pending = int(history["grade_status"].fillna("PENDING").eq("PENDING").sum())
        vals = [
            ("Stored",len(history)),("Graded",metrics["graded"]),("Pending",pending),("Actual Hit Rate",f"{metrics['hit_rate']*100:.1f}%" if metrics["graded"] else "—"),
            ("Avg Projected",f"{metrics['avg_prediction']*100:.1f}%" if metrics["graded"] else "—"),("Calibration Gap",f"{metrics['calibration_gap']*100:+.1f} pts" if metrics["graded"] else "—"),("Brier",f"{metrics['brier']:.3f}" if metrics["graded"] else "—"),("Top-5 Hit Rate",f"{top5['hit_rate']*100:.1f}%" if top5["predictions"] else "—"),
        ]
        st.markdown('<div class="hit-backtest">' + ''.join(f'<div class="hit-stat"><span>{_e(k)}</span><b>{_e(v)}</b></div>' for k,v in vals) + '</div>', unsafe_allow_html=True)
        with st.expander("🎯 Calibration by probability tier"):
            cal = calibration_table(history)
            if cal.empty: st.info("Probability tiers appear after predictions are graded.")
            else: st.dataframe(cal, use_container_width=True, hide_index=True)
        with st.expander("🧪 Model-version performance"):
            versions = model_version_table(history)
            if not versions.empty: st.dataframe(versions, use_container_width=True, hide_index=True)
        with st.expander("🗂️ Prediction history", expanded=False):
            display = history.iloc[::-1].head(100).copy()
            cols = ["created_at_et","model_version","source","rank","player_name","team","opponent","predicted_p1","confidence","grade_status","actual_hits"]
            display = display[[c for c in cols if c in display.columns]]
            if "predicted_p1" in display:
                display["predicted_p1"] = pd.to_numeric(display["predicted_p1"], errors="coerce").map(lambda x:f"{x*100:.1f}%" if pd.notna(x) else "")
            st.dataframe(display, use_container_width=True, hide_index=True)

    with st.expander("♻️ Restore history backup"):
        upload = st.file_uploader("Upload V13 history CSV", type=["csv"], key="hit131_history_upload")
        if upload is not None and st.button("MERGE HISTORY BACKUP", use_container_width=True, key="hit131_merge"):
            result = merge_uploaded_history(upload)
            st.success(result["message"]) if result["ok"] else st.error(result["message"])


def render_hit_hub(games_df, section_header, status_info, team_logo, h):
    st.markdown(HIT_CSS, unsafe_allow_html=True)
    _hero()
    top_tab, analyzer_tab, backtest_tab = st.tabs(["🏆 Top 5 Scanner", "🔎 Player Analyzer", "📈 Backtest"])
    with top_tab:
        _render_top_scanner(games_df)
    with analyzer_tab:
        _render_analyzer(games_df, team_logo, status_info)
    with backtest_tab:
        _render_backtest()
    st.caption("Hit Model V13 • UI V13.1 • Sportsbook price does not drive the probability projection • Deep market decisions should use current confirmed lineup and matchup data whenever available.")
