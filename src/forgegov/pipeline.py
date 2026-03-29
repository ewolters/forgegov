"""CI/CD pipeline runner for the Forge ecosystem.

Stages:
    lint        — ruff check across all packages
    test        — pytest per-package
    contract    — forgegov contract enforcement
    calibrate   — forgecal golden reference validation
    integration — cross-package import smoke tests
    certify     — forgedoc generates calibration certificate
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .contracts import ContractResult, check
from .registry import PackageInfo, ScanResult, scan

logger = logging.getLogger(__name__)

STAGES = ["lint", "test", "contract", "calibrate", "integration", "certify"]


@dataclass
class StageResult:
    """Result of a single pipeline stage."""

    stage: str
    passed: bool
    duration_s: float = 0.0
    detail: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Result of the full pipeline run."""

    stages: list[StageResult] = field(default_factory=list)
    scan_result: ScanResult | None = None
    contract_result: ContractResult | None = None
    total_duration_s: float = 0.0

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.stages)

    def summary(self) -> str:
        lines = []
        for s in self.stages:
            icon = "PASS" if s.passed else "FAIL"
            lines.append(f"  [{icon}] {s.stage} ({s.duration_s:.1f}s)")
            for err in s.errors[:5]:
                lines.append(f"         {err}")
        status = "PASSED" if self.passed else "FAILED"
        lines.insert(0, f"Pipeline {status} ({self.total_duration_s:.1f}s)")
        return "\n".join(lines)


def _find_package_root(pkg: PackageInfo) -> Path | None:
    """Find the project root (directory containing pyproject.toml) for a package."""
    # Package location is like ~/forgespc/src/forgespc/
    # Walk up looking for pyproject.toml
    current = pkg.location
    for _ in range(5):
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return None


