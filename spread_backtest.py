from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

ET = ZoneInfo("America/New_York")
MLB_LIVE_API = "https://statsapi.mlb.com/api/v1.1"
HISTORY_PATH = Path("spread_prediction_history.csv")
MODEL_VERSION = "V15.3"

HISTORY_COLUMNS = [
    "prediction_key",
    "scan_id",
    "created_at_et",
    "game_date",
    "model_version",
    "source",
    "rank",
    "game_pk",
    "selected_side",
    "team_id",
    "team",
    "opponent",
    "line",
    "core_cover",
    "history_adjustment",
    "predicted_cover",
    "fair_odds",
    "win_prob",
    "projected_margin",
    "projected_away_runs",
    "projected_home_runs",
    "confidence",
    "data_score",
    "simulations",
    "mc_se",
    "batch_spread",
    "h2h_games",
    "h2h_record",
    "h2h_cover_rate",
    "h2h_avg_margin",
    "venue_record",
    "game_status",
    "grade_status",
    "actual_away_runs",
    "actual_home_runs",
    "actual_selected_margin",
    "actual_cover",
    "actual_push",
    "graded_at_et",
]


def _now_et():
    return datetime.now(ET)


def _empty_history():
    return pd.DataFrame(columns=HISTORY_COLUMNS)


def _prediction_key(game_pk, model_version=MODEL_VERSION):
    # One clean first pregame snapshot per game/model version.
    return f"{int(game_pk)}:{model_version}"


def load_spread_history():
    if not HISTORY_PATH.exists():
        return _empty_history()
    try:
        df = pd.read_csv(HISTORY_PATH)
    except Exception:
        return _empty_history()

    for col in HISTORY_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    return df[HISTORY_COLUMNS]


def _write_history(df):
    out = df.copy()
    for col in HISTORY_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    out[HISTORY_COLUMNS].to_csv(HISTORY_PATH, index=False)


def append_spread_records(records):
    if not records:
        current = load_spread_history()
        return 0, len(current)

    current = load_spread_history()
    incoming = pd.DataFrame(records)

    for col in HISTORY_COLUMNS:
        if col not in incoming.columns:
            incoming[col] = np.nan
    incoming = incoming[HISTORY_COLUMNS]

    existing = set(current["prediction_key"].dropna().astype(str))
    incoming = incoming[~incoming["prediction_key"].astype(str).isin(existing)].copy()

    if incoming.empty:
        return 0, len(current)

    merged = pd.concat([current, incoming], ignore_index=True)
    merged = merged.drop_duplicates(subset=["prediction_key"], keep="first")
    _write_history(merged)
    return len(incoming), len(merged)


def save_spread_scan(results, model_version=MODEL_VERSION):
    if not results:
        return 0, len(load_spread_history()), None

    now = _now_et()
    scan_id = now.strftime("%Y%m%dT%H%M%S")
    rows = []

    for rank, result in enumerate(results, 1):
        history = result.get("history") or {}
        summary = history.get("summary") or {}
        side = result.get("selected_side")
        if side not in ("home", "away"):
            side = "home" if result.get("team") == result.get("home_name") else "away"

        rows.append(
            {
                "prediction_key": _prediction_key(result["game_pk"], model_version),
                "scan_id": scan_id,
                "created_at_et": now.isoformat(),
                "game_date": now.strftime("%Y-%m-%d"),
                "model_version": model_version,
                "source": "daily_spread_scanner",
                "rank": rank,
                "game_pk": int(result["game_pk"]),
                "selected_side": side,
                "team_id": result.get("team_id"),
                "team": result.get("team"),
                "opponent": result.get("opponent"),
                "line": result.get("line"),
                "core_cover": result.get("core_cover"),
                "history_adjustment": result.get("history_adjustment"),
                "predicted_cover": result.get("cover"),
                "fair_odds": result.get("fair_odds"),
                "win_prob": result.get("win_prob"),
                "projected_margin": result.get("projected_margin"),
                "projected_away_runs": result.get("away_score"),
                "projected_home_runs": result.get("home_score"),
                "confidence": result.get("confidence"),
                "data_score": result.get("data_score"),
                "simulations": result.get("simulations"),
                "mc_se": result.get("mc_se"),
                "batch_spread": result.get("batch_spread"),
                "h2h_games": summary.get("games"),
                "h2h_record": (
                    f'{summary.get("wins", 0)}-{summary.get("losses", 0)}'
                    if summary.get("games")
                    else "N/A"
                ),
                "h2h_cover_rate": summary.get("raw_cover_rate"),
                "h2h_avg_margin": summary.get("avg_margin"),
                "venue_record": summary.get("venue_record"),
                "game_status": result.get("status", "Scheduled"),
                "grade_status": "PENDING",
            }
        )

    added, total = append_spread_records(rows)
    return added, total, scan_id


