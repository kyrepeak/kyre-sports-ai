"""MLB Spread / Run Line V15.6 — Top-5 card Step 1.

Presentation-only wrapper over verified V15.5/V15.4/V15.3/V15.2.

Step 1 adds to Today's Strongest Spread Projections only:
- both MLB team logos;
- deterministic display-only Pick Strength + Probability Strength labels;
- existing H2H summary surfaced more clearly;
- last-five completed H2H matchup ledger from the already-fetched V15.2 history;
- current-line historical context clearly labeled as a replay at TODAY'S selected
  +/-1.5 line, never as the historical sportsbook closing run line.

Protected behavior:
- V15.2 history-adjusted cover probability is unchanged;
- V15.2 history weights/adjustment cap are unchanged;
- projected score, fair odds, simulation, data confidence and rank order are unchanged;
- V15.3 backtest, V15.4 live board and V15.5 verified-slate intake are unchanged.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

import mlb_spread_hub_v155 as prior

# Verified production chain.
v154 = prior.base
v153 = v154.base
v152 = v153.base

MODEL_VERSION = "V15.6 • TOP-5 CARD STEP 1"

_ACTIVE_GAME_META: dict[int, dict] = {}


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _safe_int(value):
    try:
        return int(float(value))
    except Exception:
        return 0


def _game_map(frame: pd.DataFrame | None) -> dict[int, dict]:
    out: dict[int, dict] = {}
    if frame is None or frame.empty:
        return out
    for _, row in frame.iterrows():
        pk = _safe_int(row.get("game_pk"))
        if not pk:
            continue
        out[pk] = {
            "away_team_id": _safe_int(row.get("away_team_id")),
            "home_team_id": _safe_int(row.get("home_team_id")),
            "away_team": str(row.get("away_team") or "Away"),
            "home_team": str(row.get("home_team") or "Home"),
        }
    return out


def _enrich_scan_result(original_scan, row, simulations):
    """Attach identity metadata only; never alter the V15.2 model payload."""
    result = original_scan(row, simulations)
    away_id = _safe_int(row.get("away_team_id"))
    home_id = _safe_int(row.get("home_team_id"))
    team_id = _safe_int(result.get("team_id"))
    result["away_team_id"] = away_id
    result["home_team_id"] = home_id
    result["opponent_id"] = home_id if team_id == away_id else away_id
    result["card_identity_version"] = MODEL_VERSION
    return result


def _identity(result):
    pk = _safe_int(result.get("game_pk"))
    meta = _ACTIVE_GAME_META.get(pk) or {}
    away_id = _safe_int(result.get("away_team_id") or meta.get("away_team_id"))
    home_id = _safe_int(result.get("home_team_id") or meta.get("home_team_id"))
    team_id = _safe_int(result.get("team_id"))
    opponent_id = _safe_int(result.get("opponent_id"))
    if not opponent_id and away_id and home_id and team_id:
        opponent_id = home_id if team_id == away_id else away_id
    return team_id, opponent_id, away_id, home_id


def _strength(result):
    """Display label only. It does not qualify, filter, rerank or change probability."""
    p = _num(result.get("cover"), 0.0)
    data = str(result.get("confidence") or "LOW").upper()
    converged = bool(result.get("converged"))

    if not converged or data == "LOW":
        pick = "WATCH"
        cls = "watch"
    elif p >= 0.68 and data == "HIGH":
        pick = "ELITE"
        cls = "elite"
    elif p >= 0.64 and data in {"HIGH", "MEDIUM-HIGH"}:
        pick = "STRONG"
        cls = "strong"
    elif p >= 0.60:
        pick = "SOLID"
        cls = "solid"
    else:
        pick = "LEAN"
        cls = "lean"

    if p >= 0.68:
        prob = "VERY HIGH"
    elif p >= 0.64:
        prob = "HIGH"
    elif p >= 0.60:
        prob = "GOOD"
    elif p >= 0.56:
        prob = "MODERATE"
    else:
        prob = "LEAN"
    return pick, prob, cls


def _reliability(games):
    n = int(games or 0)
    if n >= 8:
        return "HIGH", "good"
    if n >= 5:
        return "MEDIUM", "mid"
    if n >= 1:
        return "LOW", "warn"
    return "NO SAMPLE", "warn"


def _last_five_summary(games):
    recent = list(games or [])[:5]
    wins = sum(1 for g in recent if _num(g.get("margin"), 0.0) > 0)
    losses = sum(1 for g in recent if _num(g.get("margin"), 0.0) < 0)
    return recent, wins, losses


def _fmt_date(value):
    try:
        return datetime.fromisoformat(str(value)[:10]).strftime("%b %d, %Y")
    except Exception:
        return str(value or "—")


def _last5_html(result, h):
    context = result.get("history") or {}
    games, _, _ = _last_five_summary(context.get("games") or [])
    line = _num(result.get("line"), np.nan)
    if not games:
        return '<div class="ks156-empty">No completed H2H meetings were available in the existing V15.2 history sample.</div>'

    rows = []
    opponent = h(result.get("opponent") or "Opponent")
    for g in games:
        team_runs = _num(g.get("team_runs"), np.nan)
        opp_runs = _num(g.get("opponent_runs"), np.nan)
        margin = _num(g.get("margin"), np.nan)
        loc = "vs" if str(g.get("location") or "").lower() == "home" else "@"
        if np.isfinite(margin):
            wl = "W" if margin > 0 else "L" if margin < 0 else "T"
            wl_cls = "win" if margin > 0 else "loss" if margin < 0 else "push"
        else:
            wl, wl_cls = "—", "push"

        if np.isfinite(margin) and np.isfinite(line):
            replay_margin = margin + line
            if replay_margin > 0:
                replay, replay_cls = "COVER", "cover"
            elif replay_margin < 0:
                replay, replay_cls = "MISS", "miss"
            else:
                replay, replay_cls = "PUSH", "push"
        else:
            replay, replay_cls = "—", "push"

        score = "—"
        if np.isfinite(team_runs) and np.isfinite(opp_runs):
            score = f"{int(team_runs)}-{int(opp_runs)}"
        margin_text = "—" if not np.isfinite(margin) else f"{margin:+.0f}"
        rows.append(
            f'<div class="ks156-hrow">'
            f'<span>{h(_fmt_date(g.get("date")))}</span>'
            f'<span>{loc} {opponent}</span>'
            f'<strong>{h(score)}</strong>'
            f'<b class="{wl_cls}">{wl}</b>'
            f'<span>{h(margin_text)}</span>'
            f'<b class="{replay_cls}">{replay}</b>'
            f'</div>'
        )
    return "".join(rows)


def _css():
    st.markdown(
        '''<style>
.ks156-card{position:relative;overflow:hidden}
.ks156-top{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ks156-badges{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.ks156-pill{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.48rem;font-weight:950;letter-spacing:.04em;white-space:nowrap;border:1px solid #36536a;background:#0a1928;color:#c8d8e4}
.ks156-pill.elite{border-color:#2d865f;background:#0d3428;color:#86efb7}.ks156-pill.strong{border-color:#39769a;background:#0b2b3f;color:#91ddff}.ks156-pill.solid{border-color:#887121;background:#362f0f;color:#ffe27b}.ks156-pill.lean,.ks156-pill.watch{border-color:#705845;background:#2c2118;color:#f4bd85}
.ks156-matchup{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:9px;align-items:center;margin:7px 0 8px;padding:9px;border:1px solid rgba(88,132,160,.34);border-radius:13px;background:rgba(5,18,31,.58)}
.ks156-team{display:flex;align-items:center;gap:7px;min-width:0}.ks156-team.right{justify-content:flex-end;text-align:right}.ks156-team .ks156-logo{width:38px;height:38px;display:flex;align-items:center;justify-content:center;flex:0 0 38px}.ks156-team .ks156-logo img{max-width:38px!important;max-height:38px!important;width:38px!important;height:38px!important;object-fit:contain!important}.ks156-team-copy{min-width:0}.ks156-team-name{font-size:.68rem;font-weight:950;color:#f4f8fb;line-height:1.16}.ks156-team-sub{font-size:.49rem;color:#8299aa;margin-top:2px}.ks156-vs{font-size:.49rem;font-weight:900;color:#667f91}
.ks156-quick{display:flex;gap:6px;flex-wrap:wrap;margin:7px 0}.ks156-mini{font-size:.48rem;border:1px solid #29485d;border-radius:999px;padding:4px 7px;color:#a9bdca;background:#071522}.ks156-mini b{color:#f6fbff}
.ks156-strength-basis{font-size:.49rem;line-height:1.5;color:#8099aa;margin:7px 0 2px}.ks156-strength-basis b{color:#dceaf3}
.ks156-history-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin:9px 0}.ks156-history-grid div{background:#071522;border:1px solid #29485d;border-radius:9px;padding:8px}.ks156-history-grid small{display:block;color:#71899a;font-size:.42rem;font-weight:900}.ks156-history-grid strong{display:block;color:#f5f9fc;font-size:.64rem;margin-top:2px}
.ks156-hlabel{font-size:.48rem;font-weight:950;color:#8edcff;letter-spacing:.05em;margin:10px 0 5px}.ks156-hhead,.ks156-hrow{display:grid;grid-template-columns:1.25fr 1.25fr .7fr .48fr .55fr .82fr;gap:5px;align-items:center}.ks156-hhead{font-size:.37rem;color:#688397;font-weight:950;padding:0 6px 3px}.ks156-hrow{font-size:.43rem;color:#b5c7d4;background:#06131f;border:1px solid #213b4d;border-radius:8px;padding:7px 6px;margin:4px 0}.ks156-hrow strong{color:#f5f9fc}.ks156-hrow b{text-align:center;border-radius:999px;padding:3px 4px;font-size:.37rem}.ks156-hrow b.win,.ks156-hrow b.cover{background:#0d3327;color:#7df2ba}.ks156-hrow b.loss,.ks156-hrow b.miss{background:#351a1e;color:#ff9ca5}.ks156-hrow b.push{background:#352f16;color:#ffe17a}.ks156-empty{color:#8298a8;font-size:.5rem;padding:8px 0}.ks156-disclaimer{font-size:.43rem;line-height:1.5;color:#6c8495;margin-top:7px}
@media(max-width:640px){.ks156-matchup{grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:5px}.ks156-team{gap:5px}.ks156-team .ks156-logo,.ks156-team .ks156-logo img{width:31px!important;height:31px!important;max-width:31px!important;max-height:31px!important}.ks156-team-name{font-size:.58rem}.ks156-hhead,.ks156-hrow{grid-template-columns:1.1fr 1.15fr .62fr .44fr .52fr .72fr;font-size:.38rem}.ks156-history-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>''',
        unsafe_allow_html=True,
    )


def _render_cards(results, status_info, team_logo, h):
    _css()
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, r in enumerate(results[:5], 1):
        status_label, status_css = status_info(r.get("status"))
        badge = v152._badge_class(r.get("confidence"))
        first = " ks-first" if rank == 1 else ""
        team_id, opponent_id, _, _ = _identity(r)
        selected_logo = team_logo(team_id) if team_id else ""
        opponent_logo = team_logo(opponent_id) if opponent_id else ""
        summary = (r.get("history") or {}).get("summary") or {}
        h2h_games = int(summary.get("games") or 0)
        h2h_text = f'{int(summary.get("wins") or 0)}-{int(summary.get("losses") or 0)}' if h2h_games else "N/A"
        h2h_cover = summary.get("raw_cover_rate")
        h2h_cover_text = f"{float(h2h_cover) * 100:.0f}%" if h2h_cover is not None else "N/A"
        reliability, rel_cls = _reliability(h2h_games)
        last5, last5_w, last5_l = _last_five_summary((r.get("history") or {}).get("games") or [])
        last5_record = f"{last5_w}-{last5_l}" if last5 else "N/A"
        pick_strength, probability_strength, strength_cls = _strength(r)
        score = f'{r["away_name"]} {r["away_score"]:.1f} — {r["home_name"]} {r["home_score"]:.1f}'
        avg_margin = _num(summary.get("avg_margin"), np.nan)
        avg_margin_text = "N/A" if not np.isfinite(avg_margin) else f"{avg_margin:+.1f}"
        avg_for = _num(summary.get("avg_team_runs"), np.nan)
        avg_against = _num(summary.get("avg_opponent_runs"), np.nan)
        avg_score = "N/A" if not (np.isfinite(avg_for) and np.isfinite(avg_against)) else f"{avg_for:.1f}-{avg_against:.1f}"
        one_run = summary.get("one_run_rate")
        one_run_text = "N/A" if one_run is None else f"{float(one_run) * 100:.0f}%"
        history_adj = _num(r.get("history_adjustment"), 0.0)

        card = (
            f'<div class="ks-pick-card ks156-card{first}">'
            f'<div class="ks156-top"><div class="ks-rank">{medals.get(rank, "•")} #{rank}</div>'
            '<div class="ks156-badges">'
            f'<span class="ks156-pill {strength_cls}">PICK STRENGTH • {h(pick_strength)}</span>'
            f'<span class="ks156-pill {strength_cls}">PROB STRENGTH • {h(probability_strength)}</span>'
            '</div></div>'
            '<div class="ks-card-main">'
            '<div class="ks156-matchup">'
            f'<div class="ks156-team"><span class="ks156-logo">{selected_logo}</span><div class="ks156-team-copy"><div class="ks156-team-name">{h(r["team"])} {r["line"]:+.1f}</div><div class="ks156-team-sub">SELECTED RUN-LINE SIDE</div></div></div>'
            '<div class="ks156-vs">VS</div>'
            f'<div class="ks156-team right"><div class="ks156-team-copy"><div class="ks156-team-name">{h(r["opponent"])}</div><div class="ks156-team-sub">OPPONENT</div></div><span class="ks156-logo">{opponent_logo}</span></div>'
            '</div>'
            f'<div class="ks-matchup">Projected {h(score)}</div>'
            '<div class="ks-meta-line">'
            f'<span class="ks-status {status_css}">{h(status_label)}</span>'
            f'<span class="ks-mini">🕒 {h(r["first_pitch"])} ET</span>'
            f'<span class="ks-mini">H2H L10 {h(h2h_text)}</span>'
            '</div>'
            '<div class="ks156-quick">'
            f'<span class="ks156-mini">LAST 5 H2H <b>{h(last5_record)}</b></span>'
            f'<span class="ks156-mini">AVG H2H MARGIN <b>{h(avg_margin_text)}</b></span>'
            f'<span class="ks156-mini">H2H SAMPLE <b class="{rel_cls}">{h(reliability)}</b></span>'
            '</div>'
            f'<div class="ks156-strength-basis">Strength label is display-only • <b>{r["cover"] * 100:.1f}%</b> history-adjusted cover • <b>{h(r.get("confidence"))}</b> data • convergence <b>{"PASS" if r.get("converged") else "FAIL"}</b>.</div>'
            '<details class="ks-card-details"><summary>＋ H2H history + last 5 + spread details</summary>'
            '<div class="ks-detail-body">'
            '<div class="ks156-history-grid">'
            f'<div><small>H2H L10 RECORD</small><strong>{h(h2h_text)}</strong></div>'
            f'<div><small>H2H COVER @ TODAY\'S {r["line"]:+.1f}</small><strong>{h(h2h_cover_text)}</strong></div>'
            f'<div><small>AVG H2H SCORE</small><strong>{h(avg_score)}</strong></div>'
            f'<div><small>AVG H2H MARGIN</small><strong>{h(avg_margin_text)}</strong></div>'
            f'<div><small>CURRENT-SEASON H2H</small><strong>{h(summary.get("current_season_record", "0-0"))}</strong></div>'
            f'<div><small>CURRENT-VENUE H2H</small><strong>{h(summary.get("venue_record", "0-0"))}</strong></div>'
            f'<div><small>ONE-RUN H2H RATE</small><strong>{h(one_run_text)}</strong></div>'
            f'<div><small>HISTORY ADJUSTMENT</small><strong>{history_adj * 100:+.1f} pp</strong></div>'
            '</div>'
            '<div class="ks156-hlabel">LAST 5 COMPLETED HEAD-TO-HEAD MEETINGS</div>'
            '<div class="ks156-hhead"><span>DATE</span><span>MATCHUP</span><span>SCORE</span><span>W/L</span><span>MARGIN</span><span>AT TODAY\'S LINE</span></div>'
            f'<div>{_last5_html(r, h)}</div>'
            f'<div class="ks156-disclaimer">The COVER/MISS labels replay each historical final score against today\'s selected {r["line"]:+.1f} line. They are not claimed to be the sportsbook closing run line from those historical dates.</div>'
            f'<div class="ks156-disclaimer">Core cover <b>{r["core_cover"] * 100:.1f}%</b> • V15.2 history adjustment <b>{history_adj * 100:+.1f} pp</b> • Win <b>{r["win_prob"] * 100:.1f}%</b> • One-run model probability <b>{r["one_run"] * 100:.1f}%</b> • Data <b>{r["data_score"]}/9</b>.</div>'
            '</div></details>'
            '</div>'
            '<div class="ks-right">'
            f'<div class="ks-prob">{r["cover"] * 100:.1f}%</div>'
            '<div class="ks-prob-label">History-adjusted cover</div>'
            '<div class="ks-card-meta">'
            f'<span class="ks-badge {badge}">DATA {h(r["confidence"])}</span>'
            f'<span class="ks-mini">Fair {h(r["fair_odds"])}</span>'
            '</div></div></div>'
        )
        st.markdown(card, unsafe_allow_html=True)


def render_spread_hub(games_df, section_header, status_info, team_logo, h):
    """Render V15.5 unchanged except for the V15.2 Top-5 card renderer."""
    global _ACTIVE_GAME_META
    _ACTIVE_GAME_META = _game_map(games_df)
    if not _ACTIVE_GAME_META:
        try:
            day = prior.schedule.current_selected_date()
            fresh, _ = prior.schedule.load_with_diagnostics(day)
            _ACTIVE_GAME_META = _game_map(fresh)
        except Exception:
            _ACTIVE_GAME_META = {}

    original_scan = v152._scan_game
    original_cards = v152._render_cards

    def scan_with_identity(row, simulations):
        return _enrich_scan_result(original_scan, row, simulations)

    v152._scan_game = scan_with_identity
    v152._render_cards = _render_cards
    try:
        st.caption(
            "🧩 MLB Spread V15.6 Card Step 1 • both team logos + Pick Strength + clearer H2H/Last-5 history • V15.2 probability/ranking math unchanged."
        )
        return prior.render_spread_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        v152._scan_game = original_scan
        v152._render_cards = original_cards


__all__ = ["MODEL_VERSION", "render_spread_hub"]
