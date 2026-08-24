"""WNBA Spread V1.6.8 — Top-5 Card Step 6: spread-specific market context.

Presentation-only wrapper over the verified V1.6.7 Step-4 style repair + V1.6.6
Step-5 availability layer. Step 6 does not fetch a new provider and does not
create a second spread model. It reads only fields already present in the
verified Step-7 final candidate row (selected spread, price, sportsbook,
projected home margin, 5M MC cover probability, push probability, MC fair odds,
market no-vig probability, no-vig edge and EV) and turns them into spread-
specific descriptive context.

Nothing here feeds the protected V1.6.1 margin model, SportsGameOdds transport,
analytical probability, 5,000,000 Monte Carlo, convergence, qualification,
selected side, edge/EV, Pick Strength or ranking.
"""
from __future__ import annotations

from html import escape
import math

import numpy as np
import streamlit as st

import wnba_spread_hub_v163 as step3
import wnba_spread_hub_v166 as step5
import wnba_spread_hub_v167 as previous

base = step5.base
MODEL_VERSION = "WNBA SPREAD V1.6.8 • TOP-5 CARD STEP 6 MARKET CONTEXT"
_ORIGINAL_INSTALL_STEP5 = step5._install_step5


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _compact_html(fragment: str) -> str:
    return "".join(line.strip() for line in str(fragment or "").splitlines())


def _line(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x):
        return "—"
    if abs(x) < 1e-9:
        return "PK"
    return f"{x:+.1f}"


def _odds(value) -> str:
    x = _num(value, np.nan)
    if not np.isfinite(x) or abs(x) < 1e-9:
        return "—"
    return f"{x:+.0f}"


def _pct(value, digits=1) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:.{digits}f}%"


def _pp(value) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:+.1f} pp"


def _pts(value) -> str:
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:+.1f} pts"


def _american_implied(value):
    x = _num(value, np.nan)
    if not np.isfinite(x) or x == 0:
        return np.nan
    return (-x / (-x + 100.0)) if x < 0 else (100.0 / (x + 100.0))


def _spread_role(spread: float) -> tuple[str, str]:
    if not np.isfinite(spread) or abs(spread) < 1e-9:
        return "PICK'EM", "mid"
    if spread > 0:
        return "UNDERDOG", "good"
    return "FAVORITE", "mid"


def _line_mechanics(spread: float, push: float) -> tuple[str, str]:
    if not np.isfinite(spread):
        return "LINE FORMAT UNKNOWN", "warn"
    frac = abs(spread) - math.floor(abs(spread))
    if abs(frac - 0.5) < 1e-6:
        return "HALF-POINT • NO EXACT PUSH", "good"
    if np.isfinite(push) and push > 0:
        return f"WHOLE LINE • {_pct(push)} PUSH", "warn"
    return "WHOLE LINE • PUSH POSSIBLE", "mid"


def _disagreement(edge_pp: float) -> tuple[str, str]:
    if not np.isfinite(edge_pp):
        return "MARKET GAP UNAVAILABLE", "warn"
    if edge_pp >= 10.0:
        return "MAJOR MODEL / MARKET GAP", "good"
    if edge_pp >= 5.0:
        return "CLEAR MODEL / MARKET GAP", "good"
    if edge_pp >= 2.0:
        return "MODEST MODEL EDGE", "mid"
    if edge_pp > -2.0:
        return "NEAR MARKET", "mid"
    return "MARKET ABOVE MODEL", "bad"


def _cushion_label(cushion: float) -> tuple[str, str]:
    if not np.isfinite(cushion):
        return "CUSHION UNAVAILABLE", "warn"
    if cushion >= 5.0:
        return "STRONG MEAN CUSHION", "good"
    if cushion >= 2.5:
        return "MODERATE MEAN CUSHION", "mid"
    if cushion > 0:
        return "THIN MEAN CUSHION", "warn"
    return "MEAN OUTSIDE SPREAD", "bad"


