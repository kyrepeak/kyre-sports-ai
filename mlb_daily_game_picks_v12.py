"""MLB Daily Game Picks V1.2 — Step 3 cross-market normalization contract.

Defines a single auditable 0-100 Pick Strength Score for future game-level ranking.
No Top-3 recommendation is emitted yet. Critically, candidates without a verified
production-model probability/edge remain UNSCORED rather than receiving synthetic
or guessed values.
"""
from __future__ import annotations

import math
import streamlit as st

import mlb_daily_game_picks_v11 as base

VERSION = "MLB Daily Game Picks V1.2 • STEP 3"

# Neutral probability baselines are comparison anchors, not sportsbook priors.
# Step 4 will feed each candidate's REAL production probability + reliability.
MARKET_RULES = {
    "1+ Hit": {"baseline":0.650,"uncertainty":0.080,"min_rel":0.55,"family":"PLAYER"},
    "Home Run": {"baseline":0.120,"uncertainty":0.100,"min_rel":0.55,"family":"PLAYER"},
    "H+R+RBI": {"baseline":0.500,"uncertainty":0.120,"min_rel":0.55,"family":"PLAYER"},
    "Pitcher Strikeouts": {"baseline":0.500,"uncertainty":0.100,"min_rel":0.58,"family":"PLAYER"},
    "Moneyline": {"baseline":0.500,"uncertainty":0.070,"min_rel":0.60,"family":"GAME"},
    "Run Line": {"baseline":0.500,"uncertainty":0.100,"min_rel":0.60,"family":"GAME"},
    "Total": {"baseline":0.500,"uncertainty":0.100,"min_rel":0.60,"family":"GAME"},
}

WEIGHTS = {
    "probability_strength":0.34,
    "market_relative_edge":0.26,
    "model_reliability":0.18,
    "data_quality":0.12,
    "confirmation":0.06,
    "uncertainty":0.04,
}


def _clamp(x,lo=0.0,hi=1.0):
    return max(lo,min(hi,float(x)))


def normalize_candidate(*, market, probability=None, reliability=None, data_quality=None,
                        confirmed=False, uncertainty=None, stale=False):
    """Return an auditable score only when real production inputs are present.

    probability must come from an existing production engine. No imputation occurs.
    """
    rule=MARKET_RULES.get(str(market))
    if not rule or probability is None or reliability is None or data_quality is None:
        return {"status":"UNSCORED","score":None,"reason":"verified production probability/reliability/data-quality input not connected"}
    try:
        p=_clamp(probability,.001,.999); rel=_clamp(reliability); dq=_clamp(data_quality)
        unc=float(uncertainty if uncertainty is not None else rule["uncertainty"])
    except Exception:
        return {"status":"UNSCORED","score":None,"reason":"invalid normalization input"}

    # Absolute probability is market-aware: rare-event markets are not punished merely
    # because their raw probability is naturally lower than 1+ Hit probabilities.
    b=float(rule["baseline"]); scale=max(.08, min(.35, b*(1-b)*1.65))
    relative=_clamp(.5 + (p-b)/(2*scale))
    edge=_clamp(.5 + (p-b)/(2*max(.05,unc)))
    confirmation=1.0 if confirmed else .55
    uncertainty_score=1.0-_clamp(unc/.25)

    score100=100.0*(
        WEIGHTS["probability_strength"]*relative +
        WEIGHTS["market_relative_edge"]*edge +
        WEIGHTS["model_reliability"]*rel +
        WEIGHTS["data_quality"]*dq +
        WEIGHTS["confirmation"]*confirmation +
        WEIGHTS["uncertainty"]*uncertainty_score
    )
    if stale: score100-=8.0
    if rel < float(rule["min_rel"]): score100-=10.0*(float(rule["min_rel"])-rel)/max(.01,float(rule["min_rel"]))
    score100=max(0.0,min(100.0,score100))
    return {
        "status":"SCORED","score":score100,"probability":p,"baseline":b,
        "relative_component":relative,"edge_component":edge,"reliability":rel,
        "data_quality":dq,"confirmation":confirmation,"uncertainty":unc,
        "stale":bool(stale),
    }


