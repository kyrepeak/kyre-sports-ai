"""CFB Game Total Page 2 Step 3 — integrated Game Total flow.

Presentation-only navigation for the already-approved Page-2 analysis stages.
It adds no data fetching, projection/model logic, probability logic, market
ownership, or Page-1 behavior.
"""
from __future__ import annotations

STEP2_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP2_MATCHUP_HERO_PHX_FROZEN"
STEP3_MARKER = "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_ACTIVE"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_FROZEN"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_MARKET_OWNERSHIP = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0

FLOW_STEPS = (
    (1, "Outlook", "gtp2-outlook"),
    (2, "Team Snapshot", "gtp2-team-snapshot"),
    (3, "Trends", "gtp2-trends"),
    (4, "Line Lab", "gtp2-line-lab"),
    (5, "Best Bet", "gtp2-best-bet"),
)

PAGE2_STEP3_CSS = r"""
<style>
.gtp2s3-wrap{max-width:1180px;margin:0 auto 18px;color:#f7fbff}
.gtp2s3-title{display:flex;align-items:end;justify-content:space-between;gap:14px;margin:0 2px 10px}
.gtp2s3-title strong{color:#fff;font-size:15px;font-weight:950;letter-spacing:.02em}
.gtp2s3-title span{color:#83a8bd;font-size:9px;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
.gtp2s3-flow{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;padding:9px;border:1px solid rgba(72,197,255,.32);border-radius:18px;background:linear-gradient(180deg,rgba(8,28,42,.96),rgba(4,15,25,.98));box-shadow:0 14px 34px rgba(0,0,0,.24),0 0 28px rgba(41,185,255,.05)}
.gtp2s3-step{min-width:0;display:flex;align-items:center;gap:9px;padding:10px 11px;border:1px solid rgba(87,157,190,.20);border-radius:13px;background:rgba(11,34,50,.70);color:#a9bfd0;text-decoration:none;transition:border-color .16s ease,background .16s ease,transform .16s ease}
.gtp2s3-step:hover{border-color:rgba(84,207,255,.58);background:rgba(19,65,91,.70);transform:translateY(-1px)}
.gtp2s3-step.is-active{border-color:rgba(76,218,255,.90);background:linear-gradient(135deg,rgba(10,144,211,.40),rgba(16,71,122,.54));box-shadow:inset 0 0 0 1px rgba(90,226,255,.14),0 0 22px rgba(41,190,255,.13);color:#fff}
.gtp2s3-num{width:27px;height:27px;flex:0 0 27px;display:grid;place-items:center;border:1px solid rgba(82,204,246,.34);border-radius:9px;background:rgba(20,91,126,.23);color:#61d8ff;font-size:10px;font-weight:1000}
.gtp2s3-step.is-active .gtp2s3-num{border-color:#6de5ff;background:rgba(26,181,235,.22);color:#eaffff}
.gtp2s3-label{min-width:0;display:block;color:inherit;font-size:10px;font-weight:950;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:760px){.gtp2s3-title{align-items:start;flex-direction:column;gap:4px}.gtp2s3-flow{display:flex;overflow-x:auto;scroll-snap-type:x proximity;padding:8px}.gtp2s3-step{min-width:150px;scroll-snap-align:start}.gtp2s3-flow::-webkit-scrollbar{height:4px}.gtp2s3-flow::-webkit-scrollbar-thumb{background:rgba(82,205,247,.32);border-radius:999px}}
@media(max-width:480px){.gtp2s3-step{min-width:132px;padding:9px}.gtp2s3-label{font-size:9px}.gtp2s3-num{width:25px;height:25px;flex-basis:25px}}
</style>
"""


def build_integrated_game_total_flow_html(active_step: int = 1) -> str:
    """Build the five-stage Page-2 jump tracker with one active stage."""
    if isinstance(active_step, bool) or not isinstance(active_step, int) or not 1 <= active_step <= len(FLOW_STEPS):
        raise ValueError("active_step must be an integer from 1 through 5")

    controls: list[str] = []
    for number, label, anchor in FLOW_STEPS:
        current = ' aria-current="step"' if number == active_step else ""
        controls.append(
            f'<a class="gtp2s3-step{(" is-active" if number == active_step else "")}" '
            f'href="#{anchor}"{current}>'
            f'<span class="gtp2s3-num">{number}</span>'
            f'<span class="gtp2s3-label">{label}</span>'
            "</a>"
        )

    return f"""
{PAGE2_STEP3_CSS}
<div class="gtp2s3-wrap" data-step3="{STEP3_MARKER}">
  <div class="gtp2s3-title">
    <strong>Game Total Flow</strong>
    <span>Tap a stage to jump through the analysis</span>
  </div>
  <nav class="gtp2s3-flow" data-testid="gtp2s3-flow" data-active-step="{active_step}" aria-label="Game Total analysis stages">
    {''.join(controls)}
  </nav>
</div>
"""


__all__ = [
    "FLOW_STEPS",
    "FREEZE_TOKEN",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "NETWORK_CALLS_ADDED",
    "PAGE2_STEP3_CSS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP2_FREEZE_TOKEN",
    "STEP3_MARKER",
    "build_integrated_game_total_flow_html",
]
