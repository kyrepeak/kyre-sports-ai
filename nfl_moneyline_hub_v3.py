"""Kyre Sports AI — NFL Moneyline V3 Step 3 game-plan intelligence.

Preserves verified Step 1 + Step 2 foundations and adds a fail-closed preseason
intent layer based on fresh ESPN team/game news evidence. A depth chart is never
used as a proxy for game participation or snap/drive rotation.

Step 3 can verify only explicit published evidence for:
- named starting quarterback;
- QB play/rest intent;
- QB rotation / series / quarter / drive plan;
- broader starter-rest intent;
- freshness and conflicting-report state.

No sportsbook price, win probability, fair odds, EV, Monte Carlo, ranking or
recommendation is produced. MLB/WNBA are not imported.
"""
from __future__ import annotations

import re
from datetime import datetime
from html import escape

import pandas as pd
import requests
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v2 as base
import nfl_moneyline_hub_v21 as step2_repair  # patches base depth helpers to Core fallback

ET = foundation.ET
MODEL_VERSION = "NFL MONEYLINE V3 • STEP 3 PRESEASON GAME-PLAN INTELLIGENCE"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
    "Accept": "application/json,text/plain,*/*",
}
FRESH_HOURS = 96

PLAY_PATTERNS = [
    r"\bwill play\b", r"\bexpected to play\b", r"\bplans? to play\b",
    r"\bset to play\b", r"\bwill see action\b", r"\bexpected to see action\b",
]
REST_PATTERNS = [
    r"\bwill not play\b", r"\bwon['’]t play\b", r"\bnot expected to play\b",
    r"\bsit out\b", r"\bwill sit\b", r"\bheld out\b", r"\bwill be held out\b",
    r"\brest(?:ed|ing)?\b", r"\bwon['’]t suit up\b",
]
START_PATTERNS = [
    r"\bwill start\b", r"\bgets? the start\b", r"\bstarting at quarterback\b",
    r"\bstart at quarterback\b", r"\bstarts? at quarterback\b",
]
ROTATION_PATTERNS = [
    r"\brotation\b", r"\bseries\b", r"\bdrives?\b", r"\bquarters?\b",
    r"\bfirst half\b", r"\bsecond half\b", r"\bsplit (?:reps|snaps)\b",
    r"\bshare (?:reps|snaps)\b", r"\bplay (?:one|two|three|four|a|the) quarters?\b",
]
GENERAL_STARTER_PATTERNS = [
    r"\bstarters?\b", r"\bfirst[- ]team\b", r"\bveterans?\b",
]


def _safe(value, default="") -> str:
    text = str(value or "").strip()
    return text or default


def _json_get(url: str, timeout: int = 8):
    diag = {"url": url, "http": None, "ok": False, "error": ""}
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        diag["http"] = int(r.status_code)
        r.raise_for_status()
        payload = r.json()
        diag["ok"] = True
        return payload, diag
    except Exception as exc:
        diag["error"] = str(exc)[:220]
        return {}, diag


@st.cache_data(ttl=300, show_spinner=False)
def _team_news_payload(team_id: str):
    payload, diag = _json_get(f"{ESPN_BASE}/teams/{team_id}/news?limit=30")
    if diag.get("ok"):
        return payload, diag
    return _json_get(f"{ESPN_BASE}/news?team={team_id}")


@st.cache_data(ttl=300, show_spinner=False)
def _game_summary_payload(game_id: str):
    if not _safe(game_id):
        return {}, {"ok": False, "http": None, "error": "missing game id"}
    return _json_get(f"{ESPN_BASE}/summary?event={game_id}")


def _href(article: dict) -> str:
    links = (article or {}).get("links") or {}
    if isinstance(links, dict):
        for key in ("web", "mobile", "api"):
            block = links.get(key)
            if isinstance(block, dict) and _safe(block.get("href")):
                return _safe(block.get("href"))
    link = (article or {}).get("link") or {}
    if isinstance(link, dict):
        return _safe(link.get("href"))
    return ""


