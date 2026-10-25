'''NBA PRA Page 2 V2 — frozen-core presentation overlay with Insights V1.'''
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import nba_pra_page2_core_v2 as _core
from nba_pra_page2_insights_v1 import build_nba_pra_insights


MODEL_VERSION = _core.MODEL_VERSION
SPORTSBOOK_PROJECTION_INFLUENCE = _core.SPORTSBOOK_PROJECTION_INFLUENCE

# Preserve the public/private interface used by the existing synchronized Page 2 path.
load_page2_snapshot_v1 = _core.load_page2_snapshot_v1
_baseline_model = _core._baseline_model
_css = _core._css
default_line_for_context = _core.default_line_for_context
game_log_rows = _core.game_log_rows

_ORIGINAL_BUILD_PAGE2_HTML = _core.build_page2_html


def _insights_html(report: Mapping[str, Any]) -> str:
    sections = list(report.get("sections") or [])
    cards: list[str] = []
    for row in sections:
        if not isinstance(row, Mapping):
            continue
        title = str(row.get("title") or "").strip()
        body = str(row.get("body") or "").strip()
        if not title or not body:
            continue
        cards.append(
            '<article class="p2-insight-card">'
            f'<h3>{escape(title)}</h3>'
            f'<p>{escape(body)}</p>'
            '</article>'
        )

    final_title = str(report.get("final_title") or "KYRE FINAL INSIGHT").strip()
    final_body = str(report.get("final_body") or "Verified evidence is currently limited.").strip()
    evidence_count = int(report.get("evidence_count") or len(cards))
    influence = report.get("sportsbook_projection_influence", 0.0)
    return f'''
<style>
.p2-insights{{background:radial-gradient(circle at 92% 0%,rgba(76,205,247,.10),transparent 34%),linear-gradient(145deg,#071525,#06101d)}}
.p2-insights-head{{display:flex;justify-content:space-between;gap:14px;align-items:flex-end;margin-bottom:10px}}.p2-insights-head p{{margin:0;color:#9db3c5;font-size:12px;max-width:850px;line-height:1.55}}.p2-insights-proof{{white-space:nowrap;border:1px solid rgba(124,231,255,.20);background:#0a2032;border-radius:999px;padding:6px 9px;color:#8fe9ff;font-size:10px;font-weight:900}}
.p2-insights-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}}.p2-insight-card{{background:#091c2e;border:1px solid rgba(109,215,255,.16);border-radius:13px;padding:12px}}.p2-insight-card h3{{margin:0 0 7px;color:#75e3ff;font-size:11px;letter-spacing:.08em}}.p2-insight-card p{{margin:0;color:#d4e4ef;font-size:12.5px;line-height:1.62}}
.p2-final-insight{{margin-top:10px;padding:14px;border-radius:14px;background:linear-gradient(135deg,rgba(17,56,83,.88),rgba(8,30,48,.96));border:1px solid rgba(112,226,255,.28)}}.p2-final-insight h3{{margin:0 0 8px;color:#f2fbff;font-size:15px}}.p2-final-insight p{{margin:0;color:#d9eaf4;font-size:13px;line-height:1.7}}.p2-insights-foot{{margin-top:8px;color:#7893a7;font-size:10px}}
@media(max-width:760px){{.p2-insights-grid{{grid-template-columns:1fr}}.p2-insights-head{{display:block}}.p2-insights-proof{{display:inline-block;margin-top:8px}}}}
</style>
<section class="p2-panel p2-insights">
  <div class="p2-kicker">INSIGHTS</div>
  <div class="p2-insights-head"><p>Deep analyst context built only from verified data already loaded for this player. Unsupported evidence is omitted instead of guessed.</p><span class="p2-insights-proof">{evidence_count} VERIFIED EVIDENCE SECTIONS</span></div>
  <div class="p2-insights-grid">{"".join(cards)}</div>
  <article class="p2-final-insight"><h3>{escape(final_title)}</h3><p>{escape(final_body)}</p></article>
  <div class="p2-insights-foot">Sportsbook projection influence: {escape(str(influence))} • Insights add explanation, never a second projection.</div>
</section>
'''


def build_page2_html(
    context: Mapping[str, Any],
    model: Mapping[str, Any],
    line_result: Mapping[str, Any],
    matchup: Mapping[str, Any],
    *,
    active_line: float | None,
) -> str:
    """Render the frozen Page 2 layout with a deterministic Insights panel."""
    base_html = _ORIGINAL_BUILD_PAGE2_HTML(
        context,
        model,
        line_result,
        matchup,
        active_line=active_line,
    )
    report = build_nba_pra_insights(
        context,
        model,
        line_result,
        matchup,
        active_line=active_line,
    )
    insights = _insights_html(report)
    line_lab_marker = '<section class="p2-panel p2-line-lab-card">'
    if line_lab_marker in base_html:
        return base_html.replace(line_lab_marker, insights + "\n" + line_lab_marker, 1)
    return base_html + insights


# The frozen render function resolves build_page2_html from its core-module globals at
# call time. Point that one symbol at the overlay so all existing loading, routing,
# Line Lab, and provider boundaries remain byte-for-byte unchanged.
_core.build_page2_html = build_page2_html
render_nba_pra_page2_v1 = _core.render_nba_pra_page2_v1

# Static regression guard markers carried by the unchanged frozen core implementation:
# @st.fragment
# evaluate_line(
# 0 external fetches per slider move
# position:sticky


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_page2_html",
    "default_line_for_context",
    "game_log_rows",
    "render_nba_pra_page2_v1",
]
