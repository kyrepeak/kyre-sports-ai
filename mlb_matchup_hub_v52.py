"""MLB Matchup Explorer V5.6 — cleanup Step 12 premium scouting card.

Presentation-only wrapper over certified Cleanup Step 11. It keeps the stable
Game -> Player selector, Phoenix local times and MLB logos, while replacing the
old scattered V2 Steps 1-12 research presentation with one continuous premium
scouting card. Existing builders still execute at the same certified render
points; this wrapper only captures their already-produced dictionaries and
reformats them. Probability, calibration, Monte Carlo, rankings and Moneyline
math remain unchanged.
"""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

import mlb_matchup_hub_v41 as current
import mlb_matchup_hub_v45 as hero_helpers
import mlb_matchup_hub_v46 as collapse_ui
import mlb_matchup_hub_v49 as caption_ui
import mlb_matchup_hub_v50 as legacy_ui
import mlb_matchup_hub_v51 as step11_ui
import mlb_matchup_player_v24 as p1
import mlb_matchup_player_v25 as p2
import mlb_matchup_player_v26 as p3
import mlb_matchup_player_v27 as p4
import mlb_matchup_player_v28 as p5
import mlb_matchup_player_v29 as p6
import mlb_matchup_player_v30 as p7
import mlb_matchup_player_v31 as p8
import mlb_matchup_player_v32 as p9
import mlb_matchup_player_v33 as p10
import mlb_matchup_player_v35 as final_layer

VERSION = "MLB Matchup Hub V5.6 • Cleanup Step 12 Scouting Card"
FROZEN_MATCHUP_CHAIN = step11_ui.FROZEN_MATCHUP_CHAIN
FROZEN_STEP11_PRESENTATION = "mlb_matchup_hub_v51"
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"

