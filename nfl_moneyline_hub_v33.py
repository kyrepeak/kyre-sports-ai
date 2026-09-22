"""Kyre Sports AI — NFL Moneyline V3.3 Step-3B trusted game-plan discovery.

Preserves Step 1, Step 2.1 and Step 3.2 guardrails. Repairs the remaining Step-3
coverage gap revealed by a healthy ESPN scanner that returned real articles but
no explicit game-plan evidence.

Adds a second, cached discovery layer through Google News RSS, but only keeps
articles from an allow-list of official / high-trust NFL reporting sources.
Speculative secondary-source wording is display-only and cannot unlock the
preseason game-plan gate. The existing explicit starter + participation + rotation
+ no-conflict requirement remains unchanged.

No sportsbook, probability, Monte Carlo, ranking or recommendation logic is added.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ETREE
from urllib.parse import quote_plus, urlparse

import pandas as pd
import requests
import streamlit as st

# Apply V3.1 helper repair + V3.2 ESPN scanner repair before patching V3 context.
import nfl_moneyline_hub_v32 as scanfix  # noqa: F401
import nfl_moneyline_hub_v3 as v3

MODEL_VERSION = "NFL MONEYLINE V3.3 • STEP 3B TRUSTED NEWS DISCOVERY"

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"

# Official team sites. These are eligible as primary evidence when an item is
# fresh, matchup-contextual and passes the same explicit V3 language tests.
OFFICIAL_TEAM_DOMAINS = {
    "ARI": "azcardinals.com", "ATL": "atlantafalcons.com", "BAL": "baltimoreravens.com",
    "BUF": "buffalobills.com", "CAR": "panthers.com", "CHI": "chicagobears.com",
    "CIN": "bengals.com", "CLE": "clevelandbrowns.com", "DAL": "dallascowboys.com",
    "DEN": "denverbroncos.com", "DET": "detroitlions.com", "GB": "packers.com",
    "HOU": "houstontexans.com", "IND": "colts.com", "JAX": "jaguars.com",
    "KC": "chiefs.com", "LV": "raiders.com", "LAC": "chargers.com",
    "LAR": "therams.com", "MIA": "miamidolphins.com", "MIN": "vikings.com",
    "NE": "patriots.com", "NO": "neworleanssaints.com", "NYG": "giants.com",
    "NYJ": "newyorkjets.com", "PHI": "philadelphiaeagles.com", "PIT": "steelers.com",
    "SF": "49ers.com", "SEA": "seahawks.com", "TB": "buccaneers.com",
    "TEN": "tennesseetitans.com", "WSH": "commanders.com",
}

# Tier A can unlock when the existing V3 explicit-language rules pass.
TIER_A_DOMAINS = {
    "nfl.com", "espn.com", "apnews.com", "cbssports.com", "rotowire.com",
    "seattletimes.com", "tennessean.com",
}

# Tier B is useful, but requires explicit attribution and is rejected when the
# wording is merely prediction/guessing. This keeps betting/editorial expectation
# from being promoted into verified coach intent.
TIER_B_DOMAINS = {
    "vsin.com", "nbcsports.com", "profootballtalk.nbcsports.com", "foxsports.com",
    "sports.yahoo.com", "si.com", "spokesman.com", "fieldgulls.com",
    "musiccitymiracles.com", "usatoday.com",
}

ATTRIBUTION_PAT = re.compile(r"\b(said|says|announced|confirmed|told|stated|according to|plans? to|will use|is using)\b", re.I)
SPECULATION_PAT = re.compile(r"\b(i would|i'd|we would|guess|maybe|perhaps|might|likely|i expect|we expect|prediction)\b", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(value) -> str:
    text = html.unescape(str(value or ""))
    text = TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _domain(value: str) -> str:
    try:
        host = (urlparse(str(value or "")).hostname or "").lower()
    except Exception:
        host = ""
    return host[4:] if host.startswith("www.") else host


def _domain_matches(host: str, domain: str) -> bool:
    host = _domain(host) if "://" in str(host) else str(host or "").lower().lstrip("www.")
    domain = str(domain or "").lower().lstrip("www.")
    return bool(host and domain and (host == domain or host.endswith("." + domain)))


def _source_tier(team_abbr: str, source_url: str) -> str:
    host = _domain(source_url)
    official = OFFICIAL_TEAM_DOMAINS.get(v3._safe(team_abbr).upper(), "")
    if official and _domain_matches(host, official):
        return "OFFICIAL"
    if any(_domain_matches(host, d) for d in TIER_A_DOMAINS):
        return "TIER A"
    if any(_domain_matches(host, d) for d in TIER_B_DOMAINS):
        return "TIER B"
    return "REJECT"


@st.cache_data(ttl=300, show_spinner=False)
def _google_news_xml(query: str):
    url = (
        f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}"
        "&hl=en-US&gl=US&ceid=US:en"
    )
    diag = {"ok": False, "http": None, "error": "", "url": url}
    try:
        response = requests.get(url, headers=v3.HEADERS, timeout=8)
        diag["http"] = int(response.status_code)
        response.raise_for_status()
        diag["ok"] = True
        return response.text, diag
    except Exception as exc:
        diag["error"] = str(exc)[:220]
        return "", diag


def _rss_rows(xml_text: str, team_abbr: str):
    if not xml_text:
        return []
    try:
        root = ETREE.fromstring(xml_text)
    except Exception:
        return []

    rows = []
    for item in root.findall(".//item")[:30]:
        title = _clean_html(item.findtext("title"))
        description = _clean_html(item.findtext("description"))
        link = v3._safe(item.findtext("link"))
        pub_raw = v3._safe(item.findtext("pubDate"))
        source_node = item.find("source")
        publisher = _clean_html(source_node.text if source_node is not None else "")
        source_url = v3._safe(source_node.attrib.get("url")) if source_node is not None else ""
        tier = _source_tier(team_abbr, source_url)
        if tier == "REJECT":
            continue
        try:
            published = pd.to_datetime(pub_raw, utc=True).tz_convert(v3.ET) if pub_raw else pd.NaT
        except Exception:
            published = pd.NaT
        if not title and not description:
            continue
        rows.append({
            "headline": title,
            "description": description,
            "href": link,
            "published": published,
            "source": f"TRUSTED NEWS • {publisher or _domain(source_url) or tier}",
            "source_tier": tier,
            "source_url": source_url,
        })
    return rows


@st.cache_data(ttl=300, show_spinner=False)
def _trusted_news_rows(team_abbr: str, team_name: str, opponent_name: str, qb_names: tuple[str, ...]):
    # Query 1 centers the exact matchup. Query 2 centers named QBs so coach/rotation
    # stories that omit the opponent in the headline can still be discovered.
    queries = [
        f'"{team_name}" "{opponent_name}" preseason quarterback starters rotation when:4d',
    ]
    if qb_names:
        qbs = " OR ".join(f'"{name}"' for name in qb_names[:4])
        queries.append(f'"{team_name}" preseason ({qbs}) starters rotation when:4d')

    out, seen = [], set()
    for query in queries:
        xml_text, diag = _google_news_xml(query)
        if not diag.get("ok"):
            continue
        for row in _rss_rows(xml_text, team_abbr):
            key = (row.get("headline", "").lower(), row.get("source_url", "").lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
    return out[:24]


def _supplemental_qualifying(article: dict, classified: dict) -> bool:
    """Apply trust/anti-speculation guard on top of V3's existing classifier."""
    if not classified.get("qualifying"):
        return False
    tier = article.get("source_tier")
    if tier in {None, "", "OFFICIAL", "TIER A"}:
        return True

    text = f"{article.get('headline', '')}. {article.get('description', '')}"
    # Tier B must contain explicit attribution. Speculative wording is rejected
    # unless the same item also clearly attributes the information to a speaker.
    attributed = bool(ATTRIBUTION_PAT.search(text))
    speculative = bool(SPECULATION_PAT.search(text))
    if not attributed:
        return False
    if speculative and not re.search(r"\b(said|announced|confirmed|told|stated)\b", text, flags=re.I):
        return False
    return True


