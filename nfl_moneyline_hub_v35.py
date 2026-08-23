"""Kyre Sports AI — NFL Moneyline V3.5 Step-3D sentence-scoped evidence attribution.

Repairs a semantic bug exposed by V3.4 full-text enrichment: article-level PLAY/REST/
START/ROTATION flags could be applied to every quarterback mentioned anywhere in a
long article. V3.5 attributes signals only inside sentence-local QB windows and
aggregates conflicts per quarterback from those scoped signals.

All Step 1 / Step 2.1 / Step 3.2-3.4 source, freshness, trust, and fail-closed
rules remain preserved. No sportsbook, probability, Monte Carlo, ranking or
recommendation logic is added. MLB/WNBA remain isolated and untouched.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

import nfl_moneyline_hub_v34 as v34
import nfl_moneyline_hub_v33 as v33
import nfl_moneyline_hub_v3 as v3

MODEL_VERSION = "NFL MONEYLINE V3.5 • STEP 3D SENTENCE-SCOPED ATTRIBUTION"

# Sentence-ish boundaries. Semicolon and bullets are also split because sports
# reports often pack several player-status statements into one paragraph.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|[\n\r]+|\s*[•·]\s*|\s*;\s*")


def _qb_aliases(name: str) -> tuple[str, ...]:
    name = v3._safe(name)
    if not name:
        return ()
    parts = name.split()
    aliases = [name.lower()]
    if len(parts) >= 2 and len(parts[-1]) >= 4:
        aliases.append(parts[-1].lower())
    return tuple(dict.fromkeys(aliases))


def _sentence_has_qb(sentence: str, name: str) -> bool:
    low = sentence.lower()
    for alias in _qb_aliases(name):
        if " " in alias:
            if alias in low:
                return True
        elif re.search(rf"\b{re.escape(alias)}\b", low):
            return True
    return False


def _split_sentences(text: str) -> list[str]:
    chunks = []
    for part in _SENTENCE_SPLIT.split(str(text or "")):
        part = re.sub(r"\s+", " ", part).strip()
        if len(part) >= 8:
            chunks.append(part)
    return chunks


def _scoped_classify_article(article: dict, ctx: dict, opponent_name: str, kickoff):
    headline = v3._safe(article.get("headline"))
    description = v3._safe(article.get("description"))
    full_text = f"{headline}. {description}".strip()
    low_all = full_text.lower()

    published = article.get("published")
    fresh = False
    hours_before = None
    if pd.notna(published) and pd.notna(kickoff):
        delta = kickoff - published
        hours_before = delta.total_seconds() / 3600.0
        fresh = 0 <= hours_before <= v3.FRESH_HOURS

    preseason_context = "preseason" in low_all
    opponent_hit = any(tok in low_all for tok in v3._opponent_tokens(opponent_name))
    contextual = article.get("source") == "ESPN GAME SUMMARY" or preseason_context or opponent_hit

    qbs = [v3._safe(q.get("name")) for q in (ctx.get("qbs", []) or []) if v3._safe(q.get("name"))]
    sentences = _split_sentences(full_text)

    per_qb = {name: set() for name in qbs}
    starter_candidates = set()
    general_starters = False
    signal_sentences = []

    for sent in sentences:
        mentioned = [name for name in qbs if _sentence_has_qb(sent, name)]
        has_play = v3._match_any(v3.PLAY_PATTERNS, sent)
        has_rest = v3._match_any(v3.REST_PATTERNS, sent)
        has_start = v3._match_any(v3.START_PATTERNS, sent)
        has_rot = v3._match_any(v3.ROTATION_PATTERNS, sent)
        has_general = v3._match_any(v3.GENERAL_STARTER_PATTERNS, sent) and (has_play or has_rest)

        if has_general:
            general_starters = True

        # Do not attribute a status to multiple QBs when one sentence contains
        # contradictory status verbs. That sentence is ambiguous by construction.
        contradictory = has_play and has_rest

        if mentioned and not contradictory:
            for name in mentioned:
                if has_play:
                    per_qb[name].add("PLAY")
                if has_rest:
                    per_qb[name].add("REST")
                if has_rot:
                    per_qb[name].add("ROTATION")

            # Starter evidence is only safe when exactly one verified QB is named
            # in the sentence carrying the START phrase.
            if has_start and len(mentioned) == 1:
                per_qb[mentioned[0]].add("START")
                starter_candidates.add(mentioned[0])

            if any((has_play, has_rest, has_start, has_rot)):
                signal_sentences.append({
                    "sentence": sent[:500],
                    "qbs": list(mentioned),
                    "play": has_play,
                    "rest": has_rest,
                    "start": has_start,
                    "rotation": has_rot,
                    "ambiguous": False,
                })
        elif mentioned and contradictory:
            signal_sentences.append({
                "sentence": sent[:500],
                "qbs": list(mentioned),
                "play": True,
                "rest": True,
                "start": has_start,
                "rotation": has_rot,
                "ambiguous": True,
            })

    mentioned_with_signal = [name for name, states in per_qb.items() if states]
    play = any("PLAY" in states for states in per_qb.values())
    rest = any("REST" in states for states in per_qb.values())
    start = any("START" in states for states in per_qb.values())
    rotation = any("ROTATION" in states for states in per_qb.values())

    explicit_qb = bool(mentioned_with_signal and (play or rest or start or rotation))
    explicit_general = bool(general_starters)
    qualifying = bool(fresh and contextual and (explicit_qb or explicit_general))

    labels = []
    if start:
        labels.append("START")
    if play:
        labels.append("PLAY")
    if rest:
        labels.append("REST")
    if rotation:
        labels.append("ROTATION")
    if explicit_general:
        labels.append("STARTER INTENT")

    starter_name = next(iter(starter_candidates)) if len(starter_candidates) == 1 else ""
    return {
        **article,
        "mentions": mentioned_with_signal,
        "play": play,
        "rest": rest,
        "start": start,
        "rotation": rotation,
        "general_starters": general_starters,
        "fresh": fresh,
        "hours_before": hours_before,
        "contextual": contextual,
        "qualifying": qualifying,
        "labels": labels,
        "starter_name": starter_name,
        "per_qb_signals": {k: sorted(v) for k, v in per_qb.items() if v},
        "signal_sentences": signal_sentences,
    }


# All downstream V3.3/V3.4 diagnostics now see sentence-scoped classification.
v3._classify_article = _scoped_classify_article


# Rebuild the team context with per-QB signal aggregation instead of applying
# one article-level PLAY/REST flag to every QB mentioned in that article.
_ORIGINAL_V33_CONTEXT = v33._team_gameplan_context


def _team_gameplan_context(ctx: dict, opponent_name: str, game_id: str, kickoff):
    # Reuse V3.3 discovery, V3.4 full-text enrichment and source guards by
    # reproducing the compact aggregation over those already-patched inputs.
    team_id = v3._safe(ctx.get("team_id"))
    team_payload, tdiag = v3._team_news_payload(team_id) if team_id else ({}, {"ok": False, "http": None, "error": "missing team id"})
    summary_payload, sdiag = v3._game_summary_payload(game_id)

    articles = v3._article_rows(team_payload, "ESPN TEAM NEWS")
    articles.extend(v3._article_rows(summary_payload, "ESPN GAME SUMMARY"))

    qb_names = tuple(v3._safe(qb.get("name")) for qb in (ctx.get("qbs", []) or []) if v3._safe(qb.get("name")))
    supplemental = v33._trusted_news_rows(
        v3._safe(ctx.get("abbr")).upper(),
        v3._safe(ctx.get("team"), ctx.get("abbr")),
        opponent_name,
        qb_names,
    )
    articles.extend(supplemental)

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
        item = _scoped_classify_article(article, ctx, opponent_name, kickoff)
        if article.get("source_tier"):
            item["qualifying"] = v33._supplemental_qualifying(article, item)
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
    rotation_qbs = set()
    for item in evidence:
        if item.get("starter_name"):
            starter_candidates.add(item["starter_name"])
        for name, signals in (item.get("per_qb_signals") or {}).items():
            bucket = status_by_qb.setdefault(name, set())
            bucket.update(x for x in signals if x in {"PLAY", "REST"})
            if "ROTATION" in signals:
                rotation_qbs.add(name)

    conflicts = []
    for name, states in status_by_qb.items():
        if "PLAY" in states and "REST" in states:
            conflicts.append(f"{name}: PLAY vs REST")
    if len(starter_candidates) > 1:
        conflicts.append("multiple explicit starter names")

    explicit_participation = any(bool(states & {"PLAY", "REST"}) for states in status_by_qb.values())
    rotation_verified = bool(rotation_qbs)
    named_participants = {name for name, states in status_by_qb.items() if states & {"PLAY", "REST"}}
    if len(named_participants) >= 2:
        rotation_verified = True

    starter_verified = len(starter_candidates) == 1
    starter_name = next(iter(starter_candidates)) if starter_verified else ""
    starter_intent_verified = any(x.get("general_starters") for x in evidence)
    ready = bool(starter_verified and explicit_participation and rotation_verified and not conflicts)

    result = {
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

    # Keep V3.4 diagnostic rows available using the newly scoped classifier.
    try:
        result["diagnostics"] = v34._diagnostic_rows(ctx, opponent_name, game_id, kickoff)
    except Exception:
        result["diagnostics"] = []
    return result


v3._team_gameplan_context = _team_gameplan_context


def render_nfl_moneyline_hub():
    return v34.render_nfl_moneyline_hub()


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
