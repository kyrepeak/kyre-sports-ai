"""Compatibility package shim for Vercel subdirectory-root execution.

When Vercel deploys this directory as the project root it imports app.py as a
standalone module from /var/task.  In that layout the normal parent package
name is not importable.  Exposing __path__ lets imports such as
``vercel_finalizer.authority`` resolve against this same directory while
remaining invisible to normal repository-root package imports.
"""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent)]
