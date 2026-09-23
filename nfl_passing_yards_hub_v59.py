"""NFL Passing Yards V59 — dedicated quarterback analysis view.

Additive over frozen V58. The Step 1 two-quarterback picker is inherited
unchanged. When a quarterback slot is present in the query, V59 composes exactly
one dedicated analysis view from the already-captured certified payload.

No model, projection, probability, market math, data provider, sportsbook
influence, widget-key, or frozen Step 1 behavior is changed.
"""
from __future__ import annotations

from html import escape

import nfl_passing_yards_hub_v58 as prior
from kyre_universal_components_v1 import build_badge, build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

MODEL_VERSION = "NFL PASSING YARDS V59 • QB DRILL-DOWN STEP 2"
FROZEN_PRIOR = "nfl_passing_yards_hub_v58"
DRILLDOWN_STEP = 2
DETAIL_SYSTEM_VERSION = "v59"
DETAIL_CLEANUP_VERSION = "step1-2-v1"
DETAIL_CLEANUP_STEPS = 2
DETAIL_CLEANUP_STEP34_VERSION = "step3-4-v1"
DETAIL_CLEANUP_STEP56_VERSION = "step5-6-v1"
DETAIL_CLEANUP_COMPLETED_STEPS = 6
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
MAY_MODIFY_DATA = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_QB_SLOT_PARAM = "ks_qb_slot"

