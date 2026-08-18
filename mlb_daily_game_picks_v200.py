"""MLB Daily Game Picks V2.0 — Step 5 Top-3 selector.

Reads only already-built production connector caches, converts each verified output
through the existing Step 3 cross-market normalization contract, and selects the
Top 3 scored candidates for every MLB game. No production probability model is
reimplemented here and no missing input is fabricated.

Connected production families:
- 1+ Hit V2.1
- Home Run HR V1.1
- H+R+RBI V1.0
- Pitcher K V1.0.x
- Moneyline V16.3

Run Line and Total retain the existing Step 4 fallback bridge until dedicated
connectors are individually verified.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_daily_game_picks_v199 as base
import mlb_daily_game_picks_v12 as step3
import mlb_daily_game_picks_v13 as step4

VERSION = "MLB Daily Game Picks V2.0 • STEP 5 TOP-3 SELECTOR"
_DIRECT_MARKETS = {"1+ Hit", "Home Run", "H+R+RBI", "Pitcher Strikeouts", "Moneyline"}
_PLAYER_MARKETS = {"1+ Hit", "Home Run", "H+R+RBI", "Pitcher Strikeouts"}
_orig_step4_candidates = step4._production_candidates


def _finite(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _clamp(v, lo=0.0, hi=1.0):
    x = _finite(v, lo)
    return max(lo, min(hi, x))


def _gamepk(row):
    try:
        return str(int(float(row.get("game_pk"))))
    except Exception:
        return str(row.get("game_pk") or row.get("gamePk") or "")


def _day(row):
    try:
        return str(row.get("game_date") or "")[:10]
    except Exception:
        return ""


def _same_game(r, gpk):
    try:
        return str(int(float(r.get("game_pk")))) == str(gpk)
    except Exception:
        return str(r.get("game_pk") or "") == str(gpk)


def _scored(*, market, name, side, line, probability, reliability, data_quality,
            confirmed, source, team=None, extra=None):
    p = _finite(probability)
    rel = _finite(reliability)
    dq = _finite(data_quality)
    if p is None or rel is None or dq is None:
        return None
    norm = step3.normalize_candidate(
        market=market,
        probability=p,
        reliability=_clamp(rel),
        data_quality=_clamp(dq),
        confirmed=bool(confirmed),
        uncertainty=None,
        stale=False,
    )
    if norm.get("status") != "SCORED":
        return None
    out = {
        "market": market,
        "name": str(name or "Candidate"),
        "side": str(side or ""),
        "line": line,
        "probability": p,
        "reliability": _clamp(rel),
        "data_quality": _clamp(dq),
        "score": float(norm["score"]),
        "source": source,
        "normalization": norm,
        "team": team,
    }
    if extra:
        out.update(extra)
    return out


def _hit_candidates(row):
    day = _day(row); gpk = _gamepk(row)
    pack = st.session_state.get(f"dgp_prod_1hit_v15::{day}", {}) or {}
    out = []
    for r in pack.get("rows", []) or []:
        if not _same_game(r, gpk):
            continue
        p = _finite(r.get("p")); rel = _finite(r.get("reliability"))
        sample = max(0.0, _finite(r.get("sample"), 0.0) or 0.0)
        if p is None or rel is None:
            continue
        sample_q = _clamp(sample / 400.0)
        dq = _clamp(.35 * rel + .65 * sample_q)
        c = _scored(
            market="1+ Hit",
            name=r.get("player") or r.get("player_name"),
            side="1+ Hit",
            line=.5,
            probability=p,
            reliability=rel,
            data_quality=dq,
            confirmed=bool(r.get("confirmed")),
            source="1+ Hit V2.1 production fast scan",
            team=r.get("team"),
            extra={"sample": sample, "sample_unit": r.get("sample_unit")},
        )
        if c:
            out.append(c)
    return out


def _hr_candidates(row):
    day = _day(row); gpk = _gamepk(row)
    pack = st.session_state.get(f"dgp_prod_hr_v16::{day}", {}) or {}
    out = []
    for r in pack.get("rows", []) or []:
        if not _same_game(r, gpk):
            continue
        p = _finite(r.get("p_hr"))
        dq = _clamp((_finite(r.get("data_score"), 0.0) or 0.0) / 7.0)
        season_rel = _finite(r.get("season_reliability"), 0.0) or 0.0
        sc_rel = _finite(r.get("statcast_reliability"), 0.0) or 0.0
        rel = _clamp(.70 * season_rel + .30 * sc_rel)
        c = _scored(
            market="Home Run",
            name=r.get("player_name"),
            side="1+ HR",
            line=.5,
            probability=p,
            reliability=rel,
            data_quality=dq,
            confirmed=bool(r.get("lineup_confirmed")),
            source="HR V1.1 calibrated production model",
            team=r.get("team"),
            extra={"expected_hr": r.get("expected_hr"), "confidence": r.get("confidence")},
        )
        if c:
            out.append(c)
    return out


def _hrr_candidates(row):
    day = _day(row); gpk = _gamepk(row)
    pack = st.session_state.get(f"dgp_prod_hrrbi_v17::{day}", {}) or {}
    out = []
    for r in pack.get("rows", []) or []:
        if not _same_game(r, gpk):
            continue
        sim = r.get("sim") or {}
        p = _finite(sim.get("p2"))
        dq = _clamp((_finite(r.get("data_score"), 0.0) or 0.0) / 7.0)
        profile = r.get("profile") or {}
        pa = max(0.0, _finite(profile.get("pa"), 0.0) or 0.0)
        sample_rel = pa / (pa + 180.0) if pa > 0 else 0.0
        rel = _clamp(.65 * sample_rel + .35 * dq)
        c = _scored(
            market="H+R+RBI",
            name=r.get("player_name"),
            side="2+ H+R+RBI",
            line=1.5,
            probability=p,
            reliability=rel,
            data_quality=dq,
            confirmed=bool(r.get("lineup_confirmed")),
            source="H+R+RBI V1.0 joint-event production model",
            team=r.get("team"),
            extra={
                "expected_total": sim.get("expected_total"),
                "median": sim.get("median"),
                "mode": sim.get("mode"),
                "simulations": sim.get("n"),
            },
        )
        if c:
            out.append(c)
    return out


def _pitcher_k_candidates(row):
    day = _day(row); gpk = _gamepk(row)
    pack = st.session_state.get(f"dgp_prod_pitcherk_v18::{day}", {}) or {}
    out = []
    for r in pack.get("rows", []) or []:
        if not _same_game(r, gpk):
            continue
        grade = r.get("grade") or {}
        p = _finite(grade.get("win_prob"))
        rel = _clamp(_finite(r.get("reliability"), 0.0) or 0.0)
        opp = max(0.0, _finite(r.get("opp_sample"), 0.0) or 0.0)
        dq = _clamp(.75 * rel + .25 * _clamp(opp / 1200.0))
        line = _finite(grade.get("line"))
        side = str(grade.get("side") or "")
        side_text = f"{side} {line:g}" if line is not None else side
        c = _scored(
            market="Pitcher Strikeouts",
            name=r.get("player_name"),
            side=side_text,
            line=line,
            probability=p,
            reliability=rel,
            data_quality=dq,
            confirmed=bool(r.get("opp_lineup_confirmed")),
            source="Pitcher K V1.0.x production model",
            team=r.get("team"),
            extra={
                "expected_k": (r.get("sim") or {}).get("mean"),
                "fair_odds": grade.get("fair_odds"),
                "push_probability": grade.get("p_push"),
            },
        )
        if c:
            out.append(c)
    return out


def _confidence_rel(v):
    t = str(v or "").upper()
    if t == "HIGH": return .90
    if "MEDIUM-HIGH" in t: return .80
    if "MEDIUM" in t: return .70
    return .58


def _moneyline_candidates(row):
    day = _day(row); gpk = _gamepk(row)
    pack = st.session_state.get(f"dgp_prod_moneyline_v19::{day}", {}) or {}
    out = []
    confirmed = step4.base.base.base._confirmed_flag(row)
    for r in pack.get("rows", []) or []:
        if not _same_game(r, gpk):
            continue
        rel = _confidence_rel(r.get("confidence"))
        dq = _clamp((_finite(r.get("data_score"), 0.0) or 0.0) / 9.0)
        sides = (
            (r.get("away_name"), r.get("final_away"), "away"),
            (r.get("home_name"), r.get("final_home"), "home"),
        )
        for team, p, side_name in sides:
            c = _scored(
                market="Moneyline",
                name=team,
                side="ML",
                line=None,
                probability=p,
                reliability=rel,
                data_quality=dq,
                confirmed=confirmed,
                source="Moneyline V16.3 production model",
                team=team,
                extra={
                    "confidence": r.get("confidence"),
                    "simulations": r.get("simulations"),
                    "mc_se": r.get("mc_se"),
                    "converged": r.get("converged"),
                    "model_side": side_name,
                },
            )
            if c:
                out.append(c)
    return out


def _direct_candidates(row, market):
    if market == "1+ Hit": return _hit_candidates(row)
    if market == "Home Run": return _hr_candidates(row)
    if market == "H+R+RBI": return _hrr_candidates(row)
    if market == "Pitcher Strikeouts": return _pitcher_k_candidates(row)
    if market == "Moneyline": return _moneyline_candidates(row)
    return []


def _production_candidates(row, market):
    if market in _DIRECT_MARKETS:
        rows = _direct_candidates(row, market)
    else:
        # Preserve the old verified read-only bridge for Run Line / Total until
        # those two families receive dedicated connectors.
        try:
            rows = _orig_step4_candidates(row, market)
        except Exception:
            rows = []
    uniq = {}
    for c in rows or []:
        key = (
            c.get("market"), c.get("name"), c.get("side"), str(c.get("line")),
            round(_finite(c.get("probability"), 0.0) or 0.0, 7),
        )
        uniq[key] = c
    return sorted(
        uniq.values(),
        key=lambda x: (
            _finite(x.get("score"), 0.0) or 0.0,
            _finite(x.get("reliability"), 0.0) or 0.0,
            _finite(x.get("data_quality"), 0.0) or 0.0,
            _finite(x.get("probability"), 0.0) or 0.0,
        ),
        reverse=True,
    )


def _all_candidates(row):
    out = []
    for market in step4.base.base.MARKETS:
        out.extend(_production_candidates(row, market))
    return out


def _top3(row):
    ordered = sorted(
        _all_candidates(row),
        key=lambda x: (
            _finite(x.get("score"), 0.0) or 0.0,
            _finite(x.get("reliability"), 0.0) or 0.0,
            _finite(x.get("data_quality"), 0.0) or 0.0,
            _finite(x.get("probability"), 0.0) or 0.0,
        ),
        reverse=True,
    )
    selected = []
    used_player = set()
    moneyline_used = False
    used_exact = set()

    # First pass: strongest normalized candidates with a light correlation guard.
    for c in ordered:
        exact = (c.get("market"), c.get("name"), c.get("side"), str(c.get("line")))
        if exact in used_exact:
            continue
        market = c.get("market")
        if market == "Moneyline":
            if moneyline_used:
                continue
        elif market in _PLAYER_MARKETS:
            ident = (str(c.get("name") or "").lower(), str(c.get("team") or "").lower())
            if ident in used_player:
                continue
        selected.append(c)
        used_exact.add(exact)
        if market == "Moneyline": moneyline_used = True
        elif market in _PLAYER_MARKETS: used_player.add(ident)
        if len(selected) == 3:
            return selected

    # Second pass only relaxes the same-player guard if a game otherwise has fewer
    # than three real scored candidates. Opposite Moneyline sides remain blocked.
    for c in ordered:
        exact = (c.get("market"), c.get("name"), c.get("side"), str(c.get("line")))
        if exact in used_exact:
            continue
        if c.get("market") == "Moneyline" and moneyline_used:
            continue
        selected.append(c)
        used_exact.add(exact)
        if c.get("market") == "Moneyline": moneyline_used = True
        if len(selected) == 3:
            break
    return selected


def _css():
    st.markdown("""
