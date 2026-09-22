"""Monster Dependency Map V1.

Static, dependency-light impact analysis for the Kyre Sports AI repository.
The map is developer tooling only: it does not import application modules,
execute sports logic, change projections, alter routing, or modify runtime data.

It understands normal Python imports plus the repository's common dynamic import
shapes (``import_module(NAME)``, ``__import__(NAME)``, and ``_import(NAME)``)
when the module name is a literal or a module-level string constant.
"""
from __future__ import annotations

import argparse
import ast
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

DEPENDENCY_MAP_VERSION = "MONSTER_DEPENDENCY_MAP_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False

DEFAULT_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".github",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
    }
)

DEFAULT_ENTRYPOINT_PATHS = frozenset({"app.py", "sports_api/main.py"})

# These names are treated as explicit guardrail signals, not as permission to
# edit or rewrite anything. The map only reports when a blast radius reaches one.
PROTECTED_NAME_MARKERS = (
    "frozen",
    "freeze_manifest",
    "projection_v14",
    "over_under_projection_v14",
)


@dataclass(frozen=True)
class ImportEdge:
    source: str
    target: str
    kind: str
    lineno: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "lineno": self.lineno,
        }


@dataclass
class DependencyMap:
    root: Path
    module_to_path: dict[str, str]
    edges: list[ImportEdge]
    parse_errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def path_to_module(self) -> dict[str, str]:
        return {path: module for module, path in self.module_to_path.items()}

    def dependencies(self) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = {module: set() for module in self.module_to_path}
        for edge in self.edges:
            graph.setdefault(edge.source, set()).add(edge.target)
        return graph

    def dependents(self) -> dict[str, set[str]]:
        reverse: dict[str, set[str]] = {module: set() for module in self.module_to_path}
        for edge in self.edges:
            reverse.setdefault(edge.target, set()).add(edge.source)
        return reverse

    def _walk(self, start: str, graph: dict[str, set[str]]) -> list[str]:
        if start not in self.module_to_path:
            return []
        seen: set[str] = set()
        queue: deque[str] = deque(sorted(graph.get(start, set())))
        while queue:
            current = queue.popleft()
            if current == start or current in seen:
                continue
            seen.add(current)
            queue.extend(sorted(graph.get(current, set()) - seen))
        return sorted(seen)

    def transitive_dependencies(self, module: str) -> list[str]:
        return self._walk(module, self.dependencies())

    def transitive_dependents(self, module: str) -> list[str]:
        return self._walk(module, self.dependents())

    def module_for(self, value: str) -> str | None:
        cleaned = str(value or "").strip().replace("\\", "/")
        if cleaned in self.module_to_path:
            return cleaned
        return self.path_to_module.get(cleaned)

    def impacted_entrypoints(self, module: str) -> list[str]:
        downstream = set(self.transitive_dependents(module)) | {module}
        hits = []
        for candidate in sorted(downstream):
            path = self.module_to_path.get(candidate, "")
            if path in DEFAULT_ENTRYPOINT_PATHS:
                hits.append(path)
        return hits

    def protected_reach(self, module: str) -> list[str]:
        related = (
            set(self.transitive_dependencies(module))
            | set(self.transitive_dependents(module))
            | {module}
        )
        protected: list[str] = []
        for candidate in sorted(related):
            path = self.module_to_path.get(candidate, "")
            lowered = f"{candidate} {path}".lower()
            if any(marker in lowered for marker in PROTECTED_NAME_MARKERS):
                protected.append(path or candidate)
        return protected

    def impact_report(self, value: str) -> dict[str, Any]:
        module = self.module_for(value)
        if module is None:
            return {
                "version": DEPENDENCY_MAP_VERSION,
                "status": "NOT_FOUND",
                "query": value,
                "projection_weight": PROJECTION_WEIGHT,
                "may_modify_projection": MAY_MODIFY_PROJECTION,
            }

        deps = self.dependencies()
        reverse = self.dependents()
        direct_dependencies = sorted(deps.get(module, set()))
        direct_dependents = sorted(reverse.get(module, set()))
        transitive_dependencies = self.transitive_dependencies(module)
        transitive_dependents = self.transitive_dependents(module)
        entrypoints = self.impacted_entrypoints(module)
        protected = self.protected_reach(module)

        blast_radius = len(transitive_dependents)
        if entrypoints and blast_radius >= 20:
            risk = "CRITICAL"
        elif entrypoints or blast_radius >= 10:
            risk = "HIGH"
        elif blast_radius >= 3:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        return {
            "version": DEPENDENCY_MAP_VERSION,
            "status": "OK",
            "query": value,
            "module": module,
            "path": self.module_to_path[module],
            "risk": risk,
            "blast_radius": blast_radius,
            "direct_dependencies": direct_dependencies,
            "direct_dependents": direct_dependents,
            "transitive_dependencies": transitive_dependencies,
            "transitive_dependents": transitive_dependents,
            "impacted_entrypoints": entrypoints,
            "protected_reach": protected,
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
        }

    def snapshot(self) -> dict[str, Any]:
        deps = self.dependencies()
        reverse = self.dependents()
        busiest = sorted(
            (
                {
                    "module": module,
                    "path": self.module_to_path[module],
                    "direct_dependents": len(reverse.get(module, set())),
                    "direct_dependencies": len(deps.get(module, set())),
                    "blast_radius": len(self.transitive_dependents(module)),
                }
                for module in self.module_to_path
            ),
            key=lambda row: (-row["blast_radius"], -row["direct_dependents"], row["module"]),
        )
        return {
            "version": DEPENDENCY_MAP_VERSION,
            "root": str(self.root),
            "modules": len(self.module_to_path),
            "edges": len(self.edges),
            "parse_errors": list(self.parse_errors),
            "entrypoints": [
                path for path in sorted(DEFAULT_ENTRYPOINT_PATHS) if path in self.path_to_module
            ],
            "highest_blast_radius": busiest[:25],
            "projection_weight": PROJECTION_WEIGHT,
            "may_modify_projection": MAY_MODIFY_PROJECTION,
        }


