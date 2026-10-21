"""Line-bound WNBA PRA model artifact built outside the page request path."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
from typing import Any, Callable, Mapping

from wnba_pra_source_clean_guard_v1 import source_clean_generation

SCHEMA_VERSION = "wnba_pra_page_model_artifact_v1"
DEFAULT_MODEL_VERSION = "PRA V3.6.17"


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [dict(x) for x in value if isinstance(x, Mapping)]
    if isinstance(value, tuple):
        return [dict(x) for x in value if isinstance(x, Mapping)]
    if hasattr(value, "to_dict"):
        try:
            rows = value.to_dict("records")
            return [dict(x) for x in rows if isinstance(x, Mapping)]
        except Exception:
            return []
    return []


def _field(snapshot: Any, name: str, default: Any = None) -> Any:
    if isinstance(snapshot, Mapping):
        return snapshot.get(name, default)
    return getattr(snapshot, name, default)


def _clean_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        if hasattr(value, "item"):
            return _clean_scalar(value.item())
    except Exception:
        pass
    return str(value)


def _clean_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): _clean_json(v) for k, v in value.items()}


def _clean_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _clean_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_clean_json(v) for v in value]
    return _clean_scalar(value)


def _norm_name(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _line_key(player_name: Any, line: Any) -> str:
    return f"{_norm_name(player_name)}|{float(line):.3f}"


def _hash_payload(payload: Mapping[str, Any]) -> str:
    raw = deepcopy(dict(payload))
    raw.pop("content_hash", None)
    text = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _merge_final_rows(standard: Any, final_rows: Any) -> Any:
    try:
        import pandas as pd
        std = standard.copy() if hasattr(standard, "copy") else pd.DataFrame(standard)
        fin = final_rows.copy() if hasattr(final_rows, "copy") else pd.DataFrame(final_rows)
        if std is None or std.empty:
            return fin
        if fin is None or fin.empty:
            return std
        keys = ["game_id", "player_key", "line", "book"]
        if not all(k in std.columns and k in fin.columns for k in keys):
            return pd.concat([std, fin], ignore_index=True)
        fkeys = set(tuple(x) for x in fin[keys].astype(str).itertuples(index=False, name=None))
        keep = [tuple(x) not in fkeys for x in std[keys].astype(str).itertuples(index=False, name=None)]
        return pd.concat([std.loc[keep], fin], ignore_index=True)
    except Exception:
        return final_rows or standard


def _build_preserved_snapshot(day: str) -> tuple[Any, int]:
    bridge = importlib.import_module("wnba_pra_api_market_bridge_v2")
    token = bridge.install()
    try:
        season = int(str(day)[:4])
        api_module = importlib.import_module("wnba_api_client_v1")
        api = api_module.KyreWNBAAPIClient(
            base_url=api_module.PRA_VERCEL_BASE_URL, attempts=1, timeout_seconds=10
        )
        schedule_payload = api.games_for_date(str(day), season)
        live_market = bridge.market_snapshot(str(day))
        props = live_market.get("player_props")
        focus_names: set[str] = set()
        if props is not None and hasattr(props, "columns") and "player_name" in props.columns:
            focus_names = {str(value).strip() for value in props["player_name"].tolist() if str(value).strip()}
        with source_clean_generation(
            str(day), season, schedule_payload=schedule_payload, focus_names=focus_names
        ) as guard:
            snapshot_mod = importlib.import_module("wnba_pra_product_snapshot_v1")
            snapshot = snapshot_mod.build_product_snapshot(day)
            stored = _field(snapshot, "stored_mc_rows")
            if not _records(stored):
                monte = importlib.import_module("wnba_pra_monte_carlo_v311")
                standard_rows, standard_meta = monte.run_standard(day)
                final_rows, final_meta = monte.run_final(day, standard_rows)
                combined = _merge_final_rows(standard_rows, final_rows)
                final_mod = importlib.import_module("wnba_pra_final_v32")
                selected = final_mod.select_master_card(combined.copy(), limit=final_mod.MAX_CARD)
                snapshot = {
                    "schedule": _field(snapshot, "schedule"),
                    "schedule_diag": _field(snapshot, "schedule_diag", {}),
                    "projections": _field(snapshot, "projections"),
                    "market_rows": _field(snapshot, "market_rows"),
                    "market_meta": _field(snapshot, "market_meta", {}),
                    "matchup_rows": _field(snapshot, "matchup_rows"),
                    "matchup_meta": _field(snapshot, "matchup_meta", {}),
                    "stored_mc_rows": combined,
                    "stored_mc_meta": {"source": "5M/10M", "standard": standard_meta, "final": final_meta},
                    "final_card": selected,
                    "availability_diag": _field(snapshot, "availability_diag", {}),
                    "role_diag": _field(snapshot, "role_diag", {}),
                }
            return snapshot, guard.blocked_calls
    finally:
        bridge.restore(token)


def _model_row(row: Mapping[str, Any], projection_map: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    player = row.get("player") or row.get("player_name") or row.get("PLAYER_NAME")
    line = row.get("line")
    if not player or line is None:
        return None
    try:
        line_f = float(line)
    except (TypeError, ValueError):
        return None
    model_over = row.get("model_over", row.get("p_over"))
    try:
        p_over = float(model_over)
    except (TypeError, ValueError):
        p_over = None
    p_under = row.get("model_under", row.get("p_under"))
    if p_under is None and p_over is not None:
        p_under = 1.0 - p_over
    pkey = str(row.get("player_key") or "")
    proj = projection_map.get(pkey, {})
    out = {
        "game_id": _clean_scalar(row.get("game_id")),
        "player_key": pkey or None,
        "player_name": str(player),
        "team": _clean_scalar(row.get("team") or row.get("TEAM_NAME") or proj.get("TEAM_NAME")),
        "opponent": _clean_scalar(row.get("opponent") or row.get("OPPONENT") or proj.get("OPPONENT")),
        "line": line_f,
        "p_over": _clean_scalar(p_over),
        "p_under": _clean_scalar(p_under),
        "no_vig_over": _clean_scalar(row.get("no_vig_over")),
        "edge": _clean_scalar(row.get("edge")),
        "ev100": _clean_scalar(row.get("ev100")),
        "final_ready": bool(row.get("final_ready")),
        "model_qualified": bool(row.get("model_qualified")),
        "converged": bool(row.get("converged")),
        "data_quality": _clean_scalar(row.get("data_quality")),
        "context_quality": _clean_scalar(row.get("context_quality")),
        "variance_source": _clean_scalar(row.get("variance_source")),
        "model_pass": _clean_scalar(row.get("pass_source")),
        "projection_pra": _clean_scalar(row.get("projection") or proj.get("PROJ_PRA")),
        "projection_minutes": _clean_scalar(proj.get("PROJ_MIN")),
    }
    return out


def build_model_artifact(
    day: str,
    season: int = 2026,
    *,
    snapshot_builder: Callable[[str], Any] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    datetime.strptime(str(day), "%Y-%m-%d")
    if int(season) != 2026:
        raise ValueError("WNBA PRA model artifact currently supports season 2026.")
    blocked_calls = 0
    if snapshot_builder is None:
        snapshot, blocked_calls = _build_preserved_snapshot(str(day))
    else:
        snapshot = snapshot_builder(str(day))

    projections = _records(_field(snapshot, "projections"))
    projection_map = {str(r.get("player_key") or ""): r for r in projections if r.get("player_key")}
    rows = []
    for raw in _records(_field(snapshot, "stored_mc_rows")):
        cooked = _model_row(raw, projection_map)
        if cooked:
            rows.append(cooked)
    rows.sort(key=lambda r: (_norm_name(r.get("player_name")), float(r.get("line") or 0.0)))
    line_bindings = {_line_key(r["player_name"], r["line"]): deepcopy(r) for r in rows}

    final_card = []
    for raw in _records(_field(snapshot, "final_card")):
        player = raw.get("player") or raw.get("player_name") or raw.get("PLAYER_NAME")
        if not player or raw.get("line") is None:
            continue
        final_card.append({
            "game_id": _clean_scalar(raw.get("game_id")),
            "player_key": _clean_scalar(raw.get("player_key")),
            "player_name": str(player),
            "line": float(raw.get("line")),
            "side": _clean_scalar(raw.get("side") or raw.get("bet_side") or "over"),
            "final_ready": bool(raw.get("final_ready")),
            "decision_label": _clean_scalar(raw.get("decision_label")),
            "decision_tier": _clean_scalar(raw.get("decision_tier")),
            "decision_strength": _clean_scalar(raw.get("decision_strength")),
        })

    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "date": str(day),
        "season": int(season),
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "model_version": DEFAULT_MODEL_VERSION,
        "source_status": "DEGRADED_SOURCE_CLEAN" if blocked_calls else "SOURCE_CLEAN",
        "blocked_fallback_calls": int(blocked_calls),
        "schedule": _records(_field(snapshot, "schedule")),
        "projections": projections,
        "rows": rows,
        "line_bindings": line_bindings,
        "final_card": final_card,
        "diagnostics": {
            "schedule": _clean_mapping(_field(snapshot, "schedule_diag", {})),
            "market": _clean_mapping(_field(snapshot, "market_meta", {})),
            "matchup": _clean_mapping(_field(snapshot, "matchup_meta", {})),
            "monte_carlo": _clean_mapping(_field(snapshot, "stored_mc_meta", {})),
            "availability": _clean_mapping(_field(snapshot, "availability_diag", {})),
            "role": _clean_mapping(_field(snapshot, "role_diag", {})),
        },
    }
    artifact["content_hash"] = _hash_payload(artifact)
    return validate_model_artifact(artifact)


def validate_model_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("model artifact must be an object")
    out = deepcopy(dict(payload))
    if out.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("model artifact schema mismatch")
    datetime.strptime(str(out.get("date") or ""), "%Y-%m-%d")
    if int(out.get("season") or 0) != 2026:
        raise ValueError("model artifact season mismatch")
    datetime.fromisoformat(str(out.get("generated_at") or "").replace("Z", "+00:00"))
    if not isinstance(out.get("rows"), list) or not isinstance(out.get("line_bindings"), Mapping):
        raise ValueError("model artifact rows/line bindings invalid")
    expected = _hash_payload(out)
    if out.get("content_hash") != expected:
        raise ValueError("model artifact content hash mismatch")
    for row in out["rows"]:
        if not isinstance(row, Mapping):
            raise ValueError("model artifact row invalid")
        key = _line_key(row.get("player_name"), row.get("line"))
        bound = out["line_bindings"].get(key)
        if not isinstance(bound, Mapping) or float(bound.get("line")) != float(row.get("line")):
            raise ValueError("model artifact line binding mismatch")
    return out


__all__ = ["SCHEMA_VERSION", "build_model_artifact", "validate_model_artifact"]