def _team_gameplan_context(ctx: dict, opponent_name: str, game_id: str, kickoff):
    team_id = v3._safe(ctx.get("team_id"))
    team_payload, tdiag = v3._team_news_payload(team_id) if team_id else ({}, {"ok": False, "http": None, "error": "missing team id"})
    summary_payload, sdiag = v3._game_summary_payload(game_id)

    articles = v3._article_rows(team_payload, "ESPN TEAM NEWS")
    articles.extend(v3._article_rows(summary_payload, "ESPN GAME SUMMARY"))

    qb_names = tuple(v3._safe(qb.get("name")) for qb in (ctx.get("qbs", []) or []) if v3._safe(qb.get("name")))
    supplemental = _trusted_news_rows(
        v3._safe(ctx.get("abbr")).upper(),
        v3._safe(ctx.get("team"), ctx.get("abbr")),
        opponent_name,
        qb_names,
    )
    articles.extend(supplemental)

    # Cross-provider dedupe by normalized headline; prefer ESPN/official first.
    deduped, seen = [], set()
    for article in articles:
        key = re.sub(r"\W+", " ", v3._safe(article.get("headline")).lower()).strip()
        if not key:
            key = v3._safe(article.get("href")).lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(article)

    classified = []
    for article in deduped:
        item = v3._classify_article(article, ctx, opponent_name, kickoff)
        if article.get("source_tier"):
            item["qualifying"] = _supplemental_qualifying(article, item)
            item["source_tier"] = article.get("source_tier")
            item["source_url"] = article.get("source_url")
        classified.append(item)

    evidence = [x for x in classified if x.get("qualifying")]
    evidence.sort(
        key=lambda x: x.get("published") if pd.notna(x.get("published")) else pd.Timestamp.min.tz_localize("UTC"),
        reverse=True,
    )

    status_by_qb = {}
    starter_candidates = set()
    for item in evidence:
        if item.get("starter_name"):
            starter_candidates.add(item["starter_name"])
        for name in item.get("mentions", []):
            bucket = status_by_qb.setdefault(name, set())
            if item.get("play"):
                bucket.add("PLAY")
            if item.get("rest"):
                bucket.add("REST")

    conflicts = []
    for name, states in status_by_qb.items():
        if "PLAY" in states and "REST" in states:
            conflicts.append(f"{name}: PLAY vs REST")
    if len(starter_candidates) > 1:
        conflicts.append("multiple explicit starter names")

    explicit_participation = any((x.get("play") or x.get("rest")) and x.get("mentions") for x in evidence)
    rotation_verified = any(x.get("rotation") and x.get("mentions") for x in evidence)
    named_participants = {name for name, states in status_by_qb.items() if states}
    if len(named_participants) >= 2:
        rotation_verified = True

    starter_verified = len(starter_candidates) == 1
    starter_name = next(iter(starter_candidates)) if starter_verified else ""
    starter_intent_verified = any(x.get("general_starters") for x in evidence)
    ready = bool(starter_verified and explicit_participation and rotation_verified and not conflicts)

    return {
        "team": v3._safe(ctx.get("team"), ctx.get("abbr")),
        "abbr": v3._safe(ctx.get("abbr")),
        "news_ok": bool(tdiag.get("ok") or sdiag.get("ok") or supplemental),
        "team_news_http": tdiag.get("http"),
        "summary_http": sdiag.get("http"),
        "articles_scanned": len(classified),
        "espn_scanned": len(classified) - len(supplemental),
        "trusted_scanned": len(supplemental),
        "evidence": evidence,
        "starter_verified": starter_verified,
        "starter_name": starter_name,
        "participation_verified": explicit_participation,
        "rotation_verified": rotation_verified,
        "starter_intent_verified": starter_intent_verified,
        "conflicts": conflicts,
        "ready": ready,
    }


# Patch only Step-3 evidence coverage. V3 classification/gate logic stays intact.
v3._team_gameplan_context = _team_gameplan_context


def render_nfl_moneyline_hub():
    # V3's original caption says ESPN-only. Rewrite that one caption during this
    # render so production accurately describes the expanded evidence layer.
    real_caption = st.caption

    def _caption(body, *args, **kwargs):
        if isinstance(body, str) and "ESPN team/game news only" in body:
            body = body.replace(
                "ESPN team/game news only",
                "ESPN + trusted official/beat-news discovery",
            )
        return real_caption(body, *args, **kwargs)

    st.caption = _caption
    try:
        return v3.render_nfl_moneyline_hub()
    finally:
        st.caption = real_caption


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
