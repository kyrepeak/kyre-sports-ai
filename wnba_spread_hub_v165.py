"""WNBA Spread V1.6.5 — Top-5 Card Step 4: matchup analytics.

Presentation-only wrapper over the verified V1.6.4 Step-3 rendering layer.
Step 4 adds recent pace / offensive rating / defensive rating / net rating and
read-only offense-vs-defense matchup comparisons. It reuses the existing WNBA
context possession estimator and ESPN game summaries already present in the
repository. Nothing in this module feeds the protected V1.6.1 spread model,
SportsGameOdds market, analytical probability, 5,000,000 Monte Carlo,
convergence, qualification, selected side, edge/EV, Pick Strength or ranking.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_context_v26 as context
import wnba_spread_hub_v163 as step3
import wnba_spread_hub_v164 as previous

base = step3.base
MODEL_VERSION = "WNBA SPREAD V1.6.5 • TOP-5 CARD STEP 4 MATCHUP ANALYTICS"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _compact_html(fragment: str) -> str:
    """Prevent generated card HTML from becoming an indented Markdown code block."""
    return "".join(line.strip() for line in str(fragment or "").splitlines())


def _rating(value, signed=False) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    return f"{x:+.1f}" if signed else f"{x:.1f}"


def _reliability(samples: int) -> tuple[str, str]:
    n = int(samples or 0)
    if n >= 5:
        return "HIGH", "good"
    if n >= 3:
        return "MEDIUM", "mid"
    if n >= 1:
        return "LOW", "warn"
    return "NO DATA", "warn"


def _recent_team_rows(team_games: pd.DataFrame, team_id: int, limit: int = 5) -> pd.DataFrame:
    if team_games is None or team_games.empty:
        return pd.DataFrame()
    if not {"TEAM_ID", "GAME_DATE", "GAME_ID", "OPP_ID", "PF", "PA"}.issubset(team_games.columns):
        return pd.DataFrame()
    part = team_games.loc[
        pd.to_numeric(team_games["TEAM_ID"], errors="coerce").fillna(0).astype(int).eq(int(team_id))
    ].copy()
    if part.empty:
        return part
    part["GAME_DATE"] = pd.to_datetime(part["GAME_DATE"], errors="coerce")
    return part.dropna(subset=["GAME_DATE"]).sort_values("GAME_DATE", ascending=False).head(int(limit)).reset_index(drop=True)


def _profile_from_recent(recent: pd.DataFrame, team_id: int, adv_map: dict) -> dict:
    samples = []
    for _, game in recent.iterrows():
        gid = str(game.get("GAME_ID") or "")
        adv = adv_map.get(gid)
        if adv is None or not isinstance(adv, pd.DataFrame) or adv.empty:
            continue

        ids = pd.to_numeric(adv.get("TEAM_ID"), errors="coerce").fillna(0).astype(int)
        team_part = adv.loc[ids.eq(int(team_id))]
        opp_id = int(_num(game.get("OPP_ID"), 0) or 0)
        opp_part = adv.loc[ids.eq(opp_id)]
        if team_part.empty or opp_part.empty:
            continue

        team_poss = _num(team_part.iloc[0].get("POSS"), np.nan)
        opp_poss = _num(opp_part.iloc[0].get("POSS"), np.nan)
        pf = _num(game.get("PF"), np.nan)
        pa = _num(game.get("PA"), np.nan)
        if (
            not np.isfinite(team_poss)
            or not np.isfinite(opp_poss)
            or team_poss <= 0
            or opp_poss <= 0
            or not np.isfinite(pf)
            or not np.isfinite(pa)
        ):
            continue

        samples.append(
            {
                "pace": float((team_poss + opp_poss) / 2.0),
                "ortg": float(100.0 * pf / team_poss),
                "drtg": float(100.0 * pa / opp_poss),
            }
        )

    if not samples:
        return {
            "state": "NO_DATA",
            "samples": 0,
            "pace": np.nan,
            "ortg": np.nan,
            "drtg": np.nan,
            "netrtg": np.nan,
        }

    data = pd.DataFrame(samples)
    pace = float(pd.to_numeric(data["pace"], errors="coerce").mean())
    ortg = float(pd.to_numeric(data["ortg"], errors="coerce").mean())
    drtg = float(pd.to_numeric(data["drtg"], errors="coerce").mean())
    return {
        "state": "READY",
        "samples": int(len(data)),
        "pace": pace,
        "ortg": ortg,
        "drtg": drtg,
        "netrtg": float(ortg - drtg),
    }


@st.cache_data(ttl=900, show_spinner=False, max_entries=64)
def _pair_advanced(day_str: str, selected_id: int, opponent_id: int) -> dict:
    """Build one recent-five advanced snapshot for both teams with shared requests."""
    day = pd.to_datetime(day_str).normalize()
    season = int(day.year)
    try:
        team_games = context._season_team_games(season)
    except Exception as exc:
        return {"state": "UNAVAILABLE", "error": str(exc)[:180]}

    if team_games is None or team_games.empty:
        return {"state": "UNAVAILABLE", "error": "ESPN current-season team game index returned no completed WNBA games"}

    dates = pd.to_datetime(team_games.get("GAME_DATE"), errors="coerce")
    team_games = team_games.loc[dates < day].copy()
    if team_games.empty:
        return {"state": "UNAVAILABLE", "error": "no completed advanced-stat source games exist before this slate date"}

    selected_recent = _recent_team_rows(team_games, int(selected_id), 5)
    opponent_recent = _recent_team_rows(team_games, int(opponent_id), 5)
    ids = []
    for frame in (selected_recent, opponent_recent):
        if frame is not None and not frame.empty:
            ids.extend(frame["GAME_ID"].astype(str).tolist())
    game_ids = list(dict.fromkeys(gid for gid in ids if gid))
    if not game_ids:
        return {"state": "UNAVAILABLE", "error": "recent ESPN game IDs could not be resolved for either matchup team"}

    adv_map = {}
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(game_ids)))) as pool:
        futures = {pool.submit(context._game_advanced, gid): gid for gid in game_ids}
        for future in as_completed(futures):
            gid = futures[future]
            try:
                result = future.result()
                adv_map[gid] = result if isinstance(result, pd.DataFrame) else pd.DataFrame()
            except Exception:
                adv_map[gid] = pd.DataFrame()

    selected = _profile_from_recent(selected_recent, int(selected_id), adv_map)
    opponent = _profile_from_recent(opponent_recent, int(opponent_id), adv_map)
    available = int(selected.get("samples", 0) or 0) + int(opponent.get("samples", 0) or 0)
    if available <= 0:
        return {
            "state": "UNAVAILABLE",
            "error": "recent ESPN game summaries did not yield valid possession samples for this matchup",
            "selected": selected,
            "opponent": opponent,
        }

    return {
        "state": "READY" if selected.get("samples", 0) and opponent.get("samples", 0) else "PARTIAL",
        "season": season,
        "selected": selected,
        "opponent": opponent,
        "source": "ESPN WNBA recent game summaries",
        "formula": "POSS ≈ FGA + 0.44×FTA − OREB + TO",
    }


def _team_advanced_html(team_name: str, team_id: int, role: str, profile: dict) -> str:
    team = escape(str(team_name or "Team"))
    role_text = escape(str(role or "TEAM"))
    logo = escape(step3.prior._logo(int(team_id)), quote=True)
    img = f'<img src="{logo}" alt="{team} logo">' if logo else "🏀"
    samples = int(profile.get("samples", 0) or 0)
    rel, rel_class = _reliability(samples)

    if str(profile.get("state") or "").upper() != "READY":
        return f"""
        <div class="ks-spread165-team">
          <div class="ks-spread165-teamhead"><span class="ks-spread165-logo">{img}</span><span><b>{team}</b><small>{role_text}</small></span><span class="ks-spread165-chip {rel_class}">{rel}</span></div>
          <div class="ks-spread165-empty">No valid recent advanced possession sample was available for this team.</div>
        </div>
        """

    return f"""
    <div class="ks-spread165-team">
      <div class="ks-spread165-teamhead">
        <span class="ks-spread165-logo">{img}</span>
        <span><b>{team}</b><small>{role_text} • RECENT {samples}/5 VALID GAME(S)</small></span>
        <span class="ks-spread165-chip {rel_class}">{rel}</span>
      </div>
      <div class="ks-spread165-grid">
        <div><small>RECENT PACE EST.</small><strong>{_rating(profile.get('pace'))}</strong></div>
        <div><small>OFF RTG</small><strong>{_rating(profile.get('ortg'))}</strong></div>
        <div><small>DEF RTG</small><strong>{_rating(profile.get('drtg'))}</strong></div>
        <div><small>NET RTG</small><strong>{_rating(profile.get('netrtg'), signed=True)}</strong></div>
      </div>
    </div>
    """


def _comparison_html(selected_name: str, opponent_name: str, selected: dict, opponent: dict) -> str:
    sel_pace = _num(selected.get("pace"), np.nan)
    opp_pace = _num(opponent.get("pace"), np.nan)
    sel_ortg = _num(selected.get("ortg"), np.nan)
    opp_ortg = _num(opponent.get("ortg"), np.nan)
    sel_drtg = _num(selected.get("drtg"), np.nan)
    opp_drtg = _num(opponent.get("drtg"), np.nan)
    sel_net = _num(selected.get("netrtg"), np.nan)
    opp_net = _num(opponent.get("netrtg"), np.nan)

    blended_pace = float(np.nanmean([sel_pace, opp_pace])) if np.isfinite(sel_pace) or np.isfinite(opp_pace) else np.nan
    selected_ovd = sel_ortg - opp_drtg if np.isfinite(sel_ortg) and np.isfinite(opp_drtg) else np.nan
    opponent_ovd = opp_ortg - sel_drtg if np.isfinite(opp_ortg) and np.isfinite(sel_drtg) else np.nan
    net_adv = sel_net - opp_net if np.isfinite(sel_net) and np.isfinite(opp_net) else np.nan

    if np.isfinite(net_adv):
        if net_adv >= 5.0:
            read = f"{selected_name} has the stronger recent efficiency profile."
            read_class = "good"
        elif net_adv <= -5.0:
            read = f"{opponent_name} has the stronger recent efficiency profile."
            read_class = "bad"
        else:
            read = "Recent efficiency profiles are relatively balanced."
            read_class = "mid"
    else:
        read = "Advanced comparison is partial because one or more recent efficiency fields are unavailable."
        read_class = "warn"

    return f"""
    <div class="ks-spread165-compare">
      <div class="ks-spread165-comparehead">RECENT MATCHUP COMPARISON • CONTEXT ONLY</div>
      <div class="ks-spread165-compgrid">
        <div><small>BLENDED RECENT PACE</small><strong>{_rating(blended_pace)}</strong></div>
        <div><small>SELECTED NET RTG ADV.</small><strong>{_rating(net_adv, signed=True)}</strong></div>
        <div><small>SELECTED OFFENSE vs OPP DEF</small><strong>{_rating(selected_ovd, signed=True)}</strong></div>
        <div><small>OPP OFFENSE vs SELECTED DEF</small><strong>{_rating(opponent_ovd, signed=True)}</strong></div>
        <div class="wide"><small>EFFICIENCY READ</small><strong class="{read_class}">{escape(read)}</strong></div>
      </div>
    </div>
    """


def _matchup_block(day_str: str, row) -> str:
    try:
        selected_is_home = step3.prior._is_home(row)
        away_id, home_id, identity_source = step3.prior._resolved_team_ids(str(day_str), row)
        if not away_id or not home_id:
            raise ValueError("team IDs could not be resolved from the verified daily schedule")

        away_name = str(row.get("away_team") or "Away")
        home_name = str(row.get("home_team") or "Home")
        selected_id = home_id if selected_is_home else away_id
        opponent_id = away_id if selected_is_home else home_id
        selected_name = str(row.get("best_side") or (home_name if selected_is_home else away_name))
        opponent_name = away_name if selected_is_home else home_name

        pair = _pair_advanced(str(day_str), int(selected_id), int(opponent_id))
        state = str(pair.get("state") or "UNAVAILABLE").upper()
        if state == "UNAVAILABLE":
            raise RuntimeError(str(pair.get("error") or "recent advanced matchup source unavailable"))
        selected = pair.get("selected") or {}
        opponent = pair.get("opponent") or {}
        season = int(pair.get("season") or pd.to_datetime(day_str).year)
        source = str(pair.get("source") or "ESPN WNBA recent game summaries")
        formula = str(pair.get("formula") or "POSS ≈ FGA + 0.44×FTA − OREB + TO")
    except Exception as exc:
        return _compact_html(f"""
        <div class="ks-spread165-wrap">
          <div class="ks-spread165-head"><span>STEP 4 • MATCHUP ANALYTICS</span><span class="ks-spread165-chip warn">SOURCE CHECK</span></div>
          <div class="ks-spread165-empty">Recent advanced matchup context is temporarily unavailable. Steps 1–3 and the verified Spread model remain unchanged.</div>
          <div class="ks-spread165-note">Diagnostic • {escape(str(exc)[:180])}</div>
        </div>
        """)

    sel_n = int(selected.get("samples", 0) or 0)
    opp_n = int(opponent.get("samples", 0) or 0)
    status = "VERIFIED ADVANCED" if sel_n > 0 and opp_n > 0 else "PARTIAL ADVANCED"
    status_class = "good" if sel_n > 0 and opp_n > 0 else "warn"

    return _compact_html(f"""
    <div class="ks-spread165-wrap">
      <div class="ks-spread165-head"><span>STEP 4 • MATCHUP ANALYTICS</span><span class="ks-spread165-chip {status_class}">{status}</span></div>
      <div class="ks-spread165-scope">{season} • recent-five advanced window • completed games strictly before this slate • no future-game leakage</div>
      <div class="ks-spread165-teams">
        {_team_advanced_html(selected_name, selected_id, 'SELECTED SPREAD SIDE', selected)}
        {_team_advanced_html(opponent_name, opponent_id, 'OPPONENT', opponent)}
      </div>
      {_comparison_html(selected_name, opponent_name, selected, opponent)}
      <div class="ks-spread165-note">Source • {escape(source)} • {escape(formula)} • identity • {escape(str(identity_source))} • Pace is an approximate recent possession environment; OffRtg/DefRtg are points per 100 estimated possessions. Descriptive only • NOT FED INTO projected margin, 5M Monte Carlo, market probability, edge, EV, qualification, selected side, Pick Strength or card ranking.</div>
    </div>
    """)


def _form_plus_step4(day_str: str, row) -> str:
    # Use V1.6.4's already-fixed Step-3 fragment, then append compact Step-4 HTML.
    return previous._clean_form_block(day_str, row) + _matchup_block(day_str, row)


def _install_step4() -> None:
    # First restore V1.6.4's clean Step-3 seam, then append Step 4 at that same
    # presentation boundary. Nothing beneath the card renderer is mutated.
    previous._install_render_repair()
    step3._form_block = _form_plus_step4


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install_step4()
    st.markdown(
        """
