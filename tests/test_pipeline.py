"""Tests for forgegov.pipeline — CI/CD pipeline runner."""

import pytest
from forgegov.pipeline import (
    PipelineResult,
    StageResult,
    run,
    STAGES,
    _find_package_root,
)
from forgegov.registry import scan


class TestStageResult:
    def test_stage_result_defaults(self):
        s = StageResult(stage="test", passed=True)
        assert s.duration_s == 0.0
        assert s.detail == ""
        assert s.errors == []

    def test_stage_result_with_errors(self):
        s = StageResult(stage="test", passed=False, errors=["pkg: 2 failed"])
        assert not s.passed
        assert len(s.errors) == 1


class TestPipelineResult:
    def test_empty_pipeline_passes(self):
        r = PipelineResult()
        assert r.passed is True

    def test_pipeline_with_passing_stages(self):
        r = PipelineResult(stages=[
            StageResult(stage="test", passed=True),
            StageResult(stage="contract", passed=True),
        ])
        assert r.passed is True

    def test_pipeline_with_failing_stage(self):
        r = PipelineResult(stages=[
            StageResult(stage="test", passed=True),
            StageResult(stage="contract", passed=False),
        ])
        assert r.passed is False

    def test_summary_format(self):
        r = PipelineResult(
            stages=[
                StageResult(stage="test", passed=True, duration_s=1.2, detail="5 passed"),
                StageResult(stage="contract", passed=False, duration_s=0.3,
                            errors=["pkg:f.py:1 bad"]),
            ],
            total_duration_s=1.5,
        )
        summary = r.summary()
        assert "FAILED" in summary
        assert "test" in summary
        assert "contract" in summary
        assert "PASS" in summary
        assert "FAIL" in summary


class TestFindPackageRoot:
    def test_finds_root_for_installed_package(self):
        result = scan()
        if not result.packages:
            pytest.skip("No forge packages installed")
        for pkg in result.packages:
            root = _find_package_root(pkg)
            if root:
                assert (root / "pyproject.toml").exists()


class TestPipelineRun:
    def test_run_contract_stage_only(self):
        result = run(stages=["contract"])
        assert isinstance(result, PipelineResult)
        assert len(result.stages) == 1
        assert result.stages[0].stage == "contract"

    def test_run_integration_stage_only(self):
        result = run(stages=["integration"])
        assert isinstance(result, PipelineResult)
        assert len(result.stages) == 1
        assert result.stages[0].stage == "integration"

    def test_run_with_nonexistent_package(self):
        result = run(packages=["forge_nonexistent_xyz"])
        assert isinstance(result, PipelineResult)
        # No packages found, so no stages should produce errors
        assert result.scan_result is not None
        assert len(result.scan_result.packages) == 0

    def test_run_calibrate_stage(self):
        """Calibrate stage should gracefully handle missing forgecal."""
        result = run(stages=["calibrate"])
        assert isinstance(result, PipelineResult)
        assert len(result.stages) == 1
        # Should either pass (skipped) or have meaningful errors
        assert isinstance(result.stages[0].passed, bool)

    def test_run_certify_stage(self):
        """Certify stage should gracefully handle missing forgedoc."""
        result = run(stages=["certify"])
        assert isinstance(result, PipelineResult)
        assert len(result.stages) == 1
        assert isinstance(result.stages[0].passed, bool)


class TestReport:
    def test_to_dict_structure(self):
        result = run(stages=["contract"])
        d = result.to_dict()
        assert "forgegov_version" in d
        assert "timestamp" in d
        assert "passed" in d
        assert "stages" in d
        assert "packages" in d
        assert "contract_errors" in d
        assert "contract_warnings" in d
        assert isinstance(d["passed"], bool)
        assert isinstance(d["packages"], dict)

    def test_to_dict_stage_detail(self):
        result = run(stages=["contract"])
        d = result.to_dict()
        assert len(d["stages"]) == 1
        stage = d["stages"][0]
        assert stage["stage"] == "contract"
        assert "passed" in stage
        assert "errors" in stage

    def test_to_dict_packages_populated(self):
        result = run(stages=["contract"])
        d = result.to_dict()
        if d["packages"]:
            pkg = next(iter(d["packages"].values()))
            assert "version" in pkg
            assert "has_calibration" in pkg
            assert "modules" in pkg

    def test_write_report(self, tmp_path):
        result = run(stages=["contract"])
        report_path = result.write_report(tmp_path)
        assert report_path.exists()
        assert report_path.name == "forgegov_latest.json"

        import json
        data = json.loads(report_path.read_text())
        assert data["passed"] == result.passed

        # Should also write timestamped copy
        history_files = [f for f in tmp_path.iterdir() if f.name.startswith("forgegov_2")]
        assert len(history_files) == 1

    def test_write_report_is_valid_json(self, tmp_path):
        result = run(stages=["integration"])
        report_path = result.write_report(tmp_path)

        import json
        data = json.loads(report_path.read_text())
        # Should be consumable by SVEND: just check it parses and has the key field
        assert isinstance(data.get("passed"), bool)


class TestStages:
    def test_all_stages_defined(self):
        expected = {"lint", "test", "contract", "calibrate", "integration", "certify"}
        assert set(STAGES) == expected
