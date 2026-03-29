"""Contract enforcement for Forge packages.

Ensures every forge package follows ecosystem conventions:
- No web framework imports (Django, Flask, etc.)
- No database imports (psycopg2, sqlalchemy, django.db, etc.)
- No LLM SDK imports (anthropic, openai, etc.)
- Has __version__ in __init__.py
- Has calibration.py with get_calibration_adapter()
- File I/O isolated to designated modules only
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .registry import PackageInfo, ScanResult

logger = logging.getLogger(__name__)

# Imports that must never appear in a forge computation package.
# Keys are module prefixes, values are the reason they're banned.
BANNED_IMPORTS = {
    "django": "web framework",
    "flask": "web framework",
    "fastapi": "web framework",
    "starlette": "web framework",
    "psycopg2": "database driver",
    "sqlalchemy": "ORM/database",
    "pymongo": "database driver",
    "anthropic": "LLM SDK",
    "openai": "LLM SDK",
    "celery": "task queue",
    "redis": "external service",
}

# Modules where file I/O is acceptable (calibration data, drift history).
# Package-specific overrides — key is package name, value is set of allowed modules.
IO_ALLOWED_MODULES: dict[str, set[str]] = {
    "forgespc": {"calibration"},
    "forgecal": {"drift", "runner"},
    "forgedoc": {"*"},  # Rendering IS I/O — entire package exempt
}

# AST node names that indicate file I/O
IO_FUNCTIONS = {"open", "Path.read_text", "Path.write_text", "Path.read_bytes",
                "Path.write_bytes", "Path.mkdir", "Path.unlink", "Path.glob",
                "Path.rglob"}

IO_ATTR_NAMES = {"read_text", "write_text", "read_bytes", "write_bytes",
                 "mkdir", "unlink", "rmdir"}


@dataclass
class ContractViolation:
    """A single contract violation."""

    package: str
    file: str
    line: int
    rule: str
    message: str
    severity: str = "error"  # error, warning

    def __str__(self) -> str:
        return f"{self.package}:{self.file}:{self.line} [{self.rule}] {self.message}"


@dataclass
class ContractResult:
    """Result of contract checking for one or more packages."""

    violations: list[ContractViolation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(v.severity == "error" for v in self.violations)

    @property
    def errors(self) -> list[ContractViolation]:
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warnings(self) -> list[ContractViolation]:
        return [v for v in self.violations if v.severity == "warning"]


def _relative(path: Path, root: Path) -> str:
    """Get a display-friendly relative path."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _check_banned_imports(
    tree: ast.AST, pkg_name: str, filepath: str
) -> list[ContractViolation]:
    """Check for banned imports in an AST."""
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for banned, reason in BANNED_IMPORTS.items():
                    if alias.name == banned or alias.name.startswith(f"{banned}."):
                        violations.append(ContractViolation(
                            package=pkg_name,
                            file=filepath,
                            line=node.lineno,
                            rule="NO_FRAMEWORK",
                            message=f"Banned import '{alias.name}' ({reason})",
                        ))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for banned, reason in BANNED_IMPORTS.items():
                    if node.module == banned or node.module.startswith(f"{banned}."):
                        violations.append(ContractViolation(
                            package=pkg_name,
                            file=filepath,
                            line=node.lineno,
                            rule="NO_FRAMEWORK",
                            message=f"Banned import from '{node.module}' ({reason})",
                        ))
    return violations


def _check_file_io(
    tree: ast.AST, pkg_name: str, module_name: str, filepath: str
) -> list[ContractViolation]:
    """Check for file I/O in modules where it's not allowed."""
    allowed = IO_ALLOWED_MODULES.get(pkg_name, set())
    if "*" in allowed or module_name in allowed:
        return []

    violations = []
    for node in ast.walk(tree):
        # open() calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                violations.append(ContractViolation(
                    package=pkg_name,
                    file=filepath,
                    line=node.lineno,
                    rule="NO_IO",
                    message="File I/O (open) not allowed in this module",
                ))
            # Path method calls like path.read_text()
            elif isinstance(node.func, ast.Attribute) and node.func.attr in IO_ATTR_NAMES:
                violations.append(ContractViolation(
                    package=pkg_name,
                    file=filepath,
                    line=node.lineno,
                    rule="NO_IO",
                    message=f"File I/O (.{node.func.attr}) not allowed in this module",
                ))
    return violations


def _check_structure(pkg: PackageInfo) -> list[ContractViolation]:
    """Check structural conventions."""
    violations = []

    if not pkg.has_version:
        violations.append(ContractViolation(
            package=pkg.name,
            file="__init__.py",
            line=0,
            rule="HAS_VERSION",
            message="Missing __version__ in __init__.py",
        ))

    if not pkg.has_all_export:
        violations.append(ContractViolation(
            package=pkg.name,
            file="__init__.py",
            line=0,
            rule="HAS_ALL",
            message="Missing __all__ in __init__.py",
            severity="warning",
        ))

    if not pkg.has_py_typed:
        violations.append(ContractViolation(
            package=pkg.name,
            file="py.typed",
            line=0,
            rule="HAS_PY_TYPED",
            message="Missing py.typed marker (PEP 561)",
            severity="warning",
        ))

    if not pkg.has_calibration:
        violations.append(ContractViolation(
            package=pkg.name,
            file="calibration.py",
            line=0,
            rule="HAS_CALIBRATION",
            message="Missing calibration.py with get_calibration_adapter()",
            severity="warning",
        ))

    return violations


def _walk_python_files(pkg_dir: Path):
    """Yield (module_name, path) for all .py files in a package."""
    for py_file in sorted(pkg_dir.rglob("*.py")):
        # Derive module name from path relative to package dir
        rel = py_file.relative_to(pkg_dir)
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            module_name = ".".join(parts[:-1]) if len(parts) > 1 else "__init__"
        else:
            parts[-1] = parts[-1].removesuffix(".py")
            module_name = ".".join(parts)
        yield module_name, py_file


def check_one(pkg: PackageInfo) -> ContractResult:
    """Check contracts for a single package.

    Args:
        pkg: PackageInfo from registry.scan()

    Returns:
        ContractResult with any violations found.
    """
    result = ContractResult()
    result.violations.extend(_check_structure(pkg))

    if not pkg.location.is_dir():
        return result

    for module_name, py_file in _walk_python_files(pkg.location):
        filepath = _relative(py_file, pkg.location)
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError) as exc:
            result.violations.append(ContractViolation(
                package=pkg.name,
                file=filepath,
                line=0,
                rule="PARSEABLE",
                message=f"Cannot parse: {exc}",
            ))
            continue

        result.violations.extend(_check_banned_imports(tree, pkg.name, filepath))
        result.violations.extend(_check_file_io(tree, pkg.name, module_name, filepath))

    return result


def check(scan_result: ScanResult) -> ContractResult:
    """Check contracts across all discovered packages.

    Args:
        scan_result: ScanResult from registry.scan()

    Returns:
        ContractResult with violations from all packages.
    """
    combined = ContractResult()
    for pkg in scan_result.packages:
        pkg_result = check_one(pkg)
        combined.violations.extend(pkg_result.violations)
    return combined
