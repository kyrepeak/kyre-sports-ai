from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit

MODEL_VERSION = "CFB GAME TOTAL • PAGE1 TO PAGE2 HANDOFF • STEP 7 V1"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_PAGE2 = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_OTHER_SPORTS = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

ROOT = Path(__file__).resolve().parents[1]
ROUTER_PATH = ROOT / "streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1.py"
PAGE1_PATH = ROOT / "cfb_game_total_clean_page_v43.py"
SELECTOR_PATH = ROOT / "cfb_game_total_clean_page_v14.py"
V11_PATH = ROOT / "cfb_game_total_clean_page_v11.py"
PAGE2_PATH = ROOT / "cfb_game_total_page2_step8_final_runtime_v1.py"

PAGE1_OWNER = "cfb_game_total_clean_page_v43"
PAGE2_RUNTIME = "cfb_game_total_page2_step8_final_runtime_v1"
EXPECTED_SELECTED_DAY = "2026-10-10"
EXPECTED_EVENT_ID = "401760001"


class Step7HandoffCertificationFailure(RuntimeError):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        raise Step7HandoffCertificationFailure(f"MISSING_DEPENDENCY:{path.name}")
    return path.read_text(encoding="utf-8")


def _literal_constants(source: str) -> dict[str, Any]:
    tree = ast.parse(source)
    values: dict[str, Any] = {}
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
            value = node.value
        if target and value is not None:
            try:
                values[target] = ast.literal_eval(value)
            except (ValueError, TypeError):
                continue
    return values


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            segment = ast.get_source_segment(source, node)
            if segment:
                return segment
    raise Step7HandoffCertificationFailure(f"FUNCTION_MISSING:{name}")


def _resolve_v11_date_query_key(v11_source: str) -> str:
    value = _literal_constants(v11_source).get("DATE_QUERY_KEY")
    key = str(value or "").strip()
    if not key:
        raise Step7HandoffCertificationFailure("V11_DATE_QUERY_KEY_MISSING")
    return key


def _execute_selector_href(
    selector_source: str,
    *,
    v11_source: str,
    selected_day: date,
    event_id: str,
) -> str:
    constants = _literal_constants(selector_source)
    required = (
        "EVENT_QUERY_KEY",
        "SELECTOR_SYNC_QUERY_KEY",
        "ROUTE_QUERY_SPORT",
        "ROUTE_QUERY_MARKET",
        "CFB_SPORT_LABEL",
        "GAME_TOTAL_MARKET",
    )
    missing = [name for name in required if name not in constants]
    if missing:
        raise Step7HandoffCertificationFailure("SELECTOR_CONSTANT_MISSING:" + ",".join(missing))

    namespace: dict[str, Any] = {
        "Any": Any,
        "Mapping": Mapping,
        "date": date,
        "urlencode": urlencode,
        **{name: constants[name] for name in required},
        "DATE_QUERY_KEY": _resolve_v11_date_query_key(v11_source),
    }
    exec(_function_source(selector_source, "_clean"), namespace)
    exec(_function_source(selector_source, "_game_id"), namespace)
    exec(_function_source(selector_source, "_selector_href"), namespace)
    return str(namespace["_selector_href"]({"espn_event_id": event_id}, selected_day))


