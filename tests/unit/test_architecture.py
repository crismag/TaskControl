"""Executable enforcement of the dependency rules.

``development/engineering/repository/11_DEPENDENCY_RULES.md`` states the forbidden import
edges. Prose does not fail a build, so this module turns those rules into a test that
does.

The checker parses source with :mod:`ast` rather than importing modules, so a violation is
caught even when the offending module would fail to import, and no side effect of an
import can influence the result.

The final test in this file checks the checker itself: it feeds a deliberately
non-compliant sample through the same code path and asserts a violation is reported. A
rule engine that cannot fail is not enforcement.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "taskcontrol"

FORBIDDEN_IMPORTS: dict[str, frozenset[str]] = {
    "domain": frozenset(
        {
            "fastapi",
            "starlette",
            "typer",
            "click",
            "sqlalchemy",
            "alembic",
            "pydantic",
            "pydantic_settings",
            "httpx",
            "requests",
            "uvicorn",
            "taskcontrol.adapters",
            "taskcontrol.api",
            "taskcontrol.apps",
            "taskcontrol.application",
            "taskcontrol.cli",
            "taskcontrol.infrastructure",
        }
    ),
    "application": frozenset(
        {
            "fastapi",
            "starlette",
            "typer",
            "click",
            "sqlalchemy",
            "alembic",
            "uvicorn",
            "taskcontrol.adapters",
            "taskcontrol.api",
            "taskcontrol.apps",
            "taskcontrol.cli",
        }
    ),
    "ports": frozenset(
        {
            "fastapi",
            "starlette",
            "typer",
            "sqlalchemy",
            "taskcontrol.adapters",
            "taskcontrol.api",
            "taskcontrol.apps",
            "taskcontrol.cli",
            "taskcontrol.infrastructure",
        }
    ),
    "adapters": frozenset({"taskcontrol.api", "taskcontrol.cli", "taskcontrol.apps"}),
    "api": frozenset({"typer", "click", "taskcontrol.cli", "taskcontrol.apps", "sqlalchemy"}),
    "cli": frozenset({"fastapi", "taskcontrol.api", "taskcontrol.apps", "sqlalchemy"}),
    "infrastructure": frozenset(
        {
            "taskcontrol.adapters",
            "taskcontrol.api",
            "taskcontrol.application",
            "taskcontrol.apps",
            "taskcontrol.cli",
            "taskcontrol.domain",
        }
    ),
    "common": frozenset(
        {
            "fastapi",
            "starlette",
            "typer",
            "sqlalchemy",
            "taskcontrol.adapters",
            "taskcontrol.api",
            "taskcontrol.application",
            "taskcontrol.apps",
            "taskcontrol.cli",
            "taskcontrol.domain",
            "taskcontrol.infrastructure",
        }
    ),
}
"""Layer -> module prefixes that layer must never import.