def _run_subprocess(cmd: list[str], cwd: Path | None = None, timeout: int = 300) -> tuple[int, str]:
    """Run a subprocess, return (returncode, combined output)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = proc.stdout
        if proc.stderr:
            output += "\n" + proc.stderr
        return proc.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, f"Timed out after {timeout}s"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"


def _stage_lint(packages: list[PackageInfo]) -> StageResult:
    """Run ruff check on all packages."""
    t0 = time.monotonic()
    errors = []
    for pkg in packages:
        root = _find_package_root(pkg)
        if root is None:
            errors.append(f"{pkg.name}: cannot find project root")
            continue
        rc, output = _run_subprocess([sys.executable, "-m", "ruff", "check", "."], cwd=root)
        if rc != 0:
            # Summarize: count violations
            lines = output.strip().splitlines()
            violation_lines = [l for l in lines if l and not l.startswith("Found")]
            errors.append(f"{pkg.name}: {len(violation_lines)} lint violations")
            for line in violation_lines[:3]:
                errors.append(f"  {line}")

    return StageResult(
        stage="lint",
        passed=len(errors) == 0,
        duration_s=time.monotonic() - t0,
        detail=f"Checked {len(packages)} packages",
        errors=errors,
    )


def _stage_test(packages: list[PackageInfo]) -> StageResult:
    """Run pytest on each package."""
    t0 = time.monotonic()
    errors = []
    total_passed = 0
    total_failed = 0

    for pkg in packages:
        root = _find_package_root(pkg)
        if root is None:
            errors.append(f"{pkg.name}: cannot find project root")
            continue
        if not (root / "tests").exists():
            errors.append(f"{pkg.name}: no tests/ directory")
            continue

        rc, output = _run_subprocess(
            [sys.executable, "-m", "pytest", "-q", "--tb=no", "--no-header"],
            cwd=root,
            timeout=120,
        )
        # Parse pytest summary line like "37 passed" or "2 failed, 35 passed"
        last_line = output.strip().splitlines()[-1] if output.strip() else ""
        if rc == 0:
            total_passed += 1
        else:
            total_failed += 1
            errors.append(f"{pkg.name}: {last_line}")

    return StageResult(
        stage="test",
        passed=total_failed == 0,
        duration_s=time.monotonic() - t0,
        detail=f"{total_passed} packages passed, {total_failed} failed",
        errors=errors,
    )


def _stage_contract(scan_result: ScanResult) -> tuple[StageResult, ContractResult]:
    """Run contract enforcement."""
    t0 = time.monotonic()
    contract_result = check(scan_result)

    error_strs = [str(v) for v in contract_result.errors]
    warning_strs = [str(v) for v in contract_result.warnings]

    detail = f"{len(contract_result.errors)} errors, {len(contract_result.warnings)} warnings"

    return StageResult(
        stage="contract",
        passed=contract_result.passed,
        duration_s=time.monotonic() - t0,
        detail=detail,
        errors=error_strs,
    ), contract_result


def _stage_calibrate(scan_result: ScanResult) -> StageResult:
    """Run forgecal across all packages that have calibration adapters."""
    t0 = time.monotonic()

    try:
        from forgecal import discover_adapters, run_calibration
    except ImportError:
        return StageResult(
            stage="calibrate",
            passed=True,
            duration_s=time.monotonic() - t0,
            detail="forgecal not installed — skipped",
        )

    try:
        adapters = discover_adapters()
        if not adapters:
            return StageResult(
                stage="calibrate",
                passed=True,
                duration_s=time.monotonic() - t0,
                detail="No calibration adapters found — skipped",
            )

        report = run_calibration(adapters)
        errors = []
        if not report.is_calibrated:
            for case_result in report.results:
                if not case_result.passed:
                    errors.append(
                        f"{case_result.case.package}/{case_result.case.case_id}: "
                        f"{len(case_result.failures)} failures"
                    )

        return StageResult(
            stage="calibrate",
            passed=report.is_calibrated,
            duration_s=time.monotonic() - t0,
            detail=f"{report.total_cases} cases, {report.pass_rate:.0%} pass rate",
            errors=errors,
        )
    except Exception as exc:
        return StageResult(
            stage="calibrate",
            passed=False,
            duration_s=time.monotonic() - t0,
            detail=f"Calibration error: {exc}",
            errors=[str(exc)],
        )


def _stage_integration(scan_result: ScanResult) -> StageResult:
    """Smoke test: import every discovered package and its top-level modules."""
    import importlib

    t0 = time.monotonic()
    errors = []

    for pkg in scan_result.packages:
        # Test top-level import
        try:
            importlib.import_module(pkg.name)
        except Exception as exc:
            errors.append(f"{pkg.name}: import failed — {exc}")
            continue

        # Test each submodule
        for mod_name in pkg.modules:
            fqn = f"{pkg.name}.{mod_name}"
            try:
                importlib.import_module(fqn)
            except Exception as exc:
                errors.append(f"{fqn}: import failed — {exc}")

    return StageResult(
        stage="integration",
        passed=len(errors) == 0,
        duration_s=time.monotonic() - t0,
        detail=f"Tested {sum(1 + len(p.modules) for p in scan_result.packages)} imports",
        errors=errors,
    )


def _stage_certify(pipeline_result: PipelineResult) -> StageResult:
    """Generate calibration certificate via forgedoc."""
    t0 = time.monotonic()

    try:
        from forgedoc import Document, render
    except ImportError:
        return StageResult(
            stage="certify",
            passed=True,
            duration_s=time.monotonic() - t0,
            detail="forgedoc not installed — skipped",
        )

    try:
        doc = Document(title="Forge Ecosystem Calibration Certificate")

        # Summary section
        summary = doc.add_section("Pipeline Summary")
        for stage in pipeline_result.stages:
            if stage.stage == "certify":
                continue
            status = "PASS" if stage.passed else "FAIL"
            summary.content += f"- {stage.stage}: {status} ({stage.detail})\n"

        # Package inventory
        if pipeline_result.scan_result:
            inv = doc.add_section("Package Inventory")
            headers = ["Package", "Version", "Calibration", "Contract"]
            rows = []
            for pkg in pipeline_result.scan_result.packages:
                cal = "Yes" if pkg.has_calibration else "No"
                # Check contract status
                contract_ok = "Pass"
                if pipeline_result.contract_result:
                    pkg_errors = [
                        v for v in pipeline_result.contract_result.errors
                        if v.package == pkg.name
                    ]
                    if pkg_errors:
                        contract_ok = f"{len(pkg_errors)} errors"
                rows.append([pkg.name, pkg.version, cal, contract_ok])
            inv.add_table(headers, rows)

        cert_bytes = render(doc, format="pdf")

        # Write to a known location
        cert_path = Path.home() / ".forge" / "certificates"
        cert_path.mkdir(parents=True, exist_ok=True)

        from datetime import date
        filename = f"forge_calibration_{date.today().isoformat()}.pdf"
        (cert_path / filename).write_bytes(cert_bytes)

        return StageResult(
            stage="certify",
            passed=True,
            duration_s=time.monotonic() - t0,
            detail=f"Certificate written to {cert_path / filename}",
        )
    except Exception as exc:
        return StageResult(
            stage="certify",
            passed=False,
            duration_s=time.monotonic() - t0,
            detail=f"Certificate generation failed: {exc}",
            errors=[str(exc)],
        )


def run(
    packages: list[str] | None = None,
    stages: list[str] | None = None,
) -> PipelineResult:
    """Run the governance pipeline.

    Args:
        packages: Package names to scan. Defaults to all known packages.
        stages: Stages to run. Defaults to all stages.
            Available: lint, test, contract, calibrate, integration, certify

    Returns:
        PipelineResult with stage results and overall pass/fail.
    """
    t0 = time.monotonic()
    run_stages = stages or STAGES
    result = PipelineResult()

    # Always scan first
    scan_result = scan(packages)
    result.scan_result = scan_result

    if not scan_result.packages:
        result.total_duration_s = time.monotonic() - t0
        return result

    for stage_name in run_stages:
        if stage_name not in STAGES:
            logger.warning("Unknown stage: %s", stage_name)
            continue

        if stage_name == "lint":
            result.stages.append(_stage_lint(scan_result.packages))
        elif stage_name == "test":
            result.stages.append(_stage_test(scan_result.packages))
        elif stage_name == "contract":
            stage_result, contract_result = _stage_contract(scan_result)
            result.stages.append(stage_result)
            result.contract_result = contract_result
        elif stage_name == "calibrate":
            result.stages.append(_stage_calibrate(scan_result))
        elif stage_name == "integration":
            result.stages.append(_stage_integration(scan_result))
        elif stage_name == "certify":
            result.stages.append(_stage_certify(result))

    result.total_duration_s = time.monotonic() - t0
    return result