_DETAIL_CSS = r"""
<style data-passing-yards-qb-detail="v59">
.ks-py59,.ks-py59 *{box-sizing:border-box}
.ks-py59{
  width:100%;max-width:1120px;margin:.35rem auto 1rem;
  color:var(--kyre-sem-text-primary)
}
.ks-py59-toolbar{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  flex-wrap:wrap;margin-bottom:10px
}
.ks-py59-back{
  display:inline-flex;align-items:center;justify-content:center;min-height:42px;
  padding:8px 12px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:999px;background:rgba(255,255,255,.018);
  color:var(--kyre-sem-text-accent-soft)!important;text-decoration:none!important;
  font-size:.76rem;font-weight:900;line-height:1
}
.ks-py59-head{
  display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:16px;
  margin-bottom:12px;padding:18px 20px;
  border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-card);
  background:
    radial-gradient(circle at top right,var(--kyre-sem-accent-wash-soft),transparent 34%),
    linear-gradient(145deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
  box-shadow:var(--kyre-sem-shadow-card),var(--kyre-sem-shadow-glow)
}
.ks-py59-headcopy{min-width:0;max-width:720px}
.ks-py59-kicker{
  color:var(--kyre-sem-text-accent-soft);font-size:.66rem;font-weight:950;
  letter-spacing:.12em;text-transform:uppercase
}
.ks-py59-title{
  margin:.28rem 0 0;font-size:clamp(1.8rem,4vw,2.75rem);
  font-weight:950;line-height:1.02;letter-spacing:-.025em
}
.ks-py59-sub{
  max-width:660px;margin:.55rem 0 0;color:var(--kyre-sem-text-muted);
  font-size:.86rem;line-height:1.55
}
.ks-py59-player{
  min-width:0;padding:14px;border:1px solid var(--kyre-sem-border-medium);
  border-radius:var(--kyre-sem-radius-card);
  background:linear-gradient(155deg,var(--kyre-sem-surface-panel-alt),var(--kyre-sem-surface-panel));
  box-shadow:var(--kyre-sem-shadow-card)
}

/* Step 2 — compact selected-QB identity card. */
.ks-py59-identity{
  margin-bottom:12px;padding:14px;border:1px solid var(--kyre-sem-border-soft);
  border-radius:var(--kyre-sem-radius-section);
  background:linear-gradient(145deg,rgba(255,255,255,.022),rgba(255,255,255,.008))
}
.ks-py59-identity-head{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  margin-bottom:12px;padding-bottom:9px;border-bottom:1px solid var(--kyre-sem-border-soft)
}
.ks-py59-identity-head span:first-child{
  color:var(--kyre-sem-text-accent-soft);font-size:.64rem;font-weight:950;
  letter-spacing:.08em;text-transform:uppercase
}
.ks-py59-identity-head span:last-child{
  color:var(--kyre-sem-text-muted);font-size:.62rem;font-weight:800
}
.ks-py59-identity .kpass29-card{
  position:relative!important;overflow:visible!important;margin:0!important;padding:0!important;
  border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important
}
.ks-py59-identity .kpass29-card:after{display:none!important}
.ks-py59-identity .kpass29-top{
  position:relative!important;display:grid!important;
  grid-template-columns:88px minmax(0,1fr) 48px!important;
  align-items:center!important;gap:12px!important;min-width:0!important
}
.ks-py59-identity .kpass29-head{
  width:88px!important;height:88px!important;min-width:88px!important;max-width:88px!important;
  flex:0 0 88px!important;border:1px solid var(--kyre-sem-border-medium)!important;
  border-radius:18px!important;background:var(--kyre-sem-surface-panel)!important;
  overflow:hidden!important;display:flex!important;align-items:flex-end!important;justify-content:center!important
}
.ks-py59-identity .kpass29-head img{
  width:100%!important;height:100%!important;max-width:100%!important;max-height:100%!important;
  object-fit:cover!important;object-position:center top!important;display:block!important
}
.ks-py59-identity .kpass29-ident{min-width:0!important}
.ks-py59-identity .kpass29-name{
  color:var(--kyre-sem-text-primary)!important;font-size:1.22rem!important;font-weight:950!important;
  line-height:1.08!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important
}
.ks-py59-identity .kpass29-meta{
  margin-top:5px!important;color:var(--kyre-sem-text-muted)!important;
  font-size:.76rem!important;line-height:1.4!important;
  white-space:normal!important;overflow:visible!important;text-overflow:clip!important
}
.ks-py59-identity .kpass29-badges{
  display:flex!important;flex-wrap:wrap!important;gap:6px!important;margin-top:8px!important
}
.ks-py59-identity .kpass29-badge{
  padding:4px 7px!important;border-radius:999px!important;
  font-size:.56rem!important;line-height:1!important
}
.ks-py59-identity .kpass29-logo{
  width:48px!important;height:48px!important;min-width:48px!important;max-width:48px!important;
  padding:5px!important;border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:12px!important;background:var(--kyre-sem-surface-panel)!important;
  object-fit:contain!important
}
.ks-py59-identity .kpass29-main{
  position:relative!important;display:grid!important;
  grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:8px!important;
  margin-top:12px!important
}
.ks-py59-identity .kpass29-metric{
  min-width:0!important;padding:10px!important;border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:12px!important;background:rgba(255,255,255,.018)!important
}
.ks-py59-identity .kpass29-metric b{
  display:block!important;color:var(--kyre-sem-text-primary)!important;
  font-size:.88rem!important;line-height:1.15!important;
  white-space:normal!important;overflow:visible!important;text-overflow:clip!important
}
.ks-py59-identity .kpass29-metric span{
  display:block!important;margin-top:4px!important;color:var(--kyre-sem-text-muted)!important;
  font-size:.56rem!important;font-weight:900!important;line-height:1.25!important;
  text-transform:uppercase!important;white-space:normal!important;overflow:visible!important
}
.ks-py59-identity .kpass29-foot{
  position:relative!important;margin-top:10px!important;padding-top:9px!important;
  border-top:1px solid var(--kyre-sem-border-soft)!important;
  color:var(--kyre-sem-text-muted)!important;font-size:.68rem!important;line-height:1.5!important
}
.ks-py59-identity .kpass29-foot strong{color:var(--kyre-sem-text-accent-soft)!important}

/* Step 3 — Current Market + Edge: separate values from labels and compact the card. */
.ks-py59-section[data-qb-analysis-section="market"],
.ks-py59-section[data-qb-analysis-section="projection"]{
  padding:12px;background:linear-gradient(145deg,rgba(255,255,255,.018),rgba(255,255,255,.006))
}
.ks-py59-section[data-qb-analysis-section="market"]>strong,
.ks-py59-section[data-qb-analysis-section="projection"]>strong{
  margin:0 0 10px;padding:0 0 9px;border-bottom:1px solid var(--kyre-sem-border-soft);
  font-size:.66rem;letter-spacing:.09em
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-card{
  margin:0!important;padding:0!important;border:0!important;border-radius:0!important;
  background:transparent!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-top{
  display:flex!important;align-items:flex-start!important;justify-content:space-between!important;
  gap:10px!important;margin:0 0 10px!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy21-team-logo-slot{
  width:40px!important;height:40px!important;flex:0 0 40px!important;
  margin:0!important;border-radius:10px!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-name{
  font-size:1rem!important;line-height:1.18!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-sub{
  margin-top:4px!important;font-size:.67rem!important;line-height:1.45!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-grade{
  padding:5px 8px!important;font-size:.60rem!important;line-height:1!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-hero{
  display:grid!important;grid-template-columns:1.15fr repeat(2,minmax(0,1fr))!important;
  gap:8px!important;margin:0 0 8px!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-hero>div,
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-metrics>div{
  min-width:0!important;padding:10px!important;border-radius:11px!important;
  border:1px solid var(--kyre-sem-border-soft)!important;background:rgba(255,255,255,.018)!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-hero b{
  display:block!important;font-size:1rem!important;line-height:1.12!important;
  white-space:normal!important;overflow-wrap:anywhere!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-hero span{
  display:block!important;margin-top:4px!important;font-size:.57rem!important;
  line-height:1.25!important;letter-spacing:.03em!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-metrics{
  display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;
  gap:8px!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-metrics>div{
  display:flex!important;flex-direction:column!important;gap:5px!important;
  color:var(--kyre-sem-text-muted)!important;font-size:.64rem!important;line-height:1.3!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-metrics b{
  display:block!important;margin:0!important;color:var(--kyre-sem-text-primary)!important;
  font-size:.88rem!important;line-height:1.15!important;
  white-space:normal!important;overflow-wrap:anywhere!important
}
.ks-py59-section[data-qb-analysis-section="market"] .kpy10-note{
  margin-top:9px!important;padding-top:9px!important;
  color:var(--kyre-sem-text-muted)!important;font-size:.67rem!important;line-height:1.55!important
}

/* Step 4 — Baseline Projection: clean metric hierarchy without changing any values. */
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-proj{
  margin:0!important;padding:0!important;border:0!important;border-radius:0!important;
  background:transparent!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projtop{
  display:flex!important;align-items:flex-start!important;justify-content:space-between!important;
  gap:10px!important;margin:0 0 10px!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projname{
  font-size:1rem!important;line-height:1.18!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projsub{
  margin-top:4px!important;font-size:.67rem!important;line-height:1.45!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projgrade{
  padding:5px 8px!important;font-size:.60rem!important;line-height:1!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projhero{
  display:grid!important;grid-template-columns:1.25fr repeat(2,minmax(0,1fr))!important;
  gap:8px!important;margin:0 0 8px!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projhero>div,
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projmeta>div{
  min-width:0!important;padding:10px!important;border-radius:11px!important;
  border:1px solid var(--kyre-sem-border-soft)!important;background:rgba(255,255,255,.018)!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projhero b{
  display:block!important;font-size:1.04rem!important;line-height:1.12!important;
  white-space:normal!important;overflow-wrap:anywhere!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projhero span{
  display:block!important;margin-top:4px!important;font-size:.57rem!important;
  line-height:1.25!important;letter-spacing:.03em!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projmeta{
  display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projmeta>div{
  color:var(--kyre-sem-text-muted)!important;font-size:.64rem!important;line-height:1.35!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projmeta b{
  display:block!important;margin:0 0 5px!important;color:var(--kyre-sem-text-primary)!important;
  font-size:.88rem!important;line-height:1.15!important;
  white-space:normal!important;overflow-wrap:anywhere!important
}
.ks-py59-section[data-qb-analysis-section="projection"] .kpy-projctx{
  margin-top:9px!important;padding-top:9px!important;
  color:var(--kyre-sem-text-muted)!important;font-size:.67rem!important;line-height:1.55!important
}


/* Step 5 — Context + Uncertainty: compact readable evidence hierarchy. */
.ks-py59-section[data-qb-analysis-section="context"]{
  padding:12px;border-color:rgba(168,85,247,.30);
  background:linear-gradient(145deg,rgba(22,14,34,.94),rgba(8,19,31,.94))
}
.ks-py59-section[data-qb-analysis-section="context"]>strong{
  margin:0 0 10px;padding:0 0 9px;border-bottom:1px solid var(--kyre-sem-border-soft);
  font-size:.66rem;letter-spacing:.09em
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-card{
  margin:0!important;padding:0!important;border:0!important;border-radius:0!important;
  background:transparent!important;box-shadow:none!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-top{
  display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;
  align-items:start!important;gap:10px!important;margin:0 0 10px!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-name{
  color:var(--kyre-sem-text-primary)!important;font-size:1rem!important;
  font-weight:950!important;line-height:1.16!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-sub{
  margin-top:4px!important;color:var(--kyre-sem-text-muted)!important;
  font-size:.67rem!important;line-height:1.45!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-grade{
  padding:5px 8px!important;border-radius:999px!important;
  font-size:.58rem!important;font-weight:950!important;white-space:nowrap!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-hero{
  display:grid!important;grid-template-columns:1.25fr 1fr 1fr!important;
  gap:8px!important;margin:0 0 8px!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-hero>div,
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-meta>div{
  min-width:0!important;padding:10px!important;border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:11px!important;background:rgba(255,255,255,.018)!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-hero b{
  display:block!important;color:var(--kyre-sem-text-primary)!important;
  font-size:1rem!important;line-height:1.12!important;overflow-wrap:anywhere!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-hero span{
  display:block!important;margin-top:4px!important;color:var(--kyre-sem-text-muted)!important;
  font-size:.56rem!important;font-weight:900!important;line-height:1.25!important;
  text-transform:uppercase!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-meta{
  display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;
  gap:7px!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-meta>div{
  color:var(--kyre-sem-text-muted)!important;font-size:.64rem!important;line-height:1.35!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-meta b{
  display:block!important;margin:0 0 4px!important;color:var(--kyre-sem-text-primary)!important;
  font-size:.86rem!important;line-height:1.18!important;overflow-wrap:anywhere!important
}
.ks-py59-section[data-qb-analysis-section="context"] .kpy8-note{
  margin-top:9px!important;padding-top:9px!important;border-top:1px solid var(--kyre-sem-border-soft)!important;
  color:var(--kyre-sem-text-muted)!important;font-size:.66rem!important;line-height:1.5!important
}

/* Step 6 — Distribution + Probability: compact probability ladder. */
.ks-py59-section[data-qb-analysis-section="distribution"]{
  padding:12px;border-color:rgba(59,130,246,.30);
  background:linear-gradient(145deg,rgba(7,20,37,.96),rgba(8,19,31,.94))
}
.ks-py59-section[data-qb-analysis-section="distribution"]>strong{
  margin:0 0 10px;padding:0 0 9px;border-bottom:1px solid var(--kyre-sem-border-soft);
  font-size:.66rem;letter-spacing:.09em
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-card{
  margin:0!important;padding:0!important;border:0!important;border-radius:0!important;
  background:transparent!important;box-shadow:none!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-top{
  display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;
  align-items:start!important;gap:10px!important;margin:0 0 10px!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-name{
  color:var(--kyre-sem-text-primary)!important;font-size:1rem!important;
  font-weight:950!important;line-height:1.16!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-sub{
  margin-top:4px!important;color:var(--kyre-sem-text-muted)!important;
  font-size:.67rem!important;line-height:1.45!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-grade{
  padding:5px 8px!important;border-radius:999px!important;
  font-size:.58rem!important;font-weight:950!important;white-space:nowrap!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-hero{
  display:grid!important;grid-template-columns:1.25fr 1fr 1fr!important;
  gap:8px!important;margin:0 0 8px!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-hero>div{
  min-width:0!important;padding:10px!important;border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:11px!important;background:rgba(255,255,255,.018)!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-hero b{
  display:block!important;color:var(--kyre-sem-text-primary)!important;
  font-size:1rem!important;line-height:1.12!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-hero span{
  display:block!important;margin-top:4px!important;color:var(--kyre-sem-text-muted)!important;
  font-size:.56rem!important;font-weight:900!important;line-height:1.25!important;
  text-transform:uppercase!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-q{
  display:grid!important;grid-template-columns:repeat(5,minmax(0,1fr))!important;
  gap:6px!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-q>div{
  min-width:0!important;padding:8px 5px!important;border:1px solid var(--kyre-sem-border-soft)!important;
  border-radius:10px!important;background:rgba(255,255,255,.014)!important;text-align:center!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-q b{
  display:block!important;color:var(--kyre-sem-text-primary)!important;
  font-size:.75rem!important;line-height:1.12!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-q span{
  display:block!important;margin-top:4px!important;color:var(--kyre-sem-text-muted)!important;
  font-size:.52rem!important;font-weight:900!important;line-height:1.2!important
}
.ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-note{
  margin-top:9px!important;padding-top:9px!important;border-top:1px solid var(--kyre-sem-border-soft)!important;
  color:var(--kyre-sem-text-muted)!important;font-size:.66rem!important;line-height:1.5!important
}

.ks-py59-section{
  min-width:0;margin-top:var(--kyre-space-3);padding:var(--kyre-space-3);
  border:1px solid var(--kyre-sem-border-soft);border-radius:var(--kyre-sem-radius-section);
  background:rgba(255,255,255,.016);overflow-wrap:anywhere
}
.ks-py59-section>strong{
  display:block;margin-bottom:var(--kyre-space-2);color:var(--kyre-sem-text-accent-soft);
  font-size:.61rem;font-weight:950;letter-spacing:.07em;text-transform:uppercase
}
.ks-py59-evidence{
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--kyre-space-3);
  margin-top:var(--kyre-space-3)
}
.ks-py59-evidence .ks-py59-section{margin-top:0}
.ks-py59-support{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--kyre-space-3);
  margin-top:var(--kyre-space-3)
}
.ks-py59-support details{
  min-width:0;padding:var(--kyre-space-3);border:1px solid var(--kyre-sem-border-soft);
  border-radius:var(--kyre-sem-radius-section);background:rgba(255,255,255,.012)
}
.ks-py59-support summary{
  cursor:pointer;color:var(--kyre-sem-text-accent-soft);font-size:.64rem;font-weight:900
}
.ks-py59-supportbody{margin-top:var(--kyre-space-3);overflow-wrap:anywhere}
@media(max-width:900px){
  .ks-py59-evidence,.ks-py59-support{grid-template-columns:1fr}
}
@media(max-width:680px){
  .ks-py59{margin-top:.15rem}
  .ks-py59-toolbar{margin-bottom:8px}
  .ks-py59-back{min-height:40px;padding:8px 11px;font-size:.72rem}
  .ks-py59-head{
    grid-template-columns:1fr;align-items:start;gap:10px;
    padding:15px;margin-bottom:10px
  }
  .ks-py59-title{font-size:2rem}
  .ks-py59-sub{font-size:.80rem;line-height:1.5}
  .ks-py59-player{padding:10px}
  .ks-py59-identity{padding:11px;margin-bottom:10px}
  .ks-py59-identity-head{margin-bottom:10px}
  .ks-py59-identity .kpass29-top{
    grid-template-columns:70px minmax(0,1fr) 38px!important;gap:10px!important
  }
  .ks-py59-identity .kpass29-head{
    width:70px!important;height:70px!important;min-width:70px!important;max-width:70px!important;
    flex-basis:70px!important;border-radius:15px!important
  }
  .ks-py59-identity .kpass29-logo{
    width:38px!important;height:38px!important;min-width:38px!important;max-width:38px!important;
    border-radius:10px!important;padding:4px!important
  }
  .ks-py59-identity .kpass29-name{font-size:1.05rem!important}
  .ks-py59-identity .kpass29-meta{font-size:.69rem!important}
  .ks-py59-identity .kpass29-main{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .ks-py59-identity .kpass29-main>.kpass29-metric:nth-child(3){grid-column:1/-1!important}
  .ks-py59-identity .kpass29-metric{padding:9px!important}
  .ks-py59-identity .kpass29-metric b{font-size:.82rem!important}
  .ks-py59-identity .kpass29-foot{font-size:.64rem!important}
  .ks-py59-section[data-qb-analysis-section="market"],
  .ks-py59-section[data-qb-analysis-section="projection"]{padding:10px}
  .ks-py59-section[data-qb-analysis-section="market"] .kpy10-top,
  .ks-py59-section[data-qb-analysis-section="projection"] .kpy-projtop{
    flex-direction:column!important;gap:8px!important
  }
  .ks-py59-section[data-qb-analysis-section="market"] .kpy10-grade,
  .ks-py59-section[data-qb-analysis-section="projection"] .kpy-projgrade{
    align-self:flex-start!important
  }
  .ks-py59-section[data-qb-analysis-section="market"] .kpy10-hero,
  .ks-py59-section[data-qb-analysis-section="projection"] .kpy-projhero{
    grid-template-columns:repeat(2,minmax(0,1fr))!important
  }
  .ks-py59-section[data-qb-analysis-section="market"] .kpy10-hero>div:first-child,
  .ks-py59-section[data-qb-analysis-section="projection"] .kpy-projhero>div:first-child{
    grid-column:1/-1!important
  }
  .ks-py59-section[data-qb-analysis-section="market"] .kpy10-metrics{
    grid-template-columns:1fr!important
  }
  .ks-py59-section[data-qb-analysis-section="projection"] .kpy-projmeta{
    grid-template-columns:1fr!important
  }
  .ks-py59-section[data-qb-analysis-section="market"] .kpy10-metrics>div,
  .ks-py59-section[data-qb-analysis-section="projection"] .kpy-projmeta>div{
    min-height:0!important
  }
  /* Step 5-6 mobile cleanup */
  .ks-py59-section[data-qb-analysis-section="context"],
  .ks-py59-section[data-qb-analysis-section="distribution"]{padding:10px}
  .ks-py59-section[data-qb-analysis-section="context"] .kpy8-top,
  .ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-top{
    grid-template-columns:1fr!important
  }
  .ks-py59-section[data-qb-analysis-section="context"] .kpy8-grade,
  .ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-grade{
    justify-self:start!important
  }
  .ks-py59-section[data-qb-analysis-section="context"] .kpy8-hero,
  .ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-hero{
    grid-template-columns:repeat(2,minmax(0,1fr))!important
  }
  .ks-py59-section[data-qb-analysis-section="context"] .kpy8-hero>div:first-child,
  .ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-hero>div:first-child{
    grid-column:1/-1!important
  }
  .ks-py59-section[data-qb-analysis-section="context"] .kpy8-meta{
    grid-template-columns:1fr!important
  }
  .ks-py59-section[data-qb-analysis-section="distribution"] .kpy9-q{
    grid-template-columns:repeat(3,minmax(0,1fr))!important
  }
}
</style>
"""

