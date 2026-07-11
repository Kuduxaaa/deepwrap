from __future__ import annotations

import ast
import hashlib
import json

from pathlib import Path
from typing import Any

from deepwrap.function_calling import Tool


class ProjectIntelligence:
    """Persistent structural index of project files, symbols, imports, and calls."""

    def __init__(self, root: str | Path, index_path: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.index_path = Path(index_path).expanduser().resolve()
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, Any] = {"files": {}}
        if self.index_path.is_file():
            try:
                self.data = json.loads(self.index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

    @staticmethod
    def _hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def index_project(self, glob: str = "**/*.py") -> dict[str, Any]:
        files = self.data.setdefault("files", {})
        seen: set[str] = set()
        changed = 0
        errors: list[dict[str, str]] = []
        for path in self.root.glob(glob):
            if not path.is_file() or ".git" in path.parts:
                continue
            relative = str(path.relative_to(self.root))
            seen.add(relative)
            digest = self._hash(path)
            if files.get(relative, {}).get("hash") == digest:
                continue
            try:
                files[relative] = self._analyze_python(path, digest)
                changed += 1
            except (OSError, SyntaxError) as exc:
                errors.append({"path": relative, "error": str(exc)})
        removed = [path for path in files if path not in seen]
        for path in removed:
            files.pop(path, None)
        self.index_path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        return {
            "root": str(self.root),
            "files": len(files),
            "changed": changed,
            "removed": removed,
            "errors": errors,
        }

    def _analyze_python(self, path: Path, digest: str) -> dict[str, Any]:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        symbols: list[dict[str, Any]] = []
        imports: list[str] = []
        calls: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(
                    {
                        "name": node.name,
                        "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                        "line": node.lineno,
                        "end_line": getattr(node, "end_lineno", node.lineno),
                    }
                )
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.extend(f"{module}.{alias.name}".strip(".") for alias in node.names)
            elif isinstance(node, ast.Call):
                name = self._call_name(node.func)
                if name:
                    calls.append({"name": name, "line": node.lineno})
        return {
            "hash": digest,
            "lines": len(source.splitlines()),
            "symbols": symbols,
            "imports": sorted(set(imports)),
            "calls": calls,
        }

    @staticmethod
    def _call_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = ProjectIntelligence._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return None

    def overview(self) -> dict[str, Any]:
        files = self.data.get("files", {})
        return {
            "root": str(self.root),
            "files": len(files),
            "lines": sum(item.get("lines", 0) for item in files.values()),
            "symbols": sum(len(item.get("symbols", [])) for item in files.values()),
            "imports": sorted({value for item in files.values() for value in item.get("imports", [])}),
        }

    def find_symbol(self, query: str) -> list[dict[str, Any]]:
        query = query.lower()
        results = []
        for path, item in self.data.get("files", {}).items():
            for symbol in item.get("symbols", []):
                if query in symbol["name"].lower():
                    results.append({"path": path, **symbol})
        return results

    def references(self, name: str) -> list[dict[str, Any]]:
        results = []
        for path, item in self.data.get("files", {}).items():
            for call in item.get("calls", []):
                if call["name"] == name or call["name"].endswith(f".{name}"):
                    results.append({"path": path, **call})
        return results

    @property
    def definitions(self) -> tuple[Tool, ...]:
        return (
            Tool("index_project", "Incrementally index project files into a structural intelligence graph.", {"type": "object", "properties": {"glob": {"type": "string", "default": "**/*.py"}}}),
            Tool("project_overview", "Return indexed project size, symbols, and dependencies.", {"type": "object", "properties": {}}),
            Tool("find_symbol", "Find classes or functions by name with source locations.", {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
            Tool("find_references", "Find indexed call sites for a function or method name.", {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}),
        )

    @property
    def functions(self) -> dict[str, Any]:
        return {
            "index_project": self.index_project,
            "project_overview": self.overview,
            "find_symbol": self.find_symbol,
            "find_references": self.references,
        }
