"""ForgeGov — Governance, contract enforcement, and CI/CD for the Forge ecosystem.

Discovers installed forge packages, enforces structural contracts,
runs test/calibration/integration pipelines, and coordinates releases.

Usage:
    from forgegov import registry, contracts, pipeline

    # Scan installed forge packages
    packages = registry.scan()

    # Check contracts
    violations = contracts.check(packages)

    # Run full pipeline
    result = pipeline.run(packages)

CLI:
    forgegov run                  # Full pipeline
    forgegov run --stage test     # Single stage
    forgegov check forgespc       # Contract check on one package
    forgegov status               # Quick health report
    forgegov compat               # Compatibility matrix
"""

from .registry import PackageInfo, ScanResult, scan
from .contracts import ContractViolation, check, check_one
from .pipeline import PipelineResult, StageResult, run

__all__ = [
    "PackageInfo",
    "ScanResult",
    "scan",
    "ContractViolation",
    "check",
    "check_one",
    "PipelineResult",
    "StageResult",
    "run",
]

__version__ = "0.1.0"