_SCOUT_CSS = r"""
<style>
.mx52-intro{display:flex;justify-content:space-between;align-items:flex-end;gap:12px;margin:4px 1px 9px}.mx52-intro-main{font-size:.92rem;font-weight:950;color:#f5f8fc}.mx52-intro-side{font-size:.49rem;line-height:1.4;text-align:right;color:#7f93aa;font-weight:900;letter-spacing:.11em;text-transform:uppercase}
.mx52-shell{position:relative;border:1px solid #a98628;border-left:7px solid #e0b52d;border-radius:25px;background:linear-gradient(150deg,#0b1727 0%,#08111e 55%,#07101b 100%);padding:18px 17px 20px;margin:0 0 12px;overflow:hidden;box-shadow:0 18px 38px rgba(0,0,0,.22)}
.mx52-shell:before{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle at 90% 0%,rgba(53,105,164,.13),transparent 29%)}
.mx52-verified{position:relative;color:#69d9ff;font-size:.52rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase;margin-bottom:14px}
.mx52-player{position:relative;display:grid;grid-template-columns:92px 1fr;gap:14px;align-items:center;margin-bottom:15px}.mx52-photo-shell{width:88px;height:88px;border-radius:50%;padding:3px;background:linear-gradient(145deg,#4c9bff,#234c79);box-shadow:0 0 0 4px rgba(54,125,201,.11)}.mx52-photo{width:100%;height:100%;object-fit:cover;object-position:center top;border-radius:50%;display:block;background:#132334}.mx52-name{font-size:1.48rem;line-height:1.04;font-weight:950;color:#fff;letter-spacing:-.025em}.mx52-teamrow{display:flex;align-items:center;gap:7px;margin-top:5px;color:#a9bacb;font-size:.65rem;font-weight:800}.mx52-teamlogo{width:34px;height:34px;object-fit:contain}.mx52-match{font-size:.58rem;color:#8ca2b8;line-height:1.45;margin-top:3px}.mx52-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}.mx52-chip{border:1px solid #36516b;border-radius:999px;padding:4px 8px;font-size:.47rem;font-weight:900;color:#b8cadb;background:#101b29}.mx52-chip.good{border-color:#2b6f4c;color:#8ce2aa;background:#0c2417}.mx52-chip.gold{border-color:#796522;color:#e8c95d;background:#241f0d}
.mx52-step{position:relative;border:1px solid color-mix(in srgb,var(--a) 55%,#26384b);border-radius:18px;background:linear-gradient(145deg,color-mix(in srgb,var(--a) 7%,#0a1420),#08111b 68%);padding:13px 14px;margin:11px 0}.mx52-step.s1{--a:#57b8ff}.mx52-step.s2{--a:#6fc8ff}.mx52-step.s3{--a:#e6b53a}.mx52-step.s4{--a:#53bde5}.mx52-step.s5{--a:#56c6ea}.mx52-step.s6{--a:#b88ae8}.mx52-step.s7{--a:#5dc878}.mx52-step.s8{--a:#d59a55}.mx52-step.s9{--a:#51c7c7}.mx52-step.s10{--a:#829ff0}.mx52-step.s11{--a:#ff8c68}.mx52-step.s12{--a:#e8c44d}
.mx52-stephead{display:flex;justify-content:space-between;align-items:flex-start;gap:9px}.mx52-steptitle{font-size:.53rem;font-weight:950;letter-spacing:.075em;text-transform:uppercase;color:var(--a);line-height:1.35}.mx52-pill{flex:0 0 auto;max-width:46%;border:1px solid color-mix(in srgb,var(--a) 60%,#26384b);border-radius:999px;padding:4px 8px;color:var(--a);font-size:.43rem;font-weight:900;text-transform:uppercase;text-align:center;white-space:normal;line-height:1.2}.mx52-lines{margin-top:10px}.mx52-line{font-size:.60rem;color:#c1ceda;line-height:1.5;margin:5px 0}.mx52-line b{color:#f0f5f9;font-weight:900}.mx52-subbox{border:1px solid #253d54;border-radius:11px;padding:7px 8px;margin:6px 0;background:#091622;color:#aebfd0;font-size:.55rem;line-height:1.42}.mx52-audit{border-top:1px solid color-mix(in srgb,var(--a) 28%,#25384a);padding-top:8px;margin-top:9px;font-size:.48rem;color:#6f8296;line-height:1.45}
.mx52-final{position:relative;border:1px solid #a98628;border-left:5px solid #e0b52d;border-radius:20px;background:linear-gradient(145deg,#12150e,#0a1115 70%);padding:14px;margin-top:14px}.mx52-finalhead{display:flex;justify-content:space-between;gap:8px;color:#e8c75e;font-size:.55rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.mx52-badges{display:flex;flex-wrap:wrap;gap:7px;margin:12px 0}.mx52-badge{border:1px solid #35536e;border-radius:999px;padding:7px 10px;font-size:.49rem;font-weight:950;color:#a8cce9;background:#0d1a26}.mx52-badge.green{border-color:#2f7452;color:#8ce1aa;background:#0b2418}.mx52-badge.gold{border-color:#80651f;color:#e7c35a;background:#211c0b}.mx52-evidence{border-radius:13px;padding:10px 11px;margin:8px 0;font-size:.58rem;font-weight:800;line-height:1.45}.mx52-evidence.ok{border:1px solid #2d6f4b;background:#0c2518;color:#9edbb2}.mx52-evidence.watch{border:1px solid #7b6120;background:#241d0b;color:#e5c96c}.mx52-neutral{font-size:.53rem;color:#8599ab;line-height:1.55;margin-top:7px}.mx52-big{font-size:3.25rem;line-height:.95;font-weight:980;letter-spacing:-.05em;color:#fff;margin:20px 0 4px}.mx52-bigsub{font-size:.60rem;font-weight:900;color:#8294a9;letter-spacing:.03em;text-transform:uppercase}.mx52-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:15px}.mx52-metric{border:1px solid #294159;border-radius:15px;padding:12px 11px;background:#091522}.mx52-metric span{display:block;font-size:.46rem;font-weight:900;color:#6f879d;text-transform:uppercase;letter-spacing:.05em}.mx52-metric b{display:block;margin-top:6px;color:#f2f7fb;font-size:1rem;font-weight:950}.mx52-confidence{display:inline-flex;margin-top:12px;border:1px solid #2e7450;background:#0d281a;color:#8ee1aa;border-radius:999px;padding:6px 10px;font-size:.52rem;font-weight:950;text-transform:uppercase}.mx52-foot{font-size:.46rem;color:#687d90;line-height:1.5;margin-top:10px}
@media(max-width:640px){.mx52-intro{margin-top:2px}.mx52-intro-main{font-size:.82rem}.mx52-intro-side{font-size:.43rem}.mx52-shell{padding:14px 12px 16px;border-radius:21px;border-left-width:6px}.mx52-player{grid-template-columns:78px 1fr;gap:10px}.mx52-photo-shell{width:75px;height:75px}.mx52-name{font-size:1.12rem}.mx52-teamrow{font-size:.56rem}.mx52-teamlogo{width:28px;height:28px}.mx52-match{font-size:.51rem}.mx52-chip{font-size:.42rem;padding:3px 6px}.mx52-step{padding:11px 10px;border-radius:15px;margin:8px 0}.mx52-steptitle{font-size:.47rem}.mx52-pill{font-size:.38rem;padding:3px 6px}.mx52-line{font-size:.54rem;margin:4px 0}.mx52-subbox{font-size:.50rem;padding:6px 7px}.mx52-audit{font-size:.43rem}.mx52-final{padding:12px 10px;border-radius:17px}.mx52-finalhead{font-size:.48rem}.mx52-badge{font-size:.43rem;padding:6px 8px}.mx52-evidence{font-size:.52rem;padding:8px 9px}.mx52-big{font-size:2.75rem}.mx52-bigsub{font-size:.52rem}.mx52-metric{padding:10px 9px}.mx52-metric span{font-size:.40rem}.mx52-metric b{font-size:.86rem}}
</style>
"""


