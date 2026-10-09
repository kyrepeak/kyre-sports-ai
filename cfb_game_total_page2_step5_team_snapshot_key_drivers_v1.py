"""CFB Game Total Page 2 Step 5 — Team Snapshot + Key Drivers.

Presentation-only comparison for already-owned team driver values. The caller
supplies display-ready pace, explosive, red-zone, defense, and favorable-side
context. This module does not fetch data or calculate sports/model meaning.
"""
from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

STEP2_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP2_MATCHUP_HERO_PHX_FROZEN"
STEP3_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP3_INTEGRATED_FLOW_FROZEN"
STEP4_FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP4_OUTLOOK_SUMMARY_FROZEN"
STEP5_MARKER = "CFB_GAME_TOTAL_PAGE2_V1_STEP5_TEAM_SNAPSHOT_KEY_DRIVERS_ACTIVE"
FREEZE_TOKEN = "CFB_GAME_TOTAL_PAGE2_V1_STEP5_TEAM_SNAPSHOT_KEY_DRIVERS_FROZEN"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_MARKET_OWNERSHIP = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0

PAGE2_STEP5_CSS = r"""
<style>
.gtp2s5-wrap{max-width:1180px;margin:0 auto 20px;color:#f7fbff;scroll-margin-top:18px}
.gtp2s5-card{overflow:hidden;border:1px solid rgba(75,197,255,.32);border-radius:20px;background:radial-gradient(circle at 50% 0,rgba(36,184,243,.10),transparent 35%),linear-gradient(180deg,rgba(7,27,41,.98),rgba(4,15,24,.99));box-shadow:0 16px 38px rgba(0,0,0,.25),0 0 28px rgba(46,190,255,.05)}
.gtp2s5-head{display:flex;align-items:end;justify-content:space-between;gap:16px;padding:17px 18px 13px;border-bottom:1px solid rgba(82,174,211,.17)}
.gtp2s5-kicker{display:block;margin-bottom:5px;color:#66d9ff;font-size:8px;font-weight:1000;letter-spacing:.13em;text-transform:uppercase}
.gtp2s5-head h3{margin:0;color:#fff;font-size:20px;line-height:1.05;font-weight:1000;letter-spacing:-.02em}
.gtp2s5-head p{margin:5px 0 0;color:#8ea9bb;font-size:9px;font-weight:750}
.gtp2s5-owned{padding:5px 9px;border:1px solid rgba(86,202,246,.24);border-radius:999px;background:rgba(11,67,94,.26);color:#83dfff;font-size:7px;font-weight:950;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
.gtp2s5-body{padding:14px}
.gtp2s5-teams{display:grid;grid-template-columns:minmax(0,1fr) 110px minmax(0,1fr);gap:10px;align-items:center;margin-bottom:10px}
.gtp2s5-team{padding:13px 14px;border:1px solid rgba(86,169,203,.22);border-radius:14px;background:rgba(10,35,51,.76)}
.gtp2s5-team span{display:block;color:#7597ab;font-size:7px;font-weight:950;letter-spacing:.10em;text-transform:uppercase}
.gtp2s5-team strong{display:block;margin-top:5px;color:#fff;font-size:17px;font-weight:1000;overflow-wrap:anywhere}
.gtp2s5-vs{text-align:center;color:#5dcfff;font-size:9px;font-weight:1000;letter-spacing:.12em;text-transform:uppercase}
.gtp2s5-drivers{display:grid;gap:8px}
.gtp2s5-driver{display:grid;grid-template-columns:minmax(0,1fr) 150px minmax(0,1fr);gap:10px;align-items:stretch}
.gtp2s5-value{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0;padding:12px 13px;border:1px solid rgba(84,154,185,.18);border-radius:13px;background:rgba(7,28,42,.72)}
.gtp2s5-value strong{color:#f5fbff;font-size:13px;font-weight:1000;overflow-wrap:anywhere}
.gtp2s5-value.is-favorable{border-color:rgba(72,224,177,.43);background:linear-gradient(145deg,rgba(9,75,61,.34),rgba(7,31,44,.80))}
.gtp2s5-value.is-favorable strong{color:#7aefbf}
.gtp2s5-driver-label{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:8px;border:1px solid rgba(84,173,209,.16);border-radius:12px;background:rgba(9,36,53,.58)}
.gtp2s5-driver-label strong{color:#dff6ff;font-size:9px;font-weight:1000;letter-spacing:.03em}
.gtp2s5-fav{display:block;margin-top:4px;color:#69dfff;font-size:7px;font-weight:950;line-height:1.2}
.gtp2s5-fav.even{color:#9eb2bf}
@media(max-width:760px){.gtp2s5-head{align-items:start;flex-direction:column;gap:9px}.gtp2s5-owned{align-self:flex-start}.gtp2s5-teams{grid-template-columns:1fr 58px 1fr}.gtp2s5-driver{grid-template-columns:minmax(0,1fr) 116px minmax(0,1fr)}.gtp2s5-team strong{font-size:15px}.gtp2s5-value{padding:10px}.gtp2s5-value strong{font-size:11px}}
@media(max-width:480px){.gtp2s5-card{border-radius:17px}.gtp2s5-head{padding:14px 13px 11px}.gtp2s5-head h3{font-size:18px}.gtp2s5-body{padding:10px}.gtp2s5-teams{grid-template-columns:1fr 34px 1fr;gap:6px}.gtp2s5-team{padding:10px 8px}.gtp2s5-team strong{font-size:13px}.gtp2s5-driver{grid-template-columns:minmax(0,1fr) 92px minmax(0,1fr);gap:6px}.gtp2s5-value{padding:9px 7px}.gtp2s5-value strong{font-size:10px}.gtp2s5-driver-label{padding:7px 4px}.gtp2s5-driver-label strong{font-size:8px}.gtp2s5-fav{font-size:6px}}
</style>
"""