def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""

def _section(kind: str, title: str, content: str) -> str:
    cleanup_marker = ""
    if kind == "market":
        cleanup_marker = ' data-qb-detail-cleanup-step3="green"'
    elif kind == "projection":
        cleanup_marker = ' data-qb-detail-cleanup-step4="green"'
    elif kind == "context":
        cleanup_marker = ' data-qb-detail-cleanup-step5="green"'
    elif kind == "distribution":
        cleanup_marker = ' data-qb-detail-cleanup-step6="green"'
    return (
        f'<section class="ks-py59-section" data-qb-analysis-section="{kind}"{cleanup_marker}>'
        f'<strong>{title}</strong>'
        + (content or "<div>Unavailable</div>")
        + "</section>"
    )

def _support(kind: str, title: str, content: str) -> str:
    return (
        f'<details data-qb-analysis-support="{kind}"><summary>{title}</summary>'
        '<div class="ks-py59-supportbody">'
        + (content or "<div>Unavailable</div>")
        + "</div></details>"
    )

def _selected_analysis(captured: dict[str, list[str]], slot: int) -> str:
    index = slot - 1
    back = escape(prior._current_nav_url(None), quote=True)

    identity = _piece(captured, "identity", index)
    market = _piece(captured, "market", index)
    projection = _piece(captured, "projection", index)
    context = _piece(captured, "context", index)
    distribution = _piece(captured, "distribution", index)
    profile = _piece(captured, "profile", index)
    defense = _piece(captured, "defense", index)
    pressure = _piece(captured, "pressure", index)
    personnel = _piece(captured, "personnel", index)
    environment = _piece(captured, "environment", index)

    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + prior._SELECTION_CSS
        + _DETAIL_CSS
        + f'<section class="ks-py59" data-passing-yards-qb-detail="v59" '
          f'data-passing-yards-selected-qb="{slot}" data-qb-analysis-slot="{slot}" '
          f'data-qb-detail-cleanup-version="{DETAIL_CLEANUP_VERSION}">'
        + '<div class="ks-py59-toolbar">'
        + f'<a class="ks-py59-back" data-qb-back="true" href="{back}">← Back to Quarterbacks</a>'
        + build_badge("DEDICATED QB VIEW", tone="success")
        + "</div>"
        + '<header class="ks-py59-head" data-qb-detail-cleanup-step1="green"><div class="ks-py59-headcopy">'
        + '<div class="ks-py59-kicker">SELECTED QUARTERBACK • PASSING YARDS</div>'
        + '<h2 class="ks-py59-title">Quarterback Analysis</h2>'
        + '<p class="ks-py59-sub">One player. One workspace. Certified analysis isolated to the selected quarterback.</p>'
        + "</div>"
        + build_badge("MODEL FROZEN", tone="success")
        + "</header>"
        + f'<article class="ks-py59-player" data-selected-qb-analysis="{slot}" data-qb-analysis-index="{index}">'
        + '<div class="ks-py59-identity" data-qb-detail-cleanup-step2="green">'
        + '<div class="ks-py59-identity-head"><span>Player Identity</span><span>Verified ESPN profile</span></div>'
        + (identity or "<div>Quarterback identity unavailable.</div>")
        + "</div>"
        + _section("market", "Current Market + Edge", market)
        + '<div class="ks-py59-evidence">'
        + _section("projection", "Baseline Projection", projection)
        + _section("context", "Context + Uncertainty", context)
        + _section("distribution", "Distribution + Probability", distribution)
        + "</div>"
        + '<div class="ks-py59-support">'
        + _support("matchup", "Matchup Drivers", (profile or "") + (defense or ""))
        + _support("conditions", "Conditions + Personnel", (pressure or "") + (personnel or "") + (environment or ""))
        + "</div></article></section>"
    )

def _qb_drilldown_step2_html(captured: dict[str, list[str]]) -> str:
    raw = prior._param(_QB_SLOT_PARAM)
    if raw in {"1", "2"}:
        return _selected_analysis(captured, int(raw))
    return prior._selection_screen(captured)

def render_nfl_passing_yards_hub() -> None:
    original = prior._qb_drilldown_html
    prior._qb_drilldown_html = _qb_drilldown_step2_html
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._qb_drilldown_html = original

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V59 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DETAIL_CLEANUP_COMPLETED_STEPS",
    "DETAIL_CLEANUP_STEP34_VERSION",
    "DETAIL_CLEANUP_STEPS",
    "DETAIL_CLEANUP_VERSION",
    "DETAIL_SYSTEM_VERSION",
    "DISPLAY_ONLY",
    "DRILLDOWN_STEP",
    "FROZEN_PRIOR",
    "MAY_MODIFY_DATA",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_qb_drilldown_step2_html",
    "_selected_analysis",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
