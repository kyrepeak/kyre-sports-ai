"""MLB Matchup Explorer V5.7 — cleanup Step 13 scouting-card rendering hotfix.

Presentation-only wrapper over certified Cleanup Step 11 and the Step 12 visual
work. The certified V2 player layer is allowed to execute normally; this wrapper
captures its finished Step 1-12 HTML at the Streamlit output boundary, then
renders those exact cards once inside a continuous gold-rail scouting shell.
No probability, calibration, Monte Carlo, ranking or Moneyline math is changed.
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
import mlb_matchup_player_v35 as final_layer

VERSION = "MLB Matchup Hub V5.7 • Cleanup Step 13 Scouting Card Hotfix"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_STEP11_PRESENTATION = "mlb_matchup_hub_v51"
FROZEN_STEP12_PRESENTATION = "mlb_matchup_hub_v52"
FROZEN_V2_PRESENTATION = "mlb_matchup_hub_v41"

_HOTFIX_CSS = r"""
<style>
/* Restore the complete Player Spotlight CSS chain that Step 12 accidentally
   dropped. The HTML was valid; its styles simply were not present. */
.mx53-intro{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin:4px 1px 9px}.mx53-intro-main{font-size:.92rem;font-weight:950;color:#f7f9fc}.mx53-intro-side{font-size:.48rem;line-height:1.4;text-align:right;color:#7d91a5;font-weight:900;letter-spacing:.10em;text-transform:uppercase}
.mx53-shell{position:relative;border:1px solid #a98628;border-left:7px solid #e0b52d;border-radius:25px;background:linear-gradient(150deg,#0b1727,#08111e 58%,#07101b);padding:17px 16px 20px;margin:0 0 12px;overflow:hidden;box-shadow:0 18px 38px rgba(0,0,0,.22)}
.mx53-shell:before{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle at 88% 0%,rgba(55,110,175,.13),transparent 30%)}
.mx53-verified{position:relative;color:#6ad8ff;font-size:.50rem;font-weight:950;letter-spacing:.10em;text-transform:uppercase;margin-bottom:12px}
.mx53-player{position:relative;display:grid;grid-template-columns:88px 1fr;gap:13px;align-items:center;margin-bottom:14px}.mx53-photo-wrap{width:84px;height:84px;border-radius:50%;padding:3px;background:linear-gradient(145deg,#4b9cff,#234e79)}.mx53-photo{width:100%;height:100%;border-radius:50%;object-fit:cover;object-position:center top;display:block;background:#132334}.mx53-name{font-size:1.38rem;line-height:1.04;font-weight:950;color:#fff;letter-spacing:-.025em}.mx53-team{display:flex;align-items:center;gap:7px;margin-top:5px;color:#a9bacb;font-size:.62rem;font-weight:800}.mx53-logo{width:31px;height:31px;object-fit:contain}.mx53-match{font-size:.56rem;color:#8da3b8;line-height:1.45;margin-top:3px}.mx53-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}.mx53-chip{border:1px solid #36516b;border-radius:999px;padding:4px 7px;font-size:.44rem;font-weight:900;color:#bad0df;background:#101b29}.mx53-chip.good{border-color:#2e714e;color:#8fe1aa;background:#0c2417}.mx53-chip.gold{border-color:#796522;color:#e8ca5f;background:#241f0d}

/* Existing certified Step cards are retained exactly, but visually nested into
   one continuous scouting card instead of being emitted as separate elements. */
.mx53-shell .mxv2-step{position:relative!important;margin:9px 0!important;border-radius:17px!important;box-shadow:none!important}.mx53-shell .mxv2-statgrid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.mx53-shell .mxv2-mini{min-width:0!important}.mx53-shell .mxv2-top{gap:8px!important}.mx53-shell .mxv2-badge{max-width:48%!important;white-space:normal!important;text-align:center!important}.mx53-shell .mxv2-pitchrow,.mx53-shell .mxv2-bprow,.mx53-shell .mxv2-formrow{overflow:hidden!important}

.mx53-final{position:relative;border:1px solid #a98628;border-left:5px solid #e0b52d;border-radius:20px;background:linear-gradient(145deg,#12150e,#0a1115 72%);padding:14px;margin-top:14px}.mx53-finalhead{display:flex;justify-content:space-between;gap:8px;color:#e8c75e;font-size:.53rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.mx53-badges{display:flex;flex-wrap:wrap;gap:7px;margin:11px 0}.mx53-badge{border:1px solid #35536e;border-radius:999px;padding:6px 9px;font-size:.47rem;font-weight:950;color:#a8cce9;background:#0d1a26}.mx53-badge.green{border-color:#2f7452;color:#8ce1aa;background:#0b2418}.mx53-badge.gold{border-color:#80651f;color:#e7c35a;background:#211c0b}.mx53-evidence{border-radius:12px;padding:9px 10px;margin:7px 0;font-size:.56rem;font-weight:800;line-height:1.45}.mx53-evidence.ok{border:1px solid #2d6f4b;background:#0c2518;color:#9edbb2}.mx53-evidence.watch{border:1px solid #7b6120;background:#241d0b;color:#e5c96c}.mx53-big{font-size:3.15rem;line-height:.95;font-weight:980;letter-spacing:-.05em;color:#fff;margin:18px 0 4px}.mx53-bigsub{font-size:.58rem;font-weight:900;color:#8294a9;letter-spacing:.03em;text-transform:uppercase}.mx53-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:14px}.mx53-metric{border:1px solid #294159;border-radius:14px;padding:11px 10px;background:#091522}.mx53-metric span{display:block;font-size:.44rem;font-weight:900;color:#6f879d;text-transform:uppercase;letter-spacing:.05em}.mx53-metric b{display:block;margin-top:5px;color:#f2f7fb;font-size:.96rem;font-weight:950}.mx53-foot{font-size:.45rem;color:#687d90;line-height:1.5;margin-top:9px}
@media(max-width:640px){.mx53-intro-main{font-size:.82rem}.mx53-intro-side{font-size:.42rem}.mx53-shell{padding:13px 11px 15px;border-radius:21px;border-left-width:6px}.mx53-player{grid-template-columns:74px 1fr;gap:10px}.mx53-photo-wrap{width:71px;height:71px}.mx53-name{font-size:1.08rem}.mx53-team{font-size:.54rem}.mx53-logo{width:27px;height:27px}.mx53-match{font-size:.49rem}.mx53-chip{font-size:.40rem;padding:3px 6px}.mx53-shell .mxv2-step{margin:8px 0!important;border-radius:15px!important}.mx53-final{padding:11px 9px;border-radius:17px}.mx53-finalhead{font-size:.47rem}.mx53-badge{font-size:.42rem;padding:5px 7px}.mx53-evidence{font-size:.50rem;padding:8px}.mx53-big{font-size:2.65rem}.mx53-bigsub{font-size:.50rem}.mx53-metric{padding:9px 8px}.mx53-metric span{font-size:.39rem}.mx53-metric b{font-size:.84rem}}
</style>
"""


def _esc(value: Any) -> str:
    return html.escape(str(value if value not in (None, "") else "—"))


def _rate(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"


def _num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _odds(value: Any) -> str:
    try:
        number = int(value)
        return f"+{number}" if number > 0 else str(number)
    except Exception:
        return "—"


def _score(value: Any) -> str:
    try:
        return f"{int(float(value))}/100"
    except Exception:
        return "—"


def _player_header(context: dict[str, Any]) -> str:
    row = context["row"]
    player = context["player"]
    player_id = int(player.get("id") or 0)
    side = str(player.get("side") or "").lower()
    team_id = row.get("away_team_id") if side == "away" else row.get("home_team_id")
    photo = hero_helpers._headshot_url(player_id) if player_id else ""
    logo = step11_ui._team_logo_url(team_id)
    role_label, _ = step11_ui.step1._role(player)
    slot = int(player.get("slot") or 0)
    slot_html = f'<span class="mx53-chip gold">Batting #{slot}</span>' if role_label != "Bench" and 1 <= slot <= 9 else ""
    role_class = "good" if role_label == "Confirmed" else ""
    photo_html = f'<img class="mx53-photo" src="{_esc(photo)}" alt="{_esc(player.get("name"))}">' if photo else '<div class="mx53-photo">⚾</div>'
    logo_html = f'<img class="mx53-logo" src="{_esc(logo)}" alt="{_esc(player.get("team"))} logo">' if logo else "⚾"
    pitcher = player.get("opponent_pitcher") or "TBD"
    return (
        '<div class="mx53-verified">⚾ Verified player • Matchup Intelligence V2</div>'
        '<div class="mx53-player">'
        f'<div class="mx53-photo-wrap">{photo_html}</div><div>'
        f'<div class="mx53-name">{_esc(player.get("name") or "Player")}</div>'
        f'<div class="mx53-team">{logo_html}<span>{_esc(player.get("team"))} • {_esc(player.get("position"))}</span></div>'
        f'<div class="mx53-match">vs {_esc(pitcher)} • 🌵 {_esc(step11_ui._phoenix_time_text(row))}</div>'
        f'<div class="mx53-chips"><span class="mx53-chip {role_class}">{_esc(role_label)}</span>{slot_html}</div>'
        '</div></div>'
    )


def _final_summary(raw: dict[str, Any] | None, final: dict[str, Any] | None, notices: list[str], step_count: int) -> str:
    raw = raw or {}
    final = final or {}
    calibration = str(final.get("calibration_status_step12") or "PENDING")
    watch_items = list(dict.fromkeys(x.strip() for x in notices if str(x).strip()))
    if step_count != 12:
        watch_items.insert(0, f"Visual capture returned {step_count}/12 certified Step cards")
    watch = " • ".join(watch_items[:4]) if watch_items else "No additional readiness warnings surfaced"
    return (
        '<div class="mx53-final">'
        '<div class="mx53-finalhead"><span>FINAL • MATCHUP EVIDENCE SUMMARY</span><span>V2 probability unchanged</span></div>'
        '<div class="mx53-badges">'
        f'<span class="mx53-badge green">GRADE • {_esc(final.get("final_grade"))}</span>'
        f'<span class="mx53-badge">CONFIDENCE • {int(final.get("final_confidence") or 0)}/100</span>'
        f'<span class="mx53-badge">DATA • {_score(raw.get("composite_data_score"))}</span>'
        f'<span class="mx53-badge gold">CALIBRATION • {_esc(calibration)}</span></div>'
        f'<div class="mx53-evidence ok">✅ Certified evidence • {step_count}/12 Step cards captured from the live V2 render path</div>'
        f'<div class="mx53-evidence watch">⚠ Watchlist • {_esc(watch)}</div>'
        f'<div class="mx53-big">{_rate(final.get("final_p1_plus"))}</div>'
        f'<div class="mx53-bigsub">1+ Hit Probability • Fair {_odds(final.get("final_fair_odds_1_plus"))}</div>'
        '<div class="mx53-grid">'
        f'<div class="mx53-metric"><span>P(0 Hit)</span><b>{_rate(final.get("final_p0"))}</b></div>'
        f'<div class="mx53-metric"><span>P(2+ Hits)</span><b>{_rate(final.get("final_p2_plus"))}</b></div>'
        f'<div class="mx53-metric"><span>Expected Hits</span><b>{_num(final.get("final_expected_hits"))}</b></div>'
        f'<div class="mx53-metric"><span>Median / Mode</span><b>{_num(final.get("final_median_hits"),0)} / {_num(final.get("final_mode_hits"),0)}</b></div>'
        f'<div class="mx53-metric"><span>Raw P(1+)</span><b>{_rate(raw.get("p1_plus"))}</b></div>'
        f'<div class="mx53-metric"><span>Reliability Range</span><b>{_rate(final.get("reliability_low"))}–{_rate(final.get("reliability_high"))}</b></div>'
        f'<div class="mx53-metric"><span>Raw Status</span><b>{_esc(raw.get("probability_status"))}</b></div>'
        f'<div class="mx53-metric"><span>Calibration Sample</span><b>{int(final.get("calibration_sample") or 0)}</b></div>'
        '</div>'
        f'<div class="mx53-foot">Presentation-only hotfix. The cards above are the exact finished Step 1–12 HTML emitted by the certified V2 player layer; no second probability or calibration run is created here.</div>'
        '</div>'
    )


def _scouting_html(context: dict[str, Any], step_html: list[str], raw: dict[str, Any] | None, final: dict[str, Any] | None, notices: list[str]) -> str:
    return (
        '<div class="mx53-intro"><div class="mx53-intro-main">🔥 Full 1+ Hit Matchup Intelligence</div><div class="mx53-intro-side">Pure player evidence<br>Steps 1–12</div></div>'
        '<div class="mx53-shell">'
        + _player_header(context)
        + "".join(step_html)
        + _final_summary(raw, final, notices, len(step_html))
        + '</div>'
    )


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

    # Step 11's spotlight depends on Step 9 + Step 10 CSS. Restore the whole chain.
    st.markdown(
        step11_ui.step9._STEP9_CSS
        + step11_ui.step10._STEP10_CSS
        + step11_ui._STEP11_CSS
        + _HOTFIX_CSS,
        unsafe_allow_html=True,
    )
    step11_ui._render_stable_selectors(games_df)
    context = hero_helpers._selected_context(games_df)
    hero_slot = st.empty()
    step11_ui._render_spotlight(hero_slot, context, None)

    captured_steps: list[str] = []
    notices: list[str] = []
    profiles: dict[str, dict[str, Any] | None] = {"raw": None, "final": None}
    capture_active = {"value": False}

    original_selectbox = st.selectbox
    original_text_input = st.text_input
    original_markdown = st.markdown
    original_expander = st.expander
    original_caption = st.caption
    original_warning = st.warning
    original_info = st.info
    original_raw_profile = final_layer._render_step11_profile
    original_final_profile = final_layer._render_step12_profile
    legacy_markdown = legacy_ui._legacy_markdown_passthrough(original_markdown)

    def capture_markdown(body: Any, *args: Any, **kwargs: Any):
        text = str(body or "")
        if '<div class="mxv2-step ' in text:
            capture_active["value"] = True
            captured_steps.append(text)
            return None
        return legacy_markdown(body, *args, **kwargs)

    def capture_warning(body: Any, *args: Any, **kwargs: Any):
        if capture_active["value"]:
            notices.append(str(body or ""))
            return None
        return original_warning(body, *args, **kwargs)

    def capture_info(body: Any, *args: Any, **kwargs: Any):
        if capture_active["value"]:
            notices.append(str(body or ""))
            return None
        return original_info(body, *args, **kwargs)

    def capture_raw(profile: dict[str, Any] | None) -> None:
        profiles["raw"] = profile
        return original_raw_profile(profile)

    def capture_final(profile: dict[str, Any] | None) -> None:
        profiles["final"] = profile
        original_final_profile(profile)
        capture_active["value"] = False
        step11_ui._render_spotlight(hero_slot, context, profile)
        if context:
            original_markdown(
                _scouting_html(context, captured_steps, profiles.get("raw"), profile, notices),
                unsafe_allow_html=True,
            )

    st.selectbox = step11_ui.step1._legacy_selectbox_passthrough(original_selectbox)
    st.text_input = legacy_ui._legacy_text_input_passthrough(original_text_input)
    st.markdown = capture_markdown
    st.expander = collapse_ui._collapsed_expander(original_expander)
    st.caption = _research_caption(original_caption)
    st.warning = capture_warning
    st.info = capture_info
    final_layer._render_step11_profile = capture_raw
    final_layer._render_step12_profile = capture_final
    try:
        current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        final_layer._render_step12_profile = original_final_profile
        final_layer._render_step11_profile = original_raw_profile
        st.info = original_info
        st.warning = original_warning
        st.caption = original_caption
        st.expander = original_expander
        st.markdown = original_markdown
        st.text_input = original_text_input
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP11_PRESENTATION",
    "FROZEN_STEP12_PRESENTATION",
    "FROZEN_V2_PRESENTATION",
    "VERSION",
    "_HOTFIX_CSS",
    "_scouting_html",
    "render_matchup_hub",
]