def _css():
    st.markdown("""
<style>
.dgp-norm-title{font-size:11px;letter-spacing:1.4px;font-weight:900;color:#9eb3c8;text-transform:uppercase;margin:12px 0 8px}
.dgp-norm-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:7px;margin:0 0 10px}
.dgp-norm{border:1px solid #29435e;border-radius:12px;background:#0c1b2d;padding:9px 8px;min-height:86px}.dgp-norm span{display:block;color:#dbe7f4;font-size:10px;font-weight:850}.dgp-norm b{display:block;color:#54dbff;font-size:10px;margin-top:7px}.dgp-norm small{display:block;color:#748aa1;font-size:9px;margin-top:3px;line-height:1.3}
.dgp-formula{border:1px solid #31516e;border-radius:14px;background:#0a1728;padding:12px 14px;color:#a8bdd1;font-size:11px;line-height:1.55;margin:8px 0 12px}.dgp-formula strong{color:#f5f8fc}
@media(max-width:900px){.dgp-norm-grid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:620px){.dgp-norm-grid{grid-template-columns:repeat(2,1fr)}}
</style>
""",unsafe_allow_html=True)


def _norm_html():
    cells=[]
    for m in base.MARKETS:
        r=MARKET_RULES[m]
        cells.append(f'''<div class="dgp-norm"><span>{base._esc(m)}</span><b>NORMALIZATION READY</b><small>Baseline {r['baseline']*100:.0f}% • Min reliability {r['min_rel']*100:.0f}% • {r['family']}</small></div>''')
    return '<div class="dgp-norm-grid">'+''.join(cells)+'</div>'


