"""V20.5 sportsbook normalization for Slate cards.

Builds on V20.3 but prevents obviously incompatible/partial-game total lines
from being compared as if they were the same full-game market. Best prices are
only compared at matching lines.
"""

from collections import Counter

import numpy as np

from slate_odds_feed_v203 import slate_snapshots_for_games_v203


def _valid_full_game_total_rows(rows):
    rows = [dict(r) for r in (rows or [])]
    posted = [float(r["total_line"]) for r in rows if r.get("total_line") is not None]
    if not posted:
        return rows, []

    # MLB full-game totals normally live in this broad range. Do not discard an
    # unusual line if it is the only line posted, but if another book has a
    # plausible full-game line, suppress extreme alternate/partial candidates.
    plausible = [x for x in posted if 6.0 <= x <= 13.5]
    filtered = []
    warnings = []
    for r in rows:
        line = r.get("total_line")
        if line is None:
            filtered.append(r)
            continue
        line = float(line)
        if plausible and not (6.0 <= line <= 13.5):
            warnings.append(f"{r.get('Book')}: O/U {line:g} excluded from full-game consensus")
            r["total_line"] = None
            r["over_price"] = None
            r["under_price"] = None
            r["Over"] = None
            r["Under"] = None
            r["total_filtered"] = True
        filtered.append(r)
    return filtered, warnings


def _line_groups(rows, field):
    groups = {}
    for r in rows:
        line = r.get(field)
        if line is None:
            continue
        key = round(float(line), 4)
        groups.setdefault(key, []).append(r)
    return groups


def _best_price_at_exact_line(rows, line, price_field):
    if line is None:
        return None
    candidates = []
    for r in rows:
        if r.get("total_line") is None or r.get(price_field) is None:
            continue
        if abs(float(r["total_line"]) - float(line)) <= 1e-6:
            candidates.append((int(r[price_field]), str(r.get("Book"))))
    if not candidates:
        return None
    price, book = max(candidates, key=lambda x: x[0])
    return {"line": float(line), "price": int(price), "book": book}


def _choose_total_line(rows):
    groups = _line_groups(rows, "total_line")
    if not groups:
        return None, "not_posted"
    counts = Counter({line: len(items) for line, items in groups.items()})
    max_count = max(counts.values())
    leaders = sorted([line for line, count in counts.items() if count == max_count])
    if max_count >= 2:
        # True cross-book consensus: at least two books are pricing the same line.
        return float(np.median(leaders)), "consensus"
    if len(groups) == 1:
        return float(next(iter(groups))), "single_book"
    # Multiple books posted different totals. Do not pretend those prices are
    # directly comparable; show the split on the card instead.
    return None, "split"


def _normalize_snapshot(snapshot):
    rows, warnings = _valid_full_game_total_rows(snapshot.get("rows") or [])
    snapshot["rows"] = rows
    total_line, total_status = _choose_total_line(rows)
    snapshot["total_market_status"] = total_status
    snapshot["total_warnings"] = warnings
    snapshot["total_lines_by_book"] = {
        str(r.get("Book")): float(r["total_line"])
        for r in rows
        if r.get("total_line") is not None
    }

    best = dict(snapshot.get("best") or {})
    best["consensus_total"] = total_line
    best["over"] = _best_price_at_exact_line(rows, total_line, "over_price")
    best["under"] = _best_price_at_exact_line(rows, total_line, "under_price")
    snapshot["best"] = best
    return snapshot


def slate_snapshots_for_games_v205(games_df, api_key, bookmakers):
    snapshots = slate_snapshots_for_games_v203(games_df, api_key, bookmakers)
    return {pk: _normalize_snapshot(snap) for pk, snap in snapshots.items()}
