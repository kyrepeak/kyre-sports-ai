"""CFB O/U multi-source logo resolver V2.

Additive presentation-only logo resolver above permanently frozen ESPN resolver V1.

Provider order
--------------
1. Frozen ESPN resolver V1.
2. Official athletics website discovered from a verified Wikipedia football page.
3. Wikipedia football-page image.
4. Wikimedia Commons logo search.

This resolver fills missing sides independently. It never changes schedule
identity, model inputs, projected points, probabilities, final selection,
Top-5 ranking, reliability, sportsbook state, EV, or simulation behavior.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any, Mapping
from urllib.parse import unquote, urljoin, urlparse

import streamlit as st

import cfb_over_under_logo_resolver_v1 as espn
import cfb_schedule_v1 as schedule_v1
import cfb_team_data_v1 as team_data_v1

MODEL_VERSION = "CFB O/U MULTI-SOURCE LOGO RESOLVER V2"
FROZEN_ESPN_RESOLVER = "cfb_over_under_logo_resolver_v1"

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

_FORBIDDEN_OFFICIAL_DOMAINS = (
    "wikipedia.org",
    "wikimedia.org",
    "espn.com",
    "ncaa.com",
    "sports-reference.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "tiktok.com",
    "archive.org",
    "web.archive.org",
)

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".svg")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _name_key(value: Any) -> str:
    return espn._name_key(value)


def _aliases(value: Any) -> set[str]:
    return espn._aliases(value)


def _tokens(value: Any) -> set[str]:
    text = _clean(value).lower().replace("&", " and ")
    text = re.sub(r"\([^)]*\)", " ", text)
    stop = {
        "university", "college", "state", "the", "of", "at", "and",
        "football", "team", "athletics", "athletic",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text)
        if len(token) >= 2 and token not in stop
    }


def _safe_http_url(value: Any) -> str:
    text = _clean(value)
    if text.startswith("//"):
        text = "https:" + text
    if not text.startswith(("https://", "http://")):
        return ""
    parsed = urlparse(text)
    if not parsed.netloc:
        return ""
    return text


def _merge_visual(
    base: Mapping[str, Any],
    update: Mapping[str, Any],
) -> dict[str, Any]:
    out = dict(base or {})
    for key, value in (update or {}).items():
        if value not in (None, "", [], {}):
            out[key] = value
    return out


def _pages(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    query = payload.get("query") or {}
    pages = query.get("pages") or []
    if isinstance(pages, Mapping):
        return [dict(v) for v in pages.values() if isinstance(v, Mapping)]
    if isinstance(pages, list):
        return [dict(v) for v in pages if isinstance(v, Mapping)]
    return []


def _candidate_score(
    page: Mapping[str, Any],
    team_name: str,
    conference: str,
) -> float:
    title = _clean(page.get("title"))
    extract = _clean(page.get("extract"))
    lower_title = title.lower()
    team_tokens = _tokens(team_name)
    title_tokens = _tokens(title)
    overlap = len(team_tokens & title_tokens)

    score = float(overlap * 4)
    if "football" in lower_title:
        score += 6.0
    if _name_key(team_name) and _name_key(team_name) in _name_key(title):
        score += 5.0

    qualifier = ""
    match = re.search(r"\(([^)]*)\)", team_name)
    if match:
        qualifier = match.group(1).strip().lower()
    if qualifier and qualifier in (title + " " + extract).lower():
        score += 4.0

    conf = _clean(conference)
    if conf and re.search(rf"\b{re.escape(conf)}\b", extract, flags=re.I):
        score += 3.0

    if lower_title.endswith(" football"):
        score += 5.0
    if any(
        term in lower_title
        for term in (
            "disambiguation",
            "season",
            "history of",
            "rivalry",
            "football game",
            "championship game",
            "series",
            "stadium",
            "list of",
        )
    ):
        score -= 10.0
    return score


@st.cache_data(ttl=86400, show_spinner=False)
def _wikipedia_candidates(
    team_name: str,
    conference: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = _clean(team_name)
    conf = _clean(conference)
    queries = [f"{base} football"]
    if conf and conf.upper() not in {"FBS", "FCS"}:
        queries.append(f"{base} football {conf}")

    attempts: list[dict[str, Any]] = []
    found: dict[int, dict[str, Any]] = {}
    for search in queries:
        payload, diag = schedule_v1._fetch_json_with_fallback(
            WIKIPEDIA_API,
            {
                "action": "query",
                "generator": "search",
                "gsrsearch": search,
                "gsrnamespace": 0,
                "gsrlimit": 8,
                "prop": "pageimages|info|extracts|extlinks",
                "piprop": "thumbnail|original",
                "pithumbsize": 600,
                "inprop": "url",
                "exintro": 1,
                "explaintext": 1,
                "exsentences": 3,
                "ellimit": "max",
                "redirects": 1,
                "format": "json",
                "formatversion": 2,
            },
            f"Wikipedia CFB logo search: {search}",
        )
        attempts.extend(diag)
        for page in _pages(payload):
            pageid = int(page.get("pageid") or 0)
            if pageid <= 0:
                continue
            page["_logo_score"] = _candidate_score(page, base, conf)
            previous = found.get(pageid)
            if previous is None or page["_logo_score"] > previous.get("_logo_score", -999):
                found[pageid] = page

        if found and max(float(row.get("_logo_score") or 0.0) for row in found.values()) >= 12.0:
            break

    ranked = sorted(
        found.values(),
        key=lambda row: (float(row.get("_logo_score") or 0.0), -int(row.get("pageid") or 0)),
        reverse=True,
    )
    return ranked, attempts


def _logo_url_score(url: str, team_name: str) -> float:
    parsed = urlparse(_safe_http_url(url))
    text = unquote(parsed.path).lower()
    team_tokens = _tokens(team_name)
    path_tokens = _tokens(text)
    score = 0.0
    if "logo" in text:
        score += 8.0
    if any(term in text for term in ("wordmark", "brand", "athletic-mark", "primary-mark", "secondary-mark")):
        score += 5.0
    score += 2.5 * len(team_tokens & path_tokens)
    if text.endswith(".svg"):
        score += 2.0
    if any(
        term in text
        for term in (
            "photo",
            "gallery",
            "player",
            "stadium",
            "civil_war",
            "game_",
            "presto",
            "article",
            "story",
        )
    ):
        score -= 8.0
    return score


def _is_wikimedia_logo_url(url: str, team_name: str) -> bool:
    safe = _safe_http_url(url)
    if not safe:
        return False
    path = unquote(urlparse(safe).path).lower()
    path_tokens = _tokens(path)
    team_tokens = _tokens(team_name)
    if not (team_tokens & path_tokens):
        return False
    logo_marker = any(
        term in path
        for term in ("logo", "wordmark", "primary-mark", "secondary-mark", "athletic-mark")
    )
    vector_mark = path.endswith(".svg")
    return bool(logo_marker or vector_mark)


def _page_image(page: Mapping[str, Any], team_name: str) -> str:
    team_tokens = _tokens(team_name)
    for key in ("original", "thumbnail"):
        obj = page.get(key) or {}
        if isinstance(obj, Mapping):
            url = _safe_http_url(obj.get("source"))
            if (
                url
                and "upload.wikimedia.org" in urlparse(url).netloc.lower()
                and _is_wikimedia_logo_url(url, team_name)
                and _logo_url_score(url, team_name) >= 5.0
            ):
                return url
    return ""


def _external_links(page: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for item in page.get("extlinks") or []:
        if isinstance(item, Mapping):
            value = item.get("*") or item.get("url")
        else:
            value = item
        url = _safe_http_url(value)
        if url:
            out.append(url)
    return out


def _official_url_score(url: str, team_identity: str = "") -> float:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    lower = url.lower()
    if any(domain in host for domain in _FORBIDDEN_OFFICIAL_DOMAINS):
        return -999.0

    score = 0.0
    if "/sports/football" in lower:
        score += 12.0
    if "football" in parsed.path.lower():
        score += 5.0
    if "athletics" in host or "athletic" in host:
        score += 5.0
    if any(word in host for word in ("hurricanes", "gators", "rattlers", "sooners", "longhorns", "tigers", "bulldogs")):
        score += 3.0
    identity_tokens = {
        token for token in _tokens(team_identity)
        if len(token) >= 4 and token not in {"football"}
    }
    host_key = re.sub(r"[^a-z0-9]+", "", host)
    if any(token in host_key for token in identity_tokens):
        score += 8.0
    if parsed.path in ("", "/"):
        score += 1.0
    return score


def _best_official_url(page: Mapping[str, Any]) -> str:
    links = _external_links(page)
    if not links:
        return ""
    title = _clean(page.get("title"))
    identity = title[:-9].strip() if title.lower().endswith(" football") else title
    ranked = sorted(
        ((float(_official_url_score(url, identity)), url) for url in links),
        reverse=True,
    )
    if not ranked or ranked[0][0] < 8.0:
        return ""
    return ranked[0][1]


class _LogoHtmlParser(HTMLParser):
    def __init__(self, team_name: str) -> None:
        super().__init__()
        self.team_tokens = _tokens(team_name)
        self.meta_images: list[str] = []
        self.image_candidates: list[tuple[float, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        data = {str(k).lower(): _clean(v) for k, v in attrs}
        tag = tag.lower()

        if tag == "link":
            rel = (data.get("rel") or "").lower()
            href = data.get("href") or ""
            if "icon" in rel and href:
                self.image_candidates.append((3.0, href))
            return

        if tag == "meta":
            prop = (data.get("property") or data.get("name") or "").lower()
            if prop in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
                value = _safe_http_url(data.get("content"))
                if value:
                    self.meta_images.append(value)
            return

        if tag != "img":
            return

        src = data.get("src") or data.get("data-src") or data.get("data-lazy-src") or ""
        alt = data.get("alt") or ""
        klass = data.get("class") or ""
        ident = data.get("id") or ""
        text = " ".join((src, alt, klass, ident)).lower()
        score = 0.0
        if "logo" in text:
            score += 8.0
        if "site-logo" in text or "brand" in text:
            score += 4.0
        hay_tokens = _tokens(text)
        score += 2.0 * len(self.team_tokens & hay_tokens)
        if any(
            term in text
            for term in (
                "sprite",
                "pixel",
                "tracker",
                "adserver",
                "wayback",
                "toolbar",
                "wikipedia-wordmark",
                "/static/images/",
                "wikimedia-button",
            )
        ):
            score -= 12.0
        if "favicon" in text:
            score -= 2.0
        if score > 0:
            self.image_candidates.append((score, src))



@st.cache_data(ttl=86400, show_spinner=False)
def _wikipedia_html_logo(
    page_url: str,
    team_name: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Parse the football article HTML when the pageimages API has no usable image."""
    if not _safe_http_url(page_url):
        return "", []
    html, attempts = team_data_v1._fetch_text_with_fallback(
        page_url,
        f"Wikipedia football article logo: {team_name}",
    )
    if not html:
        return "", attempts

    parser = _LogoHtmlParser(team_name)
    parser.feed(html)

    team_tokens = _tokens(team_name)
    ranked = sorted(parser.image_candidates, reverse=True)
    for score, raw in ranked:
        if score < 4.0:
            continue
        url = _safe_http_url(urljoin(page_url, raw))
        if not url:
            continue
        host = urlparse(url).netloc.lower()
        if (
            ("wikimedia.org" in host or "wikipedia.org" in host)
            and _is_wikimedia_logo_url(url, team_name)
            and _logo_url_score(url, team_name) >= 5.0
        ):
            return url, attempts

    for raw in parser.meta_images:
        url = _safe_http_url(urljoin(page_url, raw))
        if (
            url
            and "wikimedia.org" in urlparse(url).netloc.lower()
            and _is_wikimedia_logo_url(url, team_name)
            and _logo_url_score(url, team_name) >= 5.0
        ):
            return url, attempts

    return "", attempts


