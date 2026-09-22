"""MLB Pitcher Strikeouts O/U V1.0.5 — recursive nested Player Props parser.

Only changes the sportsbook ingestion layer for the isolated Pitcher K page.
The projection/workload/Monte Carlo engine remains V1.0.x unchanged.
"""
from __future__ import annotations

from collections import defaultdict
import re
import streamlit as st

import mlb_pitcher_k_hub_v104 as v104

engine = v104.engine
MODEL_VERSION = "Pitcher K V1.0.5"

_DESC_KEYS = {
    "name", "label", "key", "type", "title", "description", "category",
    "market", "marketname", "market_name", "group", "groupname", "group_name",
    "playername", "player_name", "participantname", "participant_name",
    "displayname", "display_name", "stat", "statistic", "prop", "propname",
    "prop_name", "bettype", "bet_type",
}
_LINE_KEYS = ("hdp", "line", "total", "points", "threshold", "max", "value")
_PRICE_KEYS = ("price", "odds", "decimal", "decimalOdds", "decimal_odds")


def _clean_text(x):
    return " ".join(str(x or "").replace("_", " ").replace("/", " ").split())


def _dict_descriptor(d):
    parts = []
    if not isinstance(d, dict):
        return ""
    for k, v in d.items():
        key = str(k or "").replace("-", "_").lower()
        if key in _DESC_KEYS and not isinstance(v, (dict, list, tuple)):
            s = _clean_text(v)
            if s:
                parts.append(s)
        elif key in {"participant", "player", "competitor", "athlete"} and isinstance(v, dict):
            for kk in ("name", "displayName", "display_name", "label"):
                s = _clean_text(v.get(kk))
                if s:
                    parts.append(s)
    return " | ".join(parts)


def _all_strings(obj, depth=0, max_depth=3):
    if depth > max_depth:
        return []
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list, tuple)):
                out.extend(_all_strings(v, depth + 1, max_depth))
            elif isinstance(v, str):
                s = _clean_text(v)
                if s:
                    out.append(s)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(_all_strings(v, depth + 1, max_depth))
    elif isinstance(obj, str):
        s = _clean_text(obj)
        if s:
            out.append(s)
    return out


def _is_strikeout_context(text):
    t = f" {_clean_text(text).lower()} "
    return (
        "strikeout" in t
        or "strike outs" in t
        or "strike-outs" in t
        or "pitcher ks" in t
        or "pitcher k " in t
        or "pitching strikeouts" in t
    )


def _match_pitcher(text, wanted):
    ntext = engine._norm_name(text)
    if not ntext:
        return None
    # Exact/contained normalized match. Prefer longest name to avoid surname collisions.
    for wn, original in sorted(wanted.items(), key=lambda kv: len(kv[0]), reverse=True):
        if wn and (wn == ntext or wn in ntext or ntext in wn):
            return original
    return None


def _num(v):
    return engine.sf(v)


def _line_from_dict(d):
    if not isinstance(d, dict):
        return None
    for k in _LINE_KEYS:
        if k in d:
            x = _num(d.get(k))
            if x is not None and 0 <= x <= 20:
                return float(x)
    # Sometimes the line is embedded in a label such as "Over 5.5".
    label = _dict_descriptor(d)
    m = re.search(r"(?:over|under|o|u)\s*([0-9]+(?:\.[05])?)\b", label, flags=re.I)
    if m:
        try:
            x = float(m.group(1))
            if 0 <= x <= 20:
                return x
        except Exception:
            pass
    return None


def _price_from_dict(d):
    if not isinstance(d, dict):
        return None
    for k in _PRICE_KEYS:
        if k in d:
            x = _num(d.get(k))
            if x is not None:
                return x
    return None


def _side_from_dict(d):
    if not isinstance(d, dict):
        return None
    text = " ".join(_all_strings(d, max_depth=1)).lower()
    # Keep this strict so player names containing words do not create false sides.
    if re.search(r"\bover\b", text):
        return "over"
    if re.search(r"\bunder\b", text):
        return "under"
    for k in ("side", "designation", "outcomeType", "outcome_type"):
        s = str(d.get(k) or "").lower().strip()
        if s in {"over", "o"}:
            return "over"
        if s in {"under", "u"}:
            return "under"
    return None


def _walk_nodes(obj, parent_ctx="", depth=0, max_depth=10):
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        own = _dict_descriptor(obj)
        ctx = " | ".join(x for x in (parent_ctx, own) if x)
        yield obj, ctx
        for v in obj.values():
            if isinstance(v, (dict, list, tuple)):
                yield from _walk_nodes(v, ctx, depth + 1, max_depth)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_nodes(v, parent_ctx, depth + 1, max_depth)


