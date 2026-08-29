"""Production entrypoint that installs the certified Step19A provider bridge first.

The Render process imports this module instead of sports_api.main directly so the
Step19A Step17B compatibility bridge patches the frozen sportsbook seams before
Step17B and the downstream always-on runtime bind their call graph.
"""
from __future__ import annotations

import sports_api.wnba_step19a_step17b_bridge as _wnba_step19a_step17b_bridge  # noqa: F401
from sports_api.main import app

__all__ = ["app"]