<style>
.ks-spread165-wrap{background:#0a1723;border:1px solid #36546d;border-radius:15px;padding:12px;margin-top:14px}
.ks-spread165-head{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#9ed9ff;font-size:.59rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
.ks-spread165-scope{color:#8198aa;font-size:.54rem;margin:7px 0 9px}.ks-spread165-teams{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.ks-spread165-team{background:#081522;border:1px solid #284b64;border-radius:12px;padding:10px}.ks-spread165-teamhead{display:grid;grid-template-columns:34px 1fr auto;align-items:center;gap:7px;margin-bottom:9px}
.ks-spread165-teamhead b{display:block;color:#f5fbff;font-size:.73rem;line-height:1.15}.ks-spread165-teamhead small{display:block;color:#7890a5;font-size:.44rem;font-weight:900;margin-top:3px;letter-spacing:.03em}
.ks-spread165-logo{width:32px;height:32px;display:flex;align-items:center;justify-content:center}.ks-spread165-logo img{max-width:32px;max-height:32px;object-fit:contain}
.ks-spread165-chip{border-radius:999px;padding:5px 7px;border:1px solid #355873;color:#bed4e3;font-size:.45rem;font-weight:950;white-space:nowrap}.ks-spread165-chip.good{border-color:#237a59;background:#0b3327;color:#7df2ba}.ks-spread165-chip.mid{border-color:#826c16;background:#3a3009;color:#ffe17a}.ks-spread165-chip.warn,.ks-spread165-chip.bad{border-color:#7c5832;background:#352516;color:#ffc984}
.ks-spread165-grid,.ks-spread165-compgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.ks-spread165-grid div,.ks-spread165-compgrid div{background:#07131f;border:1px solid #24445c;border-radius:9px;padding:8px}.ks-spread165-compgrid .wide{grid-column:1/-1}
.ks-spread165-grid small,.ks-spread165-compgrid small{display:block;color:#718ba0;font-size:.42rem;font-weight:950;letter-spacing:.035em}.ks-spread165-grid strong,.ks-spread165-compgrid strong{display:block;color:#f6fbff;font-size:.69rem;margin-top:3px;line-height:1.3}
.ks-spread165-compgrid strong.good{color:#7df2ba}.ks-spread165-compgrid strong.bad{color:#ffb0b7}.ks-spread165-compgrid strong.mid{color:#ffe17a}.ks-spread165-compgrid strong.warn{color:#ffc984}
.ks-spread165-compare{margin-top:9px;background:#081522;border:1px solid #284b64;border-radius:12px;padding:10px}.ks-spread165-comparehead{color:#a8cce2;font-size:.49rem;font-weight:950;letter-spacing:.045em;margin-bottom:7px}
.ks-spread165-note{color:#6f8799;font-size:.50rem;line-height:1.45;margin-top:8px}.ks-spread165-empty{color:#c8d7e3;font-size:.63rem;line-height:1.5;margin-top:8px}
@media(max-width:760px){.ks-spread165-head{align-items:flex-start}.ks-spread165-teams{grid-template-columns:1fr}.ks-spread165-chip{font-size:.43rem}}
</style>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "🎨 Spread V1.6.5 • Top-5 Card Steps 1–4 ACTIVE • verified model snapshot + official WNBA H2H + "
        "team form + recent advanced matchup analytics • all new context remains presentation-only"
    )
    # Call V1.6.3 directly so V1.6.4 does not overwrite the Step-4 wrapper after
    # we install it above. V1.6.3 still installs the verified Step-2/Step-3 card seam.
    return step3.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(previous, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
