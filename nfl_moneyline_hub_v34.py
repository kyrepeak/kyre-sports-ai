"""Kyre Sports AI — NFL Moneyline V3.4 Step-3C full-text evidence repair.

Preserves the verified Step 1 / Step 2.1 / Step 3.3 guardrails while repairing
an evidence-depth gap: discovery could find current articles, but classification
used only headline/RSS/ESPN summary text. V3.4 enriches trusted evidence with
full article text when it can be retrieved safely and exposes rejection reasons
for every scanned item.

No sportsbook price, win probability, Monte Carlo, ranking or recommendation
logic is added. MLB/WNBA remain isolated and untouched.
"""
from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st

import nfl_moneyline_hub_v33 as v33
import nfl_moneyline_hub_v3 as v3

MODEL_VERSION = "NFL MONEYLINE V3.4 • STEP 3C FULL-TEXT + DIAGNOSTICS"
ESPN_ARTICLE_API = "https://now.core.api.espn.com/v1/sports/news"
GOOGLE_HOSTS = {"news.google.com", "google.com", "www.google.com"}


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _host(url: str) -> str:
    try:
        return (urlparse(str(url or "")).hostname or "").lower().lstrip("www.")
    except Exception:
        return ""


def _strip_tags(text: str) -> str:
    text = html.unescape(str(text or ""))
    text = re.sub(r"(?is)<script\b.*?</script>", " ", text)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _recursive_article_text(obj) -> list[str]:
    """Collect likely article-body fields from a JSON object without nav noise."""
    wanted = {"articlebody", "story", "body", "content", "description", "summary", "headline", "title"}
    out: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in wanted and isinstance(value, str):
                clean = _strip_tags(value)
                if len(clean) >= 25:
                    out.append(clean)
            elif isinstance(value, (dict, list)):
                out.extend(_recursive_article_text(value))
    elif isinstance(obj, list):
        for value in obj:
            out.extend(_recursive_article_text(value))
    return out


@st.cache_data(ttl=900, show_spinner=False)
def _espn_article_detail(article_id: str) -> str:
    article_id = _safe(article_id)
    if not article_id:
        return ""
    try:
        r = requests.get(f"{ESPN_ARTICLE_API}/{article_id}", headers=v3.HEADERS, timeout=8)
        r.raise_for_status()
        parts = _recursive_article_text(r.json())
        return " ".join(dict.fromkeys(parts))[:50000]
    except Exception:
        return ""


class _VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag.lower())

    def handle_endtag(self, tag):
        tag = tag.lower()
        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx] == tag:
                del self.stack[idx:]
                break

    def handle_data(self, data):
        if any(x in {"script", "style", "nav", "footer", "header", "aside"} for x in self.stack):
            return
        text = re.sub(r"\s+", " ", str(data or "")).strip()
        if len(text) >= 2:
            self.parts.append(text)


def _jsonld_article_text(raw_html: str) -> str:
    pieces: list[str] = []
    for match in re.finditer(
        r"(?is)<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        raw_html or "",
    ):
        raw = html.unescape(match.group(1)).strip()
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        pieces.extend(_recursive_article_text(payload))
    return " ".join(dict.fromkeys(pieces))[:50000]


def _article_element_text(raw_html: str) -> str:
    match = re.search(r"(?is)<article\b[^>]*>(.*?)</article>", raw_html or "")
    if match:
        return _strip_tags(match.group(1))[:50000]
    parser = _VisibleTextParser()
    try:
        parser.feed(raw_html or "")
    except Exception:
        return ""
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()[:50000]


def _slug(text: str) -> str:
    text = re.sub(r"\s+-\s+VSiN\s*$", "", _safe(text), flags=re.I)
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text


def _derived_direct_url(article: dict) -> str:
    """Derive publisher URL only for sources with stable title->slug routes."""
    source_url = _safe(article.get("source_url"))
    host = _host(source_url)
    title = _safe(article.get("headline"))
    slug = _slug(title)
    if not host or not slug:
        return ""
    if host == "vsin.com" or host.endswith(".vsin.com"):
        return f"https://vsin.com/nfl/{slug}/"
    official_domains = set(v33.OFFICIAL_TEAM_DOMAINS.values())
    if any(host == d or host.endswith("." + d) for d in official_domains):
        return f"https://www.{host}/news/{slug}"
    return ""