def _cover_path(team_name: str, spread: float, selected_margin: float, cushion: float) -> str:
    name = str(team_name or "Selected team")
    if not np.isfinite(spread) or not np.isfinite(selected_margin):
        return "Cover-path description unavailable because the selected line or projected margin is missing."

    if spread > 0:
        if selected_margin > 0:
            return f"{name} is getting {_line(spread)} and the model mean also projects an outright win by {abs(selected_margin):.1f}."
        if abs(selected_margin) < spread:
            return f"The model mean projects {name} to lose by {abs(selected_margin):.1f}, but that is still {abs(cushion):.1f} points inside the {_line(spread)} underdog line."
        return f"The model mean projects {name} to lose by {abs(selected_margin):.1f}, which sits beyond the {_line(spread)} underdog line; any cover case comes from distribution upside rather than the mean."

    if spread < 0:
        required = abs(spread)
        if selected_margin > required:
            return f"The model mean projects {name} to win by {selected_margin:.1f}, clearing the {_line(spread)} favorite requirement by {cushion:.1f} points."
        if selected_margin > 0:
            return f"The model mean projects {name} to win by {selected_margin:.1f}, but not by enough to clear the {_line(spread)} favorite line at the mean."
        return f"The model mean projects {name} to lose by {abs(selected_margin):.1f} while laying {_line(spread)}; a cover would require a result well above the mean path."

    if selected_margin > 0:
        return f"At pick'em, the model mean projects {name} to win by {selected_margin:.1f}."
    if selected_margin < 0:
        return f"At pick'em, the model mean projects {name} to lose by {abs(selected_margin):.1f}."
    return "At pick'em, the projected mean is essentially tied."


def _risk_flags(spread: float, selected_margin: float, cushion: float, edge_pp: float, push: float, price: float) -> list[tuple[str, str]]:
    flags: list[tuple[str, str]] = []

    if np.isfinite(spread) and spread > 0 and np.isfinite(selected_margin) and selected_margin < 0 and np.isfinite(cushion) and cushion > 0:
        flags.append(("COVER ≠ OUTRIGHT WIN", "mid"))
    if np.isfinite(spread) and abs(spread) >= 8.0:
        flags.append(("LARGE SPREAD", "warn"))
    if np.isfinite(edge_pp) and edge_pp >= 10.0:
        flags.append(("LARGE MODEL / MARKET DISAGREEMENT", "warn"))
    if np.isfinite(cushion):
        if 0 < cushion < 2.5:
            flags.append(("THIN MEAN CUSHION", "warn"))
        elif cushion <= 0:
            flags.append(("MEAN DOES NOT COVER", "bad"))
    if np.isfinite(push) and push >= 0.02:
        flags.append(("MEANINGFUL PUSH EXPOSURE", "warn"))
    if np.isfinite(price) and price <= -120:
        flags.append(("JUICED BOOK PRICE", "warn"))

    if not flags:
        flags.append(("NO EXTRA SPREAD-SPECIFIC FLAG", "good"))
    return flags