def _module_name(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    parts = list(relative.parts)
    parts[-1] = parts[-1][:-3]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _python_files(root: Path, excluded_dirs: Iterable[str]) -> list[Path]:
    excluded = set(excluded_dirs)
    files: list[Path] = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts[:-1]):
            continue
        files.append(path)
    return sorted(files)


def _string_constants(tree: ast.AST) -> dict[str, str]:
    values: dict[str, str] = {}
    for node in getattr(tree, "body", []):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            values[target.id] = value.value
    return values


def _literal_or_named_string(node: ast.AST, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _resolve_local_module(name: str, modules: set[str]) -> str | None:
    candidate = str(name or "").strip().strip(".")
    if not candidate:
        return None
    if candidate in modules:
        return candidate
    parts = candidate.split(".")
    while len(parts) > 1:
        parts.pop()
        parent = ".".join(parts)
        if parent in modules:
            return parent
    return None


def _resolve_relative(current: str, level: int, module: str | None) -> str:
    package_parts = current.split(".")[:-1]
    if level > 0:
        keep = max(0, len(package_parts) - (level - 1))
        package_parts = package_parts[:keep]
    if module:
        package_parts.extend(module.split("."))
    return ".".join(part for part in package_parts if part)


def _extract_edges(
    *,
    tree: ast.AST,
    current: str,
    modules: set[str],
) -> list[ImportEdge]:
    edges: list[ImportEdge] = []
    constants = _string_constants(tree)

    def add(target_name: str | None, kind: str, lineno: int) -> None:
        if not target_name:
            return
        target = _resolve_local_module(target_name, modules)
        if target and target != current:
            edges.append(ImportEdge(current, target, kind, lineno))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add(alias.name, "import", getattr(node, "lineno", 0))
            continue

        if isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative(current, node.level, node.module)
                if node.level
                else str(node.module or "")
            )
            # Prefer an imported child module when one exists; otherwise the
            # package/base module is the dependency.
            child_added = False
            for alias in node.names:
                child = f"{base}.{alias.name}" if base else alias.name
                resolved_child = _resolve_local_module(child, modules)
                if resolved_child == child and resolved_child != current:
                    add(child, "from_import", getattr(node, "lineno", 0))
                    child_added = True
            if not child_added:
                add(base, "from_import", getattr(node, "lineno", 0))
            continue

        if isinstance(node, ast.Call) and node.args:
            function_name = ""
            if isinstance(node.func, ast.Name):
                function_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                function_name = node.func.attr
            if function_name not in {"import_module", "__import__", "_import"}:
                continue
            target_name = _literal_or_named_string(node.args[0], constants)
            add(target_name, "dynamic_import", getattr(node, "lineno", 0))

    # Deduplicate repeated AST hits while preserving the most useful line/kind.
    unique: dict[tuple[str, str, str], ImportEdge] = {}
    for edge in edges:
        unique[(edge.source, edge.target, edge.kind)] = edge
    return sorted(unique.values(), key=lambda edge: (edge.source, edge.target, edge.kind, edge.lineno))


def build_dependency_map(
    root: str | Path,
    *,
    excluded_dirs: Iterable[str] = DEFAULT_EXCLUDED_DIRS,
) -> DependencyMap:
    root_path = Path(root).resolve()
    module_to_path: dict[str, str] = {}
    paths: dict[str, Path] = {}

    for path in _python_files(root_path, excluded_dirs):
        module = _module_name(root_path, path)
        if not module:
            continue
        module_to_path[module] = path.relative_to(root_path).as_posix()
        paths[module] = path

    modules = set(module_to_path)
    edges: list[ImportEdge] = []
    parse_errors: list[dict[str, str]] = []

    for module, path in sorted(paths.items()):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            parse_errors.append(
                {
                    "module": module,
                    "path": module_to_path[module],
                    "error": f"{exc.__class__.__name__}: {exc}"[:300],
                }
            )
            continue
        edges.extend(_extract_edges(tree=tree, current=module, modules=modules))

    return DependencyMap(
        root=root_path,
        module_to_path=module_to_path,
        edges=edges,
        parse_errors=parse_errors,
    )


def _compact_report(report: dict[str, Any]) -> str:
    if report.get("status") != "OK":
        return f"Monster Dependency Map: {report.get('query')} was not found."
    entrypoints = ", ".join(report.get("impacted_entrypoints") or []) or "none"
    return (
        f"{report['risk']} • {report['path']} • blast radius {report['blast_radius']} • "
        f"direct dependents {len(report['direct_dependents'])} • entrypoints {entrypoints}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monster Dependency Map V1")
    parser.add_argument("target", nargs="?", help="Python module or repository-relative .py path")
    parser.add_argument("--root", default=".", help="Repository root (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--snapshot", action="store_true", help="Print repository dependency summary")
    args = parser.parse_args(argv)

    dependency_map = build_dependency_map(args.root)
    if args.snapshot or not args.target:
        payload = dependency_map.snapshot()
    else:
        payload = dependency_map.impact_report(args.target)

    if args.json or args.snapshot:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_compact_report(payload))
    return 0 if payload.get("status", "OK") != "NOT_FOUND" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "DEPENDENCY_MAP_VERSION",
    "MAY_MODIFY_PROJECTION",
    "PROJECTION_WEIGHT",
    "DependencyMap",
    "ImportEdge",
    "build_dependency_map",
    "main",
]