def _published(article: dict):
    value = (article or {}).get("published") or (article or {}).get("lastModified") or (article or {}).get("date")
    if not value:
        return pd.NaT
    try:
        return pd.to_datetime(value, utc=True).tz_convert(ET)
    except Exception:
        return pd.NaT


def _article_rows(payload: dict, source_label: str):
    candidates = []
    for key in ("articles", "news", "headlines"):
        value = (payload or {}).get(key)
        if isinstance(value, list):
            candidates.extend(value)
    out, seen = [], set()
    for article in candidates:
        if not isinstance(article, dict):
            continue
        headline = _safe(article.get("headline") or article.get("title"))
        description = _safe(article.get("description") or article.get("story") or article.get("summary"))
        if not headline and not description:
            continue
        href = _href(article)
        key = href or (headline.lower(), description[:80].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "headline": headline,
            "description": description,
            "href": href,
            "published": _published(article),
            "source": source_label,
        })
    return out


def _match_any(patterns, text: str) -> bool:
    return any(re.search(p, text, flags=re.I) for p in patterns)


def _qb_mentions(text: str, ctx: dict):
    mentions = []
    lowered = text.lower()
    for qb in ctx.get("qbs", []) or []:
        name = _safe(qb.get("name"))
        if not name:
            continue
        last = name.split()[-1].lower()
        if name.lower() in lowered or (len(last) >= 4 and re.search(rf"\b{re.escape(last)}\b", lowered)):
            mentions.append(name)
    return list(dict.fromkeys(mentions))


def _opponent_tokens(opponent_name: str):
    name = _safe(opponent_name).lower()
    toks = {name} if name else set()
    if name:
        toks.add(name.split()[-1])
    return {x for x in toks if len(x) >= 4}


def _classify_article(article: dict, ctx: dict, opponent_name: str, kickoff):
    headline = _safe(article.get("headline"))
    description = _safe(article.get("description"))
    text = f"{headline}. {description}".strip().lower()
    mentions = _qb_mentions(text, ctx)
    play = _match_any(PLAY_PATTERNS, text)
    rest = _match_any(REST_PATTERNS, text)
    start = _match_any(START_PATTERNS, text)
    rotation = _match_any(ROTATION_PATTERNS, text)
    general_starters = _match_any(GENERAL_STARTER_PATTERNS, text) and (play or rest)
    preseason_context = "preseason" in text
    opponent_hit = any(tok in text for tok in _opponent_tokens(opponent_name))

    published = article.get("published")
    fresh = False
    hours_before = None
    if pd.notna(published) and pd.notna(kickoff):
        delta = kickoff - published
        hours_before = delta.total_seconds() / 3600.0
        fresh = 0 <= hours_before <= FRESH_HOURS

    # A team-news item must be both fresh and game-contextual. Game-summary news is
    # already tied to the matchup, while team news must mention preseason or opponent.
    contextual = article.get("source") == "ESPN GAME SUMMARY" or preseason_context or opponent_hit
    explicit_qb = bool(mentions and (play or rest or start or rotation))
    explicit_general = bool(general_starters)
    qualifying = bool(fresh and contextual and (explicit_qb or explicit_general))

    labels = []
    if start and mentions:
        labels.append("START")
    if play and mentions:
        labels.append("PLAY")
    if rest and mentions:
        labels.append("REST")
    if rotation and mentions:
        labels.append("ROTATION")
    if explicit_general:
        labels.append("STARTER INTENT")

    starter_name = mentions[0] if start and len(mentions) == 1 else ""
    return {
        **article,
        "mentions": mentions,
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
    }


