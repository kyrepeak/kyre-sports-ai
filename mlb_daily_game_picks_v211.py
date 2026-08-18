'''MLB Daily Game Picks V2.1.1 — decision-screen intelligence.

Presentation + smart refresh orchestration only. Preserves V2.1.0 bounded sportsbook
resume, V2.0.9 mobile UI, V2.0.8 one-tap controller, V2.0.7 market-neutral
normalization, all seven production models, simulation depths, verified-market
gates, Step 5/6 selection rules, and identity firewalls.

Adds to the compact Final Card:
- prominent true model probability
- model projection versus posted line/target when available
- sportsbook + current posted odds when already present in verified caches
- per-pick freshness timestamp
- market-specific "Why this pick?" explainers based only on real model outputs
- matchup-first Total cards with both team logos
- smart Refresh Card Data: recent cards refresh fast-moving markets first, older
  cards progressively refresh more stages instead of blindly rebuilding all seven
'''

from __future__ import annotations

from html import escape
import math

import streamlit as st

import mlb_daily_game_picks_v210 as previous
import mlb_daily_game_picks_v205 as quota

ui = previous.previous
controller = ui.previous
master = ui.master
bridge = controller.bridge

VERSION = "MLB Daily Game Picks V2.1.1 • DECISION-SCREEN INTELLIGENCE"


