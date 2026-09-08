"""MLB Moneyline V17.6 — Step 10 expected game script + run distribution.

Additive synthesis wrapper over permanently frozen V17.5 Step 9. Step 10 turns
already-certified pregame evidence into a bounded, transparent team-run
expectation and overdispersed discrete run distribution.

Inputs are owned by earlier frozen steps:
- Step 3 starter vs posted opposing lineup
- Step 4 season offense baseline
- Step 5 bullpen strength + availability
- Step 6 posted lineup strength
- Step 7 park + weather run environment
- Step 8 defense + baserunning
- Step 9 recent scoring form (strictly pregame)

Important boundaries:
- Step 9 schedule density remains descriptive only and is never used here.
- Missing-player effects are not penalized again; only Step 6's already-derived
  lineup strength score is consumed.
- Step 10 does not replace or adjust the frozen Moneyline probability, ranking,
  fair odds, candidate selection, sportsbook price, or live-game model.
- Every input is bounded before synthesis and the projection fails closed when
  season offense or enough supporting components are unavailable.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_moneyline_hub_v175 as prior
import mlb_moneyline_hub_v170 as pregame
import mlb_moneyline_hub_v168 as step3
import mlb_moneyline_hub_v169 as step4
import mlb_moneyline_hub_v170 as step5
import mlb_moneyline_hub_v172 as step6
import mlb_moneyline_hub_v173 as step7
import mlb_moneyline_hub_v174 as step8

MODEL_VERSION = "V17.6 • MONEYLINE STEP 10 • EXPECTED GAME SCRIPT + RUN DISTRIBUTION"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v175"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN
SEASON = prior.SEASON

MIN_DATA_SCORE = 75
MIN_SUPPORT_COMPONENTS = 4
RECENT_BLEND = 0.18
HOME_RUN_MULTIPLIER = 1.025
RUN_FLOOR = 1.80
RUN_CEILING = 7.50
NB_DISPERSION = 5.5

_STEP10_CSS = r"""
<style>
.ml176-step10{grid-area:identity;margin-top:7px;padding:10px 11px;border:1px solid rgba(94,199,255,.30);border-radius:13px;background:linear-gradient(145deg,rgba(7,24,39,.97),rgba(9,17,27,.97));box-shadow:inset 3px 0 #5ec7ff}
.ml176-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml176-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#a9e4ff}
.ml176-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #506574;background:#182733;color:#d5e9f3}
.ml176-grade.home{border-color:#31755d;background:#0b3025;color:#98e7bf}.ml176-grade.away{border-color:#4e64a1;background:#111d3c;color:#abc2ff}.ml176-grade.neutral{border-color:#75621e;background:#31290d;color:#f4dc78}.ml176-grade.limited{border-color:#5a626a;background:#22292f;color:#d2dbe1}
.ml176-hero{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-bottom:8px}.ml176-hero div{border:1px solid rgba(94,199,255,.20);border-radius:10px;background:#091722;padding:8px;text-align:center}.ml176-hero b{display:block;color:#f4fbff;font-size:.86rem}.ml176-hero span{display:block;color:#718b99;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml176-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.ml176-side{border:1px solid rgba(94,199,255,.18);border-radius:10px;background:rgba(8,18,28,.82);padding:8px}.ml176-side.home{text-align:right}.ml176-side h4{margin:0 0 3px;color:#f2f7f8;font-size:.65rem}.ml176-side small{color:#718890;font-size:.44rem}
.ml176-run{display:inline-flex;margin-top:5px;border-radius:999px;padding:4px 7px;border:1px solid #3e6780;background:#0c2636;color:#bceaff;font-size:.45rem;font-weight:900}.ml176-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.ml176-stat{border:1px solid rgba(91,140,166,.16);border-radius:8px;padding:6px 4px;background:#091722;text-align:center}.ml176-stat b{display:block;color:#e8f0f4;font-size:.57rem}.ml176-stat span{display:block;color:#718592;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml176-note{margin-top:7px;border:1px solid rgba(94,199,255,.15);border-radius:8px;padding:6px 7px;background:#0a1c28;color:#aebdc6;font-size:.45rem;line-height:1.42}.ml176-note b{color:#e1f4ff}.ml176-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.ml176-pill{display:inline-flex;border-radius:999px;padding:4px 7px;border:1px solid rgba(94,199,255,.22);background:#0d2533;color:#c3eaff;font-size:.46rem;font-weight:850}.ml176-source{margin-top:6px;color:#708696;font-size:.43rem;line-height:1.4}
@media(max-width:640px){.ml176-grid{grid-template-columns:1fr}.ml176-side.home{text-align:left}.ml176-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.ml176-hero{grid-template-columns:1fr 1fr}.ml176-hero div:last-child{grid-column:1/-1}.ml176-step10{padding:9px}}
</style>
"""


def _f(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _score_signal(value: Any) -> float | None:
    score = _f(value)
    if score is None:
        return None
    return _clamp((score - 50.0) / 25.0, -1.0, 1.0)


def _nb_distribution(mean: float, max_runs: int = 10, dispersion: float = NB_DISPERSION) -> dict[str, Any]:
    """Negative-binomial run distribution with a stable 11+ tail bucket."""
    mu = _clamp(float(mean), 0.05, 20.0)
    r = max(0.50, float(dispersion))
    probs: list[float] = []
    p = r / (r + mu)
    q = 1.0 - p
    for k in range(max(0, int(max_runs)) + 1):
        logp = (
            math.lgamma(k + r)
            - math.lgamma(r)
            - math.lgamma(k + 1)
            + r * math.log(p)
            + k * math.log(q)
        )
        probs.append(math.exp(logp))
    tail = max(0.0, 1.0 - sum(probs))
    mode = max(range(len(probs)), key=lambda k: probs[k]) if probs else 0
    return {"mean": mu, "probs": probs, "tail": tail, "mode": mode, "dispersion": r}


def _run_buckets(dist: Mapping[str, Any]) -> dict[str, float]:
    probs = list(dist.get("probs") or [])

    def at(k: int) -> float:
        return float(probs[k]) if 0 <= k < len(probs) else 0.0

    return {
        "0_1": at(0) + at(1),
        "2_3": at(2) + at(3),
        "4_5": at(4) + at(5),
        "6_plus": max(0.0, 1.0 - sum(at(k) for k in range(0, 6))),
    }


def _team_projection(
    *,
    side: str,
    season_rpg: Any,
    recent_rpg: Any,
    starter_matchup_score: Any,
    lineup_score: Any,
    opponent_bullpen_score: Any,
    environment_score: Any,
    opponent_defense_score: Any,
    baserunning_score: Any,
) -> dict[str, Any]:
    season = _f(season_rpg)
    if season is None or season <= 0:
        return {
            "expected_runs": None,
            "data_score": 0,
            "support_components": 0,
            "reason": "Official season scoring baseline unavailable.",
            "modifiers": {},
        }

    recent = _f(recent_rpg)
    base = season
    recent_used = recent is not None and recent > 0
    if recent_used:
        base = (1.0 - RECENT_BLEND) * season + RECENT_BLEND * recent

    signals = {
        "starter_matchup": (_score_signal(starter_matchup_score), 0.10),
        "lineup": (_score_signal(lineup_score), 0.08),
        "opponent_bullpen": (_score_signal(opponent_bullpen_score), -0.08),
        "environment": (_score_signal(environment_score), 0.07),
        "opponent_defense": (_score_signal(opponent_defense_score), -0.05),
        "baserunning": (_score_signal(baserunning_score), 0.025),
    }
    usable = [(name, signal, weight) for name, (signal, weight) in signals.items() if signal is not None]
    log_adjustment = sum(float(signal) * float(weight) for _, signal, weight in usable)
    multiplier = math.exp(log_adjustment)
    if str(side).lower() == "home":
        multiplier *= HOME_RUN_MULTIPLIER

    expected = _clamp(base * multiplier, RUN_FLOOR, RUN_CEILING)
    support = len(usable) + (1 if recent_used else 0)
    data_score = 35 + min(60, support * 10) + (5 if str(side).lower() in {"away", "home"} else 0)
    data_score = int(_clamp(data_score, 0, 100))
    sufficient = support >= MIN_SUPPORT_COMPONENTS and data_score >= MIN_DATA_SCORE

    modifiers = {name: float(signal) for name, signal, _ in usable}
    if recent_used:
        modifiers["recent_scoring_blend"] = RECENT_BLEND

    return {
        "expected_runs": expected if sufficient else None,
        "raw_expected_runs": expected,
        "base_runs": base,
        "season_rpg": season,
        "recent_rpg": recent if recent_used else None,
        "data_score": data_score,
        "support_components": support,
        "reason": "" if sufficient else f"Only {support} supporting run components cleared evidence gates.",
        "modifiers": modifiers,
    }


def _script(away_runs: Any, home_runs: Any) -> tuple[str, str, str]:
    away = _f(away_runs)
    home = _f(home_runs)
    if away is None or home is None:
        return "GAME SCRIPT PENDING", "limited", "Run expectations did not clear the Step 10 gate."

    total = away + home
    margin = home - away
    if total <= 7.4:
        env = "LOW-SCORING"
    elif total >= 9.6:
        env = "HIGH-SCORING"
    else:
        env = "BALANCED-SCORING"

    if margin >= 1.0:
        direction, cls = "STRONG HOME RUN EDGE", "home"
    elif margin >= 0.45:
        direction, cls = "HOME RUN EDGE", "home"
    elif margin <= -1.0:
        direction, cls = "STRONG AWAY RUN EDGE", "away"
    elif margin <= -0.45:
        direction, cls = "AWAY RUN EDGE", "away"
    else:
        direction, cls = "TIGHT RUN SCRIPT", "neutral"

    if abs(margin) < 0.65:
        note = "One-run / late-leverage path is more plausible than a comfortable separation."
    elif margin > 0:
        note = "Expected scoring path favors the home side creating the larger run cushion."
    else:
        note = "Expected scoring path favors the away side creating the larger run cushion."
    return f"{direction} • {env}", cls, note


def _compose(
    result: Mapping[str, Any],
    row: Mapping[str, Any],
    *,
    step6_context: Mapping[str, Any],
    step7_context: Mapping[str, Any],
    step8_context: Mapping[str, Any],
    step9_context: Mapping[str, Any],
) -> dict[str, Any]:
    s3 = step3._ctx(result)
    s5 = step5._ctx(result)

    away4 = step4._team_ctx(
        result.get("away_team_id") or row.get("away_team_id"),
        result.get("away_name") or row.get("away_name") or row.get("away_team"),
    )
    home4 = step4._team_ctx(
        result.get("home_team_id") or row.get("home_team_id"),
        result.get("home_name") or row.get("home_name") or row.get("home_team"),
    )

    s6a, s6h = (step6_context.get("away") or {}), (step6_context.get("home") or {})
    s8a, s8h = (step8_context.get("away") or {}), (step8_context.get("home") or {})
    s9a, s9h = (step9_context.get("away") or {}), (step9_context.get("home") or {})
    env_score = step7_context.get("score")

    away = _team_projection(
        side="away",
        season_rpg=(away4.get("metrics") or {}).get("rpg"),
        recent_rpg=(s9a.get("l10") or {}).get("runs_per_game"),
        starter_matchup_score=(s3.get("away") or {}).get("score"),
        lineup_score=s6a.get("score"),
        opponent_bullpen_score=(s5.get("home") or {}).get("score"),
        environment_score=env_score,
        opponent_defense_score=(s8h.get("defense") or {}).get("score"),
        baserunning_score=(s8a.get("baserunning") or {}).get("score"),
    )
    home = _team_projection(
        side="home",
        season_rpg=(home4.get("metrics") or {}).get("rpg"),
        recent_rpg=(s9h.get("l10") or {}).get("runs_per_game"),
        starter_matchup_score=(s3.get("home") or {}).get("score"),
        lineup_score=s6h.get("score"),
        opponent_bullpen_score=(s5.get("away") or {}).get("score"),
        environment_score=env_score,
        opponent_defense_score=(s8a.get("defense") or {}).get("score"),
        baserunning_score=(s8h.get("baserunning") or {}).get("score"),
    )

    a_mu = away.get("expected_runs")
    h_mu = home.get("expected_runs")
    label, label_cls, note = _script(a_mu, h_mu)

    away_dist = _nb_distribution(a_mu) if a_mu is not None else {}
    home_dist = _nb_distribution(h_mu) if h_mu is not None else {}
    away_buckets = _run_buckets(away_dist) if away_dist else {}
    home_buckets = _run_buckets(home_dist) if home_dist else {}

    return {
        "away_name": str(result.get("away_name") or row.get("away_name") or row.get("away_team") or "Away"),
        "home_name": str(result.get("home_name") or row.get("home_name") or row.get("home_team") or "Home"),
        "away": away,
        "home": home,
        "away_dist": away_dist,
        "home_dist": home_dist,
        "away_buckets": away_buckets,
        "home_buckets": home_buckets,
        "label": label,
        "label_cls": label_cls,
        "script_note": note,
        "expected_total": (float(a_mu) + float(h_mu)) if a_mu is not None and h_mu is not None else None,
        "expected_margin_home": (float(h_mu) - float(a_mu)) if a_mu is not None and h_mu is not None else None,
        "mode_score": (
            f"{int(away_dist.get('mode') or 0)}-{int(home_dist.get('mode') or 0)}"
            if away_dist and home_dist else "N/A"
        ),
    }


def _pct(value: Any) -> str:
    x = _f(value)
    return "N/A" if x is None else f"{100.0 * x:.0f}%"


def _fmt(value: Any, digits: int = 2) -> str:
    x = _f(value)
    return "N/A" if x is None else f"{x:.{digits}f}"


def _side_html(
    name: str,
    side: Mapping[str, Any],
    buckets: Mapping[str, Any],
    dist: Mapping[str, Any],
    home: bool = False,
) -> str:
    mu = side.get("expected_runs")
    return (
        f'<div class="ml176-side {"home" if home else ""}">'
        f'<h4>{escape(name)}</h4>'
        f'<small>{int(side.get("support_components") or 0)} supporting components • data quality {int(side.get("data_score") or 0)}/100</small>'
        f'<div class="ml176-run">EXPECTED RUNS • {escape(_fmt(mu,2))}</div>'
        '<div class="ml176-stats">'
        f'<div class="ml176-stat"><b>{_pct(buckets.get("0_1"))}</b><span>0-1 runs</span></div>'
        f'<div class="ml176-stat"><b>{_pct(buckets.get("2_3"))}</b><span>2-3 runs</span></div>'
        f'<div class="ml176-stat"><b>{_pct(buckets.get("4_5"))}</b><span>4-5 runs</span></div>'
        f'<div class="ml176-stat"><b>{_pct(buckets.get("6_plus"))}</b><span>6+ runs</span></div>'
        '</div>'
        '<div class="ml176-stats">'
        f'<div class="ml176-stat"><b>{escape(_fmt(side.get("season_rpg"),2))}</b><span>Season R/G</span></div>'
        f'<div class="ml176-stat"><b>{escape(_fmt(side.get("recent_rpg"),2))}</b><span>Recent R/G</span></div>'
        f'<div class="ml176-stat"><b>{int(dist.get("mode") or 0) if dist else "N/A"}</b><span>Mode runs</span></div>'
        f'<div class="ml176-stat"><b>{escape(_fmt(side.get("base_runs"),2))}</b><span>Blended base</span></div>'
        '</div>'
        f'<div class="ml176-note"><b>Run synthesis:</b> bounded starter-matchup, lineup, opponent bullpen, environment, opponent defense and baserunning signals. {escape(str(side.get("reason") or ""))}</div>'
        '</div>'
    )


def _html(context: Mapping[str, Any]) -> str:
    total = context.get("expected_total")
    margin = context.get("expected_margin_home")
    margin_text = "N/A" if margin is None else f"{float(margin):+.2f}"
    return (
        '<div class="ml176-step10">'
        '<div class="ml176-head">'
        '<span class="ml176-title">STEP 10 • EXPECTED GAME SCRIPT + RUN DISTRIBUTION</span>'
        f'<span class="ml176-grade {escape(str(context.get("label_cls") or "limited"))}">{escape(str(context.get("label") or "GAME SCRIPT PENDING"))}</span>'
        '</div>'
        '<div class="ml176-hero">'
        f'<div><b>{escape(_fmt(total,2))}</b><span>Expected total runs</span></div>'
        f'<div><b>{escape(str(context.get("mode_score") or "N/A"))}</b><span>Most likely run mode A-H</span></div>'
        f'<div><b>{escape(margin_text)}</b><span>Expected home run margin</span></div>'
        '</div>'
        '<div class="ml176-grid">'
        f'{_side_html(context.get("away_name") or "Away", context.get("away") or {}, context.get("away_buckets") or {}, context.get("away_dist") or {}, False)}'
        f'{_side_html(context.get("home_name") or "Home", context.get("home") or {}, context.get("home_buckets") or {}, context.get("home_dist") or {}, True)}'
        '</div>'
        f'<div class="ml176-note"><b>Game script:</b> {escape(str(context.get("script_note") or ""))}</div>'
        '<div class="ml176-pills">'
        '<span class="ml176-pill">OVERDISPERSED RUN DISTRIBUTION</span>'
        '<span class="ml176-pill">SCHEDULE DENSITY NOT REUSED</span>'
        '<span class="ml176-pill">NO MARKET INPUT</span>'
        '<span class="ml176-pill">NO MONEYLINE PROBABILITY ADJUSTMENT</span>'
        '</div>'
        '<div class="ml176-source">Step 10 is a synthesis/cross-check layer only. It does not overwrite the frozen Moneyline win probability, ranking, fair odds, selection, or Step 5L live model.</div>'
        '</div>'
    )


def _inject(card: str, html: str) -> str:
    text = str(card or "")
    if not html or "ks-pick-card" not in text or "ml176-step10" in text:
        return text
    return text[:-6] + html + "</div>" if text.endswith("</div>") else text + html


_FROZEN_STEP9_RENDERER = prior._renderer


def _renderer(original, rows, lineups):
    step9_renderer = _FROZEN_STEP9_RENDERER(original, rows, lineups)

    def wrapped(results, status_info, team_logo, h):
        ordered = list(results or [])[:5]
        pks = [_i(r.get("game_pk")) for r in ordered]
        relevant_rows = {pk: rows.get(pk) for pk in pks if pk and rows.get(pk)}
        try:
            s6 = step6._build_context(relevant_rows)
        except Exception:
            s6 = {}
        try:
            s7 = step7._build_context(relevant_rows)
        except Exception:
            s7 = {}
        try:
            s8 = step8._build_context(relevant_rows)
        except Exception:
            s8 = {}
        try:
            s9 = prior._build_context(relevant_rows)
        except Exception:
            s9 = {}

        contexts: dict[int, dict[str, Any]] = {}
        for result in ordered:
            pk = _i(result.get("game_pk"))
            row = (relevant_rows.get(pk) or {}) if pk else {}
            if not pk:
                continue
            try:
                contexts[pk] = _compose(
                    result,
                    row,
                    step6_context=s6.get(pk) or {},
                    step7_context=s7.get(pk) or {},
                    step8_context=s8.get(pk) or {},
                    step9_context=s9.get(pk) or {},
                )
            except Exception as exc:
                contexts[pk] = {
                    "away_name": str(result.get("away_name") or "Away"),
                    "home_name": str(result.get("home_name") or "Home"),
                    "away": {},
                    "home": {},
                    "label": "GAME SCRIPT PENDING",
                    "label_cls": "limited",
                    "script_note": f"Step 10 synthesis unavailable: {type(exc).__name__}.",
                    "mode_score": "N/A",
                }

        cursor = {"i": 0}
        original_markdown = st.markdown

        def capture(body: Any, *args: Any, **kwargs: Any):
            text = str(body or "")
            if "ks-pick-card" in text and cursor["i"] < len(ordered):
                result = ordered[cursor["i"]]
                cursor["i"] += 1
                pk = _i(result.get("game_pk"))
                text = _inject(text, _html(contexts.get(pk) or {}))
            return original_markdown(text, *args, **kwargs)

        st.markdown = capture
        try:
            return step9_renderer(results, status_info, team_logo, h)
        finally:
            st.markdown = original_markdown

    return wrapped


def _render_pregame_with_step10(games_df, section_header, status_info, team_logo, h):
    original_renderer = pregame._renderer
    pregame._renderer = _renderer
    try:
        return pregame.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        pregame._renderer = original_renderer


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Preserve frozen Step 5L live mode while extending only pregame synthesis."""
    st.markdown(_STEP10_CSS, unsafe_allow_html=True)
    original_step9_pregame = prior._render_pregame_with_step9
    prior._render_pregame_with_step9 = _render_pregame_with_step10
    try:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior._render_pregame_with_step9 = original_step9_pregame


__all__ = [
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "HOME_RUN_MULTIPLIER",
    "MIN_DATA_SCORE",
    "MIN_SUPPORT_COMPONENTS",
    "MODEL_VERSION",
    "NB_DISPERSION",
    "RECENT_BLEND",
    "RUN_CEILING",
    "RUN_FLOOR",
    "_compose",
    "_nb_distribution",
    "_run_buckets",
    "_script",
    "_team_projection",
    "render_moneyline_hub",
]
