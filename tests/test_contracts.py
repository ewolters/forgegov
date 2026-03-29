"""Tests for forgegov.contracts — contract enforcement."""

import ast
import textwrap
from pathlib import Path

import pytest
from forgegov.contracts import (
    ContractResult,
    ContractViolation,
    _check_banned_imports,
    _check_file_io,
    _check_structure,
    check,
    check_one,
)
from forgegov.registry import PackageInfo, scan


class TestBannedImports:
    def test_detects_django_import(self):
        code = "import django"
        tree = ast.parse(code)
        violations = _check_banned_imports(tree, "testpkg", "bad.py")
        assert len(violations) == 1
        assert violations[0].rule == "NO_FRAMEWORK"
        assert "django" in violations[0].message

    def test_detects_django_submodule(self):
        code = "from django.conf import settings"
        tree = ast.parse(code)
        violations = _check_banned_imports(tree, "testpkg", "bad.py")
        assert len(violations) == 1
        assert "django.conf" in violations[0].message

    def test_detects_flask(self):
        code = "from flask import Flask"
        tree = ast.parse(code)
        violations = _check_banned_imports(tree, "testpkg", "bad.py")
        assert len(violations) == 1

    def test_detects_anthropic(self):
        code = "import anthropic"
        tree = ast.parse(code)
        violations = _check_banned_imports(tree, "testpkg", "bad.py")
        assert len(violations) == 1
        assert "LLM SDK" in violations[0].message

    def test_allows_numpy(self):
        code = "import numpy as np\nfrom scipy import stats"
        tree = ast.parse(code)
        violations = _check_banned_imports(tree, "testpkg", "clean.py")
        assert len(violations) == 0

    def test_allows_stdlib(self):
        code = "import math\nimport statistics\nfrom dataclasses import dataclass"
        tree = ast.parse(code)
        violations = _check_banned_imports(tree, "testpkg", "clean.py")
        assert len(violations) == 0

    def test_detects_multiple_violations(self):
        code = "import django\nimport anthropic\nfrom flask import Flask"
        tree = ast.parse(code)
        violations = _check_banned_imports(tree, "testpkg", "bad.py")
        assert len(violations) == 3


class TestFileIO:
    def test_detects_open_call(self):
        code = "f = open('file.txt', 'r')"
        tree = ast.parse(code)
        violations = _check_file_io(tree, "testpkg", "core", "core.py")
        assert len(violations) == 1
        assert violations[0].rule == "NO_IO"

    def test_detects_path_read_text(self):
        code = "from pathlib import Path\ndata = Path('x').read_text()"
        tree = ast.parse(code)
        violations = _check_file_io(tree, "testpkg", "core", "core.py")
        assert len(violations) == 1

    def test_detects_path_write_bytes(self):
        code = "p.write_bytes(data)"
        tree = ast.parse(code)
        violations = _check_file_io(tree, "testpkg", "core", "core.py")
        assert len(violations) == 1

    def test_allows_io_in_calibration_module(self):
        code = "f = open('golden.json', 'r')"
        tree = ast.parse(code)
        # forgespc.calibration is in the IO_ALLOWED_MODULES
        violations = _check_file_io(tree, "forgespc", "calibration", "calibration.py")
        assert len(violations) == 0

    def test_allows_io_in_forgedoc(self):
        code = "f = open('output.pdf', 'wb')"
        tree = ast.parse(code)
        # forgedoc has wildcard IO allowance
        violations = _check_file_io(tree, "forgedoc", "renderers.pdf", "renderers/pdf.py")
        assert len(violations) == 0

    def test_blocks_io_in_unknown_module(self):
        code = "f = open('data.csv', 'r')"
        tree = ast.parse(code)
        violations = _check_file_io(tree, "forgespc", "charts", "charts.py")
        assert len(violations) == 1


class TestStructureChecks:
    def test_missing_version_is_error(self):
        pkg = PackageInfo(
            name="testpkg", version="unknown", location=Path("/tmp"),
            has_init=True, has_version=False, has_py_typed=False,
            has_calibration=False, has_all_export=False,
        )
        violations = _check_structure(pkg)
        version_violations = [v for v in violations if v.rule == "HAS_VERSION"]
        assert len(version_violations) == 1
        assert version_violations[0].severity == "error"

    def test_missing_py_typed_is_warning(self):
        pkg = PackageInfo(
            name="testpkg", version="0.1.0", location=Path("/tmp"),
            has_init=True, has_version=True, has_py_typed=False,
            has_calibration=True, has_all_export=True,
        )
        violations = _check_structure(pkg)
        typed_violations = [v for v in violations if v.rule == "HAS_PY_TYPED"]
        assert len(typed_violations) == 1
        assert typed_violations[0].severity == "warning"

    def test_missing_calibration_is_warning(self):
        pkg = PackageInfo(
            name="testpkg", version="0.1.0", location=Path("/tmp"),
            has_init=True, has_version=True, has_py_typed=True,
            has_calibration=False, has_all_export=True,
        )
        violations = _check_structure(pkg)
        cal_violations = [v for v in violations if v.rule == "HAS_CALIBRATION"]
        assert len(cal_violations) == 1
        assert cal_violations[0].severity == "warning"

    def test_missing_all_is_warning(self):
        pkg = PackageInfo(
            name="testpkg", version="0.1.0", location=Path("/tmp"),
            has_init=True, has_version=True, has_py_typed=True,
            has_calibration=True, has_all_export=False,
        )
        violations = _check_structure(pkg)
        all_violations = [v for v in violations if v.rule == "HAS_ALL"]
        assert len(all_violations) == 1
        assert all_violations[0].severity == "warning"

    def test_fully_compliant_no_errors(self):
        pkg = PackageInfo(
            name="testpkg", version="0.1.0", location=Path("/tmp"),
            has_init=True, has_version=True, has_py_typed=True,
            has_calibration=True, has_all_export=True,
        )
        violations = _check_structure(pkg)
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) == 0


class TestCheckIntegration:
    def test_check_real_packages(self):
        """Run contract checks on actually installed forge packages."""
        scan_result = scan()
        if not scan_result.packages:
            pytest.skip("No forge packages installed")
        result = check(scan_result)
        assert isinstance(result, ContractResult)
        # Should not find any banned framework imports in real forge packages
        framework_errors = [v for v in result.errors if v.rule == "NO_FRAMEWORK"]
        assert len(framework_errors) == 0, (
            f"Found framework imports in forge packages: {framework_errors}"
        )

    def test_check_one_real_package(self):
        """Check a single real package."""
        scan_result = scan()
        if not scan_result.packages:
            pytest.skip("No forge packages installed")
        pkg = scan_result.packages[0]
        result = check_one(pkg)
        assert isinstance(result, ContractResult)


class TestContractViolation:
    def test_str_format(self):
        v = ContractViolation(
            package="forgespc", file="charts.py", line=42,
            rule="NO_FRAMEWORK", message="Banned import 'django'",
        )
        s = str(v)
        assert "forgespc" in s
        assert "charts.py" in s
        assert "42" in s
        assert "NO_FRAMEWORK" in s

    def test_contract_result_passed(self):
        result = ContractResult(violations=[])
        assert result.passed is True

    def test_contract_result_failed_with_error(self):
        result = ContractResult(violations=[
            ContractViolation("pkg", "f.py", 1, "X", "bad", severity="error"),
        ])
        assert result.passed is False

    def test_contract_result_passed_with_warnings_only(self):
        result = ContractResult(violations=[
            ContractViolation("pkg", "f.py", 1, "X", "meh", severity="warning"),
        ])
        assert result.passed is True