def _extract_book_quotes(book, markets, pitcher_names):
    wanted = {engine._norm_name(x): x for x in pitcher_names if x}
    buckets = defaultdict(lambda: {"over": None, "under": None, "updatedAt": None})
    if not wanted:
        return {}

    root = markets
    for node, ctx in _walk_nodes(root):
        # Generic Player Props is the parent; nested children must carry strikeout context.
        subtree_strings = " | ".join(_all_strings(node, max_depth=2))
        combined = " | ".join(x for x in (ctx, subtree_strings) if x)
        if not _is_strikeout_context(combined):
            continue

        pitcher = _match_pitcher(combined, wanted)
        if not pitcher:
            continue

        # Parent-shaped quote: line plus explicit over/under fields.
        line = _line_from_dict(node)
        over = _num(node.get("over")) if isinstance(node, dict) else None
        under = _num(node.get("under")) if isinstance(node, dict) else None
        updated = None
        if isinstance(node, dict):
            updated = node.get("updatedAt") or node.get("updated_at") or node.get("lastUpdate")
        if line is not None and (over is not None or under is not None):
            key = (pitcher, float(line))
            if over is not None:
                buckets[key]["over"] = over
            if under is not None:
                buckets[key]["under"] = under
            buckets[key]["updatedAt"] = updated or buckets[key]["updatedAt"]

        # Child/outcome-shaped quote: side + price + line in this node or nearby label.
        side = _side_from_dict(node)
        price = _price_from_dict(node)
        if side and price is not None:
            if line is None:
                # Check immediate nested outcome labels for a numeric threshold.
                for child_key in ("outcomes", "odds", "selections", "options", "prices"):
                    children = node.get(child_key) if isinstance(node, dict) else None
                    if isinstance(children, list):
                        for child in children:
                            if isinstance(child, dict):
                                line = _line_from_dict(child)
                                if line is not None:
                                    break
                    if line is not None:
                        break
            if line is not None:
                key = (pitcher, float(line))
                buckets[key][side] = price
                buckets[key]["updatedAt"] = updated or buckets[key]["updatedAt"]

        # Common grouped structure: parent has player/stat and children are Over/Under.
        if isinstance(node, dict):
            parent_line = line
            for child_key in ("outcomes", "odds", "selections", "options", "prices"):
                children = node.get(child_key)
                if not isinstance(children, list):
                    continue
                for child in children:
                    if not isinstance(child, dict):
                        continue
                    side = _side_from_dict(child)
                    if not side:
                        continue
                    child_line = _line_from_dict(child)
                    use_line = child_line if child_line is not None else parent_line
                    price = _price_from_dict(child)
                    if use_line is None or price is None:
                        continue
                    key = (pitcher, float(use_line))
                    buckets[key][side] = price
                    buckets[key]["updatedAt"] = (
                        child.get("updatedAt") or child.get("updated_at") or updated or buckets[key]["updatedAt"]
                    )

    out = {p: [] for p in wanted.values()}
    for (pitcher, line), q in buckets.items():
        # A line is useful even if one side price is absent; the model can still grade it.
        out[pitcher].append({
            "book": str(book),
            "line": float(line),
            "over_dec": q.get("over"),
            "under_dec": q.get("under"),
            "updatedAt": q.get("updatedAt"),
        })
    return out


def _parse_props(payload, pitcher_names):
    wanted_names = [x for x in pitcher_names if x]
    merged = {x: [] for x in wanted_names}
    books = (payload or {}).get("bookmakers") or {}
    if not isinstance(books, dict):
        return merged
    for book, markets in books.items():
        parsed = _extract_book_quotes(book, markets, wanted_names)
        for pitcher, quotes in parsed.items():
            merged.setdefault(pitcher, []).extend(quotes)
    return merged


def _nested_diagnostic(payload, pitcher_names):
    wanted = {engine._norm_name(x): x for x in pitcher_names if x}
    rows = []
    books = (payload or {}).get("bookmakers") or {}
    if not isinstance(books, dict):
        return rows
    for book, markets in books.items():
        for node, ctx in _walk_nodes(markets):
            strings = " | ".join(_all_strings(node, max_depth=1))
            combined = " | ".join(x for x in (ctx, strings) if x)
            if _is_strikeout_context(combined):
                pitcher = _match_pitcher(combined, wanted)
                line = _line_from_dict(node)
                side = _side_from_dict(node)
                if pitcher or line is not None:
                    rows.append(f"{book} | {pitcher or 'unmatched'} | line={line} | side={side or '—'} | {combined[:220]}")
            if len(rows) >= 80:
                return rows
    return rows

# Patch only the parser used by V1.0.4's existing event fetcher.
v104._parse_props = _parse_props
engine._parse_props = _parse_props
engine._fetch_market_lines = v104._fetch


def render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h):
    result = v104.v103.render_pitcher_k_hub(games_df, section_header, status_info, team_logo, h)
    meta = st.session_state.get("pk10_market_meta") or {}
    if meta.get("connected"):
        props = int(meta.get("props") or 0)
        if props > 0:
            st.success(f"🎯 Pitcher K sportsbook parser • {props} pitcher market(s) matched from {meta.get('events', 0)} event(s).")
        else:
            st.caption("Nested Player Props parser ran, but no usable pitcher-strikeout lines were returned. Manual line grading remains available.")
    return result