def _display(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return escape(text) if text else "—"


def _fav_side(value: Any) -> str:
    side = str(value or "").strip().lower()
    return side if side in {"away", "home", "even"} else "none"


def _badge(side: str, away_name: str, home_name: str) -> str:
    if side == "away":
        return f'<span class="gtp2s5-fav">Favorable: {away_name}</span>'
    if side == "home":
        return f'<span class="gtp2s5-fav">Favorable: {home_name}</span>'
    if side == "even":
        return '<span class="gtp2s5-fav even">Favorable: Even</span>'
    return '<span class="gtp2s5-fav">Favorable: —</span>'


def _driver_html(
    *,
    key: str,
    label: str,
    away_value: Any,
    home_value: Any,
    favorable: Any,
    away_name: str,
    home_name: str,
) -> str:
    side = _fav_side(favorable)
    away_class = " gtp2s5-value is-favorable" if side == "away" else " gtp2s5-value"
    home_class = " gtp2s5-value is-favorable" if side == "home" else " gtp2s5-value"
    return (
        f'<div class="gtp2s5-driver" data-driver="{key}" data-favorable="{side}">'
        f'<div class="{away_class.strip()}"><strong>{_display(away_value)}</strong></div>'
        f'<div class="gtp2s5-driver-label"><strong>{escape(label)}</strong>{_badge(side, away_name, home_name)}</div>'
        f'<div class="{home_class.strip()}"><strong>{_display(home_value)}</strong></div>'
        '</div>'
    )


def build_team_snapshot_key_drivers_html(
    *,
    away_team: Any,
    home_team: Any,
    away_pace: Any,
    home_pace: Any,
    away_explosive: Any,
    home_explosive: Any,
    away_red_zone: Any,
    home_red_zone: Any,
    away_defense: Any,
    home_defense: Any,
    favorable_for: Mapping[str, Any] | None,
) -> str:
    """Render Step 5 from display-ready owned values without recomputation."""
    away_name = _display(away_team)
    home_name = _display(home_team)
    fav = favorable_for if isinstance(favorable_for, Mapping) else {}
    rows = (
        _driver_html(key="pace", label="Pace", away_value=away_pace, home_value=home_pace, favorable=fav.get("pace"), away_name=away_name, home_name=home_name),
        _driver_html(key="explosive", label="Explosive Plays", away_value=away_explosive, home_value=home_explosive, favorable=fav.get("explosive"), away_name=away_name, home_name=home_name),
        _driver_html(key="red_zone", label="Red-Zone Rate", away_value=away_red_zone, home_value=home_red_zone, favorable=fav.get("red_zone"), away_name=away_name, home_name=home_name),
        _driver_html(key="defense", label="Defense", away_value=away_defense, home_value=home_defense, favorable=fav.get("defense"), away_name=away_name, home_name=home_name),
    )
    return f"""
{PAGE2_STEP5_CSS}
<section id="gtp2-team-snapshot" class="gtp2s5-wrap" data-step5="{STEP5_MARKER}" data-testid="gtp2s5-team-snapshot" data-value-ownership="precomputed-inputs">
  <div class="gtp2s5-card">
    <header class="gtp2s5-head">
      <div>
        <span class="gtp2s5-kicker">Stage 2 • Team Snapshot</span>
        <h3>Team Snapshot + Key Drivers</h3>
        <p>Side-by-side team context from already-owned game-total evidence.</p>
      </div>
      <span class="gtp2s5-owned">Display only • explicit favorable side</span>
    </header>
    <div class="gtp2s5-body">
      <div class="gtp2s5-teams">
        <div class="gtp2s5-team"><span>Away</span><strong>{away_name}</strong></div>
        <div class="gtp2s5-vs">vs</div>
        <div class="gtp2s5-team"><span>Home</span><strong>{home_name}</strong></div>
      </div>
      <div class="gtp2s5-drivers">{''.join(rows)}</div>
    </div>
  </div>
</section>
"""


__all__ = [
    "FREEZE_TOKEN",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "NETWORK_CALLS_ADDED",
    "PAGE2_STEP5_CSS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP2_FREEZE_TOKEN",
    "STEP3_FREEZE_TOKEN",
    "STEP4_FREEZE_TOKEN",
    "STEP5_MARKER",
    "build_team_snapshot_key_drivers_html",
]