def _fetch_feed(game_pk):
    response = requests.get(
        f"{MLB_LIVE_API}/game/{int(game_pk)}/feed/live",
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _game_status(feed):
    status = (feed.get("gameData", {}) or {}).get("status", {}) or {}
    return (
        str(status.get("abstractGameState", "")),
        str(status.get("detailedState", "")),
    )


def _final_score(feed):
    linescore = (feed.get("liveData", {}) or {}).get("linescore", {}) or {}
    teams = linescore.get("teams", {}) or {}
    away = (teams.get("away", {}) or {}).get("runs")
    home = (teams.get("home", {}) or {}).get("runs")

    if away is None or home is None:
        box = (feed.get("liveData", {}) or {}).get("boxscore", {}) or {}
        box_teams = box.get("teams", {}) or {}
        away = ((box_teams.get("away", {}) or {}).get("teamStats", {}) or {}).get("batting", {}).get("runs")
        home = ((box_teams.get("home", {}) or {}).get("teamStats", {}) or {}).get("batting", {}).get("runs")

    if away is None or home is None:
        return None
    return int(away), int(home)


def grade_spread_games():
    df = load_spread_history()
    summary = {
        "graded": 0,
        "push": 0,
        "void": 0,
        "still_pending": 0,
        "errors": 0,
    }
    if df.empty:
        return summary

    pending = df[df["grade_status"].fillna("PENDING").eq("PENDING")]
    if pending.empty:
        return summary

    feeds = {}
    for game_pk in pending["game_pk"].dropna().astype(int).unique():
        try:
            feeds[game_pk] = _fetch_feed(game_pk)
        except Exception:
            feeds[game_pk] = None
            summary["errors"] += 1

    now = _now_et().isoformat()

    for idx, row in pending.iterrows():
        game_pk = int(row["game_pk"])
        feed = feeds.get(game_pk)
        if feed is None:
            continue

        abstract, detailed = _game_status(feed)
        low = detailed.lower()

        if any(token in low for token in ("cancel", "postpon", "suspend")):
            df.at[idx, "grade_status"] = "VOID"
            df.at[idx, "game_status"] = detailed or abstract
            df.at[idx, "graded_at_et"] = now
            summary["void"] += 1
            continue

        if abstract.lower() != "final" and "final" not in low and "game over" not in low:
            summary["still_pending"] += 1
            continue

        score = _final_score(feed)
        if score is None:
            summary["errors"] += 1
            continue

        away_runs, home_runs = score
        selected_side = str(row.get("selected_side", "")).lower()
        margin = home_runs - away_runs if selected_side == "home" else away_runs - home_runs
        line = float(row.get("line", 0.0) or 0.0)
        settle = margin + line

        actual_cover = 1 if settle > 1e-9 else 0
        actual_push = 1 if abs(settle) <= 1e-9 else 0

        df.at[idx, "actual_away_runs"] = away_runs
        df.at[idx, "actual_home_runs"] = home_runs
        df.at[idx, "actual_selected_margin"] = margin
        df.at[idx, "actual_cover"] = actual_cover
        df.at[idx, "actual_push"] = actual_push
        df.at[idx, "game_status"] = detailed or "Final"
        df.at[idx, "graded_at_et"] = now

        if actual_push:
            df.at[idx, "grade_status"] = "PUSH"
            summary["push"] += 1
        else:
            df.at[idx, "grade_status"] = "GRADED"
            summary["graded"] += 1

    _write_history(df)
    return summary


def graded_spread_history(df=None):
    df = load_spread_history() if df is None else df
    if df.empty:
        return df

    out = df[df["grade_status"].isin(["GRADED", "PUSH"])].copy()
    if out.empty:
        return out

    numeric = [
        "predicted_cover",
        "core_cover",
        "history_adjustment",
        "actual_cover",
        "actual_push",
        "rank",
        "line",
    ]
    for col in numeric:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def spread_metrics(df=None):
    g = graded_spread_history(df)
    if g.empty:
        return {
            "graded": 0,
            "wins": 0,
            "losses": 0,
            "pushes": 0,
            "cover_rate": np.nan,
            "avg_prediction": np.nan,
            "brier_final": np.nan,
            "brier_core": np.nan,
            "h2h_brier_delta": np.nan,
            "calibration_gap": np.nan,
            "log_loss": np.nan,
        }

    pushes = int(g["actual_push"].fillna(0).sum())
    settled = g[g["actual_push"].fillna(0).eq(0)].copy()
    if settled.empty:
        return {
            "graded": 0,
            "wins": 0,
            "losses": 0,
            "pushes": pushes,
            "cover_rate": np.nan,
            "avg_prediction": np.nan,
            "brier_final": np.nan,
            "brier_core": np.nan,
            "h2h_brier_delta": np.nan,
            "calibration_gap": np.nan,
            "log_loss": np.nan,
        }

    p = settled["predicted_cover"].clip(1e-6, 1 - 1e-6).astype(float)
    pc = settled["core_cover"].clip(1e-6, 1 - 1e-6).astype(float)
    y = settled["actual_cover"].astype(float)
    brier_final = float(np.mean((p - y) ** 2))
    brier_core = float(np.mean((pc - y) ** 2))

    wins = int(y.sum())
    losses = int(len(y) - wins)
    return {
        "graded": len(settled),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "cover_rate": float(y.mean()),
        "avg_prediction": float(p.mean()),
        "brier_final": brier_final,
        "brier_core": brier_core,
        # Positive means history/H2H improved Brier vs the core model.
        "h2h_brier_delta": brier_core - brier_final,
        "calibration_gap": float(y.mean() - p.mean()),
        "log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
    }


def spread_calibration_table(df=None):
    g = graded_spread_history(df)
    if g.empty:
        return pd.DataFrame(
            columns=[
                "Probability Tier",
                "Picks",
                "Avg Projected",
                "Actual Cover",
                "Calibration Gap",
                "Brier",
            ]
        )

    g = g[g["actual_push"].fillna(0).eq(0)].copy()
    if g.empty:
        return pd.DataFrame()

    bins = [0.0, 0.55, 0.60, 0.65, 0.70, 1.000001]
    labels = ["<55%", "55–59.9%", "60–64.9%", "65–69.9%", "70%+"]
    g["tier"] = pd.cut(
        g["predicted_cover"],
        bins=bins,
        labels=labels,
        include_lowest=True,
        right=False,
    )

    rows = []
    for label in labels:
        group = g[g["tier"].astype(str) == label]
        if group.empty:
            continue
        p = group["predicted_cover"].astype(float)
        y = group["actual_cover"].astype(float)
        rows.append(
            {
                "Probability Tier": label,
                "Picks": len(group),
                "Avg Projected": f"{p.mean() * 100:.1f}%",
                "Actual Cover": f"{y.mean() * 100:.1f}%",
                "Calibration Gap": f"{(y.mean() - p.mean()) * 100:+.1f} pts",
                "Brier": f"{np.mean((p - y) ** 2):.3f}",
            }
        )
    return pd.DataFrame(rows)


def spread_rank_performance(df=None):
    g = graded_spread_history(df)
    if g.empty:
        return pd.DataFrame(columns=["Rank", "Picks", "Record", "Cover Rate", "Avg Projection"])

    g = g[g["actual_push"].fillna(0).eq(0)].copy()
    rows = []
    for rank, group in g.groupby("rank"):
        y = group["actual_cover"].astype(float)
        p = group["predicted_cover"].astype(float)
        wins = int(y.sum())
        losses = len(y) - wins
        rows.append(
            {
                "Rank": int(rank) if pd.notna(rank) else "N/A",
                "Picks": len(group),
                "Record": f"{wins}-{losses}",
                "Cover Rate": f"{y.mean() * 100:.1f}%",
                "Avg Projection": f"{p.mean() * 100:.1f}%",
            }
        )
    return pd.DataFrame(rows).sort_values("Rank")


def top_spread_performance(df=None):
    g = graded_spread_history(df)
    if g.empty:
        return {"top5": 0, "top5_rate": np.nan, "number1": 0, "number1_rate": np.nan}

    settled = g[g["actual_push"].fillna(0).eq(0)].copy()
    top5 = settled[pd.to_numeric(settled["rank"], errors="coerce") <= 5]
    no1 = settled[pd.to_numeric(settled["rank"], errors="coerce") == 1]

    return {
        "top5": len(top5),
        "top5_rate": float(top5["actual_cover"].mean()) if len(top5) else np.nan,
        "number1": len(no1),
        "number1_rate": float(no1["actual_cover"].mean()) if len(no1) else np.nan,
    }


def spread_history_download_bytes():
    return load_spread_history().to_csv(index=False).encode("utf-8")


def merge_uploaded_spread_history(uploaded_file):
    if uploaded_file is None:
        return 0, len(load_spread_history())

    try:
        incoming = pd.read_csv(uploaded_file)
    except Exception:
        return 0, len(load_spread_history())

    for col in HISTORY_COLUMNS:
        if col not in incoming.columns:
            incoming[col] = np.nan
    incoming = incoming[HISTORY_COLUMNS]

    current = load_spread_history()
    merged = pd.concat([current, incoming], ignore_index=True)
    before = len(current)
    merged = merged.drop_duplicates(subset=["prediction_key"], keep="first")
    _write_history(merged)
    return max(0, len(merged) - before), len(merged)
