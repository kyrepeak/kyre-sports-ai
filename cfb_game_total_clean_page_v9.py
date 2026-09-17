"""CFB Game Total Clean Page V9 — deterministic connected all-steps flow.

Presentation-only successor to frozen V8. V9 reuses the exact frozen V6 model
and display-data owners but renders the approved compact team evidence and the
connected Steps 1–12 presentation directly. No projection, distribution,
qualification, Top-5 ranking, API, or sportsbook-influence math is changed.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping, Sequence

import streamlit as st

import cfb_game_total_clean_page_v6 as step_owner
import cfb_game_total_clean_page_v7 as evidence_owner
import cfb_game_total_clean_page_v8 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V9 • V157 CONNECTED ALL-STEPS FLOW"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v8"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

frozen_page = step_owner.frozen_page
logo_v3 = step_owner.logo_v3
runtime_display = step_owner.runtime_display

_STEP_KEYWORDS = {
    4: ("pace", "tempo", "plays per game", "seconds per play"),
    5: ("explosive", "yards per play", "20+", "10+"),
    6: ("red zone",),
    7: ("third down", "3rd down"),
    8: ("turnover", "giveaway", "takeaway"),
}
_STEP_MISSING_LABELS = {
    4: "pace/tempo",
    5: "explosive-play",
    6: "red-zone",
    7: "third-down",
    8: "turnover",
}

_V157_CSS = r"""
<style>
.gt157-flow{margin:9px 0 3px;padding:10px;border:1px solid rgba(153,112,255,.22);border-radius:15px;background:linear-gradient(180deg,rgba(11,24,36,.98),rgba(7,17,27,.98))}
.gt157-head{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin-bottom:8px}.gt157-head b{color:#eee8ff;font-size:.56rem;font-weight:950;letter-spacing:.06em}.gt157-head span{color:var(--gt-gray);font-size:.27rem;text-align:right}
.gt157-legend{display:flex;gap:5px;flex-wrap:wrap;margin:0 0 8px}.gt157-legend span{padding:3px 6px;border-radius:999px;font-size:.22rem;font-weight:900}.gt157-legend .support{background:rgba(34,197,94,.13);color:var(--gt-green)}.gt157-legend .concern{background:rgba(245,158,11,.13);color:var(--gt-amber)}.gt157-legend .neutral{background:rgba(119,185,232,.12);color:var(--gt-blue)}
.gt157-progress{display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:8px}.gt157-progress span{padding:4px 7px;border-radius:999px;background:rgba(93,63,145,.16);border:1px solid rgba(189,152,255,.17);color:#cdb9f3;font-size:.25rem;font-weight:900}.gt157-progress strong{color:#f2ecff}
.gt157-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.gt157-step{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:7px;align-items:start;min-height:72px;padding:8px;border:1px solid rgba(116,145,170,.14);border-radius:10px;background:#0a1823;position:relative;overflow:hidden}.gt157-step:before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--gt-blue)}.gt157-step.ready:before{background:var(--gt-green)}.gt157-step.check:before,.gt157-step.gated:before{background:var(--gt-amber)}
.gt157-num{display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:8px;background:rgba(119,185,232,.10);color:var(--gt-blue);font-size:.37rem;font-weight:950}.gt157-step.ready .gt157-num{background:rgba(38,111,77,.15);color:var(--gt-green)}.gt157-copy{min-width:0}.gt157-copy>b{display:block;color:#edf4f9;font-size:.44rem;font-weight:950}.gt157-copy>span{display:block;color:var(--gt-gray);font-size:.26rem;line-height:1.35;margin-top:2px;white-space:normal}.gt157-state{padding:3px 6px;border-radius:999px;font-size:.24rem;font-weight:950;white-space:nowrap}.gt157-state.ready{background:rgba(34,197,94,.13);color:var(--gt-green)}.gt157-state.check,.gt157-state.gated{background:rgba(245,158,11,.13);color:var(--gt-amber)}
.gt157-facts{display:grid;gap:4px;margin-top:6px}.gt157-fact{padding:5px 6px;border-radius:7px;background:#102330;border-left:2px solid rgba(119,185,232,.55)}.gt157-fact.support{border-left-color:var(--gt-green)}.gt157-fact.concern{border-left-color:var(--gt-amber)}.gt157-fact.neutral{border-left-color:var(--gt-blue)}.gt157-facttop{display:flex;align-items:center;gap:5px;flex-wrap:wrap}.gt157-tone{padding:2px 5px;border-radius:999px;font-size:.18rem;font-weight:950;letter-spacing:.04em}.gt157-tone.support{background:rgba(34,197,94,.13);color:var(--gt-green)}.gt157-tone.concern{background:rgba(245,158,11,.13);color:var(--gt-amber)}.gt157-tone.neutral{background:rgba(119,185,232,.12);color:var(--gt-blue)}.gt157-fact b{color:#dfe9f0;font-size:.25rem}.gt157-fact span.value{display:block;color:#aebdca;font-size:.24rem;line-height:1.35;margin-top:3px;overflow-wrap:anywhere}
.gt157-model{margin-top:7px;padding-top:7px;border-top:1px solid rgba(121,146,169,.13)}.gt157-final{margin-top:6px;border:1px solid rgba(160,112,255,.20);border-radius:11px;background:linear-gradient(145deg,rgba(75,41,127,.17),#0a1723);padding:8px}.gt157-finaltop{display:flex;align-items:center;justify-content:space-between;gap:8px}.gt157-finaltop b{color:#d9c8ff;font-size:.33rem;font-weight:950;letter-spacing:.05em}.gt157-finaltop span{color:var(--gt-purple);font-size:.24rem;font-weight:950}.gt157-finalgrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;margin-top:6px}.gt157-metric{background:#102330;border-radius:7px;padding:5px;min-width:0}.gt157-metric b{display:block;color:#edf4f9;font-size:.39rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gt157-metric span{display:block;color:var(--gt-gray);font-size:.19rem;font-weight:850;text-transform:uppercase;margin-top:2px}
.gt157-top5{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:6px;padding:7px 8px;border:1px dashed rgba(119,185,232,.22);border-radius:9px;background:rgba(18,38,54,.38)}.gt157-top5 b{color:var(--gt-blue);font-size:.31rem;font-weight:950}.gt157-top5 span{color:var(--gt-gray);font-size:.24rem;text-align:right}.gt157-note{margin-top:6px;color:#7f91a1;font-size:.22rem;line-height:1.4}.gt157-note strong{color:var(--gt-purple)}
@media(max-width:760px){.gt157-grid{grid-template-columns:1fr}.gt157-head{align-items:flex-start;flex-direction:column}.gt157-head span{text-align:left}.gt157-finalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt157-finalgrid .gt157-metric:first-child{grid-column:1/-1}.gt157-top5{align-items:flex-start;flex-direction:column}.gt157-top5 span{text-align:left}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _fact(label: str, value: Any, tone: str = "NEUTRAL") -> dict[str, str]:
    normalized_tone = tone if tone in {"SUPPORT", "CONCERN", "NEUTRAL"} else "NEUTRAL"
    return {
        "label": _clean(label) or "Evidence",
        "value": _clean(value) or "Verified value unavailable",
        "tone": normalized_tone,
    }


def _display_value(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, Mapping):
        parts: list[str] = []
        for key, nested in value.items():
            text = _display_value(nested)
            if text:
                parts.append(f"{_clean(key).replace('_', ' ').title()}: {text}")
        return " • ".join(parts)
    if isinstance(value, (list, tuple, set)):
        return " • ".join(text for text in (_display_value(item) for item in value) if text)
    return _clean(value)


def _official_fact_rows(state: Mapping[str, Any], keywords: Sequence[str]) -> list[dict[str, str]]:
    team = _clean(state.get("team")) or "Team"
    facts: list[dict[str, str]] = []
    for key, row in (state.get("official_stats") or {}).items():
        if not isinstance(row, Mapping):
            continue
        label = _clean(row.get("label")) or _clean(key).replace("_", " ").title()
        haystack = f"{key} {label}".lower()
        if not any(token in haystack for token in keywords):
            continue
        value = _clean(row.get("value") or row.get("display_value") or row.get("stat"))
        rank = _clean(row.get("rank"))
        detail = " • ".join(part for part in (value, f"Rank {rank}" if rank else "") if part)
        facts.append(_fact(f"{team} • {label}", detail or "Verified source row", "SUPPORT"))
        if len(facts) >= 2:
            break
    return facts


def _build_step_evidence_v157(
    identity: Mapping[str, Any],
    away: Mapping[str, Any],
    home: Mapping[str, Any],
    display_game: Mapping[str, Any],
    raw: Mapping[str, Any],
    final: Mapping[str, Any],
    statuses: Mapping[int, str],
) -> dict[int, dict[str, list[dict[str, str]]]]:
    """Build display-only evidence facts from already-existing certified inputs."""
    cards: dict[int, dict[str, list[dict[str, str]]]] = {}
    away_name = _clean(away.get("team")) or _clean((identity.get("away") or {}).get("team")) or "Away"
    home_name = _clean(home.get("team")) or _clean((identity.get("home") or {}).get("team")) or "Home"

    def availability_tone(step: int) -> str:
        return "SUPPORT" if _clean(statuses.get(step)).upper() == "READY" else "CONCERN"

    cards[1] = {
        "facts": [_fact("Verified matchup", f"{away_name} @ {home_name}", availability_tone(1))]
    }
    cards[2] = {
        "facts": [
            _fact(
                f"{away_name} profile",
                f"{_clean(away.get('record')) or '—'} • {_num(away.get('ppg'))} PPG • {_num(away.get('allowed_pg'))} allowed",
                availability_tone(2),
            ),
            _fact(
                f"{home_name} profile",
                f"{_clean(home.get('record')) or '—'} • {_num(home.get('ppg'))} PPG • {_num(home.get('allowed_pg'))} allowed",
                availability_tone(2),
            ),
        ]
    }
    matchup_tone = "NEUTRAL" if _clean(statuses.get(3)).upper() == "READY" else "CONCERN"
    cards[3] = {
        "facts": [
            _fact(
                f"{away_name} offense vs {home_name} defense",
                f"{_num(away.get('ppg'))} PPG vs {_num(home.get('allowed_pg'))} allowed",
                matchup_tone,
            ),
            _fact(
                f"{home_name} offense vs {away_name} defense",
                f"{_num(home.get('ppg'))} PPG vs {_num(away.get('allowed_pg'))} allowed",
                matchup_tone,
            ),
        ]
    }

    for step, keywords in _STEP_KEYWORDS.items():
        facts = _official_fact_rows(away, keywords) + _official_fact_rows(home, keywords)
        if not facts:
            facts = [
                _fact(
                    "Verified evidence",
                    f"No verified {_STEP_MISSING_LABELS[step]} row in current evidence",
                    "CONCERN",
                )
            ]
        cards[step] = {"facts": facts[:4]}

    environment: list[dict[str, str]] = []
    for label, key, suffix in (
        ("Weather", "weather", ""),
        ("Temperature", "temperature", ""),
        ("Wind", "wind_mph", " mph"),
        ("Forecast", "forecast", ""),
    ):
        value = display_game.get(key)
        if value not in (None, ""):
            environment.append(_fact(label, f"{_display_value(value)}{suffix}", "SUPPORT"))
    if not environment:
        environment = [
            _fact("Environment", "No verified weather / wind field in current evidence", "CONCERN")
        ]
    cards[9] = {"facts": environment[:3]}

    history = ""
    for key in ("series_history", "history", "head_to_head"):
        history = _display_value(display_game.get(key))
        if history:
            break
    cards[10] = {
        "facts": [
            _fact(
                "Series history",
                history or "No verified matchup-history field in current evidence",
                "SUPPORT" if history else "CONCERN",
            )
        ]
    }

    raw_ready = bool(raw.get("ready"))
    raw_facts = [
        _fact(
            "Distribution projection",
            _num(raw.get("projected_combined_total")),
            "SUPPORT" if raw_ready else "CONCERN",
        )
    ]
    if raw.get("sigma") not in (None, ""):
        raw_facts.append(_fact("Distribution spread", f"σ {_num(raw.get('sigma'))}", "NEUTRAL"))
    if not raw_ready and raw.get("reasons"):
        raw_facts.append(_fact("Gate", " • ".join(str(x) for x in raw.get("reasons") or []), "CONCERN"))
    cards[11] = {"facts": raw_facts}

    final_ready = bool(final.get("ready"))
    final_facts = [
        _fact(
            "Final projection",
            _num(final.get("projected_combined_total")),
            "SUPPORT" if final_ready else "CONCERN",
        )
    ]
    core = final.get("core_50_range") or {}
    if isinstance(core, Mapping) and core:
        final_facts.append(
            _fact("Core 50%", f"{_clean(core.get('low'))}–{_clean(core.get('high'))}", "NEUTRAL")
        )
    band = final.get("most_likely_band") or {}
    if isinstance(band, Mapping) and _clean(band.get("label")):
        final_facts.append(_fact("Likely band", _clean(band.get("label")), "NEUTRAL"))
    if final.get("forecast_strength") not in (None, ""):
        final_facts.append(_fact("Forecast strength", _pct(final.get("forecast_strength")), "NEUTRAL"))
    if not final_ready and final.get("reasons"):
        final_facts.append(_fact("Final gate", " • ".join(str(x) for x in final.get("reasons") or []), "CONCERN"))
    cards[12] = {"facts": final_facts[:4]}
    return cards


def _fact_html(fact: Mapping[str, Any]) -> str:
    tone = _clean(fact.get("tone")).upper()
    if tone not in {"SUPPORT", "CONCERN", "NEUTRAL"}:
        tone = "NEUTRAL"
    css_tone = tone.lower()
    return (
        f'<div class="gt157-fact {css_tone}">'
        f'<div class="gt157-facttop"><span class="gt157-tone {css_tone}">{escape(tone)}</span>'
        f'<b>{escape(_clean(fact.get("label")) or "Evidence")}</b></div>'
        f'<span class="value">{escape(_clean(fact.get("value")) or "Verified value unavailable")}</span>'
        "</div>"
    )


def _step_row(
    number: int,
    title: str,
    status: str,
    detail: str,
    facts: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    state = "ready" if status == "READY" else ("gated" if status == "GATED" else "check")
    facts_html = "".join(_fact_html(fact) for fact in (facts or []))
    facts_block = f'<div class="gt157-facts">{facts_html}</div>' if facts_html else ""
    return f"""
<div class="gt157-step {state}" data-testid="gt157-step-{number}">
  <div class="gt157-num">{number}</div>
  <div class="gt157-copy"><b>STEP {number} • {escape(title)}</b><span>{escape(detail)}</span>{facts_block}</div>
  <span class="gt157-state {state}">{escape(status)}</span>
</div>
"""


def _combined_flow_html(
    statuses: Mapping[int, str],
    details: Mapping[int, str],
    raw: Mapping[str, Any],
    final: Mapping[str, Any],
    evidence_cards: Mapping[int, Mapping[str, Any]] | None = None,
) -> str:
    cards = evidence_cards or {}
    rows: list[str] = []
    for number, title, _test_id in step_owner._STEP_1_10:
        rows.append(
            _step_row(
                number,
                title,
                _clean(statuses.get(number)) or "CHECK",
                _clean(details.get(number)) or "Verified evidence check",
                (cards.get(number) or {}).get("facts") or [],
            )
        )

    step11_ready = bool(raw.get("ready"))
    step12_ready = bool(final.get("ready"))
    step11_status = "READY" if step11_ready else "GATED"
    step12_status = "READY" if step12_ready else "GATED"
    step11_detail = (
        "Distribution ready • frozen model output preserved"
        if step11_ready
        else " • ".join(str(x) for x in raw.get("reasons") or ["Distribution inputs incomplete"])
    )
    step12_detail = (
        "Final synthesis ready • frozen qualification preserved"
        if step12_ready
        else " • ".join(str(x) for x in final.get("reasons") or ["Final qualification unavailable"])
    )
    rows.append(
        _step_row(
            11,
            "Distribution",
            step11_status,
            step11_detail,
            (cards.get(11) or {}).get("facts") or [],
        )
    )
    rows.append(
        _step_row(
            12,
            "Final Synthesis",
            step12_status,
            step12_detail,
            (cards.get(12) or {}).get("facts") or [],
        )
    )

    ready_count = sum(1 for number in range(1, 11) if statuses.get(number) == "READY")
    ready_count += int(step11_ready) + int(step12_ready)
    attention_count = 12 - ready_count

    projected = final.get("projected_combined_total") if step12_ready else raw.get("projected_combined_total")
    core = final.get("core_50_range") or {}
    band = final.get("most_likely_band") or {}
    core_text = (
        f"{int(core.get('low') or 0)}–{int(core.get('high') or 0)}"
        if step12_ready and core
        else "—"
    )
    band_text = _clean(band.get("label")) if step12_ready and isinstance(band, Mapping) else "—"
    grade = _clean(final.get("grade")) if step12_ready else "—"
    strength = _pct(final.get("forecast_strength")) if step12_ready else "—"
    final_state = "FINAL READY" if step12_ready else ("DISTRIBUTION READY" if step11_ready else "GATED")

    return _V157_CSS + f"""
<div class="gt157-flow" data-testid="gt157-connected-all-steps">
  <div class="gt157-head">
    <b>🧩 CONNECTED GAME TOTAL FLOW • ALL STEPS</b>
    <span>Evidence → Distribution → Final → Top-5 • one scan</span>
  </div>
  <div class="gt157-legend">
    <span class="support">SUPPORT = verified evidence present</span>
    <span class="concern">CONCERN = missing / gated evidence</span>
    <span class="neutral">NEUTRAL = context, not model direction</span>
  </div>
  <div class="gt157-progress">
    <span><strong>{ready_count}/12</strong> READY</span>
    <span><strong>{attention_count}</strong> CHECK / GATED</span>
    <span>0.0% sportsbook projection influence</span>
  </div>
  <div class="gt157-grid">{''.join(rows)}</div>
  <div class="gt157-model">
    <div class="gt157-final" data-testid="gt157-final-summary">
      <div class="gt157-finaltop"><b>FINAL • MODEL SUMMARY</b><span>{escape(final_state)}</span></div>
      <div class="gt157-finalgrid">
        <div class="gt157-metric"><b>{escape(_num(projected))}</b><span>Projection</span></div>
        <div class="gt157-metric"><b>{escape(core_text)}</b><span>Core 50%</span></div>
        <div class="gt157-metric"><b>{escape(band_text or '—')}</b><span>Likely band</span></div>
        <div class="gt157-metric"><b>{escape(grade or '—')}</b><span>Grade</span></div>
        <div class="gt157-metric"><b>{escape(strength)}</b><span>Strength</span></div>
      </div>
    </div>
    <div class="gt157-top5" data-testid="gt157-top5-connector">
      <b>TOP-5 • SLATE SCANNER</b><span>Frozen ranking unchanged • full scanner remains in the inherited drawer below</span>
    </div>
    <div class="gt157-note"><strong>Presentation only.</strong> SUPPORT means a verified evidence row is present; it does not create a new betting grade. Steps 11–12 reuse frozen model outputs. No projection, probability, qualification, or Top-5 calculation is changed.</div>
  </div>
</div>
"""


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    """Render V157 directly while reusing the exact frozen V6 owners."""
    st.markdown(
        step_owner.prior.prior.prior.prior.prior._CSS
        + step_owner.prior.prior.prior.prior._V151_CSS
        + step_owner.prior._V152_EVIDENCE_CSS
        + step_owner._V152_MONSTER_CSS,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="gt152-shell">
  <div class="gt152-shelltop">
    <div><div class="gt152-kicker">CFB GAME TOTAL • MONSTER DASHBOARD</div><div class="gt152-title">College Football Game Total</div><div class="gt152-sub">Matchup first. Evidence next. Deep model machinery stays out of the way until you want it.</div></div>
    <div class="gt152-live">V153 • V157 CONNECTED FLOW ACTIVE ✅</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=datetime.now(step_owner.prior.prior.prior.prior.prior._PHOENIX).date(),
        key="cfb_v152_game_total_date",
    )
    selected_day = selected.isoformat()
    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(frozen_page.frozen_v2.frozen_v1.identity_ui._diagnostic_badges(schedule_diag), unsafe_allow_html=True)
    if not games:
        st.warning("No verified FBS-scoped games were returned for this date. V157 fails closed—no Game Total forecast is invented.")
        return

    index = st.selectbox(
        "🏟️ Game Total matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_page.frozen_v2.frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_v152_game_total_matchup_{selected_day}",
    )
    game = games[int(index)]

    # FROZEN MODEL PATH: exact certified owner and untouched selected game.
    selected_result = frozen_page.slate.analyze_game(game, selected_day)
    frozen_away = selected_result.get("away") or {}
    frozen_home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}

    # DISPLAY-ONLY PATH: same certified reconciliation owner used by V6.
    display_game, display_away, display_home, _display_diag = runtime_display.reconcile_display_bundle(
        game,
        selected_day,
        frozen_away,
        frozen_home,
    )
    visuals = logo_v3.resolve_visuals(display_game)
    identity = step_owner.prior.prior.prior._identity_state(display_game, display_away, display_home, visuals)
    away_stats = step_owner.prior.prior._team_stats_state(display_away, display_game, "away")
    home_stats = step_owner.prior.prior._team_stats_state(display_home, display_game, "home")
    away_evidence = step_owner.prior._team_evidence_state(display_away, display_game, "away")
    home_evidence = step_owner.prior._team_evidence_state(display_home, display_game, "home")

    st.markdown(step_owner._monster_matchup_hero(identity, away_stats, home_stats), unsafe_allow_html=True)
    st.markdown(step_owner._compact_game_strip(identity), unsafe_allow_html=True)
    st.markdown(step_owner._scoring_defense_summary(away_stats, home_stats), unsafe_allow_html=True)

    statuses = step_owner._existing_step_status(identity, away_evidence, home_evidence, display_game)
    details = step_owner._step_details(identity, away_evidence, home_evidence, statuses)
    step_evidence = _build_step_evidence_v157(
        identity,
        away_evidence,
        home_evidence,
        display_game,
        raw,
        final,
        statuses,
    )

    with st.container(border=True):
        st.markdown(
            """
<div class="gt153-connected-head" data-testid="gt157-connected-evidence-shell">
  <div class="gt153-connected-kicker">CONNECTED GAME TOTAL FLOW • V157</div>
  <div class="gt153-connected-title">Steps 1–12 → Final → Top-5</div>
  <div class="gt153-connected-sub">Real football evidence stays inside every step card. Frozen calculations and deep evidence remain preserved exactly.</div>
</div>
""",
            unsafe_allow_html=True,
        )
        evidence_owner._render_compact_team_cards(away_evidence, home_evidence)
        st.markdown(
            _combined_flow_html(statuses, details, raw, final, step_evidence),
            unsafe_allow_html=True,
        )

        with st.expander("🔬 Raw Steps 1–10 evidence", expanded=False):
            evidence_owner._render_raw_team_evidence(away_evidence, home_evidence)

        with st.expander("📊 Deep model evidence • Step 11 distribution", expanded=False):
            st.markdown(frozen_page.frozen_v2._distribution_card(raw), unsafe_allow_html=True)
            for panel in (
                frozen_page.frozen_v2._band_panel(raw),
                frozen_page.frozen_v2._around_projection_panel(raw),
                frozen_page.frozen_v2._exact_panel(raw),
                frozen_page.frozen_v2._components_panel(raw),
            ):
                if panel:
                    st.markdown(panel, unsafe_allow_html=True)

        with st.expander("🏁 Deep model evidence • Step 12 final synthesis", expanded=False):
            st.markdown(frozen_page._final_card(game, final), unsafe_allow_html=True)

        with st.expander("🏆 Top-5 slate scanner", expanded=False):
            scan_key = f"cfb_v152_top5_{selected_day}"
            diag_key = f"cfb_v152_scan_diag_{selected_day}"
            if st.button("Run final Game Total Top-5 scan", type="primary", key=f"cfb_v152_scan_button_{selected_day}"):
                with st.spinner("Scanning the verified CFB slate through frozen Steps 11–12..."):
                    rows, diag = frozen_page.slate.scan_slate(games, selected_day)
                    st.session_state[scan_key] = frozen_page.final_model.rank_slate(rows, limit=5)
                    st.session_state[diag_key] = diag
            top5 = st.session_state.get(scan_key) or []
            diag = st.session_state.get(diag_key) or {}
            if diag:
                st.caption(
                    f"Final scanner: {int(diag.get('games_analyzed') or 0)} analyzed • "
                    f"{int(diag.get('final_ready') or 0)} final-ready • "
                    f"{int(diag.get('qualified_forecasts') or 0)} ranked-eligible • "
                    f"{len(diag.get('errors') or [])} errors"
                )
            if top5:
                for row in top5:
                    st.markdown(frozen_page._top_card(row), unsafe_allow_html=True)
            elif diag:
                st.warning("No game cleared the frozen Step-12 qualification thresholds. V157 will not force a Top-5.")
            else:
                st.caption("Run the final slate scan to rank the strongest qualified Game Total forecasts.")

    st.caption("🛡️ V157 connected display only • frozen Game Total math preserved • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V157 Game Total V9 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_build_step_evidence_v157",
    "_combined_flow_html",
    "render_cfb_hub",
    "render_game_total_hub",
]
