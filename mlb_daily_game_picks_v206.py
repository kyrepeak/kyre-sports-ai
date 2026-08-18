"""MLB Daily Game Picks V2.0.6 — Daily Master Card.

Adds a read-only slate-wide Top 5 above the per-game Step 5 cards. The Master Card
uses only already-scored production candidates from the existing seven-market
bridge and the unchanged Step 3 Pick Strength score. It does not rerun or alter
any production model.

Master Card rules:
- minimum Pick Strength 70.0; weak candidates are never used just to fill five
- at most one final pick per MLB game
- same player is not repeated across player-prop markets
- exact duplicate candidates are removed
- all matchup identity and verified-market gates from V2.0.5/V2.0.4 remain active
"""
from __future__ import annotations

from html import escape
import math

import streamlit as st

import mlb_daily_game_picks_v205 as previous

# V2.0.5 -> V2.0.4 bridge module. We insert the Master Card after its two
# game-market connectors and before the existing per-game Step 5 renderer.
bridge = previous.previous
core = bridge.core

VERSION = "MLB Daily Game Picks V2.0.6 • DAILY MASTER CARD"
MASTER_MIN_SCORE = 70.0
MASTER_LIMIT = 5
PLAYER_MARKETS = {"1+ Hit", "Home Run", "H+R+RBI", "Pitcher Strikeouts"}


