"""Kyre Sports AI — NFL Moneyline V3.6 Step-3E official game-plan policy repair.

Repairs the final Step-3 policy gap exposed after sentence-scoped attribution:
- standard news evidence remains limited to 96 hours before kickoff;
- official team-site, matchup-specific coach game-plan reports may remain valid up
  to 10 days before kickoff when no newer conflicting evidence exists;
- a VERIFIED Step-2 QB1 may be combined with an explicit official "starters will
  play" plan instead of requiring a redundant article sentence naming that QB;
- explicit workload language (snaps/series/quarter/half) can verify preseason
  rotation/workload intent when it comes from that official plan.

This does NOT relax secondary-source trust rules and does not enable sportsbook,
probability, Monte Carlo, ranking or recommendation logic. MLB/WNBA remain isolated.
"""
from __future__ import annotations

import re
from html import escape

import pandas as pd
import streamlit as st

import nfl_moneyline_hub_v35 as v35
import nfl_moneyline_hub_v34 as v34
import nfl_moneyline_hub_v33 as v33
import nfl_moneyline_hub_v3 as v3

MODEL_VERSION = "NFL MONEYLINE V3.6 • STEP 3E OFFICIAL PLAN POLICY"
OFFICIAL_PLAN_HOURS = 24 * 10
_WORKLOAD_PAT = re.compile(
    r"\b(?:\d+\s*(?:-|to)\s*\d+\s*snaps?|\d+\s*snaps?|snaps?|series|drives?|quarters?|halftime|first\s+half|half)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# 1) Extend discovery ONLY for official team sources. Secondary sources retain
#    the existing four-day discovery/freshness behavior.
# ---------------------------------------------------------------------------
_CURRENT_TRUSTED_ROWS = v33._trusted_news_rows


@st.cache_data(ttl=300, show_spinner=False)
def _trusted_news_rows(team_abbr: str, team_name: str, opponent_name: str, qb_names: tuple[str, ...]):
    rows = list(_CURRENT_TRUSTED_ROWS(team_abbr, team_name, opponent_name, qb_names) or [])

    queries = [
        f'"{team_name}" "{opponent_name}" preseason starters snaps when:10d',
        f'"{team_name}" "{opponent_name}" preseason coach starters play when:10d',
    ]

    extra = []
    for query in queries:
        xml_text, diag = v33._google_news_xml(query)
        if not diag.get("ok"):
            continue
        for row in v33._rss_rows(xml_text, team_abbr):
            if row.get("source_tier") != "OFFICIAL":
                continue
            row = dict(row)
            # Reuse V3.4's safe allow-listed full-text path for official articles.
            candidates = []
            direct = v34._derived_direct_url(row)
            if direct:
                candidates.append(direct)
            href = str(row.get("href") or "").strip()
            if href:
                candidates.append(href)

            full_text = ""
            resolved = ""
            for candidate in candidates:
                full_text, resolved = v34._publisher_full_text(candidate, str(row.get("source_url") or ""))
                if full_text:
                    break
            row["resolved_url"] = resolved
            row["full_text_used"] = bool(full_text)
            if full_text:
                row["description"] = f"{str(row.get('description') or '').strip()} {full_text}".strip()[:50000]
            row["source"] = str(row.get("source") or "TRUSTED NEWS") + " • OFFICIAL EXTENDED"
            extra.append(row)

    # Headline/source dedupe. Keep existing current-window rows first.
    seen = set()
    out = []
    for row in rows + extra:
        key = (
            re.sub(r"\W+", " ", str(row.get("headline") or "").lower()).strip(),
            str(row.get("source_url") or "").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out[:30]


v33._trusted_news_rows = _trusted_news_rows


# ---------------------------------------------------------------------------
# 2) Keep 96h standard freshness, but allow explicit OFFICIAL matchup plans up
#    to 10 days. No Tier-A/Tier-B extension.
# ---------------------------------------------------------------------------
_ORIGINAL_SCOPED_CLASSIFIER = v35._scoped_classify_article


def _policy_classify_article(article: dict, ctx: dict, opponent_name: str, kickoff):
    item = _ORIGINAL_SCOPED_CLASSIFIER(article, ctx, opponent_name, kickoff)
    item["freshness_policy"] = "STANDARD 96H"

    if item.get("fresh") or article.get("source_tier") != "OFFICIAL":
        return item

    published = item.get("published")
    if pd.isna(published) or pd.isna(kickoff):
        return item

    hours_before = (kickoff - published).total_seconds() / 3600.0
    explicit_signal = bool(
        item.get("general_starters")
        or item.get("start")
        or item.get("play")
        or item.get("rest")
        or item.get("rotation")
        or _WORKLOAD_PAT.search(str(article.get("description") or ""))
    )

    if 0 <= hours_before <= OFFICIAL_PLAN_HOURS and item.get("contextual") and explicit_signal:
        item["fresh"] = True
        item["hours_before"] = hours_before
        explicit_qb = bool(item.get("mentions") and any(item.get(k) for k in ("start", "play", "rest", "rotation")))
        item["qualifying"] = bool(item.get("contextual") and (explicit_qb or item.get("general_starters")))
        item["freshness_policy"] = "OFFICIAL MATCHUP PLAN ≤10D"
        labels = list(item.get("labels") or [])
        if "OFFICIAL PLAN" not in labels:
            labels.append("OFFICIAL PLAN")
        item["labels"] = labels
    return item


# V3.5's context calls its module-global classifier directly; diagnostics call
# v3._classify_article. Patch both so they agree.
v35._scoped_classify_article = _policy_classify_article
v3._classify_article = _policy_classify_article


# ---------------------------------------------------------------------------
# 3) Verified evidence composition:
#    VERIFIED QB1 + OFFICIAL "starters will play" plan is a valid starter identity
#    bridge. This is not a guess; both components are independently verified.
# ---------------------------------------------------------------------------
_ORIGINAL_CONTEXT = v35._team_gameplan_context


def _official_general_plan(evidence: list[dict]):
    return [
        x for x in evidence
        if x.get("source_tier") == "OFFICIAL"
        and x.get("general_starters")
        and x.get("fresh")
        and x.get("contextual")
    ]


def _team_gameplan_context(ctx: dict, opponent_name: str, game_id: str, kickoff):
    result = _ORIGINAL_CONTEXT(ctx, opponent_name, game_id, kickoff)
    evidence = list(result.get("evidence") or [])
    plans = _official_general_plan(evidence)

    qbs = list(ctx.get("qbs") or [])
    qb1 = v3._safe((qbs[0] if qbs else {}).get("name"))
    depth_verified = str(ctx.get("depth_state") or "").upper() == "VERIFIED"

    starter_identity_ready = bool(result.get("starter_verified"))
    starter_identity_name = v3._safe(result.get("starter_name"))
    starter_identity_basis = "EXPLICIT NEWS" if starter_identity_ready else ""

    if not starter_identity_ready and depth_verified and qb1 and plans:
        starter_identity_ready = True
        starter_identity_name = qb1
        starter_identity_basis = "VERIFIED QB1 + OFFICIAL STARTERS PLAN"

    participation_ready = bool(result.get("participation_verified"))
    if not participation_ready and plans:
        # general_starters in the scoped classifier only becomes true when the
        # sentence also contains explicit PLAY/REST language.
        participation_ready = True

    rotation_ready = bool(result.get("rotation_verified"))
    workload_plan = False
    for item in plans:
        text = f"{item.get('headline', '')} {item.get('description', '')}"
        if _WORKLOAD_PAT.search(text):
            workload_plan = True
            break
    if workload_plan:
        rotation_ready = True

    conflicts = list(result.get("conflicts") or [])
    ready = bool(starter_identity_ready and participation_ready and rotation_ready and not conflicts)

    result["starter_identity_ready"] = starter_identity_ready
    result["starter_identity_name"] = starter_identity_name
    result["starter_identity_basis"] = starter_identity_basis
    result["participation_verified"] = participation_ready
    result["rotation_verified"] = rotation_ready
    result["official_plan_count"] = len(plans)
    result["official_workload_plan"] = workload_plan
    result["ready"] = ready
    return result


v3._team_gameplan_context = _team_gameplan_context


# ---------------------------------------------------------------------------
# 4) Make the per-team UI honest about explicit vs composed starter identity and
#    keep V3.4 diagnostics visible.
# ---------------------------------------------------------------------------
def _render_gameplan_team(gp: dict):
    team = v3._safe(gp.get("team"), gp.get("abbr"))
    st.markdown(f"#### {escape(team)}")
    c1, c2, c3, c4 = st.columns(4)
    starter_display = (
        gp.get("starter_name") if gp.get("starter_verified")
        else gp.get("starter_identity_name") if gp.get("starter_identity_ready")
        else "UNKNOWN"
    )
    c1.metric("Starter identity", starter_display)
    c2.metric("QB participation", "VERIFIED" if gp.get("participation_verified") else "UNKNOWN")
    c3.metric("Rotation/workload", "VERIFIED" if gp.get("rotation_verified") else "UNKNOWN")
    c4.metric("Conflicts", len(gp.get("conflicts", [])))

    basis = str(gp.get("starter_identity_basis") or "")
    if basis:
        st.caption(f"Starter basis: {basis}")

    if gp.get("ready"):
        st.success("✅ GAME-PLAN GATE PASSED • starter identity + participation + workload/rotation verified with no conflict.")
    else:
        st.warning("🔒 GAME-PLAN GATE LOCKED • starter identity/participation/workload evidence is incomplete or conflicting.")

    if gp.get("conflicts"):
        st.error("Conflicting evidence: " + " • ".join(gp.get("conflicts", [])))

    table = v3._evidence_table(gp)
    with st.expander(
        f"📰 {team} game-plan evidence • {len(gp.get('evidence', []))} qualifying / {gp.get('articles_scanned', 0)} scanned",
        expanded=False,
    ):
        if table.empty:
            st.info("No qualifying explicit game-plan report was found. UNKNOWN is preserved instead of assuming playing time.")
        else:
            st.dataframe(table, use_container_width=True, hide_index=True)
            links = []
            for item in gp.get("evidence", [])[:5]:
                if item.get("href") and item.get("headline"):
                    links.append(f"- [{item['headline']}]({item['href']})")
            if links:
                st.markdown("\n".join(links))

    diagnostics = gp.get("diagnostics", []) or []
    with st.expander(f"🔎 Why articles passed/failed • {len(diagnostics)} checked", expanded=False):
        if diagnostics:
            st.dataframe(pd.DataFrame(diagnostics), use_container_width=True, hide_index=True)
            st.caption("Full text = YES means article-body text was inspected. Official matchup plans may remain valid up to 10 days; all other evidence stays on the 96-hour rule.")
        else:
            st.info("No diagnostic rows were available for this team.")
    st.divider()


v3._render_gameplan_team = _render_gameplan_team


def render_nfl_moneyline_hub():
    # Rewrite the legacy caption only for this render so the UI reflects the
    # exact tiered freshness policy.
    real_caption = st.caption

    def _caption(body, *args, **kwargs):
        if isinstance(body, str) and "Evidence window: final 96 hours" in body:
            body = body.replace(
                "Evidence window: final 96 hours before scheduled kickoff",
                "Evidence window: 96h standard • official matchup-specific coach plans valid up to 10d when uncontradicted",
            )
        return real_caption(body, *args, **kwargs)

    st.caption = _caption
    try:
        return v35.render_nfl_moneyline_hub()
    finally:
        st.caption = real_caption


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