def _trusted_source_allowed(url: str, source_url: str = "") -> bool:
    host = _host(url)
    source_host = _host(source_url)
    if not host:
        return False
    allowed = set(v33.OFFICIAL_TEAM_DOMAINS.values()) | set(v33.TIER_A_DOMAINS) | set(v33.TIER_B_DOMAINS)
    return any(host == d or host.endswith("." + d) for d in allowed) or (
        source_host and host == source_host
    )


@st.cache_data(ttl=900, show_spinner=False)
def _publisher_full_text(url: str, source_url: str = "") -> tuple[str, str]:
    """Fetch full text only when redirects land on an allow-listed publisher."""
    if not _safe(url):
        return "", ""
    try:
        r = requests.get(url, headers=v3.HEADERS, timeout=8, allow_redirects=True)
        r.raise_for_status()
        final_url = str(r.url or url)
        if _host(final_url) in GOOGLE_HOSTS or not _trusted_source_allowed(final_url, source_url):
            return "", final_url
        raw = r.text or ""
        text = _jsonld_article_text(raw) or _article_element_text(raw)
        return text[:50000], final_url
    except Exception:
        return "", ""


# Preserve the V3.2 normalizer but enrich ESPN rows with article IDs/full detail.
_ORIGINAL_ARTICLE_ROWS = v3._article_rows