`domain` additionally forbids Pydantic: domain types are plain Python (standards 20).
Pydantic is a boundary technology and belongs in transport and settings.
"""

STDLIB_ONLY_LAYERS: frozenset[str] = frozenset({"domain"})
"""Layers permitted to import only the standard library and their own package."""

STANDARD_LIBRARY_ROOTS: frozenset[str] = frozenset(
    {
        "__future__",
        "abc",
        "ast",
        "base64",
        "collections",
        "contextlib",
        "contextvars",
        "copy",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "functools",
        "hashlib",
        "hmac",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "os",
        "pathlib",
        "re",
        "secrets",
        "shlex",
        "signal",
        "socket",
        "string",
        "subprocess",
        "sys",
        "textwrap",
        "threading",
        "time",
        "types",
        "typing",
        "unicodedata",
        "uuid",
        "warnings",
        "zoneinfo",
    }
)


@dataclass(frozen=True, slots=True)
class Violation:
    """One forbidden import found in one file.

    Attributes:
        module: Dotted path of the offending module, relative to the package.
        imported: The import that is not permitted.
        line: 1-indexed line number of the import statement.
        rule: Human-readable statement of the rule that was broken.
    """

    module: str
    imported: str
    line: int
    rule: str

    def __str__(self) -> str:
        """Return a message that points directly at the offending line."""
        return f"{self.module}:{self.line} imports {self.imported!r} — {self.rule}"


def _imported_names(tree: ast.AST) -> list[tuple[str, int]]:
    """Return every dotted module name imported in a parsed source tree.

    Relative imports are skipped: they cannot cross a layer boundary by construction.

    Args:
        tree: The parsed module.

    Returns:
        Pairs of imported dotted name and line number.
    """
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.module, node.lineno))
    return found


def _matches(imported: str, prefix: str) -> bool:
    """Whether an imported name is, or lives beneath, a prefix."""
    return imported == prefix or imported.startswith(f"{prefix}.")


def check_layer(layer: str, source_root: Path) -> list[Violation]:
    """Return every dependency-rule violation in one layer.

    Args:
        layer: Package name directly beneath ``taskcontrol``.
        source_root: Path to the ``taskcontrol`` package.

    Returns:
        Violations found, empty when the layer is compliant.
    """
    layer_root = source_root / layer
    if not layer_root.is_dir():
        return []

    forbidden = FORBIDDEN_IMPORTS.get(layer, frozenset())
    violations: list[Violation] = []

    for path in sorted(layer_root.rglob("*.py")):
        dotted = path.relative_to(source_root).with_suffix("").as_posix().replace("/", ".")
        module = f"taskcontrol.{dotted}"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for imported, line in _imported_names(tree):
            for prefix in forbidden:
                if _matches(imported, prefix):
                    violations.append(
                        Violation(module, imported, line, f"{layer}/ must not import {prefix}")
                    )
                    break
            else:
                if layer in STDLIB_ONLY_LAYERS:
                    root = imported.split(".")[0]
                    if root not in STANDARD_LIBRARY_ROOTS and root != "taskcontrol":
                        violations.append(
                            Violation(
                                module,
                                imported,
                                line,
                                f"{layer}/ may import only the standard library",
                            )
                        )
    return violations


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_IMPORTS))
def test_layer_has_no_forbidden_imports(layer: str) -> None:
    """Each layer imports only what the dependency rules permit."""
    violations = check_layer(layer, SOURCE_ROOT)
    assert not violations, "\n".join(str(violation) for violation in violations)


def test_composition_roots_define_no_routes_or_commands() -> None:
    """`apps/` wires; it never defines a route or a command body (ADR 0019)."""
    offenders: list[str] = []
    decorator_markers = ("router.", "app.get", "app.post", "app.put", "app.delete")

    for path in sorted((SOURCE_ROOT / "apps").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                rendered = ast.unparse(decorator)
                if any(marker in rendered for marker in decorator_markers):
                    offenders.append(f"{path.name}:{node.lineno} {node.name} @{rendered}")

    assert not offenders, "Composition roots must not define routes or commands:\n" + "\n".join(
        offenders
    )


def test_every_layer_directory_is_covered_by_a_rule() -> None:
    """A new top-level layer cannot be added without deciding its import rules."""
    on_disk = {
        path.name
        for path in SOURCE_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }
    unruled = on_disk - set(FORBIDDEN_IMPORTS) - {"apps"}
    assert not unruled, (
        f"Layers without a dependency rule: {sorted(unruled)}. "
        "Add them to FORBIDDEN_IMPORTS and to 11_DEPENDENCY_RULES.md."
    )


def test_checker_detects_a_deliberate_violation(tmp_path: Path) -> None:
    """The checker fails on non-compliant source.

    Without this, a checker that silently matched nothing would report a green build
    forever. It is the acceptance criterion for Wave 0's architecture test.
    """
    domain = tmp_path / "taskcontrol" / "domain"
    domain.mkdir(parents=True)
    (domain / "__init__.py").write_text("", encoding="utf-8")
    (domain / "offender.py").write_text(
        "import sqlalchemy\nfrom taskcontrol.api import dependencies\n",
        encoding="utf-8",
    )

    violations = check_layer("domain", tmp_path / "taskcontrol")

    imported = {violation.imported for violation in violations}
    assert "sqlalchemy" in imported
    assert "taskcontrol.api" in imported


def test_checker_accepts_compliant_source(tmp_path: Path) -> None:
    """The checker does not report a violation for compliant source."""
    domain = tmp_path / "taskcontrol" / "domain"
    domain.mkdir(parents=True)
    (domain / "__init__.py").write_text("", encoding="utf-8")
    (domain / "good.py").write_text(
        "from __future__ import annotations\n"
        "import dataclasses\n"
        "from enum import StrEnum\n"
        "from taskcontrol.domain import something\n",
        encoding="utf-8",
    )

    assert check_layer("domain", tmp_path / "taskcontrol") == []
