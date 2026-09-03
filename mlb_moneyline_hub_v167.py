"""MLB Moneyline V16.7 — Step 2 starting-pitcher quality.

Presentation/evidence wrapper over frozen V16.6. Adds official MLB starter-quality
information to Top-5 Moneyline cards without changing candidate selection, ranking,
probability, simulation, fair odds, market math, or the frozen Step 1 contract.

Fail-closed: unavailable/insufficient official data produces DATA LIMITED / PENDING
and Step 2 contributes no numerical adjustment.
"""
from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st
import mlb_moneyline_hub_v166 as prior

MODEL_VERSION = "V16.7 • MONEYLINE STEP 2 • STARTING PITCHER QUALITY"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v166"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN
SEASON = 2026

_STEP2_CSS = r"""
<style>
.ml167-step2{grid-area:identity;margin-top:7px;padding:10px 11px;border:1px solid rgba(91,140,166,.28);border-radius:13px;background:linear-gradient(145deg,rgba(8,22,34,.96),rgba(7,17,27,.96));box-shadow:inset 3px 0 #9b7cff}
.ml167-step2-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml167-step2-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#c2b0ff}
.ml167-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #47596a;background:#16212c;color:#c8d4de}
.ml167-grade.elite{border-color:#277353;background:#0a3024;color:#83e7b6}.ml167-grade.strong{border-color:#3d7259;background:#0d2a20;color:#9de6be}.ml167-grade.neutral{border-color:#77611c;background:#342b0d;color:#f5db73}.ml167-grade.limited{border-color:#59636c;background:#222a30;color:#d5dde2}
.ml167-pitchers{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px}.ml167-pitcher{border:1px solid rgba(91,140,166,.20);border-radius:9px;background:rgba(5,16,26,.72);padding:8px;color:#a9bac5;font-size:.49rem;line-height:1.4}.ml167-pitcher.home{text-align:right}.ml167-pitcher b{display:block;color:#f0f6fa;font-size:.64rem;line-height:1.2;margin-bottom:4px}.ml167-pitcher small{color:#778d9b;font-size:.45rem}
.ml167-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin-top:7px}.ml167-stat{border:1px solid rgba(91,140,166,.18);border-radius:8px;padding:6px 5px;background:#091722;text-align:center}.ml167-stat b{display:block;color:#e5eef3;font-size:.58rem}.ml167-stat span{display:block;color:#728795;font-size:.42rem;margin-top:2px;text-transform:uppercase;letter-spacing:.03em}.ml167-pill{display:inline-flex;align-items:center;border:1px solid rgba(91,140,166,.24);background:#0a1825;color:#b9cad6;border-radius:999px;padding:4px 7px;font-size:.48rem;font-weight:850;margin-top:7px;margin-right:4px}.ml167-pill.edge{border-color:#396b55;background:#0b291f;color:#91dfb5}.ml167-pill.away{border-color:#4a62a0;background:#101c38;color:#a9c2ff}.ml167-pill.neutral{border-color:#77611c;background:#30280d;color:#f3d977}.ml167-source{margin-top:6px;color:#708696;font-size:.43rem;line-height:1.4}
@media(max-width:640px){.ml167-pitchers{grid-template-columns:1fr}.ml167-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.ml167-pitcher.home{text-align:left}.ml167-step2{padding:9px}}
</style>
"""


