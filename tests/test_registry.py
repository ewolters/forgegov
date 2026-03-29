"""Tests for forgegov.registry — package discovery and metadata."""

import pytest
from forgegov.registry import scan, PackageInfo, ScanResult, KNOWN_PACKAGES


class TestScan:
    def test_scan_finds_installed_packages(self):
        result = scan()
        assert isinstance(result, ScanResult)
        # At least some of the known packages should be installed on this machine
        assert len(result.packages) > 0

    def test_scan_returns_package_info(self):
        result = scan()
        for pkg in result.packages:
            assert isinstance(pkg, PackageInfo)
            assert pkg.name
            assert pkg.version
            assert pkg.location.exists()
            assert pkg.has_init is True

    def test_scan_specific_package(self):
        result = scan(["forgespc"])
        if result.packages:
            assert len(result.packages) == 1
            assert result.packages[0].name == "forgespc"
        else:
            assert "forgespc" in result.missing

    def test_scan_nonexistent_package(self):
        result = scan(["forge_does_not_exist_xyz"])
        assert len(result.packages) == 0
        assert "forge_does_not_exist_xyz" in result.missing

    def test_scan_result_versions(self):
        result = scan()
        versions = result.versions
        for name, version in versions.items():
            assert isinstance(version, str)
            assert version != ""

    def test_scan_result_installed_names(self):
        result = scan()
        names = result.installed_names
        assert isinstance(names, list)
        for name in names:
            assert name.startswith("forge")

    def test_scan_result_get(self):
        result = scan()
        if result.packages:
            pkg = result.get(result.packages[0].name)
            assert pkg is not None
            assert pkg.name == result.packages[0].name

    def test_scan_result_get_missing(self):
        result = scan()
        assert result.get("forge_nonexistent") is None

    def test_scan_discovers_modules(self):
        result = scan()
        for pkg in result.packages:
            # Every package should have at least one module
            assert isinstance(pkg.modules, list)

    def test_missing_calibration_report(self):
        result = scan()
        missing_cal = result.missing_calibration()
        assert isinstance(missing_cal, list)
        # Packages without calibration.py should appear here
        for name in missing_cal:
            pkg = result.get(name)
            assert pkg is not None
            assert pkg.has_calibration is False


class TestKnownPackages:
    def test_known_packages_is_list(self):
        assert isinstance(KNOWN_PACKAGES, list)
        assert len(KNOWN_PACKAGES) > 0

    def test_all_known_start_with_forge(self):
        for name in KNOWN_PACKAGES:
            assert name.startswith("forge"), f"{name} doesn't start with 'forge'"