def _market_context_block(day_str: str, row) -> str:
    try:
        selected_is_home = step3.prior._is_home(row)
        selected_name = str(row.get("best_side") or (row.get("home_team") if selected_is_home else row.get("away_team")) or "Selected team")
        opponent_name = str((row.get("away_team") if selected_is_home else row.get("home_team")) or "Opponent")

        spread = _num(row.get("best_spread"), np.nan)
        price = _num(row.get("best_price"), np.nan)
        book = str(row.get("book") or "—")
        cover = _num(row.get("best_cover_no_push"), np.nan)
        market_novig = _num(row.get("home_market_novig") if selected_is_home else row.get("away_market_novig"), np.nan)
        edge_pp = _num(row.get("best_edge_pp"), np.nan)
        ev = _num(row.get("best_ev"), np.nan)
        push = _num(row.get("mc_push"), np.nan)
        fair = _num(row.get("mc_home_fair_odds") if selected_is_home else row.get("mc_away_fair_odds"), np.nan)
        home_margin = _num(row.get("projected_home_margin"), np.nan)
        selected_margin = home_margin if selected_is_home else (-home_margin if np.isfinite(home_margin) else np.nan)
        cushion = selected_margin + spread if np.isfinite(selected_margin) and np.isfinite(spread) else np.nan
        raw_break_even = _american_implied(price)

        role, role_class = _spread_role(spread)
        mechanics, mechanics_class = _line_mechanics(spread, push)
        gap_read, gap_class = _disagreement(edge_pp)
        cushion_read, cushion_class = _cushion_label(cushion)
        cover_path = _cover_path(selected_name, spread, selected_margin, cushion)
        flags = _risk_flags(spread, selected_margin, cushion, edge_pp, push, price)

        if np.isfinite(selected_margin):
            if selected_margin > 0:
                result_read = f"{selected_name} by {selected_margin:.1f}"
                result_class = "good"
            elif selected_margin < 0:
                result_read = f"{opponent_name} by {abs(selected_margin):.1f}"
                result_class = "mid" if spread > 0 and np.isfinite(cushion) and cushion > 0 else "bad"
            else:
                result_read = "Projected tie"
                result_class = "mid"
        else:
            result_read, result_class = "—", "warn"

        if np.isfinite(cushion) and np.isfinite(edge_pp):
            if cushion >= 5.0 and edge_pp >= 5.0:
                risk_read = "The model has both a positive mean spread cushion and a clear probability gap versus the no-vig market."
                risk_class = "good"
            elif cushion >= 2.5 and edge_pp >= 2.0:
                risk_read = "The model has a positive but not oversized mean cushion; a few points of margin movement can materially change the setup."
                risk_class = "mid"
            elif cushion > 0:
                risk_read = "The mean still covers, but the cushion is thin enough that small projection error matters."
                risk_class = "warn"
            else:
                risk_read = "The projected mean does not clear the spread; any positive cover probability is being carried by the simulated outcome distribution rather than the mean."
                risk_class = "bad"
        else:
            risk_read = "Spread-specific risk summary is partial because one or more verified final-row fields are unavailable."
            risk_class = "warn"

        flags_html = "".join(
            f'<span class="ks-spread168-flag {escape(cls)}">{escape(label)}</span>' for label, cls in flags
        )
    except Exception as exc:
        return _compact_html(f"""
        <div class="ks-spread168-wrap">
          <div class="ks-spread168-head"><span>STEP 6 • SPREAD-SPECIFIC MATCHUP + MARKET CONTEXT</span><span class="ks-spread168-chip warn">CONTEXT CHECK</span></div>
          <div class="ks-spread168-empty">Spread-specific market context could not be assembled from the existing final candidate row. Steps 1–5 and the production Spread model remain unchanged.</div>
          <div class="ks-spread168-note">Diagnostic • {escape(str(exc)[:180])}</div>
        </div>
        """)

    return _compact_html(f"""
    <div class="ks-spread168-wrap">
      <div class="ks-spread168-head"><span>STEP 6 • SPREAD-SPECIFIC MATCHUP + MARKET CONTEXT</span><span class="ks-spread168-chip good">VERIFIED FINAL-ROW CONTEXT</span></div>
      <div class="ks-spread168-scope">Existing Step-7 final candidate only • no new provider • no new projection • no reranking</div>

      <div class="ks-spread168-badges">
        <span class="ks-spread168-chip {role_class}">{escape(role)}</span>
        <span class="ks-spread168-chip {mechanics_class}">{escape(mechanics)}</span>
        <span class="ks-spread168-chip {gap_class}">{escape(gap_read)}</span>
        <span class="ks-spread168-chip {cushion_class}">{escape(cushion_read)}</span>
      </div>

      <div class="ks-spread168-grid">
        <div><small>SELECTED LINE</small><strong>{escape(selected_name)} {_line(spread)}</strong></div>
        <div><small>SPORTSBOOK PRICE</small><strong>{escape(book)} • {_odds(price)}</strong></div>
        <div><small>5M MC COVER</small><strong>{_pct(cover)}</strong></div>
        <div><small>MARKET NO-VIG</small><strong>{_pct(market_novig)}</strong></div>
        <div><small>NO-VIG DISAGREEMENT</small><strong>{_pp(edge_pp)}</strong></div>
        <div><small>BOOK RAW BREAK-EVEN</small><strong>{_pct(raw_break_even)}</strong></div>
        <div><small>MODEL FAIR PRICE</small><strong>{_odds(fair)}</strong></div>
        <div><small>BOOK PRICE</small><strong>{_odds(price)}</strong></div>
        <div><small>PROJECTED RESULT</small><strong class="{result_class}">{escape(result_read)}</strong></div>
        <div><small>SELECTED-TEAM MARGIN</small><strong>{_pts(selected_margin)}</strong></div>
        <div><small>PROJECTED COVER CUSHION</small><strong>{_pts(cushion)}</strong></div>
        <div><small>PUSH PROBABILITY</small><strong>{_pct(push)}</strong></div>
        <div class="wide"><small>COVER PATH AT THE MODEL MEAN</small><strong>{escape(cover_path)}</strong></div>
      </div>

      <div class="ks-spread168-flags"><small>SPREAD-SPECIFIC RISK FLAGS</small>{flags_html}</div>
      <div class="ks-spread168-read"><small>RISK / CONTEXT READ</small><strong class="{risk_class}">{escape(risk_read)}</strong></div>
      <div class="ks-spread168-note">Source • existing verified Step-7 final row: SportsGameOdds exact market + existing V1.6.1 projected margin + existing 5M Monte Carlo / fair odds / push probability. Step 6 is explanatory only • NOT FED INTO projected margin, Monte Carlo, market probability, no-vig edge, EV ({'—' if not np.isfinite(ev) else f'{100.0*ev:+.1f}%'}), qualification, selected side, Pick Strength or card ranking.</div>
    </div>
    """)


