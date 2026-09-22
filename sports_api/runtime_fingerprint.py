from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from pathlib import Path
from threading import Lock
from typing import Mapping

_RUNTIME_BUILD_IDENTITY: dict[str, object] | None = None
_RUNTIME_BUILD_LOCK = Lock()


def _python_source_path(module_file: str) -> Path | None:
    """Resolve a loaded module's file back to an on-disk Python source file."""
    path = Path(module_file).resolve()
    if path.suffix in {".pyc", ".pyo"}:
        try:
            path = Path(importlib.util.source_from_cache(str(path))).resolve()
        except (NotImplementedError, ValueError):
            return None
    if path.suffix != ".py" or not path.is_file():
        return None
    return path


def fingerprint_source_files(files: Mapping[str, Path]) -> dict[str, object]:
    """Hash exact source bytes and logical paths into one deterministic identity."""
    aggregate = hashlib.sha256()
    manifest: list[dict[str, str]] = []

    for logical_path, source_path in sorted(files.items()):
        data = Path(source_path).read_bytes()
        path_bytes = logical_path.encode("utf-8")
        file_sha256 = hashlib.sha256(data).hexdigest()

        # Length-prefix both fields so the aggregate has unambiguous boundaries.
        aggregate.update(len(path_bytes).to_bytes(4, "big"))
        aggregate.update(path_bytes)
        aggregate.update(len(data).to_bytes(8, "big"))
        aggregate.update(data)

        manifest.append({"path": logical_path, "sha256": file_sha256})

    if not manifest:
        raise RuntimeError("no loaded Python source files were available to fingerprint")

    return {
        "algorithm": "sha256",
        "fingerprint_scope": "loaded_python_sources_under_sports_api",
        "runtime_source_sha256": aggregate.hexdigest(),
        "file_count": len(manifest),
        "files": manifest,
    }


def build_loaded_source_fingerprint(*, package_root: Path | None = None) -> dict[str, object]:
    """Fingerprint source files for modules this Python process has actually loaded."""
    package_root = (package_root or Path(__file__).resolve().parent).resolve()
    repo_root = package_root.parent
    files: dict[str, Path] = {}

    for module in tuple(sys.modules.values()):
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue

        source_path = _python_source_path(str(module_file))
        if source_path is None:
            continue

        try:
            source_path.relative_to(package_root)
        except ValueError:
            continue

        logical_path = source_path.relative_to(repo_root).as_posix()
        files[logical_path] = source_path

    return fingerprint_source_files(files)


def get_runtime_build_identity() -> dict[str, object]:
    """
    Return one process-stable runtime source identity.

    RENDER_GIT_COMMIT is retained only as provider-reported metadata. It is
    deliberately excluded from runtime_source_sha256 and is not authoritative.
    """
    global _RUNTIME_BUILD_IDENTITY

    if _RUNTIME_BUILD_IDENTITY is None:
        with _RUNTIME_BUILD_LOCK:
            if _RUNTIME_BUILD_IDENTITY is None:
                _RUNTIME_BUILD_IDENTITY = {
                    **build_loaded_source_fingerprint(),
                    "identity_basis": "exact_loaded_source_bytes",
                    "provider_reported_commit": os.getenv("RENDER_GIT_COMMIT") or None,
                    "provider_commit_authoritative": False,
                    "process_snapshot_cached": True,
                }

    return _RUNTIME_BUILD_IDENTITY