def _f(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() in {"", "N/A", "NA", "null", "—"}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _ip(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        whole, _, frac = text.partition(".")
        if frac in {"0", "1", "2"}:
            return float(whole) + {"0": 0.0, "1": 1 / 3, "2": 2 / 3}[frac]
        return float(value)
    except (TypeError, ValueError):
        return _f(value)


def _json(url: str) -> dict[str, Any] | None:
    try:
        req = Request(url, headers={"User-Agent": "KyreSportsAI/16.7"})
        with urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def _game_feed(game_pk: int) -> dict[str, Any] | None:
    return _json(f"https://statsapi.mlb.com/api/v1.1/game/{int(game_pk)}/feed/live")


@st.cache_data(ttl=600, show_spinner=False)
def _stats(person_id: int) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    base = "https://statsapi.mlb.com/api/v1/people/{}/stats?{}"
    season_q = urlencode({"stats": "season", "group": "pitching", "season": SEASON})
    log_q = urlencode({"stats": "gameLog", "group": "pitching", "season": SEASON})
    season_data = _json(base.format(int(person_id), season_q)) or {}
    log_data = _json(base.format(int(person_id), log_q)) or {}
    season = None
    logs: list[dict[str, Any]] = []
    try:
        splits = season_data.get("stats", [])[0].get("splits", [])
        season = dict(splits[0].get("stat") or {}) if splits else None
    except Exception:
        pass
    try:
        splits = log_data.get("stats", [])[0].get("splits", [])
        logs = [dict(x.get("stat") or {}) for x in splits if isinstance(x, dict)]
    except Exception:
        pass
    return season, logs


def _probables(game_pk: int) -> dict[str, dict[str, Any]]:
    feed = _game_feed(game_pk)
    if not feed:
        return {}
    probable = ((feed.get("gameData") or {}).get("probablePitchers") or {})
    out: dict[str, dict[str, Any]] = {}
    for side in ("away", "home"):
        p = probable.get(side) or {}
        pid = _i(p.get("id"))
        if pid:
            out[side] = {"id": pid, "name": str(p.get("fullName") or "TBD")}
    return out


def _fip(s: Mapping[str, Any]) -> float | None:
    hr = _f(s.get("homeRuns")); bb = _f(s.get("baseOnBalls")); hbp = _f(s.get("hitByPitch")) or 0
    so = _f(s.get("strikeOuts")); ip = _ip(s.get("inningsPitched"))
    if None in (hr, bb, so, ip) or ip <= 0:
        return None
    return ((13 * hr) + 3 * (bb + hbp) - 2 * so) / ip + 3.10


def _recent(logs: list[dict[str, Any]], n: int = 5) -> dict[str, Any]:
    rows = [x for x in logs if _ip(x.get("inningsPitched")) is not None][-n:]
    if not rows:
        return {"starts": 0, "ip": None, "era": None, "whip": None, "fip": None}
    ip = sum(_ip(x.get("inningsPitched")) or 0 for x in rows)
    er = sum(_f(x.get("earnedRuns")) or 0 for x in rows)
    h = sum(_f(x.get("hits")) or 0 for x in rows)
    bb = sum(_f(x.get("baseOnBalls")) or 0 for x in rows)
    hr = sum(_f(x.get("homeRuns")) or 0 for x in rows)
    hbp = sum(_f(x.get("hitByPitch")) or 0 for x in rows)
    so = sum(_f(x.get("strikeOuts")) or 0 for x in rows)
    return {"starts": len(rows), "ip": ip, "era": er * 9 / ip, "whip": (h + bb) / ip, "fip": ((13 * hr) + 3 * (bb + hbp) - 2 * so) / ip + 3.10}


def _rate(s: Mapping[str, Any], num: str, den: str, scale: float = 1) -> float | None:
    a, b = _f(s.get(num)), _ip(s.get(den))
    return a / b * scale if a is not None and b and b > 0 else None


def _quality(s: Mapping[str, Any] | None, recent: Mapping[str, Any]) -> tuple[float | None, dict[str, Any]]:
    if not s:
        return None, {}
    era, whip, fip = _f(s.get("era")), _f(s.get("whip")), _fip(s)
    so9 = _rate(s, "strikeOuts", "inningsPitched", 9)
    bb9 = _rate(s, "baseOnBalls", "inningsPitched", 9)
    hr9 = _rate(s, "homeRuns", "inningsPitched", 9)
    bf, so, bb = _f(s.get("battersFaced")), _f(s.get("strikeOuts")), _f(s.get("baseOnBalls"))
    kp = so / bf * 100 if so is not None and bf and bf > 0 else None
    bp = bb / bf * 100 if bb is not None and bf and bf > 0 else None
    metrics = {"era": era, "whip": whip, "fip": fip, "so9": so9, "bb9": bb9, "hr9": hr9, "k_pct": kp, "bb_pct": bp, "ip": _ip(s.get("inningsPitched")), "recent": recent}
    components: list[float] = []
    if era is not None: components.append(max(0, min(100, 100 - era * 18)))
    if whip is not None: components.append(max(0, min(100, 100 - max(0, whip - .85) * 90))
    if fip is not None: components.append(max(0, min(100, 100 - fip * 18)))
    if so9 is not None: components.append(max(0, min(100, so9 * 10)))
    if bb9 is not None: components.append(max(0, min(100, 100 - bb9 * 22)))
    if hr9 is not None: components.append(max(0, min(100, 100 - hr9 * 30)))
    if recent.get("era") is not None: components.append(max(0, min(100, 100 - float(recent["era"]) * 15)))
    return (sum(components) / len(components), metrics) if len(components) >= 4 else (None, metrics)


def _grade(diff: float | None) -> tuple[str, str]:
    if diff is None: return "DATA LIMITED / PENDING", "limited"
    if diff >= 15: return "ELITE HOME STARTER EDGE", "elite"
    if diff >= 7: return "STRONG HOME STARTER EDGE", "strong"
    if diff <= -15: return "ELITE AWAY STARTER EDGE", "elite"
    if diff <= -7: return "STRONG AWAY STARTER EDGE", "strong"
    return "NEUTRAL", "neutral"


def _ctx(result: Mapping[str, Any]) -> dict[str, Any]:
    pk = _i(result.get("game_pk"))
    if not pk:
        return {"grade": "DATA LIMITED / PENDING", "grade_cls": "limited", "reason": "No verified MLB game PK available."}
    probs = _probables(pk)
    if not probs:
        return {"grade": "DATA LIMITED / PENDING", "grade_cls": "limited", "reason": "Official MLB probable-starter data unavailable."}
    blocks: dict[str, Any] = {}
    for side in ("away", "home"):
        p = probs.get(side)
        if not p:
            blocks[side] = {"name": "TBD", "score": None, "metrics": {}, "recent": {}}
            continue
        season, logs = _stats(p["id"])
        rec = _recent(logs)
        score, metrics = _quality(season, rec)
        blocks[side] = {"id": p["id"], "name": p["name"], "score": score, "metrics": metrics, "recent": rec}
    away, home = blocks["away"], blocks["home"]
    edge = home["score"] - away["score"] if away.get("score") is not None and home.get("score") is not None else None
    grade, grade_cls = _grade(edge)
    return {"grade": grade, "grade_cls": grade_cls, "away": away, "home": home, "edge": edge, "reason": "" if edge is not None else "Both starters need sufficient official MLB evidence before grading."}


def _fmt(v: Any, d: int = 2, suffix: str = "") -> str:
    return f"{float(v):.{d}f}{suffix}" if v is not None else "N/A"


def _html(c: Mapping[str, Any]) -> str:
    def block(p: Mapping[str, Any], home: bool) -> str:
        m, r = p.get("metrics") or {}, p.get("recent") or {}
        score = "N/A" if p.get("score") is None else f"{float(p.get('score')):.0f}/100"
        return (f'<div class="ml167-pitcher {"home" if home else ""}"><b>{escape(str(p.get("name") or "TBD"))}</b>'
                f'<small>Evidence score {score}</small>'
                f'<div class="ml167-stats"><div class="ml167-stat"><b>{_fmt(m.get("era"))}</b><span>ERA</span></div><div class="ml167-stat"><b>{_fmt(m.get("whip"))}</b><span>WHIP</span></div><div class="ml167-stat"><b>{_fmt(m.get("fip"))}</b><span>FIP</span></div><div class="ml167-stat"><b>{_fmt(m.get("k_pct"),1,"%")}</b><span>K%</span></div></div>'
                f'<div class="ml167-stats"><div class="ml167-stat"><b>{_fmt(m.get("bb_pct"),1,"%")}</b><span>BB%</span></div><div class="ml167-stat"><b>{_fmt(m.get("hr9"))}</b><span>HR/9</span></div><div class="ml167-stat"><b>{_fmt(r.get("era"))}</b><span>L5 ERA</span></div><div class="ml167-stat"><b>{_fmt(r.get("ip"),1)}</b><span>L5 IP</span></div></div></div>')
    edge = c.get("edge")
    label = "HOME STARTER EDGE" if edge is not None and edge > 0 else "AWAY STARTER EDGE" if edge is not None and edge < 0 else "STARTER QUALITY NEUTRAL"
    value = f"{abs(float(edge)):.1f} pts" if edge is not None else "N/A"
    pill_cls = "edge" if edge is not None and edge > 0 else "away" if edge is not None and edge < 0 else "neutral"
    return (f'<div class="ml167-step2"><div class="ml167-step2-head"><span class="ml167-step2-title">STEP 2 • STARTING PITCHER QUALITY</span><span class="ml167-grade {escape(str(c.get("grade_cls") or "limited"))}">{escape(str(c.get("grade") or "DATA LIMITED / PENDING"))}</span></div>'
            f'<div class="ml167-pitchers">{block(c.get("away") or {},False)}{block(c.get("home") or {},True)}</div>'
            f'<span class="ml167-pill {pill_cls}">{escape(label)} • {escape(value)}</span><span class="ml167-pill neutral">xERA • N/A unless officially supplied</span>'
            f'<div class="ml167-source">Official MLB Stats API • {SEASON} season + last 5 logged appearances. Evidence-only: no Moneyline probability adjustment. {escape(str(c.get("reason") or ""))}</div></div>')


def _inject(card: str, html: str) -> str:
    text = str(card or "")
    if not html or "ks-pick-card" not in text or "ml167-step2" in text:
        return text
    return text[:-6] + html + "</div>" if text.endswith("</div>") else text + html


# Critical recursion fix: capture the original frozen V16.6 factory BEFORE patching it.
_FROZEN_CARD_FACTORY = prior._card_renderer_with_step1


def _renderer(original, rows, lineups):
    step1 = _FROZEN_CARD_FACTORY(original, rows, lineups)

    def wrapped(results, status_info, team_logo, h):
        ordered = list(results or [])[:5]
        cursor = {"i": 0}
        original_markdown = st.markdown

        def capture(body: Any, *args: Any, **kwargs: Any):
            text = str(body or "")
            if "ks-pick-card" in text and cursor["i"] < len(ordered):
                text = _inject(text, _html(_ctx(ordered[cursor["i"]])))
                cursor["i"] += 1
            return original_markdown(text, *args, **kwargs)

        st.markdown = capture
        try:
            return step1(results, status_info, team_logo, h)
        finally:
            st.markdown = original_markdown

    return wrapped


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Render frozen V16.6 plus presentation-only Step 2 starter evidence."""
    st.markdown(_STEP2_CSS, unsafe_allow_html=True)
    original_factory = prior._card_renderer_with_step1
    prior._card_renderer_with_step1 = _renderer
    try:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior._card_renderer_with_step1 = original_factory


__all__ = ["MODEL_VERSION", "FROZEN_MODEL_CHAIN", "FROZEN_MONEYLINE_PRESENTATION", "render_moneyline_hub"]