def _finite(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _frame(games_df):
    try:
        return core.step4.base.base.base._sort_games(games_df)
    except Exception:
        return games_df


def _game_pk(row):
    try:
        return str(int(float(row.get("game_pk"))))
    except Exception:
        return str(row.get("game_pk") or "")


def _matchup(row):
    return f"{row.get('away_team') or 'Away'} @ {row.get('home_team') or 'Home'}"


def _collect_candidates(games_df):
    out = []
    if games_df is None or games_df.empty:
        return out
    frame = _frame(games_df)
    for _, row in frame.iterrows():
        pk = _game_pk(row)
        matchup = _matchup(row)
        first_pitch = str(row.get("first_pitch_et") or "TBD")
        for market in core.step4.base.base.MARKETS:
            try:
                candidates = bridge._production_candidates(row, market) or []
            except Exception:
                candidates = []
            for c in candidates:
                item = dict(c)
                item["game_pk"] = pk
                item["matchup"] = matchup
                item["first_pitch"] = first_pitch
                out.append(item)

    uniq = {}
    for c in out:
        key = (
            c.get("game_pk"), c.get("market"), c.get("name"), c.get("side"),
            str(c.get("line")), round(_finite(c.get("probability"), 0.0), 8),
        )
        uniq[key] = c
    return sorted(
        uniq.values(),
        key=lambda c: (
            _finite(c.get("score")),
            _finite(c.get("reliability")),
            _finite(c.get("data_quality")),
            _finite(c.get("probability")),
        ),
        reverse=True,
    )


def _select_master(candidates, limit=MASTER_LIMIT):
    selected = []
    used_games = set()
    used_players = set()
    used_exact = set()

    for c in candidates:
        score = _finite(c.get("score"))
        if score < MASTER_MIN_SCORE:
            continue
        game_pk = str(c.get("game_pk") or "")
        if not game_pk or game_pk in used_games:
            continue
        exact = (game_pk, c.get("market"), c.get("name"), c.get("side"), str(c.get("line")))
        if exact in used_exact:
            continue

        market = str(c.get("market") or "")
        player_key = None
        if market in PLAYER_MARKETS:
            player_key = (
                str(c.get("name") or "").strip().lower(),
                str(c.get("team") or "").strip().lower(),
            )
            if player_key in used_players:
                continue

        selected.append(c)
        used_games.add(game_pk)
        used_exact.add(exact)
        if player_key:
            used_players.add(player_key)
        if len(selected) >= int(limit):
            break
    return selected


def _tier(score):
    score = _finite(score)
    if score >= 82.0:
        return "ELITE"
    if score >= 76.0:
        return "STRONG"
    return "QUALIFIED"


def _css():
    st.markdown(
        """
<style>
.dgm-wrap{border:1px solid #2f5978;background:linear-gradient(145deg,#0b1d31,#071523);border-radius:20px;padding:15px;margin:12px 0 18px}
.dgm-kicker{color:#5ddcff;font-size:10px;font-weight:950;letter-spacing:1.5px;text-transform:uppercase}.dgm-title{font-size:27px;font-weight:1000;color:#fff;margin-top:3px}.dgm-sub{font-size:11px;line-height:1.5;color:#91a8bd;margin-top:5px}.dgm-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-top:13px}.dgm-card{border:1px solid #294967;background:#0a192a;border-radius:15px;padding:11px;min-height:190px}.dgm-card.first{border-color:#c5a72c}.dgm-rank{color:#5cdcff;font-size:10px;font-weight:950;letter-spacing:1px}.dgm-market{color:#9ab0c3;font-size:10px;font-weight:850;margin-top:8px}.dgm-name{color:#fff;font-size:15px;font-weight:1000;margin-top:3px}.dgm-side{color:#d8e4ee;font-size:11px;margin-top:3px}.dgm-score{color:#fff;font-size:25px;font-weight:1000;margin-top:10px}.dgm-score small{font-size:8px;color:#7f98ae}.dgm-tier{display:inline-block;margin-top:4px;border:1px solid #31577a;border-radius:999px;padding:2px 6px;color:#79ddff;font-size:8px;font-weight:950}.dgm-game{color:#91a7bb;font-size:9px;line-height:1.4;margin-top:8px}.dgm-meta{color:#7790a7;font-size:8px;line-height:1.45;margin-top:6px}.dgm-empty{border:1px dashed #31506b;border-radius:14px;padding:12px;color:#9fb0c0;font-size:11px;margin-top:12px}.dgm-statline{display:flex;flex-wrap:wrap;gap:7px;margin-top:11px}.dgm-stat{border:1px solid #25455f;background:#081725;border-radius:10px;padding:6px 8px;color:#8fa7bb;font-size:9px}.dgm-stat b{color:#fff}
@media(max-width:1050px){.dgm-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:650px){.dgm-grid{grid-template-columns:1fr}.dgm-title{font-size:23px}.dgm-card{min-height:0}}
</style>
""",
        unsafe_allow_html=True,
    )


def _card(c, rank):
    medals = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣", 5: "5️⃣"}
    score = _finite(c.get("score"))
    return f'''<div class="dgm-card {'first' if rank == 1 else ''}">
      <div class="dgm-rank">{medals.get(rank, '•')} DAILY #{rank}</div>
      <div class="dgm-market">{escape(str(c.get('market') or ''))}</div>
      <div class="dgm-name">{escape(str(c.get('name') or 'Candidate'))}</div>
      <div class="dgm-side">{escape(str(c.get('side') or ''))}</div>
      <div class="dgm-score">{score:.1f}<small> /100 PICK STRENGTH</small></div>
      <div class="dgm-tier">{_tier(score)}</div>
      <div class="dgm-game">{escape(str(c.get('matchup') or ''))}<br>{escape(str(c.get('first_pitch') or 'TBD'))} ET</div>
      <div class="dgm-meta">Model {_finite(c.get('probability'))*100:.1f}% • Reliability {_finite(c.get('reliability'))*100:.0f}% • Data {_finite(c.get('data_quality'))*100:.0f}%</div>
    </div>'''


def _market_rows(candidates):
    rows = []
    markets = list(core.step4.base.base.MARKETS)
    for market in markets:
        seen_games = set()
        rank = 0
        for c in candidates:
            if c.get("market") != market or _finite(c.get("score")) < MASTER_MIN_SCORE:
                continue
            pk = str(c.get("game_pk") or "")
            if pk in seen_games:
                continue
            seen_games.add(pk)
            rank += 1
            rows.append({
                "Market": market,
                "Rank": rank,
                "Pick": c.get("name"),
                "Side": c.get("side"),
                "Matchup": c.get("matchup"),
                "Pick Strength": round(_finite(c.get("score")), 1),
                "Model": f"{_finite(c.get('probability'))*100:.1f}%",
                "Reliability": f"{_finite(c.get('reliability'))*100:.0f}%",
                "Data": f"{_finite(c.get('data_quality'))*100:.0f}%",
            })
            if rank >= 3:
                break
    return rows


def _render_master(games_df):
    _css()
    candidates = _collect_candidates(games_df)
    selected = _select_master(candidates)
    qualified = [c for c in candidates if _finite(c.get("score")) >= MASTER_MIN_SCORE]
    connected_market_games = len({(c.get("game_pk"), c.get("market")) for c in candidates})

    cards = "".join(_card(c, i) for i, c in enumerate(selected, 1))
    if not cards:
        cards = '<div class="dgm-empty">Build the production connectors above. The Daily Master Card will populate only from real scored outputs; no pick is fabricated while data is missing.</div>'

    st.markdown(
        f'''<div class="dgm-wrap">
          <div class="dgm-kicker">KYRE SPORTS AI • STEP 6 • SLATE-WIDE SELECTION</div>
          <div class="dgm-title">🏆 Daily Master Card — Top 5 MLB Picks</div>
          <div class="dgm-sub">Ranks the entire slate using the same market-aware Step 3 Pick Strength already used inside every game. Final-card guardrails: minimum 70/100, one pick per game, no repeated player across prop families, and no forced fifth pick.</div>
          <div class="dgm-statline">
            <div class="dgm-stat"><b>{len(candidates)}</b> scored candidates</div>
            <div class="dgm-stat"><b>{len(qualified)}</b> at 70+</div>
            <div class="dgm-stat"><b>{connected_market_games}</b> connected game-markets</div>
            <div class="dgm-stat"><b>{len(selected)}/{MASTER_LIMIT}</b> final-card picks</div>
          </div>
          <div class="dgm-grid">{cards}</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if candidates:
        with st.expander("🎯 Best qualified picks by market", expanded=False):
            rows = _market_rows(candidates)
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
                st.caption("Up to three qualified candidates per market. A missing market/game remains absent rather than receiving a placeholder score.")
            else:
                st.info("No market candidate currently clears the 70/100 Master Card qualification floor.")

        with st.expander("🧠 Daily Master Card rules", expanded=False):
            st.caption(
                "Read-only selector: production probabilities, simulation depths, sportsbook lines, Step 3 normalization, and per-game Step 5 rankings are unchanged. "
                "The Master Card only compares candidates that already have a real scored production payload."
            )


def _render_bridge_with_master(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Preserve V2.0.4's production-candidate patch before V2.0.3 renders the page.
    bridge.previous._production_candidates = bridge._production_candidates
    bridge.core._production_candidates = bridge._production_candidates

    st.markdown("### 🎯 Complete the game-market bridge")
    bridge._connector_row(games_df, "runline")
    bridge._connector_row(games_df, "total")

    _render_master(games_df)
    return bridge.previous.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)


# V2.0.5 resolves this module object at render time, so replacing the callable
# inserts Step 6 without duplicating or altering its quota-safe odds logic.
bridge.render_daily_game_picks = _render_bridge_with_master


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    bridge.render_daily_game_picks = _render_bridge_with_master
    return previous.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