@st.cache_data(ttl=86400, show_spinner=False)
def _official_page_logo(
    official_url: str,
    team_name: str,
) -> tuple[str, list[dict[str, Any]]]:
    html, attempts = team_data_v1._fetch_text_with_fallback(
        official_url,
        f"Official athletics logo page: {team_name}",
    )
    if not html:
        return "", attempts

    parser = _LogoHtmlParser(team_name)
    parser.feed(html)

    ranked = sorted(parser.image_candidates, reverse=True)
    for parser_score, raw in ranked:
        url = _safe_http_url(urljoin(official_url, raw))
        if (
            url
            and parser_score >= 4.0
            and any(urlparse(url).path.lower().endswith(ext) for ext in _IMAGE_EXTENSIONS)
            and _logo_url_score(url, team_name) >= 3.0
        ):
            return url, attempts

    for raw in parser.meta_images:
        url = _safe_http_url(urljoin(official_url, raw))
        if url and _logo_url_score(url, team_name) >= 5.0:
            return url, attempts
    return "", attempts


def _commons_score(
    page: Mapping[str, Any],
    team_name: str,
) -> float:
    title = _clean(page.get("title"))
    lower = title.lower()
    team_tokens = _tokens(team_name)
    title_tokens = _tokens(title)
    overlap = len(team_tokens & title_tokens)
    if not overlap:
        return -999.0
    score = float(overlap * 4)
    if "logo" in lower:
        score += 7.0
    if "football" in lower:
        score += 4.0
    if "athletic" in lower or "athletics" in lower:
        score += 3.0
    if "wordmark" in lower:
        score += 1.0
    if any(term in lower for term in ("seal", "campus", "stadium", "player", "photograph", "jersey")):
        score -= 7.0
    return score


