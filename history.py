from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

ET = ZoneInfo("America/New_York")
MLB_LIVE_API = "https://statsapi.mlb.com/api/v1.1"
HISTORY_PATH = Path("prediction_history.csv")

HISTORY_COLUMNS = [
    "prediction_key",
    "scan_id",
    "created_at_et",
    "game_date",
    "model_version",
    "source",
    "rank",
    "game_pk",
    "player_id",
    "player_name",
    "team",
    "opponent",
    "starter",
    "lineup_position",
    "expected_ab",
    "predicted_p1",
    "predicted_p2",
    "predicted_p3",
    "expected_hits",
    "fair_odds",
    "confidence",
    "data_score",
    "simulations",
    "seed",
    "scenario_low",
    "scenario_high",
    "game_status",
    "grade_status",
    "actual_ab",
    "actual_pa",
    "actual_hits",
    "actual_1plus",
    "graded_at_et",
]


def _now_et():
    return datetime.now(ET)


def _empty_history():
    return pd.DataFrame(columns=HISTORY_COLUMNS)


def _prediction_key(game_pk, player_id, model_version):
    return f"{int(game_pk)}:{int(player_id)}:{model_version}"


def load_history():
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
    df = df.copy()
    for col in HISTORY_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    df[HISTORY_COLUMNS].to_csv(HISTORY_PATH, index=False)


def _odds_from_prob(prob):
    p = min(max(float(prob), 1e-6), 1 - 1e-6)
    if p >= 0.5:
        return int(round(-100 * p / (1 - p)))
    return int(round(100 * (1 - p) / p))


def append_prediction_records(records):
    if not records:
        return 0, len(load_history())

    current = load_history()
    incoming = pd.DataFrame(records)

    for col in HISTORY_COLUMNS:
        if col not in incoming.columns:
            incoming[col] = np.nan

    incoming = incoming[HISTORY_COLUMNS]
    existing_keys = set(current["prediction_key"].dropna().astype(str))
    incoming = incoming[
        ~incoming["prediction_key"].astype(str).isin(existing_keys)
    ].copy()

    if incoming.empty:
        return 0, len(current)

    merged = pd.concat([current, incoming], ignore_index=True)
    merged = merged.drop_duplicates(subset=["prediction_key"], keep="first")
    _write_history(merged)
    return len(incoming), len(merged)


def save_top5_snapshot(results, model_version="V13"):
    if not results:
        return 0, len(load_history()), None

    now = _now_et()
    scan_id = now.strftime("%Y%m%dT%H%M%S")
    rows = []

    for rank, result in enumerate(results[:5], 1):
        sim = result["sim"]
        game_pk = int(result["game_pk"])
        player_id = int(result["player_id"])

        rows.append(
            {
                "prediction_key": _prediction_key(
                    game_pk, player_id, model_version
                ),
                "scan_id": scan_id,
                "created_at_et": now.isoformat(),
                "game_date": now.strftime("%Y-%m-%d"),
                "model_version": model_version,
                "source": "daily_top5",
                "rank": rank,
                "game_pk": game_pk,
                "player_id": player_id,
                "player_name": result["player_name"],
                "team": result["team"],
                "opponent": result["opponent"],
                "starter": result.get("starter_name", "TBD"),
                "lineup_position": result.get("position"),
                "expected_ab": result.get("expected_ab"),
                "predicted_p1": sim["p_one_plus"],
                "predicted_p2": sim["p_two_plus"],
                "predicted_p3": sim["p_three_plus"],
                "expected_hits": sim["expected_hits"],
                "fair_odds": _odds_from_prob(sim["p_one_plus"]),
                "confidence": result.get("confidence"),
                "data_score": result.get("data_score"),
                "simulations": sim.get("simulations"),
                "seed": sim.get("seed"),
                "scenario_low": sim.get("scenario_low"),
                "scenario_high": sim.get("scenario_high"),
                "game_status": result.get("status", "Scheduled"),
                "grade_status": "PENDING",
            }
        )

    added, total = append_prediction_records(rows)
    return added, total, scan_id