def _esc(value: Any) -> str:
    return html.escape(str(value if value not in (None, "") else "—"))


def _num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _avg(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except Exception:
        return "—"


def _rate(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def _odds(value: Any) -> str:
    try:
        n = int(value)
        return f"+{n}" if n > 0 else str(n)
    except Exception:
        return "—"


def _score(value: Any) -> str:
    try:
        return f"{int(float(value))}/100"
    except Exception:
        return "—"


def _line(label: str, text: str) -> str:
    return f'<div class="mx52-line"><b>{_esc(label)}</b> • {text}</div>'


def _sub(text: str) -> str:
    return f'<div class="mx52-subbox">{text}</div>'


def _step(step: int, title: str, status: str, lines: list[str], audit: str) -> str:
    return (
        f'<div class="mx52-step s{step}"><div class="mx52-stephead">'
        f'<div class="mx52-steptitle">STEP {step} • {_esc(title)}</div>'
        f'<div class="mx52-pill">{_esc(status)}</div></div>'
        f'<div class="mx52-lines">{"".join(lines)}</div>'
        f'<div class="mx52-audit">{_esc(audit)}</div></div>'
    )


def _role_text(d: dict[str, Any]) -> str:
    slot = d.get("slot")
    slot_text = f"#{int(slot)}" if d.get("valid_slot") and slot else "No slot"
    return f"{_esc(d.get('lineup_source'))} • batting {slot_text} • {_esc(str(d.get('side') or '').upper())}"


def _header_html(context: dict[str, Any], d1: dict[str, Any]) -> str:
    row = context["row"]
    player = context["player"]
    player_id = int(player.get("id") or 0)
    side = str(player.get("side") or "").lower()
    team_id = row.get("away_team_id") if side == "away" else row.get("home_team_id")
    photo = hero_helpers._headshot_url(player_id) if player_id else ""
    logo = step11_ui._team_logo_url(team_id)
    photo_html = f'<img class="mx52-photo" src="{_esc(photo)}" alt="{_esc(player.get("name"))}">' if photo else '<div class="mx52-photo">⚾</div>'
    logo_html = f'<img class="mx52-teamlogo" src="{_esc(logo)}" alt="{_esc(player.get("team"))} logo">' if logo else "⚾"
    role = "Confirmed" if d1.get("confirmed") else ("Projected" if d1.get("projected") else "Bench / active")
    role_class = "good" if role == "Confirmed" else ""
    slot = d1.get("slot")
    slot_chip = f'<span class="mx52-chip gold">Batting #{int(slot)}</span>' if d1.get("valid_slot") and slot else ""
    return (
        '<div class="mx52-verified">⚾ Verified player • Matchup Intelligence V2</div>'
        '<div class="mx52-player">'
        f'<div class="mx52-photo-shell">{photo_html}</div><div>'
        f'<div class="mx52-name">{_esc(player.get("name") or d1.get("player_name"))}</div>'
        f'<div class="mx52-teamrow">{logo_html}<span>{_esc(player.get("team") or d1.get("team"))} • {_esc(player.get("position"))}</span></div>'
        f'<div class="mx52-match">vs {_esc(d1.get("opponent"))} • {_esc(d1.get("starter_name"))} ({_esc(d1.get("starter_hand"))}) • 🌵 {_esc(step11_ui._phoenix_time_text(row))}</div>'
        f'<div class="mx52-chips"><span class="mx52-chip {role_class}">{_esc(role)}</span>{slot_chip}<span class="mx52-chip">Data {_score(d1.get("score"))}</span></div>'
        '</div></div>'
    )


def _step_cards(data: dict[str, Any], context: dict[str, Any]) -> str:
    d1 = data.get("step1") or {}
    d2 = data.get("step2") or {}
    d3 = data.get("step3") or {}
    d4 = data.get("step4") or {}
    d5 = data.get("step5") or {}
    d6 = data.get("step6") or {}
    d7 = data.get("step7") or {}
    d8 = data.get("step8") or {}
    d9 = data.get("step9") or {}
    d10 = data.get("step10") or {}
    raw = data.get("step11") or {}
    final = data.get("step12") or {}

    cards: list[str] = []
    cards.append(_step(1, "Player + Opportunity Foundation", f"{d1.get('quality_label') or 'PENDING'} • {_score(d1.get('score'))}", [
        _line("Lineup", _role_text(d1)),
        _line("Game", f"{_esc(d1.get('venue'))} • 🌵 {_esc(step11_ui._phoenix_time_text(context['row']))} • {_esc(d1.get('game_status'))}"),
        _line("Starter context", f"{_esc(d1.get('starter_name'))} ({_esc(d1.get('starter_hand'))}) • batter {_esc(d1.get('batter_hand'))}"),
        _line("Season sample", f"{int(d1.get('season_games') or 0)} G • {int(d1.get('season_pa') or 0)} PA • {int(d1.get('season_hits') or 0)} H • AVG {_esc(d1.get('season_avg'))}"),
    ], f"Foundation readiness: {'READY' if d1.get('foundation_ready') else 'PARTIAL'} • identity, lineup, starter and season-sample verification only."))

    cards.append(_step(2, "Hitter True-Talent Profile", f"{d2.get('profile_quality_label') or 'PENDING'} • {_score(d2.get('profile_score'))}", [
        _line("True-talent blend", f"Season AVG {_avg(d2.get('season_avg'))} • xBA {_avg(d2.get('xba'))} • neutral skill {_avg(d2.get('neutral_hit_skill'))} • H/PA {_rate(d2.get('hit_per_pa'))}"),
        _line("Plate discipline", f"Contact {_rate(d2.get('contact_pct'))} • zone contact {_rate(d2.get('zone_contact_pct'))} • whiff {_rate(d2.get('whiff_pct'))} • K {_rate(d2.get('k_pct'))}"),
        _line("Contact quality", f"Hard-hit {_rate(d2.get('hard_hit_pct'))} • barrel {_rate(d2.get('barrel_pct'))} • BABIP {_avg(d2.get('babip'))}"),
        _line("Recent form input", f"AVG {_avg(d2.get('recent_avg'))} over {int(d2.get('recent_ab') or 0)} AB / {int(d2.get('recent_games') or 0)} games"),
    ], "Player-skill profile only; no opponent, park, bullpen or game-level probability is invented here."))

    r5 = d3.get("recent5") or {}
    tto = d3.get("tto") or {}
    cards.append(_step(3, "Starting Pitcher Quality", f"{d3.get('starter_profile_label') or 'PENDING'} • {_score(d3.get('starter_profile_score'))}", [
        _line("Starter", f"{_esc(d3.get('starter_name'))} ({_esc(d3.get('starter_hand'))}) • ERA {_num(d3.get('era'))} • xERA {_num(d3.get('xera'))} • FIP {_num(d3.get('fip'))} • WHIP {_num(d3.get('whip'))}"),
        _line("Miss / hit suppression", f"K {_rate(d3.get('k_pct'))} • BB {_rate(d3.get('bb_pct'))} • H/9 {_num(d3.get('h9'))} • xBA allowed {_avg(d3.get('xba_allowed'))}"),
        _line("Recent L5", f"{int(r5.get('starts') or 0)} starts • ERA {_num(r5.get('era'))} • WHIP {_num(r5.get('whip'))} • K {_rate(r5.get('k_pct'))}"),
        _line("Workload / TTO", f"{_num(d3.get('ip_per_start'),1)} IP/start • {_num(d3.get('pitches_per_start'),1)} pitches/start • {_esc(d3.get('third_time_label') or tto.get('status'))}"),
    ], "Starter quality is descriptive context; later layers determine how it connects to this hitter."))

    bvp_ab = int(d4.get("bvp_ab") or 0)
    cards.append(_step(4, "Platoon + Batter-vs-Pitcher", f"{d4.get('matchup_data_label') or 'PENDING'} • {_score(d4.get('matchup_data_score'))}", [
        _line("Hitter platoon", f"vs {_esc(d4.get('hitter_split_label'))}: {int(d4.get('hitter_split_hits') or 0)} H / {int(d4.get('hitter_split_ab') or 0)} AB • AVG {_avg(d4.get('hitter_split_avg'))} • OPS {_num(d4.get('hitter_split_ops'),3)}"),
        _line("Pitcher split", f"vs {_esc(d4.get('pitcher_split_label'))}: {int(d4.get('pitcher_split_hits') or 0)} H allowed / {int(d4.get('pitcher_split_bf') or 0)} BF • AVG {_avg(d4.get('pitcher_split_avg'))} • OPS {_num(d4.get('pitcher_split_ops'),3)}"),
        _line("BvP history", f"{int(d4.get('bvp_hits') or 0)}/{bvp_ab} • raw AVG {_avg(d4.get('bvp_avg'))} → shrunk {_avg(d4.get('bvp_shrunk_avg'))} • reliability {_rate(d4.get('bvp_reliability'))}"),
        _line("Context index", f"{_esc(d4.get('platoon_context_label'))} • {_score(d4.get('platoon_context_score'))} • coverage {_rate(d4.get('platoon_context_coverage'))}"),
    ], "Small BvP samples remain shrinkage-protected and cannot overpower the larger hitter/pitcher evidence."))

    pitch_boxes = "".join(_sub(f"<b>{_esc(r.get('name'))}</b> • usage {_rate(r.get('usage'))} • hitter xBA {_avg(r.get('xba'))} • contact {_rate(r.get('contact_pct'))} • whiff {_rate(r.get('whiff_pct'))}") for r in (d5.get("pitch_rows") or [])[:3])
    cards.append(_step(5, "Pitch-Mix Matchup", f"{d5.get('pitch_mix_data_label') or 'PENDING'} • {_score(d5.get('pitch_mix_data_score'))}", [
        _line("Pitch-mix verdict", f"{_esc(d5.get('pitch_mix_label'))} • index {_score(d5.get('pitch_mix_score'))} • evidence {_rate(d5.get('pitch_mix_coverage'))} • arsenal {_rate(d5.get('arsenal_coverage'))}"),
        _line("Weighted results", f"xBA {_avg(d5.get('weighted_xba'))} • contact {_rate(d5.get('weighted_contact_pct'))} • whiff {_rate(d5.get('weighted_whiff_pct'))} • EV {_num(d5.get('weighted_avg_ev'),1)} • hard-hit {_rate(d5.get('weighted_hard_hit_pct'))}"),
        pitch_boxes or _sub("Starter arsenal / hitter pitch-type sample is still pending."),
    ], "Pitch-type samples are reliability-gated; this card displays the certified arsenal mapping without adding new probability math."))

    cards.append(_step(6, "Batted-Ball Quality", f"{d6.get('batted_ball_data_label') or 'PENDING'} • {_score(d6.get('batted_ball_data_score'))}", [
        _line("Contact verdict", f"{_esc(d6.get('batted_ball_label'))} • index {_score(d6.get('batted_ball_score'))} • sample reliability {_rate(d6.get('batted_ball_reliability'))}"),
        _line("Impact quality", f"Avg EV {_num(d6.get('avg_ev'),1)} • max EV {_num(d6.get('max_ev'),1)} • hard-hit {_rate(d6.get('hard_hit_pct'))} • barrel {_rate(d6.get('barrel_pct'))} • xBA/contact {_avg(d6.get('xba_contact'))}"),
        _line("Launch profile", f"{_esc(d6.get('launch_profile_label'))} • GB {_rate(d6.get('ground_ball_pct'))} • LD {_rate(d6.get('line_drive_pct'))} • FB {_rate(d6.get('fly_ball_pct'))}"),
        _line("Spray", f"{_esc(d6.get('spray_label'))} • pull {_rate(d6.get('pull_pct'))} • center {_rate(d6.get('center_pct'))} • oppo {_rate(d6.get('oppo_pct'))} • {int(d6.get('bbe') or 0)} tracked BBE"),
    ], "Contact-quality evidence is sample protected and remains separate from environment, bullpen and PA opportunity."))

    cards.append(_step(7, "Park + Weather + Defense", f"{d7.get('environment_data_label') or 'PENDING'} • {_score(d7.get('environment_data_score'))}", [
        _line("Environment", f"{_esc(d7.get('venue_name_step7'))} • {_esc(d7.get('weather_label'))} • {_num(d7.get('temperature'),0)}°F • {_esc(d7.get('condition'))} • wind {_esc(d7.get('wind_text'))} • roof {_esc(d7.get('roof_type'))}"),
        _line("Park", f"{_esc(d7.get('park_label'))} • hit proxy {_num(d7.get('park_factor_proxy'),3)} • reliability {_rate(d7.get('park_reliability'))} • surface {_esc(d7.get('turf_type'))}"),
        _line("Opponent defense", f"{_esc(d7.get('defense_label'))} • fielding {_avg(d7.get('defense_fielding_pct'))} • errors/game {_num(d7.get('defense_errors_per_game'),2)} • reliability {_rate(d7.get('defense_reliability'))}"),
        _line("Environment index", f"{_esc(d7.get('environment_label'))} • {_score(d7.get('environment_score'))} • coverage {_rate(d7.get('environment_coverage'))}"),
    ], "Only verified venue, official game-feed weather and season fielding context are displayed; missing values stay neutral/pending."))

    relievers = " • ".join(f"{_esc(r.get('name'))} {_esc(r.get('hand'))}HP ERA {_num(r.get('era'))}" for r in (d8.get("relievers") or [])[:3]) or "Relief pool pending"
    cards.append(_step(8, "Bullpen Path", f"{d8.get('bullpen_data_label') or 'PENDING'} • {_score(d8.get('bullpen_data_score'))}", [
        _line("Bullpen quality", f"{_esc(d8.get('bullpen_quality_label'))} • ERA {_num(d8.get('era'))} • xERA {_num(d8.get('xera'))} • WHIP {_num(d8.get('whip'))} • K {_rate(d8.get('k_pct'))} • H/9 {_num(d8.get('h9'))}"),
        _line("Handedness / availability", f"LHP {_rate(d8.get('left_share'))} • RHP {_rate(d8.get('right_share'))} • depth availability {_rate(d8.get('availability_index'))} • READY {int(d8.get('ready_count') or 0)} / WATCH {int(d8.get('watch_count') or 0)} / LIMITED {int(d8.get('limited_count') or 0)}"),
        _line("Expected exposure", f"Starter {_num(d8.get('expected_starter_ip'),1)} IP • bullpen {_num(d8.get('expected_bullpen_ip'),1)} IP • bullpen share {_rate(d8.get('bullpen_inning_share'))}"),
        _sub(f"<b>Likely active relief pool</b> • {relievers}"),
    ], "Reliever names are an active-roster pool, not a guaranteed sequence; workload and handedness path remain uncertainty-aware."))

    location = "HOME" if str(d9.get("side") or "").lower() == "home" else "AWAY"
    cards.append(_step(9, "Plate Appearance Opportunity", f"{d9.get('opportunity_readiness') or 'PENDING'} • {_score(d9.get('opportunity_data_score'))}", [
        _line("Batting-order opportunity", f"Bat #{int(d9.get('slot') or 0) if d9.get('valid_slot') else '—'} • {location} • expected PA {_num(d9.get('expected_pa'))} • expected AB {_num(d9.get('expected_ab'))}"),
        _line("Empirical range", f"PA {_num(d9.get('pa_low'),1)}–{_num(d9.get('pa_high'),1)} • AB {_num(d9.get('ab_low'),1)}–{_num(d9.get('ab_high'),1)} • {int(d9.get('range_sample_games') or 0)} comparable games"),
        _line("Team opportunity", f"Season {_num(d9.get('season_team_pa_per_game'),1)} PA/G • {location.lower()} {_num(d9.get('location_team_pa_per_game'),1)} • recent-10 {_num(d9.get('recent_team_pa_per_game'),1)}"),
        _line("Opponent path", f"Nominal {_num(d9.get('nominal_starter_pa'))} PA vs starter • {_num(d9.get('nominal_bullpen_pa'))} PA vs bullpen • {_esc(d9.get('ninth_inning_note'))}"),
    ], "Opportunity is modeled independently from hit skill; projected lineups remain provisional until confirmed."))

    l5 = d10.get("l5") or {}
    l10 = d10.get("l10") or {}
    l20 = d10.get("l20") or {}
    cards.append(_step(10, "Recent Form + Stability", f"{d10.get('recent_data_label') or 'PENDING'} • {_score(d10.get('recent_data_score'))}", [
        _line("Form verdict", f"{_esc(d10.get('recent_form_label'))} • index {_score(d10.get('recent_form_score'))} • trend {_esc(d10.get('trend_label'))} • stability {_esc(d10.get('stability_label'))} {_score(d10.get('stability_score'))}"),
        _line("L5", f"AVG {_avg(l5.get('avg'))} • shrunk {_avg(l5.get('shrunk_avg'))} • 1+ hit games {_rate(l5.get('hit_game_rate'))} • K {_rate(l5.get('k_pct'))}"),
        _line("L10", f"AVG {_avg(l10.get('avg'))} • shrunk {_avg(l10.get('shrunk_avg'))} • 1+ hit games {_rate(l10.get('hit_game_rate'))} • K {_rate(l10.get('k_pct'))}"),
        _line("L20", f"AVG {_avg(l20.get('avg'))} • shrunk {_avg(l20.get('shrunk_avg'))} • 1+ hit games {_rate(l20.get('hit_game_rate'))} • K {_rate(l20.get('k_pct'))}"),
    ], "All windows use completed pregame logs plus sample shrinkage so one hot or cold game cannot own the read."))

    raw_status = raw.get("probability_status") or "PENDING"
    cards.append(_step(11, "Raw Hit Probability Engine", f"{raw_status} • data {_score(raw.get('composite_data_score'))}", [
        _line("Raw distribution", f"P(1+) {_rate(raw.get('p1_plus'))} • P(0) {_rate(raw.get('p0'))} • P(2+) {_rate(raw.get('p2_plus'))} • exactly 1 {_rate(raw.get('p_exactly_1'))}"),
        _line("Hit expectation", f"Expected hits {_num(raw.get('expected_hits'))} • median {_num(raw.get('median_hits'),0)} • mode {_num(raw.get('mode_hits'),0)} • fair 1+ {_odds(raw.get('raw_fair_odds_1_plus'))}"),
        _line("Starter / bullpen path", f"Starter hit/PA {_rate(raw.get('starter_hit_per_pa'))} over {_num(raw.get('starter_pa'))} PA • bullpen hit/PA {_rate(raw.get('bullpen_hit_per_pa'))} over {_num(raw.get('bullpen_pa'))} PA"),
        _line("Simulation", f"{int(raw.get('simulations') or 0):,} trials • {int(raw.get('batches') or 0)} batches • seed {int(raw.get('random_seed') or 0)} • {'CONVERGED' if raw.get('monte_carlo_converged') else 'CHECK'}"),
    ], "Step 11 is the certified raw/pre-calibration distribution. Step 12 owns the final published probability and confidence."))

    final_status = final.get("final_status") or "PENDING"
    cards.append(_step(12, "Calibration + Final Intelligence", f"{final_status} • {final.get('final_grade') or '—'}", [
        _line("Final distribution", f"P(1+) {_rate(final.get('final_p1_plus'))} • P(0) {_rate(final.get('final_p0'))} • P(2+) {_rate(final.get('final_p2_plus'))} • exactly 1 {_rate(final.get('final_p_exactly_1'))}"),
        _line("Final expectation", f"Expected hits {_num(final.get('final_expected_hits'))} • median/mode {_num(final.get('final_median_hits'),0)} / {_num(final.get('final_mode_hits'),0)} • fair 1+ {_odds(final.get('final_fair_odds_1_plus'))}"),
        _line("Confidence / reliability", f"{int(final.get('final_confidence') or 0)}/100 • {_esc(final.get('final_confidence_label'))} • range {_rate(final.get('reliability_low'))}–{_rate(final.get('reliability_high'))}"),
        _line("Calibration", f"{_esc(final.get('calibration_status_step12'))} • raw {_rate(final.get('p1_plus'))} → empirical {_rate(final.get('empirical_p1_plus'))} → final {_rate(final.get('final_p1_plus'))}"),
    ], "Final V2 output is copied from the certified Step 12 calibration layer; this scouting card does not recalculate or alter it."))
    return "".join(cards)


def _summary_html(data: dict[str, Any]) -> str:
    d1 = data.get("step1") or {}
    d9 = data.get("step9") or {}
    d10 = data.get("step10") or {}
    raw = data.get("step11") or {}
    final = data.get("step12") or {}
    populated = sum(1 for key in [f"step{i}" for i in range(1, 13)] if data.get(key))
    supports = []
    watches = []
    if int(d1.get("score") or 0) >= 80:
        supports.append(f"Data quality {d1.get('quality_label')}")
    if str(d9.get("opportunity_readiness") or "").upper() == "READY":
        supports.append("PA opportunity READY")
    if str(raw.get("probability_status") or "").upper() == "READY_RAW":
        supports.append("Raw model READY")
    if str(final.get("final_status") or "").upper() not in {"", "GATED", "PENDING"}:
        supports.append(f"Final model {final.get('final_status')}")
    if not d1.get("confirmed"):
        watches.append("Lineup not confirmed")
    if str(raw.get("probability_status") or "").upper() == "GATED":
        watches.append("Raw probability gated")
    cal = str(final.get("calibration_status_step12") or "PENDING")
    if cal.upper() in {"COLD_START", "WARMUP", "GATED", "PENDING"}:
        watches.append(f"Calibration {cal}")
    gates = [str(x) for x in (raw.get("probability_gates") or [])][:2]
    watches.extend(gates)
    supports_text = " • ".join(supports) if supports else "Certified evidence shown in Steps 1–12"
    watch_text = " • ".join(watches) if watches else "No additional readiness warnings surfaced"
    neutral = f"Pitch mix: {d10.get('recent_form_label') or '—'} recent form • evidence coverage {populated}/12 populated steps"
    probability = _rate(final.get("final_p1_plus"))
    confidence_label = str(final.get("final_confidence_label") or "PENDING")
    return (
        '<div class="mx52-final"><div class="mx52-finalhead"><span>FINAL • MATCHUP EVIDENCE SUMMARY</span><span>V2 probability unchanged</span></div>'
        '<div class="mx52-badges">'
        f'<span class="mx52-badge green">GRADE • {_esc(final.get("final_grade"))}</span>'
        f'<span class="mx52-badge">CONFIDENCE • {int(final.get("final_confidence") or 0)}/100</span>'
        f'<span class="mx52-badge">DATA • {_score(raw.get("composite_data_score"))}</span>'
        f'<span class="mx52-badge gold">CALIBRATION • {_esc(cal)}</span></div>'
        f'<div class="mx52-evidence ok">✅ Strongest verified evidence • {_esc(supports_text)}</div>'
        f'<div class="mx52-evidence watch">⚠ Watchlist • {_esc(watch_text)}</div>'
        f'<div class="mx52-neutral">{_esc(neutral)}</div>'
        f'<div class="mx52-big">{probability}</div>'
        f'<div class="mx52-bigsub">1+ Hit Probability • Fair {_odds(final.get("final_fair_odds_1_plus"))}</div>'
        '<div class="mx52-grid">'
        f'<div class="mx52-metric"><span>P(0 Hit)</span><b>{_rate(final.get("final_p0"))}</b></div>'
        f'<div class="mx52-metric"><span>P(2+ Hits)</span><b>{_rate(final.get("final_p2_plus"))}</b></div>'
        f'<div class="mx52-metric"><span>Expected Hits</span><b>{_num(final.get("final_expected_hits"))}</b></div>'
        f'<div class="mx52-metric"><span>Median / Mode</span><b>{_num(final.get("final_median_hits"),0)} / {_num(final.get("final_mode_hits"),0)}</b></div>'
        f'<div class="mx52-metric"><span>Raw P(1+)</span><b>{_rate(final.get("p1_plus"))}</b></div>'
        f'<div class="mx52-metric"><span>Reliability Range</span><b>{_rate(final.get("reliability_low"))}–{_rate(final.get("reliability_high"))}</b></div>'
        f'<div class="mx52-metric"><span>Final Fair 2+</span><b>{_odds(final.get("final_fair_odds_2_plus"))}</b></div>'
        f'<div class="mx52-metric"><span>Calibration Sample</span><b>{int(final.get("calibration_sample") or 0)}</b></div>'
        '</div>'
        f'<div class="mx52-confidence">{_esc(confidence_label)}</div>'
        f'<div class="mx52-foot">Evidence coverage {populated}/12 populated steps. Presentation synthesis only: final probability, fair odds, calibration, confidence and grade are displayed exactly from certified Step 12.</div>'
        '</div>'
    )


def _scouting_html(context: dict[str, Any], data: dict[str, Any]) -> str:
    d1 = data.get("step1") or {}
    source = (
        '<div class="mx52-intro"><div class="mx52-intro-main">🔥 Full 1+ Hit Matchup Intelligence</div><div class="mx52-intro-side">Pure player evidence<br>Steps 1–12</div></div>'
        '<div class="mx52-shell">'
        + _header_html(context, d1)
        + _step_cards(data, context)
        + _summary_html(data)
        + '</div>'
    )
    return "".join(line.strip() for line in source.splitlines() if line.strip())


def _capture_renderer(store: dict[str, Any], key: str, builder):
    def wrapped(games_df) -> None:
        store[key] = builder(games_df)
    return wrapped


def _research_caption(original):
    base = caption_ui._clean_engine_caption(original)
    def wrapped(body: Any, *args: Any, **kwargs: Any):
        text = str(body or "")
        if text.startswith("MLB Matchup Intelligence V2 • COMPLETE"):
            return None
        return base(body, *args, **kwargs)
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    st.markdown(step11_ui._STEP11_CSS + _SCOUT_CSS, unsafe_allow_html=True)
    step11_ui._render_stable_selectors(games_df)
    context = hero_helpers._selected_context(games_df)
    hero_slot = st.empty()
    step11_ui._render_spotlight(hero_slot, context, None)

    captured: dict[str, Any] = {}
    render_specs = [
        (p1, "_render_step1", p1._build_foundation, "step1"),
        (p2, "_render_step2", p2._build_profile, "step2"),
        (p3, "_render_step3", p3._build_step3, "step3"),
        (p4, "_render_step4", p4._build_step4, "step4"),
        (p5, "_render_step5", p5._build_step5, "step5"),
        (p6, "_render_step6", p6._build_step6, "step6"),
        (p7, "_render_step7", p7._build_step7, "step7"),
        (p8, "_render_step8", p8._build_step8, "step8"),
        (p9, "_render_step9", p9._build_step9, "step9"),
        (p10, "_render_step10", p10._build_step10, "step10"),
    ]
    original_renders = [(module, name, getattr(module, name)) for module, name, _, _ in render_specs]
    for module, name, builder, key in render_specs:
        setattr(module, name, _capture_renderer(captured, key, builder))

    original_raw_profile = final_layer._render_step11_profile
    original_final_profile = final_layer._render_step12_profile
    original_selectbox = st.selectbox
    original_text_input = st.text_input
    original_markdown = st.markdown
    original_expander = st.expander
    original_caption = st.caption

    def capture_raw(profile: dict[str, Any] | None) -> None:
        captured["step11"] = profile

    def capture_final(profile: dict[str, Any] | None) -> None:
        captured["step12"] = profile
        step11_ui._render_spotlight(hero_slot, context, profile)
        st.markdown(_scouting_html(context, captured), unsafe_allow_html=True)

    final_layer._render_step11_profile = capture_raw
    final_layer._render_step12_profile = capture_final
    st.selectbox = step11_ui.step1._legacy_selectbox_passthrough(original_selectbox)
    st.text_input = legacy_ui._legacy_text_input_passthrough(original_text_input)
    st.markdown = legacy_ui._legacy_markdown_passthrough(original_markdown)
    st.expander = collapse_ui._collapsed_expander(original_expander)
    st.caption = _research_caption(original_caption)
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        for module, name, original in original_renders:
            setattr(module, name, original)
        final_layer._render_step11_profile = original_raw_profile
        final_layer._render_step12_profile = original_final_profile
        st.caption = original_caption
        st.expander = original_expander
        st.markdown = original_markdown
        st.text_input = original_text_input
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP11_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_SCOUT_CSS",
    "_scouting_html",
    "render_matchup_hub",
]