def _article_rows(payload: dict, source_label: str):
    rows = _ORIGINAL_ARTICLE_ROWS(payload, source_label)
    raw_items = []
    if isinstance(payload, dict):
        for key in ("articles", "news", "headlines", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                raw_items.extend(x for x in value if isinstance(x, dict))

    by_headline = {}
    for item in raw_items:
        headline = _safe(item.get("headline") or item.get("title")).lower()
        if headline:
            by_headline[headline] = item

    enriched = []
    for row in rows:
        item = by_headline.get(_safe(row.get("headline")).lower(), {})
        article_id = _safe(item.get("id") or item.get("articleId") or item.get("newsId"))
        full = _espn_article_detail(article_id) if article_id else ""
        row = dict(row)
        row["article_id"] = article_id
        row["full_text_used"] = bool(full)
        if full:
            row["description"] = f"{_safe(row.get('description'))} {full}".strip()[:50000]
        enriched.append(row)
    return enriched


v3._article_rows = _article_rows


_ORIGINAL_TRUSTED_ROWS = v33._trusted_news_rows


@st.cache_data(ttl=900, show_spinner=False)
def _trusted_news_rows(team_abbr: str, team_name: str, opponent_name: str, qb_names: tuple[str, ...]):
    rows = _ORIGINAL_TRUSTED_ROWS(team_abbr, team_name, opponent_name, qb_names)
    out = []
    for row in rows:
        row = dict(row)
        candidates = []
        direct = _derived_direct_url(row)
        if direct:
            candidates.append(direct)
        href = _safe(row.get("href"))
        if href:
            candidates.append(href)

        full_text = ""
        resolved = ""
        for candidate in candidates:
            full_text, resolved = _publisher_full_text(candidate, _safe(row.get("source_url")))
            if full_text:
                break
        row["resolved_url"] = resolved
        row["full_text_used"] = bool(full_text)
        if full_text:
            row["description"] = f"{_safe(row.get('description'))} {full_text}".strip()[:50000]
        out.append(row)
    return out


v33._trusted_news_rows = _trusted_news_rows


_ORIGINAL_CONTEXT = v33._team_gameplan_context


def _rejection_reason(article: dict, classified: dict) -> str:
    if classified.get("qualifying"):
        return "QUALIFIED"
    if not classified.get("fresh"):
        return "OUTSIDE 96H WINDOW"
    if not classified.get("contextual"):
        return "NO MATCHUP/PRESEASON CONTEXT"
    if not classified.get("mentions") and not classified.get("general_starters"):
        return "NO VERIFIED QB/STARTER SIGNAL"
    if not any(classified.get(x) for x in ("start", "play", "rest", "rotation", "general_starters")):
        return "VAGUE — NO EXPLICIT PLAN LANGUAGE"
    if article.get("source_tier") == "TIER B" and not v33._supplemental_qualifying(article, classified):
        text = f"{article.get('headline', '')}. {article.get('description', '')}"
        if not v33.ATTRIBUTION_PAT.search(text):
            return "TIER B — NO ATTRIBUTION"
        if v33.SPECULATION_PAT.search(text):
            return "TIER B — SPECULATIVE"
        return "TIER B — TRUST GUARD"
    return "INCOMPLETE EXPLICIT EVIDENCE"


def _diagnostic_rows(ctx: dict, opponent_name: str, game_id: str, kickoff):
    team_id = _safe(ctx.get("team_id"))
    team_payload, _ = v3._team_news_payload(team_id) if team_id else ({}, {})
    summary_payload, _ = v3._game_summary_payload(game_id)
    articles = v3._article_rows(team_payload, "ESPN TEAM NEWS")
    articles.extend(v3._article_rows(summary_payload, "ESPN GAME SUMMARY"))
    qb_names = tuple(_safe(qb.get("name")) for qb in (ctx.get("qbs", []) or []) if _safe(qb.get("name")))
    articles.extend(_trusted_news_rows(_safe(ctx.get("abbr")).upper(), _safe(ctx.get("team"), ctx.get("abbr")), opponent_name, qb_names))

    deduped, seen = [], set()
    for article in articles:
        key = re.sub(r"\W+", " ", _safe(article.get("headline")).lower()).strip() or _safe(article.get("href")).lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(article)

    rows = []
    for article in deduped:
        classified = v3._classify_article(article, ctx, opponent_name, kickoff)
        if article.get("source_tier"):
            classified["qualifying"] = v33._supplemental_qualifying(article, classified)
        published = classified.get("published")
        rows.append({
            "Result": "✅ QUALIFIED" if classified.get("qualifying") else "❌ " + _rejection_reason(article, classified),
            "Published ET": "—" if pd.isna(published) else published.strftime("%m/%d %I:%M %p"),
            "Source": _safe(article.get("source"), "—")[:42],
            "QB": ", ".join(classified.get("mentions", [])) or "—",
            "Signals": "/".join(x for x, ok in [
                ("START", classified.get("start")), ("PLAY", classified.get("play")),
                ("REST", classified.get("rest")), ("ROT", classified.get("rotation")),
                ("STARTERS", classified.get("general_starters")),
            ] if ok) or "—",
            "Full text": "YES" if article.get("full_text_used") else "NO",
            "Headline": _safe(article.get("headline"), "—")[:120],
        })
    return rows


def _team_gameplan_context(ctx: dict, opponent_name: str, game_id: str, kickoff):
    result = _ORIGINAL_CONTEXT(ctx, opponent_name, game_id, kickoff)
    try:
        result["diagnostics"] = _diagnostic_rows(ctx, opponent_name, game_id, kickoff)
    except Exception:
        result["diagnostics"] = []
    return result


v3._team_gameplan_context = _team_gameplan_context


_ORIGINAL_RENDER_TEAM = v3._render_gameplan_team


def _render_gameplan_team(gp: dict):
    _ORIGINAL_RENDER_TEAM(gp)
    diagnostics = gp.get("diagnostics", []) or []
    with st.expander(f"🔎 Why articles passed/failed • {len(diagnostics)} checked", expanded=False):
        if not diagnostics:
            st.info("No diagnostic rows were available for this team.")
        else:
            st.dataframe(pd.DataFrame(diagnostics), use_container_width=True, hide_index=True)
            st.caption("Full text = YES means the classifier inspected publisher/ESPN article body text, not only the headline/RSS summary.")


v3._render_gameplan_team = _render_gameplan_team


def render_nfl_moneyline_hub():
    return v33.render_nfl_moneyline_hub()


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
