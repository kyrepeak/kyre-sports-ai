from __future__ import annotations

import ast
import sys
import types
from pathlib import Path


def _entrypoint_import_prefix() -> ast.Module:
    tree = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    prefix: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            break
        prefix.append(node)
    return ast.Module(body=prefix, type_ignores=[])


def test_streamlit_entrypoint_survives_stale_radar_module_without_new_probe(monkeypatch) -> None:
    stale_radar = types.ModuleType("sports_api.posthog_error_radar_v1")
    stale_radar.capture_runtime_exception = lambda *args, **kwargs: False
    monkeypatch.setitem(sys.modules, "sports_api.posthog_error_radar_v1", stale_radar)

    namespace: dict[str, object] = {}
    code = compile(_entrypoint_import_prefix(), "app.py", "exec")
    exec(code, namespace)

    assert callable(namespace["capture_runtime_exception"])
    assert callable(namespace["run_streamlit_activation_probe"])