def save_single_snapshot(
    player,
    matchup,
    pitcher,
    lineup_position,
    expected_ab,
    sim,
    confidence,
    data_score,
    model_version="V13",
):
    if not player or not matchup or not sim:
        return 0, len(load_history())

    now = _now_et()
    game_pk = int(matchup["game_pk"])
    player_id = int(player["id"])

    row = {
        "prediction_key": _prediction_key(game_pk, player_id, model_version),
        "scan_id": now.strftime("%Y%m%dT%H%M%S"),
        "created_at_et": now.isoformat(),
        "game_date": now.strftime("%Y-%m-%d"),
        "model_version": model_version,
        "source": "single_player",
        "rank": np.nan,
        "game_pk": game_pk,
        "player_id": player_id,
        "player_name": player["name"],
        "team": player.get("team_name"),
        "opponent": matchup.get("opponent"),
        "starter": (pitcher or {}).get("name", matchup.get("pitcher", "TBD")),
        "lineup_position": lineup_position,
        "expected_ab": expected_ab,
        "predicted_p1": sim["p_one_plus"],
        "predicted_p2": sim["p_two_plus"],
        "predicted_p3": sim["p_three_plus"],
        "expected_hits": sim["expected_hits"],
        "fair_odds": _odds_from_prob(sim["p_one_plus"]),
        "confidence": confidence,
        "data_score": data_score,
        "simulations": sim.get("simulations"),
        "seed": sim.get("seed"),
        "scenario_low": sim.get("scenario_low"),
        "scenario_high": sim.get("scenario_high"),
        "game_status": matchup.get("status", "Scheduled"),
        "grade_status": "PENDING",
    }
    return append_prediction_records([row])


def _fetch_game_feed(game_pk):
    response = requests.get(
        f"{MLB_LIVE_API}/game/{int(game_pk)}/feed/live",
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def _status_from_feed(feed):
    status = (feed.get("gameData", {}) or {}).get("status", {}) or {}
    return (
        str(status.get("abstractGameState", "")),
        str(status.get("detailedState", "")),
    )


def _player_batting_result(feed, player_id):
    teams = (
        feed.get("liveData", {})
        .get("boxscore", {})
        .get("teams", {})
        or {}
    )

    for side in ("away", "home"):
        player = (
            (teams.get(side, {}) or {})
            .get("players", {})
            .get(f"ID{int(player_id)}")
        )
        if not player:
            continue

        batting = (
            (player.get("stats", {}) or {}).get("batting", {}) or {}
        )
        ab = int(float(batting.get("atBats", 0) or 0))
        pa = int(float(batting.get("plateAppearances", 0) or 0))
        hits = int(float(batting.get("hits", 0) or 0))
        return {"ab": ab, "pa": pa, "hits": hits}

    return None


def grade_finished_games():
    df = load_history()
    if df.empty:
        return {
            "graded": 0,
            "dnp": 0,
            "void": 0,
            "still_pending": 0,
            "errors": 0,
        }

    pending_mask = df["grade_status"].fillna("PENDING").eq("PENDING")
    pending = df[pending_mask]
    if pending.empty:
        return {
            "graded": 0,
            "dnp": 0,
            "void": 0,
            "still_pending": 0,
            "errors": 0,
        }

    summary = {
        "graded": 0,
        "dnp": 0,
        "void": 0,
        "still_pending": 0,
        "errors": 0,
    }
    feeds = {}

    for game_pk in pending["game_pk"].dropna().astype(int).unique():
        try:
            feeds[game_pk] = _fetch_game_feed(game_pk)
        except Exception:
            feeds[game_pk] = None
            summary["errors"] += 1

    now = _now_et().isoformat()

    for idx, row in pending.iterrows():
        game_pk = int(row["game_pk"])
        feed = feeds.get(game_pk)
        if feed is None:
            continue

        abstract, detailed = _status_from_feed(feed)
        detailed_lower = detailed.lower()

        if any(
            token in detailed_lower
            for token in ("cancel", "postpon", "suspend")
        ):
            df.at[idx, "grade_status"] = "VOID"
            df.at[idx, "game_status"] = detailed or abstract
            df.at[idx, "graded_at_et"] = now
            summary["void"] += 1
            continue

        if abstract.lower() != "final" and "final" not in detailed_lower:
            summary["still_pending"] += 1
            continue

        result = _player_batting_result(feed, int(row["player_id"]))
        df.at[idx, "game_status"] = detailed or "Final"
        df.at[idx, "graded_at_et"] = now

        if not result or (result["ab"] == 0 and result["pa"] == 0):
            df.at[idx, "grade_status"] = "DNP"
            summary["dnp"] += 1
            continue

        df.at[idx, "grade_status"] = "GRADED"
        df.at[idx, "actual_ab"] = result["ab"]
        df.at[idx, "actual_pa"] = result["pa"]
        df.at[idx, "actual_hits"] = result["hits"]
        df.at[idx, "actual_1plus"] = 1 if result["hits"] >= 1 else 0
        summary["graded"] += 1

    _write_history(df)
    return summary


def graded_history(df=None):
    df = load_history() if df is None else df
    if df.empty:
        return df
    out = df[df["grade_status"].eq("GRADED")].copy()
    if out.empty:
        return out

    for col in (
        "predicted_p1",
        "predicted_p2",
        "predicted_p3",
        "expected_hits",
        "actual_hits",
        "actual_1plus",
    ):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["predicted_p1", "actual_1plus"])