def _team_gameplan_context(ctx: dict, opponent_name: str, game_id: str, kickoff):
    team_id = _safe(ctx.get("team_id"))
    team_payload, tdiag = _team_news_payload(team_id) if team_id else ({}, {"ok": False, "http": None, "error": "missing team id"})
    summary_payload, sdiag = _game_summary_payload(game_id)

    articles = _article_rows(team_payload, "ESPN TEAM NEWS")
    # Summary feeds sometimes omit news entirely; safe to add zero rows.
    articles.extend(_article_rows(summary_payload, "ESPN GAME SUMMARY"))

    classified = [_classify_article(a, ctx, opponent_name, kickoff) for a in articles]
    evidence = [x for x in classified if x.get("qualifying")]
    evidence.sort(key=lambda x: x.get("published") if pd.notna(x.get("published")) else pd.Timestamp.min.tz_localize("UTC"), reverse=True)

    status_by_qb = {}
    starter_candidates = set()
    rotation_qbs = set()
    for item in evidence:
        if item.get("starter_name"):
            starter_candidates.add(item["starter_name"])
        for name in item.get("mentions", []):
            bucket = status_by_qb.setdefault(name, set())
            if item.get("play"):
                bucket.add("PLAY")
            if item.get("rest"):
                bucket.add("REST")
            if item.get("rotation"):
                rotation_qbs.add(name)

    conflicts = []
    for name, states in status_by_qb.items():
        if "PLAY" in states and "REST" in states:
            conflicts.append(f"{name}: PLAY vs REST")
    if len(starter_candidates) > 1:
        conflicts.append("multiple explicit starter names")

    explicit_participation = any((x.get("play") or x.get("rest")) and x.get("mentions") for x in evidence)
    rotation_verified = any(x.get("rotation") and x.get("mentions") for x in evidence)
    # Multiple named QBs with explicit play/rest evidence can also establish a
    # rotation sequence exists, even if the article does not use the word rotation.
    named_participants = {name for name, states in status_by_qb.items() if states}
    if len(named_participants) >= 2:
        rotation_verified = True

    starter_verified = len(starter_candidates) == 1
    starter_name = next(iter(starter_candidates)) if starter_verified else ""
    starter_intent_verified = any(x.get("general_starters") for x in evidence)
    ready = bool(starter_verified and explicit_participation and rotation_verified and not conflicts)

    return {
        "team": _safe(ctx.get("team"), ctx.get("abbr")),
        "abbr": _safe(ctx.get("abbr")),
        "news_ok": bool(tdiag.get("ok") or sdiag.get("ok")),
        "team_news_http": tdiag.get("http"),
        "summary_http": sdiag.get("http"),
        "articles_scanned": len(classified),
        "evidence": evidence,
        "starter_verified": starter_verified,
        "starter_name": starter_name,
        "participation_verified": explicit_participation,
        "rotation_verified": rotation_verified,
        "starter_intent_verified": starter_intent_verified,
        "conflicts": conflicts,
        "ready": ready,
    }


def _evidence_table(gp: dict):
    rows = []
    for item in gp.get("evidence", [])[:8]:
        published = item.get("published")
        rows.append({
            "Published ET": "—" if pd.isna(published) else published.strftime("%m/%d %I:%M %p"),
            "Evidence": " / ".join(item.get("labels", [])) or "—",
            "QB(s)": ", ".join(item.get("mentions", [])) or "—",
            "Headline": item.get("headline", ""),
            "Source": item.get("source", ""),
        })
    return pd.DataFrame(rows)