def _render_game(row,idx):
    # Preserve verified game identity + Step 2 availability shell.
    away=base.base._txt(row,"away_team","away_name"); home=base.base._txt(row,"home_team","home_name")
    away_id=base.base._txt(row,"away_team_id",default=""); home_id=base.base._txt(row,"home_team_id",default="")
    time=base.base._txt(row,"first_pitch_et","game_time_et","start_time_et","game_time")
    venue=base.base._txt(row,"venue_name","venue"); status=base.base._txt(row,"status","game_status",default="Scheduled")
    away_sp=base.base._txt(row,"away_pitcher","away_probable_pitcher","away_starter",default="TBD")
    home_sp=base.base._txt(row,"home_pitcher","home_probable_pitcher","home_starter",default="TBD")
    confirmed=base.base._confirmed_flag(row); lineup_text="✅ LINEUPS CONFIRMED" if confirmed else "🕒 LINEUPS PENDING"
    gamepk=base.base._txt(row,"game_pk","gamePk",default="—")
    inv=base._candidate_pool(row); ready=sum(1 for m in base.MARKETS if inv["pools"][m]["ready"])

    st.markdown(f'''
<div class="dgp-game">
 <div class="dgp-top"><div class="dgp-num">GAME {idx} • MLB GAME ID {base._esc(gamepk)}</div><div class="dgp-state">{base._esc(lineup_text)}</div></div>
 <div class="dgp-match"><div class="dgp-team"><img src="{base._esc(base.base._logo(away_id))}">{base._esc(away)}</div><div class="dgp-at">@</div><div class="dgp-team"><img src="{base._esc(base.base._logo(home_id))}">{base._esc(home)}</div></div>
 <div class="dgp-meta">{base._esc(time)} ET • {base._esc(venue)} • {base._esc(status)}</div>
 <div class="dgp-starters"><div class="dgp-start"><span>Away probable starter</span><b>{base._esc(away_sp)}</b></div><div class="dgp-start"><span>Home probable starter</span><b>{base._esc(home_sp)}</b></div></div>
 <div class="dgp-health-title">Step 2 • Market availability</div>{base._health_html(inv)}
 <div class="dgp-pool-note">{ready}/7 market families eligible for MLB Game ID {base._esc(gamepk)}.</div>
 <div class="dgp-norm-title">Step 3 • Cross-market normalization</div>{_norm_html()}
 <div class="dgp-formula"><strong>Pick Strength 0–100:</strong> 34% market-aware probability strength + 26% edge above that market's anchor + 18% model reliability + 12% data quality + 6% lineup/start confirmation + 4% uncertainty control. Stale inputs receive an additional penalty. Candidates remain <strong>UNSCORED</strong> until their real production-engine probability is connected.</div>
 <div class="dgp-slots">
  <div class="dgp-slot"><div class="dgp-slotnum">🥇 PICK 1</div><div class="dgp-empty">Waiting for Step 4</div><div class="dgp-wait">Normalization contract is defined; game-level ranking remains disabled.</div></div>
  <div class="dgp-slot"><div class="dgp-slotnum">🥈 PICK 2</div><div class="dgp-empty">Waiting for Step 4</div><div class="dgp-wait">No raw percentages are compared across market families.</div></div>
  <div class="dgp-slot"><div class="dgp-slotnum">🥉 PICK 3</div><div class="dgp-empty">Waiting for Step 4</div><div class="dgp-wait">No candidate is promoted without verified model inputs.</div></div>
 </div>
</div>''',unsafe_allow_html=True)

    with st.expander(f"🧠 Step 3 normalization audit • Game {idx} • MLB ID {gamepk}",expanded=False):
        st.markdown("**Normalization weights**")
        st.json({k:f"{v*100:.0f}%" for k,v in WEIGHTS.items()},expanded=False)
        st.markdown("**Market-specific anchors and reliability gates**")
        st.dataframe([{"Market":m,"Anchor":f"{r['baseline']*100:.1f}%","Default uncertainty":f"±{r['uncertainty']*100:.1f} pts","Min reliability":f"{r['min_rel']*100:.0f}%","Family":r['family']} for m,r in MARKET_RULES.items()],use_container_width=True,hide_index=True)
        st.caption("Anchors exist only to normalize unlike markets. They do not replace a production probability, sportsbook implied probability, or fair price.")


def render_daily_game_picks(games_df,section_header=None,status_info=None,team_logo=None,h=None):
    base.base._css(); base._step2_css(); _css()
    if games_df is None or games_df.empty:
        st.info("No verified MLB games are available for the selected date."); return
    frame=base.base._sort_games(games_df); day=base.base._txt(frame.iloc[0],"game_date",default="")[:10]
    try: verified=int((frame["game_pk"].astype(str).str.len()>0).sum()) if "game_pk" in frame.columns else len(frame)
    except Exception: verified=len(frame)
    st.markdown('''<div class="dgp-hero"><div class="dgp-kicker">KYRE SPORTS AI • DAILY GAME PICKS • STEP 3</div><div class="dgp-title">🏆 Top 3 Picks — Every MLB Game</div><div class="dgp-sub">Step 3 defines the cross-market scoring contract before any candidate is ranked. Unlike market probabilities are normalized with market-aware anchors, reliability/data-quality gates, confirmation state and uncertainty controls. Missing production inputs are never fabricated.</div></div>''',unsafe_allow_html=True)
    st.success(f"✅ Step 3 normalization layer ready • {day or 'selected date'} • {verified}/{len(frame)} verified games • 7 market scoring profiles • 0 Top-3 picks ranked")
    for i,(_,row) in enumerate(frame.iterrows(),1): _render_game(row,i)
    st.markdown(f'<div class="dgp-foot">{VERSION} • 0–100 normalization contract active • no synthetic probabilities • no game-level Top 3 ranking until Step 4 • doubleheaders isolated by MLB game ID</div>',unsafe_allow_html=True)