def calibration_metrics(df=None):
    g = graded_history(df)
    if g.empty:
        return {
            "graded": 0,
            "hit_rate": np.nan,
            "avg_prediction": np.nan,
            "brier": np.nan,
            "calibration_gap": np.nan,
            "log_loss": np.nan,
        }

    p = g["predicted_p1"].clip(1e-6, 1 - 1e-6).astype(float)
    y = g["actual_1plus"].astype(float)

    return {
        "graded": len(g),
        "hit_rate": float(y.mean()),
        "avg_prediction": float(p.mean()),
        "brier": float(np.mean((p - y) ** 2)),
        "calibration_gap": float(y.mean() - p.mean()),
        "log_loss": float(
            -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
        ),
    }


def calibration_table(df=None):
    g = graded_history(df)
    if g.empty:
        return pd.DataFrame(
            columns=[
                "Probability Tier",
                "Predictions",
                "Avg Projected",
                "Actual Hit Rate",
                "Calibration Gap",
                "Brier",
            ]
        )

    bins = [0.0, 0.60, 0.70, 0.80, 0.90, 1.000001]
    labels = ["<60%", "60–69.9%", "70–79.9%", "80–89.9%", "90%+"]
    g = g.copy()
    g["tier"] = pd.cut(
        g["predicted_p1"],
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
        p = group["predicted_p1"].astype(float)
        y = group["actual_1plus"].astype(float)
        rows.append(
            {
                "Probability Tier": label,
                "Predictions": len(group),
                "Avg Projected": f"{p.mean() * 100:.1f}%",
                "Actual Hit Rate": f"{y.mean() * 100:.1f}%",
                "Calibration Gap": f"{(y.mean() - p.mean()) * 100:+.1f} pts",
                "Brier": f"{np.mean((p - y) ** 2):.3f}",
            }
        )
    return pd.DataFrame(rows)


def model_version_table(df=None):
    g = graded_history(df)
    if g.empty:
        return pd.DataFrame(
            columns=[
                "Model",
                "Predictions",
                "Avg Projected",
                "Actual Hit Rate",
                "Brier",
            ]
        )

    rows = []
    for version, group in g.groupby("model_version"):
        p = group["predicted_p1"].astype(float)
        y = group["actual_1plus"].astype(float)
        rows.append(
            {
                "Model": version,
                "Predictions": len(group),
                "Avg Projected": f"{p.mean() * 100:.1f}%",
                "Actual Hit Rate": f"{y.mean() * 100:.1f}%",
                "Brier": f"{np.mean((p - y) ** 2):.3f}",
            }
        )
    return pd.DataFrame(rows).sort_values("Model")


def top5_performance(df=None):
    g = graded_history(df)
    if g.empty:
        return {
            "predictions": 0,
            "hit_rate": np.nan,
            "rank1_rate": np.nan,
        }

    top = g[g["source"].eq("daily_top5")].copy()
    if top.empty:
        return {
            "predictions": 0,
            "hit_rate": np.nan,
            "rank1_rate": np.nan,
        }

    rank1 = top[pd.to_numeric(top["rank"], errors="coerce").eq(1)]
    return {
        "predictions": len(top),
        "hit_rate": float(top["actual_1plus"].mean()),
        "rank1_rate": (
            float(rank1["actual_1plus"].mean()) if not rank1.empty else np.nan
        ),
    }


def history_download_bytes(df=None):
    df = load_history() if df is None else df
    return df.to_csv(index=False).encode("utf-8")


def merge_uploaded_history(uploaded_file):
    try:
        incoming = pd.read_csv(uploaded_file)
    except Exception as exc:
        return {"ok": False, "message": f"Could not read CSV: {exc}"}

    required = {
        "prediction_key",
        "game_pk",
        "player_id",
        "predicted_p1",
        "grade_status",
    }
    if not required.issubset(set(incoming.columns)):
        missing = sorted(required - set(incoming.columns))
        return {
            "ok": False,
            "message": f"Missing required columns: {', '.join(missing)}",
        }

    current = load_history()
    for col in HISTORY_COLUMNS:
        if col not in incoming.columns:
            incoming[col] = np.nan

    before = len(current)
    merged = pd.concat(
        [current, incoming[HISTORY_COLUMNS]],
        ignore_index=True,
    )
    merged = merged.drop_duplicates(subset=["prediction_key"], keep="first")
    _write_history(merged)

    return {
        "ok": True,
        "added": len(merged) - before,
        "total": len(merged),
        "message": f"History restored. {len(merged) - before} new rows added.",
    }
