"""Tests for forgegov.cli — command-line interface."""

import pytest
from forgegov.cli import main


class TestCLI:
    def test_no_args_returns_zero(self):
        rc = main([])
        assert rc == 0

    def test_status_command(self):
        rc = main(["status"])
        assert rc == 0

    def test_check_command_all(self):
        # May return 0 or 1 depending on contract state, but should not crash
        rc = main(["check"])
        assert rc in (0, 1)

    def test_check_nonexistent_package(self):
        rc = main(["check", "forge_nonexistent_xyz"])
        assert rc == 1

    def test_compat_command(self):
        rc = main(["compat"])
        assert rc == 0

    def test_run_contract_only(self):
        rc = main(["run", "--stage", "contract"])
        assert rc in (0, 1)

    def test_run_integration_only(self):
        rc = main(["run", "--stage", "integration"])
        assert rc in (0, 1)