@st.cache_data(ttl=86400, show_spinner=False)
def _commons_logo(
    team_name: str,
) -> tuple[str, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []

    direct_titles = [
        f"File:{team_name} logo.svg",
        f"File:{team_name} logo.png",
        f"File:{team_name} wordmark.svg",
        f"File:{team_name} athletics logo.svg",
    ]
    direct_payload, direct_attempts = schedule_v1._fetch_json_with_fallback(
        COMMONS_API,
        {
            "action": "query",
            "titles": "|".join(direct_titles),
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "iiurlwidth": 600,
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
        },
        f"Wikimedia Commons direct CFB logo lookup: {team_name}",
    )
    attempts.extend(direct_attempts)

    direct_ranked = sorted(
        (
            (_commons_score(page, team_name), page)
            for page in _pages(direct_payload)
            if not page.get("missing")
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    for score, page in direct_ranked:
        if score < 8.0:
            continue
        info = (page.get("imageinfo") or [{}])[0] or {}
        url = _safe_http_url(info.get("thumburl") or info.get("url"))
        if url:
            return url, attempts

    payload, search_attempts = schedule_v1._fetch_json_with_fallback(
        COMMONS_API,
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"{team_name} logo",
            "gsrnamespace": 6,
            "gsrlimit": 25,
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "iiurlwidth": 600,
            "format": "json",
            "formatversion": 2,
        },
        f"Wikimedia Commons CFB logo search: {team_name}",
    )
    attempts.extend(search_attempts)
    ranked = sorted(
        (
            (_commons_score(page, team_name), page)
            for page in _pages(payload)
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    for score, page in ranked:
        if score < 8.0:
            continue
        info = (page.get("imageinfo") or [{}])[0] or {}
        url = _safe_http_url(info.get("thumburl") or info.get("url"))
        mime = _clean(info.get("mime")).lower()
        if url and (mime.startswith("image/") or urlparse(url).path.lower().endswith(_IMAGE_EXTENSIONS)):
            return url, attempts
    return "", attempts


@st.cache_data(ttl=86400, show_spinner=False)
def resolve_team_logo(
    team_name: str,
    team_slug: str = "",
    conference: str = "",
) -> dict[str, Any]:
    """Resolve one team from non-ESPN sources without guessing."""
    pages, wiki_attempts = _wikipedia_candidates(team_name, conference)
    best = pages[0] if pages and float(pages[0].get("_logo_score") or 0.0) >= 8.0 else {}

    if best:
        official_url = _best_official_url(best)
        if official_url:
            official_logo, official_attempts = _official_page_logo(
                official_url,
                team_name,
            )
            if official_logo:
                return {
                    "logo": official_logo,
                    "source": "Official athletics website",
                    "logo_provider": "official_athletics",
                    "logo_source_url": official_url,
                    "confidence": "HIGH",
                    "provider_attempts": wiki_attempts + official_attempts,
                }

        wiki_logo = _page_image(best, team_name)
        if wiki_logo:
            return {
                "logo": wiki_logo,
                "source": "Wikipedia / Wikimedia",
                "logo_provider": "wikipedia_pageimage",
                "logo_source_url": _clean(best.get("fullurl")),
                "confidence": "MEDIUM",
                "provider_attempts": wiki_attempts,
            }

        wiki_html_logo, wiki_html_attempts = _wikipedia_html_logo(
            _clean(best.get("fullurl")),
            team_name,
        )
        if wiki_html_logo:
            return {
                "logo": wiki_html_logo,
                "source": "Wikipedia / Wikimedia",
                "logo_provider": "wikipedia_html",
                "logo_source_url": _clean(best.get("fullurl")),
                "confidence": "MEDIUM",
                "provider_attempts": wiki_attempts + wiki_html_attempts,
            }

    commons_identity = team_name
    if best:
        title = _clean(best.get("title"))
        if title.lower().endswith(" football"):
            enriched = title[:-9].strip()
            if enriched:
                commons_identity = enriched

    commons_logo, commons_attempts = _commons_logo(commons_identity)
    if commons_logo:
        return {
            "logo": commons_logo,
            "source": "Wikimedia Commons",
            "logo_provider": "wikimedia_commons",
            "logo_source_url": commons_logo,
            "confidence": "MEDIUM",
            "provider_attempts": wiki_attempts + commons_attempts,
        }

    return {
        "logo": "",
        "source": "",
        "logo_provider": "",
        "logo_source_url": "",
        "confidence": "UNAVAILABLE",
        "provider_attempts": wiki_attempts + commons_attempts,
    }


def _side_identity(game: Mapping[str, Any], side: str) -> tuple[str, str, str]:
    return (
        _clean(game.get(f"{side}_team")),
        _clean(game.get(f"{side}_team_slug")),
        _clean(game.get(f"{side}_conference")),
    )


def resolve_visuals(
    game: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Resolve both teams using ESPN first, then independent multi-source fills."""
    try:
        visuals = espn.resolve_visuals(game)
    except Exception:
        visuals = {"away": {}, "home": {}}

    out = {
        "away": dict((visuals or {}).get("away") or {}),
        "home": dict((visuals or {}).get("home") or {}),
    }

    for side in ("away", "home"):
        if _clean(out[side].get("logo")):
            out[side].setdefault("logo_provider", "espn")
            out[side].setdefault("confidence", "HIGH")
            continue

        name, slug, conference = _side_identity(game, side)
        if not name:
            continue
        fallback = resolve_team_logo(name, slug, conference)
        out[side] = _merge_visual(out[side], fallback)
        out[side].setdefault("name", name)

    return out


def clear_logo_cache() -> None:
    for fn in (
        _wikipedia_candidates,
        _official_page_logo,
        _wikipedia_html_logo,
        _commons_logo,
        resolve_team_logo,
    ):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        espn.clear_logo_cache()
    except Exception:
        pass


__all__ = [
    "COMMONS_API",
    "FROZEN_ESPN_RESOLVER",
    "MODEL_VERSION",
    "WIKIPEDIA_API",
    "_best_official_url",
    "_commons_logo",
    "_page_image",
    "_wikipedia_candidates",
    "_wikipedia_html_logo",
    "clear_logo_cache",
    "resolve_team_logo",
    "resolve_visuals",
]