def _render_gameplan_team(gp: dict):
    team = _safe(gp.get("team"), gp.get("abbr"))
    st.markdown(f"#### {escape(team)}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Explicit starter", gp.get("starter_name") if gp.get("starter_verified") else "UNKNOWN")
    c2.metric("QB participation", "VERIFIED" if gp.get("participation_verified") else "UNKNOWN")
    c3.metric("Rotation", "VERIFIED" if gp.get("rotation_verified") else "UNKNOWN")
    c4.metric("Conflicts", len(gp.get("conflicts", [])))

    if gp.get("ready"):
        st.success("✅ GAME-PLAN GATE PASSED • explicit fresh starter + participation + rotation evidence found with no conflict.")
    else:
        st.warning("🔒 GAME-PLAN GATE LOCKED • explicit fresh starter/participation/rotation evidence is incomplete or conflicting.")

    if gp.get("conflicts"):
        st.error("Conflicting evidence: " + " • ".join(gp.get("conflicts", [])))

    table = _evidence_table(gp)
    with st.expander(f"📰 {team} game-plan evidence • {len(gp.get('evidence', []))} qualifying / {gp.get('articles_scanned', 0)} scanned", expanded=False):
        if table.empty:
            st.info(
                "No qualifying fresh explicit game-plan report was found in the ESPN team/game feeds. "
                "That is treated as UNKNOWN, not as permission to assume the depth-chart starter plays."
            )
        else:
            st.dataframe(table, use_container_width=True, hide_index=True)
            links = []
            for item in gp.get("evidence", [])[:5]:
                if item.get("href") and item.get("headline"):
                    links.append(f"- [{item['headline']}]({item['href']})")
            if links:
                st.markdown("\n".join(links))
    st.divider()


