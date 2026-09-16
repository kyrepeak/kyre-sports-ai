"""CFB Game Total Clean Page V1 — Monster compact dashboard.

Presentation-only additive page over permanently frozen Game Total Hub V3.
The certified schedule, Step-11 distribution model, Step-12 final synthesis,
qualification thresholds, and full-slate Top-5 ranking are reused unchanged.

V150 changes only presentation:
- Phoenix, Arizona kickoff-time display,
- exact ESPN team-ID logos with fail-closed monograms,
- display-only runtime enrichment for venue/broadcast/identity,
- compact matchup hero and Quick Read,
- compact Step 11 / Step 12 status cards,
- deep evidence preserved inside collapsed expanders,
- final Game Total Top-5 scan preserved unchanged.

No sportsbook line, price, market probability, projection influence, or new
Game Total calculation is introduced here.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import streamlit as st

import cfb_game_total_hub_v3 as frozen_page
import cfb_over_under_logo_resolver_v3 as logo_v3
import cfb_over_under_runtime_team_data_v1 as runtime_display

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V1 • MONSTER COMPACT DASHBOARD"
MARKET = "Game Total"
FROZEN_GAME_TOTAL_HUB = "cfb_game_total_hub_v3"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_PHOENIX = ZoneInfo("America/Phoenix")
_EASTERN = ZoneInfo("America/New_York")

_CSS = r"""
<style>
.gt150-shell{box-sizing:border-box;margin:8px 0 12px;border:1px solid rgba(167,128,255,.30);border-radius:20px;background:radial-gradient(circle at 92% 0%,rgba(124,58,237,.15),transparent 25rem),linear-gradient(145deg,#07111e,#0a1525 58%,#0d1120);padding:14px;overflow:hidden}
.gt150-kicker{color:#b49cff;font-size:.58rem;font-weight:950;letter-spacing:.10em;text-transform:uppercase}.gt150-title{color:#f8fbff;font-size:1.45rem;font-weight:950;letter-spacing:-.03em;margin-top:3px}.gt150-sub{color:#8fa2b7;font-size:.64rem;line-height:1.45;margin-top:4px}
.gt150-pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.gt150-pill{border:1px solid rgba(119,140,166,.25);border-radius:999px;background:#0d1b2a;color:#b5c2d1;padding:5px 8px;font-size:.40rem;font-weight:900;white-space:nowrap}.gt150-pill.good{border-color:rgba(60,207,137,.40);background:rgba(21,92,61,.27);color:#94efbd}.gt150-pill.purple{border-color:rgba(168,116,255,.40);background:rgba(75,41,127,.26);color:#cbb1ff}.gt150-pill.blue{border-color:rgba(62,177,255,.35);background:rgba(20,73,108,.25);color:#8dd6ff}.gt150-pill.amber{border-color:rgba(244,191,77,.36);background:rgba(101,72,18,.26);color:#f5d47d}
.gt150-hero{margin-top:10px;border:1px solid rgba(76,153,220,.23);border-radius:17px;background:#081522;overflow:hidden}.gt150-match{display:grid;grid-template-columns:minmax(0,1fr) 58px minmax(0,1fr);gap:8px;align-items:stretch;padding:10px}.gt150-team{display:grid;grid-template-columns:62px minmax(0,1fr);gap:9px;align-items:center;border:1px solid rgba(148,163,184,.12);border-radius:14px;background:linear-gradient(145deg,#0a1724,#0b1420);padding:9px;min-width:0}.gt150-team.home{grid-template-columns:minmax(0,1fr) 62px;text-align:right}.gt150-team.home .gt150-logo{grid-column:2}.gt150-team.home .gt150-team-copy{grid-column:1;grid-row:1}.gt150-logo{width:62px;height:62px;border:1px solid rgba(255,255,255,.10);border-radius:13px;background:#0e1b28;display:flex;align-items:center;justify-content:center;overflow:hidden}.gt150-logo img{width:53px;height:53px;object-fit:contain}.gt150-mono{color:#dce9f3;font-size:.92rem;font-weight:950}.gt150-rank{color:#79d6ff;font-size:.38rem;font-weight:950;text-transform:uppercase}.gt150-name{color:#f5f9fc;font-size:1rem;font-weight:950;line-height:1.1;margin-top:2px}.gt150-meta{color:#8195a8;font-size:.41rem;font-weight:800;line-height:1.42;margin-top:4px}.gt150-at{display:flex;flex-direction:column;align-items:center;justify-content:center;color:#71889c;font-size:.31rem;font-weight:900}.gt150-at b{display:block;color:#edf5fa;font-size:1.04rem}
.gt150-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid rgba(76,153,220,.11)}.gt150-context div{padding:8px 9px;border-right:1px solid rgba(76,153,220,.08);min-width:0}.gt150-context div:last-child{border-right:0}.gt150-context small{display:block;color:#72889b;font-size:.28rem;font-weight:950;text-transform:uppercase}.gt150-context strong{display:block;color:#dce8f0;font-size:.44rem;margin-top:3px;line-height:1.35}
.gt150-section{margin-top:11px}.gt150-section-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 1px 7px}.gt150-section-title b{color:#eaf2f7;font-size:.56rem;font-weight:950;letter-spacing:.07em}.gt150-section-title span{color:#798b9d;font-size:.35rem}.gt150-quick{display:grid;grid-template-columns:1.2fr repeat(4,minmax(0,.72fr));gap:6px}.gt150-pick{border:1px solid rgba(164,112,255,.34);border-radius:14px;background:linear-gradient(145deg,rgba(71,42,118,.31),#0a1622);padding:10px}.gt150-pick small{display:block;color:#b9a2ff;font-size:.32rem;font-weight:950;text-transform:uppercase}.gt150-pick strong{display:block;color:#fbfaff;font-size:1.22rem;margin-top:3px}.gt150-pick span{display:block;color:#8f9caf;font-size:.35rem;margin-top:3px}.gt150-q{border:1px solid rgba(137,157,179,.14);border-radius:11px;background:#0a1620;padding:9px;min-width:0}.gt150-q b{display:block;color:#e8f0f5;font-size:.65rem;line-height:1.2}.gt150-q span{display:block;color:#748797;font-size:.28rem;text-transform:uppercase;margin-top:3px;line-height:1.3}
.gt150-statuses{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.gt150-status{border:1px solid rgba(130,151,172,.16);border-radius:12px;background:#0a151f;padding:9px}.gt150-status small{display:block;color:#7c91a2;font-size:.28rem;font-weight:950;text-transform:uppercase}.gt150-status b{display:block;color:#ecf3f7;font-size:.58rem;margin-top:4px}.gt150-status span{display:block;color:#8699a6;font-size:.32rem;line-height:1.4;margin-top:3px}.gt150-status.ready{border-color:rgba(60,207,137,.28);background:rgba(17,72,51,.19)}.gt150-status.ready b{color:#a1efc5}.gt150-status.gated{border-color:rgba(255,104,112,.28);background:rgba(90,31,37,.18)}.gt150-status.gated b{color:#ffb1b6}.gt150-note{margin-top:7px;border-left:3px solid #8d6cff;background:rgba(87,60,139,.12);border-radius:0 9px 9px 0;padding:8px 9px;color:#a8b1c1;font-size:.35rem;line-height:1.5}
@media(max-width:760px){.gt150-shell{padding:11px}.gt150-title{font-size:1.22rem}.gt150-match{grid-template-columns:1fr;padding:8px}.gt150-at{min-height:23px}.gt150-team,.gt150-team.home{grid-template-columns:54px minmax(0,1fr);text-align:left}.gt150-team.home .gt150-logo{grid-column:1}.gt150-team.home .gt150-team-copy{grid-column:2;grid-row:1}.gt150-logo{width:54px;height:54px}.gt150-logo img{width:46px;height:46px}.gt150-context{grid-template-columns:repeat(2,minmax(0,1fr))}.gt150-quick{grid-template-columns:repeat(2,minmax(0,1fr))}.gt150-pick{grid-column:1/-1}.gt150-statuses{grid-template-columns:1fr}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _record(profile: Mapping[str, Any]) -> str:
    return _clean(profile.get("record_text")) or "0-0"


def _rank(profile: Mapping[str, Any]) -> str:
    try:
        value = int(profile.get("ap_rank"))
        return f"AP #{value}" if value > 0 else "UNRANKED"
    except Exception:
        return "UNRANKED"


def _monogram(name: str) -> str:
    tokens = [token for token in _clean(name).replace("&", " ").split() if token]
    return "".join(token[0].upper() for token in tokens[:2]) or "CFB"


def _logo_html(name: str, visual: Mapping[str, Any]) -> str:
    url = _clean(visual.get("logo"))
    if url:
        return f'<div class="gt150-logo"><img src="{escape(url, quote=True)}" alt="{escape(name)} logo"></div>'
    return f'<div class="gt150-logo"><span class="gt150-mono">{escape(_monogram(name))}</span></div>'


def _display_game(game: Mapping[str, Any]) -> dict[str, Any]:
    """Enrich a copy for visuals only; frozen analysis receives original game."""
    out = dict(game)
    try:
        snapshot = runtime_display._find_snapshot(out)
        if snapshot:
            runtime_display._merge_game_snapshot(out, snapshot)
            out["gt150_display_snapshot_enriched"] = True
    except Exception:
        pass
    return out


def _kickoff_datetime(game: Mapping[str, Any]) -> datetime | None:
    raw = _clean(game.get("kickoff_iso"))
    if raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=_EASTERN)
            return parsed.astimezone(_PHOENIX)
        except Exception:
            pass
    day = _clean(game.get("game_date"))
    text = _clean(game.get("kickoff_et"))
    if day and text:
        cleaned = text.replace(" ET", "").replace(" EST", "").replace(" EDT", "").strip()
        for fmt in ("%I:%M %p", "%H:%M"):
            try:
                parsed = datetime.strptime(f"{day} {cleaned}", f"%Y-%m-%d {fmt}").replace(tzinfo=_EASTERN)
                return parsed.astimezone(_PHOENIX)
            except Exception:
                pass
    return None


def _kickoff_phoenix(game: Mapping[str, Any]) -> str:
    parsed = _kickoff_datetime(game)
    if parsed is None:
        return "TBD PHOENIX"
    return parsed.strftime("%I:%M %p").lstrip("0") + " Phoenix"


def _visuals(game: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    try:
        return logo_v3.resolve_visuals(game)
    except Exception:
        return {"away": {}, "home": {}}


def _hero(game: Mapping[str, Any], away: Mapping[str, Any], home: Mapping[str, Any]) -> str:
    visuals = _visuals(game)
    away_name = _clean(away.get("team")) or _clean(game.get("away_team")) or "Away"
    home_name = _clean(home.get("team")) or _clean(game.get("home_team")) or "Home"
    away_record = _record(away)
    home_record = _record(home)
    if away_record == "0-0":
        away_record = _clean(game.get("away_record_summary")) or away_record
    if home_record == "0-0":
        home_record = _clean(game.get("home_record_summary")) or home_record
    return f"""
<div class="gt150-hero">
  <div class="gt150-match">
    <div class="gt150-team">
      {_logo_html(away_name, visuals.get('away') or {})}
      <div class="gt150-team-copy"><div class="gt150-rank">{escape(_rank(away))}</div><div class="gt150-name">{escape(away_name)}</div><div class="gt150-meta">{escape(_clean(away.get('conference')) or _clean(game.get('away_conference')) or 'Conference unavailable')} • {escape(away_record)}</div></div>
    </div>
    <div class="gt150-at"><span>GAME TOTAL</span><b>@</b></div>
    <div class="gt150-team home">
      {_logo_html(home_name, visuals.get('home') or {})}
      <div class="gt150-team-copy"><div class="gt150-rank">{escape(_rank(home))}</div><div class="gt150-name">{escape(home_name)}</div><div class="gt150-meta">{escape(_clean(home.get('conference')) or _clean(game.get('home_conference')) or 'Conference unavailable')} • {escape(home_record)}</div></div>
    </div>
  </div>
  <div class="gt150-context">
    <div><small>Kickoff • PHOENIX</small><strong>{escape(_kickoff_phoenix(game))}</strong></div>
    <div><small>Venue</small><strong>{escape(_clean(game.get('venue')) or 'Venue unavailable')}</strong></div>
    <div><small>Status</small><strong>{escape(_clean(game.get('status')) or 'Status unavailable')}</strong></div>
    <div><small>Broadcast</small><strong>{escape(_clean(game.get('broadcast')) or 'Broadcast unavailable')}</strong></div>
  </div>
</div>
"""


def _quick_read(raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    step11_ready = bool(raw.get("ready"))
    step12_ready = bool(final.get("ready"))
    core = final.get("core_50_range") or {}
    band = final.get("most_likely_band") or {}
    projected = final.get("projected_combined_total") if step12_ready else raw.get("projected_combined_total")
    headline = _num(projected) if projected is not None else "GATED"
    grade = _clean(final.get("grade")) if step12_ready else "GATED"
    strength = _pct(final.get("forecast_strength")) if step12_ready else "—"
    core_text = f"{int(core.get('low') or 0)}–{int(core.get('high') or 0)}" if step12_ready and core else "—"
    band_text = _clean(band.get("label")) if step12_ready else "—"
    return f"""
<div class="gt150-section">
  <div class="gt150-section-title"><b>⚡ QUICK READ</b><span>Frozen Steps 11–12 • presentation only</span></div>
  <div class="gt150-quick">
    <div class="gt150-pick"><small>Independent Game Total forecast</small><strong>{escape(headline)}</strong><span>{'Final qualified forecast' if step12_ready else 'No total is invented while gated'}</span></div>
    <div class="gt150-q"><b>{escape(core_text)}</b><span>Core 50% range</span></div>
    <div class="gt150-q"><b>{escape(grade or '—')}</b><span>Final grade</span></div>
    <div class="gt150-q"><b>{escape(strength)}</b><span>Forecast strength</span></div>
    <div class="gt150-q"><b>{escape(band_text or '—')}</b><span>Likely band</span></div>
  </div>
</div>
"""


def _status_cards(raw: Mapping[str, Any], final: Mapping[str, Any]) -> str:
    step11_ready = bool(raw.get("ready"))
    step12_ready = bool(final.get("ready"))
    step11_reason = "Distribution ready • model output preserved" if step11_ready else " • ".join(str(x) for x in raw.get("reasons") or ["Distribution inputs incomplete"])
    step12_reason = "Final synthesis ready • qualification preserved" if step12_ready else " • ".join(str(x) for x in final.get("reasons") or ["Final qualification unavailable"])
    return f"""
<div class="gt150-section">
  <div class="gt150-section-title"><b>MODEL STATUS</b><span>Nothing is forced through a gate</span></div>
  <div class="gt150-statuses">
    <div class="gt150-status {'ready' if step11_ready else 'gated'}"><small>STEP 11 • DISTRIBUTION</small><b>{'READY' if step11_ready else 'GATED'}</b><span>{escape(step11_reason)}</span></div>
    <div class="gt150-status {'ready' if step12_ready else 'gated'}"><small>STEP 12 • FINAL</small><b>{'READY' if step12_ready else 'GATED'}</b><span>{escape(step12_reason)}</span></div>
  </div>
  <div class="gt150-note">Sportsbook projection influence: 0.0%. Game Total remains an independent combined-score forecast; this page does not alter frozen model math.</div>
</div>
"""


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        """
<div class="gt150-shell">
  <div class="gt150-kicker">CFB GAME TOTAL • MONSTER DASHBOARD</div>
  <div class="gt150-title">🏁 College Football Game Total</div>
  <div class="gt150-sub">Fast read first. Frozen Step 11 distribution and Step 12 final synthesis stay intact; detailed evidence is collapsed below.</div>
  <div class="gt150-pills"><span class="gt150-pill good">FROZEN MODEL ✅</span><span class="gt150-pill purple">STEP 11–12 ✅</span><span class="gt150-pill blue">PHOENIX TIME ✅</span><span class="gt150-pill good">EXACT LOGOS ✅</span><span class="gt150-pill amber">SPORTSBOOK 0.0%</span></div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected = st.date_input(
        "📅 CFB Game Total slate date",
        value=datetime.now(_PHOENIX).date(),
        key="cfb_v150_game_total_date",
    )
    selected_day = selected.isoformat()

    games, schedule_diag = frozen_page.frozen_v2.frozen_v1.schedule.load_with_diagnostics(selected_day)
    st.markdown(
        frozen_page.frozen_v2.frozen_v1.identity_ui._diagnostic_badges(schedule_diag),
        unsafe_allow_html=True,
    )
    if not games:
        st.warning("No verified FBS-scoped games were returned for this date. V150 fails closed—no Game Total forecast is invented.")
        return

    index = st.selectbox(
        "🏟️ Game Total matchup",
        options=list(range(len(games))),
        format_func=lambda i: frozen_page.frozen_v2.frozen_v1.identity_ui._matchup_label(games[int(i)]),
        key=f"cfb_v150_game_total_matchup_{selected_day}",
    )
    game = games[int(index)]

    # Frozen analysis receives the original certified game object unchanged.
    selected_result = frozen_page.slate.analyze_game(game, selected_day)
    away = selected_result.get("away") or {}
    home = selected_result.get("home") or {}
    raw = selected_result.get("raw") or {}
    final = selected_result.get("final") or {}
    team_diag = selected_result.get("team_diag") or {}

    # Runtime snapshot enrichment is presentation-only and cannot flow into the
    # frozen Step 11/12 analysis above.
    display_game = _display_game(game)
    st.markdown(_hero(display_game, away, home), unsafe_allow_html=True)
    st.markdown(_quick_read(raw, final), unsafe_allow_html=True)
    st.markdown(_status_cards(raw, final), unsafe_allow_html=True)

    with st.expander("Deep evidence • Step 11 distribution", expanded=False):
        st.markdown(frozen_page.frozen_v2._distribution_card(raw), unsafe_allow_html=True)
        for panel in (
            frozen_page.frozen_v2._band_panel(raw),
            frozen_page.frozen_v2._around_projection_panel(raw),
            frozen_page.frozen_v2._exact_panel(raw),
            frozen_page.frozen_v2._components_panel(raw),
        ):
            if panel:
                st.markdown(panel, unsafe_allow_html=True)

    with st.expander("Deep evidence • Step 12 final synthesis", expanded=False):
        st.markdown(frozen_page._final_card(game, final), unsafe_allow_html=True)

    with st.expander("Deep evidence • certified team audit", expanded=False):
        st.markdown(frozen_page.frozen_v2.frozen_v1.team_ui._STEP3_CSS, unsafe_allow_html=True)
        st.markdown(
            frozen_page.frozen_v2.frozen_v1.team_ui._team_data_diagnostics(team_diag),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="cfb3-grid">'
            + frozen_page.frozen_v2.frozen_v1.team_ui._team_card(away)
            + frozen_page.frozen_v2.frozen_v1.team_ui._team_card(home)
            + "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("### 🏆 Final Game Total Top-5")
    scan_key = f"cfb_v150_top5_{selected_day}"
    diag_key = f"cfb_v150_scan_diag_{selected_day}"
    if st.button(
        "Run final Game Total Top-5 scan",
        type="primary",
        key=f"cfb_v150_scan_button_{selected_day}",
    ):
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
        st.warning("No game cleared the frozen Step-12 qualification thresholds. V150 will not force a Top-5.")
    else:
        st.caption("Run the final slate scan to rank the strongest qualified Game Total forecasts.")

    st.caption("🛡️ V150 presentation only • frozen Game Total math preserved • sportsbook projection influence 0.0%")


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V150 Game Total page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "FROZEN_GAME_TOTAL_HUB",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_display_game",
    "_kickoff_phoenix",
    "render_cfb_hub",
    "render_game_total_hub",
]