def _form_plus_step6(day_str: str, row) -> str:
    return step5._form_plus_step5(day_str, row) + _market_context_block(day_str, row)


def _install_step6() -> None:
    # Reinstall the verified Step-5 chain first, then replace only the same
    # presentation seam with Step 5 + Step 6. This function is deliberately
    # used as V1.6.6's installer hook so its own renderer can keep injecting
    # the already-verified Step-5 CSS and lower-layer behavior.
    _ORIGINAL_INSTALL_STEP5()
    step3._form_block = _form_plus_step6


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    # V1.6.7 restores Step-4 CSS and delegates to V1.6.6. V1.6.6 calls its
    # module-global _install_step5 at render time, so swap that UI installer
    # hook only. All protected production functions remain untouched.
    step5._install_step5 = _install_step6

    st.markdown(
        """
<style>
.ks-spread168-wrap{background:#0a1723;border:1px solid #36546d;border-radius:15px;padding:12px;margin-top:14px}
.ks-spread168-head{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;color:#9ed9ff;font-size:.59rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}
.ks-spread168-scope{color:#8198aa;font-size:.54rem;margin:7px 0 9px}.ks-spread168-badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:9px}
.ks-spread168-chip,.ks-spread168-flag{border-radius:999px;padding:5px 7px;border:1px solid #355873;color:#bed4e3;font-size:.43rem;font-weight:950;white-space:nowrap}.ks-spread168-chip.good,.ks-spread168-flag.good{border-color:#237a59;background:#0b3327;color:#7df2ba}.ks-spread168-chip.mid,.ks-spread168-flag.mid{border-color:#826c16;background:#3a3009;color:#ffe17a}.ks-spread168-chip.warn,.ks-spread168-flag.warn{border-color:#7c5832;background:#352516;color:#ffc984}.ks-spread168-chip.bad,.ks-spread168-flag.bad{border-color:#7a3941;background:#35171b;color:#ffadb5}
.ks-spread168-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.ks-spread168-grid div{background:#07131f;border:1px solid #24445c;border-radius:9px;padding:8px}.ks-spread168-grid .wide{grid-column:1/-1}.ks-spread168-grid small,.ks-spread168-flags small,.ks-spread168-read small{display:block;color:#718ba0;font-size:.42rem;font-weight:950;letter-spacing:.035em}.ks-spread168-grid strong{display:block;color:#f6fbff;font-size:.69rem;margin-top:3px;line-height:1.4}.ks-spread168-grid strong.good{color:#7df2ba}.ks-spread168-grid strong.mid{color:#ffe17a}.ks-spread168-grid strong.warn{color:#ffc984}.ks-spread168-grid strong.bad{color:#ffadb5}
.ks-spread168-flags,.ks-spread168-read{margin-top:8px;background:#081522;border:1px solid #284b64;border-radius:10px;padding:9px}.ks-spread168-flags .ks-spread168-flag{display:inline-block;margin:6px 5px 0 0}.ks-spread168-read strong{display:block;font-size:.61rem;line-height:1.5;margin-top:5px;color:#d8e7f2}.ks-spread168-read strong.good{color:#7df2ba}.ks-spread168-read strong.mid{color:#ffe17a}.ks-spread168-read strong.warn{color:#ffc984}.ks-spread168-read strong.bad{color:#ffadb5}
.ks-spread168-note{color:#6f8799;font-size:.50rem;line-height:1.45;margin-top:8px}.ks-spread168-empty{color:#c8d7e3;font-size:.63rem;line-height:1.5;margin-top:8px}
@media(max-width:760px){.ks-spread168-head{align-items:flex-start}.ks-spread168-chip,.ks-spread168-flag{font-size:.41rem}}
</style>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "🎨 Spread V1.6.8 • Top-5 Card Steps 1–6 ACTIVE • model snapshot + H2H + team form + recent matchup analytics + "
        "availability + spread-specific market context • all added card context remains presentation-only"
    )
    return previous.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(previous, name)
    except AttributeError:
        return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