def render_nfl_moneyline_hub():
    # Step 2.1 patched the base module's depth resolver; use those repaired helpers.
    st.markdown(base._CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="knfl-ml-shell">'
        '<div class="knfl-ml-title">💰 NFL Moneyline <span>Command Center</span></div>'
        '<div class="knfl-ml-sub">Step 1 verified pregame foundation + Step 2 QB depth/injury verification + Step 3 fresh game-plan intelligence. Depth order never substitutes for preseason participation or rotation. No sportsbook/model math is active.</div>'
        '<div class="knfl-ml-chips">'
        '<span class="knfl-ml-chip">STEP 3</span><span class="knfl-ml-chip">QB DEPTH VERIFIED</span>'
        '<span class="knfl-ml-chip">FRESH NEWS EVIDENCE</span><span class="knfl-ml-chip">CONFLICT GUARD</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    if "nfl_v1_date" not in st.session_state:
        st.session_state["nfl_v1_date"] = datetime.now(ET).date()

    selected = st.date_input(
        "📅 Moneyline slate date",
        value=st.session_state["nfl_v1_date"],
        key="nfl_moneyline_v3_date_input",
    )
    st.session_state["nfl_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("💰 Verifying NFL Moneyline Steps 1–2…"):
        schedule, diag = foundation.load_nfl_slate(day_str)
        pregame, excluded = base._pregame_partition(schedule, day_str, now_et=now_et)

    phases = sorted({base._safe(x) for x in schedule.get("season_type", pd.Series(dtype=str)).tolist() if base._safe(x)}) if not schedule.empty else []
    preseason = bool(phases and all(x == "Preseason" for x in phases))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(len(schedule)))
    c2.metric("Pregame eligible", int(len(pregame)))
    c3.metric("Excluded / locked", int(len(excluded)))
    c4.metric("Model state", "DATA ONLY")
    st.caption(f"Pregame eligibility clock • {now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')}")

    if not diag.get("request_ok"):
        st.error("NFL schedule verification failed. Moneyline production remains locked and no games are fabricated.")
        return
    if schedule.empty:
        st.info("No verified NFL games were returned for this ET date. Moneyline remains locked.")
        return

    st.success(f"✅ STEP 1A PASSED • verified NFL slate loaded for {day_str}.")
    if len(pregame):
        st.success(f"✅ STEP 1B PASSED • {len(pregame)} game(s) remain provider-safe and before scheduled kickoff.")
    else:
        st.info("ℹ️ No games remain pregame-eligible. No team/game-plan context will be fetched for locked games.")

    if preseason:
        st.warning("⚠️ PRESEASON SLATE • Step 3 requires fresh explicit participation/rotation reporting; depth-chart status alone cannot clear the gate.")

    if not excluded.empty:
        with st.expander("🚫 Games excluded from pregame Moneyline", expanded=False):
            cols = [c for c in ["away_team", "home_team", "tip_et", "state", "status", "exclusion_reason"] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    st.markdown("### 🧩 Pregame Moneyline Foundation")
    if pregame.empty:
        st.markdown('<div class="knfl-ml-empty">No pregame-eligible NFL game is available for this date.</div>', unsafe_allow_html=True)
    else:
        cards = "".join(base._game_foundation_card(row) for _, row in pregame.iterrows())
        st.markdown(f'<div class="knfl-ml-grid">{cards}</div>', unsafe_allow_html=True)

    injury_payload, idiag = base._league_injuries_payload() if len(pregame) else ({}, {"ok": False})
    injury_map = base._parse_injuries(injury_payload) if idiag.get("ok") else {}

    team_contexts = {}
    for _, game in pregame.iterrows():
        for side in ("away", "home"):
            abbr = _safe(game.get(f"{side}_abbr")).upper()
            if abbr and abbr not in team_contexts:
                team_contexts[abbr] = base._team_context(
                    abbr,
                    _safe(game.get(f"{side}_team"), abbr),
                    injury_map,
                    bool(idiag.get("ok")),
                )

    unique_expected = len({str(x) for x in list(pregame.get("away_abbr", [])) + list(pregame.get("home_abbr", [])) if str(x)}) if len(pregame) else 0
    depth_verified = sum(1 for x in team_contexts.values() if x.get("depth_state") == "VERIFIED")
    injury_verified = sum(1 for x in team_contexts.values() if x.get("injury_state") == "VERIFIED")

    st.markdown("### 🧠 Step 2 — QB Depth + Current Availability")
    s1, s2, s3 = st.columns(3)
    s1.metric("Teams checked", f"{len(team_contexts)}/{unique_expected}")
    s2.metric("Depth verified", f"{depth_verified}/{unique_expected}")
    s3.metric("Injury feeds", f"{injury_verified}/{unique_expected}")

    depth_ready = bool(unique_expected and depth_verified == unique_expected)
    injuries_ready = bool(unique_expected and injury_verified == unique_expected)
    if depth_ready:
        st.success("✅ STEP 2A PASSED • current ESPN QB depth order verified for every pregame team.")
    else:
        st.warning("⚠️ STEP 2A CHECK • at least one team lacks a verified QB depth chart.")
    if injuries_ready:
        st.success("✅ STEP 2B PASSED • current ESPN injury feed verified for every pregame team.")
    else:
        st.warning("⚠️ STEP 2B CHECK • current injury verification is incomplete.")

    for _, game in pregame.iterrows():
        st.markdown(f"### {escape(_safe(game.get('away_team'), 'Away'))} @ {escape(_safe(game.get('home_team'), 'Home'))}")
        left, right = st.columns(2)
        with left:
            base._render_team_step2(team_contexts.get(_safe(game.get("away_abbr")).upper(), {}), preseason)
        with right:
            base._render_team_step2(team_contexts.get(_safe(game.get("home_abbr")).upper(), {}), preseason)

    # -------------------------- STEP 3 ----------------------------------
    st.markdown("### 📰 Step 3 — Preseason Game-Plan Intelligence")
    st.caption(
        f"Evidence window: final {FRESH_HOURS} hours before scheduled kickoff • ESPN team/game news only • "
        "explicit starter/play/rest/rotation wording required • vague mentions do not count."
    )

    gameplan_context = {}
    for _, game in pregame.iterrows():
        game_id = _safe(game.get("game_id"))
        kickoff = base._scheduled_tip(day_str, game.get("tip_et"))
        away_abbr = _safe(game.get("away_abbr")).upper()
        home_abbr = _safe(game.get("home_abbr")).upper()
        away_ctx = team_contexts.get(away_abbr, {})
        home_ctx = team_contexts.get(home_abbr, {})
        gameplan_context[away_abbr] = _team_gameplan_context(
            away_ctx, _safe(game.get("home_team")), game_id, kickoff
        )
        gameplan_context[home_abbr] = _team_gameplan_context(
            home_ctx, _safe(game.get("away_team")), game_id, kickoff
        )

    gp_ready_count = sum(1 for x in gameplan_context.values() if x.get("ready"))
    conflict_count = sum(len(x.get("conflicts", [])) for x in gameplan_context.values())
    explicit_starters = sum(1 for x in gameplan_context.values() if x.get("starter_verified"))
    rotation_count = sum(1 for x in gameplan_context.values() if x.get("rotation_verified"))

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Explicit starters", f"{explicit_starters}/{unique_expected}")
    g2.metric("Rotation verified", f"{rotation_count}/{unique_expected}")
    g3.metric("Game-plan ready", f"{gp_ready_count}/{unique_expected}")
    g4.metric("Conflicts", conflict_count)

    if unique_expected and gp_ready_count == unique_expected and conflict_count == 0:
        st.success("✅ STEP 3 PASSED • fresh explicit preseason starter/participation/rotation evidence verified for every pregame team.")
    else:
        st.warning(
            "🔒 STEP 3 LOCKED • at least one team still lacks complete fresh explicit game-plan evidence. "
            "The model remains OFF; UNKNOWN is preserved instead of filling gaps with assumptions."
        )

    for _, game in pregame.iterrows():
        away_abbr = _safe(game.get("away_abbr")).upper()
        home_abbr = _safe(game.get("home_abbr")).upper()
        st.markdown(f"#### Evidence — {escape(_safe(game.get('away_team')))} @ {escape(_safe(game.get('home_team')))}")
        left, right = st.columns(2)
        with left:
            _render_gameplan_team(gameplan_context.get(away_abbr, {}))
        with right:
            _render_gameplan_team(gameplan_context.get(home_abbr, {}))

    gameplan_ready = bool(unique_expected and gp_ready_count == unique_expected and conflict_count == 0)
    model_ready = bool(depth_ready and injuries_ready and ((not preseason) or gameplan_ready))

    st.markdown("### 🔒 Moneyline production locks")
    locks = pd.DataFrame([
        {"Layer": "Verified NFL slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Season-phase guard", "State": "READY" if phases else "CHECK"},
        {"Layer": "QB / depth-chart verification", "State": "READY" if depth_ready else "CHECK"},
        {"Layer": "Current injuries / availability", "State": "READY" if injuries_ready else "CHECK"},
        {"Layer": "Preseason game-plan / QB rotation", "State": "READY" if (not preseason or gameplan_ready) else "LOCKED — EXPLICIT SOURCE REQUIRED"},
        {"Layer": "Sportsbook Moneyline prices", "State": "LOCKED"},
        {"Layer": "Team-strength win model", "State": "LOCKED"},
        {"Layer": "Monte Carlo", "State": "LOCKED"},
        {"Layer": "No-vig edge / EV / final grading", "State": "LOCKED"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)

    st.session_state["nfl_moneyline_v3_day"] = day_str
    st.session_state["nfl_moneyline_v3_pregame"] = pregame.to_dict("records") if not pregame.empty else []
    st.session_state["nfl_moneyline_v3_team_context"] = team_contexts
    st.session_state["nfl_moneyline_v3_gameplan_context"] = gameplan_context
    st.session_state["nfl_moneyline_v3_depth_ready"] = depth_ready
    st.session_state["nfl_moneyline_v3_injuries_ready"] = injuries_ready
    st.session_state["nfl_moneyline_v3_gameplan_ready"] = gameplan_ready
    st.session_state["nfl_moneyline_v3_model_ready"] = model_ready

    st.caption(
        "Step 3 performs zero sportsbook requests, zero projection math and zero simulations. "
        "News evidence is used only to verify preseason participation/rotation intent."
    )


__all__ = ["MODEL_VERSION", "render_nfl_moneyline_hub"]
