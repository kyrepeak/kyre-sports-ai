from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _page(state="READY", cache="FRESH", refresh=False):
    return {
        "service": "Kyre Sports API — Vercel",
        "schema_version": "wnba_pra_page_snapshot_v1",
        "date": "2026-10-21",
        "season": 2026,
        "snapshot_state": state,
        "cache_state": cache,
        "refresh_required": refresh,
        "market_board_reads": 1,
        "consensus_averaging": False,
        "selected_provider": "draftkings",
        "sportsbooks": ["DraftKings"],
        "offers": [
            {"player_name": "Rhyne Howard", "sportsbook": "DraftKings", "side": "over", "line": 23.5, "american_odds": -119, "model_state": "LINE_BOUND_READY", "p_over": .581, "p_under": .419, "projection_pra": 25.2},
            {"player_name": "Rhyne Howard", "sportsbook": "DraftKings", "side": "under", "line": 23.5, "american_odds": -114, "model_state": "LINE_BOUND_READY", "p_over": .581, "p_under": .419, "projection_pra": 25.2},
        ],
        "final_card": [{"player_name": "Rhyne Howard", "line": 23.5, "side": "over", "final_ready": True}],
    }


def test_snapshot_client_makes_exactly_one_get_without_retry():
    from wnba_pra_page_snapshot_client_v1 import fetch_page_snapshot

    class Response:
        status_code = 200
        def json(self): return _page()
    class Session:
        def __init__(self): self.calls=[]
        def get(self, url, *, params, headers, timeout, allow_redirects):
            self.calls.append((url, deepcopy(params), deepcopy(headers), timeout, allow_redirects))
            return Response()
    session=Session()
    out=fetch_page_snapshot("2026-10-21", session=session, timeout_seconds=2.0)
    assert out["snapshot_state"] == "READY"
    assert len(session.calls) == 1
    assert session.calls[0][0] == "https://kyre-runless-proof.vercel.app/api/v1/wnba/pra/page-snapshot"
    assert session.calls[0][1] == {"date":"2026-10-21","season":2026}


def test_refresh_worker_delegates_to_server_owned_refresh_request():
    import wnba_pra_page_snapshot_publish_v1 as publish

    class Response:
        status_code = 200
        def json(self): return {"state":"REFRESHED","content_hash":"sha256:"+"a"*64}
    class Session:
        def __init__(self): self.posts=[]
        def post(self,url,*,json,headers,timeout):
            self.posts.append((url,deepcopy(json),deepcopy(headers),timeout)); return Response()

    session=Session()
    assert publish.refresh_if_claimed("2026-10-21", owner_id="ignored-client-owner", session=session, background=False) is True
    assert len(session.posts) == 1
    url,payload,headers,_ = session.posts[0]
    assert url.endswith("/page-snapshot/refresh-request")
    assert payload == {"date":"2026-10-21","season":2026}
    assert "authorization" not in {str(k).lower() for k in headers}


def test_hub_has_no_heavy_model_imports_at_module_load():
    source=(ROOT/"wnba_pra_hub_v3617.py").read_text(encoding="utf-8")
    tree=ast.parse(source)
    imported=[]
    for node in tree.body:
        if isinstance(node,ast.Import): imported.extend(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom) and node.module: imported.append(node.module)
    forbidden=("wnba_pra_product_snapshot_v1","wnba_pra_market_consensus_v1","wnba_pra_product_view_model_v1","wnba_pra_product_view_v3","wnba_pra_api_market_bridge_v2","wnba_pra_playoff_context_v1","wnba_pra_monte_carlo_v311","wnba_pra_final_v32")
    assert not (set(imported) & set(forbidden)), imported


def test_hub_fresh_path_one_read_one_render_zero_refresh(monkeypatch):
    import wnba_pra_hub_v3617 as hub
    calls=[]
    monkeypatch.setattr(hub,"resolve_active_slate_date",lambda:"2026-10-21")
    monkeypatch.setattr(hub,"fetch_page_snapshot",lambda day,season=2026: calls.append(("fetch",day,season)) or _page())
    monkeypatch.setattr(hub,"render_page_snapshot",lambda payload,**kwargs: calls.append(("render",payload["snapshot_state"])))
    monkeypatch.setattr(hub,"refresh_if_claimed",lambda *a,**k: (_ for _ in ()).throw(AssertionError("refresh must not run on FRESH")))
    out=hub.render_wnba_pra_hub()
    assert out["snapshot_state"] == "READY"
    assert calls == [("fetch","2026-10-21",2026),("render","READY")]


def test_hub_stale_renders_before_refresh(monkeypatch):
    import wnba_pra_hub_v3617 as hub
    calls=[]
    monkeypatch.setattr(hub,"resolve_active_slate_date",lambda:"2026-10-21")
    monkeypatch.setattr(hub,"fetch_page_snapshot",lambda day,season=2026:_page(state="READY",cache="STALE_SAFE",refresh=True))
    monkeypatch.setattr(hub,"render_page_snapshot",lambda payload,**kwargs:calls.append("render"))
    monkeypatch.setattr(hub,"refresh_if_claimed",lambda *a,**k:calls.append("refresh") or True)
    hub.render_wnba_pra_hub()
    assert calls == ["render","refresh"]


def test_refresh_client_requests_server_owned_refresh_without_secret_header():
    import wnba_pra_page_snapshot_publish_v1 as publish
    class Response:
        status_code=200
        def json(self): return {"state":"NOT_NEEDED"}
    class Session:
        def __init__(self): self.calls=[]
        def post(self,url,*,json,headers,timeout): self.calls.append((url,deepcopy(json),deepcopy(headers),timeout)); return Response()
    session=Session()
    out=publish.request_refresh("2026-10-21",session=session,background=False)
    assert out["state"] == "NOT_NEEDED"
    assert len(session.calls)==1
    assert session.calls[0][0].endswith('/api/v1/wnba/pra/page-snapshot/refresh-request')
    assert 'authorization' not in {str(k).lower() for k in session.calls[0][2]}