def _finite(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _american(v):
    try:
        return f"{int(round(float(v))):+d}"
    except Exception:
        return "—"


def _pct(v):
    x = _finite(v)
    return f"{x * 100:.1f}%" if x is not None else "—"


def _build_timestamp(games_df):
    day = ui._day(games_df)
    saved = st.session_state.get(ui._timestamp_key(day))
    if isinstance(saved, dict):
        return saved.get("ts")
    return None


def _freshness(ts):
    if ts is None:
        return "Current session cache"
    try:
        now = ui._now_et()
        delta = max(0, int((now - ts.astimezone(ui.ET)).total_seconds()))
    except Exception:
        return ui._fmt_ts(ts)
    if delta < 60:
        age = f"{delta}s ago"
    elif delta < 3600:
        age = f"{delta // 60}m ago"
    else:
        age = f"{delta // 3600}h {(delta % 3600) // 60}m ago"
    return f"{ui._fmt_ts(ts)} • {age}"


def _game_row(games_df, game_pk):
    target = str(game_pk or "")
    if games_df is None or getattr(games_df, "empty", True):
        return None
    for _, row in games_df.iterrows():
        try:
            pk = str(int(float(row.get("game_pk"))))
        except Exception:
            pk = str(row.get("game_pk") or "")
        if pk == target:
            return row
    return None


def _cached_sportsbook_context(c, games_df):
    book = c.get("posted_book")
    price = c.get("posted_price")
    if book and price is not None:
        return str(book), _american(price), "verified connector quote"

    market = str(c.get("market") or "")
    game_pk = str(c.get("game_pk") or "")

    if market == "Pitcher Strikeouts":
        pack = controller._pack(games_df, "pitcherk") or {}
        wanted = "".join(ch for ch in str(c.get("name") or "").lower() if ch.isalnum())
        for r in pack.get("rows", []) or []:
            try:
                pk = str(int(float(r.get("game_pk"))))
            except Exception:
                pk = str(r.get("game_pk") or "")
            if pk != game_pk:
                continue
            got = "".join(ch for ch in str(r.get("player_name") or "").lower() if ch.isalnum())
            if got != wanted:
                continue
            board = r.get("market") or {}
            side = str((r.get("grade") or {}).get("side") or c.get("side") or "").upper()
            if side.startswith("OVER"):
                b, p = board.get("best_over_book"), board.get("best_over_price")
            else:
                b, p = board.get("best_under_book"), board.get("best_under_price")
            if b and p is not None:
                return str(b), _american(p), "verified pitcher-prop quote"

    if market == "Moneyline":
        day = ui._day(games_df)
        snaps = st.session_state.get(bridge._odds_key(day)) or {}
        try:
            snap = snaps.get(int(game_pk)) or snaps.get(game_pk) or {}
        except Exception:
            snap = snaps.get(game_pk) or {}
        best = dict(snap.get("best") or {})
        row = _game_row(games_df, game_pk)
        team = str(c.get("name") or "")
        away = str(row.get("away_team") or "") if row is not None else ""
        home = str(row.get("home_team") or "") if row is not None else ""
        item = best.get("away_ml") if team == away else best.get("home_ml") if team == home else None
        if isinstance(item, dict) and item.get("book") and item.get("price") is not None:
            return str(item["book"]), _american(item["price"]), "shared verified sportsbook snapshot"

    return None, None, None


def _projection_summary(c):
    market = str(c.get("market") or "")
    line = _finite(c.get("line"))

    if market == "Pitcher Strikeouts":
        proj = _finite(c.get("expected_k"))
        if proj is not None and line is not None:
            return f"Projected {proj:.2f} K • Line {line:g} • Delta {proj - line:+.2f} K"
        if proj is not None:
            return f"Projected {proj:.2f} K"

    if market == "Total":
        proj = _finite(c.get("projected_total"))
        if proj is not None and line is not None:
            return f"Projected total {proj:.2f} • Line {line:g} • Delta {proj - line:+.2f} runs"

    if market == "Run Line":
        margin = _finite(c.get("projected_margin"))
        if margin is not None and line is not None:
            return f"Projected margin {margin:+.2f} • Posted line {line:+g}"

    if market == "H+R+RBI":
        proj = _finite(c.get("expected_total"))
        if proj is not None and line is not None:
            return f"Expected H+R+RBI {proj:.2f} • Threshold {line:g}"

    if market == "Home Run":
        proj = _finite(c.get("expected_hr"))
        if proj is not None:
            return f"Expected HR {proj:.3f} • Target 1+ HR"

    if market == "1+ Hit":
        return f"Model probability {_pct(c.get('probability'))} to record 1+ hit"

    if market == "Moneyline":
        return f"Model win probability {_pct(c.get('probability'))}"

    return "Projection detail available in the Full Dashboard audit."


def _fair_context(c):
    fair = c.get("fair_odds")
    if fair is None:
        return ""
    if isinstance(fair, (int, float)):
        return f"Fair odds {_american(fair)}"
    return f"Fair odds {str(fair)}"


def _why_lines(c, games_df):
    market = str(c.get("market") or "")
    p = _finite(c.get("probability"))
    rel = _finite(c.get("reliability"))
    dq = _finite(c.get("data_quality"))
    line = _finite(c.get("line"))
    lines = []

    if p is not None:
        lines.append(f"The production engine estimates a {p*100:.1f}% true probability for this side.")
    proj = _projection_summary(c)
    if proj:
        lines.append(proj + ".")

    if market == "Pitcher Strikeouts":
        push = _finite(c.get("push_probability"))
        if push is not None and push > 0:
            lines.append(f"Push probability at the posted line is {push*100:.1f}%.")
    elif market == "Total":
        edge = _finite(c.get("model_edge_runs"))
        if edge is not None:
            lines.append(f"Model-to-market separation is {edge:+.2f} runs.")
    elif market == "H+R+RBI":
        med = c.get("median")
        mode = c.get("mode")
        if med is not None or mode is not None:
            lines.append(f"Distribution center: median {med if med is not None else '—'} • mode {mode if mode is not None else '—'}.")
    elif market == "1+ Hit":
        sample = _finite(c.get("sample"))
        if sample is not None and sample > 0:
            unit = str(c.get("sample_unit") or "sample")
            lines.append(f"Production evidence includes {sample:.0f} {unit}.")
    elif market == "Home Run":
        exp_hr = _finite(c.get("expected_hr"))
        if exp_hr is not None:
            lines.append(f"Expected home runs for the matchup are {exp_hr:.3f}; the card still ranks the actual 1+ HR probability, not raw power alone.")

    if rel is not None and dq is not None:
        lines.append(f"Reliability {rel*100:.0f}% • data quality {dq*100:.0f}% feed the market-neutral Pick Strength.")
    book, price, note = _cached_sportsbook_context(c, games_df)
    if book and price:
        lines.append(f"Verified market context: {book} {price} ({note}).")
    elif line is not None and market in {"Run Line", "Total", "Pitcher Strikeouts"}:
        lines.append("The displayed line is verified; no sportsbook price is shown when a matching cached quote is unavailable.")

    lines.append("No sportsbook price is used to create the underlying production projection.")
    return lines


def _candidate_name_html(c):
    market = str(c.get("market") or "")
    name = str(c.get("name") or "Candidate")
    if market == "Total":
        away, home = ui._split_matchup(name)
        if home:
            return (
                f'<div class="k211-total-name">'
                f'<span>{ui._img(away, 32)}</span><span>{escape(away)}</span>'
                f'<span class="k211-at">@</span>'
                f'<span>{ui._img(home, 32)}</span><span>{escape(home)}</span>'
                f'</div>'
            )
    return f'<div class="kui-name-row">{ui._candidate_logo(c)}<div class="kui-name">{escape(name)}</div></div>'


def _decision_card(c, rank, games_df, ts):
    medals = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣", 5: "5️⃣"}
    score = master._finite(c.get("score"))
    tier, tier_cls = ui._tier(score)
    prob = _pct(c.get("probability"))
    projection = _projection_summary(c)
    book, price, _ = _cached_sportsbook_context(c, games_df)
    market_line = f"{book} {price}" if book and price else "Verified model output"
    fair = _fair_context(c)
    freshness = _freshness(ts)
    fair_html = f'<span class="k211-fair">{escape(fair)}</span>' if fair else ""

    return f'''<div class="kui-card k211-card {'first' if rank == 1 else ''}">
      <div class="kui-rank">{medals.get(rank, '•')} DAILY #{rank}</div>
      <div class="kui-market">{escape(str(c.get('market') or ''))}</div>
      {_candidate_name_html(c)}
      <div class="kui-side">{escape(str(c.get('side') or ''))}</div>
      <div class="k211-prob-row"><div><b>{prob}</b><span> TRUE MODEL PROBABILITY</span></div>{fair_html}</div>
      <div class="k211-projection">{escape(projection)}</div>
      <div class="kui-score">{score:.1f}<small> /100 PICK STRENGTH</small></div>
      <div class="kui-badge {tier_cls}">{tier}</div>
      <div class="kui-matchup">{ui._matchup_html(c.get('matchup'))}</div>
      <div class="k211-market">📡 {escape(market_line)}</div>
      <div class="k211-fresh">🕐 {escape(freshness)}</div>
      <div class="kui-meta">{escape(str(c.get('first_pitch') or 'TBD'))} ET • Reliability {master._finite(c.get('reliability'))*100:.0f}% • Data {master._finite(c.get('data_quality'))*100:.0f}%</div>
    </div>'''


def _render_master_decision(games_df):
    ui._prime_active_games(games_df)
    candidates = master._collect_candidates(games_df)
    selected = master._select_master(candidates)
    qualified = [c for c in candidates if master._finite(c.get("score")) >= master.MASTER_MIN_SCORE]
    connected = len({(c.get("game_pk"), c.get("market")) for c in candidates})
    ts = _build_timestamp(games_df)

    st.markdown(
        f'''<div class="kui-master k211-head">
          <div class="kui-kicker">KYRE SPORTS AI • STEP 6 • FINAL DECISION SCREEN</div>
          <div class="kui-master-title">🏆 Daily Master Card — Top 5 MLB Picks</div>
          <div class="kui-master-sub">True probability + projection/line context + verified sportsbook quote when cached • market-neutral Pick Strength • one final pick per game • no forced fifth pick.</div>
          <div class="kui-stats">
            <div class="kui-stat"><b>{len(candidates)}</b> scored candidates</div>
            <div class="kui-stat"><b>{len(qualified)}</b> at 70+</div>
            <div class="kui-stat"><b>{connected}</b> connected game-markets</div>
            <div class="kui-stat"><b>{len(selected)}/{master.MASTER_LIMIT}</b> final picks</div>
          </div>
        </div>''',
        unsafe_allow_html=True,
    )

    if not selected:
        st.info("Build the production connectors above. The Final Card only displays real scored production outputs.")
    else:
        cols = st.columns(2)
        for i, c in enumerate(selected, 1):
            with cols[(i - 1) % 2]:
                st.markdown(_decision_card(c, i, games_df, ts), unsafe_allow_html=True)
                with st.expander("🧠 Why this pick?", expanded=False):
                    for line in _why_lines(c, games_df):
                        st.markdown(f"• {line}")

    if candidates:
        with st.expander("🎯 Best qualified picks by market", expanded=False):
            leader_html = ui._market_leader_cards(candidates)
            if leader_html:
                st.markdown(f'<div class="kui-market-grid">{leader_html}</div>', unsafe_allow_html=True)
                st.caption("Up to three qualified candidates per market. Missing or incompatible sportsbook markets remain absent/unscored.")
            else:
                st.info("No market candidate currently clears the 70/100 qualification floor.")
        with st.expander("🧠 Daily Master Card rules", expanded=False):
            st.caption(
                "V2.1.1 is presentation + refresh orchestration only. Production probabilities, simulations, verified sportsbook gates, V2.0.7 normalization, Step 5 rankings, and selection guardrails are unchanged."
            )


def _smart_refresh_stages(games_df):
    ts = _build_timestamp(games_df)
    if ts is None:
        return [x[0] for x in controller.STAGES], "No completed-card timestamp exists, so all seven stages will rebuild."
    try:
        age_min = max(0.0, (ui._now_et() - ts.astimezone(ui.ET)).total_seconds() / 60.0)
    except Exception:
        age_min = 999.0

    if age_min <= 15:
        return ["runline", "total"], "Card is ≤15 minutes old: refresh only the fast-moving full-game sportsbook markets."
    if age_min <= 45:
        return ["runline", "total", "moneyline", "pitcherk"], "Card is 15–45 minutes old: refresh game markets plus Moneyline and Pitcher K."
    return [x[0] for x in controller.STAGES], "Card is >45 minutes old: refresh the full seven-market production slate."


def _queue_smart_refresh(games_df):
    day = ui._day(games_df)
    stages, reason = _smart_refresh_stages(games_df)

    for stage in stages:
        key = controller._pack_key(games_df, stage)
        if key:
            st.session_state.pop(key, None)

    if "runline" in stages or "total" in stages:
        st.session_state.pop(bridge._odds_key(day), None)
        try:
            st.session_state.pop(quota._stamp_key(day), None)
        except Exception:
            pass

    state_key = controller._state_key(day)
    old = st.session_state.get(state_key) or {}
    fresh = controller._initial_state(day)
    fresh["active"] = True
    fresh["runs"] = int(old.get("runs", 0) or 0) + 1
    st.session_state[state_key] = fresh
    st.session_state.pop(ui._timestamp_key(day), None)
    st.session_state[f"dgp_smart_refresh_note_v211::{day}"] = (
        f"{reason} Queued: " +
        ", ".join(label for stage, label, _ in controller.STAGES if stage in stages)
    )


def _render_refresh_controls_decision(games_df):
    day = ui._day(games_df)
    auto_key = f"dgp_ui_autorefresh_v209::{day}"
    secs_key = f"dgp_ui_refreshsecs_v209::{day}"
    state = st.session_state.get(controller._state_key(day)) or {}

    if auto_key not in st.session_state:
        st.session_state[auto_key] = True
    if secs_key not in st.session_state:
        st.session_state[secs_key] = 300

    with st.expander("⚙️ Display & refresh settings", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.toggle(
                "Auto-refresh display",
                key=auto_key,
                help="Reruns the screen only. It never rebuilds a production connector.",
            )
        with c2:
            st.selectbox(
                "Display refresh interval",
                options=[120, 300, 600],
                format_func=lambda x: f"{x // 60} minutes",
                key=secs_key,
            )

        st.caption("Display auto-refresh is quota-safe: it only rerenders cached state.")
        st.divider()
        stages, reason = _smart_refresh_stages(games_df)
        labels = [label for stage, label, _ in controller.STAGES if stage in stages]
        st.caption(f"🔄 Smart data refresh plan: {reason}")
        st.caption("Will queue: " + " • ".join(labels))
        disabled = bool(state.get("active"))
        if st.button(
            "🔄 REFRESH CARD DATA",
            type="primary",
            use_container_width=True,
            disabled=disabled,
            key=f"dgp_refresh_card_data_v211::{day}",
            help="Selectively rebuilds stale/mutable production stages. It never changes model math.",
        ):
            _queue_smart_refresh(games_df)
            st.rerun()

        note_key = f"dgp_smart_refresh_note_v211::{day}"
        if st.session_state.get(note_key):
            st.info(st.session_state.pop(note_key))

    if ui.st_autorefresh is not None and bool(st.session_state.get(auto_key)) and not bool(state.get("active")):
        secs = int(st.session_state.get(secs_key, 300) or 300)
        ui.st_autorefresh(interval=max(120, secs) * 1000, key=f"dgp_ui_tick_v211::{day}")


def _inject_css_decision():
    ui._inject_css_original_v211()
    st.markdown(
        '''
<style>
.k211-head{margin-bottom:10px}
.k211-card{min-height:285px;margin-bottom:7px}
.k211-prob-row{display:flex;justify-content:space-between;align-items:flex-end;gap:8px;flex-wrap:wrap;margin-top:11px}
.k211-prob-row b{font-size:26px;color:#69e5ff;line-height:1}.k211-prob-row span{font-size:7px;color:#82a1ba;font-weight:900}
.k211-fair{border:1px solid #315d79;border-radius:999px;padding:4px 7px;color:#9bdfff!important;background:#092538;white-space:nowrap}
.k211-projection{border-left:3px solid #4bd7ff;background:#071d2d;color:#d4e8f6;border-radius:6px;padding:7px 8px;font-size:9px;font-weight:800;line-height:1.35;margin-top:9px}
.k211-market{color:#f3d77c;font-size:8px;font-weight:850;margin-top:8px}.k211-fresh{color:#83a1b7;font-size:8px;margin-top:5px}
.k211-total-name{display:flex;align-items:center;gap:7px;flex-wrap:wrap;color:#fff;font-size:15px;font-weight:1000;line-height:1.25;margin-top:5px}
.k211-at{color:#7895ab;font-size:11px}
@media(max-width:650px){.k211-card{min-height:0}.k211-prob-row b{font-size:24px}}
</style>
        ''',
        unsafe_allow_html=True,
    )


if not hasattr(ui, "_inject_css_original_v211"):
    ui._inject_css_original_v211 = ui._inject_css

ui._inject_css = _inject_css_decision
ui._render_refresh_controls = _render_refresh_controls_decision
ui._render_master_polished = _render_master_decision
ui.master._render_master = _render_master_decision


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    ui._inject_css = _inject_css_decision
    ui._render_refresh_controls = _render_refresh_controls_decision
    ui._render_master_polished = _render_master_decision
    ui.master._render_master = _render_master_decision

    st.caption(
        "🧠 V2.1.1 decision screen: true probability • projection vs line • cached sportsbook quote when available • pick freshness • Why-this-pick explainers • smart selective data refresh."
    )
    return previous.render_daily_game_picks(
        games_df, section_header, status_info, team_logo, h
    )