def _exercise_selected_event_router(router_source: str | None = None) -> dict[str, Any]:
    """Execute the frozen selected-event router path against mocked Streamlit state."""
    source = router_source if router_source is not None else _read(ROUTER_PATH)
    constants = _literal_constants(source)
    page2_runtime = str(constants.get("PAGE2_RUNTIME") or "")
    event_query_key = str(constants.get("EVENT_QUERY_KEY") or "")
    if page2_runtime != PAGE2_RUNTIME or not event_query_key:
        raise Step7HandoffCertificationFailure("ROUTER_CONSTANT_DRIFT")

    class _LiveOwner:
        def __init__(self) -> None:
            self.ACTIVE_PAGE = "live-original"
            self.active = False

        def _game_total_route_active(self) -> bool:
            return self.active

        def _restore_game_total_route_from_query(self) -> bool:
            self.active = True
            return True

    st = SimpleNamespace(query_params={event_query_key: EXPECTED_EVENT_ID})
    live_owner = _LiveOwner()
    cfb_router = SimpleNamespace(GAME_TOTAL_PAGE="cfb-original")
    render_owner = SimpleNamespace(ACTIVE_PAGE="render-original")
    observed: dict[str, str] = {}

    def _parent_render() -> str:
        observed.update(
            {
                "cfb": str(cfb_router.GAME_TOTAL_PAGE),
                "live": str(live_owner.ACTIVE_PAGE),
                "render": str(render_owner.ACTIVE_PAGE),
            }
        )
        return "PAGE2_RENDERED"

    frozen_parent = SimpleNamespace(render_app=_parent_render)

    def _unexpected_page1(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise Step7HandoffCertificationFailure("SELECTED_EVENT_FELL_THROUGH_TO_PAGE1")

    namespace: dict[str, Any] = {
        "Any": Any,
        "st": st,
        "live_owner": live_owner,
        "cfb_router": cfb_router,
        "render_owner": render_owner,
        "frozen_parent": frozen_parent,
        "PAGE2_RUNTIME": page2_runtime,
        "EVENT_QUERY_KEY": event_query_key,
        "install_games_on_day_step2_visual": _unexpected_page1,
        "install_games_on_day_step3_details": _unexpected_page1,
        "install_games_on_day_step4_interaction_mobile": _unexpected_page1,
        "_render_native_page1": _unexpected_page1,
    }
    exec(_function_source(source, "_query_value"), namespace)
    exec(_function_source(source, "_selected_game_total"), namespace)
    exec(_function_source(source, "render_app"), namespace)

    rendered = namespace["render_app"]()
    expected = {"cfb": page2_runtime, "live": page2_runtime, "render": page2_runtime}
    restored = (
        cfb_router.GAME_TOTAL_PAGE == "cfb-original"
        and live_owner.ACTIVE_PAGE == "live-original"
        and render_owner.ACTIVE_PAGE == "render-original"
    )
    selected = rendered == "PAGE2_RENDERED" and observed == expected and live_owner.active is True
    if not selected:
        raise Step7HandoffCertificationFailure(f"SELECTED_EVENT_RUNTIME_NOT_OBSERVED:{observed!r}")
    if not restored:
        raise Step7HandoffCertificationFailure("SELECTED_EVENT_ROUTER_NOT_RESTORED")
    return {
        "selected": True,
        "observed_page2_owners": observed,
        "restored": True,
    }


def certify_handoff_contract() -> dict[str, Any]:
    router = _read(ROUTER_PATH)
    page1 = _read(PAGE1_PATH)
    selector = _read(SELECTOR_PATH)
    v11 = _read(V11_PATH)
    page2 = _read(PAGE2_PATH)

    router_constants = _literal_constants(router)
    selector_constants = _literal_constants(selector)
    page2_constants = _literal_constants(page2)
    date_query_key = _resolve_v11_date_query_key(v11)

    if router_constants.get("PAGE1_NATIVE_ROUTE") != PAGE1_OWNER:
        raise Step7HandoffCertificationFailure("PAGE1_OWNER_DRIFT")
    if router_constants.get("PAGE2_RUNTIME") != PAGE2_RUNTIME:
        raise Step7HandoffCertificationFailure("PAGE2_RUNTIME_DRIFT")
    if router_constants.get("EVENT_QUERY_KEY") != "ks_cfb_game_total_event_id":
        raise Step7HandoffCertificationFailure("EVENT_QUERY_KEY_DRIFT")
    if selector_constants.get("SELECTOR_SYNC_QUERY_KEY") != "ks_cfb_game_total_selector_sync":
        raise Step7HandoffCertificationFailure("SELECTOR_SYNC_QUERY_KEY_DRIFT")
    if page2_constants.get("TIMEZONE") != "America/Phoenix":
        raise Step7HandoffCertificationFailure("PAGE2_TIMEZONE_DRIFT")
    if "MAY_MODIFY_PAGE2 = False" not in page1:
        raise Step7HandoffCertificationFailure("PAGE1_PAGE2_SCOPE_DRIFT")
    if "MAY_MODIFY_PAGE1 = False" not in page2:
        raise Step7HandoffCertificationFailure("PAGE2_PAGE1_SCOPE_DRIFT")
    if "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" not in page2:
        raise Step7HandoffCertificationFailure("SPORTSBOOK_INFLUENCE_DRIFT")

    selected_day = date.fromisoformat(EXPECTED_SELECTED_DAY)
    href = _execute_selector_href(
        selector,
        v11_source=v11,
        selected_day=selected_day,
        event_id=EXPECTED_EVENT_ID,
    )
    query = dict(parse_qsl(urlsplit(href).query, keep_blank_values=True))
    expected_query = {
        date_query_key: EXPECTED_SELECTED_DAY,
        "ks_cfb_game_total_event_id": EXPECTED_EVENT_ID,
        "ks_cfb_game_total_selector_sync": EXPECTED_EVENT_ID,
        "ks_cfb_market": "Game Total",
        "ks_sport": "College Football",
    }
    if query != expected_query:
        raise Step7HandoffCertificationFailure(f"HANDOFF_QUERY_DRIFT:{query!r}")

    runtime = _exercise_selected_event_router(router)
    return {
        "status": "GREEN",
        "model_version": MODEL_VERSION,
        "page1_owner": PAGE1_OWNER,
        "page2_runtime": PAGE2_RUNTIME,
        "event_query_key": str(router_constants["EVENT_QUERY_KEY"]),
        "selector_sync_query_key": str(selector_constants["SELECTOR_SYNC_QUERY_KEY"]),
        "date_query_key": date_query_key,
        "selected_day": EXPECTED_SELECTED_DAY,
        "event_id": EXPECTED_EVENT_ID,
        "handoff_query": expected_query,
        "page2_selected_event_activation": bool(runtime["selected"]),
        "router_observed_page2_owners": dict(runtime["observed_page2_owners"]),
        "router_restored_after_render": bool(runtime["restored"]),
        "phoenix_timezone": str(page2_constants["TIMEZONE"]),
        "network_calls_added": NETWORK_CALLS_ADDED,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(certify_handoff_contract(), sort_keys=True))
