"""Tests for forgegov.audits — standard quality audits."""

import textwrap
from pathlib import Path

import pytest

from forgegov.audits import (
    AuditResult,
    audit_markers,
    audit_stubs,
    audit_test_quality,
    audit_untested_exports,
    audit_regression,
    run_audits,
)
from forgegov.registry import PackageInfo, scan


class TestStubDetection:
    def _make_pkg(self, tmp_path, code):
        pkg_dir = tmp_path / "fakepkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "module.py").write_text(textwrap.dedent(code))
        return PackageInfo(
            name="fakepkg", version="0.1.0", location=pkg_dir,
            has_init=True, has_version=True, has_py_typed=False,
            has_calibration=False, has_all_export=False,
        )

    def test_detects_pass_stub(self, tmp_path):
        pkg = self._make_pkg(tmp_path, '''
            def my_func():
                """Docstring."""
                pass
        ''')
        findings = audit_stubs(pkg)
        assert len(findings) == 1
        assert "stub" in findings[0].message.lower()

    def test_detects_ellipsis_stub(self, tmp_path):
        pkg = self._make_pkg(tmp_path, '''
            def my_func():
                ...
        ''')
        findings = audit_stubs(pkg)
        assert len(findings) == 1

    def test_detects_not_implemented(self, tmp_path):
        pkg = self._make_pkg(tmp_path, '''
            def my_func():
                raise NotImplementedError()
        ''')
        findings = audit_stubs(pkg)
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_ignores_real_functions(self, tmp_path):
        pkg = self._make_pkg(tmp_path, '''
            def my_func():
                return 42
        ''')
        findings = audit_stubs(pkg)
        assert len(findings) == 0

    def test_ignores_private(self, tmp_path):
        pkg = self._make_pkg(tmp_path, '''
            def _helper():
                pass
        ''')
        findings = audit_stubs(pkg)
        assert len(findings) == 0


class TestMarkerDetection:
    def _make_pkg(self, tmp_path, code):
        pkg_dir = tmp_path / "fakepkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "module.py").write_text(textwrap.dedent(code))
        return PackageInfo(
            name="fakepkg", version="0.1.0", location=pkg_dir,
            has_init=True, has_version=True, has_py_typed=False,
            has_calibration=False, has_all_export=False,
        )

    def test_detects_todo(self, tmp_path):
        pkg = self._make_pkg(tmp_path, 'x = 1  # TODO: fix this\n')
        findings = audit_markers(pkg)
        assert len(findings) == 1
        assert "TODO" in findings[0].message

    def test_detects_fixme_as_error(self, tmp_path):
        pkg = self._make_pkg(tmp_path, 'x = 1  # FIXME: broken\n')
        findings = audit_markers(pkg)
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_ignores_clean_code(self, tmp_path):
        pkg = self._make_pkg(tmp_path, 'x = 1  # Normal comment\n')
        findings = audit_markers(pkg)
        assert len(findings) == 0


class TestUntestedExports:
    def test_finds_untested(self, tmp_path):
        pkg_dir = tmp_path / "fakepkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('__all__ = ["foo", "bar"]\n')
        (pkg_dir / "core.py").write_text("def foo(): pass\ndef bar(): pass\n")
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_core.py").write_text("from fakepkg import foo\ndef test_foo(): foo()\n")

        pkg = PackageInfo(
            name="fakepkg", version="0.1.0", location=pkg_dir,
            has_init=True, has_version=True, has_py_typed=False,
            has_calibration=False, has_all_export=True,
        )
        findings = audit_untested_exports(pkg)
        assert len(findings) == 1
        assert "bar" in findings[0].message


class TestRegressionDetection:
    def test_detects_new_failure(self):
        prev = {"stages": [{"stage": "test", "passed": True}], "packages": {}}
        curr = {"stages": [{"stage": "test", "passed": False, "detail": "2 failed"}], "packages": {}}
        findings = audit_regression(curr, prev)
        assert len(findings) == 1
        assert findings[0].audit == "REGRESSION"
        assert findings[0].severity == "error"

    def test_no_regression_when_stable(self):
        report = {"stages": [{"stage": "test", "passed": True}], "packages": {"forgespc": {}}}
        findings = audit_regression(report, report)
        assert len(findings) == 0

    def test_detects_missing_package(self):
        prev = {"stages": [], "packages": {"forgespc": {}, "forgedoe": {}}}
        curr = {"stages": [], "packages": {"forgespc": {}}}
        findings = audit_regression(curr, prev)
        assert len(findings) == 1
        assert "forgedoe" in findings[0].message


class TestRunAuditsIntegration:
    def test_runs_on_real_packages(self):
        scan_result = scan()
        if not scan_result.packages:
            pytest.skip("No forge packages installed")
        result = run_audits(scan_result.packages)
        assert isinstance(result, AuditResult)
        # Should not crash on any package

    def test_filter_by_audit_name(self):
        scan_result = scan()
        if not scan_result.packages:
            pytest.skip("No forge packages installed")
        result = run_audits(scan_result.packages, audits=["stubs"])
        # All findings should be STUB type
        for f in result.findings:
            assert f.audit == "STUB"
