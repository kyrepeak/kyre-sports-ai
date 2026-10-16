"""CFB Game Total Page 2 — Stage 6 Tough Matchup + Favorable Team.

Presentation-only summary of already-owned matchup evidence. No provider fetch,
model/projection/probability recompute, ranking mutation, or sportsbook influence.
"""
from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

STAGE6_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_STAGE6_TOUGH_FAVORABLE_V1_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_STAGE6_TOUGH_FAVORABLE_V1_FROZEN"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_OWNERSHIP = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

PAGE2_STAGE6_CSS = r"""
<style>
.gtp2s10-wrap{max-width:1180px;margin:0 auto 20px;color:#f7fbff}.gtp2s10-card{overflow:hidden;border:1px solid rgba(91,192,255,.30);border-radius:20px;background:linear-gradient(180deg,rgba(7,28,43,.98),rgba(4,15,24,.99));box-shadow:0 16px 38px rgba(0,0,0,.25)}
.gtp2s10-head{display:flex;align-items:end;justify-content:space-between;gap:16px;padding:17px 18px 13px;border-bottom:1px solid rgba(82,174,211,.17)}.gtp2s10-kicker{display:block;margin-bottom:5px;color:#76dfff;font-size:8px;font-weight:1000;letter-spacing:.13em;text-transform:uppercase}.gtp2s10-head h3{margin:0;color:#fff;font-size:20px;font-weight:1000}.gtp2s10-head p{margin:5px 0 0;color:#8ea9bb;font-size:9px;font-weight:750}.gtp2s10-owned{padding:5px 9px;border:1px solid rgba(86,202,246,.24);border-radius:999px;background:rgba(11,67,94,.26);color:#83dfff;font-size:7px;font-weight:950;text-transform:uppercase;white-space:nowrap}
.gtp2s10-body{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:14px}.gtp2s10-panel{padding:14px;border:1px solid rgba(91,170,203,.20);border-radius:14px;background:rgba(7,29,44,.74)}.gtp2s10-panel span{display:block;color:#7899ac;font-size:7px;font-weight:950;letter-spacing:.09em;text-transform:uppercase}.gtp2s10-panel strong{display:block;margin-top:6px;color:#fff;font-size:18px;font-weight:1000}.gtp2s10-panel p{margin:7px 0 0;color:#9db5c3;font-size:8px;font-weight:750;line-height:1.45}.gtp2s10-panel.tough{border-color:rgba(255,105,120,.32);background:rgba(89,29,39,.22)}.gtp2s10-panel.tough strong{color:#ff8995}.gtp2s10-panel.fav{border-color:rgba(72,224,177,.36);background:rgba(9,75,61,.25)}.gtp2s10-panel.fav strong{color:#7aefbf}.gtp2s10-limited{grid-column:1/-1;padding:10px 12px;border-radius:11px;background:rgba(82,94,106,.13);color:#9fb1bc;font-size:8px;font-weight:800}
@media(max-width:640px){.gtp2s10-head{align-items:start;flex-direction:column}.gtp2s10-body{grid-template-columns:1fr}.gtp2s10-limited{grid-column:auto}}
</style>
"""


def _text(value: Any, fallback: str = "—") -> str:
    text = str(value or "").strip()
    return escape(text) if text else fallback


def _battle_read(battle: Mapping[str, Any] | None) -> tuple[str, str, str]:
    row = battle if isinstance(battle, Mapping) else {}
    team = str(row.get("offense_team") or "").strip()
    title = str(row.get("read_title") or "").strip()
    note = str(row.get("read_note") or "").strip()
    tone = str(row.get("read_tone") or "").strip().lower()
    return team, title, note if note else tone


def build_tough_favorable_contract(matchup: Mapping[str, Any] | None) -> dict[str, Any]:
    """Choose only explicit verified matchup reads; never infer from missing evidence."""
    contract = matchup if isinstance(matchup, Mapping) else {}
    battles = [
        contract.get("away_offense_vs_home_defense"),
        contract.get("home_offense_vs_away_defense"),
    ]
    rows = []
    for battle in battles:
        if not isinstance(battle, Mapping):
            continue
        team = str(battle.get("offense_team") or "").strip()
        title = str(battle.get("read_title") or "").strip()
        note = str(battle.get("read_note") or "").strip()
        tone = str(battle.get("read_tone") or "").strip().lower()
        verified = int(battle.get("verified_tiles") or 0)
        if team and title and verified >= 3 and tone in {"fav", "tough", "mixed"}:
            rows.append({"team": team, "title": title, "note": note, "tone": tone, "verified": verified})

    tough = next((row for row in rows if row["tone"] == "tough"), None)
    favorable = next((row for row in rows if row["tone"] == "fav"), None)
    return {
        "ready": bool(tough or favorable),
        "tough_team": tough["team"] if tough else None,
        "tough_read": tough["title"] if tough else None,
        "tough_reason": tough["note"] if tough else "No verified tough matchup is established.",
        "favorable_team": favorable["team"] if favorable else None,
        "favorable_read": favorable["title"] if favorable else None,
        "favorable_reason": favorable["note"] if favorable else "No verified favorable team is established.",
        "verified_battles": len(rows),
        "sportsbook_projection_influence": 0.0,
    }


def build_tough_favorable_html(matchup: Mapping[str, Any] | None) -> str:
    row = build_tough_favorable_contract(matchup)
    limited = "" if row["ready"] else '<div class="gtp2s10-limited">Verified matchup evidence is limited; no side is invented.</div>'
    return f"""
{PAGE2_STAGE6_CSS}
<section id="gtp2-tough-favorable" class="gtp2s10-wrap" data-stage6="{STAGE6_MARKER}" data-testid="gtp2s10-tough-favorable" data-value-ownership="verified-matchup-read">
  <div class="gtp2s10-card">
    <header class="gtp2s10-head"><div><span class="gtp2s10-kicker">Stage 6 • Matchup Read</span><h3>Tough Matchup + Favorable Team</h3><p>Verified offense-vs-defense reads summarized without changing the model.</p></div><span class="gtp2s10-owned">Display only • fail soft</span></header>
    <div class="gtp2s10-body">
      <article class="gtp2s10-panel tough" data-testid="gtp2s10-tough"><span>Tough Matchup</span><strong>{_text(row['tough_team'])}</strong><p>{_text(row['tough_read'], 'No verified tough matchup')} • {_text(row['tough_reason'])}</p></article>
      <article class="gtp2s10-panel fav" data-testid="gtp2s10-favorable"><span>Favorable Team</span><strong>{_text(row['favorable_team'])}</strong><p>{_text(row['favorable_read'], 'No verified favorable matchup')} • {_text(row['favorable_reason'])}</p></article>
      {limited}
    </div>
  </div>
</section>
"""


__all__ = ["FREEZE_TOKEN", "NETWORK_CALLS_ADDED", "SPORTSBOOK_PROJECTION_INFLUENCE", "STAGE6_MARKER", "build_tough_favorable_contract", "build_tough_favorable_html"]