<style>
.dgp-game .dgp-slots{display:none!important}
.dgp5-panel{border:1px solid #315574;background:linear-gradient(145deg,#0b1c30,#081522);border-radius:18px;padding:13px 14px;margin:-7px 0 10px}
.dgp5-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:10px}.dgp5-head b{font-size:11px;color:#60ddff;letter-spacing:1.2px;text-transform:uppercase}.dgp5-head span{font-size:10px;color:#8299ae}
.dgp5-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.dgp5-pick{border:1px solid #2e4d69;border-radius:15px;background:#0b1929;padding:11px;min-height:145px}.dgp5-pick.first{border-color:#b99a25}.dgp5-rank{font-size:10px;color:#5cdcff;font-weight:950;letter-spacing:1px}.dgp5-market{font-size:10px;color:#92a8bc;font-weight:850;margin-top:7px}.dgp5-name{font-size:15px;color:#fff;font-weight:950;margin-top:3px}.dgp5-side{font-size:11px;color:#d2dfeb;margin-top:4px}.dgp5-score{font-size:23px;color:#fff;font-weight:1000;margin-top:10px}.dgp5-score small{font-size:9px;color:#8198ad;font-weight:850}.dgp5-meta{font-size:9px;color:#8299ae;line-height:1.45;margin-top:5px}.dgp5-empty{font-size:13px;color:#aab9c7;font-weight:850;margin-top:14px}.dgp5-note{font-size:9px;color:#71889e;margin-top:5px;line-height:1.4}
@media(max-width:700px){.dgp5-grid{grid-template-columns:1fr}.dgp5-pick{min-height:0}}
</style>
""", unsafe_allow_html=True)


def _pick_html(c, rank):
    medals = {1:"🥇", 2:"🥈", 3:"🥉"}
    medal = medals.get(rank, "•")
    return f'''<div class="dgp5-pick {'first' if rank == 1 else ''}">
      <div class="dgp5-rank">{medal} PICK {rank}</div>
      <div class="dgp5-market">{step4.base.base._esc(c.get('market'))}</div>
      <div class="dgp5-name">{step4.base.base._esc(c.get('name'))}</div>
      <div class="dgp5-side">{step4.base.base._esc(c.get('side'))}</div>
      <div class="dgp5-score">{c.get('score',0):.1f}<small> / 100 PICK STRENGTH</small></div>
      <div class="dgp5-meta">Model {c.get('probability',0)*100:.1f}% • Reliability {c.get('reliability',0)*100:.0f}% • Data {c.get('data_quality',0)*100:.0f}%</div>
      <div class="dgp5-note">{step4.base.base._esc(c.get('source'))}</div>
    </div>'''


def _render_game(row, idx):
    # Render the existing Step 1-3 card; V2.0 CSS hides its old placeholder slots.
    step4.base._render_game(row, idx)
    gamepk = _gamepk(row)
    picks = _top3(row)

    cards = ''.join(_pick_html(c, i) for i, c in enumerate(picks, 1))
    for i in range(len(picks) + 1, 4):
        cards += f'''<div class="dgp5-pick"><div class="dgp5-rank">{'🥇' if i==1 else '🥈' if i==2 else '🥉'} PICK {i}</div>
        <div class="dgp5-empty">Waiting for a scored production candidate</div>
        <div class="dgp5-note">No probability, reliability, or data-quality value is fabricated to force this slot.</div></div>'''

    st.markdown(
        '<div class="dgp5-panel"><div class="dgp5-head"><b>Step 5 • Final Top 3</b>'
        f'<span>{len(picks)}/3 scored picks • MLB ID {step4.base.base._esc(gamepk)}</span></div>'
        f'<div class="dgp5-grid">{cards}</div></div>',
        unsafe_allow_html=True,
    )

    allc = []
    cells = []
    for market in step4.base.base.MARKETS:
        cs = _production_candidates(row, market)
        allc.extend(cs)
        if cs:
            best = cs[0]
            state = "CONNECTED"
            detail = f"{len(cs)} scored • best {best['score']:.1f}/100"
        else:
            state = "UNCONNECTED"
            detail = "No complete verified production payload found"
        cells.append(
            f'<div class="dgp-bridge"><span>{step4.base.base._esc(market)}</span><b>{state}</b><small>{step4.base.base._esc(detail)}</small></div>'
        )
    st.markdown(
        '<div class="dgp-bridge-title">Step 4 • Production model bridge</div><div class="dgp-bridgegrid">'
        + ''.join(cells) + '</div>',
        unsafe_allow_html=True,
    )

    with st.expander(f"🔌 Step 4/5 scoring audit • Game {idx} • MLB ID {gamepk}", expanded=False):
        if allc:
            selected_keys = {(c.get('market'), c.get('name'), c.get('side'), str(c.get('line'))) for c in picks}
            rows = []
            for c in sorted(allc, key=lambda x: x.get("score", 0), reverse=True):
                key = (c.get('market'), c.get('name'), c.get('side'), str(c.get('line')))
                rows.append({
                    "Top 3": "✅" if key in selected_keys else "",
                    "Market": c.get("market"),
                    "Candidate": c.get("name"),
                    "Side": c.get("side"),
                    "Model probability": f"{c.get('probability',0)*100:.1f}%",
                    "Reliability": f"{c.get('reliability',0)*100:.0f}%",
                    "Data quality": f"{c.get('data_quality',0)*100:.0f}%",
                    "Pick Strength": f"{c.get('score',0):.1f}",
                    "Source": c.get("source"),
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.caption("Top 3 is ranked by the existing Step 3 Pick Strength score. Same-player duplicates are avoided when possible; opposite Moneyline sides can never both be selected.")
        else:
            st.info("No complete production payload is connected for this game yet. Build the production connectors above; nothing is estimated or imputed here.")


def _render_page(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    step4.base.base.base._css()
    step4.base.base._step2_css()
    step4.base._css()
    step4._css()
    _css()
    if games_df is None or games_df.empty:
        st.info("No verified MLB games are available for the selected date.")
        return
    frame = step4.base.base.base._sort_games(games_df)
    day = step4.base.base.base._txt(frame.iloc[0], "game_date", default="")[:10]
    total_picks = sum(len(_top3(row)) for _, row in frame.iterrows())
    st.markdown('''<div class="dgp-hero"><div class="dgp-kicker">KYRE SPORTS AI • DAILY GAME PICKS • STEP 5</div><div class="dgp-title">🏆 Top 3 Picks — Every MLB Game</div><div class="dgp-sub">Step 5 ranks only scored production outputs through the existing Step 3 market-aware normalization contract. Raw percentages from unlike markets are never compared directly. Missing production inputs remain unselected, and a light correlation guard avoids duplicate same-player props when possible.</div></div>''', unsafe_allow_html=True)
    st.success(f"🏆 Step 5 Top-3 selector active • {day or 'selected date'} • {len(frame)} games • {total_picks} qualified pick slots currently populated • no synthetic model inputs")
    for i, (_, row) in enumerate(frame.iterrows(), 1):
        _render_game(row, i)
    st.markdown(
        f'<div class="dgp-foot">{VERSION} • five dedicated production connectors + verified Step 4 fallback for remaining markets • Step 3 normalization unchanged • no fabricated probabilities • correlation guard active</div>',
        unsafe_allow_html=True,
    )


# Install the robust direct cache bridge and Step 5 renderer into the original
# Step 4 module object. All connector inheritance chains resolve that object at
# render time, so no production connector needs to be rewritten.
step4._production_candidates = _production_candidates
step4._render_game = _render_game
step4.render_daily_game_picks = _render_page


def render_daily_game_picks(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    # Reinstall patches defensively in case Streamlit reload order replaced them.
    step4._production_candidates = _production_candidates
    step4._render_game = _render_game
    step4.render_daily_game_picks = _render_page
    return base.render_daily_game_picks(games_df, section_header, status_info, team_logo, h)
