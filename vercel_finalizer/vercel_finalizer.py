"""Compatibility package shim for Vercel subdirectory-root execution.

When Vercel deploys this directory as the project root it imports app.py as a
standalone module from /var/task. In that layout the normal parent package
name is not importable. Exposing ``__path__`` lets imports such as
``vercel_finalizer.authority`` resolve against this same directory while
remaining invisible to normal repository-root package imports.

The finalizer also imports ``runless_v2`` from the repository root. During
subdirectory-root execution that parent directory is not guaranteed to be on
``sys.path``, so add it only when the package is actually present there.
"""

from pathlib import Path
import sys

_package_dir = Path(__file__).resolve().parent
__path__ = [str(_package_dir)]

for _candidate_root in (_package_dir, _package_dir.parent):
    if (_candidate_root / "runless_v2").is_dir():
        _candidate = str(_candidate_root)
        if _candidate not in sys.path:
            sys.path.insert(0, _candidate)
        break
