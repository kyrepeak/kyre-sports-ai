"""Kyre Sports AI — NFL Moneyline V3.2 Step-3 news scanner repair.

Preserves V3/V3.1 Step-3 logic and guardrails, but repairs the evidence intake:
- use ESPN's documented league-news team filter first: /news?team={TEAM_ID};
- do not treat HTTP 200 with zero usable article objects as a successful feed;
- fall back to /teams/{TEAM_ID}/news only when it actually contains articles;
- accept ESPN article containers named articles/news/headlines/items;
- preserve UNKNOWN/LOCKED when no explicit fresh game-plan evidence exists.

No sportsbook, probability, Monte Carlo, ranking or recommendation logic is added.
"""
from __future__ import annotations

import streamlit as st

# Import V3.1 first so its Step-1 -> Step-2 compatibility patch is applied.
import nfl_moneyline_hub_v31 as compat  # noqa: F401
import nfl_moneyline_hub_v3 as v3

MODEL_VERSION = "NFL MONEYLINE V3.2 • STEP 3 ESPN NEWS SCANNER REPAIR"


def _candidate_article_count(payload: dict) -> int:
    """Count only objects that look like ESPN news articles."""
    count = 0
    if not isinstance(payload, dict):
        return 0
    for key in ("articles", "news", "headlines", "items"):
        value = payload.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            if any(v3._safe(item.get(field)) for field in ("headline", "title", "description", "story", "summary")):
                count += 1
    return count


@st.cache_data(ttl=300, show_spinner=False)
def _team_news_payload(team_id: str):
    """Return a team-news payload only when it contains usable article objects."""
    team_id = v3._safe(team_id)
    if not team_id:
        return {}, {"ok": False, "http": None, "error": "missing team id", "route": "NONE", "article_candidates": 0}

    attempts = [
        ("ESPN TEAM FILTER", f"{v3.ESPN_BASE}/news?team={team_id}"),
        ("ESPN TEAM PATH", f"{v3.ESPN_BASE}/teams/{team_id}/news?limit=30"),
    ]
    last_diag = {"ok": False, "http": None, "error": "no team-news route attempted"}

    for route, url in attempts:
        payload, diag = v3._json_get(url)
        candidates = _candidate_article_count(payload) if diag.get("ok") else 0
        diag = dict(diag)
        diag["route"] = route
        diag["article_candidates"] = int(candidates)
        last_diag = diag
        if diag.get("ok") and candidates > 0:
            # Harmless metadata used only to make the selected provider route visible
            # in article source labels. Existing ESPN fields are untouched.
            payload = dict(payload)
            payload["__kyre_news_route"] = route
            return payload, diag

    # Fail closed: an HTTP-200 empty payload is not considered a usable news feed.
    last_diag = dict(last_diag)
    last_diag["ok"] = False
    if not last_diag.get("error"):
        last_diag["error"] = "ESPN team-news routes returned zero usable article objects"
    return {}, last_diag


def _article_rows(payload: dict, source_label: str):
    """Normalize ESPN news containers while avoiding non-news summary objects."""
    candidates = []
    if not isinstance(payload, dict):
        return []

    for key in ("articles", "news", "headlines", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(value)

    route = v3._safe(payload.get("__kyre_news_route"))
    label = source_label + (f" • {route}" if route else "")
    out, seen = [], set()

    for article in candidates:
        if not isinstance(article, dict):
            continue
        headline = v3._safe(article.get("headline") or article.get("title"))
        description = v3._safe(article.get("description") or article.get("story") or article.get("summary"))
        # This is deliberately strict so generic 'items' arrays from game-summary
        # payloads never become fake news articles.
        if not headline and not description:
            continue
        href = v3._href(article)
        key = href or (headline.lower(), description[:80].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "headline": headline,
            "description": description,
            "href": href,
            "published": v3._published(article),
            "source": label,
        })
    return out


# Patch only the Step-3 evidence intake. Classification, freshness, conflict,
# starter/participation/rotation and model-lock rules remain exactly V3.
v3._team_news_payload = _team_news_payload
v3._article_rows = _article_rows


def render_nfl_moneyline_hub():
    return v3.render_nfl_moneyline_hub()


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
