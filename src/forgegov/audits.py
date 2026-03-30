"""Standard quality audits for forge packages.

Goes deeper than contract enforcement — checks code quality patterns
that indicate incomplete or broken implementations.

These run as part of the pipeline 'audit' stage or standalone via CLI.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from .contracts import _walk_python_files
from .registry import PackageInfo


@dataclass
class AuditFinding:
    """A single audit finding."""

    package: str
    file: str
    line: int
    audit: str
    message: str
    severity: str = "warning"  # info, warning, error

    def __str__(self) -> str:
        return f"{self.package}:{self.file}:{self.line} [{self.audit}] {self.message}"


@dataclass
class AuditResult:
    """Result of running audits on one or more packages."""

    findings: list[AuditFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    def by_audit(self) -> dict[str, list[AuditFinding]]:
        result: dict[str, list[AuditFinding]] = {}
        for f in self.findings:
            result.setdefault(f.audit, []).append(f)
        return result


# ---------------------------------------------------------------------------
# Audit: Stub Detection
# ---------------------------------------------------------------------------

_STUB_BODIES = {"pass", "...", "Ellipsis"}


def audit_stubs(pkg: PackageInfo) -> list[AuditFinding]:
    """Find functions/methods that are stubs (empty or raise NotImplementedError)."""
    findings = []
    if not pkg.location.is_dir():
        return findings

    for module_name, py_file in _walk_python_files(pkg.location):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        filepath = str(py_file.relative_to(pkg.location))

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue  # Skip private functions

            body = node.body
            # Strip docstring
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, (ast.Constant, ast.Str))):
                body = body[1:]

            if not body:
                findings.append(AuditFinding(
                    package=pkg.name, file=filepath, line=node.lineno,
                    audit="STUB", message=f"Function '{node.name}' has empty body",
                ))
                continue

            # Single statement: pass, ..., or raise NotImplementedError
            if len(body) == 1:
                stmt = body[0]
                if isinstance(stmt, ast.Pass):
                    findings.append(AuditFinding(
                        package=pkg.name, file=filepath, line=node.lineno,
                        audit="STUB", message=f"Function '{node.name}' is a stub (pass)",
                    ))
                elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                    if repr(stmt.value.value) in _STUB_BODIES:
                        findings.append(AuditFinding(
                            package=pkg.name, file=filepath, line=node.lineno,
                            audit="STUB", message=f"Function '{node.name}' is a stub (...)",
                        ))
                elif isinstance(stmt, ast.Raise):
                    if (isinstance(stmt.exc, ast.Call)
                            and isinstance(stmt.exc.func, ast.Name)
                            and stmt.exc.func.id == "NotImplementedError"):
                        findings.append(AuditFinding(
                            package=pkg.name, file=filepath, line=node.lineno,
                            audit="STUB",
                            message=f"Function '{node.name}' raises NotImplementedError",
                            severity="error",
                        ))

    return findings


# ---------------------------------------------------------------------------
# Audit: TODO/FIXME/HACK comments
# ---------------------------------------------------------------------------

_MARKER_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX|TEMP|TEMPORARY)\b", re.IGNORECASE)


def audit_markers(pkg: PackageInfo) -> list[AuditFinding]:
    """Find TODO/FIXME/HACK comments in source code."""
    findings = []
    if not pkg.location.is_dir():
        return findings

    for module_name, py_file in _walk_python_files(pkg.location):
        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        filepath = str(py_file.relative_to(pkg.location))

        for lineno, line in enumerate(lines, 1):
            # Only check comments
            comment_idx = line.find("#")
            if comment_idx == -1:
                continue
            comment = line[comment_idx:]
            match = _MARKER_PATTERN.search(comment)
            if match:
                marker = match.group(1).upper()
                severity = "error" if marker in ("FIXME", "HACK") else "warning"
                findings.append(AuditFinding(
                    package=pkg.name, file=filepath, line=lineno,
                    audit="MARKER", message=f"{marker}: {comment.strip()[:100]}",
                    severity=severity,
                ))

    return findings


# ---------------------------------------------------------------------------
# Audit: Untested Exports
# ---------------------------------------------------------------------------

def audit_untested_exports(pkg: PackageInfo) -> list[AuditFinding]:
    """Check that every name in __all__ has at least one test reference."""
    findings = []
    if not pkg.location.is_dir():
        return findings

    # Get __all__ from package __init__.py
    init_path = pkg.location / "__init__.py"
    if not init_path.exists():
        return findings

    try:
        source = init_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return findings

    all_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                all_names.append(elt.value)

    if not all_names:
        return findings

    # Find project root and scan test files
    root = pkg.location
    for _ in range(5):
        if (root / "tests").exists():
            break
        root = root.parent
    else:
        return findings

    test_dir = root / "tests"
    if not test_dir.exists():
        return findings

    # Collect all text from test files
    test_text = ""
    for test_file in test_dir.glob("test_*.py"):
        try:
            test_text += test_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

    # Check each exported name
    for name in all_names:
        if name.startswith("_"):
            continue
        # Check if the name appears in test files (as import, call, or reference)
        if name not in test_text:
            findings.append(AuditFinding(
                package=pkg.name, file="__init__.py", line=0,
                audit="UNTESTED_EXPORT",
                message=f"Exported name '{name}' not referenced in any test file",
                severity="warning",
            ))

    return findings


# ---------------------------------------------------------------------------
# Audit: Existence-only tests (TST-001 §10.6)
# ---------------------------------------------------------------------------

_WEAK_ASSERTIONS = {
    "assertIsNotNone", "assertIsInstance", "assertTrue",
    "is not None", "is_not_none", "isinstance(",
}


def audit_test_quality(pkg: PackageInfo) -> list[AuditFinding]:
    """Flag tests that only check existence, not behavior."""
    findings = []

    root = pkg.location
    for _ in range(5):
        if (root / "tests").exists():
            break
        root = root.parent
    else:
        return findings

    test_dir = root / "tests"

    for test_file in sorted(test_dir.glob("test_*.py")):
        try:
            source = test_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(test_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        filepath = test_file.name

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue

            # Count assertions in the test
            assertions = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute):
                        if child.func.attr.startswith("assert"):
                            assertions.append(child.func.attr)
                    elif isinstance(child.func, ast.Name):
                        if child.func.id == "assert":
                            assertions.append("assert")
                elif isinstance(child, ast.Assert):
                    # Check what's being asserted
                    if isinstance(child.test, ast.Compare):
                        # assert x is not None
                        for op in child.test.ops:
                            if isinstance(op, ast.IsNot):
                                assertions.append("is_not_none")
                            elif isinstance(op, ast.Is):
                                assertions.append("is_check")
                            else:
                                assertions.append("value_check")
                    elif isinstance(child.test, ast.Call):
                        if (isinstance(child.test.func, ast.Name)
                                and child.test.func.id == "isinstance"):
                            assertions.append("isinstance")
                        else:
                            assertions.append("value_check")
                    else:
                        assertions.append("value_check")

            if not assertions:
                findings.append(AuditFinding(
                    package=pkg.name, file=filepath, line=node.lineno,
                    audit="WEAK_TEST",
                    message=f"Test '{node.name}' has no assertions",
                    severity="warning",
                ))
            elif all(a in ("is_not_none", "isinstance", "is_check") for a in assertions):
                findings.append(AuditFinding(
                    package=pkg.name, file=filepath, line=node.lineno,
                    audit="WEAK_TEST",
                    message=f"Test '{node.name}' only checks existence/type, not behavior",
                    severity="info",
                ))

    return findings


# ---------------------------------------------------------------------------
# Audit: Regression detection (diff against previous report)
# ---------------------------------------------------------------------------

def audit_regression(current_report: dict, previous_report: dict | None) -> list[AuditFinding]:
    """Compare current pipeline report against previous to detect regressions."""
    findings = []
    if previous_report is None:
        return findings

    prev_stages = {s["stage"]: s for s in previous_report.get("stages", [])}
    curr_stages = {s["stage"]: s for s in current_report.get("stages", [])}

    for stage, prev in prev_stages.items():
        curr = curr_stages.get(stage)
        if curr is None:
            continue
        if prev.get("passed") and not curr.get("passed"):
            findings.append(AuditFinding(
                package="ecosystem", file="", line=0,
                audit="REGRESSION",
                message=f"Stage '{stage}' was passing, now fails: {curr.get('detail', '')}",
                severity="error",
            ))

    # Package-level regressions
    prev_pkgs = previous_report.get("packages", {})
    curr_pkgs = current_report.get("packages", {})
    for pkg_name, prev_info in prev_pkgs.items():
        curr_info = curr_pkgs.get(pkg_name)
        if curr_info is None:
            findings.append(AuditFinding(
                package=pkg_name, file="", line=0,
                audit="REGRESSION",
                message=f"Package '{pkg_name}' was present, now missing",
                severity="error",
            ))

    return findings


# ---------------------------------------------------------------------------
# Run all audits
# ---------------------------------------------------------------------------

ALL_AUDITS = {
    "stubs": audit_stubs,
    "markers": audit_markers,
    "untested_exports": audit_untested_exports,
    "test_quality": audit_test_quality,
}


def run_audits(
    packages: list[PackageInfo],
    audits: list[str] | None = None,
) -> AuditResult:
    """Run standard audits across packages.

    Args:
        packages: List of PackageInfo from registry.scan()
        audits: Specific audits to run. None = all.

    Returns:
        AuditResult with findings.
    """
    result = AuditResult()
    audit_fns = {k: v for k, v in ALL_AUDITS.items() if audits is None or k in audits}

    for pkg in packages:
        for audit_name, audit_fn in audit_fns.items():
            findings = audit_fn(pkg)
            result.findings.extend(findings)

    return result
